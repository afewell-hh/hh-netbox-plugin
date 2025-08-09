"""
Status Sync Service - Phase 2 Unified Status Synchronization Framework

Centralized status management hub providing event-driven status updates,
status consistency validation, and real-time synchronization across all components.

Architecture:
- Centralized status management hub for all fabric components
- Event-driven status updates with real-time propagation
- Status consistency validation and automated correction
- Integration with existing event service and scheduler
- High-performance caching and batch operations
"""

import logging
import time
import asyncio
from typing import Dict, Any, List, Optional, Set, Callable
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from enum import Enum
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from collections import defaultdict

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone as django_timezone
from django.conf import settings

from ..models.fabric import HedgehogFabric
from ..models.git_repository import GitRepository
from ..application.services.event_service import EventService
from ..domain.interfaces.event_service_interface import (
    EventPriority, EventCategory, RealtimeEvent, EventSubscription
)
from ..tasks.status_reconciliation import (
    StatusReconciliationService, StatusSnapshot, StatusType, StatusState
)

logger = logging.getLogger('netbox_hedgehog.status_sync')
performance_logger = logging.getLogger('netbox_hedgehog.performance')

# Status Sync Configuration and Data Models

@dataclass
class StatusSyncConfig:
    """Configuration for status synchronization behavior"""
    max_propagation_delay: float = 5.0  # seconds
    batch_size: int = 50
    cache_ttl: int = 300  # seconds
    reconciliation_interval: int = 60  # seconds
    consistency_check_interval: int = 120  # seconds
    max_retries: int = 3
    enable_real_time_propagation: bool = True
    enable_batch_processing: bool = True

@dataclass
class StatusUpdateRequest:
    """Request for status update operation"""
    fabric_id: int
    status_type: StatusType
    new_state: StatusState
    message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    source: str = "unknown"
    priority: EventPriority = EventPriority.NORMAL
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    @property
    def cache_key(self) -> str:
        return f"status_update_{self.fabric_id}_{self.status_type.value}"

@dataclass
class StatusValidationResult:
    """Result of status consistency validation"""
    fabric_id: int
    is_consistent: bool
    inconsistencies: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    validation_timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

@dataclass  
class SyncMetrics:
    """Metrics for status sync service performance"""
    total_updates: int = 0
    successful_updates: int = 0
    failed_updates: int = 0
    avg_propagation_delay: float = 0.0
    consistency_violations: int = 0
    cache_hit_rate: float = 0.0
    last_reset: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

class StatusUpdateType(Enum):
    """Types of status update operations"""
    DIRECT = "direct"           # Direct status change
    RECONCILIATION = "reconciliation"  # From reconciliation service
    SCHEDULED = "scheduled"     # From periodic scheduler
    EVENT_DRIVEN = "event_driven"  # From external events
    VALIDATION = "validation"   # From consistency validation

