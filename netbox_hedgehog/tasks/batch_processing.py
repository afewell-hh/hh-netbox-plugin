"""
Enhanced Batch Processing - Optimized CRD Processing with Performance Monitoring

Implements high-performance batch processing for CRD operations with adaptive sizing,
performance monitoring, and integration with existing sync mechanisms and reliability patterns.

Architecture:
- Adaptive batch sizing based on performance metrics
- Parallel processing with configurable concurrency
- Performance monitoring and optimization
- Integration with circuit breaker and saga patterns
- Resource-aware processing with memory management
"""

import logging
import time
import asyncio
from typing import Dict, Any, List, Optional, Union, Callable, Tuple
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from threading import Lock, Semaphore
from collections import defaultdict, deque
import statistics
import psutil
import gc

from django.core.cache import cache
from django.db import transaction, connections
from django.utils import timezone as django_timezone
from django.conf import settings

from ..models.fabric import HedgehogFabric
from ..utils.kubernetes import KubernetesClient, KubernetesSync
from ..services.status_sync_service import get_status_sync_service, StatusUpdateRequest
from ..services.integration_coordinator import get_integration_coordinator
from ..domain.circuit_breaker import get_circuit_breaker_manager, protected_kubernetes_call
from ..domain.sync_saga import get_saga_orchestrator
from ..tasks.status_reconciliation import StatusType, StatusState
from ..application.services.event_service import EventService
from ..domain.interfaces.event_service_interface import EventPriority, EventCategory, RealtimeEvent

logger = logging.getLogger('netbox_hedgehog.batch_processing')
performance_logger = logging.getLogger('netbox_hedgehog.performance')

# Batch Processing Configuration and Data Models

class BatchStrategy(Enum):
    """Batch processing strategies"""
    FIXED_SIZE = "fixed_size"           # Fixed batch size
    ADAPTIVE = "adaptive"               # Adaptive sizing based on performance
    RESOURCE_AWARE = "resource_aware"   # Based on system resources
    PRIORITY_BASED = "priority_based"   # Prioritize by resource importance

class ProcessingMode(Enum):
    """Processing execution modes"""
    SEQUENTIAL = "sequential"           # Process batches one by one
    PARALLEL = "parallel"               # Process batches in parallel
    HYBRID = "hybrid"                   # Mix of sequential and parallel

@dataclass
class BatchProcessingConfig:
    """Configuration for batch processing"""
    default_batch_size: int = 50
    min_batch_size: int = 10
    max_batch_size: int = 200
    max_concurrent_batches: int = 4
    batch_timeout: int = 300  # seconds
    adaptive_sizing: bool = True
    resource_monitoring: bool = True
    performance_optimization: bool = True
    memory_threshold: float = 0.8  # 80% memory usage threshold
    cpu_threshold: float = 0.7     # 70% CPU usage threshold
    strategy: BatchStrategy = BatchStrategy.ADAPTIVE
    processing_mode: ProcessingMode = ProcessingMode.HYBRID
    enable_circuit_breaker: bool = True
    enable_saga_pattern: bool = True
    metrics_retention: int = 3600  # seconds

@dataclass
class BatchMetrics:
    """Performance metrics for batch processing"""
    batch_id: str
    batch_size: int
    processing_time: float
    throughput: float  # items per second
    success_count: int
    failure_count: int
    memory_usage_mb: float
    cpu_usage_percent: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate"""
        total = self.success_count + self.failure_count
        return self.success_count / max(1, total)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary"""
        return {
            'batch_id': self.batch_id,
            'batch_size': self.batch_size,
            'processing_time': self.processing_time,
            'throughput': self.throughput,
            'success_count': self.success_count,
            'failure_count': self.failure_count,
            'success_rate': self.success_rate,
            'memory_usage_mb': self.memory_usage_mb,
            'cpu_usage_percent': self.cpu_usage_percent,
            'timestamp': self.timestamp.isoformat()
        }

@dataclass
class BatchOperation:
    """Individual batch operation definition"""
    operation_id: str
    fabric_id: int
    fabric_name: str
    operation_type: str  # 'apply', 'delete', 'update', 'sync'
    resources: List[Any]
    priority: int = 5  # 1-10, lower is higher priority
    timeout: int = 300  # seconds
    retry_count: int = 0
    max_retries: int = 3
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

