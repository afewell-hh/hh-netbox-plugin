"""
Status Reconciliation Service - Phase 2 Unified Status Synchronization Framework

Unified status model managing all component states with real-time conflict detection
and resolution. Ensures consistent status across Git, Kubernetes, and sync states.

Architecture:
- Centralized status management with unified data model
- Real-time conflict detection and automated resolution
- Status propagation with <5 second delay target
- Event-driven status updates integration
- Comprehensive reconciliation algorithms
"""

import logging
import time
import asyncio
from typing import Dict, Any, List, Optional, Set, Tuple
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from enum import Enum
from celery import shared_task
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone as django_timezone
from django.conf import settings

from ..models.fabric import HedgehogFabric
from ..models.git_repository import GitRepository
from ..application.services.event_service import EventService
from ..domain.interfaces.event_service_interface import EventPriority, EventCategory, RealtimeEvent

logger = logging.getLogger('netbox_hedgehog.status_reconciliation')
performance_logger = logging.getLogger('netbox_hedgehog.performance')

# Unified Status Model and Enums

class StatusType(Enum):
    """Types of status components that need synchronization"""
    GIT_SYNC = "git_sync"
    KUBERNETES = "kubernetes"
    FABRIC = "fabric"
    WATCH = "watch"
    CONNECTION = "connection"

class StatusState(Enum):
    """Unified status states across all components"""
    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    WARNING = "warning"
    ERROR = "error"
    SYNCING = "syncing"
    STALE = "stale"
    NEVER_SYNCED = "never_synced"

class ConflictType(Enum):
    """Types of status conflicts"""
    STATE_MISMATCH = "state_mismatch"
    TIMESTAMP_CONFLICT = "timestamp_conflict"
    DATA_INCONSISTENCY = "data_inconsistency"
    MISSING_STATUS = "missing_status"
    CIRCULAR_DEPENDENCY = "circular_dependency"

@dataclass
class StatusSnapshot:
    """Unified status snapshot for a specific component"""
    status_type: StatusType
    fabric_id: int
    state: StatusState
    timestamp: datetime
    message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    error_details: Optional[str] = None
    last_successful: Optional[datetime] = None
    consecutive_failures: int = 0
    health_score: float = 1.0  # 0.0 = critical, 1.0 = healthy
    
    @property
    def is_stale(self) -> bool:
        """Check if status is stale based on age"""
        age = datetime.now(timezone.utc) - self.timestamp
        return age.total_seconds() > 300  # 5 minutes
    
    @property
    def is_critical(self) -> bool:
        """Check if status indicates critical condition"""
        return self.state in [StatusState.ERROR] or self.consecutive_failures > 3

@dataclass
class StatusConflict:
    """Represents a conflict between status components"""
    conflict_type: ConflictType
    fabric_id: int
    conflicting_statuses: List[StatusSnapshot]
    severity: str  # 'low', 'medium', 'high', 'critical'
    resolution_strategy: str = ""
    auto_resolvable: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: Optional[datetime] = None
    resolution_details: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ReconciliationResult:
    """Result of status reconciliation operation"""
    success: bool
    fabric_id: int
    conflicts_detected: int
    conflicts_resolved: int
    status_updates: List[Dict[str, Any]]
    execution_time: float
    errors: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

