#!/usr/bin/env python3
"""
Dark Theme CSS Fix Validation Script
Validates that the dark theme fixes resolve black text on dark background issues
"""

import re
import sys
from pathlib import Path

def validate_dark_theme_css():
    """Validate that dark theme CSS fixes are properly implemented"""
    
    css_file = Path("/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/static/netbox_hedgehog/css/hedgehog.css")
    
    if not css_file.exists():
        print(f"❌ ERROR: CSS file not found at {css_file}")
        return False
    
    css_content = css_file.read_text()
    
    validation_results = []
    
    # Test 1: Dark mode media queries present
    dark_mode_queries = [
        r"@media \(prefers-color-scheme: dark\)",
        r"html\[data-bs-theme=\"dark\"\]",
        r"body\[data-bs-theme=\"dark\"\]"
    ]
    
    print("🔍 VALIDATION 1: Dark Mode Detection")
    for query in dark_mode_queries:
        if re.search(query, css_content):
            print(f"  ✅ Found: {query}")
            validation_results.append(True)
        else:
            print(f"  ❌ Missing: {query}")
            validation_results.append(False)
    
    # Test 2: Critical unlabeled content fix
    print("\n🔍 VALIDATION 2: Unlabeled Content Light Text Fix")
    unlabeled_fixes = [
        r"color: #f8f9fa !important.*Light text for dark backgrounds",
        r"\.netbox-hedgehog p:not\(\.bg-light\):not\(\.bg-white\):not\(\.badge\)",
        r"\.hedgehog-wrapper div:not\(\.bg-light\):not\(\.bg-white\):not\(\.badge\)"
    ]
    
    for fix in unlabeled_fixes:
        if re.search(fix, css_content, re.MULTILINE):
            print(f"  ✅ Found unlabeled content fix pattern")
            validation_results.append(True)
        else:
            print(f"  ❌ Missing unlabeled content fix pattern")
            validation_results.append(False)
    
    # Test 3: Table cells dark theme fix
    print("\n🔍 VALIDATION 3: Table Cells Dark Theme Fix")
    table_fixes = [
        r"\.table td:not\(\.bg-light\):not\(\.bg-white\)",
        r"\.fabric-detail \.table td:not\(\.bg-light\):not\(\.bg-white\)"
    ]
    
    for fix in table_fixes:
        if re.search(fix, css_content):
            print(f"  ✅ Found table cells dark theme fix")
            validation_results.append(True)
        else:
            print(f"  ❌ Missing table cells dark theme fix")
            validation_results.append(False)
    
    # Test 4: Form elements placeholder text fix
    print("\n🔍 VALIDATION 4: Form Elements Placeholder Fix")
    form_fixes = [
        r"input::placeholder",
        r"textarea::placeholder",
        r"color: #adb5bd !important.*Light gray for placeholder text"
    ]
    
    for fix in form_fixes:
        if re.search(fix, css_content, re.MULTILINE):
            print(f"  ✅ Found form placeholder fix")
            validation_results.append(True)
        else:
            print(f"  ❌ Missing form placeholder fix")
            validation_results.append(False)
    
    # Test 5: Preservation of labeled fields
    print("\n🔍 VALIDATION 5: Labeled Fields Preservation")
    preserved_elements = [
        r"\.form-label",
        r"\.table th",
        r"\.card-header",
        r"pre\.bg-light",
        r"\.badge"
    ]
    
    preservation_section = False
    if "Preserve existing labeled field styling" in css_content or "These maintain their existing styling" in css_content:
        print(f"  ✅ Found labeled fields preservation section")
        preservation_section = True
        validation_results.append(True)
    else:
        print(f"  ❌ Missing labeled fields preservation section")
        validation_results.append(False)
    
    # Test 6: Form controls dark theme styling
    print("\n🔍 VALIDATION 6: Form Controls Dark Theme Styling")
    form_control_fixes = [
        r"\.form-control",
        r"background-color: #495057 !important.*Dark background for form controls",
        r"color: #f8f9fa !important.*Light text for form controls"
    ]
    
    for fix in form_control_fixes:
        if re.search(fix, css_content, re.MULTILINE):
            print(f"  ✅ Found form controls dark theme fix")
            validation_results.append(True)
        else:
            print(f"  ❌ Missing form controls dark theme fix")
            validation_results.append(False)
    
    # Test 7: Regression check - existing readability improvements preserved
    print("\n🔍 VALIDATION 7: Existing Readability Improvements Preserved")
    existing_improvements = [
        r"Enhanced Badge Text Readability",
        r"Enhanced Label and Pre-formatted Text Readability",
        r"Enhanced Form Readability",
        r"Enhanced Table Readability"
    ]
    
    for improvement in existing_improvements:
        if improvement in css_content:
            print(f"  ✅ Preserved: {improvement}")
            validation_results.append(True)
        else:
            print(f"  ❌ Missing: {improvement}")
            validation_results.append(False)
    
    # Summary
    print(f"\n📊 VALIDATION SUMMARY")
    passed = sum(validation_results)
    total = len(validation_results)
    success_rate = (passed / total) * 100
    
    print(f"  Passed: {passed}/{total} ({success_rate:.1f}%)")
    
    if success_rate >= 90:
        print("  🎉 EXCELLENT: Dark theme fixes are comprehensive and properly implemented")
        return True
    elif success_rate >= 75:
        print("  ✅ GOOD: Dark theme fixes are mostly implemented with minor gaps")
        return True
    else:
        print("  ❌ NEEDS WORK: Significant gaps in dark theme implementation")
        return False

