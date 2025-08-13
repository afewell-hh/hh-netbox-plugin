#!/usr/bin/env python3
"""
Kubernetes Integration Testing
Direct testing of K8s API connectivity and CRD synchronization
"""

import asyncio
import json
import time
import subprocess
from datetime import datetime
from typing import Dict, List, Any, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class KubernetesIntegrationTester:
    """Test Kubernetes integration functionality"""
    
    def __init__(self):
        self.container_id = "b05eb5eff181"
        self.k8s_endpoint = "vlab-art.l.hhdev.io:6443"
        self.test_session_id = f"k8s_integration_{int(time.time())}"
    
    async def test_kubernetes_connectivity(self) -> Dict[str, Any]:
        """Test basic Kubernetes API connectivity"""
        start_time = time.time()
        
        try:
            # Test K8s connection from within container
            k8s_test = subprocess.run([
                'docker', 'exec', self.container_id,
                'python', '-c',
                '''
import os
import ssl
import socket
from urllib3 import disable_warnings
from urllib3.exceptions import InsecureRequestWarning
import requests

disable_warnings(InsecureRequestWarning)

def test_k8s_connection():
    try:
        # Test basic network connectivity
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        result = sock.connect_ex(('vlab-art.l.hhdev.io', 6443))
        sock.close()
        
        network_reachable = result == 0
        
        # Test HTTPS endpoint
        try:
            response = requests.get(
                'https://vlab-art.l.hhdev.io:6443/version',
                verify=False,
                timeout=10
            )
            https_status = response.status_code
            response_data = response.text[:200]
        except Exception as e:
            https_status = 0
            response_data = str(e)
        
        result = {
            "network_reachable": network_reachable,
            "https_status": https_status,
            "response_preview": response_data,
            "endpoint": "vlab-art.l.hhdev.io:6443"
        }
        
        print(f"K8S_CONNECTIVITY: {result}")
        return result
        
    except Exception as e:
        print(f"K8S_ERROR: {str(e)}")
        return {"error": str(e)}

test_k8s_connection()
                '''
            ], capture_output=True, text=True, timeout=30)
            
            # Parse results
            output_lines = k8s_test.stdout.strip().split('\n')
            connectivity_data = None
            
            for line in output_lines:
                if line.startswith('K8S_CONNECTIVITY:'):
                    connectivity_data = eval(line.replace('K8S_CONNECTIVITY: ', ''))
                    break
                elif line.startswith('K8S_ERROR:'):
                    error_msg = line.replace('K8S_ERROR: ', '')
                    return {
                        "test_name": "Kubernetes Connectivity",
                        "status": "ERROR",
                        "duration": time.time() - start_time,
                        "error": error_msg
                    }
            
            if connectivity_data:
                # Evaluate connectivity success
                success = connectivity_data.get('network_reachable', False) and connectivity_data.get('https_status', 0) != 0
                
                result = {
                    "test_name": "Kubernetes Connectivity",
                    "status": "PASS" if success else "FAIL",
                    "duration": time.time() - start_time,
                    "details": connectivity_data
                }
                
                if not success:
                    result["error"] = f"K8s connectivity failed - Network: {connectivity_data.get('network_reachable')}, HTTPS: {connectivity_data.get('https_status')}"
            else:
                result = {
                    "test_name": "Kubernetes Connectivity",
                    "status": "FAIL",
                    "duration": time.time() - start_time,
                    "error": "No connectivity data returned",
                    "details": {
                        "stdout": k8s_test.stdout,
                        "stderr": k8s_test.stderr
                    }
                }
            
            return result
            
        except Exception as e:
            return {
                "test_name": "Kubernetes Connectivity", 
                "status": "ERROR",
                "duration": time.time() - start_time,
                "error": str(e)
            }
    
    async def test_kubernetes_authentication(self) -> Dict[str, Any]:
        """Test Kubernetes authentication setup"""
        start_time = time.time()
        
        try:
            # Check K8s authentication configuration
            auth_test = subprocess.run([
                'docker', 'exec', self.container_id,
                'python', '-c',
                '''
import os
from pathlib import Path

def check_k8s_auth():
    auth_info = {
        "service_account_exists": False,
        "token_exists": False,
        "ca_cert_exists": False,
        "kubeconfig_exists": False,
        "env_vars": {}
    }
    
    # Check service account files (in-cluster auth)
    sa_path = Path('/var/run/secrets/kubernetes.io/serviceaccount')
    if sa_path.exists():
        auth_info["service_account_exists"] = True
        auth_info["token_exists"] = (sa_path / 'token').exists()
        auth_info["ca_cert_exists"] = (sa_path / 'ca.crt').exists()
    
    # Check kubeconfig
    kubeconfig_paths = [
        os.path.expanduser('~/.kube/config'),
        '/root/.kube/config',
        os.environ.get('KUBECONFIG', '')
    ]
    
    for path in kubeconfig_paths:
        if path and Path(path).exists():
            auth_info["kubeconfig_exists"] = True
            auth_info["kubeconfig_path"] = path
            break
    
    # Check environment variables
    k8s_env_vars = ['KUBERNETES_SERVICE_HOST', 'KUBERNETES_SERVICE_PORT', 'KUBECONFIG']
    for var in k8s_env_vars:
        auth_info["env_vars"][var] = os.environ.get(var, 'Not set')
    
    print(f"K8S_AUTH: {auth_info}")
    return auth_info

check_k8s_auth()
                '''
            ], capture_output=True, text=True, timeout=15)
            
            # Parse auth results
            output_lines = auth_test.stdout.strip().split('\n')
            auth_data = None
            
            for line in output_lines:
                if line.startswith('K8S_AUTH:'):
                    auth_data = eval(line.replace('K8S_AUTH: ', ''))
                    break
            
            if auth_data:
                # Check if any auth method is available
                auth_available = any([
                    auth_data.get('service_account_exists', False) and auth_data.get('token_exists', False),
                    auth_data.get('kubeconfig_exists', False),
                    auth_data.get('env_vars', {}).get('KUBERNETES_SERVICE_HOST') != 'Not set'
                ])
                
                result = {
                    "test_name": "Kubernetes Authentication",
                    "status": "PASS" if auth_available else "FAIL",
                    "duration": time.time() - start_time,
                    "details": auth_data
                }
                
                if not auth_available:
                    result["error"] = "No valid Kubernetes authentication method found"
            else:
                result = {
                    "test_name": "Kubernetes Authentication",
                    "status": "FAIL",
                    "duration": time.time() - start_time,
                    "error": "Could not retrieve authentication configuration"
                }
            
            return result
            
        except Exception as e:
            return {
                "test_name": "Kubernetes Authentication",
                "status": "ERROR",
                "duration": time.time() - start_time,
                "error": str(e)
            }
    
    async def test_crd_synchronization(self) -> Dict[str, Any]:
        """Test CRD synchronization functionality"""
        start_time = time.time()
        
        try:
            # Test CRD operations
            crd_test = subprocess.run([
                'docker', 'exec', self.container_id,
                'python', '-c',
                '''
import sys
import json

def test_crd_operations():
    try:
        # Try to import K8s client
        from kubernetes import client, config
        
        # Load configuration
        try:
            config.load_incluster_config()
            config_loaded = "incluster"
        except:
            try:
                config.load_kube_config()
                config_loaded = "kubeconfig"
            except:
                config_loaded = "failed"
        
        if config_loaded == "failed":
            print(f"CRD_TEST: {{'config_loaded': False, 'error': 'No valid K8s config'}}")
            return
        
        # Test API client
        v1 = client.CoreV1Api()
        custom_api = client.CustomObjectsApi()
        
        # Test basic API call
        try:
            namespaces = v1.list_namespace(limit=1)
            api_accessible = True
            namespace_count = len(namespaces.items)
        except Exception as e:
            api_accessible = False
            namespace_count = 0
            api_error = str(e)
        
        # Test CRD listing
        try:
            api_extensions = client.ApiextensionsV1Api()
            crds = api_extensions.list_custom_resource_definition(limit=5)
            crd_accessible = True
            crd_count = len(crds.items)
            crd_names = [item.metadata.name for item in crds.items[:3]]
        except Exception as e:
            crd_accessible = False
            crd_count = 0
            crd_names = []
            crd_error = str(e)
        
        result = {
            "config_loaded": config_loaded,
            "api_accessible": api_accessible,
            "namespace_count": namespace_count,
            "crd_accessible": crd_accessible,
            "crd_count": crd_count,
            "crd_examples": crd_names
        }
        
        if not api_accessible:
            result["api_error"] = api_error
        if not crd_accessible:
            result["crd_error"] = crd_error
        
        print(f"CRD_TEST: {result}")
        
    except ImportError as e:
        print(f"CRD_ERROR: Kubernetes client not available - {e}")
    except Exception as e:
        print(f"CRD_ERROR: {e}")

test_crd_operations()
                '''
            ], capture_output=True, text=True, timeout=30)
            
            # Parse CRD test results
            output_lines = crd_test.stdout.strip().split('\n')
            crd_data = None
            
            for line in output_lines:
                if line.startswith('CRD_TEST:'):
                    crd_data = eval(line.replace('CRD_TEST: ', ''))
                    break
                elif line.startswith('CRD_ERROR:'):
                    error_msg = line.replace('CRD_ERROR: ', '')
                    return {
                        "test_name": "CRD Synchronization",
                        "status": "ERROR",
                        "duration": time.time() - start_time,
                        "error": error_msg
                    }
            
            if crd_data:
                # Evaluate CRD functionality
                success = all([
                    crd_data.get('config_loaded') != "failed",
                    crd_data.get('api_accessible', False),
                    crd_data.get('crd_accessible', False)
                ])
                
                result = {
                    "test_name": "CRD Synchronization",
                    "status": "PASS" if success else "FAIL",
                    "duration": time.time() - start_time,
                    "details": crd_data
                }
                
                if not success:
                    issues = []
                    if crd_data.get('config_loaded') == "failed":
                        issues.append("K8s config loading failed")
                    if not crd_data.get('api_accessible', False):
                        issues.append("K8s API not accessible")
                    if not crd_data.get('crd_accessible', False):
                        issues.append("CRD API not accessible")
                    
                    result["error"] = f"CRD sync issues: {', '.join(issues)}"
            else:
                result = {
                    "test_name": "CRD Synchronization",
                    "status": "FAIL",
                    "duration": time.time() - start_time,
                    "error": "No CRD test data returned"
                }
            
            return result
            
        except Exception as e:
            return {
                "test_name": "CRD Synchronization",
                "status": "ERROR",
                "duration": time.time() - start_time,
                "error": str(e)
            }
    
    async def run_all_k8s_tests(self) -> Dict[str, Any]:
        """Execute all Kubernetes integration tests"""
        logger.info(f"☸️  Starting Kubernetes integration tests - Session: {self.test_session_id}")
        
        # Run tests sequentially for K8s (connection dependencies)
        tests = [
            self.test_kubernetes_connectivity(),
            self.test_kubernetes_authentication(),
            self.test_crd_synchronization()
        ]
        
        results = []
        for test in tests:
            result = await test
            results.append(result)
            
            status_icon = "✅" if result["status"] == "PASS" else "❌" if result["status"] == "FAIL" else "⚠️"
            logger.info(f"{status_icon} {result['test_name']}: {result['status']} ({result['duration']:.2f}s)")
            
            if "error" in result:
                logger.error(f"   Error: {result['error']}")
        
        # Generate summary
        summary = {
            "session_id": self.test_session_id,
            "timestamp": datetime.now().isoformat(),
            "test_type": "Kubernetes Integration Testing",
            "k8s_endpoint": self.k8s_endpoint,
            "results": results,
            "summary": {
                "total_tests": len(results),
                "passed": len([r for r in results if r["status"] == "PASS"]),
                "failed": len([r for r in results if r["status"] == "FAIL"]),
                "errors": len([r for r in results if r["status"] == "ERROR"])
            },
            "recommendations": self.generate_k8s_recommendations(results)
        }
        
        # Save results
        results_file = f"k8s_integration_results_{self.test_session_id}.json"
        with open(results_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        logger.info(f"📊 K8s integration results saved to: {results_file}")
        return summary
    
    def generate_k8s_recommendations(self, results: List[Dict[str, Any]]) -> List[str]:
        """Generate K8s-specific recommendations"""
        recommendations = []
        
        for result in results:
            if result["status"] in ["FAIL", "ERROR"]:
                if "Connectivity" in result["test_name"]:
                    recommendations.extend([
                        "Verify network connectivity to vlab-art.l.hhdev.io:6443",
                        "Check firewall rules and DNS resolution",
                        "Confirm Kubernetes cluster is running and accessible"
                    ])
                
                if "Authentication" in result["test_name"]:
                    recommendations.extend([
                        "Configure Kubernetes service account in container",
                        "Mount kubeconfig file or set KUBECONFIG environment variable",
                        "Verify RBAC permissions for the service account"
                    ])
                
                if "CRD" in result["test_name"]:
                    recommendations.extend([
                        "Install kubernetes Python client: pip install kubernetes",
                        "Verify CRD definitions are installed in the cluster",
                        "Check custom resource permissions and RBAC"
                    ])
        
        if not recommendations:
            recommendations.append("Kubernetes integration is fully functional")
        
        return list(set(recommendations))

async def main():
    """Main K8s testing execution"""
    tester = KubernetesIntegrationTester()
    
    try:
        summary = await tester.run_all_k8s_tests()
        
        print("\n" + "="*60)
        print("☸️  KUBERNETES INTEGRATION TEST RESULTS")
        print("="*60)
        print(f"📋 Session ID: {summary['session_id']}")
        print(f"🎯 Endpoint: {summary['k8s_endpoint']}")
        print(f"✅ Passed: {summary['summary']['passed']}")
        print(f"❌ Failed: {summary['summary']['failed']}")
        print(f"⚠️  Errors: {summary['summary']['errors']}")
        
        if summary['recommendations']:
            print("\n🔧 RECOMMENDATIONS:")
            for i, rec in enumerate(summary['recommendations'], 1):
                print(f"   {i}. {rec}")
        
        print("="*60)
        
        return summary
        
    except Exception as e:
        logger.error(f"K8s integration testing failed: {e}")
        return {"error": str(e), "status": "K8S_TEST_ERROR"}

if __name__ == "__main__":
    asyncio.run(main())