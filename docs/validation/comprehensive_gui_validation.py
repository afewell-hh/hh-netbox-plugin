#!/usr/bin/env python3
"""
Comprehensive GUI State Validation for Hedgehog Fabric Sync
Production Validation Agent - Final GUI Testing
Date: August 11, 2025
"""

import os
import re
import json
from datetime import datetime
from pathlib import Path

class ProductionGUIValidator:
    def __init__(self):
        self.plugin_root = Path(__file__).parent
        self.template_path = self.plugin_root / "netbox_hedgehog/templates/netbox_hedgehog/fabric_detail.html"
        self.js_path = self.plugin_root / "netbox_hedgehog/static/netbox_hedgehog/js/gitops-dashboard.js"
        self.css_paths = [
            self.plugin_root / "netbox_hedgehog/static/netbox_hedgehog/css/fabric-consolidated.css",
            self.plugin_root / "netbox_hedgehog/static/netbox_hedgehog/css/fabric-inline-styles.css",
            self.plugin_root / "netbox_hedgehog/static/netbox_hedgehog/css/hedgehog-responsive-consolidated.css"
        ]
        self.validation_results = {}
        
    def validate_all_gui_components(self):
        """Run comprehensive GUI validation tests"""
        print("🔍 Starting Comprehensive GUI Validation...")
        
        # Test 1: Template Structure
        self.validate_template_structure()
        
        # Test 2: Sync Status Fields
        self.validate_sync_status_fields()
        
        # Test 3: Manual Sync Buttons  
        self.validate_manual_sync_buttons()
        
        # Test 4: JavaScript Integration
        self.validate_javascript_integration()
        
        # Test 5: Responsive Design
        self.validate_responsive_design()
        
        # Test 6: Error Handling
        self.validate_error_handling()
        
        # Test 7: Security Implementation
        self.validate_security_measures()
        
        # Test 8: User Workflow
        self.validate_user_workflow()
        
        return self.generate_final_report()
        
    def validate_template_structure(self):
        """Validate fabric_detail.html template structure"""
        print("📝 Validating Template Structure...")
        
        if not self.template_path.exists():
            self.validation_results["template_structure"] = {
                "status": "FAILED",
                "error": "fabric_detail.html not found"
            }
            return
            
        content = self.template_path.read_text()
        
        # Check Django template standards
        checks = {
            "extends_base": "{% extends" in content,
            "csrf_token": "{% csrf_token %}" in content,
            "static_load": "{% load static %}" in content,
            "i18n_load": "{% load i18n %}" in content,
            "responsive_meta": 'name="viewport"' in content,
            "title_block": "{% block title %}" in content
        }
        
        # Check sync-related elements
        sync_elements = {
            "sync_status_summary": "Sync Status Summary" in content,
            "git_repository_sync": "Git Repository Sync" in content,
            "sync_status_badges": "badge bg-" in content,
            "last_sync_display": "Last sync:" in content
        }
        
        all_passed = all(checks.values()) and all(sync_elements.values())
        
        self.validation_results["template_structure"] = {
            "status": "PASSED" if all_passed else "PARTIAL",
            "django_standards": checks,
            "sync_elements": sync_elements,
            "score": f"{sum(list(checks.values()) + list(sync_elements.values()))}/10"
        }
        
    def validate_sync_status_fields(self):
        """Validate all sync status fields display correctly"""
        print("🔄 Validating Sync Status Fields...")
        
        content = self.template_path.read_text()
        
        # Find all sync status fields
        status_patterns = {
            "drift_status": r"object\.drift_status",
            "calculated_sync_status": r"object\.calculated_sync_status", 
            "last_git_sync": r"object\.last_git_sync",
            "git_repository_url": r"object\.git_repository_url"
        }
        
        status_states = {
            "in_sync": "in_sync" in content,
            "drift_detected": "drift_detected" in content,
            "syncing": "syncing" in content,
            "error": "error" in content,
            "not_configured": "not_configured" in content,
            "disabled": "disabled" in content
        }
        
        found_patterns = {}
        for field, pattern in status_patterns.items():
            matches = len(re.findall(pattern, content))
            found_patterns[field] = matches
            
        # Check status badges
        badge_count = len(re.findall(r'<span class="badge bg-\w+".*?data-sync-status', content))
        
        self.validation_results["sync_status_fields"] = {
            "status": "PASSED" if all(found_patterns.values()) else "FAILED",
            "field_usage": found_patterns,
            "status_states": status_states,
            "status_badges": badge_count,
            "total_states": sum(status_states.values())
        }
        
    def validate_manual_sync_buttons(self):
        """Validate manual sync buttons are present and functional"""
        print("🔘 Validating Manual Sync Buttons...")
        
        content = self.template_path.read_text()
        
        # Find sync buttons
        button_patterns = {
            "git_sync_button": r'onclick="triggerGitSync\(\)"',
            "sync_fabric_button": r'onclick="syncFabric\(',
            "manual_sync_class": r'btn.*?sync'
        }
        
        found_buttons = {}
        for button, pattern in button_patterns.items():
            matches = re.findall(pattern, content, re.IGNORECASE)
            found_buttons[button] = len(matches)
            
        # Check button accessibility
        accessibility_checks = {
            "aria_labels": 'aria-label=' in content,
            "button_icons": 'mdi mdi-' in content,
            "button_classes": 'class="btn' in content
        }
        
        self.validation_results["manual_sync_buttons"] = {
            "status": "PASSED" if found_buttons["git_sync_button"] > 0 else "FAILED",
            "buttons_found": found_buttons,
            "accessibility": accessibility_checks,
            "total_sync_buttons": sum(found_buttons.values())
        }
        
    def validate_javascript_integration(self):
        """Validate JavaScript integration and functionality"""
        print("🔧 Validating JavaScript Integration...")
        
        if not self.js_path.exists():
            self.validation_results["javascript_integration"] = {
                "status": "FAILED",
                "error": "gitops-dashboard.js not found"
            }
            return
            
        js_content = self.js_path.read_text()
        
        # Check essential functions
        functions = {
            "triggerGitSync": "triggerGitSync" in js_content,
            "syncFabric": "syncFabric" in js_content,
            "manageFabric": "manageFabric" in js_content,
            "showNotification": "showNotification" in js_content,
            "GitOpsDashboard": "class GitOpsDashboard" in js_content
        }
        
        # Check error handling
        error_handling = {
            "try_catch_blocks": js_content.count("try {"),
            "console_error": js_content.count("console.error"),
            "null_checks": js_content.count("if (") + js_content.count("!=="),
            "safe_dom_queries": js_content.count("getElementById")
        }
        
        self.validation_results["javascript_integration"] = {
            "status": "PASSED" if all(functions.values()) else "PARTIAL",
            "functions_available": functions,
            "error_handling_score": sum(error_handling.values()),
            "error_handling_details": error_handling
        }
        
    def validate_responsive_design(self):
        """Validate responsive design implementation"""
        print("📱 Validating Responsive Design...")
        
        template_content = self.template_path.read_text()
        
        # Check responsive classes
        responsive_patterns = {
            "bootstrap_grid": r'd-flex|flex-column|flex-md-row',
            "responsive_cols": r'col-\d+|col-md-\d+|col-sm-\d+',
            "mobile_classes": r'd-md-none|d-none d-md-',
            "viewport_meta": r'name="viewport"'
        }
        
        responsive_elements = {}
        for element, pattern in responsive_patterns.items():
            matches = len(re.findall(pattern, template_content))
            responsive_elements[element] = matches
            
        # Check CSS files exist
        css_files_exist = [path.exists() for path in self.css_paths]
        
        self.validation_results["responsive_design"] = {
            "status": "PASSED" if all(css_files_exist) and sum(responsive_elements.values()) > 0 else "PARTIAL",
            "responsive_elements": responsive_elements,
            "css_files_status": {
                "consolidated": self.css_paths[0].exists(),
                "inline_styles": self.css_paths[1].exists(), 
                "responsive": self.css_paths[2].exists()
            },
            "total_responsive_classes": sum(responsive_elements.values())
        }
        
    def validate_error_handling(self):
        """Validate error states and messaging"""
        print("⚠️ Validating Error Handling...")
        
        template_content = self.template_path.read_text()
        js_content = self.js_path.read_text() if self.js_path.exists() else ""
        
        # Check template error states
        error_states = {
            "error_badges": 'bg-danger' in template_content,
            "error_icons": 'mdi-alert' in template_content,
            "error_messages": 'Sync Error' in template_content,
            "fallback_states": 'Unknown' in template_content
        }
        
        # Check JavaScript error handling
        js_error_handling = {
            "try_catch": js_content.count("try {"),
            "error_logging": js_content.count("console.error"),
            "error_notifications": "showError" in js_content,
            "graceful_fallbacks": js_content.count("|| ")
        }
        
        self.validation_results["error_handling"] = {
            "status": "PASSED" if sum(error_states.values()) >= 3 else "PARTIAL",
            "template_error_states": error_states,
            "javascript_error_handling": js_error_handling,
            "total_error_mechanisms": sum(error_states.values()) + sum(js_error_handling.values())
        }
        
    def validate_security_measures(self):
        """Validate security implementation"""
        print("🔒 Validating Security Measures...")
        
        template_content = self.template_path.read_text()
        js_content = self.js_path.read_text() if self.js_path.exists() else ""
        
        # Check Django security features
        django_security = {
            "csrf_token": "{% csrf_token %}" in template_content,
            "auto_escape": "{% autoescape" in template_content or "{{" in template_content,
            "url_tags": "{% url " in template_content,
            "no_eval": "eval(" not in js_content,
            "no_innerhtml": ".innerHTML =" not in js_content
        }
        
        # Check input sanitization
        sanitization = {
            "html_encoding": "replace(/</g, '&lt;')" in js_content,
            "safe_insertions": "insertAdjacentHTML" in js_content,
            "parameter_validation": "typeof " in js_content
        }
        
        self.validation_results["security_measures"] = {
            "status": "PASSED" if sum(django_security.values()) >= 3 else "NEEDS_ATTENTION",
            "django_security": django_security,
            "input_sanitization": sanitization,
            "security_score": f"{sum(django_security.values()) + sum(sanitization.values())}/8"
        }
        
    def validate_user_workflow(self):
        """Validate complete user workflow"""
        print("👤 Validating User Workflow...")
        
        template_content = self.template_path.read_text()
        
        # Check navigation elements
        navigation = {
            "back_button": "Back to Fabrics" in template_content,
            "edit_link": "fabric_edit" in template_content,
            "view_links": "fabric_list" in template_content,
            "breadcrumbs": "nav" in template_content or "breadcrumb" in template_content
        }
        
        # Check information display
        information = {
            "fabric_name": "{{ object.name }}" in template_content,
            "sync_timestamps": "timesince" in template_content,
            "repository_links": "target=\"_blank\"" in template_content,
            "status_indicators": "mdi mdi-" in template_content
        }
        
        # Check interaction elements
        interactions = {
            "buttons": "btn btn-" in template_content,
            "forms": "<form" in template_content or "csrf_token" in template_content,
            "modals": "modal" in template_content,
            "tooltips": "title=" in template_content or "tooltip" in template_content
        }
        
        workflow_score = sum(navigation.values()) + sum(information.values()) + sum(interactions.values())
        
        self.validation_results["user_workflow"] = {
            "status": "PASSED" if workflow_score >= 8 else "PARTIAL",
            "navigation": navigation,
            "information_display": information,
            "interactions": interactions,
            "workflow_score": f"{workflow_score}/12"
        }
        
    def generate_final_report(self):
        """Generate comprehensive GUI validation report"""
        print("📋 Generating Final Report...")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Calculate overall score
        passed_tests = sum(1 for result in self.validation_results.values() 
                          if result.get("status") == "PASSED")
        total_tests = len(self.validation_results)
        overall_score = (passed_tests / total_tests) * 100
        
        # Determine overall status
        if overall_score >= 90:
            overall_status = "PRODUCTION_READY"
        elif overall_score >= 70:
            overall_status = "NEEDS_MINOR_FIXES"
        else:
            overall_status = "NEEDS_MAJOR_WORK"
            
        final_report = {
            "validation_timestamp": timestamp,
            "overall_status": overall_status,
            "overall_score": f"{overall_score:.1f}%",
            "tests_passed": f"{passed_tests}/{total_tests}",
            "detailed_results": self.validation_results,
            "summary": {
                "template_structure": self.validation_results.get("template_structure", {}).get("status", "UNKNOWN"),
                "sync_functionality": self.validation_results.get("sync_status_fields", {}).get("status", "UNKNOWN"),
                "user_interface": self.validation_results.get("manual_sync_buttons", {}).get("status", "UNKNOWN"),
                "responsive_design": self.validation_results.get("responsive_design", {}).get("status", "UNKNOWN"),
                "security_compliance": self.validation_results.get("security_measures", {}).get("status", "UNKNOWN")
            },
            "evidence_files": [
                str(self.template_path),
                str(self.js_path),
                f"gui_validation_evidence_{timestamp}.html"
            ]
        }
        
        # Save report
        report_path = self.plugin_root / f"gui_validation_report_{timestamp}.json"
        with open(report_path, 'w') as f:
            json.dump(final_report, f, indent=2)
            
        print(f"✅ Final Report saved: {report_path}")
        print(f"🎯 Overall Status: {overall_status}")
        print(f"📊 Score: {overall_score:.1f}% ({passed_tests}/{total_tests} tests passed)")
        
        return final_report

def main():
    """Run comprehensive GUI validation"""
    validator = ProductionGUIValidator()
    report = validator.validate_all_gui_components()
    
    print("\n" + "="*50)
    print("🔍 FINAL GUI VALIDATION SUMMARY")
    print("="*50)
    print(f"Status: {report['overall_status']}")
    print(f"Score: {report['overall_score']}")
    print(f"Tests: {report['tests_passed']}")
    
    # Show critical findings
    for test_name, result in report['detailed_results'].items():
        status_icon = "✅" if result.get("status") == "PASSED" else "⚠️" if result.get("status") == "PARTIAL" else "❌"
        print(f"{status_icon} {test_name.replace('_', ' ').title()}: {result.get('status', 'UNKNOWN')}")
        
    return report

if __name__ == "__main__":
    main()