class BatchProcessor:
    """
    Enhanced batch processor with adaptive sizing and performance monitoring
    """
    
    def __init__(self, config: Optional[BatchProcessingConfig] = None):
        self.config = config or BatchProcessingConfig()
        self.status_sync_service = get_status_sync_service()
        self.integration_coordinator = get_integration_coordinator()
        self.circuit_breaker_manager = get_circuit_breaker_manager()
        self.saga_orchestrator = get_saga_orchestrator()
        self.event_service = EventService()
        
        # Performance tracking
        self.metrics_history: deque = deque(maxlen=1000)
        self.current_batch_size = self.config.default_batch_size
        self.performance_optimizer = PerformanceOptimizer(self.config)
        
        # Resource monitoring
        self.system_monitor = SystemResourceMonitor()
        
        # Thread safety and concurrency control
        self._processing_lock = Lock()
        self._metrics_lock = Lock()
        self._batch_semaphore = Semaphore(self.config.max_concurrent_batches)
        
        # Execution pools
        self.thread_executor = ThreadPoolExecutor(
            max_workers=self.config.max_concurrent_batches * 2,
            thread_name_prefix="batch_processor"
        )
        
        # Active operations tracking
        self.active_operations: Dict[str, BatchOperation] = {}
        
        logger.info(f"Batch Processor initialized with {self.config.strategy.value} strategy")
    
    async def process_crd_batch(self, fabric_id: int, operation_type: str,
                              resources: List[Any], priority: int = 5) -> Dict[str, Any]:
        """
        Process a batch of CRD operations with optimized performance
        
        Args:
            fabric_id: ID of the fabric
            operation_type: Type of operation ('apply', 'delete', 'update', 'sync')
            resources: List of resources to process
            priority: Priority level (1-10, lower is higher priority)
            
        Returns:
            Dict with batch processing results
        """
        start_time = time.time()
        operation_id = f"batch_{operation_type}_{fabric_id}_{int(time.time())}"
        
        try:
            # Get fabric
            fabric = await asyncio.to_thread(HedgehogFabric.objects.get, id=fabric_id)
            
            # Create batch operation
            batch_operation = BatchOperation(
                operation_id=operation_id,
                fabric_id=fabric_id,
                fabric_name=fabric.name,
                operation_type=operation_type,
                resources=resources,
                priority=priority,
                timeout=self.config.batch_timeout,
                metadata={
                    'total_resources': len(resources),
                    'initiated_at': datetime.now(timezone.utc).isoformat()
                }
            )
            
            # Register operation
            await self._register_batch_operation(batch_operation)
            
            # Check system resources before processing
            if not await self._check_system_resources():
                return {
                    'success': False,
                    'error': 'System resources insufficient for batch processing',
                    'operation_id': operation_id,
                    'duration': time.time() - start_time
                }
            
            # Determine optimal batch sizing
            optimal_batch_size = await self._calculate_optimal_batch_size(
                len(resources), operation_type, fabric
            )
            
            # Split resources into optimally-sized batches
            resource_batches = self._create_resource_batches(resources, optimal_batch_size)
            
            # Execute batch processing with selected strategy
            if self.config.processing_mode == ProcessingMode.SEQUENTIAL:
                processing_result = await self._process_batches_sequential(
                    batch_operation, resource_batches, fabric
                )
            elif self.config.processing_mode == ProcessingMode.PARALLEL:
                processing_result = await self._process_batches_parallel(
                    batch_operation, resource_batches, fabric
                )
            else:  # HYBRID
                processing_result = await self._process_batches_hybrid(
                    batch_operation, resource_batches, fabric
                )
            
            # Update metrics and optimization
            batch_duration = time.time() - start_time
            await self._record_batch_metrics(batch_operation, processing_result, batch_duration)
            await self._update_performance_optimization(processing_result)
            
            # Update status
            await self._update_batch_status(fabric, processing_result)
            
            return {
                'success': processing_result['success'],
                'operation_id': operation_id,
                'fabric_name': fabric.name,
                'operation_type': operation_type,
                'duration': batch_duration,
                'resources_processed': processing_result.get('total_processed', 0),
                'resources_successful': processing_result.get('total_successful', 0),
                'resources_failed': processing_result.get('total_failed', 0),
                'batches_count': len(resource_batches),
                'optimal_batch_size': optimal_batch_size,
                'throughput': processing_result.get('throughput', 0.0),
                'message': processing_result.get('message', 'Batch processing completed')
            }
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Batch processing failed for operation {operation_id}: {e}")
            
            return {
                'success': False,
                'error': str(e),
                'operation_id': operation_id,
                'duration': duration
            }
        finally:
            # Cleanup operation
            await self._cleanup_batch_operation(operation_id)
    
    async def process_fabric_sync_batch(self, fabric_id: int, 
                                      resource_types: Optional[List[str]] = None,
                                      bidirectional: bool = True) -> Dict[str, Any]:
        """
        Process fabric sync using optimized batch processing
        
        Args:
            fabric_id: ID of fabric to sync
            resource_types: Specific resource types to sync
            bidirectional: Whether to perform bidirectional sync
            
        Returns:
            Dict with sync results
        """
        start_time = time.time()
        operation_id = f"fabric_sync_batch_{fabric_id}_{int(time.time())}"
        
        try:
            fabric = await asyncio.to_thread(HedgehogFabric.objects.get, id=fabric_id)
            
            if self.config.enable_saga_pattern and bidirectional:
                # Use saga pattern for complex bidirectional sync
                sync_result = await self.saga_orchestrator.execute_bidirectional_sync_saga(
                    fabric_id, resource_types, EventPriority.NORMAL
                )
                
                return {
                    'success': sync_result['success'],
                    'operation_id': operation_id,
                    'fabric_name': fabric.name,
                    'sync_type': 'bidirectional_saga',
                    'duration': time.time() - start_time,
                    'saga_id': sync_result.get('saga_id'),
                    'steps_completed': sync_result.get('steps_completed', 0),
                    'message': sync_result.get('message', 'Saga-based sync completed')
                }
            else:
                # Use direct batch processing
                if bidirectional:
                    sync_result = await self.integration_coordinator.sync_fabric_bidirectional(
                        fabric_id, priority=EventPriority.NORMAL
                    )
                else:
                    sync_result = await self.integration_coordinator.sync_netbox_to_kubernetes(
                        fabric_id, resource_types
                    )
                
                return {
                    'success': sync_result['success'],
                    'operation_id': operation_id,
                    'fabric_name': fabric.name,
                    'sync_type': 'bidirectional' if bidirectional else 'netbox_to_k8s',
                    'duration': time.time() - start_time,
                    'resources_processed': sync_result.get('resources_processed', 0),
                    'message': sync_result.get('message', 'Direct sync completed')
                }
                
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Fabric sync batch processing failed: {e}")
            
            return {
                'success': False,
                'error': str(e),
                'operation_id': operation_id,
                'duration': duration
            }
    
    async def get_batch_metrics(self) -> Dict[str, Any]:
        """Get comprehensive batch processing metrics"""
        with self._metrics_lock:
            if not self.metrics_history:
                return {
                    'no_data': True,
                    'message': 'No batch processing metrics available'
                }
            
            recent_metrics = list(self.metrics_history)[-50:]  # Last 50 batches
            
            # Calculate aggregate metrics
            avg_processing_time = statistics.mean(m.processing_time for m in recent_metrics)
            avg_throughput = statistics.mean(m.throughput for m in recent_metrics)
            avg_success_rate = statistics.mean(m.success_rate for m in recent_metrics)
            avg_batch_size = statistics.mean(m.batch_size for m in recent_metrics)
            
            # Memory and CPU usage
            avg_memory = statistics.mean(m.memory_usage_mb for m in recent_metrics)
            avg_cpu = statistics.mean(m.cpu_usage_percent for m in recent_metrics)
            
            # Throughput trends
            throughput_trend = self._calculate_trend([m.throughput for m in recent_metrics[-10:]])
            
            return {
                'summary': {
                    'total_batches': len(self.metrics_history),
                    'recent_batches': len(recent_metrics),
                    'avg_processing_time': avg_processing_time,
                    'avg_throughput': avg_throughput,
                    'avg_success_rate': avg_success_rate,
                    'avg_batch_size': avg_batch_size
                },
                'performance': {
                    'current_batch_size': self.current_batch_size,
                    'throughput_trend': throughput_trend,
                    'avg_memory_usage_mb': avg_memory,
                    'avg_cpu_usage_percent': avg_cpu
                },
                'configuration': {
                    'strategy': self.config.strategy.value,
                    'processing_mode': self.config.processing_mode.value,
                    'adaptive_sizing': self.config.adaptive_sizing,
                    'max_concurrent_batches': self.config.max_concurrent_batches
                },
                'optimization': await self.performance_optimizer.get_metrics(),
                'system_resources': await self.system_monitor.get_current_usage(),
                'active_operations': len(self.active_operations),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
    
    async def optimize_batch_size(self, target_throughput: Optional[float] = None) -> Dict[str, Any]:
        """
        Manually trigger batch size optimization
        
        Args:
            target_throughput: Target throughput (items/second)
            
        Returns:
            Dict with optimization results
        """
        optimization_result = await self.performance_optimizer.optimize_batch_size(
            self.metrics_history, target_throughput
        )
        
        if optimization_result['optimized']:
            self.current_batch_size = optimization_result['new_batch_size']
            logger.info(f"Batch size optimized to {self.current_batch_size}")
        
        return optimization_result
    
    # Private helper methods
    
    async def _register_batch_operation(self, operation: BatchOperation):
        """Register batch operation for tracking"""
        with self._processing_lock:
            self.active_operations[operation.operation_id] = operation
        
        logger.info(f"Registered batch operation {operation.operation_id} for fabric {operation.fabric_name}")
    
    async def _cleanup_batch_operation(self, operation_id: str):
        """Clean up completed batch operation"""
        with self._processing_lock:
            self.active_operations.pop(operation_id, None)
    
    async def _check_system_resources(self) -> bool:
        """Check if system has sufficient resources for batch processing"""
        if not self.config.resource_monitoring:
            return True
        
        resource_usage = await self.system_monitor.get_current_usage()
        
        if resource_usage['memory_percent'] > self.config.memory_threshold * 100:
            logger.warning(f"Memory usage too high: {resource_usage['memory_percent']:.1f}%")
            return False
        
        if resource_usage['cpu_percent'] > self.config.cpu_threshold * 100:
            logger.warning(f"CPU usage too high: {resource_usage['cpu_percent']:.1f}%")
            return False
        
        return True
    
    async def _calculate_optimal_batch_size(self, total_resources: int, operation_type: str,
                                          fabric: HedgehogFabric) -> int:
        """Calculate optimal batch size based on various factors"""
        if not self.config.adaptive_sizing:
            return self.config.default_batch_size
        
        # Start with current optimized size
        optimal_size = self.current_batch_size
        
        # Adjust based on resource count
        if total_resources < 20:
            optimal_size = min(optimal_size, total_resources)
        elif total_resources > 500:
            optimal_size = min(optimal_size * 1.5, self.config.max_batch_size)
        
        # Adjust based on operation type
        operation_multipliers = {
            'apply': 1.0,
            'update': 0.8,
            'delete': 1.2,
            'sync': 0.9
        }
        optimal_size *= operation_multipliers.get(operation_type, 1.0)
        
        # Adjust based on system resources
        system_usage = await self.system_monitor.get_current_usage()
        if system_usage['memory_percent'] > 60:
            optimal_size *= 0.8
        if system_usage['cpu_percent'] > 50:
            optimal_size *= 0.9
        
        # Apply constraints
        optimal_size = max(self.config.min_batch_size, 
                          min(int(optimal_size), self.config.max_batch_size))
        
        logger.debug(f"Calculated optimal batch size: {optimal_size} for {total_resources} resources")
        return optimal_size
    
    def _create_resource_batches(self, resources: List[Any], batch_size: int) -> List[List[Any]]:
        """Split resources into batches of optimal size"""
        batches = []
        for i in range(0, len(resources), batch_size):
            batch = resources[i:i + batch_size]
            batches.append(batch)
        
        logger.debug(f"Created {len(batches)} batches from {len(resources)} resources")
        return batches
    
    async def _process_batches_sequential(self, operation: BatchOperation, 
                                        resource_batches: List[List[Any]],
                                        fabric: HedgehogFabric) -> Dict[str, Any]:
        """Process batches sequentially"""
        total_processed = 0
        total_successful = 0
        total_failed = 0
        batch_results = []
        
        for i, batch_resources in enumerate(resource_batches):
            batch_id = f"{operation.operation_id}_batch_{i}"
            
            try:
                batch_result = await self._process_single_batch(
                    batch_id, operation, batch_resources, fabric
                )
                
                total_processed += batch_result.get('processed', 0)
                total_successful += batch_result.get('successful', 0)
                total_failed += batch_result.get('failed', 0)
                
                batch_results.append(batch_result)
                
                # Small delay between batches to prevent overload
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Batch {batch_id} processing failed: {e}")
                total_failed += len(batch_resources)
                
                batch_results.append({
                    'batch_id': batch_id,
                    'processed': len(batch_resources),
                    'successful': 0,
                    'failed': len(batch_resources),
                    'error': str(e)
                })
        
        throughput = total_processed / max(1, sum(br.get('processing_time', 0) for br in batch_results))
        
        return {
            'success': total_failed == 0 or total_successful > 0,
            'processing_mode': 'sequential',
            'total_processed': total_processed,
            'total_successful': total_successful,
            'total_failed': total_failed,
            'throughput': throughput,
            'batch_results': batch_results,
            'message': f'Sequential processing completed: {total_successful}/{total_processed} successful'
        }
    
    async def _process_batches_parallel(self, operation: BatchOperation,
                                      resource_batches: List[List[Any]],
                                      fabric: HedgehogFabric) -> Dict[str, Any]:
        """Process batches in parallel"""
        # Create batch processing tasks
        batch_tasks = []
        for i, batch_resources in enumerate(resource_batches):
            batch_id = f"{operation.operation_id}_batch_{i}"
            task = asyncio.create_task(
                self._process_single_batch(batch_id, operation, batch_resources, fabric)
            )
            batch_tasks.append(task)
        
        # Wait for all batches to complete
        batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
        
        # Process results
        total_processed = 0
        total_successful = 0
        total_failed = 0
        successful_results = []
        
        for i, result in enumerate(batch_results):
            if isinstance(result, Exception):
                logger.error(f"Batch {i} failed with exception: {result}")
                batch_size = len(resource_batches[i])
                total_failed += batch_size
                successful_results.append({
                    'batch_id': f"{operation.operation_id}_batch_{i}",
                    'processed': batch_size,
                    'successful': 0,
                    'failed': batch_size,
                    'error': str(result)
                })
            else:
                total_processed += result.get('processed', 0)
                total_successful += result.get('successful', 0)
                total_failed += result.get('failed', 0)
                successful_results.append(result)
        
        # Calculate throughput
        processing_times = [r.get('processing_time', 0) for r in successful_results if isinstance(r, dict)]
        avg_processing_time = statistics.mean(processing_times) if processing_times else 1
        throughput = total_processed / max(1, avg_processing_time)
        
        return {
            'success': total_failed == 0 or total_successful > 0,
            'processing_mode': 'parallel',
            'total_processed': total_processed,
            'total_successful': total_successful,
            'total_failed': total_failed,
            'throughput': throughput,
            'batch_results': successful_results,
            'message': f'Parallel processing completed: {total_successful}/{total_processed} successful'
        }
    
    async def _process_batches_hybrid(self, operation: BatchOperation,
                                    resource_batches: List[List[Any]],
                                    fabric: HedgehogFabric) -> Dict[str, Any]:
        """Process batches using hybrid approach (parallel groups processed sequentially)"""
        # Group batches for parallel processing
        parallel_group_size = min(self.config.max_concurrent_batches, len(resource_batches))
        
        total_processed = 0
        total_successful = 0
        total_failed = 0
        all_batch_results = []
        
        # Process batches in parallel groups
        for group_start in range(0, len(resource_batches), parallel_group_size):
            group_end = min(group_start + parallel_group_size, len(resource_batches))
            batch_group = resource_batches[group_start:group_end]
            
            # Process this group in parallel
            group_tasks = []
            for i, batch_resources in enumerate(batch_group):
                batch_id = f"{operation.operation_id}_batch_{group_start + i}"
                task = asyncio.create_task(
                    self._process_single_batch(batch_id, operation, batch_resources, fabric)
                )
                group_tasks.append(task)
            
            # Wait for group to complete
            group_results = await asyncio.gather(*group_tasks, return_exceptions=True)
            
            # Process group results
            for i, result in enumerate(group_results):
                if isinstance(result, Exception):
                    logger.error(f"Batch group {group_start + i} failed: {result}")
                    batch_size = len(batch_group[i])
                    total_failed += batch_size
                    all_batch_results.append({
                        'batch_id': f"{operation.operation_id}_batch_{group_start + i}",
                        'processed': batch_size,
                        'successful': 0,
                        'failed': batch_size,
                        'error': str(result)
                    })
                else:
                    total_processed += result.get('processed', 0)
                    total_successful += result.get('successful', 0)
                    total_failed += result.get('failed', 0)
                    all_batch_results.append(result)
            
            # Brief pause between groups
            if group_end < len(resource_batches):
                await asyncio.sleep(0.2)
        
        # Calculate throughput
        processing_times = [r.get('processing_time', 0) for r in all_batch_results if isinstance(r, dict)]
        avg_processing_time = statistics.mean(processing_times) if processing_times else 1
        throughput = total_processed / max(1, avg_processing_time)
        
        return {
            'success': total_failed == 0 or total_successful > 0,
            'processing_mode': 'hybrid',
            'total_processed': total_processed,
            'total_successful': total_successful,
            'total_failed': total_failed,
            'throughput': throughput,
            'batch_results': all_batch_results,
            'parallel_groups': len(range(0, len(resource_batches), parallel_group_size)),
            'message': f'Hybrid processing completed: {total_successful}/{total_processed} successful'
        }
    
    async def _process_single_batch(self, batch_id: str, operation: BatchOperation,
                                  batch_resources: List[Any], fabric: HedgehogFabric) -> Dict[str, Any]:
        """Process a single batch of resources"""
        start_time = time.time()
        
        try:
            # Acquire semaphore to limit concurrent batches
            async with asyncio.Semaphore(1):  # Individual batch semaphore
                
                successful = 0
                failed = 0
                errors = []
                
                # Process each resource in the batch
                if operation.operation_type in ['apply', 'update']:
                    # Apply/Update operations to Kubernetes
                    result = await self._apply_resources_to_kubernetes(
                        fabric, batch_resources, self.config.enable_circuit_breaker
                    )
                    successful = result.get('successful', 0)
                    failed = result.get('failed', 0)
                    errors = result.get('errors', [])
                    
                elif operation.operation_type == 'delete':
                    # Delete operations from Kubernetes
                    result = await self._delete_resources_from_kubernetes(
                        fabric, batch_resources, self.config.enable_circuit_breaker
                    )
                    successful = result.get('successful', 0)
                    failed = result.get('failed', 0)
                    errors = result.get('errors', [])
                    
                elif operation.operation_type == 'sync':
                    # Sync operations between NetBox and Kubernetes
                    result = await self._sync_resources(
                        fabric, batch_resources, self.config.enable_circuit_breaker
                    )
                    successful = result.get('successful', 0)
                    failed = result.get('failed', 0)
                    errors = result.get('errors', [])
                
                processing_time = time.time() - start_time
                throughput = len(batch_resources) / max(0.001, processing_time)
                
                return {
                    'batch_id': batch_id,
                    'processed': len(batch_resources),
                    'successful': successful,
                    'failed': failed,
                    'processing_time': processing_time,
                    'throughput': throughput,
                    'errors': errors[:5]  # Limit error details
                }
                
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Single batch processing failed for {batch_id}: {e}")
            
            return {
                'batch_id': batch_id,
                'processed': len(batch_resources),
                'successful': 0,
                'failed': len(batch_resources),
                'processing_time': processing_time,
                'throughput': 0.0,
                'error': str(e)
            }
    
    async def _apply_resources_to_kubernetes(self, fabric: HedgehogFabric, 
                                           resources: List[Any],
                                           use_circuit_breaker: bool = True) -> Dict[str, Any]:
        """Apply resources to Kubernetes with optional circuit breaker protection"""
        successful = 0
        failed = 0
        errors = []
        
        try:
            if use_circuit_breaker:
                # Use circuit breaker protection
                k8s_client = KubernetesClient(fabric)
                
                for resource in resources:
                    try:
                        result = await protected_kubernetes_call(
                            fabric.id, k8s_client.apply_crd, resource
                        )
                        if result.get('success', False):
                            successful += 1
                        else:
                            failed += 1
                            errors.append(result.get('error', 'Unknown error'))
                    except Exception as e:
                        failed += 1
                        errors.append(str(e))
            else:
                # Direct application without circuit breaker
                k8s_client = KubernetesClient(fabric)
                
                for resource in resources:
                    try:
                        result = await asyncio.to_thread(k8s_client.apply_crd, resource)
                        if result.get('success', False):
                            successful += 1
                        else:
                            failed += 1
                            errors.append(result.get('error', 'Unknown error'))
                    except Exception as e:
                        failed += 1
                        errors.append(str(e))
                        
        except Exception as e:
            logger.error(f"Batch apply to Kubernetes failed: {e}")
            failed = len(resources)
            errors.append(str(e))
        
        return {
            'successful': successful,
            'failed': failed,
            'errors': errors
        }
    
    async def _delete_resources_from_kubernetes(self, fabric: HedgehogFabric,
                                              resources: List[Any],
                                              use_circuit_breaker: bool = True) -> Dict[str, Any]:
        """Delete resources from Kubernetes with optional circuit breaker protection"""
        successful = 0
        failed = 0
        errors = []
        
        try:
            if use_circuit_breaker:
                k8s_client = KubernetesClient(fabric)
                
                for resource in resources:
                    try:
                        result = await protected_kubernetes_call(
                            fabric.id, k8s_client.delete_crd, resource
                        )
                        if result.get('success', False):
                            successful += 1
                        else:
                            failed += 1
                            errors.append(result.get('error', 'Unknown error'))
                    except Exception as e:
                        failed += 1
                        errors.append(str(e))
            else:
                k8s_client = KubernetesClient(fabric)
                
                for resource in resources:
                    try:
                        result = await asyncio.to_thread(k8s_client.delete_crd, resource)
                        if result.get('success', False):
                            successful += 1
                        else:
                            failed += 1
                            errors.append(result.get('error', 'Unknown error'))
                    except Exception as e:
                        failed += 1
                        errors.append(str(e))
                        
        except Exception as e:
            logger.error(f"Batch delete from Kubernetes failed: {e}")
            failed = len(resources)
            errors.append(str(e))
        
        return {
            'successful': successful,
            'failed': failed,
            'errors': errors
        }
    
    async def _sync_resources(self, fabric: HedgehogFabric, resources: List[Any],
                            use_circuit_breaker: bool = True) -> Dict[str, Any]:
        """Sync resources between NetBox and Kubernetes"""
        successful = 0
        failed = 0
        errors = []
        
        try:
            # For sync operations, we use the integration coordinator
            resource_types = list(set(type(r).__name__ for r in resources))
            
            sync_result = await self.integration_coordinator.sync_fabric_bidirectional(
                fabric.id, priority=EventPriority.NORMAL
            )
            
            if sync_result['success']:
                successful = len(resources)
            else:
                failed = len(resources)
                errors.append(sync_result.get('error', 'Sync failed'))
                
        except Exception as e:
            logger.error(f"Resource sync failed: {e}")
            failed = len(resources)
            errors.append(str(e))
        
        return {
            'successful': successful,
            'failed': failed,
            'errors': errors
        }
    
    async def _record_batch_metrics(self, operation: BatchOperation, 
                                   result: Dict[str, Any], duration: float):
        """Record batch processing metrics for analysis"""
        try:
            system_usage = await self.system_monitor.get_current_usage()
            
            metrics = BatchMetrics(
                batch_id=operation.operation_id,
                batch_size=len(operation.resources),
                processing_time=duration,
                throughput=result.get('throughput', 0.0),
                success_count=result.get('total_successful', 0),
                failure_count=result.get('total_failed', 0),
                memory_usage_mb=system_usage['memory_used_mb'],
                cpu_usage_percent=system_usage['cpu_percent']
            )
            
            with self._metrics_lock:
                self.metrics_history.append(metrics)
            
            # Cache metrics for external access
            cache.set(
                f"batch_metrics_{operation.operation_id}",
                metrics.to_dict(),
                timeout=3600
            )
            
        except Exception as e:
            logger.error(f"Failed to record batch metrics: {e}")
    
    async def _update_performance_optimization(self, result: Dict[str, Any]):
        """Update performance optimization based on results"""
        try:
            await self.performance_optimizer.analyze_performance(
                result.get('throughput', 0.0),
                result.get('total_successful', 0),
                result.get('total_failed', 0),
                self.current_batch_size
            )
        except Exception as e:
            logger.error(f"Performance optimization update failed: {e}")
    
    async def _update_batch_status(self, fabric: HedgehogFabric, result: Dict[str, Any]):
        """Update fabric status based on batch processing results"""
        try:
            status_request = StatusUpdateRequest(
                fabric_id=fabric.id,
                status_type=StatusType.FABRIC,
                new_state=StatusState.HEALTHY if result['success'] else StatusState.ERROR,
                message=f"Batch processing completed: {result.get('message', 'Unknown result')}",
                source="batch_processor",
                priority=EventPriority.NORMAL,
                metadata={
                    'total_processed': result.get('total_processed', 0),
                    'total_successful': result.get('total_successful', 0),
                    'total_failed': result.get('total_failed', 0),
                    'throughput': result.get('throughput', 0.0)
                }
            )
            
            await self.status_sync_service.update_status(status_request)
            
        except Exception as e:
            logger.error(f"Failed to update batch status: {e}")
    
    def _calculate_trend(self, values: List[float]) -> str:
        """Calculate trend direction from a list of values"""
        if len(values) < 3:
            return "insufficient_data"
        
        # Simple trend calculation using first and last thirds
        first_third = values[:len(values)//3]
        last_third = values[-len(values)//3:]
        
        if not first_third or not last_third:
            return "insufficient_data"
        
        first_avg = statistics.mean(first_third)
        last_avg = statistics.mean(last_third)
        
        if last_avg > first_avg * 1.1:
            return "improving"
        elif last_avg < first_avg * 0.9:
            return "declining"
        else:
            return "stable"

class PerformanceOptimizer:
    """
    Performance optimizer for batch processing
    """
    
    def __init__(self, config: BatchProcessingConfig):
        self.config = config
        self.optimization_history: deque = deque(maxlen=100)
        self._last_optimization = None
    
    async def optimize_batch_size(self, metrics_history: deque, 
                                target_throughput: Optional[float] = None) -> Dict[str, Any]:
        """Optimize batch size based on performance metrics"""
        if len(metrics_history) < 5:
            return {
                'optimized': False,
                'reason': 'Insufficient metrics for optimization',
                'current_batch_size': self.config.default_batch_size
            }
        
        # Analyze recent performance
        recent_metrics = list(metrics_history)[-20:]  # Last 20 batches
        
        # Calculate performance by batch size
        size_performance = defaultdict(list)
        for metric in recent_metrics:
            size_performance[metric.batch_size].append(metric.throughput)
        
        # Find optimal batch size
        best_size = self.config.default_batch_size
        best_throughput = 0.0
        
        for size, throughputs in size_performance.items():
            if len(throughputs) >= 2:  # Need at least 2 samples
                avg_throughput = statistics.mean(throughputs)
                if avg_throughput > best_throughput:
                    best_throughput = avg_throughput
                    best_size = size
        
        # Apply optimization constraints
        if target_throughput:
            # If we have a target throughput, adjust accordingly
            current_avg = statistics.mean(m.throughput for m in recent_metrics[-5:])
            if current_avg < target_throughput:
                # Increase batch size to improve throughput
                best_size = min(int(best_size * 1.2), self.config.max_batch_size)
        
        return {
            'optimized': True,
            'new_batch_size': best_size,
            'expected_throughput': best_throughput,
            'optimization_reason': 'Performance analysis',
            'metrics_analyzed': len(recent_metrics)
        }
    
    async def analyze_performance(self, throughput: float, successful: int, 
                                failed: int, batch_size: int):
        """Analyze performance and store optimization data"""
        analysis = {
            'timestamp': datetime.now(timezone.utc),
            'throughput': throughput,
            'success_rate': successful / max(1, successful + failed),
            'batch_size': batch_size,
            'efficiency_score': throughput * (successful / max(1, successful + failed))
        }
        
        self.optimization_history.append(analysis)
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get performance optimizer metrics"""
        if not self.optimization_history:
            return {'no_data': True}
        
        recent_analyses = list(self.optimization_history)[-10:]
        
        return {
            'total_analyses': len(self.optimization_history),
            'recent_avg_throughput': statistics.mean(a['throughput'] for a in recent_analyses),
            'recent_avg_success_rate': statistics.mean(a['success_rate'] for a in recent_analyses),
            'recent_avg_efficiency': statistics.mean(a['efficiency_score'] for a in recent_analyses),
            'last_analysis': recent_analyses[-1] if recent_analyses else None
        }

class SystemResourceMonitor:
    """
    System resource monitoring for batch processing
    """
    
    def __init__(self):
        self.process = psutil.Process()
    
    async def get_current_usage(self) -> Dict[str, Any]:
        """Get current system resource usage"""
        try:
            # System-wide metrics
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            
            # Process-specific metrics
            process_memory = self.process.memory_info()
            process_cpu = self.process.cpu_percent()
            
            return {
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'memory_used_mb': memory.used / 1024 / 1024,
                'memory_available_mb': memory.available / 1024 / 1024,
                'process_memory_mb': process_memory.rss / 1024 / 1024,
                'process_cpu_percent': process_cpu,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get system resource usage: {e}")
            return {
                'cpu_percent': 0.0,
                'memory_percent': 0.0,
                'memory_used_mb': 0.0,
                'memory_available_mb': 0.0,
                'process_memory_mb': 0.0,
                'process_cpu_percent': 0.0,
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }

# Global batch processor instance
_batch_processor = None

def get_batch_processor() -> BatchProcessor:
    """Get global BatchProcessor instance"""
    global _batch_processor
    if _batch_processor is None:
        _batch_processor = BatchProcessor()
    return _batch_processor