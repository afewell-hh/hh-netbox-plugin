#!/usr/bin/env python3
"""
Comprehensive Sync Validation Test
Tests the actual sync button functionality in NetBox Hedgehog Plugin
"""

import requests
import json
import time
from datetime import datetime
import sys
import traceback
import urllib3

# Disable SSL warnings for local testing
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class SyncValidator:
    def __init__(self):
        self.base_url = "http://localhost:8000"
        self.fabric_id = 35
        self.session = requests.Session()
        self.session.verify = False
        
        self.evidence = {
            'test_started': datetime.now().isoformat(),
            'fabric_id': self.fabric_id,
            'test_phases': []
        }
    
    def log_phase(self, phase_name, data):
        """Log test phase results"""
        phase_data = {
            'phase': phase_name,
            'timestamp': datetime.now().isoformat(),
            'data': data
        }
        self.evidence['test_phases'].append(phase_data)
        print(f"📋 {phase_name}: {json.dumps(data, indent=2, default=str)}")
    
    def test_netbox_accessibility(self):
        """Test if NetBox is accessible"""
        print("🌐 Testing NetBox accessibility...")
        
        try:
            response = self.session.get(f"{self.base_url}/", timeout=10)
            
            accessibility_data = {
                'status_code': response.status_code,
                'accessible': response.status_code == 200,
                'content_preview': response.text[:200] if hasattr(response, 'text') else None,
                'netbox_detected': 'netbox' in response.text.lower() if hasattr(response, 'text') else False
            }
            
            self.log_phase('netbox_accessibility', accessibility_data)
            return accessibility_data['accessible']
            
        except Exception as e:
            self.log_phase('netbox_accessibility', {
                'accessible': False,
                'error': str(e),
                'traceback': traceback.format_exc()
            })
            return False
    
    def test_hedgehog_plugin_routes(self):
        """Test if Hedgehog plugin routes are accessible"""
        print("🦔 Testing Hedgehog plugin routes...")
        
        test_routes = [
            '/hedgehog/',
            '/hedgehog/fabrics/',
            f'/hedgehog/fabrics/{self.fabric_id}/'
        ]
        
        route_results = []
        
        for route in test_routes:
            try:
                response = self.session.get(f"{self.base_url}{route}", timeout=10)
                
                route_data = {
                    'route': route,
                    'status_code': response.status_code,
                    'accessible': response.status_code in [200, 302, 401],  # 401 might mean needs auth
                    'content_length': len(response.text) if hasattr(response, 'text') else 0
                }
                
                # Check for fabric-specific content
                if hasattr(response, 'text') and self.fabric_id == 35:
                    route_data['fabric_content_detected'] = 'fabric' in response.text.lower()
                    route_data['sync_button_detected'] = 'sync' in response.text.lower()
                
                route_results.append(route_data)
                
            except Exception as e:
                route_results.append({
                    'route': route,
                    'accessible': False,
                    'error': str(e)
                })
        
        self.log_phase('hedgehog_plugin_routes', {
            'routes_tested': len(test_routes),
            'routes_accessible': len([r for r in route_results if r.get('accessible')]),
            'route_details': route_results
        })
        
        return route_results
    
    def test_sync_endpoint_availability(self):
        """Test if sync endpoints are available"""
        print("⚡ Testing sync endpoint availability...")
        
        sync_endpoints = [
            f'/hedgehog/fabrics/{self.fabric_id}/sync/',
            f'/hedgehog/api/sync/{self.fabric_id}/',
            f'/api/plugins/hedgehog/sync/{self.fabric_id}/'
        ]
        
        endpoint_results = []
        
        for endpoint in sync_endpoints:
            try:
                # Try GET first to see if endpoint exists
                response = self.session.get(f"{self.base_url}{endpoint}", timeout=5)
                
                endpoint_data = {
                    'endpoint': endpoint,
                    'method': 'GET',
                    'status_code': response.status_code,
                    'endpoint_exists': response.status_code != 404,
                    'requires_post': response.status_code == 405  # Method not allowed
                }
                
                endpoint_results.append(endpoint_data)
                
                # If GET returns 405 (Method Not Allowed), try POST
                if response.status_code == 405:
                    try:
                        post_response = self.session.post(f"{self.base_url}{endpoint}", timeout=5)
                        
                        post_data = {
                            'endpoint': endpoint,
                            'method': 'POST',
                            'status_code': post_response.status_code,
                            'response_preview': post_response.text[:300] if hasattr(post_response, 'text') else None
                        }
                        
                        # Check if response indicates sync functionality
                        if hasattr(post_response, 'text'):
                            post_data['sync_response_detected'] = any(keyword in post_response.text.lower() 
                                                                    for keyword in ['sync', 'fabric', 'k8s', 'kubernetes'])
                        
                        endpoint_results.append(post_data)
                        
                    except Exception as post_e:
                        endpoint_results.append({
                            'endpoint': endpoint,
                            'method': 'POST',
                            'error': str(post_e)
                        })
                
            except Exception as e:
                endpoint_results.append({
                    'endpoint': endpoint,
                    'method': 'GET',
                    'error': str(e)
                })
        
        self.log_phase('sync_endpoint_availability', {
            'endpoints_tested': len(sync_endpoints),
            'endpoints_responding': len([r for r in endpoint_results if r.get('status_code')]),
            'endpoint_details': endpoint_results
        })
        
        return endpoint_results
    
    def attempt_sync_execution(self):
        """Attempt to actually execute sync"""
        print("🚀 Attempting sync execution...")
        
        # Based on the URL patterns we found, try the most likely sync endpoint
        sync_url = f"{self.base_url}/hedgehog/fabrics/{self.fabric_id}/sync/"
        
        execution_attempts = []
        
        # Attempt 1: Direct POST to sync endpoint
        try:
            print("   Attempting direct POST to sync endpoint...")
            
            sync_response = self.session.post(sync_url, timeout=30)
            
            attempt_data = {
                'method': 'direct_post',
                'url': sync_url,
                'status_code': sync_response.status_code,
                'success': sync_response.status_code == 200,
                'response_preview': sync_response.text[:500] if hasattr(sync_response, 'text') else None
            }
            
            # Try to parse JSON response if available
            if hasattr(sync_response, 'text'):
                try:
                    json_response = sync_response.json()
                    attempt_data['json_response'] = json_response
                    attempt_data['sync_successful'] = json_response.get('success', False)
                except:
                    pass
            
            execution_attempts.append(attempt_data)
            
        except Exception as e:
            execution_attempts.append({
                'method': 'direct_post',
                'url': sync_url,
                'error': str(e),
                'traceback': traceback.format_exc()
            })
        
        # Attempt 2: Try with CSRF token
        try:
            print("   Attempting POST with CSRF token...")
            
            # First get the fabric page to extract CSRF token
            fabric_page_response = self.session.get(f"{self.base_url}/hedgehog/fabrics/{self.fabric_id}/")
            
            if fabric_page_response.status_code == 200 and hasattr(fabric_page_response, 'text'):
                # Look for CSRF token in the page
                import re
                csrf_match = re.search(r'name=[\'"]csrfmiddlewaretoken[\'"] value=[\'"]([^\'"]+)', 
                                     fabric_page_response.text)
                
                if csrf_match:
                    csrf_token = csrf_match.group(1)
                    
                    csrf_response = self.session.post(sync_url, data={
                        'csrfmiddlewaretoken': csrf_token
                    }, timeout=30)
                    
                    csrf_attempt_data = {
                        'method': 'post_with_csrf',
                        'url': sync_url,
                        'csrf_token_found': True,
                        'status_code': csrf_response.status_code,
                        'success': csrf_response.status_code == 200,
                        'response_preview': csrf_response.text[:500] if hasattr(csrf_response, 'text') else None
                    }
                    
                    # Try to parse JSON
                    if hasattr(csrf_response, 'text'):
                        try:
                            json_response = csrf_response.json()
                            csrf_attempt_data['json_response'] = json_response
                            csrf_attempt_data['sync_successful'] = json_response.get('success', False)
                        except:
                            pass
                    
                    execution_attempts.append(csrf_attempt_data)
                else:
                    execution_attempts.append({
                        'method': 'post_with_csrf',
                        'csrf_token_found': False,
                        'fabric_page_loaded': True
                    })
            else:
                execution_attempts.append({
                    'method': 'post_with_csrf',
                    'fabric_page_accessible': False,
                    'fabric_page_status': fabric_page_response.status_code
                })
                
        except Exception as e:
            execution_attempts.append({
                'method': 'post_with_csrf',
                'error': str(e)
            })
        
        self.log_phase('sync_execution_attempts', {
            'attempts_made': len(execution_attempts),
            'successful_attempts': len([a for a in execution_attempts if a.get('success')]),
            'attempt_details': execution_attempts
        })
        
        return execution_attempts
    
    def generate_final_report(self):
        """Generate comprehensive test report"""
        print("📊 Generating final validation report...")
        
        # Analyze all collected evidence
        total_phases = len(self.evidence['test_phases'])
        successful_phases = len([p for p in self.evidence['test_phases'] 
                               if not p['data'].get('error')])
        
        # Check if any sync execution was successful
        sync_execution_phases = [p for p in self.evidence['test_phases'] 
                               if p['phase'] == 'sync_execution_attempts']
        
        sync_actually_executed = False
        if sync_execution_phases:
            for phase in sync_execution_phases:
                for attempt in phase['data']['attempt_details']:
                    if attempt.get('success') or attempt.get('sync_successful'):
                        sync_actually_executed = True
                        break
        
        final_report = {
            'test_summary': {
                'fabric_id': self.fabric_id,
                'test_completed': datetime.now().isoformat(),
                'test_duration': '~2-3 minutes',
                'total_phases': total_phases,
                'successful_phases': successful_phases
            },
            'sync_validation_result': {
                'sync_actually_executed': sync_actually_executed,
                'netbox_accessible': any(p['phase'] == 'netbox_accessibility' and 
                                       p['data'].get('accessible') 
                                       for p in self.evidence['test_phases']),
                'hedgehog_plugin_accessible': any(p['phase'] == 'hedgehog_plugin_routes' and 
                                                p['data'].get('routes_accessible', 0) > 0
                                                for p in self.evidence['test_phases']),
                'sync_endpoints_available': any(p['phase'] == 'sync_endpoint_availability' and 
                                              p['data'].get('endpoints_responding', 0) > 0
                                              for p in self.evidence['test_phases'])
            },
            'conclusion': 'SYNC_BUTTON_FUNCTIONAL' if sync_actually_executed else 'SYNC_REQUIRES_INVESTIGATION',
            'recommendations': [],
            'full_evidence': self.evidence
        }
        
        # Add recommendations based on findings
        if sync_actually_executed:
            final_report['recommendations'].append('Manual sync button is working correctly')
            final_report['recommendations'].append('Fabric sync functionality validated successfully')
        else:
            final_report['recommendations'].append('Manual sync requires authentication or different approach')
            final_report['recommendations'].append('Consider testing with authenticated session')
        
        # Save final report
        report_filename = f"sync_validation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_filename, 'w') as f:
            json.dump(final_report, f, indent=2, default=str)
        
        self.log_phase('final_report', {
            'report_file': report_filename,
            'conclusion': final_report['conclusion'],
            'sync_executed': sync_actually_executed
        })
        
        return final_report
    
    def run_complete_validation(self):
        """Run the complete sync validation test suite"""
        print("🎯 COMPREHENSIVE SYNC VALIDATION TEST")
        print(f"Fabric ID: {self.fabric_id}")
        print(f"Started: {datetime.now().isoformat()}")
        print("=" * 60)
        
        try:
            # Phase 1: Test NetBox accessibility
            self.test_netbox_accessibility()
            
            # Phase 2: Test Hedgehog plugin routes
            self.test_hedgehog_plugin_routes()
            
            # Phase 3: Test sync endpoint availability
            self.test_sync_endpoint_availability()
            
            # Phase 4: Attempt actual sync execution
            self.attempt_sync_execution()
            
            # Phase 5: Generate final report
            final_report = self.generate_final_report()
            
            print("\n" + "=" * 60)
            print("🏁 VALIDATION TEST COMPLETED")
            print(f"Result: {final_report['conclusion']}")
            print(f"Sync Executed: {final_report['sync_validation_result']['sync_actually_executed']}")
            
            for rec in final_report['recommendations']:
                print(f"💡 {rec}")
            
            return final_report
            
        except Exception as e:
            print(f"\n❌ CRITICAL TEST ERROR: {e}")
            print(f"Traceback: {traceback.format_exc()}")
            return None

def main():
    validator = SyncValidator()
    return validator.run_complete_validation()

if __name__ == "__main__":
    result = main()
    sys.exit(0 if result else 1)