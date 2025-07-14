"""
Batch Reconciliation Operations
==============================

This module provides batch reconciliation operations for handling multiple
resources in coordinated batches. This is essential for maintaining consistency
when reconciling related resources or performing bulk operations.
"""

import logging
import asyncio
import uuid
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from django.utils import timezone
from django.db import transaction
from django.db.models import Q

from ..models import HedgehogFabric, HedgehogResource, ReconciliationAlert
from ..models.reconciliation import AlertSeverityChoices, AlertStatusChoices, ResolutionActionChoices
from ..models.gitops import ResourceStateChoices
from .orphaned_resource_detector import OrphanedResourceDetector
from .conflict_resolution import ConflictWorkflowManager

logger = logging.getLogger(__name__)


class BatchStatus(Enum):
    """Status of batch reconciliation operations"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BatchStrategy(Enum):
    """Strategies for batch processing"""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    DEPENDENCY_AWARE = "dependency_aware"
    PRIORITY_BASED = "priority_based"


@dataclass
class BatchItem:
    """Individual item in a batch operation"""
    resource: HedgehogResource
    alert: Optional[ReconciliationAlert] = None
    action: Optional[str] = None
    priority: int = 100
    dependencies: List[str] = field(default_factory=list)
    status: str = "pending"
    result: Optional[Dict[str, Any]] = None
    processing_time: float = 0.0
    error: Optional[str] = None


@dataclass
class BatchOperation:
    """Batch reconciliation operation"""
    batch_id: str
    fabric: HedgehogFabric
    items: List[BatchItem]
    strategy: BatchStrategy = BatchStrategy.SEQUENTIAL
    status: BatchStatus = BatchStatus.PENDING
    created_at: datetime = field(default_factory=timezone.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_items: int = 0
    processed_items: int = 0
    successful_items: int = 0
    failed_items: int = 0
    processing_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)


class BatchReconciliationManager:
    """
    Manages batch reconciliation operations for multiple resources.
    """
    
    def __init__(self, fabric: HedgehogFabric):
        self.fabric = fabric
        self.logger = logging.getLogger(f"{__name__}.{fabric.name}")
        self.active_batches: Dict[str, BatchOperation] = {}
    
    def create_batch_operation(self, resources: List[HedgehogResource], 
                              strategy: BatchStrategy = BatchStrategy.SEQUENTIAL,
                              metadata: Optional[Dict[str, Any]] = None) -> BatchOperation:
        """Create a new batch operation"""
        batch_id = str(uuid.uuid4())
        
        # Create batch items
        items = []
        for resource in resources:
            # Find active alerts for this resource
            active_alert = ReconciliationAlert.objects.filter(
                fabric=self.fabric,
                resource=resource,
                status__in=[AlertStatusChoices.ACTIVE, AlertStatusChoices.ACKNOWLEDGED]
            ).first()
            
            # Determine suggested action
            suggested_action = None
            if active_alert:
                suggested_action = active_alert.suggested_action
            elif resource.has_drift:
                suggested_action = ResolutionActionChoices.MANUAL_REVIEW
            
            item = BatchItem(
                resource=resource,
                alert=active_alert,
                action=suggested_action,
                priority=self._calculate_item_priority(resource, active_alert),
                dependencies=self._get_resource_dependencies(resource)
            )
            items.append(item)
        
        # Sort items by priority and dependencies
        items = self._sort_batch_items(items, strategy)
        
        batch = BatchOperation(
            batch_id=batch_id,
            fabric=self.fabric,
            items=items,
            strategy=strategy,
            total_items=len(items),
            metadata=metadata or {}
        )
        
        self.active_batches[batch_id] = batch
        self.logger.info(f"Created batch operation {batch_id} with {len(items)} items")
        
        return batch
    
    def create_orphaned_resource_batch(self) -> BatchOperation:
        """Create a batch operation for all orphaned resources"""
        orphaned_resources = HedgehogResource.objects.filter(
            fabric=self.fabric,
            resource_state=ResourceStateChoices.ORPHANED
        )
        
        return self.create_batch_operation(
            list(orphaned_resources),
            strategy=BatchStrategy.PRIORITY_BASED,
            metadata={'batch_type': 'orphaned_resources'}
        )
    
    def create_drift_resolution_batch(self) -> BatchOperation:
        """Create a batch operation for all drifted resources"""
        drifted_resources = HedgehogResource.objects.filter(
            fabric=self.fabric,
            resource_state=ResourceStateChoices.DRIFTED
        )
        
        return self.create_batch_operation(
            list(drifted_resources),
            strategy=BatchStrategy.DEPENDENCY_AWARE,
            metadata={'batch_type': 'drift_resolution'}
        )
    
    def create_alert_resolution_batch(self, alert_types: Optional[List[str]] = None) -> BatchOperation:
        """Create a batch operation for resolving alerts"""
        alert_query = ReconciliationAlert.objects.filter(
            fabric=self.fabric,
            status__in=[AlertStatusChoices.ACTIVE, AlertStatusChoices.ACKNOWLEDGED]
        )
        
        if alert_types:
            alert_query = alert_query.filter(alert_type__in=alert_types)
        
        alerts = list(alert_query)
        resources = [alert.resource for alert in alerts]
        
        return self.create_batch_operation(
            resources,
            strategy=BatchStrategy.PRIORITY_BASED,
            metadata={'batch_type': 'alert_resolution', 'alert_types': alert_types}
        )
    
    async def execute_batch(self, batch_id: str, dry_run: bool = False) -> BatchOperation:
        """Execute a batch operation"""
        batch = self.active_batches.get(batch_id)
        if not batch:
            raise ValueError(f"Batch {batch_id} not found")
        
        if batch.status != BatchStatus.PENDING:
            raise ValueError(f"Batch {batch_id} is not in pending state")
        
        self.logger.info(f"Starting batch execution {batch_id} (dry_run={dry_run})")
        
        batch.status = BatchStatus.RUNNING
        batch.started_at = timezone.now()
        
        try:
            if batch.strategy == BatchStrategy.SEQUENTIAL:
                await self._execute_sequential(batch, dry_run)
            elif batch.strategy == BatchStrategy.PARALLEL:
                await self._execute_parallel(batch, dry_run)
            elif batch.strategy == BatchStrategy.DEPENDENCY_AWARE:
                await self._execute_dependency_aware(batch, dry_run)
            elif batch.strategy == BatchStrategy.PRIORITY_BASED:
                await self._execute_priority_based(batch, dry_run)
            
            batch.status = BatchStatus.COMPLETED
            batch.completed_at = timezone.now()
            batch.processing_time = (batch.completed_at - batch.started_at).total_seconds()
            
            self.logger.info(f"Batch {batch_id} completed: {batch.successful_items}/{batch.total_items} successful")
            
        except Exception as e:
            batch.status = BatchStatus.FAILED
            batch.errors.append(f"Batch execution failed: {str(e)}")
            self.logger.error(f"Batch {batch_id} failed: {e}")
        
        return batch
    
    async def _execute_sequential(self, batch: BatchOperation, dry_run: bool):
        """Execute batch items sequentially"""
        for item in batch.items:
            await self._process_batch_item(item, batch, dry_run)
    
    async def _execute_parallel(self, batch: BatchOperation, dry_run: bool):
        """Execute batch items in parallel"""
        tasks = []
        for item in batch.items:
            task = asyncio.create_task(self._process_batch_item(item, batch, dry_run))
            tasks.append(task)
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _execute_dependency_aware(self, batch: BatchOperation, dry_run: bool):
        """Execute batch items based on dependencies"""
        completed = set()
        remaining = batch.items.copy()
        
        while remaining:
            # Find items that can be processed (no pending dependencies)
            ready_items = []
            for item in remaining:
                if all(dep in completed for dep in item.dependencies):
                    ready_items.append(item)
            
            if not ready_items:
                # Check for circular dependencies
                pending_deps = set()
                for item in remaining:
                    pending_deps.update(item.dependencies)
                
                if not pending_deps.intersection(completed):
                    batch.errors.append("Circular dependency detected")
                    break
                
                # Process items with fewest dependencies
                ready_items = sorted(remaining, key=lambda x: len(x.dependencies))[:1]
            
            # Process ready items in parallel
            tasks = []
            for item in ready_items:
                task = asyncio.create_task(self._process_batch_item(item, batch, dry_run))
                tasks.append(task)
            
            await asyncio.gather(*tasks, return_exceptions=True)
            
            # Update completed set
            for item in ready_items:
                completed.add(f"{item.resource.kind}/{item.resource.name}")
                remaining.remove(item)
    
    async def _execute_priority_based(self, batch: BatchOperation, dry_run: bool):
        """Execute batch items based on priority"""
        # Sort by priority (lower number = higher priority)
        sorted_items = sorted(batch.items, key=lambda x: x.priority)
        
        for item in sorted_items:
            await self._process_batch_item(item, batch, dry_run)
    
    async def _process_batch_item(self, item: BatchItem, batch: BatchOperation, dry_run: bool):
        """Process a single batch item"""
        start_time = timezone.now()
        item.status = "processing"
        
        try:
            # Process based on action
            if item.action == ResolutionActionChoices.IMPORT_TO_GIT:
                result = await self._import_to_git(item, dry_run)
            elif item.action == ResolutionActionChoices.DELETE_FROM_CLUSTER:
                result = await self._delete_from_cluster(item, dry_run)
            elif item.action == ResolutionActionChoices.UPDATE_GIT:
                result = await self._update_git(item, dry_run)
            elif item.action == ResolutionActionChoices.IGNORE:
                result = await self._ignore_resource(item, dry_run)
            else:
                result = await self._manual_review(item, dry_run)
            
            item.result = result
            item.status = "completed" if result.get('success') else "failed"
            
            if result.get('success'):
                batch.successful_items += 1
                
                # Resolve alert if present
                if item.alert and not dry_run:
                    item.alert.resolve(item.action, metadata=result)
            else:
                batch.failed_items += 1
                item.error = result.get('error', 'Unknown error')
            
            batch.processed_items += 1
            
        except Exception as e:
            item.status = "failed"
            item.error = str(e)
            batch.failed_items += 1
            batch.processed_items += 1
            self.logger.error(f"Failed to process batch item {item.resource.name}: {e}")
        
        finally:
            end_time = timezone.now()
            item.processing_time = (end_time - start_time).total_seconds()
    
    async def _import_to_git(self, item: BatchItem, dry_run: bool) -> Dict[str, Any]:
        """Import resource to Git repository"""
        if dry_run:
            return {
                'success': True,
                'message': f'Would import {item.resource.name} to Git',
                'action': 'import_to_git'
            }
        
        # TODO: Implement actual Git import
        return {
            'success': True,
            'message': f'Imported {item.resource.name} to Git (placeholder)',
            'action': 'import_to_git'
        }
    
    async def _delete_from_cluster(self, item: BatchItem, dry_run: bool) -> Dict[str, Any]:
        """Delete resource from cluster"""
        if dry_run:
            return {
                'success': True,
                'message': f'Would delete {item.resource.name} from cluster',
                'action': 'delete_from_cluster'
            }
        
        # TODO: Implement actual cluster deletion
        return {
            'success': True,
            'message': f'Deleted {item.resource.name} from cluster (placeholder)',
            'action': 'delete_from_cluster'
        }
    
    async def _update_git(self, item: BatchItem, dry_run: bool) -> Dict[str, Any]:
        """Update Git with cluster state"""
        if dry_run:
            return {
                'success': True,
                'message': f'Would update Git for {item.resource.name}',
                'action': 'update_git'
            }
        
        # TODO: Implement actual Git update
        return {
            'success': True,
            'message': f'Updated Git for {item.resource.name} (placeholder)',
            'action': 'update_git'
        }
    
    async def _ignore_resource(self, item: BatchItem, dry_run: bool) -> Dict[str, Any]:
        """Ignore resource (mark as resolved)"""
        return {
            'success': True,
            'message': f'Ignored {item.resource.name}',
            'action': 'ignore'
        }
    
    async def _manual_review(self, item: BatchItem, dry_run: bool) -> Dict[str, Any]:
        """Mark resource for manual review"""
        return {
            'success': True,
            'message': f'Marked {item.resource.name} for manual review',
            'action': 'manual_review'
        }
    
    def _calculate_item_priority(self, resource: HedgehogResource, 
                               alert: Optional[ReconciliationAlert]) -> int:
        """Calculate priority for a batch item"""
        base_priority = 100
        
        # Adjust based on alert severity
        if alert:
            severity_priorities = {
                AlertSeverityChoices.CRITICAL: 10,
                AlertSeverityChoices.HIGH: 30,
                AlertSeverityChoices.MEDIUM: 50,
                AlertSeverityChoices.LOW: 70
            }
            base_priority = severity_priorities.get(alert.severity, 100)
        
        # Adjust based on resource type
        if resource.kind == 'VPC':
            base_priority -= 10  # VPCs are typically foundational
        elif resource.kind in ['Server', 'Switch']:
            base_priority -= 5   # Infrastructure resources
        
        # Adjust based on drift score
        if resource.drift_score > 0.8:
            base_priority -= 20
        elif resource.drift_score > 0.5:
            base_priority -= 10
        
        return max(base_priority, 1)
    
    def _get_resource_dependencies(self, resource: HedgehogResource) -> List[str]:
        """Get resource dependencies for batch ordering"""
        dependencies = []
        
        # Get from relationship metadata
        if resource.relationship_metadata:
            deps = resource.relationship_metadata.get('dependencies', [])
            dependencies.extend(deps)
        
        # Get from resource spec
        spec = resource.desired_spec or resource.actual_spec or {}
        
        if 'vpc' in spec:
            dependencies.append(f"VPC/{spec['vpc']}")
        
        if 'ipv4Namespace' in spec:
            dependencies.append(f"IPv4Namespace/{spec['ipv4Namespace']}")
        
        return dependencies
    
    def _sort_batch_items(self, items: List[BatchItem], strategy: BatchStrategy) -> List[BatchItem]:
        """Sort batch items based on strategy"""
        if strategy == BatchStrategy.PRIORITY_BASED:
            return sorted(items, key=lambda x: x.priority)
        elif strategy == BatchStrategy.DEPENDENCY_AWARE:
            # Topological sort based on dependencies
            return self._topological_sort(items)
        else:
            return items
    
    def _topological_sort(self, items: List[BatchItem]) -> List[BatchItem]:
        """Perform topological sort on batch items"""
        # Build dependency graph
        item_map = {f"{item.resource.kind}/{item.resource.name}": item for item in items}
        
        # Kahn's algorithm for topological sorting
        in_degree = {item: 0 for item in items}
        
        for item in items:
            for dep in item.dependencies:
                if dep in item_map:
                    in_degree[item] += 1
        
        queue = [item for item in items if in_degree[item] == 0]
        result = []
        
        while queue:
            current = queue.pop(0)
            result.append(current)
            
            current_key = f"{current.resource.kind}/{current.resource.name}"
            
            for item in items:
                if current_key in item.dependencies:
                    in_degree[item] -= 1
                    if in_degree[item] == 0:
                        queue.append(item)
        
        return result
    
    def get_batch_status(self, batch_id: str) -> Optional[BatchOperation]:
        """Get status of a batch operation"""
        return self.active_batches.get(batch_id)
    
    def cancel_batch(self, batch_id: str) -> bool:
        """Cancel a batch operation"""
        batch = self.active_batches.get(batch_id)
        if batch and batch.status == BatchStatus.RUNNING:
            batch.status = BatchStatus.CANCELLED
            self.logger.info(f"Cancelled batch operation {batch_id}")
            return True
        return False
    
    def cleanup_completed_batches(self, older_than_hours: int = 24) -> int:
        """Clean up completed batch operations"""
        cutoff_time = timezone.now() - timedelta(hours=older_than_hours)
        
        removed_count = 0
        for batch_id, batch in list(self.active_batches.items()):
            if (batch.status in [BatchStatus.COMPLETED, BatchStatus.FAILED, BatchStatus.CANCELLED] and
                batch.completed_at and batch.completed_at < cutoff_time):
                del self.active_batches[batch_id]
                removed_count += 1
        
        self.logger.info(f"Cleaned up {removed_count} completed batch operations")
        return removed_count
    
    def get_batch_statistics(self) -> Dict[str, Any]:
        """Get statistics about batch operations"""
        stats = {
            'total_batches': len(self.active_batches),
            'by_status': {},
            'by_strategy': {},
            'processing_metrics': {
                'total_items_processed': 0,
                'average_processing_time': 0,
                'success_rate': 0
            }
        }
        
        if not self.active_batches:
            return stats
        
        # Count by status
        for batch in self.active_batches.values():
            status = batch.status.value
            stats['by_status'][status] = stats['by_status'].get(status, 0) + 1
        
        # Count by strategy
        for batch in self.active_batches.values():
            strategy = batch.strategy.value
            stats['by_strategy'][strategy] = stats['by_strategy'].get(strategy, 0) + 1
        
        # Calculate processing metrics
        completed_batches = [b for b in self.active_batches.values() if b.status == BatchStatus.COMPLETED]
        
        if completed_batches:
            total_items = sum(b.total_items for b in completed_batches)
            successful_items = sum(b.successful_items for b in completed_batches)
            total_time = sum(b.processing_time for b in completed_batches)
            
            stats['processing_metrics'] = {
                'total_items_processed': total_items,
                'average_processing_time': total_time / len(completed_batches),
                'success_rate': successful_items / total_items if total_items > 0 else 0
            }
        
        return stats