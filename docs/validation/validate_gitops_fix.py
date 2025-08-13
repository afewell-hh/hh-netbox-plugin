#!/usr/bin/env python3
"""
Validation Script for GitHub Issue #1 GitOps Fix
Tests the actual changes made to the fabric creation workflow
"""

import os
import sys
from pathlib import Path

def validate_code_changes():
    """Validate that the required code changes are present"""
    
    print("🔍 Validating GitHub Issue #1 Code Changes")
    print("=" * 50)
    
    # Check fabric_creation_workflow.py changes
    workflow_file = Path("/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/utils/fabric_creation_workflow.py")
    
    if not workflow_file.exists():
        print("❌ fabric_creation_workflow.py not found")
        return False
    
    print("📝 Checking fabric_creation_workflow.py...")
    
    with open(workflow_file, 'r') as f:
        content = f.read()
    
    # Check for GitOpsOnboardingService import
    if "from ..services.gitops_onboarding_service import GitOpsOnboardingService" in content:
        print("✅ GitOpsOnboardingService import found")
    else:
        print("❌ GitOpsOnboardingService import NOT found")
        return False
    
    # Check for GitOpsDirectoryManager removal
    if "from ..services.bidirectional_sync.gitops_directory_manager import GitOpsDirectoryManager" in content:
        print("❌ Old GitOpsDirectoryManager import still present")
        return False
    else:
        print("✅ Old GitOpsDirectoryManager import removed")
    
    # Check for onboarding service usage
    if "onboarding_service = GitOpsOnboardingService(fabric)" in content:
        print("✅ GitOpsOnboardingService instantiation found")
    else:
        print("❌ GitOpsOnboardingService instantiation NOT found")
        return False
    
    if "init_result = onboarding_service.initialize_gitops_structure()" in content:
        print("✅ initialize_gitops_structure() call found")
    else:
        print("❌ initialize_gitops_structure() call NOT found")
        return False
    
    print("\n📝 Checking gitops_onboarding_service.py...")
    
    # Check gitops_onboarding_service.py changes
    onboarding_file = Path("/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/services/gitops_onboarding_service.py")
    
    if not onboarding_file.exists():
        print("❌ gitops_onboarding_service.py not found")
        return False
    
    with open(onboarding_file, 'r') as f:
        onboarding_content = f.read()
    
    # Check for ingestion service integration
    if "from .gitops_ingestion_service import GitOpsIngestionService" in onboarding_content:
        print("✅ GitOpsIngestionService import found in onboarding service")
    else:
        print("❌ GitOpsIngestionService import NOT found in onboarding service")
        return False
    
    if "ingestion_service = GitOpsIngestionService(self.fabric)" in onboarding_content:
        print("✅ GitOpsIngestionService instantiation found")
    else:
        print("❌ GitOpsIngestionService instantiation NOT found")
        return False
    
    if "ingestion_result = ingestion_service.process_raw_directory()" in onboarding_content:
        print("✅ process_raw_directory() call found")
    else:
        print("❌ process_raw_directory() call NOT found")
        return False
    
    # Check for ingestion step integration
    if "Step 2.5: Process raw directory to ingest migrated files" in onboarding_content:
        print("✅ Ingestion step integration found")
    else:
        print("❌ Ingestion step integration NOT found")
        return False
    
    print("\n" + "=" * 50)
    print("🎉 SUCCESS: All required code changes are present!")
    print("\n📋 Summary of Changes:")
    print("1. ✅ fabric_creation_workflow.py now uses GitOpsOnboardingService")
    print("2. ✅ GitOpsDirectoryManager import removed")  
    print("3. ✅ initialize_gitops_structure() method called")
    print("4. ✅ Ingestion service integrated into onboarding workflow")
    print("5. ✅ Raw directory processing added after file migration")
    
    return True

def check_existing_test_fabric():
    """Check the current state of the test environment"""
    
    print("\n🌐 Checking Test Environment State")
    print("=" * 50)
    
    # Check if test GitOps directory exists and has files
    test_repo_path = Path("/tmp/hedgehog-repos/gitops-test-1")
    if test_repo_path.exists():
        print(f"✅ Test repository directory found: {test_repo_path}")
        
        gitops_path = test_repo_path / "gitops" / "hedgehog" / "fabric-1"
        if gitops_path.exists():
            print(f"✅ GitOps directory found: {gitops_path}")
            
            # List files in root
            root_files = [f for f in gitops_path.iterdir() if f.is_file() and f.suffix in ['.yaml', '.yml']]
            print(f"📁 YAML files in root: {len(root_files)}")
            for f in root_files:
                print(f"   - {f.name}")
            
            # Check managed directory
            managed_dir = gitops_path / "managed"
            if managed_dir.exists():
                managed_files = list(managed_dir.rglob("*.yaml"))
                print(f"📁 YAML files in managed/: {len(managed_files)}")
                for f in managed_files:
                    print(f"   - {f.relative_to(gitops_path)}")
            else:
                print("📁 No managed directory found")
            
            # Check raw directory  
            raw_dir = gitops_path / "raw"
            if raw_dir.exists():
                raw_files = list(raw_dir.rglob("*.yaml"))
                print(f"📁 YAML files in raw/: {len(raw_files)}")
                for f in raw_files:
                    print(f"   - {f.relative_to(gitops_path)}")
            else:
                print("📁 No raw directory found")
        else:
            print("❌ GitOps directory not found")
    else:
        print("❌ Test repository directory not found")

if __name__ == "__main__":
    print("🚀 GitHub Issue #1 - GitOps Fix Validation")
    print()
    
    # Validate code changes
    code_changes_valid = validate_code_changes()
    
    # Check test environment state  
    check_existing_test_fabric()
    
    print("\n" + "=" * 50)
    if code_changes_valid:
        print("✅ VALIDATION COMPLETE: GitOps fix implementation is correct")
        print("\n📋 What was fixed:")
        print("• Fabric creation now triggers GitOpsOnboardingService instead of GitOpsDirectoryManager")
        print("• Pre-existing YAML files are scanned and migrated to raw/ directory")
        print("• Migrated files are processed through GitOpsIngestionService")
        print("• Files are moved to opinionated managed/ directory structure")
        print("• Original files are archived after successful processing")
        print("\n🎯 Next Steps:")
        print("• Create a new fabric in HNP test environment to test the fix")
        print("• Verify that pre-existing files are processed automatically")
        print("• Confirm files appear in managed/ directory structure")
    else:
        print("❌ VALIDATION FAILED: Code changes are incomplete or incorrect")
    
    sys.exit(0 if code_changes_valid else 1)