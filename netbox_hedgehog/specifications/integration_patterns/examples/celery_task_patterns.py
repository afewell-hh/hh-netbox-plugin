#!/usr/bin/env python3
"""
Celery Task Integration Patterns
Demonstrates best practices for Celery task implementation.
"""

import time
import logging
from typing import Dict, Any, Optional
from celery import shared_task, group, chain
from celery.exceptions import Retry
from django.db import transaction

logger = logging.getLogger(__name__)

# Basic task with retry logic
@shared_task(bind=True, autoretry_for=(Exception,), 
             retry_kwargs={'max_retries': 3, 'countdown': 60})
def basic_sync_task(self, resource_id: int) -> Dict[str, Any]:
    """Basic sync task with retry logic"""
    
    start_time = time.time()
    
    try:
        logger.info(f"Starting sync for resource {resource_id}")
        
        # Simulate work
        time.sleep(2)
        
        # Your sync logic here
        # ...
        
        duration = time.time() - start_time
        logger.info(f"Successfully synced resource {resource_id} in {duration:.2f}s")
        
        return {
            'status': 'success',
            'resource_id': resource_id,
            'duration': duration
        }
        
    except Exception as e:
        logger.error(f"Sync failed for resource {resource_id}: {e}")
        
        # Update error status in database
        # ...
        
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=min(2 ** self.request.retries * 60, 3600))

