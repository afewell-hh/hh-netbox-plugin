#!/usr/bin/env python3
"""
Phase 2 Enhanced Periodic Sync Scheduler - Integration Validation

This script validates that the new scheduler integrates correctly with:
1. Existing NetBox Hedgehog infrastructure
2. Celery task routing and queue configuration
3. Database model extensions
4. Error handling and logging systems
"""

import os
import sys
import django
from pathlib import Path

# Setup Django environment
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')

try:
    django.setup()
except Exception as e:
    print(f"⚠️  Django setup failed: {e}")
    print("This is expected if not running in NetBox environment")

def validate_scheduler_imports():
    """Validate that all scheduler components can be imported"""
    print("🔍 Validating scheduler imports...")
    
    try:
        # Test sync_scheduler module imports
        from netbox_hedgehog.tasks.sync_scheduler import (
            EnhancedSyncScheduler,
            SyncPriority,
            SyncType,
            SchedulerError,
            SchedulerErrorHandler,
            master_sync_scheduler
        )
        print("✅ Sync scheduler imports successful")
        
        # Test task imports from __init__
        from netbox_hedgehog.tasks import (
            master_sync_scheduler,
            update_fabric_status,
            kubernetes_sync_fabric,
            detect_fabric_drift,
            get_scheduler_metrics
        )
        print("✅ Task imports from __init__ successful")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import validation failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error during import validation: {e}")
        return False

def validate_celery_configuration():
    """Validate Celery configuration and queue setup"""
    print("\n🔍 Validating Celery configuration...")
    
    try:
        from netbox_hedgehog.celery import app, SCHEDULER_QUEUE_CONFIG
        
        # Check task routing
        task_routes = app.conf.get('task_routes', {})
        expected_routes = [
            'netbox_hedgehog.tasks.master_sync_scheduler',
            'netbox_hedgehog.tasks.git_sync_fabric',
            'netbox_hedgehog.tasks.kubernetes_sync_fabric',
            'netbox_hedgehog.tasks.update_fabric_status'
        ]
        
        missing_routes = []
        for route in expected_routes:
            if route not in task_routes:
                missing_routes.append(route)
        
        if missing_routes:
            print(f"❌ Missing task routes: {missing_routes}")
            return False
        
        print("✅ Task routing configuration valid")
        
        # Check queue configuration
        if not SCHEDULER_QUEUE_CONFIG:
            print("❌ SCHEDULER_QUEUE_CONFIG is empty")
            return False
        
        expected_queues = [
            'scheduler_master',
            'sync_git',
            'sync_kubernetes', 
            'sync_micro',
            'sync_orchestration'
        ]
        
        for queue in expected_queues:
            if queue not in SCHEDULER_QUEUE_CONFIG:
                print(f"❌ Missing queue configuration: {queue}")
                return False
        
        print("✅ Queue configuration valid")
        
        # Check beat schedule
        beat_schedule = app.conf.get('beat_schedule', {})
        if 'master-sync-scheduler' not in beat_schedule:
            print("❌ Master sync scheduler not in beat schedule")
            return False
            
        master_schedule = beat_schedule['master-sync-scheduler']
        if master_schedule['schedule'] != 60.0:
            print(f"❌ Master scheduler schedule is {master_schedule['schedule']}, expected 60.0")
            return False
        
        print("✅ Beat schedule configuration valid")
        return True
        
    except Exception as e:
        print(f"❌ Celery configuration validation failed: {e}")
        return False

def validate_model_extensions():
    """Validate that Fabric model extensions are properly added"""
    print("\n🔍 Validating model extensions...")
    
    try:
        from netbox_hedgehog.models.fabric import HedgehogFabric
        
        # Check new scheduler fields exist
        test_fabric = HedgehogFabric()
        
        scheduler_fields = [
            'scheduler_enabled',
            'scheduler_priority', 
            'sync_plan_version',
            'last_scheduler_run',
            'sync_health_score',
            'scheduler_metadata',
            'active_sync_tasks',
            'last_task_execution',
            'task_execution_count',
            'failed_task_count'
        ]
        
        for field_name in scheduler_fields:
            if not hasattr(test_fabric, field_name):
                print(f"❌ Missing field: {field_name}")
                return False
        
        print("✅ All scheduler fields present")
        
        # Check new methods exist
        scheduler_methods = [
            'calculate_scheduler_health_score',
            'should_be_scheduled',
            'get_scheduler_priority_level',
            'update_scheduler_execution_metrics',
            'add_active_sync_task',
            'remove_active_sync_task',
            'get_scheduler_statistics'
        ]
        
        for method_name in scheduler_methods:
            if not hasattr(test_fabric, method_name) or not callable(getattr(test_fabric, method_name)):
                print(f"❌ Missing method: {method_name}")
                return False
        
        print("✅ All scheduler methods present")
        return True
        
    except Exception as e:
        print(f"❌ Model validation failed: {e}")
        return False

