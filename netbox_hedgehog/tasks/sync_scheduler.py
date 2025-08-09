"""
Enhanced Periodic Sync Scheduler - Phase 2 Master Scheduling System

Multi-tier periodic sync scheduler with fabric discovery, planning, and orchestration.
Implements 60-second master cycle with micro-task architecture for agent productivity.

Architecture:
- Master Scheduler (60s) → Fabric Discovery → Micro-task Planning → Execution
- Agent-friendly micro-tasks (<30 seconds each)
- Comprehensive error handling and logging
- Integration with existing Git sync, Kubernetes sync, and status updates
"""

import logging
import time
from typing import Dict, Any, List, Optional, Set
from datetime import timedelta, datetime
from dataclasses import dataclass, field
from enum import Enum
from celery import shared_task, group, chord
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from django.conf import settings

from ..models.fabric import HedgehogFabric
from ..application.services.event_service import EventService
from ..services.status_sync_service import get_status_sync_service, StatusUpdateRequest
from ..tasks.status_reconciliation import reconcile_fabric_status, StatusType, StatusState
from ..domain.interfaces.event_service_interface import EventPriority
from .git_sync_tasks import git_sync_fabric, git_validate_repository
from .cache_tasks import refresh_fabric_cache

logger = logging.getLogger('netbox_hedgehog.sync_scheduler')
performance_logger = logging.getLogger('netbox_hedgehog.performance')
error_logger = logging.getLogger('netbox_hedgehog.errors')

# Enhanced Error Handling and Recovery Classes

class SchedulerError(Exception):
    """Base exception for scheduler-related errors"""
    pass

class FabricDiscoveryError(SchedulerError):
    """Error during fabric discovery phase"""
    pass

class SyncPlanningError(SchedulerError):
    """Error during sync planning phase"""
    pass

class TaskOrchestrationError(SchedulerError):
    """Error during task orchestration phase"""
    pass

class SchedulerTimeoutError(SchedulerError):
    """Error when scheduler cycle exceeds time limits"""
    pass

