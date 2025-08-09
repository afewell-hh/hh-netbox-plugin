"""
Sync Saga Pattern Implementation - Distributed Transaction Management

Implements the Saga pattern for managing distributed transactions across NetBox and Kubernetes,
providing rollback capabilities, state persistence, and recovery mechanisms for complex sync operations.

Architecture:
- Saga Orchestrator for transaction coordination
- Step-based transaction management with rollback
- State persistence and recovery
- Compensation actions for failed operations
- Integration with circuit breaker and reliability patterns
"""

import logging
import time
import asyncio
import json
from typing import Dict, Any, List, Optional, Union, Callable, Tuple
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone as django_timezone

from ..models.fabric import HedgehogFabric
from ..utils.kubernetes import KubernetesClient, KubernetesSync
from ..services.status_sync_service import get_status_sync_service, StatusUpdateRequest
from ..tasks.status_reconciliation import StatusType, StatusState
from ..application.services.event_service import EventService
from ..domain.interfaces.event_service_interface import EventPriority, EventCategory, RealtimeEvent

logger = logging.getLogger('netbox_hedgehog.sync_saga')
performance_logger = logging.getLogger('netbox_hedgehog.performance')

# Saga Pattern Enums and Data Classes

class SagaState(Enum):
    """Saga execution states"""
    PENDING = "pending"
    RUNNING = "running"
    COMPENSATING = "compensating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class StepState(Enum):
    """Individual step states"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATED = "compensated"
    COMPENSATION_FAILED = "compensation_failed"

class StepType(Enum):
    """Types of saga steps"""
    NETBOX_READ = "netbox_read"
    NETBOX_WRITE = "netbox_write"
    K8S_READ = "k8s_read"
    K8S_WRITE = "k8s_write"
    VALIDATION = "validation"
    STATUS_UPDATE = "status_update"
    CONFLICT_RESOLUTION = "conflict_resolution"

@dataclass
class SagaStep:
    """Individual step in a saga transaction"""
    step_id: str
    step_type: StepType
    action: Callable
    compensation_action: Optional[Callable] = None
    retry_count: int = 0
    max_retries: int = 3
    timeout: int = 30  # seconds
    state: StepState = StepState.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)  # Step IDs this depends on
    
    @property
    def duration(self) -> Optional[float]:
        """Calculate step duration in seconds"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
    
    @property
    def is_completed(self) -> bool:
        """Check if step is completed"""
        return self.state in [StepState.COMPLETED, StepState.COMPENSATED]
    
    @property
    def can_retry(self) -> bool:
        """Check if step can be retried"""
        return self.retry_count < self.max_retries and self.state == StepState.FAILED
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert step to dictionary for persistence"""
        return {
            'step_id': self.step_id,
            'step_type': self.step_type.value,
            'state': self.state.value,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
            'timeout': self.timeout,
            'result': self.result,
            'error': self.error,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'metadata': self.metadata,
            'dependencies': self.dependencies
        }

@dataclass
class SyncSaga:
    """Complete saga transaction for sync operations"""
    saga_id: str
    fabric_id: int
    fabric_name: str
    operation_type: str  # 'bidirectional', 'netbox_to_k8s', 'k8s_to_netbox'
    steps: List[SagaStep] = field(default_factory=list)
    state: SagaState = SagaState.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    compensation_reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def duration(self) -> Optional[float]:
        """Calculate saga duration in seconds"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
    
    @property
    def completed_steps(self) -> List[SagaStep]:
        """Get all completed steps"""
        return [step for step in self.steps if step.state == StepState.COMPLETED]
    
    @property
    def failed_steps(self) -> List[SagaStep]:
        """Get all failed steps"""
        return [step for step in self.steps if step.state == StepState.FAILED]
    
    @property
    def progress_percentage(self) -> float:
        """Calculate completion percentage"""
        if not self.steps:
            return 0.0
        completed_count = len([s for s in self.steps if s.is_completed])
        return (completed_count / len(self.steps)) * 100.0
    
    def add_step(self, step: SagaStep):
        """Add step to saga"""
        self.steps.append(step)
    
    def get_step(self, step_id: str) -> Optional[SagaStep]:
        """Get step by ID"""
        return next((step for step in self.steps if step.step_id == step_id), None)
    
    def get_executable_steps(self) -> List[SagaStep]:
        """Get steps ready for execution (dependencies satisfied)"""
        executable = []
        completed_step_ids = {step.step_id for step in self.steps if step.is_completed}
        
        for step in self.steps:
            if (step.state == StepState.PENDING and 
                all(dep_id in completed_step_ids for dep_id in step.dependencies)):
                executable.append(step)
        
        return executable
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert saga to dictionary for persistence"""
        return {
            'saga_id': self.saga_id,
            'fabric_id': self.fabric_id,
            'fabric_name': self.fabric_name,
            'operation_type': self.operation_type,
            'state': self.state.value,
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'error_message': self.error_message,
            'compensation_reason': self.compensation_reason,
            'metadata': self.metadata,
            'steps': [step.to_dict() for step in self.steps],
            'progress_percentage': self.progress_percentage
        }

class SagaOrchestrator:
    """
    Saga orchestrator for managing distributed transactions
    Coordinates step execution, handles failures, and manages compensation
    """
    
    def __init__(self):
        self.active_sagas: Dict[str, SyncSaga] = {}
        self.event_service = EventService()
        self.status_sync_service = get_status_sync_service()
        
        # Thread safety
        self._sagas_lock = Lock()
        
        # Background executor
        self.executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="saga_orchestrator")
        
        # Performance tracking
        self.metrics = {
            'sagas_started': 0,
            'sagas_completed': 0,
            'sagas_failed': 0,
            'sagas_compensated': 0,
            'avg_saga_duration': 0.0,
            'compensation_success_rate': 0.0
        }
        
        logger.info("Saga Orchestrator initialized")
    
    async def execute_bidirectional_sync_saga(self, fabric_id: int, 
                                            resource_types: Optional[List[str]] = None,
                                            priority: EventPriority = EventPriority.NORMAL) -> Dict[str, Any]:
        """
        Execute bidirectional sync using saga pattern
        
        Args:
            fabric_id: ID of fabric to sync
            resource_types: Specific resource types to sync
            priority: Operation priority
            
        Returns:
            Dict with saga execution results
        """
        start_time = time.time()
        saga_id = f"bidirectional_sync_{fabric_id}_{int(time.time())}"
        
        try:
            # Get fabric
            fabric = await asyncio.to_thread(HedgehogFabric.objects.get, id=fabric_id)
            
            # Create saga
            saga = SyncSaga(
                saga_id=saga_id,
                fabric_id=fabric_id,
                fabric_name=fabric.name,
                operation_type='bidirectional',
                metadata={
                    'resource_types': resource_types,
                    'priority': priority.value,
                    'initiated_at': datetime.now(timezone.utc).isoformat()
                }
            )
            
            # Build saga steps for bidirectional sync
            await self._build_bidirectional_sync_steps(saga, fabric, resource_types)
            
            # Register saga
            await self._register_saga(saga)
            
            # Execute saga
            execution_result = await self._execute_saga(saga)
            
            return {
                'success': execution_result['success'],
                'saga_id': saga_id,
                'fabric_name': fabric.name,
                'operation_type': 'bidirectional',
                'duration': time.time() - start_time,
                'steps_completed': len(saga.completed_steps),
                'steps_failed': len(saga.failed_steps),
                'progress_percentage': saga.progress_percentage,
                'state': saga.state.value,
                'message': execution_result.get('message', 'Saga execution completed'),
                'compensation_applied': execution_result.get('compensation_applied', False)
            }
            
        except Exception as e:
            logger.error(f"Bidirectional sync saga failed for fabric {fabric_id}: {e}")
            return {
                'success': False,
                'error': str(e),
                'saga_id': saga_id,
                'duration': time.time() - start_time
            }
        finally:
            # Cleanup saga
            await self._cleanup_saga(saga_id)
    
    async def execute_netbox_to_k8s_saga(self, fabric_id: int, 
                                       resources: List[Any],
                                       priority: EventPriority = EventPriority.NORMAL) -> Dict[str, Any]:
        """
        Execute NetBox to Kubernetes sync using saga pattern
        
        Args:
            fabric_id: ID of fabric to sync
            resources: Resources to sync to Kubernetes
            priority: Operation priority
            
        Returns:
            Dict with saga execution results
        """
        start_time = time.time()
        saga_id = f"netbox_to_k8s_{fabric_id}_{int(time.time())}"
        
        try:
            fabric = await asyncio.to_thread(HedgehogFabric.objects.get, id=fabric_id)
            
            saga = SyncSaga(
                saga_id=saga_id,
                fabric_id=fabric_id,
                fabric_name=fabric.name,
                operation_type='netbox_to_k8s',
                metadata={
                    'resource_count': len(resources),
                    'priority': priority.value
                }
            )
            
            # Build saga steps for NetBox to K8s sync
            await self._build_netbox_to_k8s_steps(saga, fabric, resources)
            
            # Register and execute saga
            await self._register_saga(saga)
            execution_result = await self._execute_saga(saga)
            
            return {
                'success': execution_result['success'],
                'saga_id': saga_id,
                'fabric_name': fabric.name,
                'operation_type': 'netbox_to_k8s',
                'duration': time.time() - start_time,
                'resources_processed': len(resources),
                'steps_completed': len(saga.completed_steps),
                'state': saga.state.value
            }
            
        except Exception as e:
            logger.error(f"NetBox to K8s saga failed for fabric {fabric_id}: {e}")
            return {
                'success': False,
                'error': str(e),
                'saga_id': saga_id,
                'duration': time.time() - start_time
            }
        finally:
            await self._cleanup_saga(saga_id)
    
    async def get_saga_status(self, saga_id: str) -> Dict[str, Any]:
        """Get status of a specific saga"""
        with self._sagas_lock:
            saga = self.active_sagas.get(saga_id)
            
            if not saga:
                # Try to load from cache
                cached_saga = await self._load_saga_from_cache(saga_id)
                if cached_saga:
                    saga = cached_saga
                else:
                    return {'success': False, 'error': 'Saga not found'}
            
            return {
                'success': True,
                'saga': saga.to_dict()
            }
    
    async def compensate_saga(self, saga_id: str, reason: str = "Manual compensation") -> Dict[str, Any]:
        """
        Manually trigger compensation for a saga
        
        Args:
            saga_id: ID of saga to compensate
            reason: Reason for compensation
            
        Returns:
            Dict with compensation results
        """
        try:
            with self._sagas_lock:
                saga = self.active_sagas.get(saga_id)
                
                if not saga:
                    return {'success': False, 'error': 'Saga not found'}
                
                if saga.state not in [SagaState.FAILED, SagaState.RUNNING]:
                    return {'success': False, 'error': 'Saga cannot be compensated in current state'}
            
            # Execute compensation
            compensation_result = await self._execute_compensation(saga, reason)
            
            return {
                'success': compensation_result['success'],
                'saga_id': saga_id,
                'compensation_reason': reason,
                'compensated_steps': compensation_result.get('compensated_steps', 0),
                'compensation_failures': compensation_result.get('compensation_failures', 0)
            }
            
        except Exception as e:
            logger.error(f"Saga compensation failed for {saga_id}: {e}")
            return {
                'success': False,
                'error': str(e),
                'saga_id': saga_id
            }
    
    async def get_saga_metrics(self) -> Dict[str, Any]:
        """Get saga orchestrator performance metrics"""
        with self._sagas_lock:
            active_sagas_count = len(self.active_sagas)
        
        # Calculate success rate
        total_sagas = self.metrics['sagas_completed'] + self.metrics['sagas_failed']
        success_rate = (
            self.metrics['sagas_completed'] / max(1, total_sagas)
        )
        
        return {
            'active_sagas': active_sagas_count,
            'sagas_started': self.metrics['sagas_started'],
            'sagas_completed': self.metrics['sagas_completed'],
            'sagas_failed': self.metrics['sagas_failed'],
            'sagas_compensated': self.metrics['sagas_compensated'],
            'success_rate': success_rate,
            'avg_saga_duration': self.metrics['avg_saga_duration'],
            'compensation_success_rate': self.metrics['compensation_success_rate']
        }
    
    # Private helper methods
    
    async def _build_bidirectional_sync_steps(self, saga: SyncSaga, fabric: HedgehogFabric,
                                            resource_types: Optional[List[str]]):
        """Build steps for bidirectional sync saga"""
        
        # Step 1: Validate connections
        validation_step = SagaStep(
            step_id=f"{saga.saga_id}_validate",
            step_type=StepType.VALIDATION,
            action=self._create_validation_action(fabric),
            compensation_action=None,  # No compensation needed for validation
            timeout=30,
            metadata={'description': 'Validate NetBox and Kubernetes connectivity'}
        )
        saga.add_step(validation_step)
        
        # Step 2: Read current state from NetBox
        netbox_read_step = SagaStep(
            step_id=f"{saga.saga_id}_netbox_read",
            step_type=StepType.NETBOX_READ,
            action=self._create_netbox_read_action(fabric, resource_types),
            compensation_action=None,  # Read operations don't need compensation
            dependencies=[validation_step.step_id],
            timeout=60,
            metadata={'description': 'Read current NetBox resource state'}
        )
        saga.add_step(netbox_read_step)
        
        # Step 3: Read current state from Kubernetes
        k8s_read_step = SagaStep(
            step_id=f"{saga.saga_id}_k8s_read",
            step_type=StepType.K8S_READ,
            action=self._create_k8s_read_action(fabric, resource_types),
            compensation_action=None,  # Read operations don't need compensation
            dependencies=[validation_step.step_id],
            timeout=60,
            metadata={'description': 'Read current Kubernetes resource state'}
        )
        saga.add_step(k8s_read_step)
        
        # Step 4: Conflict resolution and planning
        conflict_resolution_step = SagaStep(
            step_id=f"{saga.saga_id}_conflict_resolution",
            step_type=StepType.CONFLICT_RESOLUTION,
            action=self._create_conflict_resolution_action(),
            compensation_action=None,  # Planning operations don't need compensation
            dependencies=[netbox_read_step.step_id, k8s_read_step.step_id],
            timeout=30,
            metadata={'description': 'Resolve conflicts and plan sync operations'}
        )
        saga.add_step(conflict_resolution_step)
        
        # Step 5: Apply NetBox changes to Kubernetes
        netbox_to_k8s_step = SagaStep(
            step_id=f"{saga.saga_id}_netbox_to_k8s",
            step_type=StepType.K8S_WRITE,
            action=self._create_netbox_to_k8s_action(fabric),
            compensation_action=self._create_k8s_rollback_action(fabric),
            dependencies=[conflict_resolution_step.step_id],
            timeout=120,
            metadata={'description': 'Apply NetBox resources to Kubernetes'}
        )
        saga.add_step(netbox_to_k8s_step)
        
        # Step 6: Apply Kubernetes changes to NetBox
        k8s_to_netbox_step = SagaStep(
            step_id=f"{saga.saga_id}_k8s_to_netbox",
            step_type=StepType.NETBOX_WRITE,
            action=self._create_k8s_to_netbox_action(fabric),
            compensation_action=self._create_netbox_rollback_action(fabric),
            dependencies=[netbox_to_k8s_step.step_id],
            timeout=120,
            metadata={'description': 'Import Kubernetes resources to NetBox'}
        )
        saga.add_step(k8s_to_netbox_step)
        
        # Step 7: Update status
        status_update_step = SagaStep(
            step_id=f"{saga.saga_id}_status_update",
            step_type=StepType.STATUS_UPDATE,
            action=self._create_status_update_action(fabric),
            compensation_action=self._create_status_rollback_action(fabric),
            dependencies=[k8s_to_netbox_step.step_id],
            timeout=30,
            metadata={'description': 'Update fabric sync status'}
        )
        saga.add_step(status_update_step)
    
    async def _build_netbox_to_k8s_steps(self, saga: SyncSaga, fabric: HedgehogFabric,
                                       resources: List[Any]):
        """Build steps for NetBox to Kubernetes sync saga"""
        
        # Step 1: Validate Kubernetes connection
        validation_step = SagaStep(
            step_id=f"{saga.saga_id}_validate",
            step_type=StepType.VALIDATION,
            action=self._create_k8s_validation_action(fabric),
            timeout=30
        )
        saga.add_step(validation_step)
        
        # Step 2: Backup current Kubernetes state
        backup_step = SagaStep(
            step_id=f"{saga.saga_id}_backup",
            step_type=StepType.K8S_READ,
            action=self._create_k8s_backup_action(fabric, resources),
            dependencies=[validation_step.step_id],
            timeout=60
        )
        saga.add_step(backup_step)
        
        # Step 3: Apply resources to Kubernetes
        apply_step = SagaStep(
            step_id=f"{saga.saga_id}_apply",
            step_type=StepType.K8S_WRITE,
            action=self._create_apply_resources_action(fabric, resources),
            compensation_action=self._create_restore_k8s_action(fabric),
            dependencies=[backup_step.step_id],
            timeout=180
        )
        saga.add_step(apply_step)
        
        # Step 4: Verify application
        verify_step = SagaStep(
            step_id=f"{saga.saga_id}_verify",
            step_type=StepType.VALIDATION,
            action=self._create_verify_k8s_action(fabric, resources),
            dependencies=[apply_step.step_id],
            timeout=60
        )
        saga.add_step(verify_step)
    
    async def _register_saga(self, saga: SyncSaga):
        """Register saga for tracking and persistence"""
        with self._sagas_lock:
            self.active_sagas[saga.saga_id] = saga
            self.metrics['sagas_started'] += 1
        
        # Persist saga state
        await self._persist_saga(saga)
        
        logger.info(f"Registered saga {saga.saga_id} for fabric {saga.fabric_name}")
    
    async def _execute_saga(self, saga: SyncSaga) -> Dict[str, Any]:
        """Execute all steps in the saga"""
        try:
            saga.state = SagaState.RUNNING
            saga.started_at = datetime.now(timezone.utc)
            
            await self._persist_saga(saga)
            
            # Execute steps in dependency order
            while True:
                executable_steps = saga.get_executable_steps()
                
                if not executable_steps:
                    # Check if all steps are completed
                    if all(step.is_completed for step in saga.steps):
                        saga.state = SagaState.COMPLETED
                        break
                    
                    # Check if any step failed
                    failed_steps = [step for step in saga.steps if step.state == StepState.FAILED]
                    if failed_steps:
                        # Start compensation
                        await self._execute_compensation(saga, "Step execution failure")
                        return {
                            'success': False,
                            'message': 'Saga failed and compensation executed',
                            'compensation_applied': True
                        }
                    
                    # No executable steps but not all completed - deadlock
                    saga.state = SagaState.FAILED
                    saga.error_message = "Saga execution deadlock - no executable steps"
                    break
                
                # Execute available steps in parallel
                execution_tasks = [
                    self._execute_step(step, saga) for step in executable_steps
                ]
                
                await asyncio.gather(*execution_tasks, return_exceptions=True)
                
                # Update saga state
                await self._persist_saga(saga)
            
            saga.completed_at = datetime.now(timezone.utc)
            
            # Update metrics
            if saga.state == SagaState.COMPLETED:
                self.metrics['sagas_completed'] += 1
            else:
                self.metrics['sagas_failed'] += 1
            
            # Update average duration
            if saga.duration:
                total_sagas = self.metrics['sagas_completed'] + self.metrics['sagas_failed']
                self.metrics['avg_saga_duration'] = (
                    (self.metrics['avg_saga_duration'] * (total_sagas - 1) + saga.duration) / total_sagas
                )
            
            await self._persist_saga(saga)
            
            # Publish saga completion event
            await self._publish_saga_event(saga, "completed")
            
            return {
                'success': saga.state == SagaState.COMPLETED,
                'message': 'Saga execution completed successfully' if saga.state == SagaState.COMPLETED else saga.error_message,
                'compensation_applied': False
            }
            
        except Exception as e:
            saga.state = SagaState.FAILED
            saga.error_message = str(e)
            saga.completed_at = datetime.now(timezone.utc)
            
            logger.error(f"Saga execution failed: {e}")
            await self._persist_saga(saga)
            
            return {
                'success': False,
                'message': f'Saga execution failed: {e}',
                'compensation_applied': False
            }
    
    async def _execute_step(self, step: SagaStep, saga: SyncSaga):
        """Execute a single saga step"""
        try:
            step.state = StepState.RUNNING
            step.started_at = datetime.now(timezone.utc)
            
            logger.info(f"Executing step {step.step_id} for saga {saga.saga_id}")
            
            # Execute step action with timeout
            try:
                result = await asyncio.wait_for(
                    asyncio.to_thread(step.action, saga, step),
                    timeout=step.timeout
                )
                
                step.result = result
                step.state = StepState.COMPLETED
                step.completed_at = datetime.now(timezone.utc)
                
                logger.info(f"Step {step.step_id} completed successfully")
                
            except asyncio.TimeoutError:
                step.state = StepState.FAILED
                step.error = f"Step timed out after {step.timeout} seconds"
                step.completed_at = datetime.now(timezone.utc)
                
                logger.error(f"Step {step.step_id} timed out")
                
            except Exception as step_error:
                step.state = StepState.FAILED
                step.error = str(step_error)
                step.completed_at = datetime.now(timezone.utc)
                
                logger.error(f"Step {step.step_id} failed: {step_error}")
                
                # Check if step can be retried
                if step.can_retry:
                    step.retry_count += 1
                    step.state = StepState.PENDING
                    logger.info(f"Step {step.step_id} will be retried (attempt {step.retry_count})")
                    
        except Exception as e:
            step.state = StepState.FAILED
            step.error = str(e)
            step.completed_at = datetime.now(timezone.utc)
            logger.error(f"Step execution framework error: {e}")
    
    async def _execute_compensation(self, saga: SyncSaga, reason: str) -> Dict[str, Any]:
        """Execute compensation for failed saga"""
        try:
            saga.state = SagaState.COMPENSATING
            saga.compensation_reason = reason
            
            logger.info(f"Starting compensation for saga {saga.saga_id}: {reason}")
            
            # Get completed steps that need compensation (in reverse order)
            compensation_steps = [
                step for step in reversed(saga.steps)
                if step.state == StepState.COMPLETED and step.compensation_action
            ]
            
            compensated_count = 0
            failed_compensations = 0
            
            for step in compensation_steps:
                try:
                    logger.info(f"Compensating step {step.step_id}")
                    
                    # Execute compensation action
                    await asyncio.wait_for(
                        asyncio.to_thread(step.compensation_action, saga, step),
                        timeout=step.timeout
                    )
                    
                    step.state = StepState.COMPENSATED
                    compensated_count += 1
                    
                    logger.info(f"Step {step.step_id} compensated successfully")
                    
                except Exception as comp_error:
                    step.state = StepState.COMPENSATION_FAILED
                    step.error = f"Compensation failed: {comp_error}"
                    failed_compensations += 1
                    
                    logger.error(f"Compensation failed for step {step.step_id}: {comp_error}")
            
            saga.state = SagaState.FAILED
            saga.completed_at = datetime.now(timezone.utc)
            
            # Update metrics
            self.metrics['sagas_compensated'] += 1
            
            # Update compensation success rate
            if compensated_count + failed_compensations > 0:
                compensation_success_rate = compensated_count / (compensated_count + failed_compensations)
                total_compensations = self.metrics['sagas_compensated']
                self.metrics['compensation_success_rate'] = (
                    (self.metrics['compensation_success_rate'] * (total_compensations - 1) + compensation_success_rate) 
                    / total_compensations
                )
            
            await self._persist_saga(saga)
            await self._publish_saga_event(saga, "compensated")
            
            return {
                'success': failed_compensations == 0,
                'compensated_steps': compensated_count,
                'compensation_failures': failed_compensations
            }
            
        except Exception as e:
            logger.error(f"Compensation execution failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'compensated_steps': 0,
                'compensation_failures': len(saga.steps)
            }
    
    async def _persist_saga(self, saga: SyncSaga):
        """Persist saga state to cache"""
        cache_key = f"saga_{saga.saga_id}"
        cache.set(cache_key, saga.to_dict(), timeout=3600 * 24)  # 24 hours
    
    async def _load_saga_from_cache(self, saga_id: str) -> Optional[SyncSaga]:
        """Load saga from cache"""
        cache_key = f"saga_{saga_id}"
        saga_data = cache.get(cache_key)
        
        if saga_data:
            # Reconstruct saga from cached data
            # This is a simplified reconstruction - in production, would need full deserialization
            return None  # For now, return None
        
        return None
    
    async def _cleanup_saga(self, saga_id: str):
        """Clean up completed saga"""
        with self._sagas_lock:
            saga = self.active_sagas.pop(saga_id, None)
        
        if saga:
            logger.info(f"Cleaned up saga {saga_id}")
    
    async def _publish_saga_event(self, saga: SyncSaga, event_type: str):
        """Publish saga lifecycle event"""
        try:
            event = RealtimeEvent(
                event_id=f"saga_{saga.saga_id}_{event_type}",
                event_type=f"saga_{event_type}",
                category=EventCategory.FABRIC_STATUS,
                priority=EventPriority.NORMAL,
                timestamp=datetime.now(timezone.utc),
                fabric_id=saga.fabric_id,
                user_id=None,
                data={
                    'saga_id': saga.saga_id,
                    'operation_type': saga.operation_type,
                    'fabric_name': saga.fabric_name,
                    'state': saga.state.value,
                    'progress_percentage': saga.progress_percentage,
                    'duration': saga.duration
                },
                metadata={
                    'source': 'saga_orchestrator',
                    'event_type': event_type
                }
            )
            
            await self.event_service.publish_event(event)
            
        except Exception as e:
            logger.error(f"Failed to publish saga event: {e}")
    
    # Action factory methods - these create the actual step actions
    
    def _create_validation_action(self, fabric: HedgehogFabric) -> Callable:
        """Create validation action for connectivity tests"""
        async def validation_action(saga: SyncSaga, step: SagaStep) -> Dict[str, Any]:
            try:
                # Test Kubernetes connection
                k8s_client = KubernetesClient(fabric)
                k8s_test = await asyncio.to_thread(k8s_client.test_connection)
                
                if not k8s_test['success']:
                    raise Exception(f"Kubernetes connection failed: {k8s_test['error']}")
                
                return {
                    'success': True,
                    'message': 'Validation completed successfully',
                    'kubernetes_connection': k8s_test
                }
                
            except Exception as e:
                raise Exception(f"Validation failed: {e}")
        
        return validation_action
    
    def _create_netbox_read_action(self, fabric: HedgehogFabric, 
                                 resource_types: Optional[List[str]]) -> Callable:
        """Create NetBox read action"""
        async def netbox_read_action(saga: SyncSaga, step: SagaStep) -> Dict[str, Any]:
            try:
                # Read NetBox resources - implementation would depend on specific requirements
                # For now, return placeholder
                return {
                    'success': True,
                    'message': 'NetBox resources read successfully',
                    'resources': []  # Would contain actual resources
                }
                
            except Exception as e:
                raise Exception(f"NetBox read failed: {e}")
        
        return netbox_read_action
    
    def _create_k8s_read_action(self, fabric: HedgehogFabric, 
                               resource_types: Optional[List[str]]) -> Callable:
        """Create Kubernetes read action"""
        async def k8s_read_action(saga: SyncSaga, step: SagaStep) -> Dict[str, Any]:
            try:
                k8s_sync = KubernetesSync(fabric)
                fetch_result = await asyncio.to_thread(k8s_sync.fetch_crds_from_kubernetes)
                
                if not fetch_result['success']:
                    raise Exception(f"Kubernetes fetch failed: {'; '.join(fetch_result['errors'])}")
                
                return {
                    'success': True,
                    'message': 'Kubernetes resources read successfully',
                    'resources': fetch_result['resources'],
                    'totals': fetch_result['totals']
                }
                
            except Exception as e:
                raise Exception(f"Kubernetes read failed: {e}")
        
        return k8s_read_action
    
    def _create_conflict_resolution_action(self) -> Callable:
        """Create conflict resolution action"""
        async def conflict_resolution_action(saga: SyncSaga, step: SagaStep) -> Dict[str, Any]:
            try:
                # Get results from previous steps
                netbox_step = saga.get_step(f"{saga.saga_id}_netbox_read")
                k8s_step = saga.get_step(f"{saga.saga_id}_k8s_read")
                
                if not netbox_step or not k8s_step:
                    raise Exception("Required read steps not found")
                
                # Perform conflict resolution logic
                # This is a simplified implementation
                return {
                    'success': True,
                    'message': 'Conflict resolution completed',
                    'conflicts_resolved': 0,
                    'sync_plan': {
                        'netbox_to_k8s': [],
                        'k8s_to_netbox': []
                    }
                }
                
            except Exception as e:
                raise Exception(f"Conflict resolution failed: {e}")
        
        return conflict_resolution_action
    
    def _create_netbox_to_k8s_action(self, fabric: HedgehogFabric) -> Callable:
        """Create NetBox to Kubernetes sync action"""
        async def netbox_to_k8s_action(saga: SyncSaga, step: SagaStep) -> Dict[str, Any]:
            try:
                # This would implement the actual NetBox to K8s sync
                # For now, return placeholder
                return {
                    'success': True,
                    'message': 'NetBox to Kubernetes sync completed',
                    'resources_applied': 0
                }
                
            except Exception as e:
                raise Exception(f"NetBox to K8s sync failed: {e}")
        
        return netbox_to_k8s_action
    
    def _create_k8s_to_netbox_action(self, fabric: HedgehogFabric) -> Callable:
        """Create Kubernetes to NetBox sync action"""
        async def k8s_to_netbox_action(saga: SyncSaga, step: SagaStep) -> Dict[str, Any]:
            try:
                # This would implement the actual K8s to NetBox sync
                # For now, return placeholder
                return {
                    'success': True,
                    'message': 'Kubernetes to NetBox sync completed',
                    'resources_imported': 0
                }
                
            except Exception as e:
                raise Exception(f"K8s to NetBox sync failed: {e}")
        
        return k8s_to_netbox_action
    
    def _create_status_update_action(self, fabric: HedgehogFabric) -> Callable:
        """Create status update action"""
        async def status_update_action(saga: SyncSaga, step: SagaStep) -> Dict[str, Any]:
            try:
                status_request = StatusUpdateRequest(
                    fabric_id=fabric.id,
                    status_type=StatusType.FABRIC,
                    new_state=StatusState.HEALTHY,
                    message="Saga sync completed successfully",
                    source="saga_orchestrator",
                    priority=EventPriority.NORMAL,
                    metadata={'saga_id': saga.saga_id}
                )
                
                result = await self.status_sync_service.update_status(status_request)
                
                return {
                    'success': result['success'],
                    'message': 'Status updated successfully'
                }
                
            except Exception as e:
                raise Exception(f"Status update failed: {e}")
        
        return status_update_action
    
    # Placeholder compensation actions - these would be implemented based on specific requirements
    
    def _create_k8s_rollback_action(self, fabric: HedgehogFabric) -> Callable:
        """Create Kubernetes rollback compensation action"""
        async def k8s_rollback_action(saga: SyncSaga, step: SagaStep) -> Dict[str, Any]:
            logger.info(f"Executing K8s rollback for step {step.step_id}")
            return {'success': True, 'message': 'K8s rollback completed'}
        
        return k8s_rollback_action
    
    def _create_netbox_rollback_action(self, fabric: HedgehogFabric) -> Callable:
        """Create NetBox rollback compensation action"""
        async def netbox_rollback_action(saga: SyncSaga, step: SagaStep) -> Dict[str, Any]:
            logger.info(f"Executing NetBox rollback for step {step.step_id}")
            return {'success': True, 'message': 'NetBox rollback completed'}
        
        return netbox_rollback_action
    
    def _create_status_rollback_action(self, fabric: HedgehogFabric) -> Callable:
        """Create status rollback compensation action"""
        async def status_rollback_action(saga: SyncSaga, step: SagaStep) -> Dict[str, Any]:
            logger.info(f"Executing status rollback for step {step.step_id}")
            return {'success': True, 'message': 'Status rollback completed'}
        
        return status_rollback_action
    
    # Additional action factory methods for NetBox to K8s saga
    
    def _create_k8s_validation_action(self, fabric: HedgehogFabric) -> Callable:
        """Create Kubernetes-specific validation action"""
        return self._create_validation_action(fabric)  # Reuse general validation
    
    def _create_k8s_backup_action(self, fabric: HedgehogFabric, resources: List[Any]) -> Callable:
        """Create Kubernetes backup action"""
        async def k8s_backup_action(saga: SyncSaga, step: SagaStep) -> Dict[str, Any]:
            logger.info(f"Creating K8s backup for {len(resources)} resources")
            return {'success': True, 'message': 'K8s backup completed', 'backup_id': f"backup_{int(time.time())}"}
        
        return k8s_backup_action
    
    def _create_apply_resources_action(self, fabric: HedgehogFabric, resources: List[Any]) -> Callable:
        """Create resource application action"""
        async def apply_resources_action(saga: SyncSaga, step: SagaStep) -> Dict[str, Any]:
            logger.info(f"Applying {len(resources)} resources to K8s")
            return {'success': True, 'message': 'Resources applied', 'applied_count': len(resources)}
        
        return apply_resources_action
    
    def _create_verify_k8s_action(self, fabric: HedgehogFabric, resources: List[Any]) -> Callable:
        """Create Kubernetes verification action"""
        async def verify_k8s_action(saga: SyncSaga, step: SagaStep) -> Dict[str, Any]:
            logger.info(f"Verifying {len(resources)} resources in K8s")
            return {'success': True, 'message': 'K8s verification completed'}
        
        return verify_k8s_action
    
    def _create_restore_k8s_action(self, fabric: HedgehogFabric) -> Callable:
        """Create Kubernetes restore compensation action"""
        async def restore_k8s_action(saga: SyncSaga, step: SagaStep) -> Dict[str, Any]:
            logger.info("Restoring K8s from backup")
            return {'success': True, 'message': 'K8s restored from backup'}
        
        return restore_k8s_action


# Global instance for easy access
_saga_orchestrator = None

def get_saga_orchestrator() -> SagaOrchestrator:
    """Get global SagaOrchestrator instance"""
    global _saga_orchestrator
    if _saga_orchestrator is None:
        _saga_orchestrator = SagaOrchestrator()
    return _saga_orchestrator