# Task with database transaction
@shared_task(bind=True)
def transactional_task(self, data: Dict[str, Any]) -> Dict[str, Any]:
    """Task with database transaction handling"""
    
    try:
        with transaction.atomic():
            # Database operations here
            # All operations will be rolled back if any fail
            
            # Example: Update multiple records
            # Model.objects.filter(id__in=ids).update(status='processed')
            
            return {
                'status': 'success',
                'processed_count': len(data.get('items', []))
            }
            
    except Exception as e:
        logger.error(f"Transactional task failed: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }

# Batch processing task
@shared_task
def batch_processing_task(items: list, batch_size: int = 100) -> Dict[str, Any]:
    """Process items in batches"""
    
    results = {
        'total_items': len(items),
        'processed': 0,
        'failed': 0,
        'errors': []
    }
    
    # Process in batches
    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        
        try:
            # Process batch
            for item in batch:
                # Process individual item
                process_item(item)
                results['processed'] += 1
                
        except Exception as e:
            logger.error(f"Batch processing failed: {e}")
            results['failed'] += len(batch) - (results['processed'] % batch_size)
            results['errors'].append(str(e))
    
    return results

def process_item(item):
    """Process individual item"""
    # Your item processing logic here
    pass

# Chained tasks example
@shared_task
def step1_task(data: Dict[str, Any]) -> Dict[str, Any]:
    """First step in a chain"""
    logger.info("Executing step 1")
    
    # Process data
    processed_data = data.copy()
    processed_data['step1_completed'] = True
    processed_data['step1_timestamp'] = time.time()
    
    return processed_data

@shared_task
def step2_task(data: Dict[str, Any]) -> Dict[str, Any]:
    """Second step in a chain"""
    logger.info("Executing step 2")
    
    # Process data from step 1
    processed_data = data.copy()
    processed_data['step2_completed'] = True
    processed_data['step2_timestamp'] = time.time()
    
    return processed_data

@shared_task
def step3_task(data: Dict[str, Any]) -> Dict[str, Any]:
    """Final step in a chain"""
    logger.info("Executing step 3")
    
    # Final processing
    processed_data = data.copy()
    processed_data['step3_completed'] = True
    processed_data['step3_timestamp'] = time.time()
    processed_data['workflow_completed'] = True
    
    return processed_data

# Group tasks example
@shared_task
def parallel_sync_task(resource_id: int) -> Dict[str, Any]:
    """Task designed to run in parallel with others"""
    
    logger.info(f"Parallel sync for resource {resource_id}")
    
    # Simulate work
    time.sleep(1)
    
    return {
        'resource_id': resource_id,
        'status': 'completed',
        'timestamp': time.time()
    }

# Callback tasks
@shared_task
def success_callback_task(result: Dict[str, Any]):
    """Called when a task succeeds"""
    logger.info(f"Task succeeded: {result}")
    
    # Send notification, update UI, etc.
    # ...

@shared_task
def failure_callback_task(task_id: str, error: str, traceback: str):
    """Called when a task fails"""
    logger.error(f"Task {task_id} failed: {error}")
    
    # Handle failure: send alert, clean up, etc.
    # ...

# Workflow orchestration examples
def create_sync_workflow(resource_ids: list) -> Any:
    """Create a workflow for syncing multiple resources"""
    
    # Option 1: Sequential workflow using chain
    sequential_workflow = chain(
        step1_task.s({'resource_ids': resource_ids}),
        step2_task.s(),
        step3_task.s()
    )
    
    return sequential_workflow

def create_parallel_workflow(resource_ids: list) -> Any:
    """Create a parallel workflow for syncing resources"""
    
    # Option 2: Parallel workflow using group
    parallel_jobs = group([
        parallel_sync_task.s(resource_id) 
        for resource_id in resource_ids
    ])
    
    return parallel_jobs

def create_complex_workflow(resource_ids: list) -> Any:
    """Create a complex workflow combining parallel and sequential tasks"""
    
    # Step 1: Parallel processing
    parallel_step = group([
        parallel_sync_task.s(resource_id) 
        for resource_id in resource_ids
    ])
    
    # Step 2: Sequential cleanup after parallel processing
    cleanup_step = chain(
        step2_task.s(),
        step3_task.s()
    )
    
    # Combine: parallel first, then sequential
    complex_workflow = chain(parallel_step, cleanup_step)
    
    return complex_workflow

# Task monitoring and health check
@shared_task
def health_check_task() -> Dict[str, Any]:
    """Health check task for monitoring"""
    
    try:
        # Check database connectivity
        from django.db import connection
        cursor = connection.cursor()
        cursor.execute("SELECT 1")
        
        # Check external services
        # ... your health checks here ...
        
        return {
            'status': 'healthy',
            'timestamp': time.time(),
            'checks': {
                'database': 'ok',
                'external_services': 'ok'
            }
        }
        
    except Exception as e:
        return {
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': time.time()
        }

# Example usage functions
def execute_single_sync(resource_id: int):
    """Execute single sync task"""
    result = basic_sync_task.delay(resource_id)
    return result.id

def execute_batch_sync(resource_ids: list):
    """Execute batch sync using group"""
    jobs = group([
        basic_sync_task.s(resource_id) 
        for resource_id in resource_ids
    ])
    
    result = jobs.apply_async()
    return result.id

def execute_workflow(resource_ids: list, workflow_type: str = 'parallel'):
    """Execute different types of workflows"""
    
    if workflow_type == 'sequential':
        workflow = create_sync_workflow(resource_ids)
    elif workflow_type == 'parallel':
        workflow = create_parallel_workflow(resource_ids)
    elif workflow_type == 'complex':
        workflow = create_complex_workflow(resource_ids)
    else:
        raise ValueError(f"Unknown workflow type: {workflow_type}")
    
    result = workflow.apply_async()
    return result.id

# Example monitoring function
def monitor_task_progress(task_id: str) -> Dict[str, Any]:
    """Monitor task progress"""
    from celery.result import AsyncResult
    
    result = AsyncResult(task_id)
    
    return {
        'task_id': task_id,
        'status': result.status,
        'result': result.result if result.ready() else None,
        'traceback': result.traceback if result.failed() else None,
        'progress': getattr(result, 'info', {}) if result.status == 'PROGRESS' else None
    }

if __name__ == '__main__':
    print("Celery Task Pattern Examples")
    print("===========================")
    print("")
    print("Available task patterns:")
    print("- basic_sync_task: Simple task with retry logic")
    print("- transactional_task: Task with database transactions")
    print("- batch_processing_task: Batch processing with error handling")
    print("- Workflow examples: Sequential, parallel, and complex workflows")
    print("- Health check task: System monitoring")
    print("")
    print("Example usage:")
    print("task_id = execute_single_sync(123)")
    print("status = monitor_task_progress(task_id)")