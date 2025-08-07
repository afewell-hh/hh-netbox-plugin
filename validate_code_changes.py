#!/usr/bin/env python3
"""
Validate GitOps Code Changes
Tests that our implementation changes are present in the code
"""

import os
import re

def validate_onboarding_service_changes():
    """Validate changes to GitOpsOnboardingService"""
    print("🧪 Validating GitOpsOnboardingService Changes...")
    
    file_path = "netbox_hedgehog/services/gitops_onboarding_service.py"
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Check for our new methods
        checks = [
            ("_ensure_directory_structure method", "def _ensure_directory_structure(self):"),
            ("_has_files_in_raw method", "def _has_files_in_raw(self):"),
            ("_execute_ingestion_with_validation method", "def _execute_ingestion_with_validation(self):"),
            ("Directory structure creation", "self._ensure_directory_structure()"),
            ("Enhanced ingestion call", "self._execute_ingestion_with_validation()"),
            ("Error handling for ingestion", "if not ingestion_result.get('success'):"),
            ("Exception raising on failure", "raise Exception(error_msg)")
        ]
        
        passed = 0
        for check_name, check_pattern in checks:
            if check_pattern in content:
                print(f"✅ {check_name}: Found")
                passed += 1
            else:
                print(f"❌ {check_name}: Missing")
        
        print(f"📊 GitOpsOnboardingService: {passed}/{len(checks)} checks passed")
        return passed == len(checks)
        
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        return False

def validate_signal_handler_changes():
    """Validate changes to signal handlers"""
    print("\n🧪 Validating Signal Handler Changes...")
    
    file_path = "netbox_hedgehog/signals.py"
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Check for our changes
        checks = [
            ("Removed transaction.on_commit", ("transaction.on_commit", False)),
            ("Added transaction.atomic", "with transaction.atomic():"),
            ("Added error propagation", "raise  # Propagate all exceptions"),
            ("Enhanced error handling", "raise Exception(f\"GitOpsOnboardingService not available: {e}\")"),
            ("Service import validation", "from .services.gitops_onboarding_service import GitOpsOnboardingService"),
            ("Result validation", "if not result.get('success'):"),
            ("Fabric status update on failure", "instance.sync_status = 'initialization_failed'")
        ]
        
        passed = 0
        for check_name, check_pattern in checks:
            if isinstance(check_pattern, tuple):
                # Boolean check (e.g., for "not in")
                pattern, should_exist = check_pattern
                exists = pattern in content
                if (should_exist and exists) or (not should_exist and not exists):
                    print(f"✅ {check_name}: Confirmed")
                    passed += 1
                else:
                    print(f"❌ {check_name}: Failed")
            else:
                # String pattern check
                if check_pattern in content:
                    print(f"✅ {check_name}: Found")
                    passed += 1
                else:
                    print(f"❌ {check_name}: Missing")
        
        print(f"📊 Signal Handler: {passed}/{len(checks)} checks passed")
        return passed == len(checks)
        
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        return False

def validate_directory_structure_logic():
    """Validate the directory structure creation logic"""
    print("\n🧪 Validating Directory Structure Logic...")
    
    file_path = "netbox_hedgehog/services/gitops_onboarding_service.py"
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Extract the _ensure_directory_structure method
        method_start = content.find("def _ensure_directory_structure(self):")
        if method_start == -1:
            print("❌ _ensure_directory_structure method not found")
            return False
        
        method_end = content.find("\n    def ", method_start + 1)
        if method_end == -1:
            method_end = content.find("\n\nclass ", method_start + 1)
        
        method_content = content[method_start:method_end]
        
        # Check directory creation logic
        checks = [
            ("Creates raw directory", "self.raw_path"),
            ("Creates managed directory", "self.managed_path"),
            ("Creates unmanaged directory", "self.unmanaged_path"),
            ("Creates .hnp directory", "'.hnp'"),
            ("Creates CRD subdirectories", "'vpcs', 'externals', 'servers'"),
            ("Uses makedirs with mode", "os.makedirs(dir_path, mode=0o755, exist_ok=True)"),
            ("Tests write permissions", "test_file"),
            ("Handles permissions errors", "except (OSError, PermissionError)"),
            ("Has logging", "logger.info")
        ]
        
        passed = 0
        for check_name, check_pattern in checks:
            if check_pattern in method_content:
                print(f"✅ {check_name}: Found")
                passed += 1
            else:
                print(f"❌ {check_name}: Missing")
        
        print(f"📊 Directory Structure Logic: {passed}/{len(checks)} checks passed")
        return passed == len(checks)
        
    except Exception as e:
        print(f"❌ Error validating directory logic: {e}")
        return False

def validate_ingestion_validation_logic():
    """Validate the ingestion validation logic"""
    print("\n🧪 Validating Ingestion Validation Logic...")
    
    file_path = "netbox_hedgehog/services/gitops_onboarding_service.py"
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Extract the _execute_ingestion_with_validation method
        method_start = content.find("def _execute_ingestion_with_validation(self):")
        if method_start == -1:
            print("❌ _execute_ingestion_with_validation method not found")
            return False
        
        method_end = content.find("\n    def ", method_start + 1)
        if method_end == -1:
            method_end = content.find("\n\nclass ", method_start + 1)
        
        method_content = content[method_start:method_end]
        
        # Check ingestion validation logic
        checks = [
            ("Service import validation", "from .gitops_ingestion_service import GitOpsIngestionService"),
            ("Pre-ingestion file check", "raw_files = list(Path(self.raw_path).glob"),
            ("Handles no files case", "No files to process"),
            ("Executes ingestion service", "ingestion_service.process_raw_directory()"),
            ("Post-ingestion validation", "managed_files = list(Path(self.managed_path).glob"),
            ("Validates file creation", "if len(expected_files) > 0 and len(managed_files) == 0:"),
            ("Returns structured results", "'success': False"),
            ("Comprehensive error handling", "except Exception as e:")
        ]
        
        passed = 0
        for check_name, check_pattern in checks:
            if check_pattern in method_content:
                print(f"✅ {check_name}: Found")
                passed += 1
            else:
                print(f"❌ {check_name}: Missing")
        
        print(f"📊 Ingestion Validation Logic: {passed}/{len(checks)} checks passed")
        return passed == len(checks)
        
    except Exception as e:
        print(f"❌ Error validating ingestion logic: {e}")
        return False

def main():
    """Run all code validation tests"""
    print("🚀 GitOps Code Changes Validation")
    print("=" * 60)
    
    tests = [
        validate_onboarding_service_changes,
        validate_signal_handler_changes,
        validate_directory_structure_logic,
        validate_ingestion_validation_logic
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
    
    print("\n" + "=" * 60)
    print(f"📊 RESULTS: {passed}/{total} validation tests passed ({100*passed/total:.1f}%)")
    
    if passed == total:
        print("🎉 ALL CODE CHANGES VALIDATED!")
        print("✅ Implementation appears complete and correct")
    else:
        print("❌ SOME VALIDATIONS FAILED!")
        print("🔧 Code changes need attention")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)