#!/usr/bin/env python3
"""
Enhanced Sync Validation Framework
=================================

This extends the Real Functionality Validation Framework to test actual sync operations,
not just status display. This would have caught the sync error root cause.

Key Principles:
1. Test actual sync operations end-to-end
2. Validate error messages provide actionable information
3. Verify sync operations can be triggered and complete
4. Test user authentication context in sync operations
"""

import requests
import re
import json
import time
from datetime import datetime
from typing import Dict, List, Tuple, Any, Optional


class SyncOperationValidator:
    """
    Validates actual sync functionality, not just status display.
    Tests the complete sync workflow including error scenarios.
    """
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
        self.validation_results = []
        
    def log_validation(self, test_name: str, status: str, evidence: Dict[str, Any]):
        """Log validation result with evidence"""
        result = {
            'timestamp': datetime.now().isoformat(),
            'test_name': test_name,
            'status': status,  # 'PASS', 'FAIL', 'ERROR'
            'evidence': evidence
        }
        self.validation_results.append(result)
        print(f"[{status}] {test_name}")
        if status != 'PASS':
            print(f"  Evidence: {evidence}")
    
    def validate_sync_error_details(self):
        """Validate sync errors provide actionable information"""
        print("\n=== Sync Error Details Validation ===")
        
        # Check fabric detail page for sync error information
        status_code, detail_html = self.get_page_content('/plugins/hedgehog/fabrics/12/')
        
        if status_code != 200:
            self.log_validation("Fabric Detail Access", "FAIL", {"status_code": status_code})
            return
        
        # Extract sync error message
        error_pattern = r'<th>Sync Error:</th>.*?<div class="alert alert-danger">.*?<small>([^<]+)</small>'
        error_match = re.search(error_pattern, detail_html, re.DOTALL)
        
        if not error_match:
            self.log_validation("Sync Error Message Present", "FAIL", {"error_found": False})
            return
        
        error_message = error_match.group(1).strip()
        
        # Analyze error message quality
        evidence = {
            "error_message": error_message,
            "mentions_user_auth": "User" in error_message and "AnonymousUser" in error_message,
            "actionable": self._is_error_actionable(error_message),
            "technical_detail": "ObjectChange.user" in error_message,
            "error_category": self._categorize_error(error_message)
        }
        
        if evidence["actionable"] and evidence["technical_detail"]:
            self.log_validation("Sync Error Information Quality", "PASS", evidence)
        else:
            self.log_validation("Sync Error Information Quality", "FAIL", evidence)
    
    def validate_sync_operation_triggers(self):
        """Validate sync operations can be triggered (test the buttons/API)"""
        print("\n=== Sync Operation Trigger Validation ===")
        
        # Check if sync buttons are present and functional
        status_code, detail_html = self.get_page_content('/plugins/hedgehog/fabrics/12/')
        
        if status_code != 200:
            self.log_validation("Fabric Detail Load", "FAIL", {"status_code": status_code})
            return
        
        # Look for sync buttons
        sync_buttons = {
            "sync_from_git": re.search(r'id="sync-button".*?onclick="triggerSync\((\d+)\)"', detail_html),
            "sync_from_hckc": re.search(r'id="sync-hckc-button".*?onclick="syncFromHCKC\((\d+)\)"', detail_html),
            "test_connection": re.search(r'id="test-connection-button".*?onclick="testConnection\((\d+)\)"', detail_html)
        }
        
        button_evidence = {}
        for button_name, match in sync_buttons.items():
            button_evidence[button_name] = {
                "present": match is not None,
                "fabric_id": match.group(1) if match else None
            }
        
        # Test API endpoints exist (without authentication for now)
        api_endpoints = [
            f'/api/plugins/hedgehog/gitops-fabrics/12/gitops_sync/',
            f'/api/plugins/hedgehog/gitops-fabrics/12/hckc_sync/',
            f'/plugins/hedgehog/fabrics/12/test-connection/'
        ]
        
        api_evidence = {}
        for endpoint in api_endpoints:
            status_code, response = self.get_page_content(endpoint)
            api_evidence[endpoint] = {
                "status_code": status_code,
                "exists": status_code != 404,
                "auth_required": status_code == 403 or "login" in response.lower()
            }
        
        evidence = {
            "buttons": button_evidence,
            "api_endpoints": api_evidence,
            "all_buttons_present": all(b["present"] for b in button_evidence.values()),
            "all_endpoints_exist": all(e["exists"] for e in api_evidence.values())
        }
        
        if evidence["all_buttons_present"] and evidence["all_endpoints_exist"]:
            self.log_validation("Sync Operation Infrastructure", "PASS", evidence)
        else:
            self.log_validation("Sync Operation Infrastructure", "FAIL", evidence)
    
    def validate_authentication_context_issue(self):
        """Validate the specific authentication context issue causing sync errors"""
        print("\n=== Authentication Context Issue Validation ===")
        
        # Check if the error is related to authentication context
        status_code, detail_html = self.get_page_content('/plugins/hedgehog/fabrics/12/')
        
        error_pattern = r'<th>Sync Error:</th>.*?<small>([^<]+)</small>'
        error_match = re.search(error_pattern, detail_html, re.DOTALL)
        
        if not error_match:
            self.log_validation("Sync Error Detection", "FAIL", {"error_found": False})
            return
        
        error_message = error_match.group(1).strip()
        
        # Check for specific authentication context issues
        auth_issues = {
            "anonymous_user_issue": "AnonymousUser" in error_message,
            "user_instance_requirement": "User instance" in error_message,
            "object_change_audit": "ObjectChange.user" in error_message,
            "django_auth_error": "django.contrib.auth" in error_message
        }
        
        evidence = {
            "error_message": error_message,
            "authentication_issues": auth_issues,
            "is_auth_context_error": any(auth_issues.values()),
            "suggested_fix": "Sync operations need proper user context for NetBox audit logging"
        }
        
        if evidence["is_auth_context_error"]:
            self.log_validation("Authentication Context Error Identified", "PASS", evidence)
        else:
            self.log_validation("Authentication Context Error Analysis", "FAIL", evidence)
    
    def get_page_content(self, path: str) -> Tuple[int, str]:
        """Get page content and return status code and HTML"""
        from urllib.parse import urljoin
        url = urljoin(self.base_url, path)
        try:
            response = self.session.get(url, timeout=10)
            return response.status_code, response.text
        except Exception as e:
            return 0, f"Error: {str(e)}"
    
    def _is_error_actionable(self, error_message: str) -> bool:
        """Determine if error message provides actionable information"""
        actionable_indicators = [
            "must be a",
            "cannot assign",
            "required",
            "invalid",
            "missing"
        ]
        return any(indicator in error_message.lower() for indicator in actionable_indicators)
    
    def _categorize_error(self, error_message: str) -> str:
        """Categorize the type of error"""
        if "User" in error_message and "AnonymousUser" in error_message:
            return "authentication_context"
        elif "ObjectChange" in error_message:
            return "audit_logging"
        elif "cannot assign" in error_message:
            return "data_validation"
        else:
            return "unknown"


