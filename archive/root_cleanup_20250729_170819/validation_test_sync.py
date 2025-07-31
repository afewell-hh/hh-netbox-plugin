#!/usr/bin/env python3
"""
Validation script to test the sync button functionality and verify Kubernetes connection claims.
"""

import requests
import json
import time
import subprocess
import os
from datetime import datetime, timedelta

class SyncValidationTester:
    def __init__(self):
        self.base_url = "http://localhost:8000"
        self.session = requests.Session()
        self.csrf_token = None
        
    def authenticate(self):
        """Login to NetBox and get session cookies"""
        try:
            # Get login page and CSRF token
            login_page = self.session.get(f"{self.base_url}/login/")
            login_page.raise_for_status()
            
            # Extract CSRF token from login page
            import re
            csrf_match = re.search(r'csrfmiddlewaretoken.*?value="([^"]+)"', login_page.text)
            if not csrf_match:
                print("❌ Could not extract CSRF token")
                return False
                
            self.csrf_token = csrf_match.group(1)
            
            # Login
            login_data = {
                'username': 'admin',
                'password': 'admin',
                'csrfmiddlewaretoken': self.csrf_token
            }
            
            login_response = self.session.post(
                f"{self.base_url}/login/", 
                data=login_data,
                headers={'Referer': f"{self.base_url}/login/"}
            )
            
            if login_response.status_code == 200 and "Dashboard" in login_response.text:
                print("✅ Successfully authenticated to NetBox")
                return True
            else:
                print(f"❌ Authentication failed: {login_response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Authentication error: {e}")
            return False
    
    def test_fabric_sync_button(self):
        """Test the fabric sync button functionality"""
        print("\n=== Testing Fabric Sync Button ===")
        
        try:
            # Get fabric list page
            fabrics_response = self.session.get(f"{self.base_url}/plugins/hedgehog/fabrics/")
            if fabrics_response.status_code != 200:
                print(f"❌ Could not access fabric list: {fabrics_response.status_code}")
                return False
                
            print("✅ Accessed fabric list page")
            
            # Look for fabric detail URLs
            import re
            fabric_urls = re.findall(r'/plugins/hedgehog/fabrics/(\d+)/', fabrics_response.text)
            
            if not fabric_urls:
                print("❌ No fabric detail pages found")
                return False
                
            fabric_id = fabric_urls[0]
            print(f"✅ Found fabric with ID: {fabric_id}")
            
            # Access fabric detail page
            detail_response = self.session.get(f"{self.base_url}/plugins/hedgehog/fabrics/{fabric_id}/")
            if detail_response.status_code != 200:
                print(f"❌ Could not access fabric detail: {detail_response.status_code}")
                return False
                
            print("✅ Accessed fabric detail page")
            
            # Check for sync button
            if "Sync from Fabric" in detail_response.text or "sync" in detail_response.text.lower():
                print("✅ Found sync button on fabric detail page")
                
                # Try to extract sync URL
                sync_urls = re.findall(r'/plugins/hedgehog/[^"\']*sync[^"\']*', detail_response.text)
                if sync_urls:
                    sync_url = sync_urls[0]
                    print(f"✅ Found sync URL: {sync_url}")
                    
                    # Test the sync functionality
                    return self.test_sync_operation(sync_url)
                else:
                    print("⚠️ Found sync button but no sync URL")
                    return False
            else:
                print("❌ No sync button found on fabric detail page")
                return False
                
        except Exception as e:
            print(f"❌ Error testing fabric sync: {e}")
            return False
    
    def test_sync_operation(self, sync_url):
        """Test the actual sync operation"""
        print(f"\n=== Testing Sync Operation: {sync_url} ===")
        
        try:
            # Get updated CSRF token
            csrf_response = self.session.get(f"{self.base_url}/plugins/hedgehog/fabrics/")
            import re
            csrf_match = re.search(r'csrfmiddlewaretoken.*?value="([^"]+)"', csrf_response.text)
            if csrf_match:
                self.csrf_token = csrf_match.group(1)
            
            # Try the sync operation
            sync_response = self.session.post(
                f"{self.base_url}{sync_url}",
                headers={
                    'X-CSRFToken': self.csrf_token,
                    'Referer': f"{self.base_url}/plugins/hedgehog/fabrics/1/"
                }
            )
            
            print(f"✅ Sync request sent: {sync_response.status_code}")
            print(f"Response content: {sync_response.text[:500]}...")
            
            # Check for error messages
            if "error" in sync_response.text.lower() or "fail" in sync_response.text.lower():
                print("⚠️ Sync response contains error messages")
                
            # Check for success indicators
            if "success" in sync_response.text.lower() or sync_response.status_code == 200:
                print("✅ Sync operation appears to have executed")
                return True
            else:
                print("❌ Sync operation may have failed")
                return False
                
        except Exception as e:
            print(f"❌ Error during sync operation: {e}")
            return False
    
    def check_kubernetes_environment(self):
        """Check for any Kubernetes configuration in the container"""
        print("\n=== Checking Kubernetes Environment ===")
        
        try:
            # Check if kubectl is available
            result = subprocess.run(['sudo', 'docker', 'exec', '949978661a38', 'which', 'kubectl'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                print("✅ kubectl found in container")
            else:
                print("❌ kubectl not found in container")
            
            # Check for kubeconfig files
            result = subprocess.run(['sudo', 'docker', 'exec', '949978661a38', 'find', '/etc', '/root', '/opt', '-name', '*kubeconfig*', '-o', '-name', '*.kubeconfig'], 
                                  capture_output=True, text=True, timeout=10)
            if result.stdout.strip():
                print(f"✅ Found kubeconfig files: {result.stdout.strip()}")
            else:
                print("❌ No kubeconfig files found")
            
            # Check environment variables
            result = subprocess.run(['sudo', 'docker', 'exec', '949978661a38', 'env'], 
                                  capture_output=True, text=True, timeout=10)
            k8s_vars = [line for line in result.stdout.split('\n') if 'KUBERNETES' in line or 'KUBE' in line]
            if k8s_vars:
                print(f"✅ Found Kubernetes env vars: {k8s_vars}")
            else:
                print("❌ No Kubernetes environment variables found")
                
        except Exception as e:
            print(f"❌ Error checking Kubernetes environment: {e}")
    
    def check_container_logs(self):
        """Check container logs for sync-related activity"""
        print("\n=== Checking Container Logs ===")
        
        try:
            # Get recent logs
            result = subprocess.run(['sudo', 'docker', 'logs', '--tail', '50', '949978661a38'], 
                                  capture_output=True, text=True, timeout=10)
            
            # Look for sync-related log entries
            sync_logs = [line for line in result.stdout.split('\n') if 'sync' in line.lower() or 'kubernetes' in line.lower()]
            
            if sync_logs:
                print(f"✅ Found sync-related logs:")
                for log in sync_logs[-10:]:  # Show last 10
                    print(f"  {log}")
            else:
                print("❌ No sync-related logs found")
                
        except Exception as e:
            print(f"❌ Error checking container logs: {e}")
    
    def run_validation(self):
        """Run the complete validation suite"""
        print("🔍 VALIDATION: Testing Kubernetes Connection Investigation Findings")
        print("=" * 70)
        
        # Authentication
        if not self.authenticate():
            print("❌ VALIDATION FAILED: Could not authenticate to NetBox")
            return False
        
        # Test sync button
        sync_test_result = self.test_fabric_sync_button()
        
        # Check environment
        self.check_kubernetes_environment()
        
        # Check logs
        self.check_container_logs()
        
        print("\n" + "=" * 70)
        print("🔍 VALIDATION SUMMARY:")
        print(f"  Sync Button Test: {'✅ PASS' if sync_test_result else '❌ FAIL'}")
        
        return sync_test_result

if __name__ == "__main__":
    tester = SyncValidationTester()
    tester.run_validation()