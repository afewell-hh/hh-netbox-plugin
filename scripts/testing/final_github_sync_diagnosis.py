#!/usr/bin/env python3
"""
FINAL GITHUB GITOPS SYNC DIAGNOSIS

This script provides the definitive analysis of why GitHub GitOps sync 
doesn't work despite code implementation being present.

Key Findings from Comprehensive Testing:
1. Code Implementation: ✅ PRESENT (1,549+ lines)
2. URL Registration: ✅ CONFIGURED in urls.py
3. API Endpoint: ❌ RETURNS 404
4. GitHub Authentication: ❌ NOT CONFIGURED
5. Functional Testing: ❌ NEVER PERFORMED

CRITICAL ISSUE: Previous agents claimed "100% COMPLETE" without functional validation.
"""

import requests
import json
from datetime import datetime

def diagnose_github_sync_failure():
    """Final diagnosis of GitHub sync failure"""
    
    print("🔍 FINAL GITHUB GITOPS SYNC DIAGNOSIS")
    print("=" * 80)
    
    diagnosis = {
        'timestamp': datetime.now().isoformat(),
        'findings': {},
        'evidence': {},
        'root_causes': [],
        'recommendations': []
    }
    
    base_url = "http://localhost:8000"
    
    # Test 1: Check if any fabrics exist
    print("\n1. Testing fabric existence:")
    try:
        fabric_response = requests.get(f"{base_url}/plugins/hedgehog/fabrics/", timeout=10)
        
        if fabric_response.status_code == 200:
            # Look for fabric IDs in the response
            fabric_ids = []
            if 'fabrics/1/' in fabric_response.text:
                fabric_ids.append('1')
            if 'fabrics/2/' in fabric_response.text:
                fabric_ids.append('2')
                
            diagnosis['findings']['fabric_availability'] = {
                'status': 'SUCCESS',
                'fabric_list_accessible': True,
                'potential_fabric_ids': fabric_ids,
                'response_length': len(fabric_response.text)
            }
            
            print(f"   ✅ Fabric list accessible ({len(fabric_response.text)} chars)")
            if fabric_ids:
                print(f"   ✅ Potential fabric IDs found: {fabric_ids}")
            else:
                print("   ⚠️  No obvious fabric IDs detected in response")
                
        else:
            diagnosis['findings']['fabric_availability'] = {
                'status': 'FAILED',
                'status_code': fabric_response.status_code
            }
            print(f"   ❌ Fabric list not accessible: {fabric_response.status_code}")
            
    except Exception as e:
        diagnosis['findings']['fabric_availability'] = {'status': 'ERROR', 'error': str(e)}
        print(f"   ❌ Fabric availability test error: {e}")
    
    # Test 2: Test multiple fabric IDs for GitHub sync
    print("\n2. Testing GitHub sync endpoints with multiple IDs:")
    
    test_fabric_ids = ['1', '2', '3', 'test']
    github_sync_results = {}
    
    for fabric_id in test_fabric_ids:
        try:
            sync_url = f"{base_url}/plugins/hedgehog/fabrics/{fabric_id}/github-sync/"
            
            # Test both GET and POST
            get_response = requests.get(sync_url, timeout=5)
            post_response = requests.post(sync_url, timeout=5)
            
            github_sync_results[fabric_id] = {
                'get_status': get_response.status_code,
                'post_status': post_response.status_code,
                'get_accessible': get_response.status_code != 404,
                'post_accessible': post_response.status_code != 404
            }
            
            if get_response.status_code != 404 or post_response.status_code != 404:
                print(f"   ✅ Fabric {fabric_id}: GET={get_response.status_code}, POST={post_response.status_code}")
            else:
                print(f"   ❌ Fabric {fabric_id}: Both GET and POST return 404")
                
        except Exception as e:
            github_sync_results[fabric_id] = {'error': str(e)}
            print(f"   ❌ Fabric {fabric_id}: Error - {e}")
    
    diagnosis['findings']['github_sync_endpoints'] = github_sync_results
    
    # Test 3: Check URL pattern registration
    print("\n3. Testing URL pattern registration:")
    
    # Test fabric detail URLs to see if pattern works at all
    fabric_detail_tests = {}
    for fabric_id in ['1', '2']:
        try:
            detail_url = f"{base_url}/plugins/hedgehog/fabrics/{fabric_id}/"
            response = requests.get(detail_url, timeout=5)
            fabric_detail_tests[fabric_id] = {
                'status_code': response.status_code,
                'accessible': response.status_code not in [404, 500]
            }
            
            if response.status_code == 200:
                print(f"   ✅ Fabric {fabric_id} detail page works (200)")
            elif response.status_code == 404:
                print(f"   ❌ Fabric {fabric_id} detail page not found (404)")
            else:
                print(f"   ⚠️  Fabric {fabric_id} detail page: {response.status_code}")
                
        except Exception as e:
            fabric_detail_tests[fabric_id] = {'error': str(e)}
            print(f"   ❌ Fabric {fabric_id} detail test error: {e}")
    
    diagnosis['findings']['fabric_detail_endpoints'] = fabric_detail_tests
    
    # Test 4: Check other sync endpoints
    print("\n4. Testing other sync endpoints:")
    
    other_sync_endpoints = [
        'fabrics/1/sync/',
        'fabrics/1/test-connection/',
        'api/gitops/yaml-preview/',
        'api/gitops/yaml-validation/'
    ]
    
    other_sync_results = {}
    for endpoint in other_sync_endpoints:
        try:
            url = f"{base_url}/plugins/hedgehog/{endpoint}"
            response = requests.get(url, timeout=5)
            other_sync_results[endpoint] = {
                'status_code': response.status_code,
                'accessible': response.status_code != 404
            }
            
            if response.status_code != 404:
                print(f"   ✅ {endpoint}: {response.status_code}")
            else:
                print(f"   ❌ {endpoint}: 404")
                
        except Exception as e:
            other_sync_results[endpoint] = {'error': str(e)}
            print(f"   ❌ {endpoint}: Error - {e}")
    
    diagnosis['findings']['other_sync_endpoints'] = other_sync_results
    
    # Analysis: Determine root causes
    print("\n5. Root Cause Analysis:")
    
    # Check if any sync endpoints work
    any_github_sync_works = any(
        result.get('get_accessible') or result.get('post_accessible') 
        for result in github_sync_results.values() 
        if 'error' not in result
    )
    
    any_fabric_exists = any(
        result.get('accessible') 
        for result in fabric_detail_tests.values() 
        if 'error' not in result
    )
    
    other_sync_works = any(
        result.get('accessible') 
        for result in other_sync_results.values() 
        if 'error' not in result
    )
    
    if not any_github_sync_works:
        diagnosis['root_causes'].append("GitHub sync endpoints return 404 for all tested fabric IDs")
        print("   🚨 ROOT CAUSE: GitHub sync endpoints completely inaccessible")
        
    if not any_fabric_exists:
        diagnosis['root_causes'].append("No valid fabric IDs exist in system")
        print("   🚨 ROOT CAUSE: No valid fabrics exist for testing")
    else:
        print("   ✅ Some fabric detail pages accessible")
        
    if other_sync_works:
        diagnosis['root_causes'].append("Other sync endpoints work, GitHub sync specifically broken")
        print("   🚨 ROOT CAUSE: GitHub sync endpoint specifically broken")
    else:
        diagnosis['root_causes'].append("All sync endpoints may be broken")
        print("   🚨 ROOT CAUSE: Sync endpoints generally broken")
    
    # Recommendations
    print("\n6. Recommendations:")
    
    if not any_fabric_exists:
        diagnosis['recommendations'].append("Create a test fabric in NetBox first")
        print("   📋 RECOMMENDATION: Create test fabric before testing sync")
        
    if not any_github_sync_works:
        diagnosis['recommendations'].append("Check URL routing registration for GitHub sync endpoint")
        print("   📋 RECOMMENDATION: Verify URL routing for github-sync endpoint")
        
    diagnosis['recommendations'].extend([
        "Configure GitHub authentication token",
        "Perform end-to-end functional testing",
        "Validate GitHub repository processing"
    ])
    
    print("   📋 RECOMMENDATION: Configure GitHub authentication")
    print("   📋 RECOMMENDATION: Test with valid fabric ID")
    print("   📋 RECOMMENDATION: Validate actual file processing")
    
    # Final verdict
    print("\n7. FINAL VERDICT:")
    
    if any_github_sync_works:
        verdict = "GitHub sync endpoint accessible but authentication/functionality issues remain"
        print("   ⚠️  VERDICT: Endpoint accessible, functionality unknown")
    else:
        verdict = "GitHub sync endpoint completely inaccessible (404 errors)"
        print("   ❌ VERDICT: GitHub sync endpoint broken (404)")
    
    diagnosis['evidence']['final_verdict'] = verdict
    diagnosis['evidence']['github_sync_accessible'] = any_github_sync_works
    diagnosis['evidence']['fabrics_exist'] = any_fabric_exists
    diagnosis['evidence']['other_sync_works'] = other_sync_works
    
    # Save diagnosis
    try:
        with open('final_github_sync_diagnosis.json', 'w') as f:
            json.dump(diagnosis, f, indent=2)
        print(f"\n📄 Final diagnosis saved to: final_github_sync_diagnosis.json")
    except Exception as e:
        print(f"\n❌ Failed to save diagnosis: {e}")
    
    return diagnosis

if __name__ == '__main__':
    diagnose_github_sync_failure()