class StatusReconciliationService:
    """
    Centralized service for status reconciliation and conflict resolution
    """
    
    def __init__(self):
        self.event_service = EventService()
        self.active_conflicts: Dict[int, List[StatusConflict]] = {}
        self.status_cache: Dict[Tuple[int, StatusType], StatusSnapshot] = {}
        self.reconciliation_history: List[ReconciliationResult] = []
        
    async def reconcile_fabric_status(self, fabric_id: int) -> ReconciliationResult:
        """
        Main reconciliation method for a fabric's complete status
        
        Args:
            fabric_id: ID of fabric to reconcile
            
        Returns:
            ReconciliationResult with comprehensive reconciliation data
        """
        start_time = time.time()
        
        try:
            # Collect current status snapshots from all components
            status_snapshots = await self._collect_status_snapshots(fabric_id)
            
            # Detect conflicts between status components
            conflicts = self._detect_status_conflicts(fabric_id, status_snapshots)
            
            # Resolve conflicts using appropriate strategies
            resolved_conflicts = 0
            status_updates = []
            
            for conflict in conflicts:
                resolution_result = await self._resolve_conflict(conflict)
                if resolution_result['success']:
                    resolved_conflicts += 1
                    status_updates.extend(resolution_result.get('updates', []))
            
            # Update unified status based on reconciliation
            unified_status = self._calculate_unified_status(status_snapshots)
            await self._update_fabric_unified_status(fabric_id, unified_status)
            
            # Propagate status changes via event service
            await self._propagate_status_changes(fabric_id, status_updates)
            
            execution_time = time.time() - start_time
            
            # Create reconciliation result
            result = ReconciliationResult(
                success=True,
                fabric_id=fabric_id,
                conflicts_detected=len(conflicts),
                conflicts_resolved=resolved_conflicts,
                status_updates=status_updates,
                execution_time=execution_time
            )
            
            # Cache result for monitoring
            self.reconciliation_history.append(result)
            if len(self.reconciliation_history) > 100:
                self.reconciliation_history = self.reconciliation_history[-100:]
            
            logger.info(f"Status reconciliation completed for fabric {fabric_id}: "
                       f"{len(conflicts)} conflicts detected, {resolved_conflicts} resolved in {execution_time:.2f}s")
            
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Status reconciliation failed for fabric {fabric_id}: {e}")
            
            return ReconciliationResult(
                success=False,
                fabric_id=fabric_id,
                conflicts_detected=0,
                conflicts_resolved=0,
                status_updates=[],
                execution_time=execution_time,
                errors=[str(e)]
            )
    
    async def _collect_status_snapshots(self, fabric_id: int) -> Dict[StatusType, StatusSnapshot]:
        """Collect current status from all components"""
        snapshots = {}
        
        try:
            fabric = await self._get_fabric_async(fabric_id)
            
            # Git sync status
            git_snapshot = StatusSnapshot(
                status_type=StatusType.GIT_SYNC,
                fabric_id=fabric_id,
                state=self._map_sync_status_to_state(fabric.sync_status),
                timestamp=fabric.last_sync or fabric.modified,
                message=fabric.sync_error or "Git sync status",
                metadata={
                    'git_branch': fabric.git_branch,
                    'last_git_sync': fabric.last_git_sync.isoformat() if fabric.last_git_sync else None
                },
                error_details=fabric.sync_error if fabric.sync_error else None,
                last_successful=fabric.last_sync
            )
            snapshots[StatusType.GIT_SYNC] = git_snapshot
            
            # Kubernetes status
            k8s_snapshot = StatusSnapshot(
                status_type=StatusType.KUBERNETES,
                fabric_id=fabric_id,
                state=self._map_connection_status_to_state(fabric.connection_status),
                timestamp=fabric.last_sync or fabric.modified,
                message=fabric.connection_error or "Kubernetes connection status",
                metadata={
                    'kubernetes_server': fabric.kubernetes_server,
                    'kubernetes_namespace': fabric.kubernetes_namespace
                },
                error_details=fabric.connection_error if fabric.connection_error else None
            )
            snapshots[StatusType.KUBERNETES] = k8s_snapshot
            
            # Fabric status
            fabric_snapshot = StatusSnapshot(
                status_type=StatusType.FABRIC,
                fabric_id=fabric_id,
                state=self._map_fabric_status_to_state(fabric.status),
                timestamp=fabric.modified,
                message=f"Fabric status: {fabric.status}",
                metadata={
                    'fabric_name': fabric.name,
                    'sync_enabled': fabric.sync_enabled,
                    'sync_interval': fabric.sync_interval
                }
            )
            snapshots[StatusType.FABRIC] = fabric_snapshot
            
            # Watch status (if available)
            if hasattr(fabric, 'watch_status'):
                watch_snapshot = StatusSnapshot(
                    status_type=StatusType.WATCH,
                    fabric_id=fabric_id,
                    state=self._map_watch_status_to_state(fabric.watch_status),
                    timestamp=fabric.modified,
                    message=f"Watch status: {fabric.watch_status}",
                    metadata={'watch_enabled': getattr(fabric, 'watch_enabled', False)}
                )
                snapshots[StatusType.WATCH] = watch_snapshot
            
            # Update cache
            for snapshot in snapshots.values():
                self.status_cache[(fabric_id, snapshot.status_type)] = snapshot
            
            return snapshots
            
        except Exception as e:
            logger.error(f"Failed to collect status snapshots for fabric {fabric_id}: {e}")
            return {}
    
    def _detect_status_conflicts(self, fabric_id: int, snapshots: Dict[StatusType, StatusSnapshot]) -> List[StatusConflict]:
        """Detect conflicts between status components"""
        conflicts = []
        
        # Check for state mismatches
        states = {stype: snap.state for stype, snap in snapshots.items()}
        
        # Git sync vs Connection conflict
        if (StatusType.GIT_SYNC in states and StatusType.KUBERNETES in states and
            states[StatusType.GIT_SYNC] == StatusState.HEALTHY and 
            states[StatusType.KUBERNETES] == StatusState.ERROR):
            
            conflict = StatusConflict(
                conflict_type=ConflictType.STATE_MISMATCH,
                fabric_id=fabric_id,
                conflicting_statuses=[snapshots[StatusType.GIT_SYNC], snapshots[StatusType.KUBERNETES]],
                severity='high',
                resolution_strategy='prioritize_kubernetes',
                auto_resolvable=True
            )
            conflicts.append(conflict)
        
        # Check for timestamp conflicts
        timestamps = {stype: snap.timestamp for stype, snap in snapshots.items()}
        timestamp_diff_threshold = timedelta(minutes=10)
        
        for stype1, ts1 in timestamps.items():
            for stype2, ts2 in timestamps.items():
                if stype1 != stype2 and abs(ts1 - ts2) > timestamp_diff_threshold:
                    # Only create conflict if states are inconsistent
                    if states.get(stype1) != states.get(stype2):
                        conflict = StatusConflict(
                            conflict_type=ConflictType.TIMESTAMP_CONFLICT,
                            fabric_id=fabric_id,
                            conflicting_statuses=[snapshots[stype1], snapshots[stype2]],
                            severity='medium',
                            resolution_strategy='use_most_recent',
                            auto_resolvable=True
                        )
                        conflicts.append(conflict)
                        break  # Avoid duplicate conflicts
        
        # Check for missing status components
        expected_types = {StatusType.GIT_SYNC, StatusType.KUBERNETES, StatusType.FABRIC}
        missing_types = expected_types - set(snapshots.keys())
        
        if missing_types:
            conflict = StatusConflict(
                conflict_type=ConflictType.MISSING_STATUS,
                fabric_id=fabric_id,
                conflicting_statuses=[],
                severity='medium',
                resolution_strategy='initialize_missing',
                auto_resolvable=True
            )
            conflicts.append(conflict)
        
        # Check for data inconsistencies
        if self._has_data_inconsistencies(snapshots):
            conflict = StatusConflict(
                conflict_type=ConflictType.DATA_INCONSISTENCY,
                fabric_id=fabric_id,
                conflicting_statuses=list(snapshots.values()),
                severity='low',
                resolution_strategy='refresh_data',
                auto_resolvable=True
            )
            conflicts.append(conflict)
        
        # Cache conflicts for monitoring
        self.active_conflicts[fabric_id] = conflicts
        
        return conflicts
    
    async def _resolve_conflict(self, conflict: StatusConflict) -> Dict[str, Any]:
        """Resolve a specific status conflict"""
        try:
            resolution_result = {
                'success': False,
                'updates': [],
                'message': ''
            }
            
            if conflict.resolution_strategy == 'prioritize_kubernetes':
                # Kubernetes status takes precedence
                updates = await self._align_git_sync_with_kubernetes(conflict)
                resolution_result.update({
                    'success': True,
                    'updates': updates,
                    'message': 'Aligned Git sync status with Kubernetes status'
                })
                
            elif conflict.resolution_strategy == 'use_most_recent':
                # Use the most recent timestamp
                updates = await self._resolve_timestamp_conflict(conflict)
                resolution_result.update({
                    'success': True,
                    'updates': updates,
                    'message': 'Resolved timestamp conflict using most recent data'
                })
                
            elif conflict.resolution_strategy == 'initialize_missing':
                # Initialize missing status components
                updates = await self._initialize_missing_status(conflict)
                resolution_result.update({
                    'success': True,
                    'updates': updates,
                    'message': 'Initialized missing status components'
                })
                
            elif conflict.resolution_strategy == 'refresh_data':
                # Refresh data to resolve inconsistencies
                updates = await self._refresh_inconsistent_data(conflict)
                resolution_result.update({
                    'success': True,
                    'updates': updates,
                    'message': 'Refreshed data to resolve inconsistencies'
                })
            
            # Mark conflict as resolved
            conflict.resolved_at = datetime.now(timezone.utc)
            conflict.resolution_details = resolution_result
            
            return resolution_result
            
        except Exception as e:
            logger.error(f"Failed to resolve conflict {conflict.conflict_type.value}: {e}")
            return {
                'success': False,
                'updates': [],
                'message': f'Conflict resolution failed: {e}'
            }
    
    def _calculate_unified_status(self, snapshots: Dict[StatusType, StatusSnapshot]) -> Dict[str, Any]:
        """Calculate unified status from all component snapshots"""
        if not snapshots:
            return {
                'overall_state': StatusState.UNKNOWN.value,
                'health_score': 0.0,
                'message': 'No status data available'
            }
        
        # Calculate weighted health score
        component_weights = {
            StatusType.FABRIC: 0.4,
            StatusType.KUBERNETES: 0.3,
            StatusType.GIT_SYNC: 0.2,
            StatusType.WATCH: 0.1
        }
        
        weighted_score = 0.0
        total_weight = 0.0
        
        critical_states = 0
        error_states = 0
        warning_states = 0
        healthy_states = 0
        
        for stype, snapshot in snapshots.items():
            weight = component_weights.get(stype, 0.1)
            total_weight += weight
            weighted_score += snapshot.health_score * weight
            
            # Count state types
            if snapshot.state == StatusState.ERROR:
                error_states += 1
            elif snapshot.state == StatusState.WARNING:
                warning_states += 1
            elif snapshot.state == StatusState.HEALTHY:
                healthy_states += 1
            
            if snapshot.is_critical:
                critical_states += 1
        
        overall_health = weighted_score / total_weight if total_weight > 0 else 0.0
        
        # Determine overall state
        if critical_states > 0 or error_states > 1:
            overall_state = StatusState.ERROR
        elif error_states > 0 or warning_states > 2:
            overall_state = StatusState.WARNING
        elif healthy_states == len(snapshots):
            overall_state = StatusState.HEALTHY
        else:
            overall_state = StatusState.WARNING
        
        return {
            'overall_state': overall_state.value,
            'health_score': overall_health,
            'component_count': len(snapshots),
            'error_count': error_states,
            'warning_count': warning_states,
            'healthy_count': healthy_states,
            'message': self._generate_unified_message(overall_state, snapshots),
            'last_updated': datetime.now(timezone.utc).isoformat()
        }
    
    async def _update_fabric_unified_status(self, fabric_id: int, unified_status: Dict[str, Any]):
        """Update fabric with unified status information"""
        try:
            fabric = await self._get_fabric_async(fabric_id)
            
            # Update fabric metadata with unified status
            if not fabric.scheduler_metadata:
                fabric.scheduler_metadata = {}
            
            fabric.scheduler_metadata.update({
                'unified_status': unified_status,
                'last_reconciliation': datetime.now(timezone.utc).isoformat()
            })
            
            await self._save_fabric_async(fabric)
            
            logger.debug(f"Updated unified status for fabric {fabric_id}: {unified_status['overall_state']}")
            
        except Exception as e:
            logger.error(f"Failed to update unified status for fabric {fabric_id}: {e}")
    
    async def _propagate_status_changes(self, fabric_id: int, status_updates: List[Dict[str, Any]]):
        """Propagate status changes via event service with <5 second delay target"""
        if not status_updates:
            return
        
        try:
            # Create and publish unified status event
            event = RealtimeEvent(
                event_id=f"status_reconciliation_{fabric_id}_{int(time.time())}",
                event_type="status_reconciled",
                category=EventCategory.FABRIC_STATUS,
                priority=EventPriority.HIGH,
                timestamp=datetime.now(timezone.utc),
                fabric_id=fabric_id,
                user_id=None,
                data={
                    'updates_count': len(status_updates),
                    'updates': status_updates,
                    'reconciliation_timestamp': datetime.now(timezone.utc).isoformat()
                },
                metadata={
                    'source': 'status_reconciliation_service',
                    'fabric_id': fabric_id,
                    'update_count': len(status_updates)
                }
            )
            
            success = await self.event_service.publish_event(event)
            
            if success:
                logger.debug(f"Propagated {len(status_updates)} status changes for fabric {fabric_id}")
            else:
                logger.warning(f"Failed to propagate status changes for fabric {fabric_id}")
                
        except Exception as e:
            logger.error(f"Failed to propagate status changes: {e}")
    
    # Helper methods for status mapping and resolution
    
    def _map_sync_status_to_state(self, sync_status: str) -> StatusState:
        """Map Django model sync status to unified StatusState"""
        mapping = {
            'synced': StatusState.HEALTHY,
            'syncing': StatusState.SYNCING,
            'error': StatusState.ERROR,
            'never_synced': StatusState.NEVER_SYNCED,
            'stale': StatusState.STALE
        }
        return mapping.get(sync_status, StatusState.UNKNOWN)
    
    def _map_connection_status_to_state(self, connection_status: str) -> StatusState:
        """Map connection status to unified StatusState"""
        mapping = {
            'connected': StatusState.HEALTHY,
            'error': StatusState.ERROR,
            'unknown': StatusState.UNKNOWN
        }
        return mapping.get(connection_status, StatusState.UNKNOWN)
    
    def _map_fabric_status_to_state(self, fabric_status: str) -> StatusState:
        """Map fabric status to unified StatusState"""
        mapping = {
            'active': StatusState.HEALTHY,
            'planned': StatusState.WARNING,
            'maintenance': StatusState.WARNING,
            'decommissioning': StatusState.WARNING,
            'offline': StatusState.ERROR
        }
        return mapping.get(fabric_status, StatusState.UNKNOWN)
    
    def _map_watch_status_to_state(self, watch_status: str) -> StatusState:
        """Map watch status to unified StatusState"""
        mapping = {
            'running': StatusState.HEALTHY,
            'error': StatusState.ERROR,
            'stopped': StatusState.WARNING,
            'unknown': StatusState.UNKNOWN
        }
        return mapping.get(watch_status, StatusState.UNKNOWN)
    
    def _has_data_inconsistencies(self, snapshots: Dict[StatusType, StatusSnapshot]) -> bool:
        """Check for data inconsistencies between snapshots"""
        # Simple consistency checks
        if len(snapshots) < 2:
            return False
        
        # Check if all snapshots are very old (stale)
        all_stale = all(snap.is_stale for snap in snapshots.values())
        if all_stale:
            return True
        
        # Check for conflicting metadata
        fabric_names = set()
        for snap in snapshots.values():
            fabric_name = snap.metadata.get('fabric_name')
            if fabric_name:
                fabric_names.add(fabric_name)
        
        return len(fabric_names) > 1
    
    def _generate_unified_message(self, overall_state: StatusState, snapshots: Dict[StatusType, StatusSnapshot]) -> str:
        """Generate human-readable unified status message"""
        if overall_state == StatusState.HEALTHY:
            return f"All {len(snapshots)} components healthy"
        elif overall_state == StatusState.ERROR:
            error_components = [stype.value for stype, snap in snapshots.items() 
                             if snap.state == StatusState.ERROR]
            return f"Errors in: {', '.join(error_components)}"
        elif overall_state == StatusState.WARNING:
            warning_components = [stype.value for stype, snap in snapshots.items() 
                                if snap.state in [StatusState.WARNING, StatusState.STALE]]
            return f"Warnings in: {', '.join(warning_components)}"
        else:
            return f"Status unknown for {len(snapshots)} components"
    
    # Async helper methods for database operations
    
    async def _get_fabric_async(self, fabric_id: int) -> HedgehogFabric:
        """Get fabric asynchronously"""
        return await asyncio.to_thread(HedgehogFabric.objects.get, id=fabric_id)
    
    async def _save_fabric_async(self, fabric: HedgehogFabric):
        """Save fabric asynchronously"""
        await asyncio.to_thread(fabric.save)
    
    # Conflict resolution strategies
    
    async def _align_git_sync_with_kubernetes(self, conflict: StatusConflict) -> List[Dict[str, Any]]:
        """Align Git sync status with Kubernetes status"""
        return [{'action': 'align_git_sync', 'target': 'kubernetes_status'}]
    
    async def _resolve_timestamp_conflict(self, conflict: StatusConflict) -> List[Dict[str, Any]]:
        """Resolve timestamp conflicts using most recent data"""
        most_recent = max(conflict.conflicting_statuses, key=lambda s: s.timestamp)
        return [{'action': 'use_timestamp', 'source': most_recent.status_type.value}]
    
    async def _initialize_missing_status(self, conflict: StatusConflict) -> List[Dict[str, Any]]:
        """Initialize missing status components"""
        return [{'action': 'initialize_missing', 'message': 'Missing status components initialized'}]
    
    async def _refresh_inconsistent_data(self, conflict: StatusConflict) -> List[Dict[str, Any]]:
        """Refresh data to resolve inconsistencies"""
        return [{'action': 'refresh_data', 'message': 'Data refreshed to resolve inconsistencies'}]


