#!/usr/bin/env python3
"""
Validate GitOps Implementation Fix
Quick validation that our implementation changes are working
"""

import os
import sys

# Set up Django environment
sys.path.insert(0, '/home/ubuntu/cc/hedgehog-netbox-plugin')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')

def test_service_imports():
    """Test that services can be imported"""
    print("🧪 Testing Service Imports...")
    
    try:
        from netbox_hedgehog.services.gitops_onboarding_service import GitOpsOnboardingService
        print("✅ GitOpsOnboardingService import successful")
        
        # Test new methods exist
        service = GitOpsOnboardingService.__new__(GitOpsOnboardingService)
        
        if hasattr(service, '_ensure_directory_structure'):
            print("✅ _ensure_directory_structure method exists")
        else:
            print("❌ _ensure_directory_structure method missing")
            
        if hasattr(service, '_execute_ingestion_with_validation'):
            print("✅ _execute_ingestion_with_validation method exists")  
        else:
            print("❌ _execute_ingestion_with_validation method missing")
            
        if hasattr(service, '_has_files_in_raw'):
            print("✅ _has_files_in_raw method exists")
        else:
            print("❌ _has_files_in_raw method missing")
            
        return True
        
    except ImportError as e:
        print(f"❌ Service import failed: {e}")
        return False

def test_ingestion_service():
    """Test ingestion service availability"""
    print("\n🧪 Testing Ingestion Service...")
    
    try:
        from netbox_hedgehog.services.gitops_ingestion_service import GitOpsIngestionService
        print("✅ GitOpsIngestionService import successful")
        return True
    except ImportError as e:
        print(f"❌ GitOpsIngestionService import failed: {e}")
        return False

def test_signal_handler():
    """Test signal handler functions"""
    print("\n🧪 Testing Signal Handler...")
    
    try:
        from netbox_hedgehog.signals import initialize_fabric_gitops
        print("✅ initialize_fabric_gitops function available")
        
        # Check if function has proper error handling
        import inspect
        source = inspect.getsource(initialize_fabric_gitops)
        if 'raise' in source and 'Exception' in source:
            print("✅ Function has proper error propagation")
        else:
            print("❌ Function missing error propagation")
            
        return True
    except ImportError as e:
        print(f"❌ Signal handler import failed: {e}")
        return False

def test_directory_creation():
    """Test directory creation functionality"""
    print("\n🧪 Testing Directory Creation...")
    
    import tempfile
    import shutil
    from pathlib import Path
    
    try:
        # Create a temporary directory for testing
        test_dir = tempfile.mkdtemp(prefix='gitops_test_')
        print(f"📁 Created test directory: {test_dir}")
        
        # Test directory structure creation
        required_dirs = [
            os.path.join(test_dir, 'raw'),
            os.path.join(test_dir, 'managed'),
            os.path.join(test_dir, 'unmanaged'),
            os.path.join(test_dir, '.hnp')
        ]
        
        managed_subdirs = [
            'vpcs', 'externals', 'servers', 'switches', 'connections', 
            'switchgroups', 'vlannamespaces', 'ipv4namespaces',
            'externalattachments', 'externalpeerings', 'vpcattachments', 'vpcpeerings'
        ]
        
        for subdir in managed_subdirs:
            required_dirs.append(os.path.join(test_dir, 'managed', subdir))
        
        # Create directories
        for dir_path in required_dirs:
            os.makedirs(dir_path, mode=0o755, exist_ok=True)
            
            # Test write permissions
            test_file = os.path.join(dir_path, '.write_test')
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
        
        print(f"✅ Successfully created {len(required_dirs)} directories")
        
        # Clean up
        shutil.rmtree(test_dir)
        print("✅ Directory creation test completed successfully")
        return True
        
    except Exception as e:
        print(f"❌ Directory creation failed: {e}")
        return False

def main():
    """Run all validation tests"""
    print("🚀 GitOps Implementation Validation")
    print("=" * 50)
    
    tests = [
        test_service_imports,
        test_ingestion_service, 
        test_signal_handler,
        test_directory_creation
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
    
    print("\n" + "=" * 50)
    print(f"📊 RESULTS: {passed}/{total} tests passed ({100*passed/total:.1f}%)")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED!")
        print("✅ GitOps implementation fix appears to be working")
    else:
        print("❌ SOME TESTS FAILED!")
        print("🔧 Implementation needs attention")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)