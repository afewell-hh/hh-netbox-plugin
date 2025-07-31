#!/usr/bin/env python3
"""
Validate Fabric Detail Page Fixes
=================================

This script validates that the fabric detail page fixes are working correctly:
1. Purple dashboard-overview bar is removed
2. Git Configuration box overflow is fixed  
3. Dual sync status display is working
"""

import requests
import re
from datetime import datetime

def validate_purple_bar_removal():
    """Test that purple dashboard-overview bar is removed"""
    print("=== Testing Purple Bar Removal ===")
    
    response = requests.get("http://localhost:8000/plugins/hedgehog/fabrics/12/")
    
    if response.status_code != 200:
        print(f"❌ Page not accessible: {response.status_code}")
        return False
    
    html = response.text
    
    # Check for purple dashboard elements
    purple_indicators = [
        'dashboard-overview',
        'hedgehog-dashboard-overview', 
        'hedgehog-status-cards',
        'hedgehog-status-card'
    ]
    
    found_purple = []
    for indicator in purple_indicators:
        if indicator in html:
            found_purple.append(indicator)
    
    if found_purple:
        print(f"❌ Purple bar elements still found: {found_purple}")
        return False
    else:
        print("✅ Purple dashboard-overview bar successfully removed")
        return True

def validate_git_configuration_overflow_fix():
    """Test that Git Configuration text overflow is fixed"""
    print("\n=== Testing Git Configuration Overflow Fix ===")
    
    response = requests.get("http://localhost:8000/plugins/hedgehog/fabrics/12/")
    html = response.text
    
    # Look for text-break class applications
    text_break_patterns = [
        r'<span class="text-break"[^>]*>',
        r'word-break: break-all',
        r'overflow-wrap: break-word'
    ]
    
    found_fixes = []
    for pattern in text_break_patterns:
        if re.search(pattern, html):
            found_fixes.append(pattern)
    
    if len(found_fixes) >= 2:  # Should have text-break class and CSS properties
        print("✅ Git Configuration overflow fixes applied")
        print(f"   Found fixes: {len(found_fixes)}/3")
        return True
    else:
        print(f"❌ Insufficient overflow fixes applied: {found_fixes}")
        return False

def validate_dual_sync_status():
    """Test that dual sync status display is working"""
    print("\n=== Testing Dual Sync Status Display ===")
    
    response = requests.get("http://localhost:8000/plugins/hedgehog/fabrics/12/")
    html = response.text
    
    # Look for dual sync indicators
    sync_patterns = [
        r'Git Repository Sync',
        r'HCKC.*Sync|Kubernetes.*Sync',
        r'mdi-git',
        r'mdi-kubernetes'
    ]
    
    found_sync = []
    for pattern in sync_patterns:
        if re.search(pattern, html):
            found_sync.append(pattern)
    
    if len(found_sync) >= 3:  # Should have both sync types and icons
        print("✅ Dual sync status display working")
        print(f"   Found indicators: {len(found_sync)}/4")
        return True
    else:
        print(f"❌ Dual sync status not properly displayed: {found_sync}")
        return False

def validate_page_functionality():
    """Test that the page loads and renders correctly"""
    print("\n=== Testing Page Functionality ===")
    
    response = requests.get("http://localhost:8000/plugins/hedgehog/fabrics/12/")
    
    if response.status_code != 200:
        print(f"❌ Page not loading: {response.status_code}")
        return False
        
    html = response.text
    
    # Check for basic page elements
    essential_elements = [
        'Fabric Details',
        'Git Configuration', 
        'Fabric Information',
        'test-fabric-gitops-mvp2'  # Fabric name
    ]
    
    missing_elements = []
    for element in essential_elements:
        if element not in html:
            missing_elements.append(element)
    
    if missing_elements:
        print(f"❌ Missing essential elements: {missing_elements}")
        return False
    else:
        print("✅ Page functionality working correctly")
        return True

def main():
    """Run complete validation of fabric page fixes"""
    print("FABRIC DETAIL PAGE FIXES VALIDATION")
    print("=" * 50)
    print(f"Testing fabric page at: {datetime.now()}")
    print("=" * 50)
    
    tests = [
        validate_purple_bar_removal,
        validate_git_configuration_overflow_fix, 
        validate_dual_sync_status,
        validate_page_functionality
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Test failed with error: {e}")
            results.append(False)
    
    print("\n" + "=" * 50)
    print("=== VALIDATION SUMMARY ===")
    
    passed = sum(results)
    total = len(results)
    
    print(f"Tests passed: {passed}/{total}")
    print(f"Success rate: {passed/total*100:.1f}%")
    
    if passed == total:
        print("🎉 ALL FABRIC PAGE FIXES VALIDATED!")
        print("✅ Purple bar removed")
        print("✅ Git Configuration overflow fixed")
        print("✅ Dual sync status working")
        print("✅ Page functionality confirmed")
    else:
        print("❌ Some fixes need attention:")
        test_names = [
            "Purple bar removal",
            "Git Configuration overflow fix",
            "Dual sync status display", 
            "Page functionality"
        ]
        for i, (name, result) in enumerate(zip(test_names, results)):
            status = "✅" if result else "❌"
            print(f"   {status} {name}")
    
    print("=" * 50)
    return passed == total

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)