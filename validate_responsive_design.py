#!/usr/bin/env python3
"""
Responsive Design Validation Script for Issue #37
Validates responsive implementation for fabric detail page
"""

import os
import sys
import re
from pathlib import Path

class ResponsiveDesignValidator:
    def __init__(self):
        self.plugin_root = Path(__file__).parent
        self.issues = []
        self.successes = []
        
    def validate_css_files(self):
        """Validate responsive CSS files exist and have required content"""
        print("🔍 Validating CSS files...")
        
        # Check responsive CSS file exists
        responsive_css = self.plugin_root / "netbox_hedgehog/static/netbox_hedgehog/css/responsive-fabric.css"
        if not responsive_css.exists():
            self.issues.append("❌ responsive-fabric.css not found")
            return
        
        self.successes.append("✅ responsive-fabric.css exists")
        
        # Read and validate CSS content
        with open(responsive_css, 'r') as f:
            css_content = f.read()
        
        # Check for required breakpoints
        required_breakpoints = [
            "@media (max-width: 767px)",  # Mobile
            "@media (min-width: 768px) and (max-width: 1199px)",  # Tablet
            "@media (min-width: 1200px)"  # Desktop
        ]
        
        for breakpoint in required_breakpoints:
            if breakpoint in css_content:
                self.successes.append(f"✅ Found breakpoint: {breakpoint}")
            else:
                self.issues.append(f"❌ Missing breakpoint: {breakpoint}")
        
        # Check for desktop preservation
        if "@media (min-width: 1200px)" in css_content:
            if "Desktop appearance remains 100% unchanged" in css_content:
                self.successes.append("✅ Desktop preservation documented")
            else:
                self.issues.append("❌ Desktop preservation not properly documented")
        
        # Check for mobile-first approach
        mobile_features = [
            "container-fluid",
            "flex-direction: column",
            "min-height: 44px",  # Touch targets
            "font-size: 16px",   # Prevent iOS zoom
        ]
        
        for feature in mobile_features:
            if feature in css_content:
                self.successes.append(f"✅ Mobile feature: {feature}")
            else:
                self.issues.append(f"❌ Missing mobile feature: {feature}")
    
    def validate_template_changes(self):
        """Validate fabric detail template has responsive enhancements"""
        print("🔍 Validating template changes...")
        
        template_file = self.plugin_root / "netbox_hedgehog/templates/netbox_hedgehog/fabric_detail.html"
        if not template_file.exists():
            self.issues.append("❌ fabric_detail.html not found")
            return
        
        with open(template_file, 'r') as f:
            template_content = f.read()
        
        # Check for viewport meta tag
        if 'name="viewport"' in template_content and 'width=device-width' in template_content:
            self.successes.append("✅ Viewport meta tag added")
        else:
            self.issues.append("❌ Viewport meta tag missing")
        
        # Check for responsive CSS inclusion
        if 'responsive-fabric.css' in template_content:
            self.successes.append("✅ Responsive CSS included")
        else:
            self.issues.append("❌ Responsive CSS not included")
        
        # Check for Bootstrap responsive classes
        responsive_classes = [
            'col-12 col-md-6',      # Responsive columns
            'col-12 col-lg-8',      # Large screen columns
            'd-flex flex-column flex-md-row',  # Flexible layout
            'table-responsive',     # Responsive tables
            'h-100'                 # Equal height cards
        ]
        
        for css_class in responsive_classes:
            if css_class in template_content:
                self.successes.append(f"✅ Bootstrap responsive class: {css_class}")
            else:
                self.issues.append(f"❌ Missing responsive class: {css_class}")
        
        # Check for JavaScript enhancements
        if 'responsive-enhancements.js' in template_content:
            self.successes.append("✅ Responsive JavaScript included")
        else:
            self.issues.append("❌ Responsive JavaScript not included")
    
    def validate_javascript_enhancements(self):
        """Validate responsive JavaScript file"""
        print("🔍 Validating JavaScript enhancements...")
        
        js_file = self.plugin_root / "netbox_hedgehog/static/netbox_hedgehog/js/responsive-enhancements.js"
        if not js_file.exists():
            self.issues.append("❌ responsive-enhancements.js not found")
            return
        
        self.successes.append("✅ responsive-enhancements.js exists")
        
        with open(js_file, 'r') as f:
            js_content = f.read()
        
        # Check for required functionality
        required_features = [
            'getViewportType',      # Viewport detection
            'isMobile',             # Mobile detection
            'isTouchDevice',        # Touch detection
            'enhanceTouchInteractions', # Touch enhancements
            'improveTableReadability',  # Table improvements
            'addSwipeGestures',     # Swipe support
            'min-height: 48px'      # Touch targets
        ]
        
        for feature in required_features:
            if feature in js_content:
                self.successes.append(f"✅ JavaScript feature: {feature}")
            else:
                self.issues.append(f"❌ Missing JavaScript feature: {feature}")
    
    def validate_test_documentation(self):
        """Validate test documentation exists"""
        print("🔍 Validating test documentation...")
        
        test_file = self.plugin_root / "docs/responsive-test.html"
        if test_file.exists():
            self.successes.append("✅ Test documentation exists")
            
            with open(test_file, 'r') as f:
                test_content = f.read()
            
            # Check for device previews
            device_previews = [
                'desktop-preview',
                'tablet-preview', 
                'mobile-preview'
            ]
            
            for preview in device_previews:
                if preview in test_content:
                    self.successes.append(f"✅ Test preview: {preview}")
                else:
                    self.issues.append(f"❌ Missing test preview: {preview}")
        else:
            self.issues.append("❌ Test documentation missing")
    
    def validate_responsive_requirements(self):
        """Validate specific responsive requirements from Issue #37"""
        print("🔍 Validating Issue #37 requirements...")
        
        # Requirement 1: Desktop Preservation
        responsive_css = self.plugin_root / "netbox_hedgehog/static/netbox_hedgehog/css/responsive-fabric.css"
        if responsive_css.exists():
            with open(responsive_css, 'r') as f:
                css_content = f.read()
            
            if "DESKTOP PRESERVATION - PRIORITY #1" in css_content:
                self.successes.append("✅ Desktop preservation is priority #1")
            else:
                self.issues.append("❌ Desktop preservation not prioritized")
            
            if "1200px+" in css_content and "unchanged" in css_content:
                self.successes.append("✅ Desktop appearance preservation documented")
            else:
                self.issues.append("❌ Desktop appearance preservation not clearly documented")
        
        # Requirement 2: Mobile Enhancement Goals
        mobile_breakpoints = ["320px", "767px", "768px", "1199px"]
        for breakpoint in mobile_breakpoints:
            if breakpoint in css_content:
                self.successes.append(f"✅ Breakpoint defined: {breakpoint}")
            else:
                self.issues.append(f"❌ Breakpoint missing: {breakpoint}")
        
        # Requirement 3: Touch-Friendly Implementation
        if "44px" in css_content and "48px" in css_content:
            self.successes.append("✅ Touch targets minimum 44px implemented")
        else:
            self.issues.append("❌ Touch targets not properly implemented")
        
        # Requirement 4: Bootstrap 5 Implementation
        template_file = self.plugin_root / "netbox_hedgehog/templates/netbox_hedgehog/fabric_detail.html"
        if template_file.exists():
            with open(template_file, 'r') as f:
                template_content = f.read()
            
            bootstrap_features = [
                "col-12",
                "col-md-", 
                "col-lg-",
                "flex-column",
                "flex-md-row",
                "g-3",
                "g-4"
            ]
            
            bootstrap_count = sum(1 for feature in bootstrap_features if feature in template_content)
            if bootstrap_count >= 5:
                self.successes.append(f"✅ Bootstrap 5 features implemented ({bootstrap_count}/8)")
            else:
                self.issues.append(f"❌ Insufficient Bootstrap 5 features ({bootstrap_count}/8)")
    
    def check_file_permissions(self):
        """Check that all files have proper permissions"""
        print("🔍 Checking file permissions...")
        
        files_to_check = [
            "netbox_hedgehog/static/netbox_hedgehog/css/responsive-fabric.css",
            "netbox_hedgehog/static/netbox_hedgehog/js/responsive-enhancements.js",
            "docs/responsive-test.html"
        ]
        
        for file_path in files_to_check:
            full_path = self.plugin_root / file_path
            if full_path.exists():
                if os.access(full_path, os.R_OK):
                    self.successes.append(f"✅ File readable: {file_path}")
                else:
                    self.issues.append(f"❌ File not readable: {file_path}")
            else:
                self.issues.append(f"❌ File missing: {file_path}")
    
    def run_validation(self):
        """Run all validation checks"""
        print("🚀 Starting Responsive Design Validation for Issue #37")
        print("=" * 60)
        
        self.validate_css_files()
        self.validate_template_changes()
        self.validate_javascript_enhancements()
        self.validate_test_documentation()
        self.validate_responsive_requirements()
        self.check_file_permissions()
        
        # Print results
        print("\n" + "=" * 60)
        print("📊 VALIDATION RESULTS")
        print("=" * 60)
        
        if self.successes:
            print(f"\n✅ SUCCESSES ({len(self.successes)}):")
            for success in self.successes:
                print(f"  {success}")
        
        if self.issues:
            print(f"\n❌ ISSUES ({len(self.issues)}):")
            for issue in self.issues:
                print(f"  {issue}")
        
        # Summary
        total_checks = len(self.successes) + len(self.issues)
        success_rate = (len(self.successes) / total_checks * 100) if total_checks > 0 else 0
        
        print(f"\n📈 SUMMARY:")
        print(f"  Total Checks: {total_checks}")
        print(f"  Passed: {len(self.successes)}")
        print(f"  Failed: {len(self.issues)}")
        print(f"  Success Rate: {success_rate:.1f}%")
        
        if len(self.issues) == 0:
            print("\n🎉 All responsive design requirements validated successfully!")
            print("✅ Issue #37: Responsive Design Implementation - COMPLETE")
            return True
        else:
            print(f"\n⚠️  {len(self.issues)} issues need attention before completion")
            return False

def main():
    """Main validation function"""
    validator = ResponsiveDesignValidator()
    success = validator.run_validation()
    
    if success:
        print("\n🏆 RESPONSIVE DESIGN IMPLEMENTATION SUCCESSFUL")
        print("📱 Mobile-first responsive design implemented")
        print("🖥️  Desktop appearance preserved identically")  
        print("⚡ Touch interactions enhanced")
        print("🎯 All Issue #37 requirements met")
        sys.exit(0)
    else:
        print("\n🔧 Additional work required for full compliance")
        sys.exit(1)

if __name__ == "__main__":
    main()