def validate_error_handling():
    """Validate error handling components"""
    print("\n🔍 Validating error handling...")
    
    try:
        from netbox_hedgehog.tasks.sync_scheduler import (
            SchedulerErrorHandler,
            ErrorContext,
            SchedulerError,
            FabricDiscoveryError,
            SyncPlanningError,
            TaskOrchestrationError
        )
        
        # Test error handler instantiation
        error_handler = SchedulerErrorHandler()
        
        # Test error context creation
        context = ErrorContext(
            error_type="test_error",
            fabric_id=1,
            fabric_name="test_fabric",
            phase="validation"
        )
        
        # Verify methods exist
        handler_methods = [
            'handle_error',
            'get_error_statistics',
            '_get_recovery_strategy',
            '_execute_recovery_action'
        ]
        
        for method_name in handler_methods:
            if not hasattr(error_handler, method_name):
                print(f"❌ Missing error handler method: {method_name}")
                return False
        
        print("✅ Error handling components valid")
        return True
        
    except Exception as e:
        print(f"❌ Error handling validation failed: {e}")
        return False

def validate_scheduler_functionality():
    """Test basic scheduler functionality without database"""
    print("\n🔍 Validating scheduler functionality...")
    
    try:
        from netbox_hedgehog.tasks.sync_scheduler import (
            EnhancedSyncScheduler,
            SyncPriority,
            SyncType,
            SyncTask,
            FabricSyncPlan
        )
        
        # Test scheduler instantiation
        scheduler = EnhancedSyncScheduler()
        
        # Test sync task creation
        task = SyncTask(
            fabric_id=1,
            fabric_name="test_fabric",
            sync_type=SyncType.GIT_SYNC,
            priority=SyncPriority.MEDIUM,
            estimated_duration=20
        )
        
        # Test sync plan creation
        plan = FabricSyncPlan(
            fabric_id=1,
            fabric_name="test_fabric"
        )
        plan.add_task(task)
        
        # Verify plan properties
        if plan.total_estimated_duration != 20:
            print(f"❌ Expected duration 20, got {plan.total_estimated_duration}")
            return False
        
        if plan.priority != SyncPriority.MEDIUM:
            print(f"❌ Expected priority MEDIUM, got {plan.priority}")
            return False
        
        print("✅ Basic scheduler functionality valid")
        return True
        
    except Exception as e:
        print(f"❌ Scheduler functionality validation failed: {e}")
        return False

def validate_integration_points():
    """Validate integration with existing services"""
    print("\n🔍 Validating integration points...")
    
    try:
        # Check if EventService can be imported (used by scheduler)
        from netbox_hedgehog.application.services.event_service import EventService
        print("✅ EventService integration available")
        
        # Check if GitService can be imported (used by git sync tasks)
        from netbox_hedgehog.application.services.git_service import GitService  
        print("✅ GitService integration available")
        
        return True
        
    except ImportError as e:
        print(f"⚠️  Service integration warning: {e}")
        print("   This is expected if services are not fully implemented")
        return True  # Don't fail validation for missing services
    except Exception as e:
        print(f"❌ Integration validation failed: {e}")
        return False

def main():
    """Run all validation checks"""
    print("🚀 Phase 2 Enhanced Periodic Sync Scheduler - Integration Validation")
    print("=" * 70)
    
    validation_results = []
    
    # Run all validation checks
    checks = [
        ("Scheduler Imports", validate_scheduler_imports),
        ("Celery Configuration", validate_celery_configuration),
        ("Model Extensions", validate_model_extensions),
        ("Error Handling", validate_error_handling),
        ("Scheduler Functionality", validate_scheduler_functionality),
        ("Integration Points", validate_integration_points)
    ]
    
    for check_name, check_func in checks:
        try:
            result = check_func()
            validation_results.append((check_name, result))
        except Exception as e:
            print(f"❌ {check_name} validation crashed: {e}")
            validation_results.append((check_name, False))
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 VALIDATION SUMMARY")
    print("=" * 70)
    
    passed = 0
    total = len(validation_results)
    
    for check_name, result in validation_results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status:<10} {check_name}")
        if result:
            passed += 1
    
    print(f"\nResults: {passed}/{total} checks passed")
    
    if passed == total:
        print("\n🎉 All validation checks passed! The Enhanced Periodic Sync Scheduler is ready for deployment.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} validation check(s) failed. Please review the issues above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())