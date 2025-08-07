#!/usr/bin/env python3
"""
Functional Validation Script for GitOps Sync Fix
This script should be run in a Django environment with a running NetBox instance.
"""

import os
import sys
import django
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
import json
import requests
from datetime import datetime

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')
django.setup()

# Now we can import our models
from netbox_hedgehog.models import HedgehogFabric, GitRepository
from netbox_hedgehog.models.vpc_api import VPC


class GitOpsSyncFunctionalValidator:
    """Functional validation for GitOps sync fix"""
    
    def __init__(self):
        self.client = Client()
        self.test_results = {
            'start_time': datetime.now().isoformat(),
            'tests': {},
            'github_state': {},
            'database_state': {},
            'errors': []
        }
        
    def setup_test_environment(self):
        """Set up test data"""
        print("🔧 Setting up test environment...")
        
        # Create test user
        self.test_user, created = User.objects.get_or_create(
            username='gitops_test_user',
            defaults={
                'email': 'test@example.com',
                'is_staff': True,
                'is_superuser': True
            }
        )
        if created:
            self.test_user.set_password('testpass123')
            self.test_user.save()
            
        # Login test user
        login_success = self.client.login(username='gitops_test_user', password='testpass123')
        self.test_results['tests']['user_login'] = login_success
        print(f"   User login: {'✅' if login_success else '❌'}")
        
        # Get or create test fabric
        self.test_fabric, created = HedgehogFabric.objects.get_or_create(
            name='test-fabric-gitops-validation',
            defaults={
                'description': 'Fabric for GitOps sync validation',
                'sync_status': 'never_synced',
                'connection_status': 'connected'
            }
        )
        
        # Get or create test git repository  
        self.test_repo, created = GitRepository.objects.get_or_create(
            name='gitops-test-1',
            defaults={
                'url': 'https://github.com/afewell-hh/gitops-test-1',
                'branch': 'main',
                'fabric': self.test_fabric
            }
        )
        
        self.test_fabric.git_repository = self.test_repo
        self.test_fabric.save()
        
        print(f"   Test fabric created: {self.test_fabric.name} (ID: {self.test_fabric.id})")
        return True
        
    def test_github_baseline_state(self):
        """Check GitHub repository baseline state"""
        print("\n📁 Testing GitHub baseline state...")
        
        github_token = os.environ.get('GITHUB_TOKEN')
        if not github_token:
            print("   ⚠️  GitHub token not available - skipping GitHub tests")
            self.test_results['github_state']['token_available'] = False
            return False
            
        headers = {
            'Authorization': f'token {github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        try:
            # Check raw directory contents
            response = requests.get(
                'https://api.github.com/repos/afewell-hh/gitops-test-1/contents/raw',
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                files = response.json()
                file_names = [f['name'] for f in files]
                self.test_results['github_state']['raw_files_before'] = file_names
                print(f"   Raw directory files: {file_names}")
                
                expected_files = ['.gitkeep', 'prepop.yaml', 'test-vpc-2.yaml', 'test-vpc.yaml']
                all_expected_present = all(f in file_names for f in expected_files)
                self.test_results['github_state']['expected_files_present'] = all_expected_present
                
                if all_expected_present:
                    print("   ✅ All expected files present in raw/")
                    return True
                else:
                    missing = [f for f in expected_files if f not in file_names]
                    print(f"   ❌ Missing expected files: {missing}")
                    return False
            else:
                print(f"   ❌ GitHub API error: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"   ❌ GitHub connection error: {e}")
            self.test_results['errors'].append(f"GitHub baseline check: {e}")
            return False
            
    def test_database_baseline_state(self):
        """Check database baseline state"""
        print("\n🗄️  Testing database baseline state...")
        
        # Count existing VPCs
        vpc_count_before = VPC.objects.count()
        self.test_results['database_state']['vpc_count_before'] = vpc_count_before
        print(f"   VPC count before sync: {vpc_count_before}")
        
        # Check fabric sync status
        fabric_status_before = self.test_fabric.sync_status
        self.test_results['database_state']['fabric_sync_status_before'] = fabric_status_before
        print(f"   Fabric sync status before: {fabric_status_before}")
        
        return True
        
    def test_sync_endpoint_access(self):
        """Test that sync endpoint is accessible"""
        print("\n🔗 Testing sync endpoint access...")
        
        sync_url = reverse('netbox_hedgehog:fabric_sync', kwargs={'pk': self.test_fabric.pk})
        print(f"   Sync URL: {sync_url}")
        
        # Test GET request (should not be allowed)
        get_response = self.client.get(sync_url)
        self.test_results['tests']['sync_get_response'] = get_response.status_code
        
        if get_response.status_code == 405:  # Method not allowed
            print("   ✅ GET request properly rejected (405)")
        else:
            print(f"   ⚠️  Unexpected GET response: {get_response.status_code}")
            
        return True
        
    def test_sync_functionality(self):
        """Test the actual sync functionality"""
        print("\n🔄 Testing sync functionality...")
        
        sync_url = reverse('netbox_hedgehog:fabric_sync', kwargs={'pk': self.test_fabric.pk})
        
        # Perform POST request to trigger sync
        post_response = self.client.post(sync_url)
        self.test_results['tests']['sync_post_response'] = post_response.status_code
        
        print(f"   POST response status: {post_response.status_code}")
        
        if post_response.status_code == 200:
            try:
                response_data = json.loads(post_response.content)
                self.test_results['tests']['sync_response_data'] = response_data
                
                if response_data.get('success'):
                    print("   ✅ Sync reported success")
                    print(f"   Message: {response_data.get('message', 'No message')}")
                    return True
                else:
                    print("   ❌ Sync reported failure")
                    print(f"   Error: {response_data.get('error', 'No error message')}")
                    return False
                    
            except json.JSONDecodeError:
                print("   ❌ Invalid JSON response")
                return False
        else:
            print(f"   ❌ Unexpected status code: {post_response.status_code}")
            return False
            
    def test_post_sync_database_state(self):
        """Check database state after sync"""
        print("\n🗄️  Testing post-sync database state...")
        
        # Refresh fabric from database
        self.test_fabric.refresh_from_db()
        
        # Count VPCs after sync
        vpc_count_after = VPC.objects.count()
        self.test_results['database_state']['vpc_count_after'] = vpc_count_after
        
        vpc_count_before = self.test_results['database_state']['vpc_count_before']
        vpc_increase = vpc_count_after - vpc_count_before
        
        print(f"   VPC count after sync: {vpc_count_after}")
        print(f"   VPC increase: {vpc_increase}")
        
        if vpc_increase > 0:
            print("   ✅ New VPC records created")
            
            # List new VPCs
            print("   New VPCs:")
            new_vpcs = VPC.objects.all().order_by('-id')[:vpc_increase]
            for vpc in new_vpcs:
                print(f"     - {vpc.name} (ID: {vpc.id})")
                
            self.test_results['database_state']['new_vpcs_created'] = True
            return True
        else:
            print("   ❌ No new VPC records created")
            self.test_results['database_state']['new_vpcs_created'] = False
            return False
            
    def test_post_sync_github_state(self):
        """Check GitHub state after sync"""
        print("\n📁 Testing post-sync GitHub state...")
        
        github_token = os.environ.get('GITHUB_TOKEN')
        if not github_token:
            print("   ⚠️  GitHub token not available - skipping")
            return False
            
        headers = {
            'Authorization': f'token {github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        try:
            # Check raw directory after sync
            response = requests.get(
                'https://api.github.com/repos/afewell-hh/gitops-test-1/contents/raw',
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                files_after = response.json()
                file_names_after = [f['name'] for f in files_after]
                self.test_results['github_state']['raw_files_after'] = file_names_after
                
                files_before = self.test_results['github_state']['raw_files_before']
                
                print(f"   Raw files before: {files_before}")
                print(f"   Raw files after: {file_names_after}")
                
                # Check if YAML files were removed (but .gitkeep should remain)
                yaml_files_before = [f for f in files_before if f.endswith('.yaml')]
                yaml_files_after = [f for f in file_names_after if f.endswith('.yaml')]
                
                if len(yaml_files_after) < len(yaml_files_before):
                    print("   ✅ YAML files moved from raw/ (GitOps working)")
                    self.test_results['github_state']['files_moved'] = True
                    return True
                else:
                    print("   ❌ YAML files still in raw/ (GitOps may not be working)")
                    self.test_results['github_state']['files_moved'] = False
                    return False
                    
            # Check managed directory structure
            managed_response = requests.get(
                'https://api.github.com/repos/afewell-hh/gitops-test-1/contents/managed',
                headers=headers,
                timeout=10
            )
            
            if managed_response.status_code == 200:
                managed_dirs = managed_response.json()
                managed_dir_names = [d['name'] for d in managed_dirs if d['type'] == 'dir']
                self.test_results['github_state']['managed_directories'] = managed_dir_names
                print(f"   Managed directories: {managed_dir_names}")
                
                if 'vpcs' in managed_dir_names:
                    print("   ✅ VPCs directory created in managed/")
                    return True
                else:
                    print("   ❌ VPCs directory not found in managed/")
                    return False
            else:
                print("   ⚠️  Managed directory not accessible")
                return False
                
        except Exception as e:
            print(f"   ❌ GitHub post-sync check error: {e}")
            self.test_results['errors'].append(f"GitHub post-sync check: {e}")
            return False
            
    def generate_final_report(self):
        """Generate final validation report"""
        print("\n" + "="*60)
        print("🎯 FUNCTIONAL VALIDATION FINAL REPORT")
        print("="*60)
        
        self.test_results['end_time'] = datetime.now().isoformat()
        
        # Count successful tests
        tests = self.test_results['tests']
        database = self.test_results['database_state']
        github = self.test_results['github_state']
        
        success_indicators = [
            tests.get('user_login', False),
            tests.get('sync_post_response', 0) == 200,
            database.get('new_vpcs_created', False),
            github.get('files_moved', False)
        ]
        
        passed_tests = sum(success_indicators)
        total_tests = len(success_indicators)
        
        print(f"✅ User Login:              {tests.get('user_login', False)}")
        print(f"✅ Sync Endpoint Response:  {tests.get('sync_post_response', 0) == 200}")
        print(f"✅ New VPCs Created:        {database.get('new_vpcs_created', False)}")
        print(f"✅ Files Moved from raw/:   {github.get('files_moved', False)}")
        
        success_rate = (passed_tests / total_tests) * 100
        print(f"\n📊 Success Rate: {passed_tests}/{total_tests} ({success_rate:.1f}%)")
        
        if success_rate >= 75:
            print("🟢 FUNCTIONAL VALIDATION: PASSED")
            print("   GitOps sync fix is working correctly!")
            verdict = "APPROVED"
        elif success_rate >= 50:
            print("🟡 FUNCTIONAL VALIDATION: PARTIAL")
            print("   Some functionality working, but issues found")
            verdict = "NEEDS_INVESTIGATION"
        else:
            print("🔴 FUNCTIONAL VALIDATION: FAILED") 
            print("   Critical issues found")
            verdict = "REJECTED"
            
        # Save detailed results
        results_file = "functional_validation_results.json"
        with open(results_file, 'w') as f:
            json.dump(self.test_results, f, indent=2)
            
        print(f"\n📋 Detailed results saved to: {results_file}")
        print(f"🏁 FINAL VERDICT: {verdict}")
        
        return verdict == "APPROVED"
        
    def cleanup_test_data(self):
        """Clean up test data"""
        print("\n🧹 Cleaning up test data...")
        
        # Note: In a real test, you might want to clean up
        # For now, we'll leave test data for inspection
        print("   Test data left for inspection")


def main():
    """Run functional validation"""
    print("🚀 GitOps Sync Fix - Functional Validation")
    print("="*50)
    
    validator = GitOpsSyncFunctionalValidator()
    
    try:
        # Setup
        if not validator.setup_test_environment():
            print("❌ Failed to set up test environment")
            return 1
            
        # Baseline testing
        validator.test_github_baseline_state()
        validator.test_database_baseline_state()
        validator.test_sync_endpoint_access()
        
        # Core functionality testing
        validator.test_sync_functionality()
        
        # Post-sync validation
        validator.test_post_sync_database_state()
        validator.test_post_sync_github_state()
        
        # Generate report
        success = validator.generate_final_report()
        
        return 0 if success else 1
        
    except Exception as e:
        print(f"❌ Validation failed with error: {e}")
        validator.test_results['errors'].append(f"Main validation error: {e}")
        return 1
    finally:
        validator.cleanup_test_data()


if __name__ == '__main__':
    sys.exit(main())