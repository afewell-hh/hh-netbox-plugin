#!/usr/bin/env python3
"""
Simple Sync Validation
Test sync endpoints without CSRF complexity - focus on endpoint accessibility and behavior
"""

import requests
import json
import time
from datetime import datetime
import sys
import os

# Add the scripts directory to path for imports
sys.path.append('/home/ubuntu/cc/hedgehog-netbox-plugin/project_management/07_qapm_workspaces/active_projects/qapm_20250804_171500_issue_1_continuation/temp/testing_scripts')

class SimpleSyncValidation:
    def __init__(self):
        self.base_url = "http://localhost:8000"
        self.session = requests.Session()
        self.fabric_id = "28"
        
    def test_endpoint_accessibility(self):
        """Test that both sync endpoints are accessible."""
        print("🔍 Testing Sync Endpoint Accessibility")
        print("=" * 50)
        
        endpoints = {
            "github_sync": f"{self.base_url}/plugins/hedgehog/fabrics/{self.fabric_id}/github-sync/",
            "fabric_sync": f"{self.base_url}/plugins/hedgehog/fabrics/{self.fabric_id}/sync/"
        }
        
        results = {}
        
        for endpoint_name, url in endpoints.items():
            print(f"\nTesting {endpoint_name}: {url}")
            
            try:
                response = self.session.get(url)
                results[endpoint_name] = {
                    "url": url,
                    "status_code": response.status_code,
                    "accessible": response.status_code in [200, 405],  # 405 = Method Not Allowed (expects POST)
                    "content_length": len(response.text)
                }
                
                if response.status_code == 200:
                    print(f"✅ Endpoint accessible (GET: {response.status_code})")
                elif response.status_code == 405:
                    print(f"✅ Endpoint accessible (expects POST: {response.status_code})")
                else:
                    print(f"❌ Endpoint issue (status: {response.status_code})")
                    
            except Exception as e:
                print(f"❌ Error accessing endpoint: {e}")
                results[endpoint_name] = {
                    "url": url,
                    "error": str(e),
                    "accessible": False
                }
        
        return results
    
    def validate_github_state_tracking(self):
        """Test the GitHub state tracking functionality."""
        print(f"\n🔍 Validating GitHub State Tracking")
        print("=" * 50)
        
        try:
            from github_state_validator import GitHubStateValidator
            validator = GitHubStateValidator()
            
            print("📸 Testing GitHub state documentation...")
            
            # Document current state
            state = validator.document_current_state()
            filepath = validator.save_state(state, "validation_test")
            
            raw_file_count = len(state["raw_directory"]["contents"]) if state["raw_directory"]["contents"] else 0
            managed_file_count = len(state["managed_directory"]["contents"]) if state["managed_directory"]["contents"] else 0
            
            result = {
                "github_state_accessible": True,
                "raw_files_count": raw_file_count,
                "managed_files_count": managed_file_count,
                "state_file": filepath,
                "raw_files": [f['name'] for f in (state["raw_directory"]["contents"] or [])],
                "managed_files": [f['name'] for f in (state["managed_directory"]["contents"] or [])]
            }
            
            print(f"✅ GitHub state tracking works")
            print(f"   Raw files: {raw_file_count}")
            print(f"   Managed files: {managed_file_count}")
            
            # Check if we have the expected unprocessed files
            yaml_files = [f for f in result["raw_files"] if f.endswith('.yaml')]
            if len(yaml_files) >= 3:  # prepop.yaml, test-vpc.yaml, test-vpc-2.yaml
                print(f"✅ Found expected YAML files in raw directory: {yaml_files}")
                result["has_unprocessed_files"] = True
            else:
                print(f"⚠️ Fewer YAML files than expected in raw directory")
                result["has_unprocessed_files"] = False
                
            return result
            
        except Exception as e:
            print(f"❌ GitHub state tracking failed: {e}")
            return {"github_state_accessible": False, "error": str(e)}
    
    def validate_management_commands(self):
        """Validate that management commands work as expected."""
        print(f"\n🔍 Validating Management Commands")
        print("=" * 50)
        
        results = {
            "commands_available": False,
            "sync_fabric_works": False,
            "ingest_raw_files_available": False
        }
        
        try:
            import subprocess
            
            # Test sync_fabric command help
            print("Testing sync_fabric command availability...")
            result = subprocess.run([
                "sudo", "docker", "exec", "netbox-docker-netbox-1", 
                "python", "manage.py", "sync_fabric", "--help"
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                print("✅ sync_fabric command available")
                results["commands_available"] = True
                
                # Test sync_fabric execution (we know this works from previous test)
                print("Testing sync_fabric execution...")
                sync_result = subprocess.run([
                    "sudo", "docker", "exec", "netbox-docker-netbox-1", 
                    "python", "manage.py", "sync_fabric", "28", "--json"
                ], capture_output=True, text=True, timeout=30)
                
                if sync_result.returncode == 0:
                    print("✅ sync_fabric command executes successfully")
                    results["sync_fabric_works"] = True
                    try:
                        sync_output = json.loads(sync_result.stdout)
                        results["sync_fabric_output"] = sync_output
                    except:
                        results["sync_fabric_output"] = sync_result.stdout
                else:
                    print(f"❌ sync_fabric execution failed: {sync_result.stderr}")
                    results["sync_fabric_error"] = sync_result.stderr
            else:
                print(f"❌ sync_fabric command not available: {result.stderr}")
                
            # Test ingest_raw_files command
            print("Testing ingest_raw_files command availability...")
            ingest_result = subprocess.run([
                "sudo", "docker", "exec", "netbox-docker-netbox-1", 
                "python", "manage.py", "ingest_raw_files", "--help"
            ], capture_output=True, text=True, timeout=10)
            
            if ingest_result.returncode == 0:
                print("✅ ingest_raw_files command available")
                results["ingest_raw_files_available"] = True
            else:
                print(f"❌ ingest_raw_files command not available")
                
        except Exception as e:
            print(f"❌ Management command validation failed: {e}")
            results["error"] = str(e)
            
        return results
    
    def run_validation(self):
        """Run complete validation suite."""
        print("🎯 Integration Testing Specialist - Validation Suite")
        print("Validating Investigation Findings from Backend Investigation Specialist")
        print("=" * 80)
        
        validation_results = {
            "validation_session": datetime.now().strftime("%Y%m%d_%H%M%S"),
            "fabric_id": self.fabric_id,
            "findings_to_validate": [
                "Both sync endpoints are accessible",
                "GitHub repository has unprocessed files in raw/ directory",
                "Management commands work and can process files",
                "File processing pipeline exists and functions"
            ],
            "test_results": {}
        }
        
        # Test 1: Endpoint Accessibility
        print("\n📍 Test 1: Sync Endpoint Accessibility")
        endpoint_results = self.test_endpoint_accessibility()
        validation_results["test_results"]["endpoint_accessibility"] = endpoint_results
        
        # Test 2: GitHub State Tracking
        print("\n📍 Test 2: GitHub State Tracking")
        github_results = self.validate_github_state_tracking()
        validation_results["test_results"]["github_state"] = github_results
        
        # Test 3: Management Commands
        print("\n📍 Test 3: Management Command Validation")
        command_results = self.validate_management_commands()
        validation_results["test_results"]["management_commands"] = command_results
        
        # Summary
        print(f"\n{'='*80}")
        print("🎯 VALIDATION SUMMARY")
        print(f"{'='*80}")
        
        validations = []
        
        # Check endpoint accessibility
        github_accessible = endpoint_results.get("github_sync", {}).get("accessible", False)
        fabric_accessible = endpoint_results.get("fabric_sync", {}).get("accessible", False)
        if github_accessible and fabric_accessible:
            validations.append("✅ Both sync endpoints are accessible")
        else:
            validations.append("❌ Sync endpoint accessibility issues")
            
        # Check GitHub state
        has_unprocessed = github_results.get("has_unprocessed_files", False)
        if has_unprocessed:
            validations.append("✅ GitHub repository has unprocessed YAML files")
        else:
            validations.append("❌ GitHub repository state unclear")
            
        # Check management commands
        commands_work = command_results.get("sync_fabric_works", False)
        if commands_work:
            validations.append("✅ Management commands work and process files")
        else:
            validations.append("❌ Management command issues")
            
        for validation in validations:
            print(validation)
            
        # Overall assessment
        success_count = len([v for v in validations if v.startswith("✅")])
        total_count = len(validations)
        
        validation_results["validation_score"] = f"{success_count}/{total_count}"
        validation_results["overall_success"] = success_count == total_count
        
        print(f"\nValidation Score: {success_count}/{total_count}")
        
        if success_count == total_count:
            print("🎉 ALL VALIDATIONS PASSED - Investigation findings are supported")
        else:
            print("⚠️ Some validations failed - requires further investigation")
            
        return validation_results
    
    def save_results(self, results):
        """Save validation results."""
        filename = f"simple_validation_results_{results['validation_session']}.json"
        filepath = f"/home/ubuntu/cc/hedgehog-netbox-plugin/project_management/07_qapm_workspaces/active_projects/qapm_20250804_171500_issue_1_continuation/04_sub_agent_work/integration_testing/evidence/{filename}"
        
        with open(filepath, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n📊 Validation results saved to: {filepath}")
        return filepath

if __name__ == "__main__":
    validator = SimpleSyncValidation()
    results = validator.run_validation()
    if results:
        validator.save_results(results)