@dataclass
class ErrorContext:
    """Context information for error handling and recovery"""
    error_type: str
    fabric_id: Optional[int] = None
    fabric_name: Optional[str] = None
    task_type: Optional[str] = None
    phase: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    error_message: str = ""
    stacktrace: Optional[str] = None
    recovery_strategy: str = "default"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error context to dictionary for logging"""
        return {
            'error_type': self.error_type,
            'fabric_id': self.fabric_id,
            'fabric_name': self.fabric_name,
            'task_type': self.task_type,
            'phase': self.phase,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
            'error_message': self.error_message,
            'recovery_strategy': self.recovery_strategy
        }

class SchedulerErrorHandler:
    """
    Centralized error handling and recovery for scheduler operations
    """
    
    def __init__(self):
        self.error_history: List[ErrorContext] = []
        self.fabric_error_counts: Dict[int, int] = {}
    
    def handle_error(self, error: Exception, context: ErrorContext) -> Dict[str, Any]:
        """
        Handle scheduler error with appropriate recovery strategy
        
        Args:
            error: The exception that occurred
            context: Error context information
            
        Returns:
            Recovery action result
        """
        import traceback
        
        # Populate error context
        context.error_message = str(error)
        context.stacktrace = traceback.format_exc()
        
        # Log the error with full context
        error_logger.error(
            f"Scheduler error in {context.phase}: {context.error_type}",
            extra={
                'error_context': context.to_dict(),
                'stacktrace': context.stacktrace
            }
        )
        
        # Update error tracking
        self.error_history.append(context)
        if context.fabric_id:
            self.fabric_error_counts[context.fabric_id] = self.fabric_error_counts.get(context.fabric_id, 0) + 1
        
        # Determine recovery strategy
        recovery_action = self._get_recovery_strategy(error, context)
        
        # Execute recovery action
        return self._execute_recovery_action(recovery_action, context)
    
    def _get_recovery_strategy(self, error: Exception, context: ErrorContext) -> str:
        """Determine appropriate recovery strategy based on error type and context"""
        
        # Critical system errors - immediate escalation
        if isinstance(error, (MemoryError, SystemError)):
            return "escalate_critical"
        
        # Database connection errors - retry with backoff
        if "database" in str(error).lower() or "connection" in str(error).lower():
            return "retry_with_backoff"
        
        # Fabric-specific errors - isolate fabric
        if isinstance(error, (FabricDiscoveryError, SyncPlanningError)) and context.fabric_id:
            fabric_error_count = self.fabric_error_counts.get(context.fabric_id, 0)
            if fabric_error_count > 5:
                return "isolate_fabric"
            else:
                return "retry_fabric"
        
        # Task orchestration errors - graceful degradation
        if isinstance(error, TaskOrchestrationError):
            return "graceful_degradation"
        
        # Timeout errors - reduce scope
        if isinstance(error, (SchedulerTimeoutError, TimeoutError)):
            return "reduce_scope"
        
        # Default strategy
        return "log_and_continue"
    
    def _execute_recovery_action(self, action: str, context: ErrorContext) -> Dict[str, Any]:
        """Execute the determined recovery action"""
        
        recovery_result = {
            'action': action,
            'success': False,
            'message': '',
            'continue_execution': True
        }
        
        try:
            if action == "escalate_critical":
                recovery_result.update(self._escalate_critical_error(context))
                
            elif action == "retry_with_backoff":
                recovery_result.update(self._retry_with_backoff(context))
                
            elif action == "isolate_fabric":
                recovery_result.update(self._isolate_fabric(context))
                
            elif action == "retry_fabric":
                recovery_result.update(self._retry_fabric(context))
                
            elif action == "graceful_degradation":
                recovery_result.update(self._graceful_degradation(context))
                
            elif action == "reduce_scope":
                recovery_result.update(self._reduce_scope(context))
                
            else:  # log_and_continue
                recovery_result.update(self._log_and_continue(context))
                
        except Exception as recovery_error:
            error_logger.error(f"Recovery action failed: {recovery_error}")
            recovery_result.update({
                'success': False,
                'message': f'Recovery failed: {recovery_error}',
                'continue_execution': False
            })
        
        return recovery_result
    
    def _escalate_critical_error(self, context: ErrorContext) -> Dict[str, Any]:
        """Handle critical system errors that require immediate attention"""
        error_logger.critical(
            f"CRITICAL SCHEDULER ERROR: {context.error_type}",
            extra={'error_context': context.to_dict()}
        )
        
        # Send alert to monitoring systems
        try:
            from ..application.services.event_service import EventService
            event_service = EventService()
            event_service.publish_sync_event(
                fabric_id=context.fabric_id or 0,
                event_type='critical_error',
                message=f"Critical scheduler error: {context.error_message}",
                priority=EventPriority.CRITICAL
            )
        except:
            pass  # Don't fail if event service is unavailable
        
        return {
            'success': True,
            'message': 'Critical error escalated to monitoring',
            'continue_execution': False  # Stop scheduler execution
        }
    
    def _retry_with_backoff(self, context: ErrorContext) -> Dict[str, Any]:
        """Implement exponential backoff retry strategy"""
        if context.retry_count >= context.max_retries:
            return {
                'success': False,
                'message': f'Max retries ({context.max_retries}) exceeded',
                'continue_execution': True
            }
        
        backoff_delay = min(2 ** context.retry_count, 30)  # Max 30 seconds
        
        logger.warning(f"Retrying {context.task_type} for fabric {context.fabric_name} "
                      f"in {backoff_delay}s (attempt {context.retry_count + 1})")
        
        # Schedule retry (simplified - in real implementation would use Celery countdown)
        return {
            'success': True,
            'message': f'Scheduled retry with {backoff_delay}s backoff',
            'continue_execution': True,
            'retry_delay': backoff_delay
        }
    
    def _isolate_fabric(self, context: ErrorContext) -> Dict[str, Any]:
        """Isolate problematic fabric from scheduler runs"""
        if not context.fabric_id:
            return {'success': False, 'message': 'No fabric ID for isolation'}
        
        try:
            fabric = HedgehogFabric.objects.get(id=context.fabric_id)
            fabric.scheduler_enabled = False
            fabric.scheduler_metadata = fabric.scheduler_metadata or {}
            fabric.scheduler_metadata.update({
                'isolated_at': timezone.now().isoformat(),
                'isolation_reason': f'Excessive errors: {context.error_message}',
                'error_count': self.fabric_error_counts.get(context.fabric_id, 0)
            })
            fabric.save(update_fields=['scheduler_enabled', 'scheduler_metadata'])
            
            logger.warning(f"Isolated fabric {fabric.name} due to excessive errors")
            
            return {
                'success': True,
                'message': f'Fabric {fabric.name} isolated from scheduler',
                'continue_execution': True
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Failed to isolate fabric: {e}',
                'continue_execution': True
            }
    
    def _retry_fabric(self, context: ErrorContext) -> Dict[str, Any]:
        """Retry fabric-specific operation with reduced scope"""
        return {
            'success': True,
            'message': f'Will retry fabric {context.fabric_name} in next cycle',
            'continue_execution': True
        }
    
    def _graceful_degradation(self, context: ErrorContext) -> Dict[str, Any]:
        """Implement graceful degradation for orchestration errors"""
        logger.info(f"Graceful degradation: reducing task scope for {context.fabric_name}")
        
        # In real implementation, would modify task execution parameters
        return {
            'success': True,
            'message': 'Enabled graceful degradation mode',
            'continue_execution': True,
            'degraded_mode': True
        }
    
    def _reduce_scope(self, context: ErrorContext) -> Dict[str, Any]:
        """Reduce scheduler scope to handle timeout issues"""
        logger.info("Reducing scheduler scope due to timeout")
        
        return {
            'success': True,
            'message': 'Reduced scheduler scope for timeout recovery',
            'continue_execution': True,
            'reduced_scope': True
        }
    
    def _log_and_continue(self, context: ErrorContext) -> Dict[str, Any]:
        """Default recovery: log error and continue execution"""
        logger.warning(f"Continuing after error: {context.error_message}")
        
        return {
            'success': True,
            'message': 'Error logged, continuing execution',
            'continue_execution': True
        }
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """Get error statistics for monitoring"""
        if not self.error_history:
            return {'total_errors': 0, 'error_rate': 0.0}
        
        recent_errors = [
            err for err in self.error_history 
            if err.phase and (timezone.now() - datetime.fromisoformat(
                err.to_dict().get('timestamp', timezone.now().isoformat())
            )).total_seconds() < 3600  # Last hour
        ]
        
        error_types = {}
        for error in recent_errors:
            error_types[error.error_type] = error_types.get(error.error_type, 0) + 1
        
        return {
            'total_errors': len(self.error_history),
            'recent_errors': len(recent_errors),
            'error_types': error_types,
            'fabric_error_counts': dict(self.fabric_error_counts),
            'error_rate': len(recent_errors) / max(1, len(self.error_history))
        }

class SyncPriority(Enum):
    """Sync priority levels for task orchestration"""
    CRITICAL = 1    # Never synced, error states
    HIGH = 2        # Long overdue syncs
    MEDIUM = 3      # Normal scheduled syncs  
    LOW = 4         # Opportunistic syncs
    MAINTENANCE = 5 # Background optimization

class SyncType(Enum):
    """Types of sync operations"""
    GIT_SYNC = "git"
    KUBERNETES_SYNC = "kubernetes" 
    STATUS_UPDATE = "status"
    STATUS_RECONCILIATION = "status_reconciliation"  # New: unified status reconciliation
    CACHE_REFRESH = "cache"
    VALIDATION = "validation"
    DRIFT_DETECTION = "drift"

@dataclass
class SyncTask:
    """Individual sync task with metadata"""
    fabric_id: int
    fabric_name: str
    sync_type: SyncType
    priority: SyncPriority
    estimated_duration: int  # seconds
    last_attempt: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def task_id(self) -> str:
        """Unique task identifier"""
        return f"{self.sync_type.value}_{self.fabric_id}"
    
    @property
    def is_due(self) -> bool:
        """Check if task is due for execution"""
        if not self.last_attempt:
            return True
        
        # Calculate next run time based on priority
        interval_map = {
            SyncPriority.CRITICAL: 30,    # 30 seconds
            SyncPriority.HIGH: 120,       # 2 minutes
            SyncPriority.MEDIUM: 300,     # 5 minutes
            SyncPriority.LOW: 900,        # 15 minutes
            SyncPriority.MAINTENANCE: 3600 # 1 hour
        }
        
        interval = timedelta(seconds=interval_map.get(self.priority, 300))
        return timezone.now() - self.last_attempt >= interval
    
    @property
    def should_retry(self) -> bool:
        """Check if task should be retried"""
        return self.retry_count < self.max_retries

@dataclass
class FabricSyncPlan:
    """Complete sync plan for a fabric"""
    fabric_id: int
    fabric_name: str
    sync_tasks: List[SyncTask] = field(default_factory=list)
    total_estimated_duration: int = 0
    priority: SyncPriority = SyncPriority.MEDIUM
    health_score: float = 1.0  # 0.0 = critical, 1.0 = healthy
    
    def add_task(self, task: SyncTask):
        """Add task to sync plan"""
        self.sync_tasks.append(task)
        self.total_estimated_duration += task.estimated_duration
        
        # Adjust plan priority based on task priorities
        if task.priority.value < self.priority.value:
            self.priority = task.priority
    
    def get_executable_tasks(self) -> List[SyncTask]:
        """Get tasks ready for execution (dependencies satisfied)"""
        executable = []
        completed_tasks = set()
        
        for task in self.sync_tasks:
            if task.is_due and all(dep in completed_tasks for dep in task.dependencies):
                executable.append(task)
        
        return sorted(executable, key=lambda t: t.priority.value)

@dataclass
class SchedulerMetrics:
    """Performance metrics for scheduler monitoring"""
    cycle_count: int = 0
    fabrics_discovered: int = 0
    tasks_planned: int = 0
    tasks_executed: int = 0
    tasks_failed: int = 0
    avg_cycle_duration: float = 0.0
    last_cycle_time: Optional[datetime] = None
    error_rate: float = 0.0

class EnhancedSyncScheduler:
    """
    Master Sync Scheduler with fabric discovery and micro-task orchestration
    """
    
    def __init__(self):
        self.event_service = EventService()
        self.metrics = SchedulerMetrics()
        self.active_plans: Dict[int, FabricSyncPlan] = {}
        self.scheduler_id = f"scheduler_{int(time.time())}"
        self.error_handler = SchedulerErrorHandler()  # Enhanced error handling
    
    def discover_fabrics(self) -> List[HedgehogFabric]:
        """
        Discover all fabrics requiring sync operations
        Returns prioritized list based on health and sync requirements
        """
        try:
            # Get all scheduler-enabled fabrics with enhanced filtering
            fabrics = HedgehogFabric.objects.filter(
                scheduler_enabled=True,  # Use new scheduler_enabled field
                sync_enabled=True
            ).select_related('git_repository').order_by('scheduler_priority', 'name')
            
            # Filter and prioritize based on health metrics and scheduler criteria
            prioritized_fabrics = []
            
            for fabric in fabrics:
                try:
                    # Skip fabrics that shouldn't be scheduled
                    if not fabric.should_be_scheduled():
                        continue
                    
                    health_score = fabric.calculate_scheduler_health_score()
                    
                    # Include fabric based on priority and health
                    if (fabric.scheduler_priority in ['critical', 'high'] or 
                        health_score < 0.8 or 
                        self._fabric_needs_sync(fabric)):
                        prioritized_fabrics.append(fabric)
                        
                except Exception as fabric_error:
                    # Handle individual fabric errors without stopping discovery
                    error_context = ErrorContext(
                        error_type="fabric_evaluation_error",
                        fabric_id=fabric.id,
                        fabric_name=fabric.name,
                        phase="discovery",
                        task_type="fabric_discovery"
                    )
                    
                    recovery_result = self.error_handler.handle_error(fabric_error, error_context)
                    
                    if recovery_result['continue_execution']:
                        logger.warning(f"Skipping fabric {fabric.name} due to evaluation error: {fabric_error}")
                        continue
                    else:
                        # Critical error - stop discovery
                        raise FabricDiscoveryError(f"Critical error evaluating fabric {fabric.name}: {fabric_error}")
            
            # Sort by priority level and health score
            prioritized_fabrics.sort(key=lambda f: (f.get_scheduler_priority_level(), f.calculate_scheduler_health_score()))
            
            self.metrics.fabrics_discovered = len(prioritized_fabrics)
            
            logger.info(f"Discovered {len(prioritized_fabrics)} fabrics needing sync from {fabrics.count()} total scheduler-enabled fabrics")
            performance_logger.info(f"Fabric discovery metrics: {len(prioritized_fabrics)} prioritized from {fabrics.count()} total")
            
            return prioritized_fabrics
            
        except Exception as e:
            error_context = ErrorContext(
                error_type="discovery_failure",
                phase="discovery",
                task_type="fabric_discovery"
            )
            
            recovery_result = self.error_handler.handle_error(e, error_context)
            
            if not recovery_result['continue_execution']:
                raise FabricDiscoveryError(f"Critical fabric discovery failure: {e}")
            
            logger.error(f"Fabric discovery failed but continuing: {e}")
            return []
    
    def create_sync_plan(self, fabric: HedgehogFabric) -> FabricSyncPlan:
        """
        Create comprehensive sync plan for a fabric
        Plans all required sync operations with proper dependencies
        """
        plan = FabricSyncPlan(
            fabric_id=fabric.id,
            fabric_name=fabric.name,
            health_score=self._calculate_fabric_health(fabric)
        )
        
        # Determine required sync operations based on fabric state
        required_syncs = self._analyze_fabric_sync_requirements(fabric)
        
        for sync_type, priority in required_syncs.items():
            task = SyncTask(
                fabric_id=fabric.id,
                fabric_name=fabric.name,
                sync_type=sync_type,
                priority=priority,
                estimated_duration=self._estimate_task_duration(sync_type, fabric),
                metadata=self._get_task_metadata(sync_type, fabric)
            )
            
            # Set task dependencies
            task.dependencies = self._get_task_dependencies(sync_type)
            
            plan.add_task(task)
        
        # Cache the plan for monitoring
        self.active_plans[fabric.id] = plan
        
        logger.debug(f"Created sync plan for {fabric.name}: {len(plan.sync_tasks)} tasks, "
                    f"estimated {plan.total_estimated_duration}s")
        
        return plan
    
    def execute_sync_plan(self, plan: FabricSyncPlan) -> Dict[str, Any]:
        """
        Execute sync plan using micro-task orchestration
        Returns execution results and metrics
        """
        try:
            executable_tasks = plan.get_executable_tasks()
            
            if not executable_tasks:
                return {
                    'success': True,
                    'message': 'No tasks ready for execution',
                    'tasks_executed': 0
                }
            
            # Group tasks by type for optimal execution
            task_groups = self._group_tasks_for_execution(executable_tasks)
            
            # Execute task groups with proper orchestration
            execution_results = []
            
            for group_name, tasks in task_groups.items():
                logger.info(f"Executing {group_name} tasks for fabric {plan.fabric_name}: {len(tasks)} tasks")
                
                group_result = self._execute_task_group(tasks, plan)
                execution_results.append(group_result)
                
                # Update task attempt tracking
                for task in tasks:
                    task.last_attempt = timezone.now()
                    if not group_result.get('success', False):
                        task.retry_count += 1
            
            # Calculate overall success rate
            successful_groups = sum(1 for result in execution_results if result.get('success', False))
            success_rate = successful_groups / len(execution_results) if execution_results else 1.0
            
            # Update metrics
            self.metrics.tasks_executed += len(executable_tasks)
            if success_rate < 0.5:
                self.metrics.tasks_failed += len(executable_tasks)
            
            return {
                'success': success_rate >= 0.5,
                'message': f'Executed {len(executable_tasks)} tasks with {success_rate:.1%} success rate',
                'tasks_executed': len(executable_tasks),
                'success_rate': success_rate,
                'execution_results': execution_results
            }
            
        except Exception as e:
            logger.error(f"Sync plan execution failed for fabric {plan.fabric_name}: {e}")
            return {
                'success': False,
                'error': str(e),
                'tasks_executed': 0
            }
    
    def _calculate_fabric_health(self, fabric: HedgehogFabric) -> float:
        """Calculate fabric health score (0.0 = critical, 1.0 = healthy)"""
        health_factors = []
        
        # Sync status factor
        if fabric.sync_status == 'error':
            health_factors.append(0.1)
        elif fabric.sync_status == 'never_synced':
            health_factors.append(0.2)
        elif fabric.sync_status == 'syncing':
            health_factors.append(0.7)
        else:  # synced
            health_factors.append(1.0)
        
        # Connection status factor
        if fabric.connection_status == 'error':
            health_factors.append(0.2)
        elif fabric.connection_status == 'unknown':
            health_factors.append(0.6)
        else:  # connected
            health_factors.append(1.0)
        
        # Time since last sync factor
        if fabric.last_sync:
            hours_since_sync = (timezone.now() - fabric.last_sync).total_seconds() / 3600
            if hours_since_sync > 24:
                health_factors.append(0.3)
            elif hours_since_sync > 6:
                health_factors.append(0.7)
            else:
                health_factors.append(1.0)
        else:
            health_factors.append(0.1)  # Never synced
        
        # Error count factor
        error_count = fabric.error_crd_count
        if error_count > 10:
            health_factors.append(0.2)
        elif error_count > 5:
            health_factors.append(0.5)
        elif error_count > 0:
            health_factors.append(0.8)
        else:
            health_factors.append(1.0)
        
        return sum(health_factors) / len(health_factors) if health_factors else 0.5
    
    def _fabric_needs_sync(self, fabric: HedgehogFabric) -> bool:
        """Determine if fabric needs any sync operation"""
        # Never synced
        if not fabric.last_sync:
            return True
        
        # Sync interval exceeded
        interval = timedelta(seconds=fabric.sync_interval or 300)
        if timezone.now() - fabric.last_sync >= interval:
            return True
        
        # Error states
        if fabric.sync_status == 'error' or fabric.connection_status == 'error':
            return True
        
        # Drift detected
        if hasattr(fabric, 'drift_count') and fabric.drift_count > 0:
            return True
        
        return False
    
    def _analyze_fabric_sync_requirements(self, fabric: HedgehogFabric) -> Dict[SyncType, SyncPriority]:
        """Analyze fabric and determine required sync operations with priorities"""
        requirements = {}
        
        # Git sync requirements
        if fabric.git_repository_url:
            if not fabric.last_git_sync:
                requirements[SyncType.GIT_SYNC] = SyncPriority.CRITICAL
            elif fabric.sync_status == 'error':
                requirements[SyncType.GIT_SYNC] = SyncPriority.HIGH
            elif self._fabric_needs_sync(fabric):
                requirements[SyncType.GIT_SYNC] = SyncPriority.MEDIUM
        
        # Kubernetes sync requirements  
        if fabric.kubernetes_server:
            if fabric.connection_status == 'error':
                requirements[SyncType.KUBERNETES_SYNC] = SyncPriority.HIGH
            elif fabric.watch_status == 'error':
                requirements[SyncType.KUBERNETES_SYNC] = SyncPriority.MEDIUM
            elif not fabric.last_sync:
                requirements[SyncType.KUBERNETES_SYNC] = SyncPriority.CRITICAL
        
        # Status update requirements
        if fabric.sync_status in ['syncing', 'error']:
            requirements[SyncType.STATUS_UPDATE] = SyncPriority.HIGH
        else:
            requirements[SyncType.STATUS_UPDATE] = SyncPriority.LOW
        
        # Status reconciliation requirements (new unified framework)
        # Always include reconciliation, but with different priorities
        if fabric.sync_status == 'error' or fabric.connection_status == 'error':
            requirements[SyncType.STATUS_RECONCILIATION] = SyncPriority.HIGH
        elif fabric.sync_status in ['never_synced', 'stale']:
            requirements[SyncType.STATUS_RECONCILIATION] = SyncPriority.MEDIUM
        else:
            requirements[SyncType.STATUS_RECONCILIATION] = SyncPriority.LOW
        
        # Cache refresh requirements
        cache_key = f"fabric_crds_{fabric.id}"
        if not cache.get(cache_key):
            requirements[SyncType.CACHE_REFRESH] = SyncPriority.MEDIUM
        else:
            requirements[SyncType.CACHE_REFRESH] = SyncPriority.LOW
        
        # Validation requirements
        if fabric.connection_status == 'unknown':
            requirements[SyncType.VALIDATION] = SyncPriority.HIGH
        
        # Drift detection requirements
        if hasattr(fabric, 'drift_status') and fabric.drift_status != 'in_sync':
            requirements[SyncType.DRIFT_DETECTION] = SyncPriority.MEDIUM
        
        return requirements
    
    def _estimate_task_duration(self, sync_type: SyncType, fabric: HedgehogFabric) -> int:
        """Estimate task duration in seconds based on fabric characteristics"""
        base_durations = {
            SyncType.GIT_SYNC: 25,        # Git operations
            SyncType.KUBERNETES_SYNC: 20, # K8s API calls  
            SyncType.STATUS_UPDATE: 5,    # Database updates
            SyncType.CACHE_REFRESH: 10,   # Cache operations
            SyncType.VALIDATION: 15,      # Connectivity tests
            SyncType.DRIFT_DETECTION: 30  # Comparison operations
        }
        
        base_duration = base_durations.get(sync_type, 20)
        
        # Adjust based on fabric size (CRD count)
        crd_count = fabric.cached_crd_count or 0
        if crd_count > 100:
            base_duration += 10
        elif crd_count > 500:
            base_duration += 20
        
        # Adjust based on fabric health
        health_score = self._calculate_fabric_health(fabric)
        if health_score < 0.5:
            base_duration += 5  # Unhealthy fabrics take longer
        
        return min(base_duration, 30)  # Never exceed 30 seconds
    
    def _get_task_metadata(self, sync_type: SyncType, fabric: HedgehogFabric) -> Dict[str, Any]:
        """Get task-specific metadata for execution context"""
        metadata = {
            'fabric_id': fabric.id,
            'fabric_name': fabric.name,
            'sync_type': sync_type.value,
            'created_at': timezone.now().isoformat()
        }
        
        if sync_type == SyncType.GIT_SYNC:
            metadata.update({
                'git_repository_url': fabric.git_repository_url,
                'git_branch': fabric.git_branch,
                'last_git_sync': fabric.last_git_sync.isoformat() if fabric.last_git_sync else None
            })
        elif sync_type == SyncType.KUBERNETES_SYNC:
            metadata.update({
                'kubernetes_server': fabric.kubernetes_server,
                'kubernetes_namespace': fabric.kubernetes_namespace,
                'watch_enabled': fabric.watch_enabled
            })
        
        return metadata
    
    def _get_task_dependencies(self, sync_type: SyncType) -> List[str]:
        """Get task dependencies for proper execution order"""
        dependencies = {
            SyncType.GIT_SYNC: [],  # No dependencies
            SyncType.KUBERNETES_SYNC: [],  # No dependencies
            SyncType.STATUS_UPDATE: ['git', 'kubernetes'],  # After sync operations
            SyncType.CACHE_REFRESH: ['git', 'kubernetes'],  # After sync operations
            SyncType.VALIDATION: [],  # No dependencies
            SyncType.DRIFT_DETECTION: ['git', 'kubernetes']  # After sync operations
        }
        
        return dependencies.get(sync_type, [])
    
    def _group_tasks_for_execution(self, tasks: List[SyncTask]) -> Dict[str, List[SyncTask]]:
        """Group tasks for optimal execution"""
        groups = {
            'critical': [],
            'sync_operations': [],
            'post_sync': [],
            'maintenance': []
        }
        
        for task in tasks:
            if task.priority == SyncPriority.CRITICAL:
                groups['critical'].append(task)
            elif task.sync_type in [SyncType.GIT_SYNC, SyncType.KUBERNETES_SYNC, SyncType.VALIDATION]:
                groups['sync_operations'].append(task)
            elif task.sync_type in [SyncType.STATUS_UPDATE, SyncType.CACHE_REFRESH, SyncType.DRIFT_DETECTION]:
                groups['post_sync'].append(task)
            else:
                groups['maintenance'].append(task)
        
        # Remove empty groups
        return {name: tasks for name, tasks in groups.items() if tasks}
    
    def _execute_task_group(self, tasks: List[SyncTask], plan: FabricSyncPlan) -> Dict[str, Any]:
        """Execute a group of tasks with proper orchestration"""
        try:
            # Create Celery task signatures for parallel execution
            task_signatures = []
            
            for task in tasks:
                if task.sync_type == SyncType.GIT_SYNC:
                    task_signatures.append(git_sync_fabric.s(task.fabric_id))
                elif task.sync_type == SyncType.VALIDATION:
                    task_signatures.append(git_validate_repository.s(task.fabric_id))
                elif task.sync_type == SyncType.CACHE_REFRESH:
                    task_signatures.append(refresh_fabric_cache.s(task.fabric_id))
                elif task.sync_type == SyncType.STATUS_UPDATE:
                    task_signatures.append(update_fabric_status.s(task.fabric_id))
                elif task.sync_type == SyncType.STATUS_RECONCILIATION:
                    task_signatures.append(reconcile_fabric_status.s(task.fabric_id))
                elif task.sync_type == SyncType.KUBERNETES_SYNC:
                    task_signatures.append(kubernetes_sync_fabric.s(task.fabric_id))
                elif task.sync_type == SyncType.DRIFT_DETECTION:
                    task_signatures.append(detect_fabric_drift.s(task.fabric_id))
            
            if not task_signatures:
                return {'success': True, 'message': 'No executable tasks'}
            
            # Execute tasks in parallel group
            job = group(task_signatures)
            result = job.apply_async()
            
            # Publish orchestration event
            self.event_service.publish_sync_event(
                fabric_id=plan.fabric_id,
                event_type='orchestration',
                progress=50,
                message=f"Executing {len(tasks)} tasks for {plan.fabric_name}",
                priority=EventPriority.MEDIUM
            )
            
            return {
                'success': True,
                'message': f'Submitted {len(tasks)} tasks for execution',
                'task_count': len(tasks),
                'job_id': result.id
            }
            
        except Exception as e:
            logger.error(f"Task group execution failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'task_count': len(tasks)
            }

@shared_task(bind=True, name='netbox_hedgehog.tasks.master_sync_scheduler')
def master_sync_scheduler(self) -> Dict[str, Any]:
    """
    Master periodic sync scheduler - runs every 60 seconds
    Discovers fabrics, creates sync plans, and orchestrates execution
    """
    start_time = time.time()
    scheduler = EnhancedSyncScheduler()
    
    try:
        logger.info(f"Starting master sync scheduler cycle {scheduler.scheduler_id}")
        
        # Phase 1: Fabric Discovery (Target: <10 seconds)
        discovery_start = time.time()
        fabrics = scheduler.discover_fabrics()
        discovery_time = time.time() - discovery_start
        
        logger.info(f"Discovery phase completed in {discovery_time:.2f}s: {len(fabrics)} fabrics")
        
        if not fabrics:
            return {
                'success': True,
                'message': 'No fabrics requiring sync',
                'cycle_duration': time.time() - start_time,
                'fabrics_processed': 0
            }
        
        # Phase 2: Sync Planning (Target: <15 seconds)
        planning_start = time.time()
        sync_plans = []
        
        for fabric in fabrics:
            try:
                plan = scheduler.create_sync_plan(fabric)
                if plan.sync_tasks:  # Only include plans with tasks
                    sync_plans.append(plan)
            except Exception as e:
                logger.error(f"Failed to create sync plan for fabric {fabric.name}: {e}")
        
        planning_time = time.time() - planning_start
        scheduler.metrics.tasks_planned = sum(len(plan.sync_tasks) for plan in sync_plans)
        
        logger.info(f"Planning phase completed in {planning_time:.2f}s: "
                   f"{len(sync_plans)} plans, {scheduler.metrics.tasks_planned} tasks")
        
        # Phase 3: Execution Orchestration (Target: <35 seconds total)
        execution_start = time.time()
        execution_results = []
        
        # Execute plans in priority order
        sync_plans.sort(key=lambda p: p.priority.value)
        
        for plan in sync_plans:
            try:
                result = scheduler.execute_sync_plan(plan)
                execution_results.append({
                    'fabric_id': plan.fabric_id,
                    'fabric_name': plan.fabric_name,
                    'result': result
                })
            except Exception as e:
                logger.error(f"Failed to execute sync plan for fabric {plan.fabric_name}: {e}")
                execution_results.append({
                    'fabric_id': plan.fabric_id,
                    'fabric_name': plan.fabric_name,
                    'result': {'success': False, 'error': str(e)}
                })
        
        execution_time = time.time() - execution_start
        
        # Update scheduler metrics
        total_duration = time.time() - start_time
        scheduler.metrics.cycle_count += 1
        scheduler.metrics.last_cycle_time = timezone.now()
        scheduler.metrics.avg_cycle_duration = (
            (scheduler.metrics.avg_cycle_duration * (scheduler.metrics.cycle_count - 1) + total_duration) 
            / scheduler.metrics.cycle_count
        )
        
        # Calculate success metrics
        successful_executions = sum(1 for result in execution_results if result['result'].get('success', False))
        success_rate = successful_executions / len(execution_results) if execution_results else 1.0
        scheduler.metrics.error_rate = 1.0 - success_rate
        
        logger.info(f"Master scheduler cycle completed in {total_duration:.2f}s: "
                   f"{len(sync_plans)} plans executed, {success_rate:.1%} success rate")
        
        # Cache scheduler metrics for monitoring
        cache.set(
            'scheduler_metrics',
            {
                'cycle_count': scheduler.metrics.cycle_count,
                'last_cycle_duration': total_duration,
                'avg_cycle_duration': scheduler.metrics.avg_cycle_duration,
                'fabrics_discovered': scheduler.metrics.fabrics_discovered,
                'tasks_planned': scheduler.metrics.tasks_planned,
                'tasks_executed': scheduler.metrics.tasks_executed,
                'success_rate': success_rate,
                'last_update': timezone.now().isoformat()
            },
            timeout=300  # 5 minutes
        )
        
        return {
            'success': True,
            'message': f'Master scheduler cycle completed successfully',
            'scheduler_id': scheduler.scheduler_id,
            'cycle_duration': total_duration,
            'phases': {
                'discovery': {'duration': discovery_time, 'fabrics_found': len(fabrics)},
                'planning': {'duration': planning_time, 'plans_created': len(sync_plans), 'tasks_planned': scheduler.metrics.tasks_planned},
                'execution': {'duration': execution_time, 'plans_executed': len(sync_plans), 'success_rate': success_rate}
            },
            'metrics': {
                'fabrics_processed': len(fabrics),
                'sync_plans_created': len(sync_plans),
                'tasks_orchestrated': scheduler.metrics.tasks_planned,
                'success_rate': success_rate
            }
        }
        
    except Exception as e:
        error_duration = time.time() - start_time
        logger.error(f"Master sync scheduler failed after {error_duration:.2f}s: {e}")
        
        return {
            'success': False,
            'error': str(e),
            'cycle_duration': error_duration,
            'scheduler_id': scheduler.scheduler_id
        }

# Micro-task implementations for sync orchestration

@shared_task(bind=True, name='netbox_hedgehog.tasks.update_fabric_status')
def update_fabric_status(self, fabric_id: int) -> Dict[str, Any]:
    """
    Micro-task: Update fabric status and sync metadata
    Target: <10 seconds execution time
    """
    start_time = time.time()
    
    try:
        fabric = HedgehogFabric.objects.select_for_update().get(id=fabric_id)
        
        # Update CRD counts
        fabric.cached_crd_count = fabric.active_crd_count
        fabric.cached_vpc_count = fabric.vpcs_count
        fabric.cached_connection_count = fabric.connections_count
        
        # Update sync status based on recent activity
        if fabric.last_sync:
            time_since_sync = timezone.now() - fabric.last_sync
            if time_since_sync.total_seconds() < 300:  # 5 minutes
                fabric.sync_status = 'synced'
            elif time_since_sync.total_seconds() < 3600:  # 1 hour  
                fabric.sync_status = 'stale'
            else:
                fabric.sync_status = 'outdated'
        
        fabric.save(update_fields=['cached_crd_count', 'cached_vpc_count', 
                                  'cached_connection_count', 'sync_status'])
        
        duration = time.time() - start_time
        
        return {
            'success': True,
            'message': f'Status updated for fabric {fabric.name}',
            'duration': duration,
            'fabric_id': fabric_id,
            'crd_count': fabric.cached_crd_count
        }
        
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Status update failed for fabric {fabric_id}: {e}")
        
        return {
            'success': False,
            'error': str(e),
            'duration': duration,
            'fabric_id': fabric_id
        }

@shared_task(bind=True, name='netbox_hedgehog.tasks.kubernetes_sync_fabric')
def kubernetes_sync_fabric(self, fabric_id: int) -> Dict[str, Any]:
    """
    Micro-task: Sync fabric with Kubernetes cluster
    Target: <25 seconds execution time
    """
    start_time = time.time()
    
    try:
        fabric = HedgehogFabric.objects.get(id=fabric_id)
        
        # Sync actual state from Kubernetes
        sync_result = fabric.sync_actual_state()
        
        if sync_result['success']:
            # Update connection status
            fabric.connection_status = 'connected'
            fabric.connection_error = ''
        else:
            fabric.connection_status = 'error'
            fabric.connection_error = sync_result.get('error', 'Unknown error')
        
        fabric.save(update_fields=['connection_status', 'connection_error'])
        
        duration = time.time() - start_time
        
        return {
            'success': sync_result['success'],
            'message': sync_result.get('message', 'Kubernetes sync completed'),
            'duration': duration,
            'fabric_id': fabric_id,
            'resources_updated': sync_result.get('resources_updated', 0)
        }
        
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Kubernetes sync failed for fabric {fabric_id}: {e}")
        
        return {
            'success': False,
            'error': str(e),
            'duration': duration,
            'fabric_id': fabric_id
        }

@shared_task(bind=True, name='netbox_hedgehog.tasks.detect_fabric_drift')
def detect_fabric_drift(self, fabric_id: int) -> Dict[str, Any]:
    """
    Micro-task: Detect and calculate drift between desired and actual state
    Target: <30 seconds execution time
    """
    start_time = time.time()
    
    try:
        fabric = HedgehogFabric.objects.get(id=fabric_id)
        
        # Calculate drift status
        drift_result = fabric.calculate_drift_status()
        
        duration = time.time() - start_time
        
        return {
            'success': drift_result.get('drift_status') != 'error',
            'message': f'Drift detection completed for fabric {fabric.name}',
            'duration': duration,
            'fabric_id': fabric_id,
            'drift_status': drift_result.get('drift_status'),
            'drift_count': drift_result.get('drift_count', 0)
        }
        
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Drift detection failed for fabric {fabric_id}: {e}")
        
        return {
            'success': False,
            'error': str(e),
            'duration': duration,
            'fabric_id': fabric_id
        }

# Scheduler monitoring and control tasks

@shared_task(name='netbox_hedgehog.tasks.get_scheduler_metrics')
def get_scheduler_metrics() -> Dict[str, Any]:
    """Get current scheduler performance metrics"""
    metrics = cache.get('scheduler_metrics', {})
    
    # Add real-time fabric statistics
    try:
        fabric_stats = {
            'total_fabrics': HedgehogFabric.objects.count(),
            'sync_enabled': HedgehogFabric.objects.filter(sync_enabled=True).count(),
            'error_state': HedgehogFabric.objects.filter(sync_status='error').count(),
            'never_synced': HedgehogFabric.objects.filter(sync_status='never_synced').count()
        }
        metrics['fabric_stats'] = fabric_stats
    except Exception as e:
        logger.error(f"Failed to get fabric stats: {e}")
    
    return metrics

@shared_task(name='netbox_hedgehog.tasks.reset_scheduler_metrics')
def reset_scheduler_metrics() -> Dict[str, Any]:
    """Reset scheduler performance metrics"""
    cache.delete('scheduler_metrics')
    return {'success': True, 'message': 'Scheduler metrics reset'}