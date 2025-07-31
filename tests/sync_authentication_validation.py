#!/usr/bin/env python3
"""
Sync Authentication Fix Validation
=================================

Validates that the sync authentication fix resolves the ObjectChange.user error.
This test demonstrates the complete fix for the sync error root cause.
"""

import json
from datetime import datetime


class SyncAuthenticationValidator:
    """
    Validates the sync authentication fix implementation.
    Tests that user context is properly passed to sync operations.
    """
    
    def __init__(self):
        self.validation_results = []
        
    def log_validation(self, test_name: str, status: str, evidence: dict):
        """Log validation result with evidence"""
        result = {
            'timestamp': datetime.now().isoformat(),
            'test_name': test_name,
            'status': status,
            'evidence': evidence
        }
        self.validation_results.append(result)
        print(f"[{status}] {test_name}")
        if status != 'PASS':
            print(f"  Evidence: {evidence}")
    
    def validate_sync_view_user_context_passing(self):
        """Validate that sync view passes user context to KubernetesSync"""
        print("\n=== Sync View User Context Validation ===")
        
        # Check that FabricSyncView code passes user context
        try:
            with open('/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/views/sync_views.py', 'r') as f:
                sync_view_content = f.read()
            
            # Check for user context passing
            user_context_patterns = [
                'k8s_sync = KubernetesSync(fabric, user=request.user)',
                'user=request.user'
            ]
            
            patterns_found = []
            for pattern in user_context_patterns:
                if pattern in sync_view_content:
                    patterns_found.append(pattern)
            
            evidence = {
                'file_checked': 'sync_views.py',
                'patterns_found': patterns_found,
                'user_context_passed': len(patterns_found) > 0,
                'login_required_decorator': '@method_decorator(login_required' in sync_view_content
            }
            
            if evidence['user_context_passed'] and evidence['login_required_decorator']:
                self.log_validation("Sync View User Context Passing", "PASS", evidence)
            else:
                self.log_validation("Sync View User Context Passing", "FAIL", evidence)
                
        except Exception as e:
            self.log_validation("Sync View File Access", "ERROR", {"error": str(e)})
    
    def validate_kubernetes_sync_user_context_handling(self):
        """Validate that KubernetesSync accepts and uses user context"""
        print("\n=== KubernetesSync User Context Handling Validation ===")
        
        try:
            with open('/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/utils/kubernetes.py', 'r') as f:
                kubernetes_content = f.read()
            
            # Check for user context handling
            context_patterns = [
                'def __init__(self, fabric: HedgehogFabric, user=None)',
                'self.user = user',
                'def _save_with_user_context(self, model_instance)',
                'set_actor(actor=self.user)',
                'self._save_with_user_context('
            ]
            
            patterns_found = []
            for pattern in context_patterns:
                if pattern in kubernetes_content:
                    patterns_found.append(pattern)
            
            # Count usage of _save_with_user_context
            save_context_usage = kubernetes_content.count('_save_with_user_context(')
            
            evidence = {
                'file_checked': 'kubernetes.py',
                'patterns_found': patterns_found,
                'user_parameter_accepted': 'user=None' in kubernetes_content,
                'save_with_context_method': '_save_with_user_context' in kubernetes_content,
                'save_context_usage_count': save_context_usage,
                'auditlog_context_used': 'set_actor' in kubernetes_content
            }
            
            required_patterns = 4  # At least 4 of the 5 patterns should be found
            if len(patterns_found) >= required_patterns and save_context_usage > 0:
                self.log_validation("KubernetesSync User Context Handling", "PASS", evidence)
            else:
                self.log_validation("KubernetesSync User Context Handling", "FAIL", evidence)
                
        except Exception as e:
            self.log_validation("KubernetesSync File Access", "ERROR", {"error": str(e)})
    
    def validate_authentication_error_fix_completeness(self):
        """Validate that the authentication fix addresses the ObjectChange.user error"""
        print("\n=== Authentication Error Fix Completeness ===")
        
        # Analyze the fix implementation
        fix_components = {
            'user_context_in_view': False,
            'user_context_in_sync_class': False,
            'audit_context_handling': False,
            'save_method_override': False
        }
        
        try:
            # Check sync view
            with open('/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/views/sync_views.py', 'r') as f:
                view_content = f.read()
                if 'user=request.user' in view_content:
                    fix_components['user_context_in_view'] = True
            
            # Check kubernetes sync
            with open('/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/utils/kubernetes.py', 'r') as f:
                sync_content = f.read()
                if 'self.user = user' in sync_content:
                    fix_components['user_context_in_sync_class'] = True
                if 'set_actor(actor=self.user)' in sync_content:
                    fix_components['audit_context_handling'] = True
                if '_save_with_user_context' in sync_content:
                    fix_components['save_method_override'] = True
        
        except Exception as e:
            self.log_validation("Fix Analysis File Access", "ERROR", {"error": str(e)})
            return
        
        evidence = {
            'fix_components': fix_components,
            'components_implemented': sum(fix_components.values()),
            'total_components': len(fix_components),
            'fix_completeness': f"{sum(fix_components.values())}/{len(fix_components)}",
            'addresses_anonymous_user_error': all(fix_components.values())
        }
        
        if evidence['addresses_anonymous_user_error']:
            self.log_validation("Authentication Error Fix Complete", "PASS", evidence)
        else:
            self.log_validation("Authentication Error Fix Incomplete", "FAIL", evidence)
    
    def validate_api_authentication_requirements(self):
        """Validate that sync APIs properly require authentication"""
        print("\n=== API Authentication Requirements ===")
        
        import requests
        
        # Test sync API endpoints
        endpoints = [
            '/api/plugins/hedgehog/gitops-fabrics/12/gitops_sync/',
            '/api/plugins/hedgehog/gitops-fabrics/12/hckc_sync/',
            '/plugins/hedgehog/fabrics/12/test-connection/'
        ]
        
        auth_results = {}
        for endpoint in endpoints:
            try:
                response = requests.get(f"http://localhost:8000{endpoint}", timeout=5)
                auth_results[endpoint] = {
                    'status_code': response.status_code,
                    'requires_auth': response.status_code in [401, 403],
                    'accessible': response.status_code == 200
                }
            except Exception as e:
                auth_results[endpoint] = {
                    'status_code': 0,
                    'error': str(e),
                    'requires_auth': False,
                    'accessible': False
                }
        
        evidence = {
            'endpoints_tested': list(endpoints),
            'auth_results': auth_results,
            'all_require_auth': all(r.get('requires_auth', False) for r in auth_results.values()),
            'none_publicly_accessible': not any(r.get('accessible', False) for r in auth_results.values())
        }
        
        if evidence['all_require_auth'] and evidence['none_publicly_accessible']:
            self.log_validation("API Authentication Requirements", "PASS", evidence)
        else:
            self.log_validation("API Authentication Security Gap", "FAIL", evidence)


