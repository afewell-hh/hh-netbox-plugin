#!/usr/bin/env python3
"""
Mandatory Failing Tests for HNP Fabric Sync

These tests MUST PASS before any agent can claim fabric sync functionality is working.
All tests are designed to FAIL with the current broken configuration and PASS only
when the implementation is actually complete.

Run with: python3 tests/mandatory_failing_tests.py
"""

import os
import sys
import tempfile
import yaml
import subprocess
import requests
from pathlib import Path
from datetime import datetime

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

class TestFailureException(Exception):
    """Raised when a test fails"""
    pass

class MandatoryFabricSyncTests:
    """
    Comprehensive test suite that prevents false completion claims.
    These tests verify actual functionality, not just code existence.
    """
    
    def __init__(self):
        self.test_results = []
        self.failed_tests = []
        
    def run_django_command(self, command):
        """Execute Django management command in NetBox container"""
        cmd = [
            'sudo', 'docker', 'exec', 'netbox-docker-netbox-1',
            'python3', 'manage.py', 'shell', '-c', command
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                raise TestFailureException(f"Django command failed: {result.stderr}")
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            raise TestFailureException("Django command timed out")
        except Exception as e:
            raise TestFailureException(f"Failed to execute Django command: {str(e)}")
    
    def test_fabric_exists(self):
        """Test 1: Verify fabric record exists"""
        print("Test 1: Checking fabric exists...")
        
        command = """
from netbox_hedgehog.models.fabric import HedgehogFabric
try:
    fabric = HedgehogFabric.objects.get(id=19)
    print(f"FABRIC_EXISTS:{fabric.name}")
except HedgehogFabric.DoesNotExist:
    print("FABRIC_NOT_FOUND")
"""
        
        output = self.run_django_command(command)
        if "FABRIC_EXISTS:HCKC" not in output:
            raise TestFailureException(f"Fabric not found or wrong name: {output}")
        
        print("✓ Fabric exists")
    
    def test_git_repository_exists(self):
        """Test 2: Verify GitRepository record exists"""
        print("Test 2: Checking GitRepository exists...")
        
        command = """
from netbox_hedgehog.models.git_repository import GitRepository
try:
    repo = GitRepository.objects.get(id=6)
    print(f"REPO_EXISTS:{repo.url}")
except GitRepository.DoesNotExist:
    print("REPO_NOT_FOUND")
"""
        
        output = self.run_django_command(command)
        if "REPO_EXISTS:https://github.com/afewell-hh/gitops-test-1" not in output:
            raise TestFailureException(f"GitRepository not found or wrong URL: {output}")
        
        print("✓ GitRepository exists")
    
    def test_fabric_git_repository_link(self):
        """Test 3: CRITICAL - Verify fabric links to GitRepository (CURRENTLY FAILS)"""
        print("Test 3: Checking fabric->GitRepository link...")
        
        command = """
from netbox_hedgehog.models.fabric import HedgehogFabric
fabric = HedgehogFabric.objects.get(id=19)
if fabric.git_repository is None:
    print("LINK_MISSING")
elif fabric.git_repository.id == 6:
    print("LINK_CORRECT")
else:
    print(f"LINK_WRONG:{fabric.git_repository.id}")
"""
        
        output = self.run_django_command(command)
        
        # This test SHOULD FAIL with current broken configuration
        if "LINK_MISSING" in output:
            raise TestFailureException(
                "EXPECTED FAILURE: Fabric.git_repository is None. "
                "Agent MUST fix this by setting fabric.git_repository = GitRepository(id=6)"
            )
        elif "LINK_WRONG" in output:
            raise TestFailureException(
                f"EXPECTED FAILURE: Fabric linked to wrong GitRepository. "
                f"Agent MUST link to GitRepository ID 6. Output: {output}"
            )
        elif "LINK_CORRECT" not in output:
            raise TestFailureException(f"Unexpected output: {output}")
        
        print("✓ Fabric correctly linked to GitRepository")
    
    def test_fabric_gitops_directory(self):
        """Test 4: CRITICAL - Verify fabric has correct GitOps directory (CURRENTLY FAILS)"""
        print("Test 4: Checking GitOps directory path...")
        
        command = """
from netbox_hedgehog.models.fabric import HedgehogFabric
fabric = HedgehogFabric.objects.get(id=19)
print(f"GITOPS_DIR:{fabric.gitops_directory}")
"""
        
        output = self.run_django_command(command)
        
        # This test SHOULD FAIL with current broken configuration
        if "GITOPS_DIR:/" in output:
            raise TestFailureException(
                "EXPECTED FAILURE: GitOps directory is root '/'. "
                "Agent MUST fix this by setting gitops_directory = 'gitops/hedgehog/fabric-1/'"
            )
        elif "GITOPS_DIR:gitops/hedgehog/fabric-1/" not in output:
            raise TestFailureException(
                f"EXPECTED FAILURE: Wrong GitOps directory path. "
                f"Expected 'gitops/hedgehog/fabric-1/', got: {output}"
            )
        
        print("✓ GitOps directory path correct")
    
    def test_git_repository_authentication(self):
        """Test 5: Verify GitRepository authentication works"""
        print("Test 5: Testing Git repository authentication...")
        
        command = """
from netbox_hedgehog.models.git_repository import GitRepository
repo = GitRepository.objects.get(id=6)
has_creds = bool(repo.encrypted_credentials)
print(f"HAS_CREDENTIALS:{has_creds}")

if has_creds:
    result = repo.test_connection()
    print(f"CONNECTION_SUCCESS:{result['success']}")
    if result['success']:
        print(f"AUTHENTICATED:{result['authenticated']}")
    else:
        print(f"CONNECTION_ERROR:{result['error']}")
else:
    print("NO_CREDENTIALS")
"""
        
        output = self.run_django_command(command)
        
        if "HAS_CREDENTIALS:False" in output or "NO_CREDENTIALS" in output:
            raise TestFailureException(
                "EXPECTED FAILURE: No encrypted credentials found. "
                "Agent MUST set up repository authentication."
            )
        
        if "CONNECTION_SUCCESS:False" in output:
            raise TestFailureException(
                "EXPECTED FAILURE: Git connection test failed. "
                "Agent MUST fix repository authentication."
            )
        
        if "CONNECTION_SUCCESS:True" not in output or "AUTHENTICATED:True" not in output:
            raise TestFailureException(f"Authentication test failed: {output}")
        
        print("✓ Git repository authentication works")
    
    def test_repository_content_accessible(self):
        """Test 6: Verify repository content is accessible"""
        print("Test 6: Testing repository content access...")
        
        command = """
from netbox_hedgehog.models.git_repository import GitRepository
import tempfile
import yaml
from pathlib import Path

repo = GitRepository.objects.get(id=6)
with tempfile.TemporaryDirectory() as temp_dir:
    result = repo.clone_repository(temp_dir)
    if not result['success']:
        print(f"CLONE_FAILED:{result['error']}")
    else:
        gitops_path = Path(temp_dir) / 'gitops' / 'hedgehog' / 'fabric-1'
        if not gitops_path.exists():
            print("GITOPS_PATH_NOT_FOUND")
        else:
            yaml_files = list(gitops_path.glob('*.yaml'))
            print(f"YAML_FILES_FOUND:{len(yaml_files)}")
            
            crd_count = 0
            for yaml_file in yaml_files:
                try:
                    with open(yaml_file, 'r') as f:
                        docs = list(yaml.safe_load_all(f))
                        for doc in docs:
                            if doc and 'kind' in doc and 'metadata' in doc:
                                kind = doc['kind']
                                if kind in ['VPC', 'Connection', 'Switch', 'Server']:
                                    crd_count += 1
                except Exception as e:
                    print(f"YAML_ERROR:{yaml_file.name}:{e}")
            
            print(f"VALID_CRDS_FOUND:{crd_count}")
"""
        
        output = self.run_django_command(command)
        
        if "CLONE_FAILED:" in output:
            raise TestFailureException(f"Repository clone failed: {output}")
        
        if "GITOPS_PATH_NOT_FOUND" in output:
            raise TestFailureException(
                "GitOps path 'gitops/hedgehog/fabric-1' not found in repository"
            )
        
        if "YAML_FILES_FOUND:0" in output:
            raise TestFailureException("No YAML files found in GitOps directory")
        
        if "VALID_CRDS_FOUND:0" in output:
            raise TestFailureException("No valid Hedgehog CRDs found in YAML files")
        
        print("✓ Repository content accessible")
    
    def test_sync_creates_crd_records(self):
        """Test 7: CRITICAL - Verify sync actually creates CRD records (CURRENTLY FAILS)"""
        print("Test 7: Testing sync creates CRD records...")
        
        command = """
from netbox_hedgehog.models.fabric import HedgehogFabric
from netbox_hedgehog.models.vpc_api import VPC
from netbox_hedgehog.models.wiring_api import Connection, Switch

fabric = HedgehogFabric.objects.get(id=19)

# Check pre-sync state
vpc_before = VPC.objects.filter(fabric=fabric).count()
conn_before = Connection.objects.filter(fabric=fabric).count() 
switch_before = Switch.objects.filter(fabric=fabric).count()
print(f"PRE_SYNC_VPCS:{vpc_before}")
print(f"PRE_SYNC_CONNECTIONS:{conn_before}")
print(f"PRE_SYNC_SWITCHES:{switch_before}")

# Attempt sync
try:
    result = fabric.trigger_gitops_sync()
    print(f"SYNC_SUCCESS:{result['success']}")
    if not result['success']:
        print(f"SYNC_ERROR:{result['error']}")
    else:
        print(f"SYNC_MESSAGE:{result['message']}")
        
        # Check post-sync state
        vpc_after = VPC.objects.filter(fabric=fabric).count()
        conn_after = Connection.objects.filter(fabric=fabric).count()
        switch_after = Switch.objects.filter(fabric=fabric).count()
        
        print(f"POST_SYNC_VPCS:{vpc_after}")
        print(f"POST_SYNC_CONNECTIONS:{conn_after}")
        print(f"POST_SYNC_SWITCHES:{switch_after}")
        
        total_crds = vpc_after + conn_after + switch_after
        print(f"TOTAL_CRDS_CREATED:{total_crds}")
        
        # Check fabric cached counts
        fabric.refresh_from_db()
        print(f"CACHED_CRD_COUNT:{fabric.cached_crd_count}")
        
except Exception as e:
    print(f"SYNC_EXCEPTION:{str(e)}")
"""
        
        output = self.run_django_command(command)
        
        if "SYNC_SUCCESS:False" in output:
            raise TestFailureException(
                f"EXPECTED FAILURE: Sync operation failed. "
                f"Agent MUST fix sync functionality. Output: {output}"
            )
        
        if "SYNC_EXCEPTION:" in output:
            raise TestFailureException(
                f"EXPECTED FAILURE: Sync threw exception. "
                f"Agent MUST fix sync implementation. Output: {output}"
            )
        
        if "TOTAL_CRDS_CREATED:0" in output:
            raise TestFailureException(
                "EXPECTED FAILURE: No CRDs created after sync. "
                "Agent MUST fix sync to actually create database records."
            )
        
        if "CACHED_CRD_COUNT:0" in output:
            raise TestFailureException(
                "EXPECTED FAILURE: Fabric cached count not updated. "
                "Agent MUST fix sync to update fabric counts."
            )
        
        print("✓ Sync creates CRD records")
    
    def test_gui_fabric_page_loads(self):
        """Test 8: Verify fabric detail page loads"""
        print("Test 8: Testing fabric detail page...")
        
        try:
            # Test if we can reach the fabric page
            response = requests.get('http://localhost:8000/plugins/hedgehog/fabrics/19/', timeout=10)
            
            if response.status_code == 404:
                raise TestFailureException("Fabric detail page not found (404)")
            elif response.status_code == 500:
                raise TestFailureException("Fabric detail page has server error (500)")
            elif response.status_code == 403:
                raise TestFailureException("Fabric detail page access forbidden (403)")
            elif response.status_code != 200:
                raise TestFailureException(f"Fabric detail page error: HTTP {response.status_code}")
            
            if "HCKC" not in response.text:
                raise TestFailureException("Fabric name 'HCKC' not found on page")
            
            print("✓ Fabric detail page loads")
            
        except requests.exceptions.ConnectionError:
            raise TestFailureException(
                "Cannot connect to NetBox at localhost:8000. "
                "Ensure NetBox container is running and accessible."
            )
        except requests.exceptions.Timeout:
            raise TestFailureException("Fabric detail page request timed out")
    
    def test_sync_button_exists(self):
        """Test 9: Verify sync button exists on fabric page"""  
        print("Test 9: Testing sync button exists...")
        
        try:
            response = requests.get('http://localhost:8000/plugins/hedgehog/fabrics/19/', timeout=10)
            
            if response.status_code != 200:
                raise TestFailureException(f"Cannot access fabric page: HTTP {response.status_code}")
            
            # Look for sync button indicators
            page_text = response.text.lower()
            if 'sync now' not in page_text and 'sync' not in page_text:
                raise TestFailureException("No sync button found on fabric detail page")
            
            print("✓ Sync button exists")
            
        except requests.exceptions.RequestException as e:
            raise TestFailureException(f"Failed to check sync button: {str(e)}")
    
    def test_fabric_counts_display(self):
        """Test 10: Verify fabric displays CRD counts correctly"""
        print("Test 10: Testing fabric CRD count display...")
        
        # First get the actual database counts
        command = """
from netbox_hedgehog.models.fabric import HedgehogFabric
from netbox_hedgehog.models.vpc_api import VPC
from netbox_hedgehog.models.wiring_api import Connection, Switch

fabric = HedgehogFabric.objects.get(id=19)
vpc_count = VPC.objects.filter(fabric=fabric).count()
conn_count = Connection.objects.filter(fabric=fabric).count()
switch_count = Switch.objects.filter(fabric=fabric).count()

print(f"DB_VPC_COUNT:{vpc_count}")
print(f"DB_CONNECTION_COUNT:{conn_count}")
print(f"DB_SWITCH_COUNT:{switch_count}")
print(f"CACHED_COUNT:{fabric.cached_crd_count}")
"""
        
        db_output = self.run_django_command(command)
        
        # Then check if the GUI shows these counts
        try:
            response = requests.get('http://localhost:8000/plugins/hedgehog/fabrics/19/', timeout=10)
            
            if response.status_code != 200:
                raise TestFailureException(f"Cannot access fabric page: HTTP {response.status_code}")
            
            # If there are CRDs in the database, they should be displayed
            if "DB_VPC_COUNT:0" not in db_output and "DB_CONNECTION_COUNT:0" not in db_output:
                # There are CRDs, so they should be visible on the page
                if "Total CRDs: 0" in response.text:
                    raise TestFailureException("GUI shows 0 CRDs but database has CRDs")
            
            print("✓ Fabric counts display correctly")
            
        except requests.exceptions.RequestException as e:
            raise TestFailureException(f"Failed to check fabric counts: {str(e)}")
    
    def run_all_tests(self):
        """Run all mandatory tests and report results"""
        print("=" * 60)
        print("RUNNING MANDATORY FABRIC SYNC TESTS")
        print("=" * 60)
        print()
        
        tests = [
            self.test_fabric_exists,
            self.test_git_repository_exists,
            self.test_fabric_git_repository_link,
            self.test_fabric_gitops_directory,
            self.test_git_repository_authentication,
            self.test_repository_content_accessible,
            self.test_sync_creates_crd_records,
            self.test_gui_fabric_page_loads,
            self.test_sync_button_exists,
            self.test_fabric_counts_display
        ]
        
        passed = 0
        failed = 0
        
        for test_func in tests:
            try:
                test_func()
                passed += 1
                self.test_results.append(f"✓ {test_func.__name__}: PASSED")
            except TestFailureException as e:
                failed += 1
                self.failed_tests.append(test_func.__name__)
                self.test_results.append(f"✗ {test_func.__name__}: FAILED - {str(e)}")
                print(f"✗ FAILED: {str(e)}")
            except Exception as e:
                failed += 1
                self.failed_tests.append(test_func.__name__)
                self.test_results.append(f"✗ {test_func.__name__}: ERROR - {str(e)}")
                print(f"✗ ERROR: {str(e)}")
            
            print()
        
        print("=" * 60)
        print("TEST RESULTS SUMMARY")
        print("=" * 60)
        print(f"PASSED: {passed}")
        print(f"FAILED: {failed}")
        print(f"TOTAL:  {passed + failed}")
        print()
        
        if failed > 0:
            print("FAILED TESTS:")
            for test_name in self.failed_tests:
                print(f"  - {test_name}")
            print()
            print("⚠️  FABRIC SYNC IS NOT WORKING")
            print("   Agents MUST fix all failing tests before claiming completion")
            print("   See AGENT_VALIDATION_PROTOCOL.md for required evidence")
        else:
            print("🎉 ALL TESTS PASSED")
            print("   Fabric sync functionality is working correctly")
            print("   Agents may now provide evidence of completion")
        
        print()
        
        # Save detailed test results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = f"mandatory_test_results_{timestamp}.json"
        
        import json
        with open(results_file, 'w') as f:
            json.dump({
                'timestamp': timestamp,
                'passed': passed,
                'failed': failed,
                'failed_tests': self.failed_tests,
                'detailed_results': self.test_results
            }, f, indent=2)
        
        print(f"Detailed results saved to: {results_file}")
        
        return failed == 0

def main():
    """Main test runner"""
    print("HNP Fabric Sync Mandatory Test Suite")
    print("Version 1.0 - Designed to prevent false completion claims")
    print()
    
    tester = MandatoryFabricSyncTests()
    success = tester.run_all_tests()
    
    if not success:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()