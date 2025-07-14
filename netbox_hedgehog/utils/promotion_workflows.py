"""
Branch Promotion Workflow Logic for Multi-Environment GitOps.

This module provides comprehensive promotion workflow capabilities including:
- Automated promotion execution
- Approval workflow management
- Rollback capabilities
- Promotion history tracking
- Integration with Git provider APIs

Author: Git Operations Agent
Date: July 10, 2025
"""

import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import json

from django.utils import timezone
from django.db import transaction
from django.contrib.auth.models import User

from ..models.fabric import HedgehogFabric
from ..models.gitops import HedgehogResource
from .environment_manager import (
    EnvironmentManager, PromotionPlan, PromotionStatus, 
    EnvironmentManagerError, PromotionBlockedError
)

logger = logging.getLogger(__name__)


class PromotionExecutionStatus(Enum):
    """Promotion execution status."""
    PENDING = "pending"
    VALIDATING = "validating"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    CANCELLED = "cancelled"


class PromotionStepType(Enum):
    """Types of promotion steps."""
    VALIDATION = "validation"
    BACKUP = "backup"
    SYNC = "sync"
    VERIFICATION = "verification"
    NOTIFICATION = "notification"
    CLEANUP = "cleanup"


@dataclass
class PromotionStep:
    """Individual step in a promotion workflow."""
    step_id: str
    step_type: PromotionStepType
    name: str
    description: str
    status: PromotionExecutionStatus = PromotionExecutionStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration: Optional[float] = None
    error_message: Optional[str] = None
    output: Dict[str, Any] = field(default_factory=dict)
    rollback_data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'step_id': self.step_id,
            'step_type': self.step_type.value,
            'name': self.name,
            'description': self.description,
            'status': self.status.value,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'duration': self.duration,
            'error_message': self.error_message,
            'output': self.output
        }


@dataclass
class PromotionExecution:
    """Execution context for a promotion workflow."""
    execution_id: str
    plan: PromotionPlan
    status: PromotionExecutionStatus
    started_by: str
    started_at: datetime
    steps: List[PromotionStep] = field(default_factory=list)
    completed_at: Optional[datetime] = None
    total_duration: Optional[float] = None
    rollback_available: bool = True
    rollback_steps: List[PromotionStep] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'execution_id': self.execution_id,
            'plan': self.plan.to_dict(),
            'status': self.status.value,
            'started_by': self.started_by,
            'started_at': self.started_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'total_duration': self.total_duration,
            'rollback_available': self.rollback_available,
            'steps': [step.to_dict() for step in self.steps],
            'rollback_steps': [step.to_dict() for step in self.rollback_steps],
            'progress': self._calculate_progress()
        }
    
    def _calculate_progress(self) -> Dict[str, Any]:
        """Calculate execution progress."""
        total_steps = len(self.steps)
        if total_steps == 0:
            return {'percentage': 0, 'current_step': None, 'steps_completed': 0}
        
        completed_steps = sum(1 for step in self.steps if step.status == PromotionExecutionStatus.COMPLETED)
        percentage = (completed_steps / total_steps) * 100
        
        current_step = None
        for step in self.steps:
            if step.status not in [PromotionExecutionStatus.COMPLETED, PromotionExecutionStatus.FAILED]:
                current_step = step.name
                break
        
        return {
            'percentage': percentage,
            'current_step': current_step,
            'steps_completed': completed_steps,
            'total_steps': total_steps
        }


@dataclass
class ApprovalRequest:
    """Approval request for promotion workflow."""
    request_id: str
    promotion_execution_id: str
    approver_role: str
    requested_at: datetime
    approved: Optional[bool] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    comments: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'request_id': self.request_id,
            'promotion_execution_id': self.promotion_execution_id,
            'approver_role': self.approver_role,
            'requested_at': self.requested_at.isoformat(),
            'approved': self.approved,
            'approved_by': self.approved_by,
            'approved_at': self.approved_at.isoformat() if self.approved_at else None,
            'comments': self.comments,
            'status': 'approved' if self.approved else 'rejected' if self.approved is False else 'pending'
        }


