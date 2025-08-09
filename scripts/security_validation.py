#!/usr/bin/env python3
"""
Security Validation Script for Issue #33
Validates CSRF protection and security implementations in fabric templates and forms
"""

import os
import re
import sys
import json
from pathlib import Path

def find_templates():
    """Find all fabric-related HTML templates"""
    base_path = Path("/home/ubuntu/cc/hedgehog-netbox-plugin")
    templates = []
    
    for template_path in base_path.rglob("*.html"):
        if "fabric" in template_path.name.lower() and "templates" in str(template_path):
            templates.append(template_path)
    
    return templates

def check_csrf_protection(template_path):
    """Check if template has CSRF protection"""
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Check for forms that need CSRF protection
        has_form = bool(re.search(r'<form[^>]*method\s*=\s*["\']post["\']', content, re.IGNORECASE))
        has_csrf = bool(re.search(r'{%\s*csrf_token\s*%}', content))
        
        return {
            'has_form': has_form,
            'has_csrf': has_csrf,
            'needs_csrf': has_form and not has_csrf,
            'content_length': len(content)
        }
    except Exception as e:
        return {'error': str(e)}

def check_form_security(form_path):
    """Check Python form files for security implementations"""
    try:
        with open(form_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        security_features = {
            'has_validation': bool(re.search(r'def clean_', content)),
            'has_sanitization': bool(re.search(r'escape\(', content)),
            'has_permission_checks': bool(re.search(r'PermissionDenied|has_perm', content)),
            'has_input_validation': bool(re.search(r'ValidationError', content)),
            'content_length': len(content)
        }
        
        return security_features
    except Exception as e:
        return {'error': str(e)}

def main():
    """Main security validation function"""
    print("🔒 Security Validation for Issue #33")
    print("=" * 50)
    
    # Check templates
    templates = find_templates()
    template_results = []
    
    print(f"\n📄 Checking {len(templates)} fabric templates...")
    
    for template in templates:
        result = check_csrf_protection(template)
        result['path'] = str(template)
        template_results.append(result)
        
        status = "✅" if not result.get('needs_csrf', True) else "⚠️"
        print(f"{status} {template.name}: CSRF {'OK' if not result.get('needs_csrf', True) else 'MISSING'}")
    
    # Check form files
    form_files = [
        Path("/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/forms/fabric.py"),
        Path("/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/forms/fabric_forms.py"),
        Path("/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/views/fabric.py")
    ]
    
    form_results = []
    print(f"\n🐍 Checking {len(form_files)} Python form/view files...")
    
    for form_file in form_files:
        if form_file.exists():
            result = check_form_security(form_file)
            result['path'] = str(form_file)
            form_results.append(result)
            
            security_score = sum([
                result.get('has_validation', False),
                result.get('has_sanitization', False),
                result.get('has_permission_checks', False),
                result.get('has_input_validation', False)
            ])
            
            status = "✅" if security_score >= 3 else "⚠️" if security_score >= 2 else "❌"
            print(f"{status} {form_file.name}: Security Score {security_score}/4")
    
    # Generate summary
    csrf_issues = sum(1 for r in template_results if r.get('needs_csrf', False))
    security_issues = sum(1 for r in form_results if sum([
        r.get('has_validation', False),
        r.get('has_sanitization', False), 
        r.get('has_permission_checks', False),
        r.get('has_input_validation', False)
    ]) < 3)
    
    print(f"\n📊 Security Summary:")
    print(f"   Templates checked: {len(templates)}")
    print(f"   CSRF issues found: {csrf_issues}")
    print(f"   Python files checked: {len(form_results)}")
    print(f"   Security issues found: {security_issues}")
    
    # Save detailed results
    results = {
        'timestamp': '2025-08-09',
        'issue': '#33',
        'templates': template_results,
        'forms': form_results,
        'summary': {
            'templates_total': len(templates),
            'csrf_issues': csrf_issues,
            'forms_total': len(form_results),
            'security_issues': security_issues,
            'overall_status': 'PASS' if csrf_issues == 0 and security_issues == 0 else 'NEEDS_ATTENTION'
        }
    }
    
    output_file = Path("/home/ubuntu/cc/hedgehog-netbox-plugin/docs/security_validation_results.json")
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n💾 Detailed results saved to: {output_file}")
    
    # Return appropriate exit code
    if csrf_issues == 0 and security_issues == 0:
        print("\n🎉 All security checks PASSED!")
        return 0
    else:
        print(f"\n⚠️  Security validation completed with {csrf_issues + security_issues} issues")
        return 1

if __name__ == "__main__":
    sys.exit(main())