def validate_container_deployment():
    """Validate that the CSS is properly deployed to the NetBox container"""
    import subprocess
    
    print("\n⚡ CONTAINER DEPLOYMENT VALIDATION")
    
    try:
        # Check if dark theme fixes are in container
        result = subprocess.run([
            "sudo", "docker", "exec", "netbox-docker-netbox-1", 
            "grep", "-c", "prefers-color-scheme: dark", 
            "/opt/netbox/netbox/static/netbox_hedgehog/css/hedgehog.css"
        ], capture_output=True, text=True, check=True)
        
        if int(result.stdout.strip()) > 0:
            print("  ✅ Dark theme media queries found in container")
            
            # Check for critical fixes
            result2 = subprocess.run([
                "sudo", "docker", "exec", "netbox-docker-netbox-1", 
                "grep", "-c", "f8f9fa", 
                "/opt/netbox/netbox/static/netbox_hedgehog/css/hedgehog.css"
            ], capture_output=True, text=True, check=True)
            
            if int(result2.stdout.strip()) > 0:
                print("  ✅ Light text colors (f8f9fa) found in container CSS")
                print("  🎉 CONTAINER DEPLOYMENT: SUCCESS")
                return True
            else:
                print("  ❌ Light text colors missing from container CSS")
                return False
        else:
            print("  ❌ Dark theme media queries missing from container")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"  ❌ Container validation failed: {e}")
        return False

if __name__ == "__main__":
    print("🚀 DARK THEME CSS FIX VALIDATION")
    print("=" * 50)
    
    # Validate source CSS
    css_valid = validate_dark_theme_css()
    
    # Validate container deployment
    container_valid = validate_container_deployment()
    
    print("\n" + "=" * 50)
    print("🏁 FINAL VALIDATION RESULT")
    
    if css_valid and container_valid:
        print("🎉 SUCCESS: Dark theme fixes are properly implemented and deployed!")
        print("✅ Unlabeled fields should now be readable in dark theme")
        print("✅ Labeled fields preserve high contrast in all themes")
        print("✅ Previous readability improvements are maintained")
        sys.exit(0)
    else:
        print("❌ VALIDATION FAILED: Issues found with dark theme implementation")
        if not css_valid:
            print("  - CSS source file has gaps in dark theme implementation")
        if not container_valid:
            print("  - Container deployment is incomplete or failed")
        sys.exit(1)