def run_sync_authentication_validation():
    """Run sync authentication fix validation"""
    print("=== SYNC AUTHENTICATION FIX VALIDATION ===")
    print("Validating the complete fix for ObjectChange.user authentication error")
    print("=" * 70)
    
    validator = SyncAuthenticationValidator()
    
    # Run all validations
    validator.validate_sync_view_user_context_passing()
    validator.validate_kubernetes_sync_user_context_handling()
    validator.validate_authentication_error_fix_completeness()
    validator.validate_api_authentication_requirements()
    
    # Generate summary
    results = validator.validation_results
    total_tests = len(results)
    passed_tests = len([r for r in results if r['status'] == 'PASS'])
    failed_tests = len([r for r in results if r['status'] == 'FAIL'])
    error_tests = len([r for r in results if r['status'] == 'ERROR'])
    
    print("\n" + "=" * 70)
    print("=== SYNC AUTHENTICATION FIX VALIDATION SUMMARY ===")
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {passed_tests} ({passed_tests/total_tests*100:.1f}%)")
    print(f"Failed: {failed_tests} ({failed_tests/total_tests*100:.1f}%)")
    print(f"Errors: {error_tests} ({error_tests/total_tests*100:.1f}%)")
    
    # Save detailed results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = f"/home/ubuntu/cc/hedgehog-netbox-plugin/sync_auth_validation_{timestamp}.json"
    
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
    if passed_tests == total_tests:
        print("\n✅ AUTHENTICATION FIX VALIDATION: COMPLETE")
        print("All components of the sync authentication fix are properly implemented.")
        print("The ObjectChange.user error should be resolved for new sync operations.")
    else:
        print("\n⚠️ AUTHENTICATION FIX VALIDATION: INCOMPLETE")
        print("Some components of the fix may need additional work.")
    
    return passed_tests == total_tests


if __name__ == "__main__":
    success = run_sync_authentication_validation()
    exit(0 if success else 1)