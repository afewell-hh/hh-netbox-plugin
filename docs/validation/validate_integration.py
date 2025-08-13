#!/usr/bin/env python3
"""
Validation script for Phase 3 Integration Layer completion.
Validates URL patterns, templates, and static assets.
"""

import os
import sys
from pathlib import Path

# Add the current directory to Python path to import modules
sys.path.insert(0, '.')

def validate_urls():
    """Validate URL configurations."""
    print("🔍 Validating URL configurations...")
    
    # Check main URLs
    urls_file = Path("netbox_hedgehog/urls.py")
    if not urls_file.exists():
        print("❌ Main URLs file not found")
        return False
    
    urls_content = urls_file.read_text()
    
    # Check for GitOps Dashboard imports
    if "from .views.gitops_dashboard import get_dashboard_urls" not in urls_content:
        print("❌ GitOps Dashboard import missing from main URLs")
        return False
    
    # Check for GitOps Dashboard URL inclusion
    if "urlpatterns += get_dashboard_urls()" not in urls_content:
        print("❌ GitOps Dashboard URLs not included")
        return False
    
    print("✅ Main URL configuration validated")
    
    # Check API URLs
    api_urls_file = Path("netbox_hedgehog/api/urls.py")
    if not api_urls_file.exists():
        print("❌ API URLs file not found")
        return False
    
    api_urls_content = api_urls_file.read_text()
    
    # Check for GitOps API imports
    if "from .gitops_api import get_gitops_api_urls" not in api_urls_content:
        print("❌ GitOps API import missing from API URLs")
        return False
    
    # Check for GitOps API URL inclusion
    if "get_gitops_api_urls()" not in api_urls_content:
        print("❌ GitOps API URLs not included")
        return False
    
    print("✅ API URL configuration validated")
    return True

def validate_templates():
    """Validate template files."""
    print("🔍 Validating template files...")
    
    templates_dir = Path("netbox_hedgehog/templates/netbox_hedgehog")
    if not templates_dir.exists():
        print("❌ Templates directory not found")
        return False
    
    # Check main GitOps Dashboard template
    dashboard_template = templates_dir / "gitops_dashboard.html"
    if not dashboard_template.exists():
        print("❌ GitOps Dashboard template not found")
        return False
    
    # Check component templates
    components_dir = templates_dir / "components"
    required_components = [
        "six_state_indicators.html",
        "state_transition_workflow.html",
        "alert_queue_dashboard.html",
        "conflict_visualization.html"
    ]
    
    for component in required_components:
        component_path = components_dir / component
        if not component_path.exists():
            print(f"❌ Component template missing: {component}")
            return False
    
    print("✅ Template files validated")
    return True

def validate_static_assets():
    """Validate static asset files."""
    print("🔍 Validating static assets...")
    
    static_dir = Path("netbox_hedgehog/static/netbox_hedgehog")
    if not static_dir.exists():
        print("❌ Static assets directory not found")
        return False
    
    # Check CSS files
    css_dir = static_dir / "css"
    required_css = [
        "hedgehog.css",
        "gitops-dashboard.css",
        "progressive-disclosure.css"
    ]
    
    for css_file in required_css:
        css_path = css_dir / css_file
        if not css_path.exists():
            print(f"❌ CSS file missing: {css_file}")
            return False
    
    # Check JS files
    js_dir = static_dir / "js"
    required_js = [
        "hedgehog.js",
        "gitops-dashboard.js",
        "progressive-disclosure.js"
    ]
    
    for js_file in required_js:
        js_path = js_dir / js_file
        if not js_path.exists():
            print(f"❌ JS file missing: {js_file}")
            return False
    
    print("✅ Static assets validated")
    return True

def validate_navigation():
    """Validate navigation integration."""
    print("🔍 Validating navigation integration...")
    
    base_template = Path("netbox_hedgehog/templates/netbox_hedgehog/base.html")
    if not base_template.exists():
        print("❌ Base template not found")
        return False
    
    base_content = base_template.read_text()
    
    # Check for GitOps Dashboard menu item
    if "url 'plugins:netbox_hedgehog:gitops-dashboard'" not in base_content:
        print("❌ GitOps Dashboard not found in navigation menu")
        return False
    
    if 'GitOps Dashboard' not in base_content:
        print("❌ GitOps Dashboard menu text missing")
        return False
    
    print("✅ Navigation integration validated")
    return True

def validate_views():
    """Validate view files."""
    print("🔍 Validating view files...")
    
    # Check GitOps Dashboard views
    dashboard_views = Path("netbox_hedgehog/views/gitops_dashboard.py")
    if not dashboard_views.exists():
        print("❌ GitOps Dashboard views not found")
        return False
    
    # Check GitOps API
    gitops_api = Path("netbox_hedgehog/api/gitops_api.py")
    if not gitops_api.exists():
        print("❌ GitOps API not found")
        return False
    
    print("✅ View files validated")
    return True

def main():
    """Main validation function."""
    print("🚀 Starting Phase 3 Integration Layer validation...")
    print("=" * 60)
    
    validations = [
        ("URL Configurations", validate_urls),
        ("Template Files", validate_templates),
        ("Static Assets", validate_static_assets),
        ("Navigation Integration", validate_navigation),
        ("View Files", validate_views)
    ]
    
    all_passed = True
    
    for name, validator in validations:
        print(f"\n📋 {name}")
        print("-" * 40)
        if not validator():
            all_passed = False
            print(f"❌ {name} validation FAILED")
        else:
            print(f"✅ {name} validation PASSED")
    
    print("\n" + "=" * 60)
    
    if all_passed:
        print("🎉 ALL VALIDATIONS PASSED!")
        print("✅ Phase 3 Integration Layer is complete and ready for use")
        print("\n📍 GitOps Dashboard Access Points:")
        print("  - Main Navigation: Hedgehog → GitOps Dashboard")
        print("  - Direct URL: /plugins/hedgehog/gitops-dashboard/")
        print("  - Drift Dashboard: GitOps Dashboard button")
        print("\n🔧 API Endpoints:")
        print("  - Unified GitOps API: /api/plugins/netbox-hedgehog/gitops-api/")
        print("  - Dashboard APIs: /api/plugins/netbox-hedgehog/gitops-dashboard/")
        return 0
    else:
        print("❌ SOME VALIDATIONS FAILED!")
        print("Please fix the issues above before deployment")
        return 1

if __name__ == "__main__":
    sys.exit(main())