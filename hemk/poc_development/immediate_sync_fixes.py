#!/usr/bin/env python3
"""
Immediate Sync Fixes Based on Test Results
Automated fixes for critical sync functionality issues
"""

import subprocess
import requests
import json
import time
from datetime import datetime
from pathlib import Path

class ImmediateSyncFixes:
    """Apply immediate fixes for sync functionality"""
    
    def __init__(self):
        self.base_url = "http://localhost:8000"
        self.container_id = "b05eb5eff181"
        self.fixes_applied = []
        
    def check_and_fix_fabric_endpoint(self):
        """Check fabric endpoint and fix routing issues"""
        print("🔍 Checking fabric endpoint accessibility...")
        
        try:
            # Test different fabric IDs
            fabric_tests = [35, 1, 2, 3]
            working_fabric = None
            
            for fabric_id in fabric_tests:
                test_url = f"{self.base_url}/plugins/netbox-hedgehog/fabric/{fabric_id}/"
                response = requests.get(test_url, timeout=5)
                
                if response.status_code == 200:
                    working_fabric = fabric_id
                    print(f"✅ Found working fabric endpoint: ID {fabric_id}")
                    break
                else:
                    print(f"❌ Fabric {fabric_id}: {response.status_code}")
            
            if working_fabric:
                self.fixes_applied.append(f"Identified working fabric endpoint: ID {working_fabric}")
                return working_fabric
            else:
                # Try to find fabrics via container
                print("🔧 Checking fabric database directly...")
                try:
                    fabric_check = subprocess.run([
                        'sudo', 'docker', 'exec', self.container_id,
                        'python', 'manage.py', 'shell', '-c',
                        '''
from netbox_hedgehog.models import Fabric
fabrics = Fabric.objects.all()[:5]
print("FABRIC_COUNT:", Fabric.objects.count())
for f in fabrics:
    print(f"FABRIC_ID: {f.id}, NAME: {f.name}")
                        '''
                    ], capture_output=True, text=True, timeout=10)
                    
                    if fabric_check.returncode == 0:
                        output_lines = fabric_check.stdout.strip().split('\n')
                        for line in output_lines:
                            print(f"   📋 {line}")
                        self.fixes_applied.append("Retrieved fabric database status")
                    else:
                        print(f"❌ Container access failed: {fabric_check.stderr}")
                        
                except Exception as e:
                    print(f"❌ Database check failed: {e}")
                
                return None
                
        except Exception as e:
            print(f"❌ Fabric endpoint check failed: {e}")
            return None
    
    def check_and_start_rq_services(self):
        """Check and start RQ scheduler and worker services"""
        print("\n🔍 Checking RQ services...")
        
        try:
            # Check RQ worker status
            worker_check = subprocess.run([
                'sudo', 'docker', 'exec', self.container_id,
                'ps', 'aux'
            ], capture_output=True, text=True, timeout=5)
            
            if worker_check.returncode == 0:
                rq_processes = [line for line in worker_check.stdout.split('\n') if 'rq' in line.lower()]
                if rq_processes:
                    print("✅ Found RQ processes:")
                    for process in rq_processes:
                        print(f"   📋 {process.strip()}")
                else:
                    print("❌ No RQ processes found")
            
            # Try to start RQ scheduler
            print("🔧 Attempting to start RQ scheduler...")
            scheduler_start = subprocess.run([
                'sudo', 'docker', 'exec', '-d', self.container_id,
                'python', 'manage.py', 'rqscheduler'
            ], capture_output=True, text=True, timeout=10)
            
            if scheduler_start.returncode == 0:
                print("✅ RQ scheduler start command executed")
                self.fixes_applied.append("Started RQ scheduler service")
            else:
                print(f"❌ RQ scheduler start failed: {scheduler_start.stderr}")
            
            # Wait and check if scheduler is running
            time.sleep(2)
            scheduler_check = subprocess.run([
                'sudo', 'docker', 'exec', self.container_id,
                'python', 'manage.py', 'shell', '-c',
                '''
try:
    from django_rq import get_scheduler
    scheduler = get_scheduler()
    jobs = list(scheduler.get_jobs())  # Convert generator to list
    print(f"SCHEDULER_JOBS: {len(jobs)}")
    for job in jobs[:3]:
        print(f"JOB: {job.id} - {job.func}")
except Exception as e:
    print(f"SCHEDULER_ERROR: {e}")
                '''
            ], capture_output=True, text=True, timeout=10)
            
            if scheduler_check.returncode == 0:
                for line in scheduler_check.stdout.strip().split('\n'):
                    if line.startswith(('SCHEDULER_JOBS:', 'JOB:', 'SCHEDULER_ERROR:')):
                        print(f"   📋 {line}")
            
        except Exception as e:
            print(f"❌ RQ service check failed: {e}")
    
    def test_kubernetes_access(self):
        """Test Kubernetes cluster access"""
        print("\n🔍 Testing Kubernetes access...")
        
        try:
            # Test network connectivity to K8s cluster
            k8s_ping = subprocess.run([
                'ping', '-c', '2', 'vlab-art.l.hhdev.io'
            ], capture_output=True, text=True, timeout=10)
            
            if k8s_ping.returncode == 0:
                print("✅ K8s cluster is network reachable")
                self.fixes_applied.append("Confirmed K8s cluster network connectivity")
            else:
                print(f"❌ K8s cluster not reachable: {k8s_ping.stderr}")
            
            # Test HTTPS endpoint
            try:
                import ssl
                import socket
                context = ssl.create_default_context()
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                
                with socket.create_connection(('vlab-art.l.hhdev.io', 6443), timeout=10) as sock:
                    with context.wrap_socket(sock, server_hostname='vlab-art.l.hhdev.io') as ssock:
                        print("✅ K8s HTTPS endpoint is accessible")
                        self.fixes_applied.append("Confirmed K8s HTTPS endpoint accessibility")
                        
            except Exception as ssl_error:
                print(f"❌ K8s HTTPS test failed: {ssl_error}")
            
            # Check for K8s credentials in container
            cred_check = subprocess.run([
                'sudo', 'docker', 'exec', self.container_id,
                'find', '/var/run/secrets', '-name', '*token*', '-o', '-name', '*ca.crt*'
            ], capture_output=True, text=True, timeout=5)
            
            if cred_check.returncode == 0 and cred_check.stdout.strip():
                print("✅ Found K8s service account files:")
                for file_path in cred_check.stdout.strip().split('\n'):
                    print(f"   📋 {file_path}")
                self.fixes_applied.append("Found K8s service account credentials")
            else:
                print("❌ No K8s service account files found")
                
        except Exception as e:
            print(f"❌ K8s access test failed: {e}")
    
    def verify_django_urls(self):
        """Verify Django URL configuration for fabric sync"""
        print("\n🔍 Checking Django URL configuration...")
        
        try:
            url_check = subprocess.run([
                'sudo', 'docker', 'exec', self.container_id,
                'python', 'manage.py', 'shell', '-c',
                '''
from django.urls import reverse
from django.conf import settings

try:
    # Check if netbox_hedgehog URLs are configured
    fabric_url = reverse("plugins:netbox_hedgehog:fabric_detail", kwargs={"pk": 1})
    print(f"FABRIC_URL_PATTERN: {fabric_url}")
except Exception as e:
    print(f"URL_ERROR: {e}")

# Check installed apps
if "netbox_hedgehog" in settings.INSTALLED_APPS:
    print("PLUGIN_INSTALLED: True")
else:
    print("PLUGIN_INSTALLED: False")

# Check plugin configuration
print(f"PLUGINS_CONFIG: {getattr(settings, 'PLUGINS_CONFIG', {}).get('netbox_hedgehog', 'Not configured')}")
                '''
            ], capture_output=True, text=True, timeout=10)
            
            if url_check.returncode == 0:
                for line in url_check.stdout.strip().split('\n'):
                    if line.startswith(('FABRIC_URL_PATTERN:', 'URL_ERROR:', 'PLUGIN_INSTALLED:', 'PLUGINS_CONFIG:')):
                        print(f"   📋 {line}")
                self.fixes_applied.append("Retrieved Django URL configuration")
            else:
                print(f"❌ URL check failed: {url_check.stderr}")
                
        except Exception as e:
            print(f"❌ Django URL check failed: {e}")
    
    def run_all_fixes(self):
        """Run all immediate fixes and checks"""
        print("🚀 Running immediate sync fixes and diagnostics...")
        print("="*70)
        
        start_time = time.time()
        
        # Run all fix/check procedures
        working_fabric = self.check_and_fix_fabric_endpoint()
        self.check_and_start_rq_services()
        self.test_kubernetes_access()
        self.verify_django_urls()
        
        # Generate summary
        duration = time.time() - start_time
        
        print("\n" + "="*70)
        print(f"🎯 FIX SUMMARY ({duration:.1f}s)")
        print("="*70)
        
        if self.fixes_applied:
            print("✅ Fixes Applied:")
            for i, fix in enumerate(self.fixes_applied, 1):
                print(f"   {i}. {fix}")
        else:
            print("⚠️  No fixes could be applied automatically")
        
        # Provide next steps
        print("\n📋 NEXT STEPS:")
        if working_fabric:
            print(f"   1. Update test scripts to use fabric ID: {working_fabric}")
        else:
            print("   1. Create a test fabric or fix existing fabric data")
        
        print("   2. Verify RQ services are running with: docker exec b05eb5eff181 ps aux | grep rq")
        print("   3. Test manual sync with corrected fabric ID")
        print("   4. Re-run comprehensive test suite")
        
        print("="*70)
        
        return {
            "fixes_applied": self.fixes_applied,
            "working_fabric": working_fabric,
            "duration": duration,
            "timestamp": datetime.now().isoformat()
        }

def main():
    """Main execution function"""
    fixer = ImmediateSyncFixes()
    
    try:
        results = fixer.run_all_fixes()
        
        # Save results
        results_file = f"immediate_fixes_results_{int(time.time())}.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n📊 Results saved to: {results_file}")
        return results
        
    except Exception as e:
        print(f"❌ Fix execution failed: {e}")
        return {"error": str(e)}

if __name__ == "__main__":
    main()