class StatusSyncService:
    """
    Centralized service for status synchronization and management
    Provides the main hub for all status-related operations
    """
    
    def __init__(self, config: Optional[StatusSyncConfig] = None):
        self.config = config or StatusSyncConfig()
        self.event_service = EventService()
        self.reconciliation_service = StatusReconciliationService()
        
        # Internal state management
        self.metrics = SyncMetrics()
        self.update_queue: List[StatusUpdateRequest] = []
        self.validation_cache: Dict[int, StatusValidationResult] = {}
        self.status_listeners: Dict[int, List[Callable]] = defaultdict(list)
        
        # Thread safety
        self._queue_lock = Lock()
        self._metrics_lock = Lock()
        self._cache_lock = Lock()
        
        # Background executor for async operations
        self.executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="status_sync")
        
        # Subscribe to relevant events
        self._setup_event_subscriptions()
        
        logger.info("Status Sync Service initialized with real-time propagation enabled")
    
    async def update_status(self, request: StatusUpdateRequest) -> Dict[str, Any]:
        """
        Main method to update status with real-time propagation
        
        Args:
            request: StatusUpdateRequest with update details
            
        Returns:
            Dict with update result and metrics
        """
        start_time = time.time()
        
        try:
            # Validate request
            validation_result = self._validate_update_request(request)
            if not validation_result['valid']:
                return {
                    'success': False,
                    'error': validation_result['error'],
                    'propagation_delay': 0.0
                }
            
            # Check for duplicate/redundant updates
            if await self._is_duplicate_update(request):
                return {
                    'success': True,
                    'message': 'Duplicate update filtered',
                    'propagation_delay': time.time() - start_time
                }
            
            # Execute the status update
            update_result = await self._execute_status_update(request)
            
            if update_result['success']:
                # Real-time propagation
                if self.config.enable_real_time_propagation:
                    await self._propagate_status_change(request, update_result)
                
                # Update metrics
                self._update_metrics(request, update_result, time.time() - start_time)
                
                # Schedule consistency validation if needed
                if request.priority in [EventPriority.HIGH, EventPriority.CRITICAL]:
                    asyncio.create_task(self._schedule_consistency_check(request.fabric_id))
            
            propagation_delay = time.time() - start_time
            
            return {
                'success': update_result['success'],
                'message': update_result.get('message', 'Status updated successfully'),
                'propagation_delay': propagation_delay,
                'fabric_id': request.fabric_id,
                'status_type': request.status_type.value,
                'new_state': request.new_state.value
            }
            
        except Exception as e:
            propagation_delay = time.time() - start_time
            logger.error(f"Status update failed for fabric {request.fabric_id}: {e}")
            
            with self._metrics_lock:
                self.metrics.failed_updates += 1
            
            return {
                'success': False,
                'error': str(e),
                'propagation_delay': propagation_delay,
                'fabric_id': request.fabric_id
            }
    
    async def batch_update_status(self, requests: List[StatusUpdateRequest]) -> Dict[str, Any]:
        """
        Batch update multiple status requests for optimal performance
        
        Args:
            requests: List of StatusUpdateRequest objects
            
        Returns:
            Dict with batch update results
        """
        if not self.config.enable_batch_processing:
            # Fall back to individual updates
            results = []
            for request in requests:
                result = await self.update_status(request)
                results.append(result)
            return {
                'success': all(r['success'] for r in results),
                'individual_results': results,
                'batch_size': len(requests)
            }
        
        start_time = time.time()
        
        try:
            # Group requests by fabric for efficient processing
            fabric_groups = defaultdict(list)
            for request in requests:
                fabric_groups[request.fabric_id].append(request)
            
            batch_results = []
            
            # Process each fabric group
            for fabric_id, fabric_requests in fabric_groups.items():
                try:
                    # Execute updates for this fabric
                    fabric_result = await self._batch_update_fabric(fabric_id, fabric_requests)
                    batch_results.append(fabric_result)
                    
                    # Real-time propagation for the fabric
                    if self.config.enable_real_time_propagation:
                        await self._propagate_batch_changes(fabric_id, fabric_requests, fabric_result)
                        
                except Exception as e:
                    logger.error(f"Batch update failed for fabric {fabric_id}: {e}")
                    batch_results.append({
                        'fabric_id': fabric_id,
                        'success': False,
                        'error': str(e)
                    })
            
            execution_time = time.time() - start_time
            successful_batches = sum(1 for result in batch_results if result.get('success', False))
            
            # Update batch metrics
            with self._metrics_lock:
                self.metrics.total_updates += len(requests)
                self.metrics.successful_updates += sum(r.get('updates_count', 0) for r in batch_results)
            
            return {
                'success': successful_batches > 0,
                'message': f'Processed {len(requests)} status updates across {len(fabric_groups)} fabrics',
                'batch_results': batch_results,
                'execution_time': execution_time,
                'total_requests': len(requests),
                'successful_fabrics': successful_batches
            }
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Batch status update failed: {e}")
            
            return {
                'success': False,
                'error': str(e),
                'execution_time': execution_time,
                'total_requests': len(requests)
            }
    
    async def validate_status_consistency(self, fabric_id: int, force_refresh: bool = False) -> StatusValidationResult:
        """
        Validate status consistency for a fabric
        
        Args:
            fabric_id: ID of fabric to validate
            force_refresh: Force refresh of validation cache
            
        Returns:
            StatusValidationResult with consistency information
        """
        # Check cache first unless forced refresh
        if not force_refresh and fabric_id in self.validation_cache:
            cached_result = self.validation_cache[fabric_id]
            # Use cached result if recent (within cache TTL)
            age = datetime.now(timezone.utc) - cached_result.validation_timestamp
            if age.total_seconds() < self.config.cache_ttl:
                return cached_result
        
        try:
            # Get current status snapshots
            snapshots = await self.reconciliation_service._collect_status_snapshots(fabric_id)
            
            # Perform consistency checks
            inconsistencies = []
            recommendations = []
            
            # Check 1: Timestamp consistency
            if len(snapshots) > 1:
                timestamps = [snap.timestamp for snap in snapshots.values()]
                time_spread = max(timestamps) - min(timestamps)
                if time_spread.total_seconds() > 600:  # 10 minutes
                    inconsistencies.append(f"Status timestamps span {time_spread.total_seconds():.0f} seconds")
                    recommendations.append("Synchronize status update timing")
            
            # Check 2: State consistency
            states = [snap.state for snap in snapshots.values()]
            error_states = sum(1 for state in states if state == StatusState.ERROR)
            if error_states > 0 and any(state == StatusState.HEALTHY for state in states):
                inconsistencies.append("Mixed error and healthy states detected")
                recommendations.append("Investigate and reconcile conflicting states")
            
            # Check 3: Data freshness
            stale_components = [snap.status_type.value for snap in snapshots.values() if snap.is_stale]
            if stale_components:
                inconsistencies.append(f"Stale data in components: {', '.join(stale_components)}")
                recommendations.append("Refresh stale status components")
            
            # Create validation result
            result = StatusValidationResult(
                fabric_id=fabric_id,
                is_consistent=len(inconsistencies) == 0,
                inconsistencies=inconsistencies,
                recommendations=recommendations
            )
            
            # Cache result
            with self._cache_lock:
                self.validation_cache[fabric_id] = result
            
            # Update metrics
            if not result.is_consistent:
                with self._metrics_lock:
                    self.metrics.consistency_violations += 1
            
            return result
            
        except Exception as e:
            logger.error(f"Status consistency validation failed for fabric {fabric_id}: {e}")
            return StatusValidationResult(
                fabric_id=fabric_id,
                is_consistent=False,
                inconsistencies=[f"Validation failed: {e}"],
                recommendations=["Retry validation or check system health"]
            )
    
    async def get_fabric_status_summary(self, fabric_id: int) -> Dict[str, Any]:
        """
        Get comprehensive status summary for a fabric
        
        Args:
            fabric_id: ID of fabric
            
        Returns:
            Dict with complete status summary
        """
        try:
            # Get status snapshots
            snapshots = await self.reconciliation_service._collect_status_snapshots(fabric_id)
            
            # Get validation result
            validation = await self.validate_status_consistency(fabric_id)
            
            # Calculate unified status
            unified_status = self.reconciliation_service._calculate_unified_status(snapshots)
            
            # Get recent status updates from cache
            recent_updates = self._get_recent_updates(fabric_id)
            
            return {
                'fabric_id': fabric_id,
                'unified_status': unified_status,
                'component_status': {
                    stype.value: {
                        'state': snap.state.value,
                        'message': snap.message,
                        'timestamp': snap.timestamp.isoformat(),
                        'is_stale': snap.is_stale,
                        'health_score': snap.health_score
                    }
                    for stype, snap in snapshots.items()
                },
                'consistency_validation': {
                    'is_consistent': validation.is_consistent,
                    'inconsistencies_count': len(validation.inconsistencies),
                    'recommendations_count': len(validation.recommendations),
                    'last_validated': validation.validation_timestamp.isoformat()
                },
                'recent_updates': recent_updates,
                'summary_timestamp': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get status summary for fabric {fabric_id}: {e}")
            return {
                'fabric_id': fabric_id,
                'error': str(e),
                'summary_timestamp': datetime.now(timezone.utc).isoformat()
            }
    
    def register_status_listener(self, fabric_id: int, callback: Callable[[StatusUpdateRequest], None]):
        """
        Register a callback for status updates on a specific fabric
        
        Args:
            fabric_id: Fabric to listen for
            callback: Function to call on status updates
        """
        self.status_listeners[fabric_id].append(callback)
        logger.debug(f"Registered status listener for fabric {fabric_id}")
    
    def get_sync_metrics(self) -> Dict[str, Any]:
        """Get current synchronization metrics"""
        with self._metrics_lock:
            metrics_dict = {
                'total_updates': self.metrics.total_updates,
                'successful_updates': self.metrics.successful_updates,
                'failed_updates': self.metrics.failed_updates,
                'success_rate': (
                    self.metrics.successful_updates / max(1, self.metrics.total_updates)
                ),
                'avg_propagation_delay': self.metrics.avg_propagation_delay,
                'consistency_violations': self.metrics.consistency_violations,
                'cache_hit_rate': self.metrics.cache_hit_rate,
                'queue_size': len(self.update_queue),
                'active_listeners': sum(len(listeners) for listeners in self.status_listeners.values()),
                'last_reset': self.metrics.last_reset.isoformat(),
                'current_time': datetime.now(timezone.utc).isoformat()
            }
        
        return metrics_dict
    
    def reset_metrics(self):
        """Reset synchronization metrics"""
        with self._metrics_lock:
            self.metrics = SyncMetrics()
        
        logger.info("Status sync metrics reset")
    
    # Private helper methods
    
    def _validate_update_request(self, request: StatusUpdateRequest) -> Dict[str, Any]:
        """Validate a status update request"""
        if not isinstance(request.fabric_id, int) or request.fabric_id <= 0:
            return {'valid': False, 'error': 'Invalid fabric_id'}
        
        if not isinstance(request.status_type, StatusType):
            return {'valid': False, 'error': 'Invalid status_type'}
        
        if not isinstance(request.new_state, StatusState):
            return {'valid': False, 'error': 'Invalid new_state'}
        
        return {'valid': True}
    
    async def _is_duplicate_update(self, request: StatusUpdateRequest) -> bool:
        """Check if update request is a duplicate"""
        cache_key = f"last_update_{request.fabric_id}_{request.status_type.value}"
        last_update = cache.get(cache_key)
        
        if last_update:
            # Check if same state and recent (within 10 seconds)
            if (last_update.get('state') == request.new_state.value and
                time.time() - last_update.get('timestamp', 0) < 10):
                return True
        
        return False
    
    async def _execute_status_update(self, request: StatusUpdateRequest) -> Dict[str, Any]:
        """Execute the actual status update"""
        try:
            # Get fabric
            fabric = await asyncio.to_thread(HedgehogFabric.objects.get, id=request.fabric_id)
            
            # Update appropriate status field based on type
            update_fields = []
            
            if request.status_type == StatusType.GIT_SYNC:
                fabric.sync_status = self._map_state_to_sync_status(request.new_state)
                if request.metadata.get('error'):
                    fabric.sync_error = str(request.metadata['error'])
                update_fields.extend(['sync_status', 'sync_error'])
                
            elif request.status_type == StatusType.KUBERNETES:
                fabric.connection_status = self._map_state_to_connection_status(request.new_state)
                if request.metadata.get('error'):
                    fabric.connection_error = str(request.metadata['error'])
                update_fields.extend(['connection_status', 'connection_error'])
                
            elif request.status_type == StatusType.FABRIC:
                if hasattr(fabric, 'status'):
                    fabric.status = self._map_state_to_fabric_status(request.new_state)
                    update_fields.append('status')
            
            # Update timestamp metadata
            if not fabric.scheduler_metadata:
                fabric.scheduler_metadata = {}
            
            fabric.scheduler_metadata.update({
                f'last_{request.status_type.value}_update': request.timestamp.isoformat(),
                f'{request.status_type.value}_source': request.source
            })
            update_fields.append('scheduler_metadata')
            
            # Save changes
            await asyncio.to_thread(fabric.save, update_fields=update_fields)
            
            # Cache the update
            cache_key = f"last_update_{request.fabric_id}_{request.status_type.value}"
            cache.set(cache_key, {
                'state': request.new_state.value,
                'timestamp': time.time(),
                'source': request.source
            }, timeout=3600)
            
            return {
                'success': True,
                'message': f'Updated {request.status_type.value} status to {request.new_state.value}',
                'fabric_name': fabric.name
            }
            
        except Exception as e:
            logger.error(f"Failed to execute status update: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _propagate_status_change(self, request: StatusUpdateRequest, update_result: Dict[str, Any]):
        """Propagate status change via event service"""
        try:
            # Create status change event
            event = RealtimeEvent(
                event_id=f"status_sync_{request.fabric_id}_{request.status_type.value}_{int(time.time())}",
                event_type=f"status_updated_{request.status_type.value}",
                category=EventCategory.FABRIC_STATUS,
                priority=request.priority,
                timestamp=request.timestamp,
                fabric_id=request.fabric_id,
                user_id=None,
                data={
                    'status_type': request.status_type.value,
                    'old_state': 'unknown',  # Could track this if needed
                    'new_state': request.new_state.value,
                    'message': request.message,
                    'source': request.source,
                    'update_metadata': request.metadata
                },
                metadata={
                    'source': 'status_sync_service',
                    'update_type': 'direct',
                    'propagation_timestamp': datetime.now(timezone.utc).isoformat()
                }
            )
            
            # Publish event
            success = await self.event_service.publish_event(event)
            
            if success:
                logger.debug(f"Propagated status change for fabric {request.fabric_id}")
                
                # Notify registered listeners
                for listener in self.status_listeners.get(request.fabric_id, []):
                    try:
                        listener(request)
                    except Exception as e:
                        logger.error(f"Status listener callback failed: {e}")
            else:
                logger.warning(f"Failed to propagate status change for fabric {request.fabric_id}")
                
        except Exception as e:
            logger.error(f"Status change propagation failed: {e}")
    
    async def _batch_update_fabric(self, fabric_id: int, requests: List[StatusUpdateRequest]) -> Dict[str, Any]:
        """Execute batch update for a single fabric"""
        try:
            successful_updates = 0
            
            # Group by status type for efficient updates
            status_updates = defaultdict(list)
            for request in requests:
                status_updates[request.status_type].append(request)
            
            # Execute updates
            fabric = await asyncio.to_thread(HedgehogFabric.objects.select_for_update().get, id=fabric_id)
            update_fields = set()
            
            for status_type, type_requests in status_updates.items():
                # Use latest request for each status type
                latest_request = max(type_requests, key=lambda r: r.timestamp)
                
                try:
                    result = await self._apply_status_update_to_fabric(fabric, latest_request)
                    if result['success']:
                        successful_updates += 1
                        update_fields.update(result.get('update_fields', []))
                except Exception as e:
                    logger.error(f"Failed to apply status update {status_type.value}: {e}")
            
            # Save all changes at once
            if update_fields:
                await asyncio.to_thread(fabric.save, update_fields=list(update_fields))
            
            return {
                'fabric_id': fabric_id,
                'success': successful_updates > 0,
                'updates_count': successful_updates,
                'total_requests': len(requests),
                'fabric_name': fabric.name
            }
            
        except Exception as e:
            logger.error(f"Batch update failed for fabric {fabric_id}: {e}")
            return {
                'fabric_id': fabric_id,
                'success': False,
                'error': str(e),
                'updates_count': 0
            }
    
    async def _propagate_batch_changes(self, fabric_id: int, requests: List[StatusUpdateRequest], 
                                     fabric_result: Dict[str, Any]):
        """Propagate batch status changes"""
        try:
            # Create batch update event
            event = RealtimeEvent(
                event_id=f"status_batch_{fabric_id}_{int(time.time())}",
                event_type="status_batch_updated",
                category=EventCategory.FABRIC_STATUS,
                priority=EventPriority.NORMAL,
                timestamp=datetime.now(timezone.utc),
                fabric_id=fabric_id,
                user_id=None,
                data={
                    'batch_size': len(requests),
                    'successful_updates': fabric_result.get('updates_count', 0),
                    'status_types': list(set(r.status_type.value for r in requests)),
                    'fabric_name': fabric_result.get('fabric_name', 'unknown')
                },
                metadata={
                    'source': 'status_sync_service',
                    'update_type': 'batch',
                    'propagation_timestamp': datetime.now(timezone.utc).isoformat()
                }
            )
            
            await self.event_service.publish_event(event)
            
        except Exception as e:
            logger.error(f"Batch change propagation failed: {e}")
    
    async def _apply_status_update_to_fabric(self, fabric: HedgehogFabric, 
                                           request: StatusUpdateRequest) -> Dict[str, Any]:
        """Apply a single status update to fabric model"""
        update_fields = []
        
        try:
            if request.status_type == StatusType.GIT_SYNC:
                fabric.sync_status = self._map_state_to_sync_status(request.new_state)
                if request.metadata.get('error'):
                    fabric.sync_error = str(request.metadata['error'])
                update_fields.extend(['sync_status', 'sync_error'])
                
            elif request.status_type == StatusType.KUBERNETES:
                fabric.connection_status = self._map_state_to_connection_status(request.new_state)
                if request.metadata.get('error'):
                    fabric.connection_error = str(request.metadata['error'])
                update_fields.extend(['connection_status', 'connection_error'])
            
            return {'success': True, 'update_fields': update_fields}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _update_metrics(self, request: StatusUpdateRequest, result: Dict[str, Any], delay: float):
        """Update synchronization metrics"""
        with self._metrics_lock:
            self.metrics.total_updates += 1
            
            if result['success']:
                self.metrics.successful_updates += 1
            else:
                self.metrics.failed_updates += 1
            
            # Update average propagation delay
            total_ops = self.metrics.successful_updates + self.metrics.failed_updates
            self.metrics.avg_propagation_delay = (
                (self.metrics.avg_propagation_delay * (total_ops - 1) + delay) / total_ops
            )
    
    async def _schedule_consistency_check(self, fabric_id: int):
        """Schedule consistency check for a fabric"""
        # Add small delay to allow propagation
        await asyncio.sleep(2)
        
        try:
            validation_result = await self.validate_status_consistency(fabric_id, force_refresh=True)
            
            if not validation_result.is_consistent:
                logger.warning(f"Consistency issues detected for fabric {fabric_id}: "
                             f"{len(validation_result.inconsistencies)} issues")
                
                # Could trigger automatic reconciliation here
                # await self.reconciliation_service.reconcile_fabric_status(fabric_id)
                
        except Exception as e:
            logger.error(f"Consistency check failed for fabric {fabric_id}: {e}")
    
    def _setup_event_subscriptions(self):
        """Setup event subscriptions for status updates"""
        try:
            # Subscribe to sync events
            sync_subscription = EventSubscription(
                subscription_id="status_sync_service",
                event_types=["sync_completed", "sync_failed", "connection_status_changed"],
                categories=[EventCategory.GIT_SYNC, EventCategory.FABRIC_STATUS],
                callback=self._handle_sync_event,
                fabric_ids=None,  # All fabrics
                user_id=None
            )
            
            self.event_service.subscribe(sync_subscription)
            logger.info("Status sync service subscribed to relevant events")
            
        except Exception as e:
            logger.error(f"Failed to setup event subscriptions: {e}")
    
    async def _handle_sync_event(self, event: RealtimeEvent):
        """Handle sync events and update status accordingly"""
        try:
            if not event.fabric_id:
                return
            
            # Create status update request based on event
            if event.event_type.startswith('sync_'):
                status_type = StatusType.GIT_SYNC
                if 'completed' in event.event_type:
                    new_state = StatusState.HEALTHY
                elif 'failed' in event.event_type:
                    new_state = StatusState.ERROR
                else:
                    new_state = StatusState.SYNCING
                    
            elif 'connection' in event.event_type:
                status_type = StatusType.KUBERNETES
                new_state = StatusState.HEALTHY if 'connected' in event.event_type else StatusState.ERROR
            else:
                return
            
            # Create and process update request
            update_request = StatusUpdateRequest(
                fabric_id=event.fabric_id,
                status_type=status_type,
                new_state=new_state,
                message=f"Updated from event: {event.event_type}",
                source="event_service",
                priority=event.priority,
                timestamp=event.timestamp,
                metadata=event.data
            )
            
            await self.update_status(update_request)
            
        except Exception as e:
            logger.error(f"Failed to handle sync event {event.event_id}: {e}")
    
    def _get_recent_updates(self, fabric_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent status updates from cache"""
        try:
            updates = []
            for status_type in StatusType:
                cache_key = f"last_update_{fabric_id}_{status_type.value}"
                update_info = cache.get(cache_key)
                if update_info:
                    updates.append({
                        'status_type': status_type.value,
                        'state': update_info.get('state'),
                        'timestamp': update_info.get('timestamp'),
                        'source': update_info.get('source')
                    })
            
            # Sort by timestamp and limit
            updates.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
            return updates[:limit]
            
        except Exception as e:
            logger.error(f"Failed to get recent updates for fabric {fabric_id}: {e}")
            return []
    
    # Status mapping helper methods
    
    def _map_state_to_sync_status(self, state: StatusState) -> str:
        """Map StatusState to Django model sync status"""
        mapping = {
            StatusState.HEALTHY: 'synced',
            StatusState.SYNCING: 'syncing',
            StatusState.ERROR: 'error',
            StatusState.NEVER_SYNCED: 'never_synced',
            StatusState.STALE: 'stale',
            StatusState.WARNING: 'stale'
        }
        return mapping.get(state, 'unknown')
    
    def _map_state_to_connection_status(self, state: StatusState) -> str:
        """Map StatusState to Django model connection status"""
        mapping = {
            StatusState.HEALTHY: 'connected',
            StatusState.ERROR: 'error',
            StatusState.WARNING: 'unknown',
            StatusState.UNKNOWN: 'unknown'
        }
        return mapping.get(state, 'unknown')
    
    def _map_state_to_fabric_status(self, state: StatusState) -> str:
        """Map StatusState to Django model fabric status"""
        mapping = {
            StatusState.HEALTHY: 'active',
            StatusState.ERROR: 'offline',
            StatusState.WARNING: 'planned',
            StatusState.UNKNOWN: 'planned'
        }
        return mapping.get(state, 'planned')
    
    def __del__(self):
        """Cleanup resources on destruction"""
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=False)


# Global instance for easy access
_status_sync_service = None

def get_status_sync_service() -> StatusSyncService:
    """Get global StatusSyncService instance"""
    global _status_sync_service
    if _status_sync_service is None:
        _status_sync_service = StatusSyncService()
    return _status_sync_service