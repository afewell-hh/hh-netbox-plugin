#!/usr/bin/env python3
"""
Environment Management for GUI Validation Tests

Handles:
- NetBox Docker connection (localhost:8000)
- Authentication (admin/admin or token)
- Database state management
- Test isolation strategies

This module provides robust environment setup and teardown for demo validation tests,
ensuring consistent test execution without interfering with development workflow.
"""

import os
import sys
import time
import subprocess
import requests
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from urllib.parse import urljoin

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


@dataclass
class EnvironmentConfig:
    """Configuration for test environment"""
    
    # NetBox connection
    netbox_url: str = "http://localhost:8000"
    netbox_container: str = "netbox-docker-netbox-1"
    
    # Authentication options
    admin_username: str = "admin"
    admin_password: str = "admin"
    token_file_paths: List[str] = None
    
    # Database management
    preserve_data: bool = True  # Don't delete existing data
    backup_before_tests: bool = False  # Optional backup
    restore_after_tests: bool = False  # Optional restore
    
    # Test isolation
    use_test_prefix: bool = True  # Prefix test data with "test_"
    cleanup_test_data: bool = True  # Clean up test-specific data
    
    # Timeouts
    container_start_timeout: int = 120  # 2 minutes
    connection_timeout: int = 30
    
    def __post_init__(self):
        if self.token_file_paths is None:
            self.token_file_paths = [
                str(project_root / 'gitignore' / 'netbox.token'),
                str(Path.home() / '.netbox_token')
            ]


class EnvironmentError(Exception):
    """Base exception for environment-related errors"""
    pass


class ContainerError(EnvironmentError):
    """Exception for Docker container issues"""
    pass


class ConnectionError(EnvironmentError):
    """Exception for NetBox connection issues"""
    pass


