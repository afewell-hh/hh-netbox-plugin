#!/usr/bin/env python3
"""
CSS Readability Improvements Validation Script
Validates that CSS improvements are deployed and functional in NetBox container
"""

import subprocess
import requests
import sys
import re
from pathlib import Path

class CSSReadabilityValidator:
    def __init__(self):
        self.netbox_url = "http://localhost:8000"
        self.container_name = "netbox-docker-netbox-1"
        self.issues_found = []
        self.validations_passed = []
        
    def log_issue(self, issue):
        """Log a validation issue"""
        self.issues_found.append(issue)
        print(f"❌ {issue}")
        
    def log_success(self, success):
        """Log a successful validation"""
        self.validations_passed.append(success)
        print(f"✅ {success}")
        
    def run_docker_command(self, cmd):
        """Execute command in NetBox container"""
        try:
            result = subprocess.run(
                ["sudo", "docker", "exec", self.container_name] + cmd,
                capture_output=True, text=True, check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            return None
            
    def test_css_file_deployment(self):
        """Test 1: Verify CSS files are deployed in container"""
        print("\n🔍 Testing CSS File Deployment...")
        
        # Check hedgehog.css exists and has correct size
        stat_output = self.run_docker_command([
            "stat", "/opt/netbox/netbox/static/netbox_hedgehog/css/hedgehog.css"
        ])
        
        if stat_output and "Size: 34477" in stat_output:
            self.log_success("hedgehog.css deployed with correct size (34,477 bytes)")
        else:
            self.log_issue("hedgehog.css not found or incorrect size in container")
            
        # Check progressive-disclosure.css exists
        stat_output = self.run_docker_command([
            "stat", "/opt/netbox/netbox/static/netbox_hedgehog/css/progressive-disclosure.css"
        ])
        
        if stat_output and "Size: 9448" in stat_output:
            self.log_success("progressive-disclosure.css deployed with correct size (9,448 bytes)")
        else:
            self.log_issue("progressive-disclosure.css not found or incorrect size in container")
            
    def test_css_content_validation(self):
        """Test 2: Verify CSS improvements are present in deployed files"""
        print("\n🔍 Testing CSS Content Validation...")
        
        # Test warning badge fix
        grep_result = self.run_docker_command([
            "grep", "-A", "3", "Pure black for maximum contrast on yellow",
            "/opt/netbox/netbox/static/netbox_hedgehog/css/hedgehog.css"
        ])
        
        if grep_result and "color: #000 !important" in grep_result:
            self.log_success("Warning badge high contrast fix present")
        else:
            self.log_issue("Warning badge high contrast fix not found")
            
        # Test pre-formatted text fixes
        grep_result = self.run_docker_command([
            "grep", "-A", "5", "pre.bg-light",
            "/opt/netbox/netbox/static/netbox_hedgehog/css/hedgehog.css"
        ])
        
        if grep_result and "Pure black for maximum contrast" in grep_result:
            self.log_success("Pre-formatted text readability improvements present")
        else:
            self.log_issue("Pre-formatted text readability improvements not found")
            
        # Test utility classes
        grep_result = self.run_docker_command([
            "grep", "-A", "10", "readable-text",
            "/opt/netbox/netbox/static/netbox_hedgehog/css/hedgehog.css"
        ])
        
        if grep_result and "readable-secondary-text" in grep_result:
            self.log_success("Utility classes for readability present")
        else:
            self.log_issue("Utility classes for readability not found")
            
    def test_http_accessibility(self):
        """Test 3: Verify CSS files are accessible via HTTP"""
        print("\n🔍 Testing HTTP Accessibility...")
        
        # Test hedgehog.css HTTP access
        try:
            response = requests.get(f"{self.netbox_url}/static/netbox_hedgehog/css/hedgehog.css", timeout=10)
            if response.status_code == 200 and len(response.content) > 30000:
                self.log_success("hedgehog.css accessible via HTTP with correct content size")
            else:
                self.log_issue(f"hedgehog.css HTTP access failed: {response.status_code}")
        except Exception as e:
            self.log_issue(f"hedgehog.css HTTP access error: {str(e)}")
            
        # Test progressive-disclosure.css HTTP access
        try:
            response = requests.get(f"{self.netbox_url}/static/netbox_hedgehog/css/progressive-disclosure.css", timeout=10)
            if response.status_code == 200 and len(response.content) > 5000:
                self.log_success("progressive-disclosure.css accessible via HTTP with correct content size")
            else:
                self.log_issue(f"progressive-disclosure.css HTTP access failed: {response.status_code}")
        except Exception as e:
            self.log_issue(f"progressive-disclosure.css HTTP access error: {str(e)}")
            
    def test_netbox_pages_accessibility(self):
        """Test 4: Verify HNP pages are accessible"""
        print("\n🔍 Testing NetBox Page Accessibility...")
        
        test_urls = [
            "/plugins/hedgehog/fabrics/",
            "/plugins/hedgehog/vpcs/",
            "/plugins/hedgehog/connections/",
            "/plugins/hedgehog/switches/"
        ]
        
        for url in test_urls:
            try:
                response = requests.get(f"{self.netbox_url}{url}", timeout=10, allow_redirects=False)
                # 200 = accessible, 302 = authentication redirect (normal)
                if response.status_code in [200, 302]:
                    self.log_success(f"HNP page {url} accessible (status: {response.status_code})")
                else:
                    self.log_issue(f"HNP page {url} not accessible (status: {response.status_code})")
            except Exception as e:
                self.log_issue(f"HNP page {url} access error: {str(e)}")
                
    def test_container_health(self):
        """Test 5: Verify NetBox container health"""
        print("\n🔍 Testing Container Health...")
        
        # Check container status
        try:
            result = subprocess.run(
                ["sudo", "docker", "ps", "--filter", f"name={self.container_name}", "--format", "{{.Status}}"],
                capture_output=True, text=True, check=True
            )
            
            status = result.stdout.strip()
            if "healthy" in status.lower():
                self.log_success(f"NetBox container healthy: {status}")
            else:
                self.log_issue(f"NetBox container not healthy: {status}")
                
        except subprocess.CalledProcessError as e:
            self.log_issue(f"Failed to check container status: {str(e)}")
            
        # Check for recent CSS-related log entries
        try:
            result = subprocess.run(
                ["sudo", "docker", "logs", "--tail", "50", self.container_name],
                capture_output=True, text=True, check=True
            )
            
            logs = result.stdout
            if "static/netbox_hedgehog/css" in logs:
                self.log_success("CSS files being served according to container logs")
            else:
                print("ℹ️  No recent CSS access in container logs (this is normal)")
                
        except subprocess.CalledProcessError as e:
            self.log_issue(f"Failed to check container logs: {str(e)}")
            
    def test_css_specificity_and_overrides(self):
        """Test 6: Verify CSS improvements have proper specificity"""
        print("\n🔍 Testing CSS Specificity and Overrides...")
        
        # Check for !important declarations (needed to override NetBox styles)
        grep_result = self.run_docker_command([
            "grep", "-c", "!important",
            "/opt/netbox/netbox/static/netbox_hedgehog/css/hedgehog.css"
        ])
        
        if grep_result and int(grep_result) > 50:
            self.log_success(f"CSS has proper specificity with {grep_result} !important declarations")
        else:
            self.log_issue("CSS may lack proper specificity for NetBox style overrides")
            
        # Check for comprehensive selector coverage
        grep_result = self.run_docker_command([
            "grep", "-c", "html body",
            "/opt/netbox/netbox/static/netbox_hedgehog/css/hedgehog.css"
        ])
        
        if grep_result and int(grep_result) > 10:
            self.log_success(f"CSS has comprehensive selector coverage with {grep_result} high-specificity selectors")
        else:
            self.log_issue("CSS may lack comprehensive selector coverage")
    
    def generate_report(self):
        """Generate final validation report"""
        print("\n" + "="*80)
        print("CSS READABILITY IMPROVEMENTS VALIDATION REPORT")
        print("="*80)
        
        print(f"\n✅ VALIDATIONS PASSED: {len(self.validations_passed)}")
        for success in self.validations_passed:
            print(f"   • {success}")
            
        if self.issues_found:
            print(f"\n❌ ISSUES FOUND: {len(self.issues_found)}")
            for issue in self.issues_found:
                print(f"   • {issue}")
        else:
            print(f"\n🎉 NO ISSUES FOUND - ALL VALIDATIONS PASSED!")
            
        print(f"\n📊 SUMMARY:")
        print(f"   Total Tests: {len(self.validations_passed) + len(self.issues_found)}")
        print(f"   Passed: {len(self.validations_passed)}")
        print(f"   Failed: {len(self.issues_found)}")
        
        success_rate = (len(self.validations_passed) / (len(self.validations_passed) + len(self.issues_found))) * 100
        print(f"   Success Rate: {success_rate:.1f}%")
        
        if len(self.issues_found) == 0:
            print(f"\n🎯 VALIDATION RESULT: ✅ CSS READABILITY IMPROVEMENTS SUCCESSFULLY DEPLOYED")
            return True
        else:
            print(f"\n🎯 VALIDATION RESULT: ❌ ISSUES DETECTED - REQUIRES ATTENTION")
            return False

def main():
    """Main validation function"""
    print("CSS Readability Improvements Validation")
    print("=" * 50)
    
    validator = CSSReadabilityValidator()
    
    # Run all validation tests
    validator.test_css_file_deployment()
    validator.test_css_content_validation()
    validator.test_http_accessibility()
    validator.test_netbox_pages_accessibility()
    validator.test_container_health()
    validator.test_css_specificity_and_overrides()
    
    # Generate final report
    success = validator.generate_report()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()