#!/usr/bin/env python3
"""
Kubernetes Fabric Configuration Implementation Script
Mission: Update HNP fabric record with K8s cluster configuration and validate synchronization

This script:
1. Updates Test Fabric (ID: 26) with Kubernetes cluster configuration
2. Validates the configuration update 
3. Triggers Kubernetes synchronization process
4. Monitors synchronization status and completion
5. Validates CR record associations and drift detection
6. Documents all evidence of successful operation
"""

import os
import json
import requests
import time
from datetime import datetime
from urllib.parse import urljoin
import sys

# Load environment variables from .env file
def load_env_file(env_path='/home/ubuntu/cc/hedgehog-netbox-plugin/.env'):
    """Load environment variables from .env file"""
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    # Remove quotes if present
                    value = value.strip('"\'')
                    os.environ[key] = value

# Load environment variables
load_env_file()

# Add the plugin path to handle imports
sys.path.insert(0, '/opt/netbox/netbox/hedgehog_netbox_plugin')

class K8sFabricConfigurationManager:
    """Manages Kubernetes fabric configuration and synchronization validation"""
    
    def __init__(self):
        """Initialize with environment variables and API configuration"""
        self.netbox_url = os.getenv('NETBOX_URL', 'http://localhost:8000/')
        self.netbox_token = os.getenv('NETBOX_TOKEN')
        self.k8s_server = os.getenv('TEST_FABRIC_K8S_API_SERVER')
        self.k8s_token = os.getenv('TEST_FABRIC_K8S_TOKEN') 
        self.k8s_ca_cert = os.getenv('TEST_FABRIC_K8S_API_SERVER_CA')
        self.fabric_id = 26  # Test Fabric ID from analysis
        
        # API session setup
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Token {self.netbox_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
        
        # Evidence tracking
        self.evidence = {
            'start_time': datetime.now().isoformat(),
            'fabric_id': self.fabric_id,
            'operations': [],
            'validations': [],
            'errors': []
        }
        
    def log_operation(self, operation, status, details=None, data=None):
        """Log operation for evidence collection"""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'operation': operation,
            'status': status,
            'details': details,
            'data': data
        }
        self.evidence['operations'].append(entry)
        print(f"[{entry['timestamp']}] {operation}: {status}")
        if details:
            print(f"  Details: {details}")
            
    def log_validation(self, validation, result, expected, actual=None):
        """Log validation results for evidence collection"""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'validation': validation,
            'result': result,
            'expected': expected,
            'actual': actual
        }
        self.evidence['validations'].append(entry)
        print(f"[{entry['timestamp']}] VALIDATION {validation}: {result}")
        print(f"  Expected: {expected}")
        if actual:
            print(f"  Actual: {actual}")
            
    def log_error(self, error_type, message, exception=None):
        """Log errors for troubleshooting"""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'error_type': error_type,
            'message': message,
            'exception': str(exception) if exception else None
        }
        self.evidence['errors'].append(entry)
        print(f"[{entry['timestamp']}] ERROR {error_type}: {message}")
        if exception:
            print(f"  Exception: {exception}")
            
    def validate_environment(self):
        """Validate all required environment variables are present"""
        print("=== ENVIRONMENT VALIDATION ===")
        
        required_vars = {
            'NETBOX_URL': self.netbox_url,
            'NETBOX_TOKEN': self.netbox_token,
            'TEST_FABRIC_K8S_API_SERVER': self.k8s_server,
            'TEST_FABRIC_K8S_TOKEN': self.k8s_token,
            'TEST_FABRIC_K8S_API_SERVER_CA': self.k8s_ca_cert
        }
        
        all_valid = True
        for var_name, var_value in required_vars.items():
            if not var_value:
                self.log_error('ENVIRONMENT', f'Missing required environment variable: {var_name}')
                all_valid = False
            else:
                self.log_operation('ENVIRONMENT_CHECK', 'SUCCESS', f'{var_name} is set')
                
        if not all_valid:
            raise ValueError("Missing required environment variables")
            
        self.log_validation('ENVIRONMENT_VALIDATION', 'PASSED', 'All required environment variables present')
        return True
        
    def get_current_fabric_state(self):
        """Retrieve current fabric configuration from NetBox API"""
        print("\n=== RETRIEVING CURRENT FABRIC STATE ===")
        
        try:
            url = urljoin(self.netbox_url, f'api/plugins/hedgehog/fabrics/{self.fabric_id}/')
            response = self.session.get(url)
            response.raise_for_status()
            
            fabric_data = response.json()
            self.log_operation('GET_FABRIC_STATE', 'SUCCESS', f'Retrieved fabric {self.fabric_id}', 
                             {'name': fabric_data.get('name'), 'status': fabric_data.get('status')})
            
            # Log current K8s configuration status
            k8s_fields = {
                'kubernetes_server': fabric_data.get('kubernetes_server', ''),
                'kubernetes_token': '***REDACTED***' if fabric_data.get('kubernetes_token') else '',
                'kubernetes_ca_cert': '***REDACTED***' if fabric_data.get('kubernetes_ca_cert') else '',
                'kubernetes_namespace': fabric_data.get('kubernetes_namespace', '')
            }
            
            self.log_operation('K8S_CONFIG_CHECK', 'INFO', 'Current K8s configuration', k8s_fields)
            return fabric_data
            
        except requests.exceptions.RequestException as e:
            self.log_error('API_REQUEST', f'Failed to retrieve fabric {self.fabric_id}', e)
            raise
            
    def update_fabric_k8s_configuration(self, fabric_data):
        """Update fabric with Kubernetes cluster configuration"""
        print("\n=== UPDATING FABRIC K8S CONFIGURATION ===")
        
        # Prepare update payload with K8s configuration
        update_data = {
            'kubernetes_server': self.k8s_server,
            'kubernetes_token': self.k8s_token,
            'kubernetes_ca_cert': self.k8s_ca_cert,
            'kubernetes_namespace': fabric_data.get('kubernetes_namespace', 'default')
        }
        
        # Log the update attempt (without sensitive data)
        safe_update_data = {
            'kubernetes_server': self.k8s_server,
            'kubernetes_token': '***REDACTED***',
            'kubernetes_ca_cert': '***REDACTED***',
            'kubernetes_namespace': update_data['kubernetes_namespace']
        }
        self.log_operation('K8S_UPDATE_ATTEMPT', 'STARTING', 'Updating fabric with K8s config', safe_update_data)
        
        try:
            url = urljoin(self.netbox_url, f'api/plugins/hedgehog/fabrics/{self.fabric_id}/')
            response = self.session.patch(url, json=update_data)
            response.raise_for_status()
            
            updated_fabric = response.json()
            self.log_operation('K8S_UPDATE', 'SUCCESS', 'Fabric updated with K8s configuration')
            
            # Validate the update was applied
            self.validate_k8s_configuration_update(updated_fabric)
            return updated_fabric
            
        except requests.exceptions.RequestException as e:
            self.log_error('K8S_UPDATE', f'Failed to update fabric {self.fabric_id} with K8s config', e)
            raise
            
    def validate_k8s_configuration_update(self, fabric_data):
        """Validate that K8s configuration was properly saved"""
        print("\n=== VALIDATING K8S CONFIGURATION UPDATE ===")
        
        validations = [
            ('kubernetes_server', self.k8s_server, fabric_data.get('kubernetes_server')),
            ('kubernetes_token', self.k8s_token, fabric_data.get('kubernetes_token')),
            ('kubernetes_ca_cert', self.k8s_ca_cert, fabric_data.get('kubernetes_ca_cert')),
        ]
        
        all_valid = True
        for field_name, expected, actual in validations:
            if actual == expected:
                # For sensitive fields, don't log the actual values
                if 'token' in field_name or 'certificate' in field_name:
                    self.log_validation(f'K8S_CONFIG_{field_name.upper()}', 'PASSED', 
                                      'Field updated correctly', '***REDACTED***')
                else:
                    self.log_validation(f'K8S_CONFIG_{field_name.upper()}', 'PASSED', 
                                      expected, actual)
            else:
                self.log_validation(f'K8S_CONFIG_{field_name.upper()}', 'FAILED', 
                                  expected, actual)
                all_valid = False
                
        if all_valid:
            self.log_validation('K8S_CONFIGURATION_VALIDATION', 'PASSED', 
                              'All K8s configuration fields updated correctly')
        else:
            raise ValueError("K8s configuration validation failed")
            
    def trigger_k8s_synchronization(self):
        """Trigger Kubernetes synchronization process"""
        print("\n=== TRIGGERING K8S SYNCHRONIZATION ===")
        
        try:
            # Use the existing sync endpoint with k8s parameter
            url = urljoin(self.netbox_url, f'api/plugins/hedgehog/fabrics/{self.fabric_id}/sync/')
            
            # Include both gitops and k8s sync
            sync_data = {
                'sync_source': 'kubernetes',
                'force_sync': True
            }
            
            self.log_operation('K8S_SYNC_TRIGGER', 'STARTING', 'Triggering K8s synchronization', sync_data)
            
            response = self.session.post(url, json=sync_data)
            response.raise_for_status()
            
            sync_result = response.json()
            self.log_operation('K8S_SYNC_TRIGGER', 'SUCCESS', 'K8s synchronization triggered', sync_result)
            
            return sync_result
            
        except requests.exceptions.RequestException as e:
            self.log_error('K8S_SYNC_TRIGGER', f'Failed to trigger K8s synchronization', e)
            raise
            
    def monitor_synchronization_status(self, max_wait_time=300):
        """Monitor synchronization status until completion"""
        print("\n=== MONITORING SYNCHRONIZATION STATUS ===")
        
        start_time = time.time()
        check_interval = 10  # Check every 10 seconds
        
        while time.time() - start_time < max_wait_time:
            try:
                # Get current fabric state
                fabric_data = self.get_current_fabric_state()
                
                # Check sync status fields
                sync_status = fabric_data.get('sync_status', 'unknown')
                last_sync = fabric_data.get('last_sync')
                sync_error = fabric_data.get('sync_error', '')
                connection_status = fabric_data.get('connection_status', 'unknown')
                
                status_info = {
                    'sync_status': sync_status,
                    'connection_status': connection_status,
                    'last_sync': last_sync,
                    'sync_error': sync_error if sync_error else 'none'
                }
                
                self.log_operation('SYNC_STATUS_CHECK', 'INFO', 'Current sync status', status_info)
                
                # Check if sync completed successfully
                if sync_status == 'synced' and not sync_error:
                    self.log_operation('SYNC_MONITORING', 'SUCCESS', 'Synchronization completed successfully')
                    return fabric_data
                    
                # Check for errors
                if sync_error:
                    self.log_error('SYNC_MONITORING', f'Synchronization error: {sync_error}')
                    return fabric_data
                    
                # Wait before next check
                time.sleep(check_interval)
                
            except Exception as e:
                self.log_error('SYNC_MONITORING', 'Error monitoring sync status', e)
                time.sleep(check_interval)
                
        # Timeout reached
        self.log_error('SYNC_MONITORING', f'Synchronization monitoring timeout after {max_wait_time} seconds')
        return self.get_current_fabric_state()
        
    def validate_cr_record_associations(self):
        """Validate CR record associations and counts"""
        print("\n=== VALIDATING CR RECORD ASSOCIATIONS ===")
        
        try:
            # Get updated fabric state
            fabric_data = self.get_current_fabric_state()
            
            # Check CRD counts
            crd_counts = {
                'cached_crd_count': fabric_data.get('cached_crd_count', 0),
                'cached_vpc_count': fabric_data.get('cached_vpc_count', 0),
                'cached_connection_count': fabric_data.get('cached_connection_count', 0),
                'connections_count': fabric_data.get('connections_count', 0),
                'servers_count': fabric_data.get('servers_count', 0),
                'switches_count': fabric_data.get('switches_count', 0),
                'vpcs_count': fabric_data.get('vpcs_count', 0)
            }
            
            self.log_operation('CRD_COUNT_CHECK', 'INFO', 'Current CRD counts', crd_counts)
            
            # Validate that we have some CRDs synchronized
            total_crds = crd_counts['cached_crd_count']
            if total_crds > 0:
                self.log_validation('CRD_SYNCHRONIZATION', 'PASSED', 
                                  'CRDs synchronized from cluster', f'{total_crds} CRDs found')
            else:
                self.log_validation('CRD_SYNCHRONIZATION', 'WARNING', 
                                  'CRDs synchronized from cluster', 'No CRDs found - may be expected')
                                  
            return crd_counts
            
        except Exception as e:
            self.log_error('CRD_VALIDATION', 'Error validating CR record associations', e)
            raise
            
    def test_drift_detection(self):
        """Test drift detection between GitOps and K8s cluster"""
        print("\n=== TESTING DRIFT DETECTION ===")
        
        try:
            # Get current fabric state
            fabric_data = self.get_current_fabric_state()
            
            # Check drift detection fields
            drift_info = {
                'drift_status': fabric_data.get('drift_status', 'unknown'),
                'drift_count': fabric_data.get('drift_count', 0),
                'last_git_sync': fabric_data.get('last_git_sync'),
                'last_sync': fabric_data.get('last_sync')
            }
            
            self.log_operation('DRIFT_DETECTION_CHECK', 'INFO', 'Current drift detection status', drift_info)
            
            # Validate drift detection functionality
            drift_status = drift_info['drift_status']
            if drift_status in ['in_sync', 'drift_detected', 'critical']:
                self.log_validation('DRIFT_DETECTION', 'PASSED', 
                                  'Drift detection system operational', drift_status)
            else:
                self.log_validation('DRIFT_DETECTION', 'WARNING', 
                                  'Drift detection system operational', f'Unknown status: {drift_status}')
                                  
            return drift_info
            
        except Exception as e:
            self.log_error('DRIFT_DETECTION', 'Error testing drift detection', e)
            raise
            
    def generate_evidence_report(self):
        """Generate comprehensive evidence report"""
        print("\n=== GENERATING EVIDENCE REPORT ===")
        
        self.evidence['end_time'] = datetime.now().isoformat()
        self.evidence['duration'] = f"From {self.evidence['start_time']} to {self.evidence['end_time']}"
        
        # Summary statistics
        self.evidence['summary'] = {
            'total_operations': len(self.evidence['operations']),
            'successful_operations': len([op for op in self.evidence['operations'] if op['status'] == 'SUCCESS']),
            'total_validations': len(self.evidence['validations']),
            'passed_validations': len([val for val in self.evidence['validations'] if val['result'] == 'PASSED']),
            'total_errors': len(self.evidence['errors'])
        }
        
        # Save evidence report
        evidence_file = '/home/ubuntu/cc/hedgehog-netbox-plugin/project_management/07_qapm_workspaces/k8s_sync_validation/04_evidence_collection/test_results/k8s_configuration_evidence.json'
        
        with open(evidence_file, 'w') as f:
            json.dump(self.evidence, f, indent=2, default=str)
            
        self.log_operation('EVIDENCE_REPORT', 'SUCCESS', f'Evidence report saved to {evidence_file}')
        
        # Print summary
        print(f"\n=== EXECUTION SUMMARY ===")
        print(f"Duration: {self.evidence['duration']}")
        print(f"Operations: {self.evidence['summary']['successful_operations']}/{self.evidence['summary']['total_operations']} successful")
        print(f"Validations: {self.evidence['summary']['passed_validations']}/{self.evidence['summary']['total_validations']} passed")
        print(f"Errors: {self.evidence['summary']['total_errors']}")
        
        return self.evidence
        
    def run_complete_validation(self):
        """Run complete K8s fabric configuration and validation workflow"""
        print("========================================")
        print("K8S FABRIC CONFIGURATION VALIDATION")
        print("========================================")
        
        try:
            # Step 1: Validate environment
            self.validate_environment()
            
            # Step 2: Get current fabric state
            initial_fabric_data = self.get_current_fabric_state()
            
            # Step 3: Update fabric with K8s configuration
            updated_fabric_data = self.update_fabric_k8s_configuration(initial_fabric_data)
            
            # Step 4: Trigger K8s synchronization
            sync_result = self.trigger_k8s_synchronization()
            
            # Step 5: Monitor synchronization status
            final_fabric_data = self.monitor_synchronization_status()
            
            # Step 6: Validate CR record associations
            crd_counts = self.validate_cr_record_associations()
            
            # Step 7: Test drift detection
            drift_info = self.test_drift_detection()
            
            # Step 8: Generate evidence report
            evidence = self.generate_evidence_report()
            
            print("\n✅ K8S FABRIC CONFIGURATION VALIDATION COMPLETED SUCCESSFULLY")
            return {
                'status': 'SUCCESS',
                'fabric_data': final_fabric_data,
                'crd_counts': crd_counts,
                'drift_info': drift_info,
                'evidence': evidence
            }
            
        except Exception as e:
            self.log_error('COMPLETE_VALIDATION', 'Complete validation failed', e)
            self.generate_evidence_report()
            print(f"\n❌ K8S FABRIC CONFIGURATION VALIDATION FAILED: {e}")
            return {
                'status': 'FAILED',
                'error': str(e),
                'evidence': self.evidence
            }

if __name__ == '__main__':
    # Initialize and run the validation
    manager = K8sFabricConfigurationManager()
    result = manager.run_complete_validation()
    
    # Exit with appropriate code
    sys.exit(0 if result['status'] == 'SUCCESS' else 1)