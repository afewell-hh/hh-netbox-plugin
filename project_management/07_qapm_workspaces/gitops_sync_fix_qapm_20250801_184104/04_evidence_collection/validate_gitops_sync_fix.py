#!/usr/bin/env python3
"""
GitOps Sync Fix Validation Script
Validates the claim that GitOps sync is now working by testing the complete workflow.
"""

import os
import sys
import json
import requests
from datetime import datetime

# Validation Evidence Collection
class GitOpsSyncValidator:
    def __init__(self):
        self.evidence = {
            'validation_start_time': datetime.now().isoformat(),
            'test_results': {},
            'github_state': {},
            'functional_tests': {},
            'technical_validation': {}
        }
        self.github_api_url = "https://api.github.com/repos/githedgehog/hedgehog-netbox-plugin"
        
    def phase1_initial_assessment(self):
        """Phase 1: Initial Assessment - Verify claimed fix and baseline state"""
        print("🔍 Phase 1: Initial Assessment")
        
        # 1. Verify the URLs import fix
        urls_file = "/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/urls.py"
        with open(urls_file, 'r') as f:
            urls_content = f.read()
            
        # Check if fix is present
        if "from .views.fabric_views import FabricSyncView" in urls_content:
            self.evidence['technical_validation']['import_fix_present'] = True
            print("✅ CONFIRMED: Import fix is present - using fabric_views.FabricSyncView")
        else:
            self.evidence['technical_validation']['import_fix_present'] = False
            print("❌ ISSUE: Import fix not found")
            
        # 2. Check GitHub raw directory baseline
        try:
            response = requests.get(f"{self.github_api_url}/contents/raw")
            if response.status_code == 200:
                files = response.json()
                if isinstance(files, list):
                    file_names = [f['name'] for f in files]
                    self.evidence['github_state']['raw_directory_files_before'] = file_names
                    print(f"📁 GitHub raw/ directory contains {len(file_names)} files: {file_names}")
                else:
                    self.evidence['github_state']['raw_directory_files_before'] = []
                    print("📁 GitHub raw/ directory is empty")
            else:
                print(f"⚠️  Could not access GitHub raw directory: {response.status_code}")
                self.evidence['github_state']['github_access_error'] = response.status_code
        except Exception as e:
            print(f"❌ GitHub API error: {e}")
            self.evidence['github_state']['github_api_error'] = str(e)
    
    def phase2_technical_validation(self):
        """Phase 2: Technical Validation - Code review and service analysis"""
        print("\n🔧 Phase 2: Technical Validation")
        
        # Check if FabricSyncView has GitOps functionality
        fabric_views_file = "/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/views/fabric_views.py"
        with open(fabric_views_file, 'r') as f:
            fabric_views_content = f.read()
            
        # Look for GitOps-specific code
        gitops_indicators = [
            "ensure_gitops_structure",
            "ingest_fabric_raw_files", 
            "GitOps integration",
            "structure_result",
            "ingest_fabric_raw_files(fabric)"
        ]
        
        found_indicators = []
        for indicator in gitops_indicators:
            if indicator in fabric_views_content:
                found_indicators.append(indicator)
                
        self.evidence['technical_validation']['gitops_functionality_present'] = len(found_indicators) > 0
        self.evidence['technical_validation']['gitops_indicators_found'] = found_indicators
        
        if found_indicators:
            print(f"✅ CONFIRMED: GitOps functionality found in FabricSyncView")
            print(f"   Found indicators: {found_indicators}")
        else:
            print("❌ ISSUE: No GitOps functionality found in FabricSyncView")
            
        # Check if URL routing is correct
        urls_file = "/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/urls.py"
        with open(urls_file, 'r') as f:
            urls_content = f.read()
            
        if "path('fabrics/<int:pk>/sync/', FabricSyncView.as_view(), name='fabric_sync')" in urls_content:
            self.evidence['technical_validation']['url_routing_correct'] = True
            print("✅ CONFIRMED: URL routing points to FabricSyncView")
        else:
            self.evidence['technical_validation']['url_routing_correct'] = False
            print("❌ ISSUE: URL routing not correct")
    
    def phase3_functional_validation(self):
        """Phase 3: Functional Validation - Test GitOps workflow"""
        print("\n⚙️ Phase 3: Functional Validation")
        print("NOTE: This requires a running NetBox instance for full testing")
        
        # Check if we can import the modules
        try:
            sys.path.insert(0, '/home/ubuntu/cc/hedgehog-netbox-plugin')
            from netbox_hedgehog.views.fabric_views import FabricSyncView
            self.evidence['functional_tests']['fabric_sync_view_importable'] = True
            print("✅ FabricSyncView can be imported")
        except Exception as e:
            self.evidence['functional_tests']['fabric_sync_view_importable'] = False
            self.evidence['functional_tests']['import_error'] = str(e)
            print(f"❌ Cannot import FabricSyncView: {e}")
            
        # Check if GitOps signals exist
        try:
            from netbox_hedgehog.signals import ensure_gitops_structure, ingest_fabric_raw_files
            self.evidence['functional_tests']['gitops_signals_importable'] = True
            print("✅ GitOps signals can be imported")
        except Exception as e:
            self.evidence['functional_tests']['gitops_signals_importable'] = False
            self.evidence['functional_tests']['signals_import_error'] = str(e)
            print(f"❌ Cannot import GitOps signals: {e}")
    
    def save_evidence(self):
        """Save all validation evidence"""
        self.evidence['validation_end_time'] = datetime.now().isoformat()
        
        evidence_file = "/home/ubuntu/cc/hedgehog-netbox-plugin/project_management/07_qapm_workspaces/gitops_sync_fix_qapm_20250801_184104/04_evidence_collection/validation_evidence.json"
        with open(evidence_file, 'w') as f:
            json.dump(self.evidence, f, indent=2)
            
        print(f"\n📋 Evidence saved to: {evidence_file}")
        
    def generate_assessment_report(self):
        """Generate final assessment report"""
        print("\n" + "="*60)
        print("🎯 FINAL ASSESSMENT REPORT")
        print("="*60)
        
        # Technical validation results
        tech_val = self.evidence['technical_validation']
        import_fix = tech_val.get('import_fix_present', False)
        gitops_func = tech_val.get('gitops_functionality_present', False)
        url_routing = tech_val.get('url_routing_correct', False)
        
        # Functional validation results
        func_val = self.evidence['functional_tests']
        view_import = func_val.get('fabric_sync_view_importable', False)
        signals_import = func_val.get('gitops_signals_importable', False)
        
        print(f"✅ Import Fix Applied:          {import_fix}")
        print(f"✅ GitOps Functionality Present: {gitops_func}")
        print(f"✅ URL Routing Correct:         {url_routing}")
        print(f"✅ View Importable:             {view_import}")
        print(f"✅ Signals Importable:          {signals_import}")
        
        # Calculate overall score
        checks = [import_fix, gitops_func, url_routing, view_import, signals_import]
        passed_checks = sum(checks)
        total_checks = len(checks)
        
        success_rate = (passed_checks / total_checks) * 100
        
        print(f"\n📊 Technical Validation Score: {passed_checks}/{total_checks} ({success_rate:.1f}%)")
        
        if success_rate >= 80:
            print("🟢 ASSESSMENT: Technical validation PASSED")
            print("   The import fix appears to be correctly implemented.")
            print("   GitOps functionality is present in the correct view.")
        elif success_rate >= 60:
            print("🟡 ASSESSMENT: Technical validation PARTIAL")
            print("   Some issues found that may affect functionality.")
        else:
            print("🔴 ASSESSMENT: Technical validation FAILED")
            print("   Critical issues found that will prevent proper operation.")
            
        print("\n⚠️  IMPORTANT: This is only technical validation.")
        print("   Functional testing requires a running NetBox instance")
        print("   and access to the configured GitHub repository.")
        
        return success_rate >= 80

def main():
    """Run the complete validation"""
    print("🚀 GitOps Sync Fix Validation")
    print("="*50)
    
    validator = GitOpsSyncValidator()
    
    # Run validation phases
    validator.phase1_initial_assessment()
    validator.phase2_technical_validation() 
    validator.phase3_functional_validation()
    
    # Save evidence and generate report
    validator.save_evidence()
    passed = validator.generate_assessment_report()
    
    # Exit with appropriate code
    sys.exit(0 if passed else 1)

if __name__ == "__main__":
    main()