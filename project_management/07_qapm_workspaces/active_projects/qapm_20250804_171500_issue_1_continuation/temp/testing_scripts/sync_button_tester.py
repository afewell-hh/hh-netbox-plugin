#!/usr/bin/env python3
"""
Sync Button Integration Tester
Integration Testing Specialist Tool

Purpose: Test both sync button behaviors and document which endpoints are called
Tests investigation findings about GitHub Sync vs Fabric Sync behavior
"""

import requests
import json
from datetime import datetime
import time
import os

class SyncButtonTester:
    def __init__(self):
        self.base_url = "http://localhost:8000"
        self.session = requests.Session()
        self.fabric_id = None
        self.csrf_token = None
        
    def authenticate(self):
        """Authenticate with NetBox admin interface."""
        print("Authenticating with NetBox...")
        
        # Get login page to retrieve CSRF token
        login_url = f"{self.base_url}/login/"
        response = self.session.get(login_url)
        
        if response.status_code != 200:
            print(f"Failed to access login page: {response.status_code}")
            return False
            
        # Extract CSRF token from response
        csrf_start = response.text.find('name="csrfmiddlewaretoken" value="')
        if csrf_start == -1:
            print("Could not find CSRF token in login page")
            return False
            
        csrf_start += len('name="csrfmiddlewaretoken" value="')
        csrf_end = response.text.find('"', csrf_start)
        self.csrf_token = response.text[csrf_start:csrf_end]
        print(f"CSRF token acquired: {self.csrf_token[:20]}...")
        
        # Perform login
        login_data = {
            'username': 'admin',
            'password': 'admin',
            'csrfmiddlewaretoken': self.csrf_token,
            'next': '/'
        }
        
        response = self.session.post(login_url, data=login_data)
        
        if response.status_code == 200 and 'dashboard' in response.url:
            print("✅ Authentication successful")
            return True
        else:
            print(f"❌ Authentication failed: {response.status_code}, URL: {response.url}")
            return False
    
    def find_fabric_id(self):
        """Find a fabric ID to test with."""
        print("Looking for fabric to test...")
        
        # Try to access fabric list
        fabrics_url = f"{self.base_url}/plugins/hedgehog/fabrics/"
        response = self.session.get(fabrics_url)
        
        if response.status_code != 200:
            print(f"Failed to access fabrics page: {response.status_code}")
            return None
            
        # Look for fabric links in the response
        # This is a simple approach - we'll look for fabric detail URLs
        fabric_links = []
        lines = response.text.split('\n')
        for line in lines:
            if '/plugins/hedgehog/fabrics/' in line and '/plugins/hedgehog/fabrics/' != line.strip():
                # Extract fabric ID from URLs like "/plugins/hedgehog/fabrics/1/"
                start = line.find('/plugins/hedgehog/fabrics/') + len('/plugins/hedgehog/fabrics/')
                end = line.find('/', start)
                if end > start:
                    fabric_id = line[start:end]
                    if fabric_id.isdigit():
                        fabric_links.append(fabric_id)
        
        if fabric_links:
            self.fabric_id = fabric_links[0]  # Use first fabric found
            print(f"✅ Found fabric ID: {self.fabric_id}")
            return self.fabric_id
        else:
            print("❌ No fabrics found")
            return None
    
    def test_github_sync_endpoint(self):
        """Test the GitHub sync endpoint that the main button calls."""
        print(f"\n=== Testing GitHub Sync Endpoint ===")
        print("This should call FabricGitHubSyncView.post()")
        
        if not self.fabric_id:
            print("❌ No fabric ID available for testing")
            return None
            
        # GitHub sync endpoint as identified in investigation
        sync_url = f"{self.base_url}/plugins/hedgehog/fabrics/{self.fabric_id}/github-sync/"
        
        # Get CSRF token from fabric detail page first
        detail_url = f"{self.base_url}/plugins/hedgehog/fabrics/{self.fabric_id}/"
        detail_response = self.session.get(detail_url)
        
        if detail_response.status_code != 200:
            print(f"❌ Could not access fabric detail page: {detail_response.status_code}")
            return None
            
        # Extract fresh CSRF token
        csrf_start = detail_response.text.find('name="csrfmiddlewaretoken" value="')
        if csrf_start != -1:
            csrf_start += len('name="csrfmiddlewaretoken" value="')
            csrf_end = detail_response.text.find('"', csrf_start)
            fresh_csrf = detail_response.text[csrf_start:csrf_end]
        else:
            fresh_csrf = self.csrf_token
        
        print(f"Calling GitHub sync endpoint: {sync_url}")
        
        # Make the sync request
        sync_data = {
            'csrfmiddlewaretoken': fresh_csrf
        }
        
        start_time = time.time()
        response = self.session.post(sync_url, data=sync_data)
        end_time = time.time()
        
        result = {
            "endpoint": "github-sync",
            "url": sync_url,
            "status_code": response.status_code,
            "response_time": round(end_time - start_time, 2),
            "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S")
        }
        
        print(f"Response: {response.status_code} ({result['response_time']}s)")
        
        if response.status_code == 200:
            print("✅ GitHub sync endpoint accessible")
            # Check if response indicates success
            if 'success' in response.text.lower() or 'sync' in response.text.lower():
                result["success"] = True
                print("✅ Sync appears successful")
            else:
                result["success"] = False
                print("⚠️ Sync response unclear")
        else:
            print(f"❌ GitHub sync failed: {response.status_code}")
            result["success"] = False
            result["error"] = response.text[:500]  # First 500 chars of error
            
        return result
    
    def test_fabric_sync_endpoint(self):
        """Test the Fabric sync endpoint that should process files."""
        print(f"\n=== Testing Fabric Sync Endpoint ===")
        print("This should call FabricSyncView.post() and process raw files")
        
        if not self.fabric_id:
            print("❌ No fabric ID available for testing")
            return None
            
        # Fabric sync endpoint as identified in investigation
        sync_url = f"{self.base_url}/plugins/hedgehog/fabrics/{self.fabric_id}/sync/"
        
        # Get fresh CSRF token
        detail_url = f"{self.base_url}/plugins/hedgehog/fabrics/{self.fabric_id}/"
        detail_response = self.session.get(detail_url)
        
        if detail_response.status_code != 200:
            print(f"❌ Could not access fabric detail page: {detail_response.status_code}")
            return None
            
        # Extract fresh CSRF token
        csrf_start = detail_response.text.find('name="csrfmiddlewaretoken" value="')
        if csrf_start != -1:
            csrf_start += len('name="csrfmiddlewaretoken" value="')
            csrf_end = detail_response.text.find('"', csrf_start)
            fresh_csrf = detail_response.text[csrf_start:csrf_end]
        else:
            fresh_csrf = self.csrf_token
        
        print(f"Calling Fabric sync endpoint: {sync_url}")
        
        # Make the sync request
        sync_data = {
            'csrfmiddlewaretoken': fresh_csrf
        }
        
        start_time = time.time()
        response = self.session.post(sync_url, data=sync_data)
        end_time = time.time()
        
        result = {
            "endpoint": "fabric-sync",
            "url": sync_url,
            "status_code": response.status_code,
            "response_time": round(end_time - start_time, 2),
            "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S")
        }
        
        print(f"Response: {response.status_code} ({result['response_time']}s)")
        
        if response.status_code == 200:
            print("✅ Fabric sync endpoint accessible")
            # Check if response indicates success
            if 'success' in response.text.lower() or 'sync' in response.text.lower():
                result["success"] = True
                print("✅ Sync appears successful")
            else:
                result["success"] = False
                print("⚠️ Sync response unclear")
        else:
            print(f"❌ Fabric sync failed: {response.status_code}")
            result["success"] = False
            result["error"] = response.text[:500]  # First 500 chars of error
            
        return result
    
    def run_comprehensive_test(self):
        """Run comprehensive test of both sync endpoints."""
        print("🔍 Starting Comprehensive Sync Button Testing")
        print("=" * 60)
        
        # Authenticate
        if not self.authenticate():
            return None
            
        # Find fabric
        if not self.find_fabric_id():
            return None
            
        test_results = {
            "test_session": datetime.now().strftime("%Y%m%d_%H%M%S"),
            "fabric_id": self.fabric_id,
            "tests": {}
        }
        
        # Test GitHub sync endpoint
        github_result = self.test_github_sync_endpoint()
        if github_result:
            test_results["tests"]["github_sync"] = github_result
            
        # Wait between tests
        time.sleep(2)
        
        # Test Fabric sync endpoint  
        fabric_result = self.test_fabric_sync_endpoint()
        if fabric_result:
            test_results["tests"]["fabric_sync"] = fabric_result
            
        print(f"\n=== Test Summary ===")
        print(f"GitHub Sync: {'✅' if github_result and github_result.get('success') else '❌'}")
        print(f"Fabric Sync: {'✅' if fabric_result and fabric_result.get('success') else '❌'}")
        
        return test_results
    
    def save_results(self, results):
        """Save test results to evidence file."""
        if not results:
            return None
            
        filename = f"sync_button_test_results_{results['test_session']}.json"
        filepath = f"/home/ubuntu/cc/hedgehog-netbox-plugin/project_management/07_qapm_workspaces/active_projects/qapm_20250804_171500_issue_1_continuation/04_sub_agent_work/integration_testing/evidence/{filename}"
        
        with open(filepath, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"📊 Test results saved to: {filepath}")
        return filepath

if __name__ == "__main__":
    tester = SyncButtonTester()
    results = tester.run_comprehensive_test()
    if results:
        tester.save_results(results)