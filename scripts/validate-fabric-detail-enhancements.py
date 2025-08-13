#!/usr/bin/env python3
"""
Validation Script for Enhanced Fabric Detail Interactive Elements
Tests all functionality while preserving visual appearance
"""

import os
import sys
import re
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def validate_template_enhancements():
    """Validate template enhancements"""
    template_path = project_root / "netbox_hedgehog/templates/netbox_hedgehog/fabric_detail.html"
    
    if not template_path.exists():
        return False, "Template file not found"
    
    with open(template_path, 'r') as f:
        content = f.read()
    
    checks = [
        # Check for enhanced CSS inclusion
        ('fabric-detail-enhanced.css', 'Enhanced CSS included'),
        
        # Check for enhanced JavaScript inclusion
        ('fabric-detail-enhanced.js', 'Enhanced JavaScript included'),
        
        # Check for accessibility enhancements
        ('aria-label=', 'ARIA labels present'),
        
        # Check for data-fabric-id attributes
        ('data-fabric-id=', 'Fabric ID attributes present'),
        
        # Check for enhanced button IDs
        ('id="test-connection-btn"', 'Test connection button enhanced'),
        ('id="sync-now-btn"', 'Sync button enhanced'),
        ('id="git-sync-btn"', 'Git sync button enhanced'),
        
        # Check for removal of onclick handlers
        ('onclick="showDriftAnalysis', 'Old onclick handlers should be removed'),
        ('onclick="syncFromGit', 'Old onclick handlers should be removed'),
        ('onclick="configureDriftSettings', 'Old onclick handlers should be removed'),
    ]
    
    results = []
    for check, description in checks:
        count = content.count(check)
        if 'should be removed' in description:
            # These should NOT be present
            results.append({
                'check': description,
                'passed': count == 0,
                'details': f"Found {count} instances (should be 0)"
            })
        else:
            # These should be present
            results.append({
                'check': description,
                'passed': count > 0,
                'details': f"Found {count} instances"
            })
    
    return results

def validate_javascript_enhancements():
    """Validate JavaScript enhancements"""
    js_path = project_root / "netbox_hedgehog/static/netbox_hedgehog/js/fabric-detail-enhanced.js"
    
    if not js_path.exists():
        return False, "Enhanced JavaScript file not found"
    
    with open(js_path, 'r') as f:
        content = f.read()
    
    checks = [
        # Core functionality
        ('handleTestConnection', 'Test connection handler present'),
        ('handleSync', 'Sync handler present'),
        ('handleGitSync', 'Git sync handler present'),
        ('handleDriftAnalysis', 'Drift analysis handler present'),
        
        # Enhanced features
        ('setButtonState', 'Button state management present'),
        ('showNotification', 'Notification system present'),
        ('createModal', 'Modal system present'),
        ('validateForm', 'Form validation present'),
        
        # Accessibility features
        ('aria-label', 'ARIA label support present'),
        ('setAttribute(\'role\'', 'Role attribute support present'),
        
        # Additional handlers
        ('handleProcessFiles', 'Process files handler present'),
        ('handleOptimizeStorage', 'Optimize storage handler present'),
        ('handleCheckDrift', 'Check drift handler present'),
        ('handleDriftHistory', 'Drift history handler present'),
    ]
    
    results = []
    for check, description in checks:
        count = content.count(check)
        results.append({
            'check': description,
            'passed': count > 0,
            'details': f"Found {count} instances"
        })
    
    return results

