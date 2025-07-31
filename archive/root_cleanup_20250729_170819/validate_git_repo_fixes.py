#!/usr/bin/env python3
"""
Enhanced QAPM v2.1 - Comprehensive Validation of Git Repository Fixes
1. CSS Label Fix: Added text-white/text-dark classes to badges
2. Detail Page Fix: Removed shell syntax error in template
"""

import requests
import json
from datetime import datetime

def validate_fixes():
    """Comprehensive validation of both git repository fixes"""
    
    base_url = "http://localhost:8000"
    session = requests.Session()
    
    evidence = {
        "timestamp": datetime.now().isoformat(),
        "agent": "Enhanced QAPM v2.1",
        "fixes_applied": {
            "css_labels": "Added text-white/text-dark classes to badge elements",
            "detail_page": "Fixed template syntax error (removed '< /dev/null')"
        },
        "validation_results": {},
        "evidence_collected": []
    }
    
    print("🔍 Enhanced QAPM v2.1 - Git Repository Fixes Validation")
    print("=" * 60)
    
    # First authenticate
    print("\n🔐 Authenticating...")
    login_url = f"{base_url}/login/"
    
    # Get CSRF token
    login_page = session.get(login_url)
    csrf_token = None
    
    if 'csrfmiddlewaretoken' in login_page.text:
        # Extract CSRF token from form
        import re
        match = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', login_page.text)
        if match:
            csrf_token = match.group(1)
            print("✅ CSRF token obtained")
    
    # Login
    login_data = {
        'username': 'admin',
        'password': 'admin',
        'csrfmiddlewaretoken': csrf_token,
        'next': '/'
    }
    
    login_response = session.post(login_url, data=login_data, headers={
        'Referer': login_url
    }, allow_redirects=False)
    
    if login_response.status_code == 302:
        print("✅ Authentication successful")
        evidence["validation_results"]["authentication"] = "success"
    else:
        print("❌ Authentication failed")
        evidence["validation_results"]["authentication"] = "failed"
    
    # Test 1: Git Repository List Page (CSS Fix)
    print("\n📋 TEST 1: Git Repository List Page - CSS Label Fix")
    print("-" * 50)
    
    list_url = f"{base_url}/plugins/hedgehog/git-repositories/"
    list_response = session.get(list_url)
    
    evidence["validation_results"]["list_page"] = {
        "url": list_url,
        "status_code": list_response.status_code
    }
    
    if list_response.status_code == 200:
        print(f"✅ List page loaded successfully")
        
        # Check for CSS classes in the response
        if 'badge bg-success text-white' in list_response.text:
            print("✅ CSS FIX VALIDATED: text-white class present on success badges")
            evidence["validation_results"]["css_fix_success"] = True
            evidence["evidence_collected"].append({
                "type": "css_fix",
                "location": "list_page",
                "evidence": "badge bg-success text-white found in HTML"
            })
        else:
            print("❌ CSS FIX NOT FOUND: text-white class missing")
            evidence["validation_results"]["css_fix_success"] = False
        
        # Save the page for manual inspection
        with open('git_repos_list_validated.html', 'w') as f:
            f.write(list_response.text)
        print("💾 Saved list page to git_repos_list_validated.html")
        
    else:
        print(f"❌ List page failed to load: {list_response.status_code}")
    
    # Test 2: Git Repository Detail Page (Template Fix)
    print("\n📄 TEST 2: Git Repository Detail Page - Template Error Fix")
    print("-" * 50)
    
    # Try to access detail page for repository ID 1
    detail_url = f"{base_url}/plugins/hedgehog/git-repositories/1/"
    detail_response = session.get(detail_url)
    
    evidence["validation_results"]["detail_page"] = {
        "url": detail_url,
        "status_code": detail_response.status_code
    }
    
    if detail_response.status_code == 200:
        print(f"✅ Detail page loaded successfully (FIXED!)")
        evidence["validation_results"]["detail_page_fixed"] = True
        
        # Check that the error is gone
        if '< /dev/null' not in detail_response.text:
            print("✅ TEMPLATE FIX VALIDATED: Shell syntax error removed")
            evidence["evidence_collected"].append({
                "type": "template_fix",
                "location": "detail_page",
                "evidence": "No shell syntax found in template"
            })
        else:
            print("❌ Template still contains shell syntax error")
            evidence["validation_results"]["detail_page_fixed"] = False
        
        # Check CSS fix is also applied here
        if 'badge bg-success text-white' in detail_response.text:
            print("✅ CSS fix also applied to detail page")
            evidence["evidence_collected"].append({
                "type": "css_consistency",
                "location": "detail_page",
                "evidence": "Consistent CSS classes across pages"
            })
        
        # Save the page
        with open('git_repo_detail_validated.html', 'w') as f:
            f.write(detail_response.text)
        print("💾 Saved detail page to git_repo_detail_validated.html")
        
    elif detail_response.status_code == 500:
        print(f"❌ Detail page still showing error: {detail_response.status_code}")
        evidence["validation_results"]["detail_page_fixed"] = False
        
        # Save error page for debugging
        with open('git_repo_detail_error_persistent.html', 'w') as f:
            f.write(detail_response.text)
            
    elif detail_response.status_code == 404:
        print("❓ Repository ID 1 not found (may need different ID)")
        evidence["validation_results"]["detail_page_fixed"] = "unknown"
    
    # Test 3: User Experience Validation
    print("\n👤 TEST 3: User Experience Validation")
    print("-" * 35)
    
    # Simulate user workflow
    print("Simulating user workflow:")
    print("1. User views git repositories list")
    print("   - Status labels should be readable (white text on green background)")
    
    if evidence["validation_results"].get("css_fix_success"):
        print("   ✅ VALIDATED: Labels are readable")
    else:
        print("   ❌ FAILED: Labels may be unreadable")
    
    print("2. User clicks on repository name to view details")
    print("   - Detail page should load without errors")
    
    if evidence["validation_results"].get("detail_page_fixed"):
        print("   ✅ VALIDATED: Detail page loads correctly")
    else:
        print("   ❌ FAILED: Detail page has errors")
    
    # Generate comprehensive report
    print("\n📊 VALIDATION SUMMARY")
    print("=" * 50)
    
    css_fixed = evidence["validation_results"].get("css_fix_success", False)
    detail_fixed = evidence["validation_results"].get("detail_page_fixed", False)
    
    print(f"CSS Label Fix: {'✅ VALIDATED' if css_fixed else '❌ NOT VALIDATED'}")
    print(f"Detail Page Fix: {'✅ VALIDATED' if detail_fixed else '❌ NOT VALIDATED'}")
    
    overall_success = css_fixed and detail_fixed
    
    print(f"\n🎯 OVERALL VALIDATION: {'✅ BOTH FIXES WORKING' if overall_success else '❌ FIXES NEED VERIFICATION'}")
    
    if overall_success:
        print("\n✅ QAPM CERTIFICATION: Both fixes validated")
        print("   1. CSS labels now readable with proper text color classes")
        print("   2. Detail page template error fixed, page loads successfully")
        print("   3. User experience restored for git repository management")
    else:
        print("\n❌ QAPM FINDING: Additional work needed")
        if not css_fixed:
            print("   - CSS fix not properly deployed")
        if not detail_fixed:
            print("   - Detail page still has issues")
    
    # Save evidence
    evidence_file = f"git_repo_fixes_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(evidence_file, 'w') as f:
        json.dump(evidence, f, indent=2)
    
    print(f"\n💾 Complete evidence saved to: {evidence_file}")
    
    return evidence

if __name__ == "__main__":
    validate_fixes()