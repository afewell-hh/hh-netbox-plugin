#!/usr/bin/env python3
"""
Diagnostic to understand why FGD sync isn't migrating files from raw/ to managed/.
"""

import requests
import json
import subprocess
import time
from datetime import datetime

class SyncDiagnostic:
    def __init__(self):
        self.fabric_id = 35
        self.headers = {
            'Authorization': 'Token ced6a3e0a978db0ad4de39cd66af4868372d7dd0',
            'Accept': 'application/json'
        }
        
    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")
        
    def check_fabric_configuration(self):
        """Check if fabric is properly configured for GitOps sync."""
        self.log("Checking fabric GitOps configuration...")
        
        try:
            response = requests.get(
                f'http://localhost:8000/api/plugins/hedgehog/fabrics/{self.fabric_id}/',
                headers=self.headers
            )
            
            if response.status_code == 200:
                fabric = response.json()
                
                self.log(f"Fabric Name: {fabric.get('name')}")
                self.log(f"Git Repository: {fabric.get('git_repository', 'None')}")
                self.log(f"Connection Status: {fabric.get('connection_status', 'unknown')}")
                self.log(f"Sync Status: {fabric.get('sync_status', 'unknown')}")
                
                # Check critical fields for GitOps
                git_repo = fabric.get('git_repository')
                if not git_repo:
                    self.log("❌ ISSUE: No Git repository configured!")
                    self.log("   Sync cannot work without a Git repository")
                    return False
                else:
                    self.log(f"✅ Git repository configured: {git_repo}")
                    return True
                    
            else:
                self.log(f"❌ Could not get fabric info: {response.status_code}")
                return False
                
        except Exception as e:
            self.log(f"❌ Error checking fabric: {str(e)}")
            return False
    
    def check_repository_state_before_sync(self):
        """Check repository state before triggering sync."""
        self.log("Checking repository state before sync...")
        
        try:
            result = subprocess.run([
                'python3', 'test_fgd_postsync_state_v2.py'
            ], capture_output=True, text=True, cwd='/home/ubuntu/cc/hedgehog-netbox-plugin/', timeout=30)
            
            # Extract key information
            raw_files = []
            managed_files = []
            
            for line in result.stdout.split('\n'):
                if 'raw/' in line and 'CRs' in line:
                    raw_files.append(line.strip())
                elif 'managed/' in line and 'CRs' in line:
                    managed_files.append(line.strip())
            
            self.log("Raw directory files:")
            for f in raw_files:
                self.log(f"  {f}")
            
            self.log("Managed directory files:")
            for f in managed_files:
                self.log(f"  {f}")
            
            return {'raw_files': raw_files, 'managed_files': managed_files}
            
        except Exception as e:
            self.log(f"❌ Error checking repository state: {str(e)}")
            return None
    
    def trigger_sync_and_monitor(self):
        """Trigger sync and monitor for any changes."""
        self.log("Triggering sync and monitoring changes...")
        
        # Get before state
        before_state = self.check_repository_state_before_sync()
        
        # Trigger sync via authenticated session
        try:
            session = requests.Session()
            
            # Get CSRF token and login
            login_response = session.get('http://localhost:8000/login/')
            import re
            csrf_match = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', login_response.text)
            
            if csrf_match:
                csrf_token = csrf_match.group(1)
                
                # Login
                login_data = {
                    'csrfmiddlewaretoken': csrf_token,
                    'username': 'admin',
                    'password': 'admin',
                    'next': '/'
                }
                
                login_result = session.post('http://localhost:8000/login/', data=login_data)
                
                if login_result.status_code == 302:
                    # Test connection first
                    test_conn = session.post(f'http://localhost:8000/plugins/hedgehog/fabrics/{self.fabric_id}/test-connection/')
                    self.log(f"Connection test: {test_conn.status_code}")
                    
                    time.sleep(2)
                    
                    # Trigger sync
                    sync_response = session.post(f'http://localhost:8000/plugins/hedgehog/fabrics/{self.fabric_id}/sync/')
                    self.log(f"Sync trigger: {sync_response.status_code}")
                    
                    if sync_response.status_code == 200:
                        self.log("✅ Sync triggered successfully")
                        
                        # Wait and check for changes
                        self.log("Waiting 15 seconds for sync processing...")
                        time.sleep(15)
                        
                        # Check after state
                        after_state = self.check_repository_state_before_sync()
                        
                        # Compare states
                        if before_state and after_state:
                            self.log("SYNC COMPARISON:")
                            
                            if len(after_state['raw_files']) != len(before_state['raw_files']):
                                self.log(f"✅ Raw files changed: {len(before_state['raw_files'])} → {len(after_state['raw_files'])}")
                            else:
                                self.log(f"⚠️  Raw files unchanged: {len(before_state['raw_files'])}")
                            
                            if len(after_state['managed_files']) != len(before_state['managed_files']):
                                self.log(f"✅ Managed files changed: {len(before_state['managed_files'])} → {len(after_state['managed_files'])}")
                            else:
                                self.log(f"⚠️  Managed files unchanged: {len(before_state['managed_files'])}")
                        
                        return True
                    else:
                        self.log(f"❌ Sync trigger failed: {sync_response.status_code}")
                        return False
                else:
                    self.log("❌ Login failed")
                    return False
            else:
                self.log("❌ Could not get CSRF token")
                return False
                
        except Exception as e:
            self.log(f"❌ Error during sync trigger: {str(e)}")
            return False
    
    def check_service_logs(self):
        """Check if we can see any service execution logs."""
        self.log("Checking for service execution evidence...")
        
        # Look for any recent log files or evidence of service execution
        try:
            import os
            import glob
            
            # Check for any recent log files
            log_patterns = [
                '/home/ubuntu/cc/hedgehog-netbox-plugin/*validation*.json',
                '/home/ubuntu/cc/hedgehog-netbox-plugin/*results*.json',
                '/home/ubuntu/cc/hedgehog-netbox-plugin/*sync*.json'
            ]
            
            recent_files = []
            for pattern in log_patterns:
                files = glob.glob(pattern)
                for file in files:
                    stat = os.stat(file)
                    mtime = stat.st_mtime
                    if time.time() - mtime < 300:  # Files modified in last 5 minutes
                        recent_files.append((file, mtime))
            
            if recent_files:
                self.log("Recent files (last 5 minutes):")
                for file, mtime in sorted(recent_files, key=lambda x: x[1], reverse=True):
                    mod_time = datetime.fromtimestamp(mtime).strftime("%H:%M:%S")
                    self.log(f"  {file} (modified {mod_time})")
            else:
                self.log("No recent validation/sync files found")
            
            return len(recent_files) > 0
            
        except Exception as e:
            self.log(f"❌ Error checking logs: {str(e)}")
            return False
    
    def run_complete_diagnostic(self):
        """Run complete diagnostic workflow."""
        self.log("SYNC DIAGNOSTIC - Understanding FGD Sync Issues")
        self.log("="*60)
        
        results = {}
        
        # Check fabric configuration
        results['fabric_configured'] = self.check_fabric_configuration()
        
        # Check service logs
        results['service_logs'] = self.check_service_logs()
        
        # Trigger sync and monitor
        results['sync_executed'] = self.trigger_sync_and_monitor()
        
        return results
    
    def generate_diagnostic_report(self, results):
        """Generate diagnostic report with findings."""
        self.log("\n" + "="*60)
        self.log("SYNC DIAGNOSTIC REPORT")
        self.log("="*60)
        
        self.log("FINDINGS:")
        for test, result in results.items():
            status = "✅ PASS" if result else "❌ ISSUE"
            self.log(f"  {test}: {status}")
        
        # Provide recommendations
        self.log("\nRECOMMENDATIONS:")
        
        if not results.get('fabric_configured', False):
            self.log("❌ Configure Git repository for fabric before sync can work")
        
        if not results.get('sync_executed', False):
            self.log("❌ Sync execution issues - check service implementation")
        
        if results.get('fabric_configured', False) and results.get('sync_executed', False):
            self.log("✅ Basic workflow functioning - may need more time or different trigger")
        
        # Overall assessment
        issues = sum(1 for v in results.values() if not v)
        if issues == 0:
            self.log("\n🎉 DIAGNOSTIC: All systems appear functional!")
            return True
        else:
            self.log(f"\n⚠️  DIAGNOSTIC: {issues} issues identified that need resolution")
            return False

def main():
    diagnostic = SyncDiagnostic()
    results = diagnostic.run_complete_diagnostic()
    success = diagnostic.generate_diagnostic_report(results)
    return success

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)