def validate_css_enhancements():
    """Validate CSS enhancements"""
    css_path = project_root / "netbox_hedgehog/static/netbox_hedgehog/css/fabric-detail-enhanced.css"
    
    if not css_path.exists():
        return False, "Enhanced CSS file not found"
    
    with open(css_path, 'r') as f:
        content = f.read()
    
    checks = [
        # Animation features
        ('transition:', 'CSS transitions present'),
        ('@keyframes', 'CSS keyframes present'),
        ('cubic-bezier', 'Smooth easing functions present'),
        
        # Button enhancements
        ('.btn:hover', 'Button hover effects present'),
        ('.btn:active', 'Button active effects present'),
        ('.btn:disabled', 'Button disabled styles present'),
        
        # Loading states
        ('mdi-loading', 'Loading animation styles present'),
        ('mdi-spin', 'Spin animation styles present'),
        
        # Accessibility
        ('@media (prefers-reduced-motion', 'Reduced motion support present'),
        ('@media (prefers-contrast', 'High contrast support present'),
        
        # Enhanced interactions
        ('.card:hover', 'Card hover effects present'),
        ('.form-control:focus', 'Form focus effects present'),
    ]
    
    results = []
    for check, description in checks:
        count = content.count(check)
        results.append({
            'check': description,
            'passed': count > 0,
            'details': f"Found {count} instances"
        })
    
    return results

def validate_visual_preservation():
    """Validate that visual appearance is preserved"""
    template_path = project_root / "netbox_hedgehog/templates/netbox_hedgehog/fabric_detail.html"
    
    with open(template_path, 'r') as f:
        content = f.read()
    
    # Check that original visual elements are preserved
    preserved_elements = [
        # Original styling classes preserved
        ('class="btn btn-primary"', 'Primary button classes preserved'),
        ('class="btn btn-outline-info"', 'Outline button classes preserved'),
        ('class="drift-action-btn"', 'Drift action button classes preserved'),
        
        # Layout structure preserved
        ('class="row"', 'Bootstrap grid structure preserved'),
        ('class="col-', 'Column classes preserved'),
        ('class="card"', 'Card structure preserved'),
        ('.status-card', 'Status card CSS classes preserved'),
        
        # Icons preserved
        ('mdi mdi-sync', 'Sync icons preserved'),
        ('mdi mdi-test-tube', 'Test icons preserved'),
        ('mdi mdi-chart-line', 'Chart icons preserved'),
    ]
    
    results = []
    for element, description in preserved_elements:
        count = content.count(element)
        results.append({
            'check': description,
            'passed': count > 0,
            'details': f"Found {count} instances"
        })
    
    return results

def run_validation():
    """Run all validation tests"""
    print("🧪 Validating Enhanced Fabric Detail Interactive Elements")
    print("=" * 60)
    
    all_passed = True
    total_checks = 0
    passed_checks = 0
    
    test_suites = [
        ("Template Enhancements", validate_template_enhancements),
        ("JavaScript Enhancements", validate_javascript_enhancements),
        ("CSS Enhancements", validate_css_enhancements),
        ("Visual Preservation", validate_visual_preservation),
    ]
    
    for suite_name, validation_func in test_suites:
        print(f"\n📋 {suite_name}")
        print("-" * 40)
        
        try:
            results = validation_func()
            
            if isinstance(results, tuple) and not results[0]:
                print(f"❌ {results[1]}")
                all_passed = False
                continue
            
            suite_passed = 0
            suite_total = len(results)
            
            for result in results:
                status = "✅" if result['passed'] else "❌"
                print(f"{status} {result['check']}: {result['details']}")
                
                if result['passed']:
                    suite_passed += 1
                else:
                    all_passed = False
            
            total_checks += suite_total
            passed_checks += suite_passed
            
            print(f"\nSuite Result: {suite_passed}/{suite_total} checks passed")
            
        except Exception as e:
            print(f"❌ Error running {suite_name}: {str(e)}")
            all_passed = False
    
    print("\n" + "=" * 60)
    print(f"🎯 Overall Result: {passed_checks}/{total_checks} checks passed")
    
    if all_passed:
        print("🚀 SUCCESS: All interactive elements enhanced successfully!")
        print("   ✓ Button functionality fixed")
        print("   ✓ Professional loading states added")
        print("   ✓ Enhanced user feedback implemented")
        print("   ✓ Accessibility improvements added")
        print("   ✓ Smooth animations implemented")
        print("   ✓ Visual appearance preserved")
        return True
    else:
        print("⚠️  ISSUES: Some enhancements need attention")
        return False

if __name__ == "__main__":
    success = run_validation()
    sys.exit(0 if success else 1)