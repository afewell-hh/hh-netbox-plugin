#!/usr/bin/env python3
"""
Integration Test Validation Script
Comprehensive testing of fabric detail page improvements
"""

import requests
import time
import json
import sys
from urllib.parse import urljoin
from pathlib import Path

class NetBoxIntegrationTester:
    """Integration tester for Hedgehog NetBox plugin fabric improvements"""
    
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
        self.test_results = []
        self.fabric_id = 35  # Default test fabric ID
        
    def log_test(self, test_name, status, details=""):
        """Log test result"""
        result = {
            "test": test_name,
            "status": status,
            "details": details,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        self.test_results.append(result)
        status_symbol = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
        print(f"{status_symbol} {test_name}: {status}")
        if details:
            print(f"   Details: {details}")
    
    def authenticate(self, username="admin", password="admin"):
        """Authenticate with NetBox"""
        try:
            # Get login page for CSRF token
            login_url = urljoin(self.base_url, '/login/')
            response = self.session.get(login_url)
            
            if response.status_code != 200:
                self.log_test("Authentication Setup", "FAIL", f"Login page not accessible: {response.status_code}")
                return False
            
            # Extract CSRF token
            import re
            csrf_match = re.search(r'name="csrfmiddlewaretoken" value="([^"]*)"', response.text)
            if not csrf_match:
                self.log_test("Authentication Setup", "FAIL", "CSRF token not found")
                return False
            
            csrf_token = csrf_match.group(1)
            
            # Perform login
            login_data = {
                'username': username,
                'password': password,
                'csrfmiddlewaretoken': csrf_token
            }
            
            response = self.session.post(login_url, data=login_data, headers={
                'Referer': login_url
            })
            
            if response.status_code in [200, 302]:
                # Check if we're redirected or see dashboard content
                if 'dashboard' in response.text.lower() or response.status_code == 302:
                    self.log_test("Authentication", "PASS", f"Successfully logged in as {username}")
                    return True
            
            self.log_test("Authentication", "FAIL", f"Login failed: {response.status_code}")
            return False
            
        except Exception as e:
            self.log_test("Authentication", "FAIL", f"Authentication error: {str(e)}")
            return False
    
    def test_fabric_detail_page_accessibility(self):
        """Test basic fabric detail page accessibility"""
        try:
            fabric_url = urljoin(self.base_url, f'/plugins/hedgehog/fabrics/{self.fabric_id}/')
            response = self.session.get(fabric_url)
            
            if response.status_code == 200:
                self.log_test("Fabric Detail Page Access", "PASS", f"Fabric {self.fabric_id} detail page accessible")
                return response.text
            else:
                self.log_test("Fabric Detail Page Access", "FAIL", f"Page not accessible: {response.status_code}")
                return None
                
        except Exception as e:
            self.log_test("Fabric Detail Page Access", "FAIL", f"Error accessing page: {str(e)}")
            return None
    
    def test_ui_layout_improvements(self, page_content):
        """Test UI layout improvements from UI/UX Specialist Agent"""
        if not page_content:
            self.log_test("UI Layout Check", "SKIP", "No page content available")
            return
        
        # Test 1: Git Configuration section layout
        if "Git Configuration" in page_content:
            self.log_test("Git Configuration Section", "PASS", "Git Configuration section found")
            
            # Check for column layout structure
            if 'col-md-8' in page_content and 'col-md-4' in page_content:
                self.log_test("Column Layout Structure", "PASS", "Bootstrap column structure present")
            else:
                self.log_test("Column Layout Structure", "FAIL", "Column structure not found")
        else:
            self.log_test("Git Configuration Section", "FAIL", "Git Configuration section not found")
        
        # Test 2: CSS classes for readability
        if 'text-info' in page_content:
            self.log_test("Field Label Styling", "PASS", "Field labels use text-info class")
        else:
            self.log_test("Field Label Styling", "WARN", "text-info class not found")
        
        # Test 3: Responsive design elements
        responsive_elements = ['d-grid', 'gap-2', 'text-break', 'btn-outline']
        found_elements = sum(1 for element in responsive_elements if element in page_content)
        
        if found_elements >= len(responsive_elements) * 0.75:  # At least 75% of elements
            self.log_test("Responsive Design Elements", "PASS", f"Found {found_elements}/{len(responsive_elements)} responsive elements")
        else:
            self.log_test("Responsive Design Elements", "WARN", f"Only {found_elements}/{len(responsive_elements)} responsive elements found")
        
        # Test 4: Status indicators
        status_badges = ['badge bg-success', 'badge bg-warning', 'badge bg-danger', 'badge bg-secondary']
        found_badges = sum(1 for badge in status_badges if badge in page_content)
        
        if found_badges > 0:
            self.log_test("Status Badge Styling", "PASS", f"Found {found_badges} status badge types")
        else:
            self.log_test("Status Badge Styling", "FAIL", "No status badges found")
    
    def test_backend_functionality(self):
        """Test backend functionality improvements from Backend Developer Agent"""
        
        # Test 1: Fabric edit page accessibility
        try:
            edit_url = urljoin(self.base_url, f'/plugins/hedgehog/fabrics/{self.fabric_id}/edit/')
            response = self.session.get(edit_url)
            
            if response.status_code == 200:
                self.log_test("Fabric Edit Page Access", "PASS", "Edit page accessible")
                edit_content = response.text
                
                # Test 2: Sync interval field presence
                if 'sync_interval' in edit_content:
                    self.log_test("Sync Interval Field", "PASS", "Sync interval field found in form")
                else:
                    self.log_test("Sync Interval Field", "FAIL", "Sync interval field not found")
                
                # Test 3: Form validation elements
                form_elements = ['form-control', 'required', 'min-value', 'max-value']
                found_form_elements = sum(1 for element in form_elements if element in edit_content)
                
                if found_form_elements >= 2:
                    self.log_test("Form Validation Elements", "PASS", f"Found {found_form_elements} form elements")
                else:
                    self.log_test("Form Validation Elements", "WARN", f"Limited form elements: {found_form_elements}")
                    
            else:
                self.log_test("Fabric Edit Page Access", "FAIL", f"Edit page not accessible: {response.status_code}")
                
        except Exception as e:
            self.log_test("Fabric Edit Page Access", "FAIL", f"Error accessing edit page: {str(e)}")
    
    def test_status_consistency(self, page_content):
        """Test status field consistency"""
        if not page_content:
            self.log_test("Status Consistency Check", "SKIP", "No page content available")
            return
        
        # Look for status-related elements
        status_indicators = []
        
        if 'data-sync-status' in page_content:
            status_indicators.append("Sync Status")
        if 'data-connection-status' in page_content:
            status_indicators.append("Connection Status")
        
        if len(status_indicators) >= 2:
            self.log_test("Status Field Indicators", "PASS", f"Found status indicators: {', '.join(status_indicators)}")
        else:
            self.log_test("Status Field Indicators", "WARN", f"Limited status indicators: {len(status_indicators)}")
        
        # Check for logical status combinations
        contradictory_patterns = [
            ('In Sync', 'Disconnected'),
            ('Synced', 'Never synchronized'),
            ('Connected', 'Not configured')
        ]
        
        contradictions_found = []
        for pattern1, pattern2 in contradictory_patterns:
            if pattern1.lower() in page_content.lower() and pattern2.lower() in page_content.lower():
                contradictions_found.append(f"{pattern1} + {pattern2}")
        
        if contradictions_found:
            self.log_test("Status Logic Consistency", "WARN", f"Potential contradictions: {', '.join(contradictions_found)}")
        else:
            self.log_test("Status Logic Consistency", "PASS", "No obvious status contradictions detected")
    
    def test_sync_functionality(self):
        """Test sync functionality"""
        try:
            # Look for sync-related JavaScript functions or endpoints
            fabric_url = urljoin(self.base_url, f'/plugins/hedgehog/fabrics/{self.fabric_id}/')
            response = self.session.get(fabric_url)
            
            if response.status_code == 200:
                content = response.text
                
                # Check for sync-related JavaScript functions
                sync_functions = ['triggerSync', 'syncFromFabric', 'testConnection']
                found_functions = [func for func in sync_functions if func in content]
                
                if len(found_functions) >= 2:
                    self.log_test("Sync JavaScript Functions", "PASS", f"Found functions: {', '.join(found_functions)}")
                else:
                    self.log_test("Sync JavaScript Functions", "WARN", f"Limited functions: {', '.join(found_functions)}")
                
                # Check for sync interval display
                if 'sync_interval' in content or 'interval' in content.lower():
                    self.log_test("Sync Interval Display", "PASS", "Sync interval referenced on page")
                else:
                    self.log_test("Sync Interval Display", "FAIL", "No sync interval display found")
                    
        except Exception as e:
            self.log_test("Sync Functionality Test", "FAIL", f"Error testing sync functionality: {str(e)}")
    
    def test_performance_metrics(self):
        """Test basic performance metrics"""
        try:
            fabric_url = urljoin(self.base_url, f'/plugins/hedgehog/fabrics/{self.fabric_id}/')
            
            # Measure page load time
            start_time = time.time()
            response = self.session.get(fabric_url)
            load_time = time.time() - start_time
            
            if response.status_code == 200:
                page_size = len(response.content)
                
                # Performance thresholds
                if load_time < 3.0:  # Under 3 seconds
                    self.log_test("Page Load Performance", "PASS", f"Load time: {load_time:.2f}s")
                elif load_time < 5.0:  # Under 5 seconds
                    self.log_test("Page Load Performance", "WARN", f"Slow load time: {load_time:.2f}s")
                else:
                    self.log_test("Page Load Performance", "FAIL", f"Very slow load time: {load_time:.2f}s")
                
                # Page size check
                if page_size < 500000:  # Under 500KB
                    self.log_test("Page Size", "PASS", f"Page size: {page_size/1024:.1f}KB")
                else:
                    self.log_test("Page Size", "WARN", f"Large page size: {page_size/1024:.1f}KB")
                    
        except Exception as e:
            self.log_test("Performance Test", "FAIL", f"Performance test error: {str(e)}")
    
    def test_css_integration(self):
        """Test CSS file integration"""
        try:
            css_url = urljoin(self.base_url, '/static/netbox_hedgehog/css/hedgehog.css')
            response = self.session.get(css_url)
            
            if response.status_code == 200:
                self.log_test("CSS File Access", "PASS", "Hedgehog CSS file accessible")
                
                css_content = response.text
                
                # Check for specific CSS improvements mentioned in specs
                css_improvements = ['.badge', '.text-info', '.col-md-', 'responsive', 'contrast']
                found_improvements = sum(1 for improvement in css_improvements if improvement in css_content)
                
                if found_improvements >= 3:
                    self.log_test("CSS Improvements", "PASS", f"Found {found_improvements} CSS improvement indicators")
                else:
                    self.log_test("CSS Improvements", "WARN", f"Limited CSS improvements: {found_improvements}")
                    
            else:
                self.log_test("CSS File Access", "FAIL", f"CSS file not accessible: {response.status_code}")
                
        except Exception as e:
            self.log_test("CSS Integration Test", "FAIL", f"CSS test error: {str(e)}")
    
    def generate_report(self):
        """Generate comprehensive test report"""
        print("\n" + "="*80)
        print("HEDGEHOG NETBOX PLUGIN - INTEGRATION TEST REPORT")
        print("="*80)
        
        # Summary statistics
        total_tests = len(self.test_results)
        passed = sum(1 for result in self.test_results if result['status'] == 'PASS')
        failed = sum(1 for result in self.test_results if result['status'] == 'FAIL')
        warnings = sum(1 for result in self.test_results if result['status'] == 'WARN')
        skipped = sum(1 for result in self.test_results if result['status'] == 'SKIP')
        
        print(f"\nTEST SUMMARY:")
        print(f"Total Tests: {total_tests}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"⚠️  Warnings: {warnings}")
        print(f"⏭️  Skipped: {skipped}")
        print(f"Success Rate: {(passed/total_tests*100):.1f}%")
        
        # Categorized results
        categories = {
            "UI/UX Validation": ["Git Configuration", "Column Layout", "Field Label", "Responsive", "Status Badge"],
            "Backend Functionality": ["Fabric Edit", "Sync Interval", "Form Validation"],
            "Status Consistency": ["Status Field", "Status Logic"],
            "Sync Functionality": ["Sync JavaScript", "Sync Interval Display"],
            "Performance": ["Page Load", "Page Size"],
            "Integration": ["CSS File", "CSS Improvements"]
        }
        
        print("\nDETAILED RESULTS BY CATEGORY:")
        print("-" * 50)
        
        for category, keywords in categories.items():
            print(f"\n{category}:")
            category_tests = [result for result in self.test_results 
                            if any(keyword.lower() in result['test'].lower() for keyword in keywords)]
            
            for test in category_tests:
                status_symbol = "✅" if test['status'] == "PASS" else "❌" if test['status'] == "FAIL" else "⚠️" if test['status'] == "WARN" else "⏭️"
                print(f"  {status_symbol} {test['test']}: {test['status']}")
                if test['details']:
                    print(f"    └── {test['details']}")
        
        # Production readiness assessment
        print("\n" + "="*80)
        print("PRODUCTION READINESS ASSESSMENT")
        print("="*80)
        
        critical_failures = [result for result in self.test_results 
                           if result['status'] == 'FAIL' and 
                           any(critical in result['test'].lower() for critical in 
                               ['access', 'authentication', 'fabric detail', 'sync interval'])]
        
        if not critical_failures:
            if failed == 0:
                print("🎉 PRODUCTION READY: All tests passed successfully!")
                recommendation = "DEPLOY"
            elif failed <= 2 and warnings <= 3:
                print("✅ PRODUCTION READY: Minor issues detected but deployment safe")
                recommendation = "DEPLOY WITH MONITORING"
            else:
                print("⚠️  PRODUCTION CAUTION: Multiple issues require attention")
                recommendation = "DEPLOY WITH FIXES"
        else:
            print("❌ NOT PRODUCTION READY: Critical failures detected")
            recommendation = "DO NOT DEPLOY"
        
        print(f"Recommendation: {recommendation}")
        
        # Save detailed results to file
        report_file = Path("/home/ubuntu/cc/hedgehog-netbox-plugin/tests/integration_test_report.json")
        with open(report_file, 'w') as f:
            json.dump({
                'summary': {
                    'total_tests': total_tests,
                    'passed': passed,
                    'failed': failed,
                    'warnings': warnings,
                    'skipped': skipped,
                    'success_rate': passed/total_tests*100,
                    'recommendation': recommendation
                },
                'test_results': self.test_results,
                'timestamp': time.strftime("%Y-%m-%d %H:%M:%S")
            }, f, indent=2)
        
        print(f"\nDetailed results saved to: {report_file}")
        
        return recommendation == "DEPLOY" or recommendation == "DEPLOY WITH MONITORING"

def main():
    """Main test execution"""
    print("Starting Hedgehog NetBox Plugin Integration Testing...")
    print("="*60)
    
    tester = NetBoxIntegrationTester()
    
    # Phase 1: Authentication and basic access
    print("\nPhase 1: Environment Setup and Authentication")
    print("-" * 40)
    
    if not tester.authenticate():
        print("❌ Authentication failed - cannot proceed with tests")
        return False
    
    # Phase 2: Core functionality testing
    print("\nPhase 2: Core Functionality Testing")
    print("-" * 40)
    
    page_content = tester.test_fabric_detail_page_accessibility()
    tester.test_backend_functionality()
    
    # Phase 3: UI/UX validation
    print("\nPhase 3: UI/UX Validation")
    print("-" * 40)
    
    tester.test_ui_layout_improvements(page_content)
    tester.test_status_consistency(page_content)
    
    # Phase 4: Integration testing
    print("\nPhase 4: Integration Testing")
    print("-" * 40)
    
    tester.test_sync_functionality()
    tester.test_css_integration()
    
    # Phase 5: Performance testing
    print("\nPhase 5: Performance Testing")
    print("-" * 40)
    
    tester.test_performance_metrics()
    
    # Generate comprehensive report
    success = tester.generate_report()
    
    return success

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest execution interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nUnexpected error during testing: {str(e)}")
        sys.exit(1)