#!/usr/bin/env python3
"""
ENHANCED QA LAYER 5: FUNCTIONAL COMPLETENESS VALIDATION
Manual Sync Button Testing Protocol

CRITICAL MISSION: Test if the manual sync button actually works when clicked.

This script implements the 5-layer validation framework:
Layer 1: Database - Verify sync fields update when button clicked
Layer 2: Model - Check calculated_sync_status changes  
Layer 3: Template - Confirm button exists and calls correct endpoint
Layer 4: GUI - Verify status updates in real-time
Layer 5: FUNCTIONAL - Actual sync workflow completes successfully

Evidence-based testing - don't assume it works because it exists.
"""

import os
import sys
import json
import requests
from datetime import datetime, timezone
import time
import subprocess

# Add the current directory to Python path for Django imports
sys.path.append('/home/ubuntu/cc/hedgehog-netbox-plugin')

# Django setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')

try:
    import django
    django.setup()
    
    from netbox_hedgehog.models import HedgehogFabric
    from django.utils import timezone as django_timezone
    DJANGO_AVAILABLE = True
    print("✅ Django environment successfully loaded")
    
except ImportError as e:
    print(f"⚠️  Django not available, proceeding with HTTP-only testing: {e}")
    DJANGO_AVAILABLE = False

class ManualSyncButtonValidator:
    """
    Comprehensive validation for manual sync button functionality
    Tests actual button workflow, not just existence
    """
    
    def __init__(self, fabric_id=35):
        self.fabric_id = fabric_id
        self.base_url = "http://localhost:8000"  # NetBox default
        self.evidence = {
            'test_timestamp': datetime.now().isoformat(),
            'fabric_id': fabric_id,
            'layers': {}
        }
        
        # Session for maintaining cookies/auth
        self.session = requests.Session()
        
    def layer_1_database_validation(self):
        """
        Layer 1: Database State Validation
        Capture before/after database states
        """
        print("\n🔍 LAYER 1: Database State Validation")
        
        if not DJANGO_AVAILABLE:
            print("❌ Django not available, skipping database validation")
            return False
            
        try:
            fabric = HedgehogFabric.objects.get(id=self.fabric_id)
            
            before_state = {
                'fabric_id': fabric.id,
                'name': fabric.name,
                'k8s_server': fabric.kubernetes_server,
                'last_sync': str(fabric.last_sync) if fabric.last_sync else None,
                'sync_status': fabric.sync_status,
                'calculated_sync_status': fabric.calculated_sync_status,
                'sync_error': fabric.sync_error,
                'connection_error': fabric.connection_error,
                'sync_enabled': fabric.sync_enabled,
                'is_valid': fabric.is_valid,
                'timestamp_captured': str(django_timezone.now())
            }
            
            print(f"📊 Before State Captured:")
            print(f"   - Fabric: {before_state['name']} (ID: {before_state['fabric_id']})")
            print(f"   - K8s Server: {before_state['k8s_server']}")
            print(f"   - Last Sync: {before_state['last_sync']}")
            print(f"   - Sync Status: {before_state['sync_status']}")
            print(f"   - Calculated Status: {before_state['calculated_sync_status']}")
            print(f"   - Sync Enabled: {before_state['sync_enabled']}")
            print(f"   - Sync Error: {before_state['sync_error']}")
            
            # Validate sync prerequisites
            validation_issues = []
            
            if not before_state['k8s_server']:
                validation_issues.append("❌ No K8s server configured")
            if not before_state['sync_enabled']:
                validation_issues.append("❌ Sync is disabled")
                
            self.evidence['layers']['layer1'] = {
                'success': True,
                'before_state': before_state,
                'validation_issues': validation_issues,
                'can_sync': len(validation_issues) == 0
            }
            
            if validation_issues:
                print("⚠️  Sync Prerequisites Issues:")
                for issue in validation_issues:
                    print(f"     {issue}")
                return False
            else:
                print("✅ Sync prerequisites validated")
                return True
                
        except Exception as e:
            print(f"❌ Layer 1 failed: {str(e)}")
            self.evidence['layers']['layer1'] = {
                'success': False,
                'error': str(e)
            }
            return False
    
    def layer_2_model_validation(self):
        """
        Layer 2: Model Logic Validation
        Test calculated_sync_status logic
        """
        print("\n🧠 LAYER 2: Model Logic Validation")
        
        if not DJANGO_AVAILABLE:
            print("❌ Django not available, skipping model validation")
            return False
            
        try:
            fabric = HedgehogFabric.objects.get(id=self.fabric_id)
            
            # Test calculated_sync_status property
            calc_status = fabric.calculated_sync_status
            calc_display = fabric.calculated_sync_status_display
            calc_badge = fabric.calculated_sync_status_badge_class
            
            print(f"📈 Model Properties:")
            print(f"   - Calculated Status: {calc_status}")
            print(f"   - Display: {calc_display}")
            print(f"   - Badge Class: {calc_badge}")
            
            # Validate logic consistency
            logic_issues = []
            
            # Check consistency between database and calculated status
            if not fabric.kubernetes_server and calc_status != 'not_configured':
                logic_issues.append("❌ Should be 'not_configured' without K8s server")
                
            if not fabric.sync_enabled and calc_status != 'disabled':
                logic_issues.append("❌ Should be 'disabled' when sync disabled")
                
            if not fabric.last_sync and calc_status not in ['never_synced', 'not_configured', 'disabled']:
                logic_issues.append("❌ Should be 'never_synced' without last_sync")
            
            self.evidence['layers']['layer2'] = {
                'success': len(logic_issues) == 0,
                'calculated_status': calc_status,
                'display': calc_display,
                'badge_class': calc_badge,
                'logic_issues': logic_issues
            }
            
            if logic_issues:
                print("⚠️  Model Logic Issues:")
                for issue in logic_issues:
                    print(f"     {issue}")
                return False
            else:
                print("✅ Model logic validated")
                return True
                
        except Exception as e:
            print(f"❌ Layer 2 failed: {str(e)}")
            self.evidence['layers']['layer2'] = {
                'success': False,
                'error': str(e)
            }
            return False
    
    def layer_3_template_validation(self):
        """
        Layer 3: Template/Endpoint Validation
        Verify button exists and endpoint responds
        """
        print("\n🌐 LAYER 3: Template/Endpoint Validation")
        
        try:
            # First, try to access the fabric detail page
            detail_url = f"{self.base_url}/plugins/hedgehog/fabrics/{self.fabric_id}/"
            
            print(f"🔗 Testing fabric detail page: {detail_url}")
            
            detail_response = self.session.get(detail_url)
            
            if detail_response.status_code != 200:
                print(f"❌ Cannot access fabric detail page: HTTP {detail_response.status_code}")
                self.evidence['layers']['layer3'] = {
                    'success': False,
                    'error': f'Detail page unavailable: HTTP {detail_response.status_code}'
                }
                return False
            
            # Check if sync button exists in the page
            page_content = detail_response.text
            sync_button_exists = 'sync-now-btn' in page_content
            sync_endpoint_referenced = f'/plugins/hedgehog/fabrics/{self.fabric_id}/sync/' in page_content
            
            print(f"📄 Page Analysis:")
            print(f"   - Sync Button Exists: {sync_button_exists}")
            print(f"   - Sync Endpoint Referenced: {sync_endpoint_referenced}")
            
            # Test the sync endpoint directly
            sync_url = f"{self.base_url}/plugins/hedgehog/fabrics/{self.fabric_id}/sync/"
            
            print(f"🎯 Testing sync endpoint: {sync_url}")
            
            # Need to get CSRF token first
            csrf_token = self._extract_csrf_token(page_content)
            if not csrf_token:
                print("❌ Could not extract CSRF token")
                return False
            
            headers = {
                'X-CSRFToken': csrf_token,
                'Content-Type': 'application/json',
            }
            
            # Test endpoint accessibility (should get 403 or proper error, not 404)
            sync_response = self.session.post(sync_url, headers=headers, json={})
            
            endpoint_exists = sync_response.status_code != 404
            
            print(f"🔍 Endpoint Test:")
            print(f"   - HTTP Status: {sync_response.status_code}")
            print(f"   - Endpoint Exists: {endpoint_exists}")
            
            if sync_response.status_code == 200:
                try:
                    response_data = sync_response.json()
                    print(f"   - Response: {response_data}")
                except:
                    print(f"   - Response: {sync_response.text[:200]}...")
            
            self.evidence['layers']['layer3'] = {
                'success': sync_button_exists and endpoint_exists,
                'detail_page_accessible': detail_response.status_code == 200,
                'sync_button_exists': sync_button_exists,
                'sync_endpoint_exists': endpoint_exists,
                'sync_endpoint_status': sync_response.status_code,
                'csrf_token_available': bool(csrf_token)
            }
            
            if sync_button_exists and endpoint_exists:
                print("✅ Template and endpoint validated")
                return True
            else:
                print("❌ Template or endpoint validation failed")
                return False
                
        except Exception as e:
            print(f"❌ Layer 3 failed: {str(e)}")
            self.evidence['layers']['layer3'] = {
                'success': False,
                'error': str(e)
            }
            return False
    
    def layer_4_gui_validation(self):
        """
        Layer 4: GUI Behavior Validation
        Test if button behaves correctly when clicked
        """
        print("\n🖱️  LAYER 4: GUI Behavior Validation")
        
        try:
            # Get the fabric detail page
            detail_url = f"{self.base_url}/plugins/hedgehog/fabrics/{self.fabric_id}/"
            detail_response = self.session.get(detail_url)
            
            if detail_response.status_code != 200:
                print("❌ Cannot access detail page for GUI testing")
                return False
            
            # Extract CSRF token
            csrf_token = self._extract_csrf_token(detail_response.text)
            if not csrf_token:
                print("❌ Cannot extract CSRF token for GUI testing")
                return False
            
            # Simulate the exact button click behavior
            print("🖱️  Simulating manual sync button click...")
            
            sync_url = f"{self.base_url}/plugins/hedgehog/fabrics/{self.fabric_id}/sync/"
            
            headers = {
                'X-CSRFToken': csrf_token,
                'Content-Type': 'application/json',
                'Referer': detail_url,
                'X-Requested-With': 'XMLHttpRequest'  # Simulate AJAX request
            }
            
            # Record timestamp before sync
            sync_start_time = datetime.now()
            
            # Perform the sync request
            sync_response = self.session.post(sync_url, headers=headers, json={})
            
            sync_end_time = datetime.now()
            sync_duration = (sync_end_time - sync_start_time).total_seconds()
            
            print(f"⏱️  Sync Duration: {sync_duration:.2f} seconds")
            print(f"📡 Response Status: {sync_response.status_code}")
            
            # Analyze response
            gui_success = False
            response_data = {}
            
            if sync_response.status_code == 200:
                try:
                    response_data = sync_response.json()
                    gui_success = response_data.get('success', False)
                    print(f"📊 Response Data: {response_data}")
                except json.JSONDecodeError:
                    print(f"⚠️  Non-JSON response: {sync_response.text[:200]}...")
            
            self.evidence['layers']['layer4'] = {
                'success': gui_success,
                'sync_duration': sync_duration,
                'response_status': sync_response.status_code,
                'response_data': response_data,
                'sync_start_time': sync_start_time.isoformat(),
                'sync_end_time': sync_end_time.isoformat()
            }
            
            if gui_success:
                print("✅ GUI sync behavior validated")
                return True
            else:
                print("❌ GUI sync failed or returned error")
                return False
                
        except Exception as e:
            print(f"❌ Layer 4 failed: {str(e)}")
            self.evidence['layers']['layer4'] = {
                'success': False,
                'error': str(e)
            }
            return False
    
    def layer_5_functional_validation(self):
        """
        Layer 5: Functional Completeness Validation
        Verify the complete sync workflow actually works end-to-end
        """
        print("\n🎯 LAYER 5: Functional Completeness Validation")
        
        if not DJANGO_AVAILABLE:
            print("❌ Django not available, cannot validate database changes")
            return False
            
        try:
            # Get initial state
            fabric_before = HedgehogFabric.objects.get(id=self.fabric_id)
            before_last_sync = fabric_before.last_sync
            before_sync_status = fabric_before.sync_status
            before_calc_status = fabric_before.calculated_sync_status
            
            print(f"📊 Before Sync State:")
            print(f"   - Last Sync: {before_last_sync}")
            print(f"   - Sync Status: {before_sync_status}")
            print(f"   - Calculated Status: {before_calc_status}")
            
            # Perform the sync via GUI simulation
            gui_result = self.layer_4_gui_validation()
            
            if not gui_result:
                print("❌ GUI sync failed, cannot validate functional completeness")
                return False
            
            # Wait for sync to complete
            print("⏳ Waiting for sync processing...")
            time.sleep(3)
            
            # Get state after sync
            fabric_after = HedgehogFabric.objects.get(id=self.fabric_id)
            after_last_sync = fabric_after.last_sync
            after_sync_status = fabric_after.sync_status
            after_calc_status = fabric_after.calculated_sync_status
            after_sync_error = fabric_after.sync_error
            
            print(f"📈 After Sync State:")
            print(f"   - Last Sync: {after_last_sync}")
            print(f"   - Sync Status: {after_sync_status}")
            print(f"   - Calculated Status: {after_calc_status}")
            print(f"   - Sync Error: {after_sync_error}")
            
            # Validate functional changes
            functional_success = False
            changes = []
            
            # Check if last_sync was updated
            if after_last_sync != before_last_sync:
                changes.append("✅ last_sync timestamp updated")
                functional_success = True
            else:
                changes.append("❌ last_sync not updated")
            
            # Check if sync status changed appropriately
            if after_calc_status != before_calc_status:
                changes.append(f"✅ calculated_sync_status changed: {before_calc_status} → {after_calc_status}")
            else:
                changes.append(f"⚠️  calculated_sync_status unchanged: {after_calc_status}")
            
            # Check for errors
            if after_sync_error:
                changes.append(f"⚠️  Sync error present: {after_sync_error}")
            else:
                changes.append("✅ No sync errors")
            
            print("🔍 Functional Changes:")
            for change in changes:
                print(f"     {change}")
            
            self.evidence['layers']['layer5'] = {
                'success': functional_success,
                'before_state': {
                    'last_sync': str(before_last_sync) if before_last_sync else None,
                    'sync_status': before_sync_status,
                    'calculated_status': before_calc_status
                },
                'after_state': {
                    'last_sync': str(after_last_sync) if after_last_sync else None,
                    'sync_status': after_sync_status,
                    'calculated_status': after_calc_status,
                    'sync_error': after_sync_error
                },
                'changes_detected': changes,
                'database_updated': after_last_sync != before_last_sync
            }
            
            if functional_success:
                print("✅ Functional completeness validated - sync workflow works!")
                return True
            else:
                print("❌ Functional validation failed - sync did not complete properly")
                return False
                
        except Exception as e:
            print(f"❌ Layer 5 failed: {str(e)}")
            self.evidence['layers']['layer5'] = {
                'success': False,
                'error': str(e)
            }
            return False
    
    def _extract_csrf_token(self, html_content):
        """Extract CSRF token from HTML content"""
        import re
        
        # Look for CSRF token in various formats
        patterns = [
            r'csrfmiddlewaretoken["\']?\s*[:=]\s*["\']([^"\']+)["\']',
            r'name=["\']csrfmiddlewaretoken["\']\s+value=["\']([^"\']+)["\']',
            r'<input[^>]*name=["\']csrfmiddlewaretoken["\'][^>]*value=["\']([^"\']+)["\']'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html_content, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    def generate_evidence_report(self):
        """Generate comprehensive evidence report"""
        print("\n📋 GENERATING EVIDENCE REPORT")
        
        # Calculate overall success
        layer_results = []
        for layer_key, layer_data in self.evidence['layers'].items():
            layer_results.append(layer_data.get('success', False))
        
        overall_success = all(layer_results)
        
        self.evidence['overall_result'] = {
            'success': overall_success,
            'layers_passed': sum(layer_results),
            'total_layers': len(layer_results),
            'completion_percentage': (sum(layer_results) / len(layer_results) * 100) if layer_results else 0
        }
        
        # Save evidence to file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        evidence_file = f'/tmp/manual_sync_button_validation_evidence_{timestamp}.json'
        
        with open(evidence_file, 'w') as f:
            json.dump(self.evidence, f, indent=2, default=str)
        
        print(f"📄 Evidence saved to: {evidence_file}")
        
        # Generate summary
        print("\n" + "="*80)
        print("MANUAL SYNC BUTTON VALIDATION SUMMARY")
        print("="*80)
        
        if overall_success:
            print("🎉 RESULT: SYNC BUTTON WORKS CORRECTLY")
            print("   All 5 layers of validation passed successfully!")
        else:
            print("❌ RESULT: SYNC BUTTON HAS ISSUES")
            print(f"   Only {sum(layer_results)}/{len(layer_results)} layers passed")
        
        print(f"📊 Overall Success Rate: {self.evidence['overall_result']['completion_percentage']:.1f}%")
        print(f"🏗️  Fabric ID: {self.fabric_id}")
        print(f"⏰ Test Timestamp: {self.evidence['test_timestamp']}")
        
        for i, (layer_key, layer_data) in enumerate(self.evidence['layers'].items(), 1):
            status = "✅ PASS" if layer_data.get('success', False) else "❌ FAIL"
            layer_name = {
                'layer1': 'Database State',
                'layer2': 'Model Logic', 
                'layer3': 'Template/Endpoint',
                'layer4': 'GUI Behavior',
                'layer5': 'Functional Complete'
            }.get(layer_key, layer_key)
            
            print(f"📋 Layer {i} ({layer_name}): {status}")
            
            if not layer_data.get('success', False) and 'error' in layer_data:
                print(f"     Error: {layer_data['error']}")
        
        print("="*80)
        
        return overall_success, evidence_file
    
    def run_complete_validation(self):
        """Run all 5 layers of validation"""
        print("🚀 STARTING ENHANCED QA LAYER 5 VALIDATION")
        print("Testing Manual Sync Button Functionality")
        print("="*80)
        
        try:
            # Run all layers sequentially
            layer1_result = self.layer_1_database_validation()
            layer2_result = self.layer_2_model_validation() 
            layer3_result = self.layer_3_template_validation()
            layer4_result = self.layer_4_gui_validation()
            layer5_result = self.layer_5_functional_validation()
            
            # Generate comprehensive evidence report
            overall_success, evidence_file = self.generate_evidence_report()
            
            return overall_success, evidence_file
            
        except Exception as e:
            print(f"💥 CRITICAL ERROR during validation: {str(e)}")
            return False, None


if __name__ == "__main__":
    # Run the complete validation
    validator = ManualSyncButtonValidator(fabric_id=35)
    success, evidence_file = validator.run_complete_validation()
    
    if success:
        print("\n🎉 VALIDATION COMPLETE: Manual sync button works correctly!")
        exit(0)
    else:
        print("\n❌ VALIDATION FAILED: Manual sync button has issues!")
        exit(1)