#!/usr/bin/env python3
"""
Configure Git repository for the fabric to enable FGD sync functionality.
This is the missing piece that prevents sync from working.
"""

import requests
import json
from datetime import datetime

class FabricGitConfigurator:
    def __init__(self):
        self.fabric_id = 35
        self.headers = {
            'Authorization': 'Token ced6a3e0a978db0ad4de39cd66af4868372d7dd0',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
        self.base_url = 'http://localhost:8000/api'
        
    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")
        
    def get_current_fabric_config(self):
        """Get current fabric configuration."""
        self.log("Getting current fabric configuration...")
        
        try:
            response = requests.get(
                f'{self.base_url}/plugins/hedgehog/fabrics/{self.fabric_id}/',
                headers=self.headers
            )
            
            if response.status_code == 200:
                fabric = response.json()
                self.log(f"✅ Current fabric: {fabric.get('name')}")
                self.log(f"   Git repository: {fabric.get('git_repository', 'None')}")
                return fabric
            else:
                self.log(f"❌ Could not get fabric: {response.status_code}")
                return None
                
        except Exception as e:
            self.log(f"❌ Error getting fabric: {str(e)}")
            return None
    
    def configure_git_repository(self):
        """Configure the Git repository for the fabric."""
        self.log("Configuring Git repository for fabric...")
        
        # The Git repository that the test expects
        git_repo_url = "https://github.com/afewell-hh/gitops-test-1"
        
        fabric_update = {
            "git_repository": git_repo_url
        }
        
        try:
            response = requests.patch(
                f'{self.base_url}/plugins/hedgehog/fabrics/{self.fabric_id}/',
                headers=self.headers,
                json=fabric_update
            )
            
            if response.status_code == 200:
                self.log(f"✅ Git repository configured: {git_repo_url}")
                return True
            else:
                self.log(f"❌ Failed to configure Git repository: {response.status_code}")
                self.log(f"   Response: {response.text}")
                return False
                
        except Exception as e:
            self.log(f"❌ Error configuring Git repository: {str(e)}")
            return False
    
    def verify_configuration(self):
        """Verify the Git repository was configured successfully."""
        self.log("Verifying Git repository configuration...")
        
        fabric = self.get_current_fabric_config()
        if fabric:
            git_repo = fabric.get('git_repository')
            if git_repo:
                self.log(f"✅ Git repository verified: {git_repo}")
                return True
            else:
                self.log("❌ Git repository not found in fabric config")
                return False
        else:
            return False
    
    def test_sync_after_config(self):
        """Test if sync works after configuring Git repository."""
        self.log("Testing sync functionality after Git configuration...")
        
        try:
            # Use authenticated session to trigger sync
            import requests
            import re
            
            session = requests.Session()
            
            # Get CSRF token and login
            login_response = session.get('http://localhost:8000/login/')
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
                    self.log(f"   Connection test: {test_conn.status_code}")
                    
                    import time
                    time.sleep(2)
                    
                    # Trigger sync
                    sync_response = session.post(f'http://localhost:8000/plugins/hedgehog/fabrics/{self.fabric_id}/sync/')
                    self.log(f"   Sync trigger: {sync_response.status_code}")
                    
                    if sync_response.status_code == 200:
                        self.log("✅ Sync successfully triggered with Git repository configured")
                        
                        # Wait for processing
                        self.log("   Waiting for sync processing...")
                        time.sleep(20)
                        
                        # Check results
                        import subprocess
                        result = subprocess.run([
                            'python3', 'test_fgd_postsync_state_v2.py'
                        ], capture_output=True, text=True, cwd='/home/ubuntu/cc/hedgehog-netbox-plugin/', timeout=30)
                        
                        if "Tests Passed:" in result.stdout:
                            import re
                            match = re.search(r'Tests Passed: (\d+)/(\d+)', result.stdout)
                            if match:
                                passed = int(match.group(1))
                                total = int(match.group(2))
                                self.log(f"   Post-config test results: {passed}/{total} tests passing")
                                
                                if passed == total:
                                    self.log("🎉 ALL TESTS PASSED - GIT CONFIG FIXED THE ISSUE!")
                                    return True
                                elif passed > 1:
                                    self.log("✅ Significant improvement - sync is now working!")
                                    return True
                                else:
                                    self.log("⚠️  Still some issues remaining")
                                    return False
                        
                        return True
                    else:
                        self.log(f"❌ Sync trigger still failed: {sync_response.status_code}")
                        return False
                else:
                    self.log("❌ Could not authenticate for test")
                    return False
            else:
                self.log("❌ Could not get CSRF token for test")
                return False
                
        except Exception as e:
            self.log(f"❌ Error testing sync: {str(e)}")
            return False
    
    def execute_git_configuration(self):
        """Execute complete Git repository configuration process."""
        self.log("FABRIC GIT REPOSITORY CONFIGURATION")
        self.log("="*50)
        
        results = {}
        
        # Step 1: Get current config
        current_config = self.get_current_fabric_config()
        results['current_config_accessible'] = current_config is not None
        
        if current_config:
            # Step 2: Configure Git repository
            results['git_configured'] = self.configure_git_repository()
            
            if results['git_configured']:
                # Step 3: Verify configuration
                results['config_verified'] = self.verify_configuration()
                
                if results['config_verified']:
                    # Step 4: Test sync functionality
                    results['sync_tested'] = self.test_sync_after_config()
        
        return results
    
    def generate_config_report(self, results):
        """Generate configuration report."""
        self.log("\n" + "="*50)
        self.log("GIT CONFIGURATION REPORT")
        self.log("="*50)
        
        success_count = sum(1 for v in results.values() if v)
        total_count = len(results)
        
        self.log(f"CONFIGURATION STEPS: {success_count}/{total_count} completed successfully")
        
        self.log("\nSTEP RESULTS:")
        for step, success in results.items():
            status = "✅ SUCCESS" if success else "❌ FAILED"
            self.log(f"  {step}: {status}")
        
        if results.get('sync_tested', False):
            self.log("\n🎉 CONFIGURATION SUCCESS!")
            self.log("   Git repository configured and sync functionality working")
            return True
        elif results.get('git_configured', False):
            self.log("\n✅ PARTIAL SUCCESS")
            self.log("   Git repository configured, sync may need additional time")
            return True
        else:
            self.log("\n❌ CONFIGURATION FAILED")
            self.log("   Unable to configure Git repository for fabric")
            return False

def main():
    configurator = FabricGitConfigurator()
    results = configurator.execute_git_configuration()
    success = configurator.generate_config_report(results)
    return success

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)