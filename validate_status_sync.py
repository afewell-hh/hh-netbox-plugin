#!/usr/bin/env python3
"""
Validation script for Unified Status Synchronization Framework
Checks if all modules can be imported and basic functionality works
"""

import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def validate_imports():
    """Validate that all new modules can be imported"""
    try:
        print("✓ Validating imports...")
        
        # Test status reconciliation imports
        from netbox_hedgehog.tasks.status_reconciliation import (
            StatusReconciliationService, StatusSnapshot, StatusType, StatusState,
            StatusConflict, ConflictType, ReconciliationResult
        )
        print("  ✓ Status reconciliation module")
        
        # Test status sync service imports
        from netbox_hedgehog.services.status_sync_service import (
            StatusSyncService, StatusUpdateRequest, StatusSyncConfig,
            get_status_sync_service
        )
        print("  ✓ Status sync service module")
        
        # Test status sync tasks imports
        from netbox_hedgehog.tasks.status_sync_tasks import (
            propagate_status_update, validate_fabric_status_consistency,
            batch_propagate_status_updates, create_status_update_dict
        )
        print("  ✓ Status sync tasks module")
        
        print("✓ All imports successful!")
        return True
        
    except Exception as e:
        print(f"✗ Import validation failed: {e}")
        return False

def validate_enum_mappings():
    """Validate enum type mappings work correctly"""
    try:
        print("✓ Validating enum mappings...")
        
        from netbox_hedgehog.tasks.status_reconciliation import StatusType, StatusState
        from netbox_hedgehog.services.status_sync_service import StatusSyncService
        
        service = StatusSyncService()
        
        # Test status state mappings
        sync_status = service._map_state_to_sync_status(StatusState.HEALTHY)
        assert sync_status == 'synced', f"Expected 'synced', got '{sync_status}'"
        
        connection_status = service._map_state_to_connection_status(StatusState.ERROR)
        assert connection_status == 'error', f"Expected 'error', got '{connection_status}'"
        
        print("  ✓ Status state mappings")
        
        print("✓ Enum mappings validated!")
        return True
        
    except Exception as e:
        print(f"✗ Enum mapping validation failed: {e}")
        return False

def validate_data_structures():
    """Validate data structure creation and serialization"""
    try:
        print("✓ Validating data structures...")
        
        from netbox_hedgehog.tasks.status_reconciliation import StatusSnapshot, StatusType, StatusState
        from netbox_hedgehog.services.status_sync_service import StatusUpdateRequest
        from netbox_hedgehog.domain.interfaces.event_service_interface import EventPriority
        from datetime import datetime, timezone
        
        # Test StatusSnapshot creation
        snapshot = StatusSnapshot(
            status_type=StatusType.GIT_SYNC,
            fabric_id=1,
            state=StatusState.HEALTHY,
            timestamp=datetime.now(timezone.utc),
            message="Test snapshot"
        )
        assert snapshot.fabric_id == 1
        assert not snapshot.is_critical  # Healthy state should not be critical
        
        print("  ✓ StatusSnapshot creation")
        
        # Test StatusUpdateRequest creation
        request = StatusUpdateRequest(
            fabric_id=1,
            status_type=StatusType.KUBERNETES,
            new_state=StatusState.SYNCING,
            message="Test update request",
            priority=EventPriority.NORMAL
        )
        assert request.fabric_id == 1
        assert request.cache_key == "status_update_1_kubernetes"
        
        print("  ✓ StatusUpdateRequest creation")
        
        print("✓ Data structures validated!")
        return True
        
    except Exception as e:
        print(f"✗ Data structure validation failed: {e}")
        return False

def validate_service_creation():
    """Validate that services can be created without errors"""
    try:
        print("✓ Validating service creation...")
        
        from netbox_hedgehog.tasks.status_reconciliation import StatusReconciliationService
        from netbox_hedgehog.services.status_sync_service import StatusSyncService, StatusSyncConfig
        
        # Test reconciliation service creation
        reconciliation_service = StatusReconciliationService()
        assert reconciliation_service is not None
        assert hasattr(reconciliation_service, 'active_conflicts')
        
        print("  ✓ StatusReconciliationService creation")
        
        # Test status sync service creation
        config = StatusSyncConfig(
            max_propagation_delay=3.0,
            batch_size=25
        )
        sync_service = StatusSyncService(config)
        assert sync_service is not None
        assert sync_service.config.max_propagation_delay == 3.0
        
        print("  ✓ StatusSyncService creation")
        
        # Test global service getter
        from netbox_hedgehog.services.status_sync_service import get_status_sync_service
        global_service = get_status_sync_service()
        assert global_service is not None
        
        print("  ✓ Global service getter")
        
        print("✓ Service creation validated!")
        return True
        
    except Exception as e:
        print(f"✗ Service creation validation failed: {e}")
        return False

def main():
    """Main validation function"""
    print("=== Unified Status Synchronization Framework Validation ===")
    print()
    
    validations = [
        validate_imports,
        validate_enum_mappings,
        validate_data_structures,
        validate_service_creation
    ]
    
    passed = 0
    total = len(validations)
    
    for validation in validations:
        try:
            if validation():
                passed += 1
            print()
        except Exception as e:
            print(f"✗ Validation failed with exception: {e}")
            print()
    
    print("=== Validation Summary ===")
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 All validations passed! Status synchronization framework is ready.")
        return 0
    else:
        print("❌ Some validations failed. Please check the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())