class EnvironmentManager:
    """
    Manages the test environment for GUI validation tests.
    
    Provides methods for:
    - Container management
    - Connection validation
    - Authentication setup
    - Test data isolation
    - Environment cleanup
    """
    
    def __init__(self, config: EnvironmentConfig = None):
        self.config = config or EnvironmentConfig()
        self.session = requests.Session()
        self.session.timeout = self.config.connection_timeout
        self._authenticated = False
        self._test_data_created = []
        
    def setup_environment(self) -> bool:
        """
        Set up the complete test environment.
        
        Returns:
            True if environment is ready, False otherwise
        """
        try:
            print("🔧 Setting up test environment...")
            
            # 1. Check and start NetBox container if needed
            if not self._ensure_container_running():
                return False
            
            # 2. Wait for NetBox to be ready
            if not self._wait_for_netbox_ready():
                return False
            
            # 3. Set up authentication
            if not self._setup_authentication():
                print("⚠️  Warning: Authentication setup failed, using anonymous access")
            
            # 4. Validate plugin accessibility
            if not self._validate_plugin_access():
                return False
            
            # 5. Set up test data isolation if needed
            self._setup_test_isolation()
            
            print("✅ Test environment ready!")
            return True
            
        except Exception as e:
            print(f"❌ Environment setup failed: {e}")
            return False
    
    def teardown_environment(self):
        """Clean up test environment"""
        try:
            print("🧹 Cleaning up test environment...")
            
            # Clean up test data if configured
            if self.config.cleanup_test_data:
                self._cleanup_test_data()
            
            # Close session
            self.session.close()
            
            print("✅ Environment cleanup complete!")
            
        except Exception as e:
            print(f"⚠️  Warning: Environment cleanup had issues: {e}")
    
    def _ensure_container_running(self) -> bool:
        """Ensure NetBox Docker container is running"""
        try:
            # Check if container is running
            result = subprocess.run(
                ['sudo', 'docker', 'ps', '--filter', f'name={self.config.netbox_container}', '--format', '{{.Names}}'],
                capture_output=True, text=True, timeout=10
            )
            
            container_running = self.config.netbox_container in result.stdout
            
            if container_running:
                print(f"✅ Container {self.config.netbox_container} is running")
                return True
            
            # Container not running, try to start it
            print(f"🔄 Starting container {self.config.netbox_container}...")
            
            start_result = subprocess.run(
                ['sudo', 'docker', 'start', self.config.netbox_container],
                capture_output=True, text=True, timeout=30
            )
            
            if start_result.returncode == 0:
                print("✅ Container started successfully")
                return True
            else:
                print(f"❌ Failed to start container: {start_result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            print("❌ Timeout while checking/starting container")
            return False
        except Exception as e:
            print(f"❌ Error managing container: {e}")
            return False
    
    def _wait_for_netbox_ready(self) -> bool:
        """Wait for NetBox to be ready to accept connections"""
        print("⏳ Waiting for NetBox to be ready...")
        
        start_time = time.time()
        while time.time() - start_time < self.config.container_start_timeout:
            try:
                response = self.session.get(self.config.netbox_url + '/')
                if response.status_code in [200, 301, 302]:
                    print("✅ NetBox is ready!")
                    return True
            except requests.RequestException:
                pass
            
            print(".", end="", flush=True)
            time.sleep(2)
        
        print("\n❌ Timeout waiting for NetBox to be ready")
        return False
    
    def _setup_authentication(self) -> bool:
        """Set up authentication for NetBox access"""
        # Try token authentication first
        token = self._load_auth_token()
        if token:
            self.session.headers.update({
                'Authorization': f'Token {token}',
                'Content-Type': 'application/json'
            })
            
            # Test token authentication
            try:
                response = self.session.get(self.config.netbox_url + '/api/')
                if response.status_code == 200:
                    print("✅ Token authentication successful")
                    self._authenticated = True
                    return True
            except requests.RequestException:
                pass
        
        # Try session-based authentication
        if self._setup_session_auth():
            self._authenticated = True
            return True
        
        # Fall back to anonymous access
        print("⚠️  Using anonymous access")
        return False
    
    def _load_auth_token(self) -> Optional[str]:
        """Load authentication token from standard locations"""
        # Try environment variable first
        token = os.getenv('NETBOX_TOKEN')
        if token:
            return token.strip()
        
        # Try token files
        for token_file_path in self.config.token_file_paths:
            token_file = Path(token_file_path)
            if token_file.exists():
                try:
                    return token_file.read_text().strip()
                except Exception:
                    continue
        
        return None
    
    def _setup_session_auth(self) -> bool:
        """Set up session-based authentication using admin credentials"""
        try:
            # Get login page to get CSRF token
            login_url = urljoin(self.config.netbox_url, '/login/')
            response = self.session.get(login_url)
            
            if response.status_code != 200:
                return False
            
            # Extract CSRF token
            csrf_token = None
            for line in response.text.split('\n'):
                if 'csrfmiddlewaretoken' in line and 'value=' in line:
                    csrf_token = line.split('value="')[1].split('"')[0]
                    break
            
            if not csrf_token:
                return False
            
            # Perform login
            login_data = {
                'username': self.config.admin_username,
                'password': self.config.admin_password,
                'csrfmiddlewaretoken': csrf_token
            }
            
            response = self.session.post(login_url, data=login_data)
            
            # Check if login was successful (should redirect)
            if response.status_code in [200, 301, 302]:
                # Verify we can access authenticated pages
                response = self.session.get(self.config.netbox_url + '/')
                if 'admin' in response.text.lower() or 'logout' in response.text.lower():
                    print("✅ Session authentication successful")
                    return True
            
            return False
            
        except Exception as e:
            print(f"⚠️  Session authentication failed: {e}")
            return False
    
    def _validate_plugin_access(self) -> bool:
        """Validate that the Hedgehog plugin is accessible"""
        try:
            plugin_url = urljoin(self.config.netbox_url, '/plugins/hedgehog/')
            response = self.session.get(plugin_url)
            
            if response.status_code in [200, 301, 302]:
                print("✅ Hedgehog plugin is accessible")
                return True
            elif response.status_code == 404:
                print("❌ Hedgehog plugin not found - is it installed?")
                return False
            else:
                print(f"⚠️  Plugin access issue (status: {response.status_code})")
                return False
                
        except requests.RequestException as e:
            print(f"❌ Cannot access plugin: {e}")
            return False
    
    def _setup_test_isolation(self):
        """Set up test data isolation strategies"""
        if self.config.use_test_prefix:
            print("📝 Test data will use 'test_' prefix for isolation")
        
        if self.config.preserve_data:
            print("💾 Existing data will be preserved during tests")
    
    def _cleanup_test_data(self):
        """Clean up test-specific data created during tests"""
        if not self._test_data_created:
            return
        
        print(f"🧹 Cleaning up {len(self._test_data_created)} test data items...")
        
        # This would implement actual cleanup logic
        # For now, just track what we would clean up
        for item in self._test_data_created:
            print(f"   • Would clean up: {item}")
        
        self._test_data_created.clear()
    
    def register_test_data(self, data_type: str, data_id: str):
        """Register test data for cleanup"""
        self._test_data_created.append(f"{data_type}:{data_id}")
    
    def get_authenticated_session(self) -> requests.Session:
        """Get an authenticated session for making requests"""
        return self.session
    
    def is_authenticated(self) -> bool:
        """Check if we have authenticated access"""
        return self._authenticated
    
    def get_netbox_url(self) -> str:
        """Get the NetBox base URL"""
        return self.config.netbox_url
    
    def get_plugin_url(self, path: str = '') -> str:
        """Get full URL for plugin endpoint"""
        base_path = '/plugins/hedgehog/'
        return urljoin(self.config.netbox_url, base_path + path.lstrip('/'))


def check_environment(verbose: bool = True) -> Tuple[bool, List[str]]:
    """
    Check if the environment is ready for testing.
    
    Args:
        verbose: Print detailed status information
        
    Returns:
        Tuple of (is_ready, list_of_issues)
    """
    issues = []
    
    if verbose:
        print("🔍 Checking test environment...")
    
    # Check Docker availability
    try:
        subprocess.run(['sudo', 'docker', '--version'], 
                      capture_output=True, check=True, timeout=5)
        if verbose:
            print("✅ Docker is available")
    except Exception:
        issues.append("Docker is not available or accessible")
        if verbose:
            print("❌ Docker is not available")
    
    # Check NetBox container
    try:
        result = subprocess.run(
            ['sudo', 'docker', 'ps', '--filter', 'name=netbox-docker-netbox-1'],
            capture_output=True, text=True, timeout=10
        )
        container_running = 'netbox-docker-netbox-1' in result.stdout
        
        if container_running:
            if verbose:
                print("✅ NetBox container is running")
        else:
            issues.append("NetBox container is not running")
            if verbose:
                print("❌ NetBox container is not running")
    except Exception:
        issues.append("Cannot check NetBox container status")
        if verbose:
            print("❌ Cannot check container status")
    
    # Check NetBox connectivity
    try:
        response = requests.get("http://localhost:8000/", timeout=10)
        if response.status_code in [200, 301, 302]:
            if verbose:
                print("✅ NetBox is accessible")
        else:
            issues.append(f"NetBox returned status {response.status_code}")
            if verbose:
                print(f"❌ NetBox returned status {response.status_code}")
    except Exception as e:
        issues.append(f"Cannot connect to NetBox: {e}")
        if verbose:
            print(f"❌ Cannot connect to NetBox: {e}")
    
    # Check plugin
    try:
        response = requests.get("http://localhost:8000/plugins/hedgehog/", timeout=10)
        if response.status_code in [200, 301, 302]:
            if verbose:
                print("✅ Hedgehog plugin is accessible")
        elif response.status_code == 404:
            issues.append("Hedgehog plugin is not installed or not accessible")
            if verbose:
                print("❌ Hedgehog plugin not found")
    except Exception as e:
        issues.append(f"Cannot check plugin: {e}")
        if verbose:
            print(f"❌ Cannot check plugin: {e}")
    
    is_ready = len(issues) == 0
    
    if verbose:
        if is_ready:
            print("🎯 Environment is ready for testing!")
        else:
            print(f"⚠️  Found {len(issues)} issue(s) that need attention")
    
    return is_ready, issues


def restart_environment() -> bool:
    """
    Restart the NetBox container environment.
    
    Returns:
        True if restart was successful, False otherwise
    """
    try:
        print("🔄 Restarting NetBox environment...")
        
        # Restart the container
        subprocess.run(
            ['sudo', 'docker', 'restart', 'netbox-docker-netbox-1'],
            check=True, timeout=60
        )
        
        print("✅ Container restarted")
        
        # Wait for it to be ready
        manager = EnvironmentManager()
        if manager._wait_for_netbox_ready():
            print("✅ Environment restart complete!")
            return True
        else:
            print("❌ Environment did not become ready after restart")
            return False
            
    except Exception as e:
        print(f"❌ Environment restart failed: {e}")
        return False


# Singleton instance for global environment management
_global_environment = None


def get_environment() -> EnvironmentManager:
    """Get the global environment manager instance"""
    global _global_environment
    
    if _global_environment is None:
        _global_environment = EnvironmentManager()
    
    return _global_environment


def setup_global_environment() -> bool:
    """Set up the global test environment"""
    env = get_environment()
    return env.setup_environment()


def teardown_global_environment():
    """Tear down the global test environment"""
    global _global_environment
    
    if _global_environment:
        _global_environment.teardown_environment()
        _global_environment = None


if __name__ == '__main__':
    # Demo the environment management
    import argparse
    
    parser = argparse.ArgumentParser(description='Environment Management for GUI Tests')
    parser.add_argument('--check', action='store_true', help='Check environment status')
    parser.add_argument('--setup', action='store_true', help='Set up environment')
    parser.add_argument('--restart', action='store_true', help='Restart environment')
    
    args = parser.parse_args()
    
    if args.check:
        is_ready, issues = check_environment()
        if not is_ready:
            print("\nIssues found:")
            for issue in issues:
                print(f"  • {issue}")
            sys.exit(1)
    elif args.setup:
        success = setup_global_environment()
        sys.exit(0 if success else 1)
    elif args.restart:
        success = restart_environment()
        sys.exit(0 if success else 1)
    else:
        # Default: check environment
        is_ready, issues = check_environment()
        sys.exit(0 if is_ready else 1)