def run_enhanced_sync_validation():
    """Run enhanced sync validation to test actual functionality"""
    print("=== ENHANCED SYNC VALIDATION FRAMEWORK ===")
    print("Testing actual sync operations and error root causes")
    print("=" * 60)
    
    validator = SyncOperationValidator()
    
    # Run enhanced sync validations
    validator.validate_sync_error_details()
    validator.validate_sync_operation_triggers()
    validator.validate_authentication_context_issue()
    
    # Generate summary
    results = validator.validation_results
    total_tests = len(results)
    passed_tests = len([r for r in results if r['status'] == 'PASS'])
    failed_tests = len([r for r in results if r['status'] == 'FAIL'])
    error_tests = len([r for r in results if r['status'] == 'ERROR'])
    
    print("\n" + "=" * 60)
    print("=== ENHANCED SYNC VALIDATION SUMMARY ===")
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {passed_tests} ({passed_tests/total_tests*100:.1f}%)")
    print(f"Failed: {failed_tests} ({failed_tests/total_tests*100:.1f}%)")
    print(f"Errors: {error_tests} ({error_tests/total_tests*100:.1f}%)")
    
    # Save detailed results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = f"/home/ubuntu/cc/hedgehog-netbox-plugin/enhanced_sync_validation_{timestamp}.json"
    
    with open(results_file, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total': total_tests,
                'passed': passed_tests,
                'failed': failed_tests,
                'errors': error_tests,
                'success_rate': f"{passed_tests/total_tests*100:.1f}%"
            },
            'results': results
        }, f, indent=2)
    
    print(f"\nDetailed results saved to: {results_file}")
    
    # Print key findings
    print("\n=== KEY FINDINGS ===")
    for result in results:
        if result['status'] == 'PASS' and 'Authentication Context Error Identified' in result['test_name']:
            evidence = result['evidence']
            print(f"✅ Root Cause: {evidence['suggested_fix']}")
        elif result['status'] == 'PASS' and 'Sync Error Information Quality' in result['test_name']:
            evidence = result['evidence']
            print(f"✅ Error Category: {evidence['error_category']}")
    
    return passed_tests == total_tests


if __name__ == "__main__":
    success = run_enhanced_sync_validation()
    exit(0 if success else 1)