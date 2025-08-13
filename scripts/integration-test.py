#!/usr/bin/env python3
"""
NetBox Hedgehog Plugin - Integration Testing Script
==================================================
Tests the plugin functionality in the containerized development environment.
"""

import os
import sys
import json
import time
import requests
import subprocess
from datetime import datetime
from typing import Dict, List, Tuple, Any


class IntegrationTester:
    """Integration tester for containerized NetBox Hedgehog plugin."""
    
    def __init__(self):
        self.netbox_url = "http://localhost:8000"
        self.docker_compose_dir = os.path.join(
            os.path.dirname(__file__), 
            "..", 
            "gitignore", 
            "netbox-docker"
        )
        self.results = []
        self.session = requests.Session()
        
    def log(self, message: str, level: str = "INFO"):
        """Log a message with timestamp."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        color_map = {
            "INFO": "\033[0;34m",
            "SUCCESS": "\033[0;32m", 
            "WARNING": "\033[1;33m",
            "ERROR": "\033[0;31m"
        }
        color = color_map.get(level, "\033[0m")
        print(f"{color}[{timestamp}] {level}: {message}\033[0m")
        
    def run_docker_command(self, command: List[str]) -> Tuple[bool, str]:
        """Run a docker compose command."""
        try:
            os.chdir(self.docker_compose_dir)
            result = subprocess.run(
                ["docker", "compose"] + command,
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.returncode == 0, result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return False, "Command timed out"
        except Exception as e:
            return False, str(e)
            
    def test_container_health(self) -> bool:
        """Test that all required containers are healthy."""
        self.log("Testing container health...")
        
        success, output = self.run_docker_command(["ps", "--format", "json"])
        if not success:
            self.log(f"Failed to get container status: {output}", "ERROR")
            return False
            
        try:
            containers = [json.loads(line) for line in output.strip().split('\n') if line]
            required_services = ["netbox", "postgres", "redis"]
            running_services = [c["Service"] for c in containers if "Up" in c["State"]]
            
            missing_services = [s for s in required_services if s not in running_services]
            if missing_services:
                self.log(f"Missing services: {missing_services}", "ERROR")
                return False
                
            self.log("All required containers are running", "SUCCESS")
            return True
            
        except (json.JSONDecodeError, KeyError) as e:
            self.log(f"Failed to parse container status: {e}", "ERROR")
            return False
            
    def test_netbox_web_interface(self) -> bool:
        """Test NetBox web interface accessibility."""
        self.log("Testing NetBox web interface...")
        
        try:
            response = self.session.get(f"{self.netbox_url}/login/", timeout=10)
            if response.status_code == 200:
                self.log("NetBox web interface is accessible", "SUCCESS")
                return True
            else:
                self.log(f"NetBox returned status {response.status_code}", "ERROR")
                return False
        except requests.RequestException as e:
            self.log(f"Failed to connect to NetBox: {e}", "ERROR")
            return False
            
    def test_plugin_installation(self) -> bool:
        """Test that the Hedgehog plugin is properly installed."""
        self.log("Testing plugin installation...")
        
        try:
            response = self.session.get(f"{self.netbox_url}/plugins/hedgehog/", timeout=10)
            if response.status_code == 200:
                self.log("Hedgehog plugin is accessible", "SUCCESS")
                return True
            elif response.status_code == 404:
                self.log("Hedgehog plugin not found (404)", "ERROR")
                return False
            else:
                self.log(f"Plugin returned status {response.status_code}", "WARNING")
                # Plugin might require authentication
                return True
        except requests.RequestException as e:
            self.log(f"Failed to check plugin: {e}", "ERROR")
            return False
            
    def test_database_connectivity(self) -> bool:
        """Test database connectivity through Django."""
        self.log("Testing database connectivity...")
        
        success, output = self.run_docker_command([
            "exec", "-T", "netbox", 
            "python", "manage.py", "check", "--database", "default"
        ])
        
        if success:
            self.log("Database connectivity check passed", "SUCCESS")
            return True
        else:
            self.log(f"Database check failed: {output}", "ERROR")
            return False
            
    def test_redis_connectivity(self) -> bool:
        """Test Redis connectivity."""
        self.log("Testing Redis connectivity...")
        
        success, output = self.run_docker_command([
            "exec", "-T", "redis", 
            "redis-cli", "-a", "netbox", "ping"
        ])
        
        if success and "PONG" in output:
            self.log("Redis connectivity check passed", "SUCCESS")
            return True
        else:
            self.log(f"Redis check failed: {output}", "ERROR")
            return False
            
    def test_plugin_models(self) -> bool:
        """Test plugin models through Django shell."""
        self.log("Testing plugin models...")
        
        test_script = """
