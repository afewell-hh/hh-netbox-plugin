#!/usr/bin/env python3
"""
Real Functionality Validation Framework
=====================================

A comprehensive testing framework that validates ACTUAL user-facing behavior,
not just technical implementation. Designed to catch the types of failures
that previous testing missed.

Key Principles:
1. Data Accuracy Validation - Verify displayed values match database reality
2. Functional Interaction Testing - Actually click buttons and validate responses  
3. Cross-Page Consistency - Verify same data displays consistently across pages
4. User Experience Validation - Test complete workflows end-to-end
"""

import requests
import re
import json
import time
from datetime import datetime
from typing import Dict, List, Tuple, Any, Optional
from urllib.parse import urljoin


class RealFunctionalityValidator:
    """
    Base class for real functionality validation.
    Validates actual behavior, not just technical implementation.
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
    
    def get_page_content(self, path: str) -> Tuple[int, str]:
        """Get page content and return status code and HTML"""
        url = urljoin(self.base_url, path)
        try:
            response = self.session.get(url, timeout=10)
            return response.status_code, response.text
        except Exception as e:
            return 0, f"Error: {str(e)}"
    
    def extract_metric_value(self, html: str, metric_name: str) -> Optional[str]:
        """Extract metric value from dashboard HTML"""
        # Pattern for dashboard metric cards
        pattern = rf'<h2>([^<]*)</h2>\s*<p[^>]*>{re.escape(metric_name)}</p>'
        match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
        return match.group(1).strip() if match else None
    
    def extract_list_count(self, html: str, list_type: str) -> Optional[int]:
        """Extract count from list page (e.g., 'Total: 2 VPCs')"""
        patterns = [
            rf'Total:\s*(\d+)\s*{re.escape(list_type)}',
            rf'(\d+)\s*{re.escape(list_type)}\s*found',
            rf'{re.escape(list_type)}\s*count:\s*(\d+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                return int(match.group(1))
        return None


class DashboardMetricsValidator(RealFunctionalityValidator):
    """
    Validates dashboard metrics accuracy by cross-referencing with actual data pages.
    This would have caught the VPC count display failure.
    """
    
    def validate_dashboard_metrics_accuracy(self):
        """Validate all dashboard metrics match reality"""
        print("\n=== Dashboard Metrics Accuracy Validation ===")
        
        # Get dashboard content
        status_code, dashboard_html = self.get_page_content('/plugins/hedgehog/')
        if status_code != 200:
            self.log_validation(
                "Dashboard Load", "FAIL",
                {"status_code": status_code, "error": "Dashboard inaccessible"}
            )
            return
        
        # Test 1: VPC Count Accuracy
        self._validate_vpc_count_accuracy(dashboard_html)
        
        # Test 2: Fabric Count Accuracy  
        self._validate_fabric_count_accuracy(dashboard_html)
        
        # Test 3: Sync Status Accuracy
        self._validate_sync_status_accuracy(dashboard_html)
        
    def _validate_vpc_count_accuracy(self, dashboard_html: str):
        """Validate VPC count matches VPC list page"""
        # Extract dashboard VPC count
        dashboard_vpc_count = self.extract_metric_value(dashboard_html, "VPCs")
        
        # Get VPC list page count
        status_code, vpc_list_html = self.get_page_content('/plugins/hedgehog/vpcs/')
        vpc_list_count = None
        
        if status_code == 200:
            vpc_list_count = self.extract_list_count(vpc_list_html, "VPCs")
        
        # Validate consistency
        evidence = {
            "dashboard_value": dashboard_vpc_count,
            "list_page_value": vpc_list_count,
            "dashboard_empty": dashboard_vpc_count is None or dashboard_vpc_count == "",
            "list_page_accessible": status_code == 200
        }
        
        if dashboard_vpc_count is None or dashboard_vpc_count == "":
            self.log_validation("VPC Count Display", "FAIL", evidence)
        elif vpc_list_count is not None and dashboard_vpc_count != str(vpc_list_count):
            self.log_validation("VPC Count Consistency", "FAIL", evidence)
        else:
            self.log_validation("VPC Count Accuracy", "PASS", evidence)
    
    def _validate_fabric_count_accuracy(self, dashboard_html: str):
        """Validate fabric count matches fabric list page"""
        dashboard_fabric_count = self.extract_metric_value(dashboard_html, "Total Fabrics")
        
        status_code, fabric_list_html = self.get_page_content('/plugins/hedgehog/fabrics/')
        fabric_list_count = None
        
        if status_code == 200:
            fabric_list_count = self.extract_list_count(fabric_list_html, "Fabrics")
            
        evidence = {
            "dashboard_value": dashboard_fabric_count,
            "list_page_value": fabric_list_count,
            "dashboard_empty": dashboard_fabric_count is None or dashboard_fabric_count == "",
            "list_page_accessible": status_code == 200
        }
        
        if dashboard_fabric_count is None or dashboard_fabric_count == "":
            self.log_validation("Fabric Count Display", "FAIL", evidence)
        elif fabric_list_count is not None and dashboard_fabric_count != str(fabric_list_count):
            self.log_validation("Fabric Count Consistency", "FAIL", evidence)
        else:
            self.log_validation("Fabric Count Accuracy", "PASS", evidence)
    
    def _validate_sync_status_accuracy(self, dashboard_html: str):
        """Validate sync status metrics reflect actual fabric sync states"""
        in_sync_count = self.extract_metric_value(dashboard_html, "In Sync")
        drift_count = self.extract_metric_value(dashboard_html, "Drift Detected")
        
        # Check fabric detail pages for actual sync status
        status_code, fabric_list_html = self.get_page_content('/plugins/hedgehog/fabrics/')
        actual_sync_states = []
        
        if status_code == 200:
            # Extract fabric links and check their sync status
            fabric_links = re.findall(r'/plugins/hedgehog/fabrics/(\d+)/', fabric_list_html)
            
            for fabric_id in fabric_links:
                detail_status, detail_html = self.get_page_content(f'/plugins/hedgehog/fabrics/{fabric_id}/')
                if detail_status == 200:
                    # Look for sync status badge
                    sync_status_match = re.search(r'Sync Status:.*?<span[^>]*>([^<]+)</span>', detail_html, re.DOTALL)
                    if sync_status_match:
                        actual_sync_states.append(sync_status_match.group(1).strip())
        
        evidence = {
            "dashboard_in_sync": in_sync_count,
            "dashboard_drift": drift_count,
            "actual_fabric_sync_states": actual_sync_states,
            "fabric_count": len(actual_sync_states)
        }
        
        # Validate sync metrics are not hardcoded zeros
        if in_sync_count == "0" and drift_count == "0" and len(actual_sync_states) > 0:
            self.log_validation("Sync Status Not Hardcoded", "FAIL", evidence)
        else:
            self.log_validation("Sync Status Calculation", "PASS", evidence)


class NavigationIntegrityValidator(RealFunctionalityValidator):
    """
    Validates navigation works completely and pages load without errors.
    This would have caught the Git Repository navigation failure.
    """
    
    def validate_navigation_integrity(self):
        """Validate all navigation links work without server errors"""
        print("\n=== Navigation Integrity Validation ===")
        
        # Test key navigation paths
        navigation_tests = [
            ('/plugins/hedgehog/', 'Dashboard'),
            ('/plugins/hedgehog/fabrics/', 'Fabric List'),
            ('/plugins/hedgehog/git-repos/', 'Git Repository List'),
            ('/plugins/hedgehog/vpcs/', 'VPC List'),
            ('/plugins/hedgehog/connections/', 'Connection List'),
        ]
        
        for path, name in navigation_tests:
            status_code, html = self.get_page_content(path)
            
            evidence = {
                "path": path,
                "status_code": status_code,
                "server_error": status_code >= 500,
                "page_loads": status_code == 200,
                "error_content": html[:200] if status_code >= 400 else None
            }
            
            if status_code >= 500:
                self.log_validation(f"Navigation - {name}", "FAIL", evidence)
            elif status_code == 200:
                self.log_validation(f"Navigation - {name}", "PASS", evidence)
            else:
                self.log_validation(f"Navigation - {name}", "ERROR", evidence)


class EmptyValueDetector(RealFunctionalityValidator):
    """
    Detects empty values and display failures across the application.
    This would have caught the VPC metrics empty display issue.
    """
    
    def detect_empty_values(self):
        """Scan for empty values in key metrics and data displays"""
        print("\n=== Empty Value Detection ===")
        
        # Check dashboard for empty metric values
        status_code, dashboard_html = self.get_page_content('/plugins/hedgehog/')
        if status_code == 200:
            self._detect_empty_dashboard_metrics(dashboard_html)
        
        # Check list pages for empty content
        list_pages = [
            ('/plugins/hedgehog/fabrics/', 'Fabric List'),
            ('/plugins/hedgehog/vpcs/', 'VPC List'),
            ('/plugins/hedgehog/git-repos/', 'Git Repository List')
        ]
        
        for path, name in list_pages:
            status_code, html = self.get_page_content(path)
            if status_code == 200:
                self._detect_empty_list_content(html, name, path)
    
    def _detect_empty_dashboard_metrics(self, html: str):
        """Detect empty metric values in dashboard"""
        # Look for empty h2 tags (metric values)
        empty_h2_matches = re.findall(r'<h2>\s*</h2>', html)
        
        # Look for metrics with specific names
        metrics = ['Total Fabrics', 'VPCs', 'In Sync', 'Drift Detected']
        empty_metrics = []
        
        for metric in metrics:
            value = self.extract_metric_value(html, metric)
            if value is None or value.strip() == "":
                empty_metrics.append(metric)
        
        evidence = {
            "empty_h2_count": len(empty_h2_matches),
            "empty_metrics": empty_metrics,
            "total_metrics_checked": len(metrics)
        }
        
        if empty_metrics:
            self.log_validation("Dashboard Empty Values", "FAIL", evidence)
        else:
            self.log_validation("Dashboard Metric Population", "PASS", evidence)
    
    def _detect_empty_list_content(self, html: str, name: str, path: str):
        """Detect if list pages have content or are unexpectedly empty"""
        # Look for table rows (indicating list content)
        table_rows = len(re.findall(r'<tr[^>]*>.*?</tr>', html, re.DOTALL))
        
        # Look for "no items" messages
        no_items_patterns = [
            r'no\s+\w+\s+found',
            r'no\s+items',
            r'empty\s+list',
            r'nothing\s+to\s+display'
        ]
        
        has_no_items_message = any(re.search(pattern, html, re.IGNORECASE) for pattern in no_items_patterns)
        
        evidence = {
            "path": path,
            "table_rows": table_rows,
            "has_content": table_rows > 1,  # Header row + at least one data row
            "has_no_items_message": has_no_items_message
        }
        
        if table_rows <= 1 and not has_no_items_message:
            self.log_validation(f"{name} Content Check", "FAIL", evidence)
        else:
            self.log_validation(f"{name} Content Population", "PASS", evidence)


def run_comprehensive_validation():
    """Run comprehensive real functionality validation"""
    print("=== REAL FUNCTIONALITY VALIDATION FRAMEWORK ===")
    print("Testing actual user-facing behavior, not just technical implementation")
    print("=" * 60)
    
    # Initialize validators
    dashboard_validator = DashboardMetricsValidator()
    navigation_validator = NavigationIntegrityValidator()
    empty_value_detector = EmptyValueDetector()
    
    # Run validation suites
    dashboard_validator.validate_dashboard_metrics_accuracy()
    navigation_validator.validate_navigation_integrity()
    empty_value_detector.detect_empty_values()
    
    # Collect all results
    all_results = (
        dashboard_validator.validation_results +
        navigation_validator.validation_results +
        empty_value_detector.validation_results
    )
    
    # Generate summary
    total_tests = len(all_results)
    passed_tests = len([r for r in all_results if r['status'] == 'PASS'])
    failed_tests = len([r for r in all_results if r['status'] == 'FAIL'])
    error_tests = len([r for r in all_results if r['status'] == 'ERROR'])
    
    print("\n" + "=" * 60)
    print("=== VALIDATION SUMMARY ===")
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {passed_tests} ({passed_tests/total_tests*100:.1f}%)")
    print(f"Failed: {failed_tests} ({failed_tests/total_tests*100:.1f}%)")
    print(f"Errors: {error_tests} ({error_tests/total_tests*100:.1f}%)")
    
    # Save detailed results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = f"/home/ubuntu/cc/hedgehog-netbox-plugin/validation_results_{timestamp}.json"
    
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
            'results': all_results
        }, f, indent=2)
    
    print(f"\nDetailed results saved to: {results_file}")
    
    # Return success if no failures
    return failed_tests == 0 and error_tests == 0


if __name__ == "__main__":
    success = run_comprehensive_validation()
    exit(0 if success else 1)