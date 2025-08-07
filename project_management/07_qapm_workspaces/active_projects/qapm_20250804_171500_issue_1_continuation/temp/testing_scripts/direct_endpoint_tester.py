#!/usr/bin/env python3
"""
Direct Endpoint Tester
Test sync endpoints directly without authentication
"""

import requests
import json
from datetime import datetime
import time
import re

class DirectEndpointTester:
    def __init__(self):
        self.base_url = "http://localhost:8000"
        self.session = requests.Session()
        
    def get_fabric_list(self):
        """Extract fabric IDs from the fabrics page."""
        print("Extracting fabric information from fabrics page...")
        
        fabrics_url = f"{self.base_url}/plugins/hedgehog/fabrics/"
        response = self.session.get(fabrics_url)
        
        if response.status_code != 200:
            print(f"❌ Could not access fabrics page: {response.status_code}")
            return []
            
        # Look for fabric links/IDs in the HTML
        fabric_ids = []
        
        # Pattern to find fabric detail links
        pattern = r'/plugins/hedgehog/fabrics/(\d+)/'
        matches = re.findall(pattern, response.text)
        
        for match in matches:
            if match not in fabric_ids:
                fabric_ids.append(match)
                
        print(f"Found {len(fabric_ids)} fabric(s): {fabric_ids}")
        return fabric_ids
    
    def test_fabric_detail_page(self, fabric_id):
        """Test access to fabric detail page and look for sync buttons."""
        print(f"\nTesting fabric {fabric_id} detail page...")
        
        detail_url = f"{self.base_url}/plugins/hedgehog/fabrics/{fabric_id}/"
        response = self.session.get(detail_url)
        
        if response.status_code != 200:
            print(f"❌ Could not access fabric detail page: {response.status_code}")
            return None
            
        print(f"✅ Fabric detail page accessible")
        
        # Look for sync button JavaScript functions
        has_trigger_sync = 'triggerSync(' in response.text
        has_sync_from_fabric = 'syncFromFabric(' in response.text
        
        print(f"Has triggerSync() function: {'✅' if has_trigger_sync else '❌'}")
        print(f"Has syncFromFabric() function: {'✅' if has_sync_from_fabric else '❌'}")
        
        # Look for CSRF token
        csrf_pattern = r'name="csrfmiddlewaretoken" value="([^"]+)"'
        csrf_match = re.search(csrf_pattern, response.text)
        csrf_token = csrf_match.group(1) if csrf_match else None
        
        if csrf_token:
            print(f"CSRF token found: {csrf_token[:20]}...")
        else:
            print("❌ No CSRF token found")
        
        return {
            "fabric_id": fabric_id,
            "page_accessible": True,
            "has_trigger_sync": has_trigger_sync,
            "has_sync_from_fabric": has_sync_from_fabric,
            "csrf_token": csrf_token
        }
    
    def test_sync_endpoint(self, fabric_id, endpoint_type, csrf_token=None):
        """Test a specific sync endpoint."""
        if endpoint_type == "github":
            endpoint_url = f"{self.base_url}/plugins/hedgehog/fabrics/{fabric_id}/github-sync/"
            endpoint_name = "GitHub Sync (FabricGitHubSyncView)"
        elif endpoint_type == "fabric":
            endpoint_url = f"{self.base_url}/plugins/hedgehog/fabrics/{fabric_id}/sync/"
            endpoint_name = "Fabric Sync (FabricSyncView)"
        else:
            print(f"❌ Unknown endpoint type: {endpoint_type}")
            return None
            
        print(f"\n=== Testing {endpoint_name} ===")
        print(f"URL: {endpoint_url}")
        
        # First test GET request to see if endpoint exists
        start_time = time.time()
        get_response = self.session.get(endpoint_url)
        get_time = time.time() - start_time
        
        print(f"GET request: {get_response.status_code} ({get_time:.2f}s)")
        
        result = {
            "endpoint_type": endpoint_type,
            "endpoint_name": endpoint_name,
            "url": endpoint_url,
            "get_status": get_response.status_code,
            "get_time": round(get_time, 2),
            "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S")
        }
        
        # Test POST request if we have CSRF token
        if csrf_token and get_response.status_code in [200, 405]:  # 405 = Method Not Allowed (expects POST)
            print("Testing POST request...")
            
            post_data = {
                'csrfmiddlewaretoken': csrf_token
            }
            
            start_time = time.time()
            post_response = self.session.post(endpoint_url, data=post_data)
            post_time = time.time() - start_time
            
            print(f"POST request: {post_response.status_code} ({post_time:.2f}s)")
            
            result["post_status"] = post_response.status_code
            result["post_time"] = round(post_time, 2)
            
            # Check response content for success indicators
            if post_response.status_code == 200:
                response_text = post_response.text.lower()
                success_indicators = ['success', 'completed', 'synced', 'processed']
                error_indicators = ['error', 'failed', 'exception']
                
                has_success = any(indicator in response_text for indicator in success_indicators)
                has_error = any(indicator in response_text for indicator in error_indicators)
                
                result["has_success_indicator"] = has_success
                result["has_error_indicator"] = has_error
                
                if has_success and not has_error:
                    print("✅ Response indicates success")
                    result["likely_success"] = True
                elif has_error:
                    print("❌ Response indicates error")
                    result["likely_success"] = False
                else:
                    print("⚠️ Response unclear")
                    result["likely_success"] = None
                    
                # Save response snippet for analysis
                result["response_snippet"] = post_response.text[:1000]
        else:
            print("⚠️ Skipping POST test (no CSRF token or endpoint unavailable)")
            
        return result
    
    def run_comprehensive_endpoint_test(self):
        """Run comprehensive test of all endpoints."""
        print("🔍 Starting Direct Endpoint Testing")
        print("=" * 60)
        
        # Get fabric list
        fabric_ids = self.get_fabric_list()
        if not fabric_ids:
            print("❌ No fabrics found to test")
            return None
            
        test_results = {
            "test_session": datetime.now().strftime("%Y%m%d_%H%M%S"),
            "fabrics_tested": [],
            "endpoint_tests": {}
        }
        
        # Test each fabric (but limit to first one for now)
        fabric_id = fabric_ids[0]
        print(f"\n🎯 Testing Fabric ID: {fabric_id}")
        
        # Test fabric detail page
        detail_info = self.test_fabric_detail_page(fabric_id)
        if not detail_info:
            return None
            
        test_results["fabrics_tested"].append(detail_info)
        
        # Test both sync endpoints
        csrf_token = detail_info.get("csrf_token")
        
        # Test GitHub sync endpoint
        github_result = self.test_sync_endpoint(fabric_id, "github", csrf_token)
        if github_result:
            test_results["endpoint_tests"]["github_sync"] = github_result
            
        # Wait between tests
        time.sleep(2)
        
        # Test Fabric sync endpoint
        fabric_result = self.test_sync_endpoint(fabric_id, "fabric", csrf_token)
        if fabric_result:
            test_results["endpoint_tests"]["fabric_sync"] = fabric_result
            
        # Summary
        print(f"\n=== Test Summary ===")
        if github_result:
            status = "✅" if github_result.get("likely_success") else "❌" if github_result.get("likely_success") is False else "⚠️"
            print(f"GitHub Sync Endpoint: {status} (Status: {github_result.get('post_status', github_result.get('get_status'))})")
            
        if fabric_result:
            status = "✅" if fabric_result.get("likely_success") else "❌" if fabric_result.get("likely_success") is False else "⚠️"
            print(f"Fabric Sync Endpoint: {status} (Status: {fabric_result.get('post_status', fabric_result.get('get_status'))})")
            
        return test_results
    
    def save_results(self, results):
        """Save test results to evidence file."""
        if not results:
            return None
            
        filename = f"direct_endpoint_test_results_{results['test_session']}.json"
        filepath = f"/home/ubuntu/cc/hedgehog-netbox-plugin/project_management/07_qapm_workspaces/active_projects/qapm_20250804_171500_issue_1_continuation/04_sub_agent_work/integration_testing/evidence/{filename}"
        
        with open(filepath, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"📊 Test results saved to: {filepath}")
        return filepath

if __name__ == "__main__":
    tester = DirectEndpointTester()
    results = tester.run_comprehensive_endpoint_test()
    if results:
        tester.save_results(results)