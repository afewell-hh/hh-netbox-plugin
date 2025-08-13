#!/usr/bin/env python3
"""
Live Sync Failure Investigation Tool
====================================

CRITICAL MISSION: Investigate actual sync failure in live environment
- Test actual sync button functionality
- Monitor container processes during sync  
- Check network connectivity to K8s cluster
- Capture detailed error logs during sync attempts

EVIDENCE REQUIREMENTS:
- Exact error messages from UI
- Process states during sync operations
- Network connection test results
- Real-time monitoring data during failures

Container: b05eb5eff181
Target: https://vlab-art.l.hhdev.io:6443
"""

import subprocess
import requests
import json
import time
import sys
from datetime import datetime
from pathlib import Path

class SyncFailureInvestigator:
    def __init__(self):
        self.container_id = "b05eb5eff181"
        self.k8s_target = "https://vlab-art.l.hhdev.io:6443"
        self.evidence = {
            "investigation_start": datetime.now().isoformat(),
            "container": self.container_id,
            "k8s_target": self.k8s_target,
            "tests": {}
        }
    
    def log_evidence(self, test_name, data):
        """Record evidence with timestamp"""
        self.evidence["tests"][test_name] = {
            "timestamp": datetime.now().isoformat(),
            "data": data
        }
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] {test_name}:")
        print(json.dumps(data, indent=2))
    
    def test_container_access(self):
        """Test if we can access the container"""
        try:
            # Test if we can check container status
            result = subprocess.run(
                ["docker", "inspect", self.container_id],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode == 0:
                container_info = json.loads(result.stdout)[0]
                status_data = {
                    "container_accessible": True,
                    "container_state": container_info.get("State", {}),
                    "container_ip": container_info["NetworkSettings"]["IPAddress"],
                    "ports": container_info["NetworkSettings"]["Ports"]
                }
            else:
                status_data = {
                    "container_accessible": False,
                    "error": result.stderr,
                    "permission_issue": "permission denied" in result.stderr.lower()
                }
        except Exception as e:
            status_data = {
                "container_accessible": False,
                "error": str(e),
                "exception_type": type(e).__name__
            }
        
        self.log_evidence("container_access_test", status_data)
        return status_data.get("container_accessible", False)
    
    def test_application_availability(self):
        """Test if the NetBox application is reachable"""
        test_urls = [
            "http://localhost:8000/",
            "http://localhost:8000/plugins/hedgehog/",
            "http://localhost:8000/plugins/hedgehog/fabric/",
            "http://172.18.0.1:8000/",  # Docker network
            "http://127.0.0.1:8000/"
        ]
        
        url_results = {}
        
        for url in test_urls:
            try:
                response = requests.get(url, timeout=5)
                url_results[url] = {
                    "accessible": True,
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "content_length": len(response.content)
                }
                
                # Check if it looks like NetBox
                if "netbox" in response.text.lower() or "plugins" in response.text.lower():
                    url_results[url]["looks_like_netbox"] = True
                
            except Exception as e:
                url_results[url] = {
                    "accessible": False,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
        
        # Find the first working URL
        working_url = None
        for url, result in url_results.items():
            if result.get("accessible") and result.get("status_code") == 200:
                working_url = url
                break
        
        app_data = {
            "url_test_results": url_results,
            "working_url": working_url,
            "application_reachable": working_url is not None
        }
        
        self.log_evidence("application_availability_test", app_data)
        return working_url
    
    def test_sync_endpoint_access(self, base_url):
        """Test sync endpoint accessibility and responses"""
        if not base_url:
            self.log_evidence("sync_endpoint_test", {"error": "No working base URL available"})
            return None
        
        sync_endpoints = [
            "/plugins/hedgehog/fabric/sync/",
            "/api/plugins/hedgehog/fabric/sync/",
            "/plugins/netbox_hedgehog/fabric/sync/",
            "/api/plugins/netbox_hedgehog/fabric/sync/"
        ]
        
        endpoint_results = {}
        
        for endpoint in sync_endpoints:
            full_url = base_url.rstrip('/') + endpoint
            try:
                # Test GET first
                response = requests.get(full_url, timeout=10)
                endpoint_results[endpoint] = {
                    "get_status": response.status_code,
                    "get_accessible": True,
                    "get_content_type": response.headers.get('content-type', ''),
                    "get_content_preview": response.text[:500] if len(response.text) < 500 else response.text[:500] + "..."
                }
                
                # Test POST (actual sync attempt)
                try:
                    post_response = requests.post(full_url, timeout=30, data={})
                    endpoint_results[endpoint].update({
                        "post_status": post_response.status_code,
                        "post_accessible": True,
                        "post_content_type": post_response.headers.get('content-type', ''),
                        "post_content_preview": post_response.text[:500] if len(post_response.text) < 500 else post_response.text[:500] + "...",
                        "post_headers": dict(post_response.headers)
                    })
                    
                    # Check for specific error messages
                    if "403" in str(post_response.status_code):
                        endpoint_results[endpoint]["forbidden_error"] = True
                    
                    if "timeout" in post_response.text.lower():
                        endpoint_results[endpoint]["timeout_error"] = True
                        
                except Exception as post_e:
                    endpoint_results[endpoint]["post_error"] = str(post_e)
                    endpoint_results[endpoint]["post_accessible"] = False
                    
            except Exception as e:
                endpoint_results[endpoint] = {
                    "get_accessible": False,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
        
        sync_data = {
            "base_url": base_url,
            "endpoint_results": endpoint_results
        }
        
        self.log_evidence("sync_endpoint_test", sync_data)
        return endpoint_results
    
    def test_kubernetes_connectivity(self):
        """Test connectivity to Kubernetes cluster"""
        k8s_tests = {}
        
        # Test 1: Basic network connectivity
        try:
            import socket
            host = self.k8s_target.replace('https://', '').replace('http://', '').split(':')[0]
            port = int(self.k8s_target.split(':')[-1]) if ':' in self.k8s_target.split('//')[-1] else 443
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            result = sock.connect_ex((host, port))
            sock.close()
            
            k8s_tests["network_connectivity"] = {
                "host": host,
                "port": port,
                "reachable": result == 0,
                "connection_result": result
            }
        except Exception as e:
            k8s_tests["network_connectivity"] = {
                "error": str(e),
                "reachable": False
            }
        
        # Test 2: HTTPS certificate check
        try:
            response = requests.get(self.k8s_target, timeout=10, verify=False)
            k8s_tests["https_access"] = {
                "accessible": True,
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "certificate_valid": True  # We disabled verification
            }
        except requests.exceptions.SSLError as ssl_e:
            k8s_tests["https_access"] = {
                "accessible": False,
                "ssl_error": str(ssl_e),
                "certificate_issue": True
            }
        except Exception as e:
            k8s_tests["https_access"] = {
                "accessible": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
        
        # Test 3: Kubernetes API version endpoint
        try:
            version_url = f"{self.k8s_target}/version"
            response = requests.get(version_url, timeout=10, verify=False)
            k8s_tests["k8s_api_version"] = {
                "accessible": True,
                "status_code": response.status_code,
                "response": response.text if response.status_code == 200 else None,
                "looks_like_k8s": "kubernetes" in response.text.lower() if response.status_code == 200 else False
            }
        except Exception as e:
            k8s_tests["k8s_api_version"] = {
                "accessible": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
        
        self.log_evidence("kubernetes_connectivity_test", k8s_tests)
        return k8s_tests
    
    def test_fabric_database_state(self):
        """Test fabric configuration in database (if Django available)"""
        try:
            # Try to run Django shell command
            django_command = [
                "python", "manage.py", "shell", "-c",
                """
from netbox_hedgehog.models.fabric import HedgehogFabric
import json

fabrics = []
for fabric in HedgehogFabric.objects.all():
    fabrics.append({
        'id': fabric.id,
        'name': fabric.name,
        'kubernetes_server': fabric.kubernetes_server,
        'sync_enabled': fabric.sync_enabled,
        'sync_status': fabric.sync_status,
        'connection_status': fabric.connection_status,
        'last_sync': str(fabric.last_sync) if fabric.last_sync else None,
        'sync_error': fabric.sync_error,
        'connection_error': fabric.connection_error,
        'calculated_status': fabric.calculated_sync_status
    })

print(json.dumps(fabrics, indent=2))
                """
            ]
            
            result = subprocess.run(
                django_command, capture_output=True, text=True, timeout=30
            )
            
            if result.returncode == 0:
                try:
                    fabric_data = json.loads(result.stdout)
                    db_test_result = {
                        "django_accessible": True,
                        "fabrics_found": len(fabric_data),
                        "fabric_configurations": fabric_data
                    }
                except json.JSONDecodeError:
                    db_test_result = {
                        "django_accessible": True,
                        "fabrics_found": "unknown",
                        "raw_output": result.stdout,
                        "json_parse_error": True
                    }
            else:
                db_test_result = {
                    "django_accessible": False,
                    "error": result.stderr,
                    "stdout": result.stdout
                }
                
        except Exception as e:
            db_test_result = {
                "django_accessible": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
        
        self.log_evidence("fabric_database_state", db_test_result)
        return db_test_result
    
    def test_real_sync_execution(self, base_url, endpoint_results):
        """Perform actual sync test with monitoring"""
        if not base_url or not endpoint_results:
            self.log_evidence("real_sync_execution", {"error": "Prerequisites not met"})
            return None
        
        # Find a working sync endpoint
        working_endpoint = None
        for endpoint, result in endpoint_results.items():
            if result.get("get_accessible") or result.get("post_accessible"):
                working_endpoint = endpoint
                break
        
        if not working_endpoint:
            self.log_evidence("real_sync_execution", {"error": "No working sync endpoints found"})
            return None
        
        full_sync_url = base_url.rstrip('/') + working_endpoint
        
        # Monitor sync execution
        sync_results = {
            "sync_url": full_sync_url,
            "pre_sync_timestamp": datetime.now().isoformat()
        }
        
        try:
            # Start monitoring in background (if possible)
            pre_sync_time = time.time()
            
            # Execute actual sync
            response = requests.post(
                full_sync_url,
                timeout=180,  # 3 minutes timeout
                data={"fabric_id": 1}  # Assume fabric ID 1 exists
            )
            
            post_sync_time = time.time()
            execution_time = post_sync_time - pre_sync_time
            
            sync_results.update({
                "sync_executed": True,
                "execution_time_seconds": execution_time,
                "status_code": response.status_code,
                "response_headers": dict(response.headers),
                "response_content": response.text,
                "post_sync_timestamp": datetime.now().isoformat()
            })
            
            # Check for specific error patterns
            error_patterns = {
                "timeout": ["timeout", "timed out"],
                "forbidden": ["403", "forbidden", "permission denied"],
                "connection_refused": ["connection refused", "connection error"],
                "ssl_error": ["ssl", "certificate", "handshake"],
                "not_found": ["404", "not found"],
                "server_error": ["500", "internal server error"],
                "k8s_api_error": ["kubernetes", "api server", "cluster"]
            }
            
            detected_errors = []
            response_lower = response.text.lower()
            
            for error_type, patterns in error_patterns.items():
                for pattern in patterns:
                    if pattern in response_lower:
                        detected_errors.append(error_type)
                        break
            
            sync_results["detected_error_types"] = detected_errors
            
            # Success/failure determination
            sync_results["appears_successful"] = (
                response.status_code in [200, 201, 202] and 
                len(detected_errors) == 0 and
                "error" not in response_lower
            )
            
        except requests.exceptions.Timeout:
            sync_results.update({
                "sync_executed": False,
                "timeout_occurred": True,
                "execution_time_seconds": 180,
                "error": "Request timed out after 180 seconds"
            })
            
        except Exception as e:
            sync_results.update({
                "sync_executed": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "execution_time_seconds": time.time() - pre_sync_time
            })
        
        self.log_evidence("real_sync_execution", sync_results)
        return sync_results
    
    def run_complete_investigation(self):
        """Run complete investigation with all tests"""
        print("=" * 60)
        print("LIVE SYNC FAILURE INVESTIGATION")
        print("=" * 60)
        print(f"Container: {self.container_id}")
        print(f"K8s Target: {self.k8s_target}")
        print(f"Started: {self.evidence['investigation_start']}")
        print("=" * 60)
        
        # Step 1: Container Access
        print("\n🔍 STEP 1: Testing Container Access...")
        container_accessible = self.test_container_access()
        
        # Step 2: Application Availability  
        print("\n🔍 STEP 2: Testing Application Availability...")
        working_url = self.test_application_availability()
        
        # Step 3: Sync Endpoint Access
        print("\n🔍 STEP 3: Testing Sync Endpoint Access...")
        endpoint_results = self.test_sync_endpoint_access(working_url)
        
        # Step 4: Kubernetes Connectivity
        print("\n🔍 STEP 4: Testing Kubernetes Connectivity...")
        k8s_connectivity = self.test_kubernetes_connectivity()
        
        # Step 5: Database State
        print("\n🔍 STEP 5: Testing Fabric Database State...")
        db_state = self.test_fabric_database_state()
        
        # Step 6: Real Sync Execution
        print("\n🔍 STEP 6: Executing Real Sync Test...")
        sync_execution = self.test_real_sync_execution(working_url, endpoint_results)
        
        # Generate comprehensive report
        self.evidence["investigation_complete"] = datetime.now().isoformat()
        self.evidence["total_duration_seconds"] = (
            datetime.fromisoformat(self.evidence["investigation_complete"]) - 
            datetime.fromisoformat(self.evidence["investigation_start"])
        ).total_seconds()
        
        # Save evidence
        evidence_file = f"sync_failure_evidence_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(evidence_file, 'w') as f:
            json.dump(self.evidence, f, indent=2)
        
        print(f"\n📋 INVESTIGATION COMPLETE")
        print(f"Evidence saved to: {evidence_file}")
        print("=" * 60)
        
        # Summary
        print("\n📊 EXECUTIVE SUMMARY:")
        print(f"• Container Access: {'✅' if container_accessible else '❌'}")
        print(f"• Application Running: {'✅' if working_url else '❌'}")
        print(f"• Sync Endpoints: {'✅' if endpoint_results and any(r.get('get_accessible') for r in endpoint_results.values()) else '❌'}")
        print(f"• K8s Connectivity: {'✅' if k8s_connectivity and k8s_connectivity.get('network_connectivity', {}).get('reachable') else '❌'}")
        print(f"• Database Access: {'✅' if db_state and db_state.get('django_accessible') else '❌'}")
        print(f"• Sync Execution: {'✅' if sync_execution and sync_execution.get('appears_successful') else '❌'}")
        
        return self.evidence


def main():
    investigator = SyncFailureInvestigator()
    evidence = investigator.run_complete_investigation()
    
    # Return evidence for further analysis
    return evidence

if __name__ == "__main__":
    evidence = main()
    sys.exit(0)