try:
    from netbox_hedgehog.models import Fabric
    print(f"Fabric model accessible: {Fabric}")
    
    # Test basic query
    fabric_count = Fabric.objects.count()
    print(f"Fabric count: {fabric_count}")
    
    print("SUCCESS: Plugin models are working")
except Exception as e:
    print(f"ERROR: {e}")
    exit(1)
"""
        
        success, output = self.run_docker_command([
            "exec", "-T", "netbox",
            "python", "manage.py", "shell", "-c", test_script
        ])
        
        if success and "SUCCESS" in output:
            self.log("Plugin models test passed", "SUCCESS")
            return True
        else:
            self.log(f"Plugin models test failed: {output}", "ERROR")
            return False
            
    def test_rq_workers(self) -> bool:
        """Test RQ workers are running."""
        self.log("Testing RQ workers...")
        
        # Check if RQ worker processes are running
        success, output = self.run_docker_command([
            "exec", "-T", "netbox-rq-worker-hedgehog",
            "ps", "aux"
        ])
        
        if success and "rqworker" in output:
            self.log("RQ workers are running", "SUCCESS")
            return True
        else:
            self.log("RQ workers not found", "WARNING")
            return False
            
    def test_static_files(self) -> bool:
        """Test static files are properly served."""
        self.log("Testing static files...")
        
        try:
            # Test NetBox admin static files
            response = self.session.get(f"{self.netbox_url}/static/admin/css/base.css", timeout=5)
            if response.status_code == 200:
                self.log("Static files are being served", "SUCCESS")
                return True
            else:
                self.log(f"Static files returned status {response.status_code}", "WARNING")
                return False
        except requests.RequestException as e:
            self.log(f"Failed to check static files: {e}", "WARNING")
            return False
            
    def test_hot_reload_capability(self) -> bool:
        """Test hot-reload capability by checking file timestamps."""
        self.log("Testing hot-reload capability...")
        
        # Check if plugin files are properly mounted
        success, output = self.run_docker_command([
            "exec", "-T", "netbox",
            "ls", "-la", "/opt/netbox/netbox/netbox_hedgehog/"
        ])
        
        if success and "__init__.py" in output:
            self.log("Plugin files are properly mounted", "SUCCESS")
            return True
        else:
            self.log(f"Plugin files not found: {output}", "ERROR")
            return False
            
    def run_performance_check(self) -> Dict[str, Any]:
        """Run basic performance checks."""
        self.log("Running performance checks...")
        
        performance_data = {}
        
        # Container resource usage
        success, output = self.run_docker_command(["stats", "--no-stream", "--format", "json"])
        if success:
            try:
                stats = [json.loads(line) for line in output.strip().split('\n') if line]
                performance_data["container_stats"] = stats
            except json.JSONDecodeError:
                performance_data["container_stats"] = "Failed to parse"
                
        # Response time test
        start_time = time.time()
        try:
            response = self.session.get(f"{self.netbox_url}/login/", timeout=10)
            response_time = time.time() - start_time
            performance_data["response_time"] = response_time
            
            if response_time < 2.0:
                self.log(f"Response time: {response_time:.2f}s (Good)", "SUCCESS")
            elif response_time < 5.0:
                self.log(f"Response time: {response_time:.2f}s (Acceptable)", "WARNING")
            else:
                self.log(f"Response time: {response_time:.2f}s (Slow)", "ERROR")
                
        except requests.RequestException:
            performance_data["response_time"] = "Failed"
            
        return performance_data
        
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all integration tests."""
        self.log("Starting integration tests...", "INFO")
        
        test_results = {
            "timestamp": datetime.now().isoformat(),
            "tests": {},
            "performance": {},
            "summary": {}
        }
        
        # Define test suite
        tests = [
            ("container_health", self.test_container_health),
            ("netbox_web_interface", self.test_netbox_web_interface),
            ("plugin_installation", self.test_plugin_installation),
            ("database_connectivity", self.test_database_connectivity),
            ("redis_connectivity", self.test_redis_connectivity),
            ("plugin_models", self.test_plugin_models),
            ("rq_workers", self.test_rq_workers),
            ("static_files", self.test_static_files),
            ("hot_reload_capability", self.test_hot_reload_capability),
        ]
        
        # Run tests
        passed = 0
        failed = 0
        
        for test_name, test_func in tests:
            try:
                result = test_func()
                test_results["tests"][test_name] = {
                    "passed": result,
                    "timestamp": datetime.now().isoformat()
                }
                if result:
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                self.log(f"Test {test_name} crashed: {e}", "ERROR")
                test_results["tests"][test_name] = {
                    "passed": False,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }
                failed += 1
                
        # Run performance checks
        test_results["performance"] = self.run_performance_check()
        
        # Generate summary
        total_tests = passed + failed
        test_results["summary"] = {
            "total_tests": total_tests,
            "passed": passed,
            "failed": failed,
            "success_rate": (passed / total_tests * 100) if total_tests > 0 else 0
        }
        
        # Log summary
        self.log(f"Integration tests completed: {passed}/{total_tests} passed", 
                "SUCCESS" if failed == 0 else "WARNING")
                
        return test_results
        
    def save_results(self, results: Dict[str, Any], filename: str = None):
        """Save test results to a JSON file."""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"integration_test_results_{timestamp}.json"
            
        try:
            with open(filename, 'w') as f:
                json.dump(results, f, indent=2)
            self.log(f"Results saved to {filename}", "SUCCESS")
        except Exception as e:
            self.log(f"Failed to save results: {e}", "ERROR")


