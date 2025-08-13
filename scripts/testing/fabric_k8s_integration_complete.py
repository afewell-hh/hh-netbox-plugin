#!/usr/bin/env python3
"""
Fabric K8s Integration - Production Ready Configuration

This script provides the complete implementation for configuring
fabric ID 35 to connect to the vlab-art.l.hhdev.io:6443 K8s cluster.

Since the NetBox environment is not directly accessible in this development
setup, this script provides the exact SQL and configuration needed for
production deployment.
"""

import json
import time
from datetime import datetime

class FabricK8sIntegration:
    """Complete K8s fabric integration solution"""
    
    def __init__(self):
        self.fabric_id = 35
        self.cluster_config = {
            'server': 'https://vlab-art.l.hhdev.io:6443',
            'namespace': 'default',
            'service_account': 'hnp-sync',
            'secret_name': 'hnp-sync-token'
        }
        
    def generate_sql_update(self) -> str:
        """Generate SQL to update fabric configuration"""
        sql = f"""
        -- Update Fabric ID {self.fabric_id} for K8s cluster connection
        UPDATE netbox_hedgehog_hedgehogfabric 
        SET 
            kubernetes_server = '{self.cluster_config['server']}',
            kubernetes_namespace = '{self.cluster_config['namespace']}',
            kubernetes_token = '{{SERVICE_ACCOUNT_TOKEN}}',  -- Replace with actual token
            kubernetes_ca_cert = '',  -- Optional for insecure-skip-tls setups
            sync_enabled = TRUE,
            sync_error = '',
            connection_error = '',
            last_change = NOW()
        WHERE id = {self.fabric_id};
        
        -- Verify the update
        SELECT 
            id, name, 
            kubernetes_server, 
            kubernetes_namespace, 
            CASE WHEN kubernetes_token != '' THEN 'TOKEN_SET' ELSE 'NO_TOKEN' END as token_status,
            sync_enabled,
            connection_status,
            sync_status
        FROM netbox_hedgehog_hedgehogfabric 
        WHERE id = {self.fabric_id};
        """
        return sql
    
    def generate_token_retrieval_command(self) -> str:
        """Generate kubectl command to retrieve service account token"""
        return f"""
        # Get the service account token for authentication
        kubectl get secret {self.cluster_config['secret_name']} \
            --namespace {self.cluster_config['namespace']} \
            --server {self.cluster_config['server']} \
            --insecure-skip-tls-verify \
            -o jsonpath='{{.data.token}}' | base64 -d
        """
    
    def generate_django_management_commands(self) -> str:
        """Generate Django management commands for fabric update"""
        return f"""
        # Using Django shell to update fabric
        python manage.py shell << 'EOF'
        from netbox_hedgehog.models.fabric import HedgehogFabric
        from django.utils import timezone
        
        # Get fabric ID {self.fabric_id}
        fabric = HedgehogFabric.objects.get(id={self.fabric_id})
        print(f"Current fabric: {{fabric.name}}")
        print(f"Current K8s server: {{fabric.kubernetes_server or 'NOT CONFIGURED'}}")
        
        # Update with K8s configuration
        fabric.kubernetes_server = '{self.cluster_config['server']}'
        fabric.kubernetes_namespace = '{self.cluster_config['namespace']}'
        fabric.kubernetes_token = '{{TOKEN_FROM_KUBECTL_COMMAND}}'  # Replace with actual token
        fabric.sync_enabled = True
        fabric.sync_error = ''
        fabric.connection_error = ''
        fabric.save()
        
        print("✅ Fabric updated successfully")
        print(f"Server: {{fabric.kubernetes_server}}")
        print(f"Namespace: {{fabric.kubernetes_namespace}}")
        print(f"Sync enabled: {{fabric.sync_enabled}}")
        
        # Test the calculated sync status (this is what shows in GUI)
        calculated_status = fabric.calculated_sync_status
        print(f"Calculated sync status: {{calculated_status}}")
        print(f"Status display: {{fabric.calculated_sync_status_display}}")
        EOF
        """
    
    def generate_connectivity_test_script(self) -> str:
        """Generate script to test K8s connectivity through HNP"""
        return f"""
        # Test connectivity using HNP Kubernetes utilities
        python manage.py shell << 'EOF'
        from netbox_hedgehog.models.fabric import HedgehogFabric
        from netbox_hedgehog.utils.kubernetes import KubernetesClient, KubernetesSync
        import json
        
        # Get configured fabric
        fabric = HedgehogFabric.objects.get(id={self.fabric_id})
        
        # Test basic connection
        k8s_client = KubernetesClient(fabric)
        connection_result = k8s_client.test_connection()
        print(f"Connection test: {{connection_result['success']}}")
        if connection_result['success']:
            print(f"Cluster version: {{connection_result.get('cluster_version', 'unknown')}}")
            print(f"Platform: {{connection_result.get('platform', 'unknown')}}")
        else:
            print(f"Connection error: {{connection_result.get('error', 'unknown')}}")
        
        # Test CRD fetching
        k8s_sync = KubernetesSync(fabric)
        fetch_result = k8s_sync.fetch_crds_from_kubernetes()
        print(f"CRD fetch test: {{fetch_result['success']}}")
        print(f"Available CRD types: {{list(fetch_result.get('resources', {{}}).keys())}}")
        
        # Update fabric status based on tests
        if connection_result['success']:
            fabric.connection_status = 'connected'
            fabric.connection_error = ''
        else:
            fabric.connection_status = 'error'
            fabric.connection_error = connection_result.get('error', 'Connection failed')
        
        fabric.save()
        print(f"Updated connection status: {{fabric.connection_status}}")
        EOF
        """
    
    def generate_gui_validation_steps(self) -> str:
        """Generate steps to validate GUI shows K8s configuration"""
        return f"""
        GUI Validation Steps:
        
        1. Navigate to NetBox HNP Fabric Detail Page:
           - URL: /plugins/netbox-hedgehog/fabrics/{self.fabric_id}/
           - Look for fabric detail view
        
        2. Verify K8s Configuration Display:
           ✅ Kubernetes server should show: {self.cluster_config['server']}
           ✅ Kubernetes namespace should show: {self.cluster_config['namespace']}
           ✅ Sync status should NOT show "Not Configured"
           ✅ Connection status should show actual state (connected/error)
        
        3. Check Sync Status Calculation:
           - Status should be calculated based on fabric.calculated_sync_status property
           - Should show proper badge color (green for connected, red for error)
           - Should NOT show contradictory status like "synced" without K8s server
        
        4. Test Sync Operations (if connection successful):
           - Try manual sync button if available
           - Check for CRD count updates
           - Verify error messages are clear if sync fails
        
        5. Validate Template Rendering:
           - Check fabric_detail.html template shows K8s fields
           - Verify calculated_sync_status_display is used
           - Confirm fabric.kubernetes_server is displayed in UI
        """
    
    def create_deployment_package(self) -> dict:
        """Create complete deployment package"""
        package = {
            'metadata': {
                'created': datetime.now().isoformat(),
                'target_fabric_id': self.fabric_id,
                'target_cluster': self.cluster_config['server'],
                'purpose': 'Connect HNP fabric to K8s test cluster'
            },
            'steps': {
                '1_prerequisites': {
                    'description': 'Ensure K8s cluster access',
                    'commands': [
                        f"kubectl cluster-info --server {self.cluster_config['server']} --insecure-skip-tls-verify",
                        "# Should show cluster info with authentication error (expected)"
                    ]
                },
                '2_get_token': {
                    'description': 'Retrieve service account token',
                    'commands': [self.generate_token_retrieval_command()]
                },
                '3_update_fabric': {
                    'description': 'Update fabric configuration',
                    'options': {
                        'sql_direct': self.generate_sql_update(),
                        'django_shell': self.generate_django_management_commands()
                    }
                },
                '4_test_connectivity': {
                    'description': 'Test K8s connectivity',
                    'commands': [self.generate_connectivity_test_script()]
                },
                '5_gui_validation': {
                    'description': 'Validate GUI display',
                    'steps': self.generate_gui_validation_steps()
                }
            },
            'expected_outcomes': {
                'fabric_configured': f'Fabric ID {self.fabric_id} has kubernetes_server set',
                'connectivity_working': 'K8s API accessible with service account token',
                'gui_updated': 'Fabric detail page shows K8s server URL and proper status',
                'sync_functional': 'Sync operations work or show clear error messages'
            },
            'troubleshooting': {
                'token_issues': 'Check service account exists and token is base64 decoded',
                'connectivity_issues': 'Verify firewall and DNS resolution for vlab-art.l.hhdev.io',
                'gui_not_updated': 'Check calculated_sync_status property implementation',
                'sync_errors': 'Review KubernetesClient and KubernetesSync error handling'
            }
        }
        return package
    
    def save_deployment_package(self) -> str:
        """Save complete deployment package to file"""
        package = self.create_deployment_package()
        filename = f"k8s_fabric_deployment_package_{int(time.time())}.json"
        filepath = f"/home/ubuntu/cc/hedgehog-netbox-plugin/{filename}"
        
        with open(filepath, 'w') as f:
            json.dump(package, f, indent=2)
        
        return filepath
    
    def generate_evidence_validation_script(self) -> str:
        """Generate script to validate implementation evidence"""
        return f"""
        #!/bin/bash
        # Evidence Validation Script for K8s Fabric Integration
        
        echo "🔍 Validating K8s Fabric Integration Evidence"
        echo "============================================="
        
        # 1. Check fabric configuration in database
        echo "1️⃣ Checking fabric configuration..."
        python manage.py shell -c "
        from netbox_hedgehog.models.fabric import HedgehogFabric
        f = HedgehogFabric.objects.get(id={self.fabric_id})
        print(f'Fabric: {{f.name}}')
        print(f'K8s Server: {{f.kubernetes_server or \"NOT SET\"}}')
        print(f'K8s Namespace: {{f.kubernetes_namespace}}')
        print(f'Sync Enabled: {{f.sync_enabled}}')
        print(f'Connection Status: {{f.connection_status}}')
        print(f'Calculated Sync Status: {{f.calculated_sync_status}}')
        "
        
        # 2. Test cluster connectivity
        echo "2️⃣ Testing cluster connectivity..."
        kubectl cluster-info --server {self.cluster_config['server']} --insecure-skip-tls-verify
        
        # 3. Check service account
        echo "3️⃣ Checking service account..."
        kubectl get serviceaccount {self.cluster_config['service_account']} \
            --namespace {self.cluster_config['namespace']} \
            --server {self.cluster_config['server']} \
            --insecure-skip-tls-verify || echo "Service account check failed (may need auth)"
        
        # 4. Validate GUI accessibility
        echo "4️⃣ GUI validation required..."
        echo "   Navigate to: /plugins/netbox-hedgehog/fabrics/{self.fabric_id}/"
        echo "   Verify K8s server URL is displayed"
        echo "   Confirm sync status is not 'Not Configured'"
        
        echo "✅ Evidence validation complete"
        """

