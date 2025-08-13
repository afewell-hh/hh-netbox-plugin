#!/usr/bin/env python3
"""
CSRF Authentication Fix Verification Report
Validates all implemented fixes for the sync button CSRF authentication issue.
"""

import json
from datetime import datetime

def verify_csrf_authentication_fix():
    """Verify all CSRF authentication fixes are in place"""
    
    verification_results = {
        'timestamp': datetime.now().isoformat(),
        'fix_verification': {
            'view_decorator_fix': False,
            'csrf_template_meta_tag': False,
            'javascript_csrf_headers': False,
            'url_routing_correction': False
        },
        'fixes_applied': [],
        'remaining_issues': [],
        'authentication_status': 'UNKNOWN'
    }
    
    print("🔍 CSRF Authentication Fix Verification")
    print("=" * 50)
    
    # 1. Verify FabricSyncView has login_required decorator
    try:
        with open('netbox_hedgehog/views/fabric_views.py', 'r') as f:
            fabric_views_content = f.read()
        
        if '@method_decorator(login_required, name=\'dispatch\')\nclass FabricSyncView(View):' in fabric_views_content:
            verification_results['fix_verification']['view_decorator_fix'] = True
            verification_results['fixes_applied'].append("✅ FabricSyncView now has @method_decorator(login_required) decorator")
            print("✅ FabricSyncView authentication decorator: FIXED")
        else:
            verification_results['remaining_issues'].append("❌ FabricSyncView missing login_required decorator")
            print("❌ FabricSyncView authentication decorator: MISSING")
    except Exception as e:
        verification_results['remaining_issues'].append(f"Error checking view decorator: {e}")
        print(f"❌ Error checking view decorator: {e}")
    
    # 2. Verify CSRF meta tag in template
    try:
        with open('netbox_hedgehog/templates/netbox_hedgehog/fabric_detail_simple.html', 'r') as f:
            template_content = f.read()
        
        if 'name="csrf-token" content="{{ csrf_token }}"' in template_content:
            verification_results['fix_verification']['csrf_template_meta_tag'] = True
            verification_results['fixes_applied'].append("✅ Template includes CSRF meta tag for JavaScript access")
            print("✅ CSRF template meta tag: ADDED")
        else:
            verification_results['remaining_issues'].append("❌ Template missing CSRF meta tag")
            print("❌ CSRF template meta tag: MISSING")
    except Exception as e:
        verification_results['remaining_issues'].append(f"Error checking template: {e}")
        print(f"❌ Error checking template: {e}")
    
    # 3. Verify JavaScript includes CSRF headers
    try:
        csrf_header_count = template_content.count("'X-CSRFToken': csrftoken")
        if csrf_header_count >= 3:  # Should have multiple sync functions
            verification_results['fix_verification']['javascript_csrf_headers'] = True
            verification_results['fixes_applied'].append(f"✅ JavaScript includes CSRF token in headers ({csrf_header_count} instances)")
            print(f"✅ JavaScript CSRF headers: INCLUDED ({csrf_header_count} instances)")
        else:
            verification_results['remaining_issues'].append(f"❌ JavaScript CSRF headers incomplete ({csrf_header_count} instances)")
            print(f"❌ JavaScript CSRF headers: INCOMPLETE ({csrf_header_count} instances)")
    except Exception as e:
        verification_results['remaining_issues'].append(f"Error checking JavaScript CSRF headers: {e}")
        print(f"❌ Error checking JavaScript CSRF headers: {e}")
    
    # 4. Verify JavaScript URLs match Django URL routing
    try:
        github_sync_url_correct = '/plugins/hedgehog/fabrics/${fabricId}/github-sync/' in template_content
        fabric_sync_url_correct = '/plugins/hedgehog/fabrics/${fabricId}/sync/' in template_content
        
        if github_sync_url_correct and fabric_sync_url_correct:
            verification_results['fix_verification']['url_routing_correction'] = True
            verification_results['fixes_applied'].append("✅ JavaScript URLs corrected to match Django URL routing")
            print("✅ JavaScript URL routing: CORRECTED")
        else:
            issues = []
            if not github_sync_url_correct:
                issues.append("github-sync URL")
            if not fabric_sync_url_correct:
                issues.append("fabric sync URL")
            verification_results['remaining_issues'].append(f"❌ JavaScript URL routing incorrect: {', '.join(issues)}")
            print(f"❌ JavaScript URL routing: INCORRECT ({', '.join(issues)})")
    except Exception as e:
        verification_results['remaining_issues'].append(f"Error checking URL routing: {e}")
        print(f"❌ Error checking URL routing: {e}")
    
    # 5. Overall assessment
    fixes_count = sum(verification_results['fix_verification'].values())
    total_fixes = len(verification_results['fix_verification'])
    
    if fixes_count == total_fixes:
        verification_results['authentication_status'] = 'FIXED'
        print(f"\n🎉 CSRF AUTHENTICATION FIX COMPLETE ({fixes_count}/{total_fixes})")
        print("   HTTP 403 errors should be resolved for sync buttons")
    elif fixes_count > 0:
        verification_results['authentication_status'] = 'PARTIAL'
        print(f"\n⚠️ CSRF AUTHENTICATION PARTIALLY FIXED ({fixes_count}/{total_fixes})")
        print("   Some issues may remain")
    else:
        verification_results['authentication_status'] = 'FAILED'
        print(f"\n❌ CSRF AUTHENTICATION FIX FAILED ({fixes_count}/{total_fixes})")
        print("   HTTP 403 errors likely to persist")
    
    # 6. Summary
    print("\n" + "=" * 50)
    print("📋 SUMMARY OF CHANGES")
    print("=" * 50)
    
    if verification_results['fixes_applied']:
        print("✅ Fixes Applied:")
        for fix in verification_results['fixes_applied']:
            print(f"   {fix}")
    
    if verification_results['remaining_issues']:
        print("\n❌ Remaining Issues:")
        for issue in verification_results['remaining_issues']:
            print(f"   {issue}")
    
    # 7. Next steps
    print("\n📋 NEXT STEPS")
    print("=" * 50)
    if verification_results['authentication_status'] == 'FIXED':
        print("1. Test sync button in NetBox UI")
        print("2. Verify HTTP 403 errors are resolved")
        print("3. Confirm sync operations reach GitOps processing")
        print("4. Monitor for any remaining authentication issues")
    else:
        print("1. Address remaining issues identified above")
        print("2. Re-run verification after fixes")
        print("3. Test with actual sync button operations")
    
    # Save report
    report_file = f'csrf_fix_verification_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    with open(report_file, 'w') as f:
        json.dump(verification_results, f, indent=2)
    
    print(f"\n📄 Detailed report saved to: {report_file}")
    
    return verification_results['authentication_status'] == 'FIXED'

if __name__ == '__main__':
    success = verify_csrf_authentication_fix()
    exit(0 if success else 1)