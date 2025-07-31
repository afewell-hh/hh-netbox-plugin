#!/usr/bin/env python3
"""
MANUAL BUTTON FUNCTIONALITY VERIFICATION
=======================================

This script performs detailed verification of specific button functionality
issues identified in the comprehensive analysis.

Focus Areas:
1. Test Connection Button - Does it actually test connectivity?
2. Sync Now Button - Does it trigger real sync operations?
3. Status refresh - Do status indicators update?
4. Form submission - Does editing actually change detail page?
"""

import requests
import re
import json
import time
from datetime import datetime


class ButtonFunctionalityVerifier:
    """Verify specific button functionality issues"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.timeout = 15
        self.authenticated = False
        
    def authenticate(self) -> bool:
        """Authenticate with NetBox"""
        try:
            # Get login page and CSRF token
            login_response = self.session.get(f"{self.base_url}/login/")
            if login_response.status_code != 200:
                return False
                
            # Extract CSRF token
            csrf_match = re.search(r'name=["\']csrfmiddlewaretoken["\'] value=["\']([^"\']+)["\']', login_response.text)
            if not csrf_match:
                csrf_match = re.search(r'csrfmiddlewaretoken["\'] value=["\']([^"\']+)["\']', login_response.text)
            
            if not csrf_match:
                return False
            
            csrf_token = csrf_match.group(1)
            
            # Perform login
            login_data = {
                'username': 'admin',
                'password': 'admin', 
                'csrfmiddlewaretoken': csrf_token,
                'next': '/'
            }
            
            login_headers = {
                'Referer': f"{self.base_url}/login/",
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-CSRFToken': csrf_token
            }
            
            login_post = self.session.post(
                f"{self.base_url}/login/",
                data=login_data,
                headers=login_headers,
                allow_redirects=True
            )
            
            # Verify authentication
            test_response = self.session.get(f"{self.base_url}/plugins/hedgehog/fabrics/")
            self.authenticated = "netbox-url-name=\"login\"" not in test_response.text
            return self.authenticated
                
        except Exception as e:
            print(f"❌ Authentication error: {e}")
            return False
    
    def get_csrf_token(self, page_content: str) -> str:
        """Extract CSRF token from page content"""
        csrf_match = re.search(r'name=["\']csrfmiddlewaretoken["\'] value=["\']([^"\']+)["\']', page_content)
        if not csrf_match:
            csrf_match = re.search(r'csrfmiddlewaretoken["\'] value=["\']([^"\']+)["\']', page_content)
        return csrf_match.group(1) if csrf_match else None
    
    def test_connection_button_detailed(self, fabric_id: str = "12") -> dict:
        """Detailed test of Test Connection button functionality"""
        print(f"\n🔍 DETAILED TEST CONNECTION BUTTON ANALYSIS (Fabric {fabric_id})")
        print("-" * 60)
        
        results = {
            'button_present': False,
            'endpoint_exists': False,
            'endpoint_response': None,
            'response_data': None,
            'actually_tests_connection': False,
            'error_details': []
        }
        
        try:
            # 1. Check if button is present on detail page
            detail_response = self.session.get(f"{self.base_url}/plugins/hedgehog/fabrics/{fabric_id}/")
            if detail_response.status_code != 200:
                results['error_details'].append(f"Cannot access detail page: HTTP {detail_response.status_code}")
                return results
            
            # Look for test connection button/functionality
            detail_content = detail_response.text
            test_connection_patterns = [
                r'test[_\s-]*connection',
                r'connection[_\s-]*test',
                r'test[_\s-]*k8s',
                r'test[_\s-]*kubernetes',
                r'validate[_\s-]*connection'
            ]
            
            button_found = False
            for pattern in test_connection_patterns:
                if re.search(pattern, detail_content, re.IGNORECASE):
                    button_found = True
                    print(f"   ✓ Found test connection pattern: {pattern}")
                    break
            
            results['button_present'] = button_found
            
            if not button_found:
                results['error_details'].append("Test Connection button/functionality not found on page")
                print("   ❌ Test Connection button not found on detail page")
                return results
            
            # 2. Try various possible endpoints for test connection
            csrf_token = self.get_csrf_token(detail_content)
            if not csrf_token:
                results['error_details'].append("CSRF token not found")
                return results
            
            possible_endpoints = [
                f"/plugins/hedgehog/fabrics/{fabric_id}/test-connection/",
                f"/plugins/hedgehog/fabrics/{fabric_id}/test_connection/", 
                f"/plugins/hedgehog/fabrics/{fabric_id}/connection-test/",
                f"/plugins/hedgehog/api/fabrics/{fabric_id}/test-connection/",
                f"/plugins/hedgehog/test-connection/{fabric_id}/",
            ]
            
            headers = {
                'X-CSRFToken': csrf_token,
                'Content-Type': 'application/json',
                'Referer': f"{self.base_url}/plugins/hedgehog/fabrics/{fabric_id}/"
            }
            
            for endpoint in possible_endpoints:
                try:
                    print(f"   🔍 Testing endpoint: {endpoint}")
                    response = self.session.post(f"{self.base_url}{endpoint}", headers=headers, json={})
                    
                    print(f"      Response: HTTP {response.status_code}")
                    
                    if response.status_code == 404:
                        print(f"      ❌ Endpoint not found")
                        continue
                    elif response.status_code == 405:
                        print(f"      ⚠️ Method not allowed (endpoint exists but wrong method)")
                        results['endpoint_exists'] = True
                        continue
                    elif response.status_code in [200, 201, 400, 403, 500]:
                        print(f"      ✓ Endpoint exists and responds")
                        results['endpoint_exists'] = True
                        results['endpoint_response'] = response.status_code
                        
                        # Try to parse response
                        try:
                            if response.headers.get('content-type', '').startswith('application/json'):
                                results['response_data'] = response.json()
                                print(f"      📋 JSON Response: {json.dumps(results['response_data'], indent=2)}")
                            else:
                                results['response_data'] = response.text[:200]
                                print(f"      📋 Text Response: {results['response_data']}")
                        except:
                            pass
                        
                        # Check if response indicates actual connection testing
                        response_text = response.text.lower()
                        connection_indicators = [
                            'cluster', 'kubernetes', 'k8s', 'connection', 'connectivity', 
                            'api server', 'ping', 'health', 'status', 'version'
                        ]
                        
                        for indicator in connection_indicators:
                            if indicator in response_text:
                                results['actually_tests_connection'] = True
                                print(f"      ✅ Response contains connection testing indicator: {indicator}")
                                break
                        
                        break
                        
                except Exception as e:
                    print(f"      ❌ Error testing endpoint: {e}")
                    continue
            
            if not results['endpoint_exists']:
                results['error_details'].append("No functional test connection endpoint found")
            
        except Exception as e:
            results['error_details'].append(f"Test failed: {str(e)}")
            print(f"   ❌ Test failed: {e}")
        
        return results
    
    def test_sync_button_detailed(self, fabric_id: str = "12") -> dict:
        """Detailed test of Sync button functionality"""
        print(f"\n🔄 DETAILED SYNC BUTTON ANALYSIS (Fabric {fabric_id})")
        print("-" * 60)
        
        results = {
            'button_present': False,
            'endpoint_exists': False, 
            'endpoint_response': None,
            'response_data': None,
            'actually_syncs': False,
            'sync_type_tested': None,
            'error_details': []
        }
        
        try:
            # 1. Check for sync button on detail page
            detail_response = self.session.get(f"{self.base_url}/plugins/hedgehog/fabrics/{fabric_id}/")
            if detail_response.status_code != 200:
                results['error_details'].append(f"Cannot access detail page: HTTP {detail_response.status_code}")
                return results
            
            detail_content = detail_response.text
            sync_patterns = [
                r'sync[_\s-]*now',
                r'sync[_\s-]*from',
                r'synchroniz',
                r'refresh[_\s-]*data',
                r'update[_\s-]*from'
            ]
            
            button_found = False
            for pattern in sync_patterns:
                if re.search(pattern, detail_content, re.IGNORECASE):
                    button_found = True
                    print(f"   ✓ Found sync pattern: {pattern}")
                    break
            
            results['button_present'] = button_found
            
            if not button_found:
                results['error_details'].append("Sync button not found on page")
                print("   ❌ Sync button not found on detail page")
                return results
            
            # 2. Try sync endpoints
            csrf_token = self.get_csrf_token(detail_content)
            if not csrf_token:
                results['error_details'].append("CSRF token not found")
                return results
            
            possible_sync_endpoints = [
                f"/plugins/hedgehog/fabrics/{fabric_id}/sync/",
                f"/plugins/hedgehog/fabrics/{fabric_id}/sync-now/",
                f"/plugins/hedgehog/api/fabrics/{fabric_id}/sync/",
                f"/plugins/hedgehog/sync/{fabric_id}/",
            ]
            
            headers = {
                'X-CSRFToken': csrf_token,
                'Content-Type': 'application/json',
                'Referer': f"{self.base_url}/plugins/hedgehog/fabrics/{fabric_id}/"
            }
            
            # Test different sync types
            sync_payloads = [
                {'sync_type': 'kubernetes'},
                {'sync_type': 'git'},
                {'sync_type': 'full'},
                {},  # Empty payload
                {'action': 'sync'}
            ]
            
            for endpoint in possible_sync_endpoints:
                for payload in sync_payloads:
                    try:
                        print(f"   🔍 Testing endpoint: {endpoint} with payload: {payload}")
                        response = self.session.post(f"{self.base_url}{endpoint}", headers=headers, json=payload)
                        
                        print(f"      Response: HTTP {response.status_code}")
                        
                        if response.status_code == 404:
                            continue
                        elif response.status_code == 405:
                            results['endpoint_exists'] = True
                            continue
                        elif response.status_code in [200, 201, 400, 403, 500]:
                            results['endpoint_exists'] = True
                            results['endpoint_response'] = response.status_code
                            results['sync_type_tested'] = payload.get('sync_type', 'default')
                            
                            # Try to parse response
                            try:
                                if response.headers.get('content-type', '').startswith('application/json'):
                                    results['response_data'] = response.json()
                                    print(f"      📋 JSON Response: {json.dumps(results['response_data'], indent=2)}")
                                else:
                                    results['response_data'] = response.text[:200]
                                    print(f"      📋 Text Response: {results['response_data']}")
                            except:
                                pass
                            
                            # Check if response indicates actual sync operation
                            response_text = response.text.lower()
                            sync_indicators = [
                                'sync', 'synchroniz', 'reconcil', 'import', 'fetch', 
                                'kubernetes', 'cluster', 'git', 'repository', 'crd'
                            ]
                            
                            for indicator in sync_indicators:
                                if indicator in response_text:
                                    results['actually_syncs'] = True
                                    print(f"      ✅ Response contains sync indicator: {indicator}")
                                    break
                            
                            # If we got a successful response, use this endpoint
                            if response.status_code in [200, 201]:
                                break
                            
                    except Exception as e:
                        print(f"      ❌ Error testing endpoint: {e}")
                        continue
                
                if results['endpoint_exists']:
                    break
            
            if not results['endpoint_exists']:
                results['error_details'].append("No functional sync endpoint found")
                
        except Exception as e:
            results['error_details'].append(f"Test failed: {str(e)}")
            print(f"   ❌ Test failed: {e}")
        
        return results
    
    def test_form_to_detail_consistency(self, fabric_id: str = "12") -> dict:
        """Test if editing a fabric actually updates the detail page"""
        print(f"\n📝 FORM-TO-DETAIL CONSISTENCY TEST (Fabric {fabric_id})")
        print("-" * 60)
        
        results = {
            'can_access_edit_form': False,
            'can_get_original_data': False,
            'can_submit_changes': False,
            'changes_reflected': False,
            'original_description': None,
            'modified_description': None,
            'final_description': None,
            'error_details': []
        }
        
        try:
            # 1. Get original detail page data
            detail_response = self.session.get(f"{self.base_url}/plugins/hedgehog/fabrics/{fabric_id}/")
            if detail_response.status_code != 200:
                results['error_details'].append("Cannot access detail page")
                return results
            
            results['can_get_original_data'] = True
            
            # Extract current description
            detail_content = detail_response.text
            desc_patterns = [
                r'description[^>]*>([^<]+)<',
                r'<p[^>]*>([^<]+)</p>',
                r'Form Test - Edit Verification ([^<]+)'
            ]
            
            for pattern in desc_patterns:
                match = re.search(pattern, detail_content, re.IGNORECASE)
                if match and len(match.group(1).strip()) > 5:
                    results['original_description'] = match.group(1).strip()
                    break
            
            print(f"   📄 Original description: {results['original_description']}")
            
            # 2. Access edit form
            edit_response = self.session.get(f"{self.base_url}/plugins/hedgehog/fabrics/{fabric_id}/edit/")
            if edit_response.status_code != 200:
                results['error_details'].append(f"Cannot access edit form: HTTP {edit_response.status_code}")
                return results
            
            results['can_access_edit_form'] = True
            edit_content = edit_response.text
            
            # 3. Submit modified data
            csrf_token = self.get_csrf_token(edit_content)
            if not csrf_token:
                results['error_details'].append("CSRF token not found in edit form")
                return results
            
            # Create unique test description
            timestamp = datetime.now().strftime("%H:%M:%S")
            test_description = f"Form Test - Edit Verification {timestamp}"
            results['modified_description'] = test_description
            
            # Extract current form values
            name_match = re.search(r'name="name"[^>]*value="([^"]*)"', edit_content)
            current_name = name_match.group(1) if name_match else f"test-fabric-{fabric_id}"
            
            form_data = {
                'csrfmiddlewaretoken': csrf_token,
                'name': current_name,
                'description': test_description,
                'status': 'active',
                'connection_status': 'connected',
                'sync_status': 'error',
                'kubernetes_namespace': 'default',
                'sync_enabled': 'on',
                'sync_interval': '300'
            }
            
            headers = {
                'X-CSRFToken': csrf_token,
                'Content-Type': 'application/x-www-form-urlencoded',
                'Referer': f"{self.base_url}/plugins/hedgehog/fabrics/{fabric_id}/edit/"
            }
            
            print(f"   📝 Submitting modified description: {test_description}")
            
            submit_response = self.session.post(
                f"{self.base_url}/plugins/hedgehog/fabrics/{fabric_id}/edit/",
                data=form_data,
                headers=headers,
                allow_redirects=True
            )
            
            results['can_submit_changes'] = submit_response.status_code in [200, 201, 302]
            print(f"   📤 Form submission result: HTTP {submit_response.status_code}")
            
            if not results['can_submit_changes']:
                results['error_details'].append(f"Form submission failed: HTTP {submit_response.status_code}")
                return results
            
            # 4. Check if changes are reflected on detail page
            time.sleep(1)  # Brief pause to ensure changes are saved
            
            updated_detail_response = self.session.get(f"{self.base_url}/plugins/hedgehog/fabrics/{fabric_id}/")
            if updated_detail_response.status_code != 200:
                results['error_details'].append("Cannot access detail page after edit")
                return results
            
            updated_content = updated_detail_response.text
            
            # Check if our test description appears
            if test_description in updated_content:
                results['changes_reflected'] = True
                results['final_description'] = test_description
                print(f"   ✅ Changes successfully reflected on detail page")
            else:
                # Try to find any description on the updated page
                for pattern in desc_patterns:
                    match = re.search(pattern, updated_content, re.IGNORECASE)
                    if match:
                        results['final_description'] = match.group(1).strip()
                        break
                
                print(f"   ❌ Changes not reflected. Expected: {test_description}")
                print(f"       Found: {results['final_description']}")
                results['error_details'].append("Form changes not reflected on detail page")
                
        except Exception as e:
            results['error_details'].append(f"Test failed: {str(e)}")
            print(f"   ❌ Test failed: {e}")
        
        return results
    
    def run_detailed_verification(self) -> dict:
        """Run all detailed verification tests"""
        print("🔍 STARTING DETAILED BUTTON FUNCTIONALITY VERIFICATION")
        print("=" * 70)
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)
        
        if not self.authenticate():
            return {'error': 'Authentication failed'}
        
        results = {
            'timestamp': datetime.now().isoformat(),
            'test_connection_analysis': {},
            'sync_button_analysis': {},
            'form_consistency_analysis': {},
            'summary': {}
        }
        
        # Test connection button
        results['test_connection_analysis'] = self.test_connection_button_detailed()
        
        # Test sync button  
        results['sync_button_analysis'] = self.test_sync_button_detailed()
        
        # Test form consistency
        results['form_consistency_analysis'] = self.test_form_to_detail_consistency()
        
        # Generate summary
        results['summary'] = {
            'test_connection_functional': results['test_connection_analysis'].get('actually_tests_connection', False),
            'sync_button_functional': results['sync_button_analysis'].get('actually_syncs', False),
            'form_consistency_functional': results['form_consistency_analysis'].get('changes_reflected', False),
            'critical_issues': [],
            'recommendations': []
        }
        
        # Add recommendations
        if not results['summary']['test_connection_functional']:
            if results['test_connection_analysis'].get('button_present', False):
                results['summary']['recommendations'].append("Test Connection button is present but not functional - check endpoint implementation")
            else:
                results['summary']['recommendations'].append("Test Connection functionality missing entirely")
        
        if not results['summary']['sync_button_functional']:
            if results['sync_button_analysis'].get('button_present', False):
                results['summary']['recommendations'].append("Sync button is present but not functional - check endpoint implementation")
            else:
                results['summary']['recommendations'].append("Sync functionality missing entirely")
        
        if not results['summary']['form_consistency_functional']:
            results['summary']['recommendations'].append("Form editing does not update detail page - check form submission and data persistence")
        
        return results
    
    def print_verification_summary(self, results: dict):
        """Print verification summary"""
        print("\n" + "=" * 70)
        print("📊 DETAILED BUTTON FUNCTIONALITY VERIFICATION SUMMARY")
        print("=" * 70)
        
        summary = results.get('summary', {})
        
        print(f"🔘 Test Connection Button: {'✅ FUNCTIONAL' if summary.get('test_connection_functional') else '❌ NOT FUNCTIONAL'}")
        print(f"🔄 Sync Button: {'✅ FUNCTIONAL' if summary.get('sync_button_functional') else '❌ NOT FUNCTIONAL'}")
        print(f"📝 Form Consistency: {'✅ FUNCTIONAL' if summary.get('form_consistency_functional') else '❌ NOT FUNCTIONAL'}")
        
        # Test Connection Details
        conn_analysis = results.get('test_connection_analysis', {})
        print(f"\n🔘 TEST CONNECTION DETAILS:")
        print(f"   Button Present: {conn_analysis.get('button_present', False)}")
        print(f"   Endpoint Exists: {conn_analysis.get('endpoint_exists', False)}")
        print(f"   Actually Tests Connection: {conn_analysis.get('actually_tests_connection', False)}")
        if conn_analysis.get('error_details'):
            print(f"   Errors: {'; '.join(conn_analysis['error_details'])}")
        
        # Sync Details
        sync_analysis = results.get('sync_button_analysis', {})
        print(f"\n🔄 SYNC BUTTON DETAILS:")
        print(f"   Button Present: {sync_analysis.get('button_present', False)}")
        print(f"   Endpoint Exists: {sync_analysis.get('endpoint_exists', False)}")
        print(f"   Actually Syncs: {sync_analysis.get('actually_syncs', False)}")
        print(f"   Sync Type Tested: {sync_analysis.get('sync_type_tested', 'None')}")
        if sync_analysis.get('error_details'):
            print(f"   Errors: {'; '.join(sync_analysis['error_details'])}")
        
        # Form Consistency Details
        form_analysis = results.get('form_consistency_analysis', {})
        print(f"\n📝 FORM CONSISTENCY DETAILS:")
        print(f"   Edit Form Accessible: {form_analysis.get('can_access_edit_form', False)}")
        print(f"   Can Submit Changes: {form_analysis.get('can_submit_changes', False)}")
        print(f"   Changes Reflected: {form_analysis.get('changes_reflected', False)}")
        print(f"   Original Description: {form_analysis.get('original_description', 'Not found')}")
        print(f"   Final Description: {form_analysis.get('final_description', 'Not found')}")
        if form_analysis.get('error_details'):
            print(f"   Errors: {'; '.join(form_analysis['error_details'])}")
        
        # Recommendations
        recommendations = summary.get('recommendations', [])
        if recommendations:
            print(f"\n🎯 RECOMMENDATIONS:")
            for i, rec in enumerate(recommendations, 1):
                print(f"   {i}. {rec}")
        
        print(f"\n⏱️ Verification completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)


def main():
    """Main execution function"""
    verifier = ButtonFunctionalityVerifier()
    
    try:
        results = verifier.run_detailed_verification()
        verifier.print_verification_summary(results)
        
        # Save results
        output_file = f"button_verification_results_{int(time.time())}.json"
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\n💾 Detailed results saved to: {output_file}")
        
        # Return exit code based on functionality
        summary = results.get('summary', {})
        functional_count = sum([
            summary.get('test_connection_functional', False),
            summary.get('sync_button_functional', False),
            summary.get('form_consistency_functional', False)
        ])
        
        if functional_count == 3:
            print("🎉 ALL BUTTON FUNCTIONALITY WORKING!")
            return 0
        elif functional_count >= 2:
            print("⚠️ MOST FUNCTIONALITY WORKING - minor issues detected")
            return 1
        else:
            print("❌ SIGNIFICANT FUNCTIONALITY ISSUES DETECTED")
            return 2
            
    except Exception as e:
        print(f"❌ VERIFICATION FAILED: {e}")
        return 3


if __name__ == "__main__":
    exit(main())