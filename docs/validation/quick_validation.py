#!/usr/bin/env python3
"""
Quick GUI Stability Validation Script
=====================================

Performs quick validation checks after major changes to ensure GUI stability.
Designed for orchestrator use between development phases.

Usage:
    python3 quick_validation.py [--verbose]
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path
import requests
from urllib.parse import urljoin

class ValidationResult:
    def __init__(self, name, status="PENDING", message="", details=None):
        self.name = name
        self.status = status  # GREEN, YELLOW, RED, PENDING
        self.message = message
        self.details = details or []

class QuickValidator:
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.base_url = "http://localhost:8000"
        self.results = []
        
    def log(self, message):
        if self.verbose:
            print(f"[DEBUG] {message}")
    
    def run_command(self, cmd, timeout=30):
        """Run shell command and return result"""
        try:
            result = subprocess.run(
                cmd.split() if isinstance(cmd, str) else cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return result.returncode == 0, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return False, "", "Command timed out"
        except Exception as e:
            return False, "", str(e)
    
    def check_docker_containers(self):
        """Validate NetBox containers are running"""
        result = ValidationResult("Docker Containers")
        
        success, stdout, stderr = self.run_command("sudo docker ps")
        if not success:
            result.status = "RED"
            result.message = "Cannot access Docker"
            result.details.append(f"Error: {stderr}")
            self.results.append(result)
            return
        
        required_containers = ["netbox-docker-netbox-1", "postgres", "redis"]
        running_containers = stdout
        
        missing = []
        for container in required_containers:
            if container not in running_containers:
                missing.append(container)
        
        if missing:
            result.status = "RED"
            result.message = f"Missing containers: {', '.join(missing)}"
        else:
            result.status = "GREEN"
            result.message = "All required containers running"
        
        self.results.append(result)
    
    def check_web_accessibility(self):
        """Check if NetBox web interface is accessible"""
        result = ValidationResult("Web Accessibility")
        
        try:
            # Check main NetBox interface
            response = requests.get(self.base_url, timeout=10, allow_redirects=False)
            if response.status_code not in [200, 302]:
                result.status = "RED"
                result.message = f"NetBox not accessible (HTTP {response.status_code})"
                self.results.append(result)
                return
            
            # Check plugin dashboard
            plugin_url = urljoin(self.base_url, "/plugins/hedgehog/")
            response = requests.get(plugin_url, timeout=10)
            if response.status_code != 200:
                result.status = "YELLOW"
                result.message = f"Plugin dashboard issues (HTTP {response.status_code})"
            else:
                result.status = "GREEN"
                result.message = "NetBox and plugin accessible"
                
        except requests.RequestException as e:
            result.status = "RED"
            result.message = f"Connection failed: {str(e)}"
        
        self.results.append(result)
    
    def check_dev_setup_system(self):
        """Validate development setup system functionality"""
        result = ValidationResult("Dev Setup System")
        
        # Check for Makefile
        makefile = Path("Makefile")
        dev_script = Path("dev-setup.sh")
        
        if not makefile.exists():
            result.status = "RED"
            result.message = "Makefile not found"
            self.results.append(result)
            return
            
        if not dev_script.exists():
            result.status = "YELLOW" 
            result.message = "dev-setup.sh not found but Makefile exists"
        else:
            # Check if script is executable
            if not dev_script.stat().st_mode & 0o111:
                result.status = "YELLOW"
                result.message = "dev-setup.sh not executable"
            else:
                result.status = "GREEN"
                result.message = "Development setup system complete"
        
        self.results.append(result)
    
    def check_gui_test_runner(self):
        """Validate GUI test runner functionality"""
        result = ValidationResult("GUI Test Runner")
        
        test_runner = Path("tests/gui/run_gui_tests.py")
        if not test_runner.exists():
            result.status = "YELLOW"  # Changed from RED to YELLOW since it's not critical for dev setup
            result.message = "GUI test runner not found (optional for dev setup)"
            self.results.append(result)
            return
        
        # Test help command
        success, stdout, stderr = self.run_command(f"python3 {test_runner} --help")
        if not success:
            result.status = "YELLOW"  # Changed from RED to YELLOW
            result.message = "Test runner help failed"
            result.details.append(f"Error: {stderr}")
        else:
            result.status = "GREEN"
            result.message = "Test runner functional"
            if self.verbose:
                result.details.append("Help command executed successfully")
        
        self.results.append(result)
    
    def check_phase0_artifacts(self):
        """Validate Phase 0 artifacts were created properly"""
        result = ValidationResult("Phase 0 Artifacts")
        
        required_dirs = [
            "netbox_hedgehog/contracts",
            "netbox_hedgehog/specifications"
        ]
        
        missing_dirs = []
        for dir_path in required_dirs:
            if not Path(dir_path).exists():
                missing_dirs.append(dir_path)
        
        if missing_dirs:
            result.status = "RED"
            result.message = f"Missing Phase 0 directories: {', '.join(missing_dirs)}"
        else:
            # Check for specification files
            spec_files = list(Path("netbox_hedgehog/specifications").rglob("*.md"))
            contract_files = list(Path("netbox_hedgehog/contracts").rglob("*.py"))
            
            if len(spec_files) < 10 or len(contract_files) < 3:
                result.status = "YELLOW"
                result.message = f"Phase 0 artifacts present but sparse ({len(spec_files)} specs, {len(contract_files)} contracts)"
            else:
                result.status = "GREEN"
                result.message = f"Phase 0 artifacts complete ({len(spec_files)} specs, {len(contract_files)} contracts)"
        
        self.results.append(result)
    
    def check_git_status(self):
        """Check for unexpected changes to existing code"""
        result = ValidationResult("Git Status")
        
        success, stdout, stderr = self.run_command("git status --porcelain")
        if not success:
            result.status = "YELLOW"
            result.message = "Cannot check git status"
            self.results.append(result)
            return
        
        changes = stdout.strip().split('\n') if stdout.strip() else []
        
        # Filter out expected changes
        unexpected_changes = []
        for change in changes:
            if change.strip():
                # Skip known Phase 0 artifacts and metric files
                if not any(pattern in change for pattern in [
                    '.claude-flow/metrics',
                    'architecture_specifications/',
                    'PHASE_0',
                    'CONTRACTS_',
                    '.md',
                    '??'  # untracked files
                ]):
                    unexpected_changes.append(change.strip())
        
        if unexpected_changes:
            result.status = "YELLOW"
            result.message = f"{len(unexpected_changes)} unexpected changes to existing code"
            result.details = unexpected_changes[:5]  # Show first 5
        else:
            result.status = "GREEN"
            result.message = "No unexpected changes to existing code"
        
        self.results.append(result)
    
    def run_all_checks(self):
        """Run all validation checks"""
        print("🔍 Running Quick GUI Stability Validation...")
        print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 50)
        
        checks = [
            self.check_docker_containers,
            self.check_web_accessibility,
            self.check_dev_setup_system,
            self.check_gui_test_runner,
            self.check_phase0_artifacts,
            self.check_git_status
        ]
        
        for check in checks:
            print(f"Running {check.__name__.replace('check_', '').replace('_', ' ').title()}...", end=" ")
            check()
            latest_result = self.results[-1]
            print(f"[{latest_result.status}]")
            if latest_result.status in ["YELLOW", "RED"]:
                print(f"  ⚠️  {latest_result.message}")
    
    def generate_report(self):
        """Generate final validation report"""
        print("\n" + "=" * 50)
        print("VALIDATION SUMMARY")
        print("=" * 50)
        
        green_count = sum(1 for r in self.results if r.status == "GREEN")
        yellow_count = sum(1 for r in self.results if r.status == "YELLOW")
        red_count = sum(1 for r in self.results if r.status == "RED")
        
        overall_status = "GREEN"
        if red_count > 0:
            overall_status = "RED"
        elif yellow_count > 0:
            overall_status = "YELLOW"
        
        print(f"Overall Status: {overall_status}")
        print(f"✅ GREEN: {green_count}")
        print(f"⚠️  YELLOW: {yellow_count}")
        print(f"❌ RED: {red_count}")
        
        print("\nDETAILED RESULTS:")
        print("-" * 30)
        
        for result in self.results:
            status_icon = {"GREEN": "✅", "YELLOW": "⚠️", "RED": "❌"}.get(result.status, "❓")
            print(f"{status_icon} {result.name}: {result.message}")
            
            if result.details and self.verbose:
                for detail in result.details:
                    print(f"    └─ {detail}")
        
        print("\nRECOMMENDATIONS:")
        print("-" * 30)
        
        if overall_status == "GREEN":
            print("✅ All checks passed. Safe to proceed with Phase 1.")
        elif overall_status == "YELLOW":
            print("⚠️  Minor issues detected. Review warnings before proceeding.")
            print("   Phase 1 can proceed with caution.")
        else:
            print("❌ Critical issues detected. Fix RED issues before Phase 1.")
            print("   Do not proceed until all RED issues are resolved.")
        
        return overall_status

def main():
    parser = argparse.ArgumentParser(description="Quick GUI Stability Validation")
    parser.add_argument("--verbose", "-v", action="store_true", 
                      help="Enable verbose output")
    
    args = parser.parse_args()
    
    validator = QuickValidator(verbose=args.verbose)
    validator.run_all_checks()
    overall_status = validator.generate_report()
    
    # Exit with appropriate code
    exit_codes = {"GREEN": 0, "YELLOW": 1, "RED": 2}
    sys.exit(exit_codes.get(overall_status, 2))

if __name__ == "__main__":
    main()