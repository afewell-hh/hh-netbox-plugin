#!/usr/bin/env python3
"""
Validate Specific Visual Issues
=============================

This validates the two specific issues the user reported:
1. Fabric Kubernetes Server blank value 
2. Git Configuration columns still left-to-right instead of top-to-bottom
"""

import requests
import re

def validate_kubernetes_server_value():
    """Check if Fabric Kubernetes Server shows actual URL, not blank"""
    print("=== Validating Fabric Kubernetes Server Value ===")
    
    response = requests.get("http://localhost:8000/plugins/hedgehog/fabrics/12/")
    if response.status_code != 200:
        print(f"❌ Page not accessible: {response.status_code}")
        return False
    
    html = response.text
    
    # Look for the Kubernetes Server field value
    k8s_server_pattern = r'Fabric Kubernetes Server:.*?<td[^>]*>(.*?)</td>'
    match = re.search(k8s_server_pattern, html, re.DOTALL)
    
    if not match:
        print("❌ Fabric Kubernetes Server field not found")
        return False
    
    value_content = match.group(1).strip()
    clean_value = re.sub(r'<[^>]+>', '', value_content).strip()
    
    print(f"Current value: '{clean_value}'")
    
    # Check if it shows actual URL
    if clean_value == "—":
        print("❌ Still showing blank indicator (—)")
        return False
    elif "127.0.0.1:6443" in clean_value or "https://" in clean_value:
        print("✅ Shows actual Kubernetes server URL")
        return True
    else:
        print(f"⚠️ Shows unexpected value: {clean_value}")
        return False

def validate_git_configuration_layout():
    """Check if Git Configuration is truly displaying top-to-bottom"""
    print("\n=== Validating Git Configuration Layout ===")
    
    response = requests.get("http://localhost:8000/plugins/hedgehog/fabrics/12/")
    html = response.text
    
    # Extract the Git Configuration section
    git_section_pattern = r'Git Repository Connected.*?</div>(?=\s*<h4>Actions|$)'
    git_match = re.search(git_section_pattern, html, re.DOTALL)
    
    if not git_match:
        print("❌ Git Repository Connected section not found")
        return False
    
    git_section = git_match.group(0)
    print("Git Configuration section found")
    
    # Check the structure - should have separate div elements for each field
    field_divs = re.findall(r'<div class="mb-3">(.*?)</div>', git_section, re.DOTALL)
    
    print(f"Found {len(field_divs)} field containers")
    
    # Check if fields appear to be in separate vertical containers
    fields_found = []
    for i, div_content in enumerate(field_divs):
        if 'Repository:' in div_content:
            fields_found.append('Repository')
        elif 'GitOps Directory:' in div_content:
            fields_found.append('GitOps Directory')  
        elif 'URL:' in div_content:
            fields_found.append('URL')
        elif 'Branch:' in div_content:
            fields_found.append('Branch')
    
    print(f"Fields found in separate divs: {fields_found}")
    
    # Check if there are any table structures (which could cause horizontal layout)
    has_table = '<table' in git_section
    has_tr = '<tr' in git_section
    has_td_multiple = git_section.count('<td') > 1
    
    print(f"HTML structure analysis:")
    print(f"  - Contains table: {has_table}")
    print(f"  - Contains table rows: {has_tr}")
    print(f"  - Multiple table cells: {has_td_multiple}")
    
    # The layout should be vertical if:
    # 1. Fields are in separate div containers
    # 2. No table structure causing horizontal layout
    is_vertical = len(fields_found) >= 3 and not (has_table and has_td_multiple)
    
    if is_vertical:
        print("✅ Git Configuration appears to use vertical layout")
        return True
    else:
        print("❌ Git Configuration may still have horizontal layout issues")
        print("   Structure suggests potential horizontal display")
        return False

def check_specific_layout_issues():
    """Check for specific CSS or HTML issues that could cause horizontal display"""
    print("\n=== Checking for Layout Issues ===")
    
    response = requests.get("http://localhost:8000/plugins/hedgehog/fabrics/12/")
    html = response.text
    
    # Look for potential horizontal layout patterns
    horizontal_indicators = [
        r'<p[^>]*>.*Repository.*GitOps Directory',  # Fields in same paragraph
        r'Repository.*GitOps Directory.*(?=URL)',   # Fields on same line
        r'<div[^>]*class="[^"]*row[^"]*".*Repository', # Row class with Repository
        r'<div[^>]*class="[^"]*col-[^"]*".*Repository', # Column class structure
    ]
    
    found_horizontal = []
    for pattern in horizontal_indicators:
        if re.search(pattern, html, re.IGNORECASE):
            found_horizontal.append(pattern)
    
    if found_horizontal:
        print(f"❌ Found potential horizontal layout patterns: {len(found_horizontal)}")
        for pattern in found_horizontal:
            print(f"   - {pattern[:50]}...")
        return False
    else:
        print("✅ No obvious horizontal layout patterns detected")
        return True

def main():
    """Run validation of both specific visual issues"""
    print("VALIDATING SPECIFIC USER-REPORTED VISUAL ISSUES")
    print("=" * 60)
    
    # Test both specific issues
    k8s_server_ok = validate_kubernetes_server_value()
    git_layout_ok = validate_git_configuration_layout()
    layout_issues_ok = check_specific_layout_issues()
    
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    
    if k8s_server_ok:
        print("✅ FIXED: Fabric Kubernetes Server now shows URL instead of blank")
    else:
        print("❌ STILL BROKEN: Fabric Kubernetes Server showing blank value")
    
    if git_layout_ok and layout_issues_ok:
        print("✅ FIXED: Git Configuration appears to use vertical layout")
    else:
        print("❌ STILL BROKEN: Git Configuration may still show horizontal layout")
    
    overall_success = k8s_server_ok and git_layout_ok and layout_issues_ok
    
    if overall_success:
        print("\n🎉 BOTH ISSUES APPEAR TO BE FIXED")
    else:
        print("\n⚠️ ONE OR BOTH ISSUES STILL NEED ATTENTION")
    
    print("=" * 60)
    return overall_success

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)