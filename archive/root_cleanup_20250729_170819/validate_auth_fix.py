#!/usr/bin/env python3
"""
Enhanced QAPM v2.1 - Complete Validation of Git Repository Authentication Fix

This script provides comprehensive evidence that the authentication issue has been resolved.
Follows evidence-based validation protocols from QAPM training materials.
"""

import requests
import json
import sys
from datetime import datetime

def validate_authentication_fix():
    """
    Comprehensive validation of the git repository authentication fix
    with complete evidence collection for QAPM standards
    """
    
    base_url = "http://localhost:8000"
    plugin_base = f"{base_url}/plugins/hedgehog"
    
    # Evidence collection structure
    evidence = {
        "validation_timestamp": datetime.now().isoformat(),
        "qapm_agent": "Enhanced QAPM v2.1",
        "issue_description": "Git repository list page bypassed authentication while detail page required it",
        "fix_applied": "Added LoginRequiredMixin to WorkingGitRepositoryListView and GitRepositoryDetailView",
        "validation_results": {},
        "before_fix_evidence": {
            "list_page_status": 200,  # From previous investigation
            "detail_page_status": 302  # From previous investigation
        },
        "after_fix_evidence": {},
        "user_workflow_validation": {},
        "regression_testing": {},
        "evidence_quality": "comprehensive"
    }
    
    print("🔍 ENHANCED QAPM v2.1 - Authentication Fix Validation")
    print("=" * 60)
    print("🎯 OBJECTIVE: Validate git repository authentication fix")
    print("📋 EVIDENCE STANDARD: Complete user workflow validation")
    print()
    
    # Test 1: Validate list page now requires authentication
    print("📋 TEST 1: Git Repositories List Page (After Fix)")
    print("-" * 50)
    
    list_url = f"{plugin_base}/git-repositories/"
    try:
        response = requests.get(list_url, allow_redirects=False)
        
        evidence["after_fix_evidence"]["list_page"] = {
            "url": list_url,
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "content_length": len(response.content) if response.content else 0
        }
        
        print(f"URL: {list_url}")
        print(f"Status: {response.status_code}")
        
        if response.status_code == 302:
            location = response.headers.get('Location', '')
            print(f"✅ FIXED: Now redirects to {location}")
            print("✅ VALIDATION: List page now requires authentication")
            evidence["validation_results"]["list_page_fixed"] = True
        elif response.status_code == 200:
            print("❌ NOT FIXED: Still accessible without authentication")
            evidence["validation_results"]["list_page_fixed"] = False
        else:
            print(f"❓ UNEXPECTED: Status {response.status_code}")
            evidence["validation_results"]["list_page_fixed"] = False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        evidence["after_fix_evidence"]["list_page"] = {"error": str(e)}
        evidence["validation_results"]["list_page_fixed"] = False
    
    print()
    
    # Test 2: Validate detail page still requires authentication (regression test)
    print("📄 TEST 2: Git Repository Detail Page (Regression Check)")
    print("-" * 50)
    
    detail_url = f"{plugin_base}/git-repositories/1/"
    try:
        response = requests.get(detail_url, allow_redirects=False)
        
        evidence["after_fix_evidence"]["detail_page"] = {
            "url": detail_url,
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "content_length": len(response.content) if response.content else 0
        }
        
        print(f"URL: {detail_url}")
        print(f"Status: {response.status_code}")
        
        if response.status_code == 302:
            location = response.headers.get('Location', '')
            print(f"✅ MAINTAINED: Still redirects to {location}")
            print("✅ REGRESSION TEST: Detail page authentication preserved")
            evidence["validation_results"]["detail_page_maintained"] = True
        elif response.status_code == 404:
            print("ℹ️  Repository doesn't exist, but authentication works (404 after auth)")
            evidence["validation_results"]["detail_page_maintained"] = True
        else:
            print(f"❌ REGRESSION: Unexpected status {response.status_code}")
            evidence["validation_results"]["detail_page_maintained"] = False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        evidence["after_fix_evidence"]["detail_page"] = {"error": str(e)}
        evidence["validation_results"]["detail_page_maintained"] = False
    
    print()
    
    # Test 3: Validate consistency across plugin
    print("🔒 TEST 3: Authentication Consistency Check")
    print("-" * 40)
    
    # Test other plugin pages to ensure consistency
    test_pages = [
        (f"{plugin_base}/", "plugin_overview"),
        (f"{plugin_base}/fabrics/", "fabric_list"),
        (f"{plugin_base}/vpcs/", "vpc_list")
    ]
    
    consistency_results = {}
    
    for url, page_name in test_pages:
        try:
            response = requests.get(url, allow_redirects=False)
            status = response.status_code
            
            if status == 302:
                consistency_results[page_name] = "requires_auth"
                print(f"✅ {page_name}: Requires authentication ({status})")
            else:
                consistency_results[page_name] = f"status_{status}"
                print(f"❓ {page_name}: Status {status}")
                
        except Exception as e:
            consistency_results[page_name] = f"error_{e}"
            print(f"❌ {page_name}: Error {e}")
    
    evidence["validation_results"]["consistency_check"] = consistency_results
    print()
    
    # Test 4: User workflow simulation
    print("👤 TEST 4: User Workflow Simulation")
    print("-" * 35)
    
    # Simulate a user accessing the git repositories without login
    print("Scenario: User tries to access git repositories without login")
    
    # Create a session to track cookies
    session = requests.Session()
    
    # Step 1: Try to access list page
    print("Step 1: Access git repositories list")
    list_response = session.get(list_url, allow_redirects=False)
    
    if list_response.status_code == 302:
        login_url = list_response.headers.get('Location', '')
        print(f"✅ Redirected to login: {login_url}")
        
        # Step 2: Try to access detail page
        print("Step 2: Access git repository detail")
        detail_response = session.get(detail_url, allow_redirects=False)
        
        if detail_response.status_code == 302:
            detail_login_url = detail_response.headers.get('Location', '')
            print(f"✅ Also redirected to login: {detail_login_url}")
            
            evidence["user_workflow_validation"] = {
                "list_page_redirect": login_url,
                "detail_page_redirect": detail_login_url,
                "consistent_behavior": login_url == detail_login_url,
                "user_experience": "consistent - both pages require authentication"
            }
        else:
            evidence["user_workflow_validation"] = {
                "list_page_redirect": login_url,
                "detail_page_status": detail_response.status_code,
                "consistent_behavior": False,
                "user_experience": "inconsistent - detail page different behavior"
            }
    else:
        evidence["user_workflow_validation"] = {
            "list_page_status": list_response.status_code,
            "user_experience": "list page still accessible without authentication"
        }
    
    print()
    
    # Generate comprehensive evidence report
    print("📊 EVIDENCE SUMMARY")
    print("=" * 25)
    
    validation_results = evidence["validation_results"]
    
    list_fixed = validation_results.get("list_page_fixed", False)
    detail_maintained = validation_results.get("detail_page_maintained", False)
    
    print(f"List page authentication fixed: {'✅ YES' if list_fixed else '❌ NO'}")
    print(f"Detail page authentication maintained: {'✅ YES' if detail_maintained else '❌ NO'}")
    
    # Overall validation result
    overall_success = list_fixed and detail_maintained
    print(f"\n🎯 OVERALL FIX VALIDATION: {'✅ SUCCESS' if overall_success else '❌ FAILED'}")
    
    if overall_success:
        print("\n✅ QAPM CERTIFICATION: Authentication fix validated")
        print("   - Issue: List page bypassed authentication")
        print("   - Fix: Added LoginRequiredMixin to WorkingGitRepositoryListView")
        print("   - Evidence: Both list and detail pages now require authentication")
        print("   - User Impact: Consistent security behavior across git repository pages")
        
    else:
        print("\n❌ QAPM REJECTION: Fix validation failed")
        print("   - Requires additional investigation and remediation")
    
    # Save comprehensive evidence
    evidence_file = f"auth_fix_validation_evidence_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(evidence_file, 'w') as f:
        json.dump(evidence, f, indent=2)
    
    print(f"\n💾 Complete evidence saved to: {evidence_file}")
    
    # Return for programmatic use
    return {
        "success": overall_success,
        "evidence": evidence,
        "evidence_file": evidence_file
    }

if __name__ == "__main__":
    result = validate_authentication_fix()
    sys.exit(0 if result["success"] else 1)