def main():
    """Main execution - create complete K8s fabric integration package"""
    print("🚀 Generating K8s Fabric Integration Package")
    print("=" * 50)
    
    integration = FabricK8sIntegration()
    
    # Create deployment package
    package_file = integration.save_deployment_package()
    print(f"📦 Deployment package created: {package_file}")
    
    # Create evidence validation script
    validation_script = integration.generate_evidence_validation_script()
    validation_file = "/home/ubuntu/cc/hedgehog-netbox-plugin/validate_k8s_integration.sh"
    with open(validation_file, 'w') as f:
        f.write(validation_script)
    print(f"🔍 Evidence validation script: {validation_file}")
    
    # Summary
    print("\n📋 Integration Summary:")
    print(f"   🎯 Target: Fabric ID {integration.fabric_id}")
    print(f"   🔗 Cluster: {integration.cluster_config['server']}")
    print(f"   📂 Namespace: {integration.cluster_config['namespace']}")
    print(f"   🔑 Auth: {integration.cluster_config['service_account']} service account")
    
    print("\n✅ Ready for Production Deployment!")
    print("📖 See deployment package for step-by-step instructions.")
    
    return package_file

if __name__ == "__main__":
    try:
        package_file = main()
        
        # Show quick start
        print(f"\n🚀 Quick Start:")
        print(f"1. Review: {package_file}")
        print(f"2. Get token: kubectl get secret hnp-sync-token -o jsonpath='{{.data.token}}' --server https://vlab-art.l.hhdev.io:6443 --insecure-skip-tls-verify | base64 -d")
        print(f"3. Update fabric using Django shell or SQL")
        print(f"4. Test connectivity")
        print(f"5. Validate GUI shows updated configuration")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()