#!/usr/bin/env python3
"""
Quick Verification Script for Issue #40 TDD Tests

This script verifies that the test suite is properly set up and demonstrates
the failing behavior that needs to be fixed.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def verify_test_files():
    """Verify all test files are created and properly structured"""
    print("🔍 Verifying Issue #40 TDD Test Suite")
    print("=" * 50)
    
    test_files = [
        'tests/test_issue40_status_calculation.py',
        'tests/test_issue40_template_rendering.py', 
        'tests/test_issue40_integration.py',
        'tests/test_issue40_performance.py',
        'tests/test_issue40_gui_playwright.py',
        'tests/test_issue40_service_mocks.py',
        'tests/run_issue40_tests.py',
        'tests/ISSUE40_TDD_TEST_SUMMARY.md'
    ]
    
    all_exist = True
    for test_file in test_files:
        file_path = project_root / test_file
        if file_path.exists():
            size = file_path.stat().st_size
            print(f"✅ {test_file:<50} ({size:,} bytes)")
        else:
            print(f"❌ {test_file:<50} MISSING")
            all_exist = False
    
    return all_exist

def demonstrate_issue():
    """Demonstrate the core Issue #40 problem"""
    print(f"\n🎯 Demonstrating Issue #40 Problem")
    print("=" * 50)
    
    try:
        # Try to import the fabric model to show calculated_sync_status
        import os
        import django
        
        # Setup Django
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')
        django.setup()
        
        from netbox_hedgehog.models import HedgehogFabric
        
        # Create example fabrics that demonstrate the issue
        print("\n1. Creating test fabric with no Kubernetes server (not_configured):")
        fabric1 = HedgehogFabric(
            name='demo-not-configured',
            kubernetes_server='',  # Empty = not_configured
            sync_enabled=True
        )
        print(f"   calculated_sync_status: '{fabric1.calculated_sync_status}'")
        print(f"   calculated_sync_status_display: '{fabric1.calculated_sync_status_display}'")
        
        print("\n2. Creating test fabric with sync disabled:")
        fabric2 = HedgehogFabric(
            name='demo-disabled',
            kubernetes_server='https://k8s.example.com',
            sync_enabled=False  # Disabled
        )
        print(f"   calculated_sync_status: '{fabric2.calculated_sync_status}'")
        print(f"   calculated_sync_status_display: '{fabric2.calculated_sync_status_display}'")
        
        print("\n🚨 THE PROBLEM:")
        print("   The status_indicator.html template does NOT handle these statuses:")
        print(f"   - '{fabric1.calculated_sync_status}' (when kubernetes_server is empty)")
        print(f"   - '{fabric2.calculated_sync_status}' (when sync_enabled is False)")
        print()
        print("   Users will see incorrect or missing status displays!")
        
    except ImportError as e:
        print(f"⚠️  Could not import Django models: {e}")
        print("   This is expected if Django is not set up in this environment")
        print("   The core issue remains: template missing status handling")

def show_template_issue():
    """Show the current template and what's missing"""
    print(f"\n📄 Template Analysis")
    print("=" * 50)
    
    template_path = project_root / "netbox_hedgehog/templates/netbox_hedgehog/components/fabric/status_indicator.html"
    
    if template_path.exists():
        print(f"Current template: {template_path}")
        
        with open(template_path, 'r') as f:
            content = f.read()
        
        # Check for missing status handling
        missing_statuses = []
        if 'not_configured' not in content:
            missing_statuses.append('not_configured')
        if 'disabled' not in content and 'sync_enabled' not in content:
            missing_statuses.append('disabled')
        
        if missing_statuses:
            print(f"❌ Template is missing handling for: {', '.join(missing_statuses)}")
            print("   This confirms Issue #40: users cannot see these statuses")
        else:
            print("✅ Template appears to handle the problematic statuses")
            print("   Issue #40 may already be fixed!")
            
    else:
        print(f"⚠️  Template not found: {template_path}")
        print("   Cannot analyze template - may be different path")

def main():
    """Main verification function"""
    print("🧪 Issue #40 TDD Test Suite Verification")
    print("=" * 60)
    print("Verifying comprehensive test suite for sync status display issues")
    print()
    
    # Verify test files
    files_ok = verify_test_files()
    
    if not files_ok:
        print("\n❌ Test suite verification failed - missing files")
        return 1
    
    # Demonstrate the issue
    demonstrate_issue()
    
    # Analyze template
    show_template_issue()
    
    # Final instructions
    print(f"\n🚀 Next Steps")
    print("=" * 50)
    print("1. Run the comprehensive test suite:")
    print("   cd /home/ubuntu/cc/hedgehog-netbox-plugin")
    print("   python tests/run_issue40_tests.py")
    print()
    print("2. Expect FAILURES - this is TDD! Tests should fail first.")
    print()
    print("3. Fix the template based on test failures:")
    print("   - Add 'not_configured' status handling")  
    print("   - Add 'disabled' status handling")
    print("   - Update CSS classes and icons")
    print()
    print("4. Run tests again - they should all pass after fixes!")
    print()
    print("📖 Read tests/ISSUE40_TDD_TEST_SUMMARY.md for detailed guidance")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())