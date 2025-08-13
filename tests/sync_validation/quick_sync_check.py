#!/usr/bin/env python3
"""
Quick Sync Check
Fast diagnostic script to check the basic sync functionality without full testing.
"""

import os
import sys
import requests
import json
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

def quick_check(fabric_id=35, base_url="http://localhost:8000"):
    """Perform quick checks on sync functionality"""
    
    print("⚡ Quick Sync Functionality Check")
    print("=" * 40)
    print(f"Fabric ID: {fabric_id}")
    print(f"Base URL: {base_url}")
    print()
    
    results = {
        'timestamp': datetime.now().isoformat(),
        'fabric_id': fabric_id,
        'checks': {}
    }
    
    session = requests.Session()
    
    # Check 1: NetBox availability
    try:
        response = session.get(f"{base_url}/", timeout=5)
        netbox_available = response.status_code == 200
        print(f"✅ NetBox Available: {response.status_code}" if netbox_available else f"❌ NetBox Unavailable: {response.status_code}")
        results['checks']['netbox_available'] = netbox_available
    except Exception as e:
        print(f"❌ NetBox Unavailable: {e}")
        results['checks']['netbox_available'] = False
        return results
    
    # Check 2: Fabric page accessibility
    try:
        fabric_url = f"{base_url}/plugins/hedgehog/fabrics/{fabric_id}/"
        response = session.get(fabric_url, timeout=10)
        
        fabric_accessible = response.status_code == 200
        has_login_redirect = 'login' in response.url.lower()
        has_sync_content = 'sync' in response.text.lower()
        
        if fabric_accessible and not has_login_redirect:
            print(f"✅ Fabric Page Accessible: {response.status_code}")
            print(f"   Has sync content: {'Yes' if has_sync_content else 'No'}")
        elif has_login_redirect:
            print(f"⚠️  Fabric Page Redirects to Login: {response.url}")
        else:
            print(f"❌ Fabric Page Inaccessible: {response.status_code}")
        
        results['checks']['fabric_accessible'] = fabric_accessible and not has_login_redirect
        results['checks']['has_login_redirect'] = has_login_redirect
        results['checks']['has_sync_content'] = has_sync_content
        
    except Exception as e:
        print(f"❌ Fabric Page Error: {e}")
        results['checks']['fabric_accessible'] = False
        return results
    
    # Check 3: Sync endpoint response (without authentication)
    try:
        sync_url = f"{base_url}/plugins/hedgehog/fabrics/{fabric_id}/sync/"
        headers = {'X-Requested-With': 'XMLHttpRequest'}
        
        response = session.post(sync_url, headers=headers, timeout=10)
        
        is_redirect = response.status_code in [301, 302, 303, 307, 308]
        redirect_to_login = is_redirect and 'login' in response.headers.get('Location', '').lower()
        is_auth_error = response.status_code in [401, 403]
        is_success = response.status_code == 200
        
        if redirect_to_login:
            print(f"⚠️  Sync Endpoint Redirects to Login: {response.headers.get('Location', 'Unknown')}")
        elif is_auth_error:
            print(f"⚠️  Sync Endpoint Authentication Error: {response.status_code}")
        elif is_success:
            print(f"✅ Sync Endpoint Responds: {response.status_code}")
        else:
            print(f"❓ Sync Endpoint Unexpected Response: {response.status_code}")
        
        results['checks']['sync_endpoint_accessible'] = not redirect_to_login
        results['checks']['sync_requires_auth'] = redirect_to_login or is_auth_error
        results['checks']['sync_response_code'] = response.status_code
        
    except Exception as e:
        print(f"❌ Sync Endpoint Error: {e}")
        results['checks']['sync_endpoint_accessible'] = False
    
    # Check 4: Django setup (if possible)
    try:
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')
        import django
        django.setup()
        
        from netbox_hedgehog.models import HedgehogFabric
        
        fabric = HedgehogFabric.objects.get(pk=fabric_id)
        print(f"✅ Django Access: Fabric '{fabric.name}' found")
        print(f"   Sync Status: {fabric.sync_status}")
        print(f"   Connection Status: {getattr(fabric, 'connection_status', 'Unknown')}")
        
        results['checks']['django_accessible'] = True
        results['checks']['fabric_exists'] = True
        results['checks']['fabric_name'] = fabric.name
        results['checks']['fabric_sync_status'] = fabric.sync_status
        results['checks']['fabric_connection_status'] = getattr(fabric, 'connection_status', 'Unknown')
        
    except Exception as e:
        print(f"⚠️  Django Access Limited: {e}")
        results['checks']['django_accessible'] = False
    
    # Summary
    print("\n" + "=" * 40)
    print("📊 QUICK CHECK SUMMARY")
    
    issues = []
    if not results['checks'].get('netbox_available'):
        issues.append("NetBox not available")
    if not results['checks'].get('fabric_accessible'):
        issues.append("Fabric page not accessible")
    if results['checks'].get('has_login_redirect'):
        issues.append("Unexpected login redirect")
    if not results['checks'].get('sync_endpoint_accessible'):
        issues.append("Sync endpoint has issues")
    
    if not issues:
        print("✅ All basic checks passed")
        print("💡 Run full validation for detailed testing")
    else:
        print(f"⚠️  Issues found: {len(issues)}")
        for issue in issues:
            print(f"   • {issue}")
        print("💡 Run full validation for detailed diagnosis")
    
    # Save quick results
    results_file = Path(__file__).parent / f"quick_check_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n💾 Results saved to: {results_file}")
    
    return results

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Quick Sync Functionality Check')
    parser.add_argument('--fabric-id', type=int, default=35, help='Fabric ID to test')
    parser.add_argument('--base-url', default='http://localhost:8000', help='Base URL')
    
    args = parser.parse_args()
    
    results = quick_check(fabric_id=args.fabric_id, base_url=args.base_url)
    
    # Exit with error code if issues found
    issues_count = sum(1 for check, result in results['checks'].items() 
                      if check.endswith('_accessible') and not result)
    
    sys.exit(issues_count)