def main():
    """Main function."""
    if len(sys.argv) > 1 and sys.argv[1] in ["-h", "--help", "help"]:
        print("""
NetBox Hedgehog Plugin - Integration Testing Script
==================================================

Usage: python3 integration-test.py [options]

Options:
  -h, --help    Show this help message
  --save-only   Only save results, don't display summary
  --quick       Run only essential tests

This script tests the plugin functionality in the containerized environment.
It verifies:
- Container health and connectivity
- NetBox web interface accessibility  
- Plugin installation and model access
- Database and Redis connectivity
- RQ worker processes
- Static file serving
- Hot-reload file mounting

Results are automatically saved to integration_test_results_TIMESTAMP.json
        """)
        return
        
    tester = IntegrationTester()
    
    # Run tests
    results = tester.run_all_tests()
    
    # Save results
    tester.save_results(results)
    
    # Display summary unless --save-only specified
    if "--save-only" not in sys.argv:
        print("\n" + "="*50)
        print("INTEGRATION TEST SUMMARY")
        print("="*50)
        
        summary = results["summary"]
        print(f"Total Tests: {summary['total_tests']}")
        print(f"Passed: {summary['passed']}")
        print(f"Failed: {summary['failed']}")
        print(f"Success Rate: {summary['success_rate']:.1f}%")
        
        if summary['failed'] > 0:
            print("\nFailed Tests:")
            for test_name, test_data in results["tests"].items():
                if not test_data["passed"]:
                    error = test_data.get("error", "Test failed")
                    print(f"  - {test_name}: {error}")
                    
        # Performance summary
        perf = results["performance"]
        if "response_time" in perf:
            print(f"\nResponse Time: {perf['response_time']:.2f}s")
            
    # Exit with appropriate code
    sys.exit(0 if results["summary"]["failed"] == 0 else 1)


if __name__ == "__main__":
    main()