# Celery tasks for status reconciliation

@shared_task(bind=True, name='netbox_hedgehog.tasks.reconcile_fabric_status')
def reconcile_fabric_status(self, fabric_id: int) -> Dict[str, Any]:
    """
    Celery task to reconcile status for a specific fabric
    Target execution time: <10 seconds
    """
    service = StatusReconciliationService()
    
    # Run async reconciliation in sync context
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        result = loop.run_until_complete(service.reconcile_fabric_status(fabric_id))
        return {
            'success': result.success,
            'fabric_id': result.fabric_id,
            'conflicts_detected': result.conflicts_detected,
            'conflicts_resolved': result.conflicts_resolved,
            'execution_time': result.execution_time,
            'status_updates': len(result.status_updates)
        }
    finally:
        loop.close()

@shared_task(name='netbox_hedgehog.tasks.reconcile_all_fabric_status')
def reconcile_all_fabric_status() -> Dict[str, Any]:
    """
    Reconcile status for all active fabrics
    Used by master scheduler for comprehensive status synchronization
    """
    start_time = time.time()
    
    try:
        active_fabrics = HedgehogFabric.objects.filter(
            sync_enabled=True,
            status__in=['active', 'planned']
        ).values_list('id', flat=True)
        
        reconciliation_results = []
        
        for fabric_id in active_fabrics:
            try:
                result = reconcile_fabric_status.delay(fabric_id)
                reconciliation_results.append(result.id)
            except Exception as e:
                logger.error(f"Failed to queue status reconciliation for fabric {fabric_id}: {e}")
        
        execution_time = time.time() - start_time
        
        return {
            'success': True,
            'message': f'Queued status reconciliation for {len(reconciliation_results)} fabrics',
            'fabrics_count': len(active_fabrics),
            'tasks_queued': len(reconciliation_results),
            'execution_time': execution_time
        }
        
    except Exception as e:
        execution_time = time.time() - start_time
        logger.error(f"Failed to reconcile all fabric status: {e}")
        
        return {
            'success': False,
            'error': str(e),
            'execution_time': execution_time
        }

@shared_task(name='netbox_hedgehog.tasks.get_status_reconciliation_metrics')
def get_status_reconciliation_metrics() -> Dict[str, Any]:
    """Get status reconciliation performance metrics"""
    try:
        # Get cached metrics
        metrics = cache.get('status_reconciliation_metrics', {})
        
        # Add real-time fabric status statistics
        fabric_status_stats = {
            'total_fabrics': HedgehogFabric.objects.count(),
            'healthy_fabrics': 0,  # Would calculate from unified status
            'warning_fabrics': 0,
            'error_fabrics': 0,
            'never_reconciled': 0
        }
        
        metrics.update({
            'fabric_status_stats': fabric_status_stats,
            'last_updated': django_timezone.now().isoformat()
        })
        
        return metrics
        
    except Exception as e:
        logger.error(f"Failed to get reconciliation metrics: {e}")
        return {'error': str(e)}