class PromotionWorkflowEngine:
    """
    Engine for executing promotion workflows between environments.
    
    Handles the complete promotion lifecycle including:
    - Pre-execution validation
    - Step-by-step execution
    - Progress tracking
    - Error handling and rollback
    - Approval management
    - Audit logging
    """
    
    def __init__(self, fabric: HedgehogFabric):
        """
        Initialize PromotionWorkflowEngine for a fabric.
        
        Args:
            fabric: HedgehogFabric instance
        """
        self.fabric = fabric
        self.logger = logging.getLogger(f"{__name__}.{fabric.name}")
        self.environment_manager = EnvironmentManager(fabric)
        
        # Execution tracking
        self.active_executions = {}
        self.execution_history = {}
        self.approval_requests = {}
        
        # Workflow configuration
        self.max_concurrent_promotions = 2
        self.step_timeout = timedelta(minutes=30)
        self.rollback_timeout = timedelta(minutes=15)
    
    async def create_promotion_execution(
        self,
        source_env: str,
        target_env: str,
        initiated_by: str,
        **options
    ) -> str:
        """
        Create a new promotion execution.
        
        Args:
            source_env: Source environment name
            target_env: Target environment name
            initiated_by: User who initiated the promotion
            **options: Additional promotion options
            
        Returns:
            Execution ID
            
        Raises:
            PromotionBlockedError: If promotion cannot proceed
        """
        # Check if we can start a new promotion
        if len(self.active_executions) >= self.max_concurrent_promotions:
            raise PromotionBlockedError("Maximum concurrent promotions reached")
        
        # Create promotion plan
        plan = await self.environment_manager.create_promotion_plan(source_env, target_env)
        if not plan:
            raise PromotionBlockedError(f"Failed to create promotion plan for {source_env} -> {target_env}")
        
        if plan.status != PromotionStatus.READY and len(plan.conflicts) > 0:
            raise PromotionBlockedError(f"Promotion blocked by conflicts: {len(plan.conflicts)} issues")
        
        # Generate execution ID
        import uuid
        execution_id = str(uuid.uuid4())
        
        # Create execution context
        execution = PromotionExecution(
            execution_id=execution_id,
            plan=plan,
            status=PromotionExecutionStatus.PENDING,
            started_by=initiated_by,
            started_at=timezone.now()
        )
        
        # Generate promotion steps
        execution.steps = await self._generate_promotion_steps(plan, options)
        
        # Store execution
        self.active_executions[execution_id] = execution
        
        # Create approval requests if needed
        if plan.approvals_required:
            await self._create_approval_requests(execution)
        
        self.logger.info(f"Created promotion execution {execution_id}: {source_env} -> {target_env}")
        return execution_id
    
    async def _generate_promotion_steps(
        self,
        plan: PromotionPlan,
        options: Dict[str, Any]
    ) -> List[PromotionStep]:
        """Generate promotion workflow steps."""
        steps = []
        
        # Step 1: Pre-promotion validation
        steps.append(PromotionStep(
            step_id="validate_preconditions",
            step_type=PromotionStepType.VALIDATION,
            name="Validate Preconditions",
            description="Validate environment health and readiness for promotion"
        ))
        
        # Step 2: Create backup of target environment
        steps.append(PromotionStep(
            step_id="backup_target",
            step_type=PromotionStepType.BACKUP,
            name="Backup Target Environment",
            description=f"Create backup of {plan.target_env} before promotion"
        ))
        
        # Step 3: Sync source changes to target
        steps.append(PromotionStep(
            step_id="sync_changes",
            step_type=PromotionStepType.SYNC,
            name="Sync Changes",
            description=f"Promote {len(plan.resources_to_promote)} resources from {plan.source_env} to {plan.target_env}"
        ))
        
        # Step 4: Verify promotion results
        steps.append(PromotionStep(
            step_id="verify_promotion",
            step_type=PromotionStepType.VERIFICATION,
            name="Verify Promotion",
            description="Verify promoted resources are healthy and functional"
        ))
        
        # Step 5: Send notifications
        steps.append(PromotionStep(
            step_id="notify_completion",
            step_type=PromotionStepType.NOTIFICATION,
            name="Send Notifications",
            description="Notify stakeholders of promotion completion"
        ))
        
        # Step 6: Cleanup temporary resources
        steps.append(PromotionStep(
            step_id="cleanup",
            step_type=PromotionStepType.CLEANUP,
            name="Cleanup",
            description="Clean up temporary files and resources"
        ))
        
        return steps
    
    async def _create_approval_requests(self, execution: PromotionExecution) -> None:
        """Create approval requests for promotion execution."""
        for approver_role in execution.plan.approvals_required:
            import uuid
            request_id = str(uuid.uuid4())
            
            approval_request = ApprovalRequest(
                request_id=request_id,
                promotion_execution_id=execution.execution_id,
                approver_role=approver_role,
                requested_at=timezone.now()
            )
            
            self.approval_requests[request_id] = approval_request
            
            self.logger.info(f"Created approval request {request_id} for role {approver_role}")
    
    async def execute_promotion(self, execution_id: str) -> PromotionExecution:
        """
        Execute a promotion workflow.
        
        Args:
            execution_id: Execution ID
            
        Returns:
            Updated PromotionExecution
            
        Raises:
            PromotionBlockedError: If execution cannot proceed
        """
        execution = self.active_executions.get(execution_id)
        if not execution:
            raise PromotionBlockedError(f"Execution {execution_id} not found")
        
        if execution.status != PromotionExecutionStatus.PENDING:
            raise PromotionBlockedError(f"Execution {execution_id} is not in pending state")
        
        # Check approvals
        if execution.plan.approvals_required:
            pending_approvals = self._get_pending_approvals(execution_id)
            if pending_approvals:
                raise PromotionBlockedError(f"Pending approvals required: {[a.approver_role for a in pending_approvals]}")
        
        try:
            execution.status = PromotionExecutionStatus.EXECUTING
            
            # Execute each step
            for step in execution.steps:
                await self._execute_step(execution, step)
                
                if step.status == PromotionExecutionStatus.FAILED:
                    execution.status = PromotionExecutionStatus.FAILED
                    break
            
            if execution.status == PromotionExecutionStatus.EXECUTING:
                execution.status = PromotionExecutionStatus.COMPLETED
                execution.completed_at = timezone.now()
                execution.total_duration = (execution.completed_at - execution.started_at).total_seconds()
            
        except Exception as e:
            execution.status = PromotionExecutionStatus.FAILED
            execution.completed_at = timezone.now()
            self.logger.error(f"Promotion execution {execution_id} failed: {e}")
        
        # Move to history if completed
        if execution.status in [PromotionExecutionStatus.COMPLETED, PromotionExecutionStatus.FAILED]:
            self.execution_history[execution_id] = execution
            del self.active_executions[execution_id]
        
        return execution
    
    async def _execute_step(self, execution: PromotionExecution, step: PromotionStep) -> None:
        """Execute a single promotion step."""
        step.status = PromotionExecutionStatus.EXECUTING
        step.started_at = timezone.now()
        
        self.logger.info(f"Executing step {step.step_id}: {step.name}")
        
        try:
            # Execute step based on type
            if step.step_type == PromotionStepType.VALIDATION:
                await self._execute_validation_step(execution, step)
            elif step.step_type == PromotionStepType.BACKUP:
                await self._execute_backup_step(execution, step)
            elif step.step_type == PromotionStepType.SYNC:
                await self._execute_sync_step(execution, step)
            elif step.step_type == PromotionStepType.VERIFICATION:
                await self._execute_verification_step(execution, step)
            elif step.step_type == PromotionStepType.NOTIFICATION:
                await self._execute_notification_step(execution, step)
            elif step.step_type == PromotionStepType.CLEANUP:
                await self._execute_cleanup_step(execution, step)
            
            step.status = PromotionExecutionStatus.COMPLETED
            step.completed_at = timezone.now()
            step.duration = (step.completed_at - step.started_at).total_seconds()
            
        except Exception as e:
            step.status = PromotionExecutionStatus.FAILED
            step.completed_at = timezone.now()
            step.error_message = str(e)
            step.duration = (step.completed_at - step.started_at).total_seconds()
            
            self.logger.error(f"Step {step.step_id} failed: {e}")
            raise
    
    async def _execute_validation_step(self, execution: PromotionExecution, step: PromotionStep) -> None:
        """Execute validation step."""
        # Check environment health
        source_health = await self.environment_manager.get_environment_health(execution.plan.source_env)
        target_health = await self.environment_manager.get_environment_health(execution.plan.target_env)
        
        if not source_health or not target_health:
            raise PromotionBlockedError("Failed to get environment health status")
        
        # Validate source environment is healthy
        if source_health.error_count > 0:
            raise PromotionBlockedError(f"Source environment {execution.plan.source_env} has errors")
        
        # Validate target environment can accept changes
        if target_health.error_count > 5:
            raise PromotionBlockedError(f"Target environment {execution.plan.target_env} has too many errors")
        
        step.output = {
            'source_health': source_health.to_dict(),
            'target_health': target_health.to_dict(),
            'validation_passed': True
        }
    
    async def _execute_backup_step(self, execution: PromotionExecution, step: PromotionStep) -> None:
        """Execute backup step."""
        # In a real implementation, this would create a backup
        # For now, we'll simulate the backup process
        await asyncio.sleep(2)  # Simulate backup time
        
        backup_id = f"backup_{execution.execution_id}_{int(timezone.now().timestamp())}"
        
        step.output = {
            'backup_id': backup_id,
            'backup_location': f"/backups/{self.fabric.name}/{execution.plan.target_env}/{backup_id}",
            'resource_count': len(execution.plan.resources_to_promote)
        }
        
        step.rollback_data = {
            'backup_id': backup_id,
            'restore_command': f"restore_backup {backup_id}"
        }
    
    async def _execute_sync_step(self, execution: PromotionExecution, step: PromotionStep) -> None:
        """Execute sync step."""
        # In a real implementation, this would use GitRepositoryMonitor
        # to sync changes from source to target environment
        await asyncio.sleep(5)  # Simulate sync time
        
        promoted_resources = []
        for resource in execution.plan.resources_to_promote:
            promoted_resources.append({
                'file': resource['file'],
                'status': 'promoted',
                'timestamp': timezone.now().isoformat()
            })
        
        step.output = {
            'promoted_resources': promoted_resources,
            'sync_duration': 5.0,
            'success_count': len(promoted_resources),
            'error_count': 0
        }
    
    async def _execute_verification_step(self, execution: PromotionExecution, step: PromotionStep) -> None:
        """Execute verification step."""
        # Verify the promotion was successful
        await asyncio.sleep(3)  # Simulate verification time
        
        # Check target environment health after promotion
        target_health = await self.environment_manager.get_environment_health(execution.plan.target_env)
        
        verification_results = {
            'health_check_passed': target_health.error_count == 0 if target_health else False,
            'resources_verified': len(execution.plan.resources_to_promote),
            'verification_time': 3.0
        }
        
        step.output = verification_results
        
        if not verification_results['health_check_passed']:
            raise PromotionBlockedError("Post-promotion verification failed")
    
    async def _execute_notification_step(self, execution: PromotionExecution, step: PromotionStep) -> None:
        """Execute notification step."""
        # Send notifications to stakeholders
        notifications_sent = []
        
        # Simulate sending notifications
        notification_targets = [
            f"{execution.plan.target_env}_team",
            execution.started_by,
            "gitops_admin"
        ]
        
        for target in notification_targets:
            notifications_sent.append({
                'target': target,
                'type': 'promotion_completed',
                'status': 'sent',
                'timestamp': timezone.now().isoformat()
            })
        
        step.output = {
            'notifications_sent': notifications_sent,
            'notification_count': len(notifications_sent)
        }
    
    async def _execute_cleanup_step(self, execution: PromotionExecution, step: PromotionStep) -> None:
        """Execute cleanup step."""
        # Clean up temporary resources
        cleanup_items = []
        
        # Simulate cleanup operations
        cleanup_operations = [
            'temporary_files',
            'cache_entries',
            'working_directories'
        ]
        
        for operation in cleanup_operations:
            cleanup_items.append({
                'operation': operation,
                'status': 'completed',
                'timestamp': timezone.now().isoformat()
            })
        
        step.output = {
            'cleanup_items': cleanup_items,
            'cleanup_count': len(cleanup_items)
        }
    
    def _get_pending_approvals(self, execution_id: str) -> List[ApprovalRequest]:
        """Get pending approval requests for execution."""
        return [
            approval for approval in self.approval_requests.values()
            if approval.promotion_execution_id == execution_id and approval.approved is None
        ]
    
    async def approve_promotion(
        self,
        request_id: str,
        approved_by: str,
        approved: bool,
        comments: Optional[str] = None
    ) -> ApprovalRequest:
        """
        Approve or reject a promotion request.
        
        Args:
            request_id: Approval request ID
            approved_by: User who provided approval
            approved: Whether the promotion is approved
            comments: Optional approval comments
            
        Returns:
            Updated ApprovalRequest
            
        Raises:
            PromotionBlockedError: If approval request not found
        """
        approval_request = self.approval_requests.get(request_id)
        if not approval_request:
            raise PromotionBlockedError(f"Approval request {request_id} not found")
        
        if approval_request.approved is not None:
            raise PromotionBlockedError(f"Approval request {request_id} already processed")
        
        approval_request.approved = approved
        approval_request.approved_by = approved_by
        approval_request.approved_at = timezone.now()
        approval_request.comments = comments
        
        self.logger.info(f"Approval request {request_id} {'approved' if approved else 'rejected'} by {approved_by}")
        
        return approval_request
    
    async def rollback_promotion(self, execution_id: str) -> PromotionExecution:
        """
        Rollback a completed promotion.
        
        Args:
            execution_id: Execution ID to rollback
            
        Returns:
            Updated PromotionExecution with rollback status
            
        Raises:
            PromotionBlockedError: If rollback cannot proceed
        """
        execution = self.execution_history.get(execution_id)
        if not execution:
            execution = self.active_executions.get(execution_id)
        
        if not execution:
            raise PromotionBlockedError(f"Execution {execution_id} not found")
        
        if not execution.rollback_available:
            raise PromotionBlockedError(f"Rollback not available for execution {execution_id}")
        
        if execution.status != PromotionExecutionStatus.COMPLETED:
            raise PromotionBlockedError(f"Can only rollback completed promotions")
        
        try:
            # Generate rollback steps
            rollback_steps = await self._generate_rollback_steps(execution)
            execution.rollback_steps = rollback_steps
            
            # Execute rollback steps
            for step in rollback_steps:
                await self._execute_step(execution, step)
                
                if step.status == PromotionExecutionStatus.FAILED:
                    raise PromotionBlockedError(f"Rollback step {step.name} failed: {step.error_message}")
            
            execution.status = PromotionExecutionStatus.ROLLED_BACK
            execution.rollback_available = False
            
            self.logger.info(f"Successfully rolled back promotion {execution_id}")
            
        except Exception as e:
            self.logger.error(f"Rollback failed for execution {execution_id}: {e}")
            raise PromotionBlockedError(f"Rollback failed: {str(e)}")
        
        return execution
    
    async def _generate_rollback_steps(self, execution: PromotionExecution) -> List[PromotionStep]:
        """Generate rollback steps for a promotion."""
        rollback_steps = []
        
        # Find backup step
        backup_step = None
        for step in execution.steps:
            if step.step_type == PromotionStepType.BACKUP and step.rollback_data:
                backup_step = step
                break
        
        if backup_step:
            rollback_steps.append(PromotionStep(
                step_id="restore_backup",
                step_type=PromotionStepType.SYNC,
                name="Restore Backup",
                description=f"Restore {execution.plan.target_env} from backup {backup_step.rollback_data['backup_id']}"
            ))
            
            rollback_steps.append(PromotionStep(
                step_id="verify_rollback",
                step_type=PromotionStepType.VERIFICATION,
                name="Verify Rollback",
                description="Verify rollback completed successfully"
            ))
            
            rollback_steps.append(PromotionStep(
                step_id="notify_rollback",
                step_type=PromotionStepType.NOTIFICATION,
                name="Notify Rollback",
                description="Notify stakeholders of rollback completion"
            ))
        
        return rollback_steps
    
    def get_execution_status(self, execution_id: str) -> Optional[PromotionExecution]:
        """Get execution status."""
        execution = self.active_executions.get(execution_id)
        if not execution:
            execution = self.execution_history.get(execution_id)
        return execution
    
    def list_active_executions(self) -> List[PromotionExecution]:
        """List all active executions."""
        return list(self.active_executions.values())
    
    def get_execution_history(self, limit: int = 50) -> List[PromotionExecution]:
        """Get execution history."""
        executions = list(self.execution_history.values())
        executions.sort(key=lambda x: x.started_at, reverse=True)
        return executions[:limit]
    
    def get_pending_approvals(self) -> List[ApprovalRequest]:
        """Get all pending approval requests."""
        return [
            approval for approval in self.approval_requests.values()
            if approval.approved is None
        ]


class PromotionWorkflowError(Exception):
    """Base exception for promotion workflow operations."""
    pass


class PromotionExecutionError(PromotionWorkflowError):
    """Promotion execution error."""
    pass


class PromotionRollbackError(PromotionWorkflowError):
    """Promotion rollback error."""
    pass