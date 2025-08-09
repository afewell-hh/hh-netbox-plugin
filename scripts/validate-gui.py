#!/usr/bin/env python3
"""
GUI validation script - Simple validation to confirm GUI testing framework works
This is a minimal version to start testing the concept
"""
import subprocess
import sys
import os

def check_nodejs():
    """Check if Node.js is available"""
    try:
        result = subprocess.run(['node', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ Node.js available: {result.stdout.strip()}")
            return True
        else:
            print("❌ Node.js not available")
            return False
    except FileNotFoundError:
        print("❌ Node.js not installed")
        return False

def check_netbox_accessibility():
    """Check if NetBox is accessible for GUI testing"""
    try:
        result = subprocess.run(['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}', 'http://localhost:8000/'], capture_output=True, text=True)
        status_code = result.stdout.strip()
        
        if status_code in ['200', '302']:  # 302 is normal for login redirect
            print(f"✅ NetBox accessible (HTTP {status_code})")
            return True
        else:
            print(f"❌ NetBox not accessible (HTTP {status_code})")
            return False
    except Exception as e:
        print(f"❌ Error checking NetBox: {e}")
        return False

def basic_page_test():
    """Basic test using curl to check for HTML comment bug"""
    try:
        # Test the known problematic page
        result = subprocess.run([
            'curl', '-s', 'http://localhost:8000/plugins/hedgehog/git-repositories/1/'
        ], capture_output=True, text=True)
        
        html_content = result.stdout
        
        # Look for HTML comments that should be hidden but are visible
        problematic_comments = []
        lines = html_content.split('\n')
        for i, line in enumerate(lines):
            if '<\\!--' in line:  # Escaped HTML comment (bug)
                problematic_comments.append(f"Line {i+1}: {line.strip()}")
        
        if problematic_comments:
            print(f"❌ HTML Comment Bug Found ({len(problematic_comments)} instances):")
            for comment in problematic_comments[:3]:  # Show first 3
                print(f"   {comment}")
            return False
        else:
            print("✅ No HTML comment bugs detected")
            return True
            
    except Exception as e:
        print(f"❌ Error testing page: {e}")
        return False

def check_playwright_framework():
    """Check if Playwright GUI testing framework is properly configured"""
    try:
        # Check if package.json exists with Playwright
        if not os.path.exists('package.json'):
            print("❌ package.json not found")
            return False
        
        with open('package.json', 'r') as f:
            import json
            package_data = json.load(f)
        
        playwright_installed = '@playwright/test' in package_data.get('devDependencies', {})
        if not playwright_installed:
            print("❌ @playwright/test not found in devDependencies")
            return False
        
        print("✅ Playwright framework properly configured")
        return True
        
    except Exception as e:
        print(f"❌ Error checking Playwright framework: {e}")
        return False

def run_basic_gui_test():
    """Run a basic Playwright GUI test"""
    try:
        # Check if tests directory exists
        if not os.path.exists('tests/gui'):
            print("❌ GUI tests directory not found")
            return False
        
        # Run a single basic test with timeout
        result = subprocess.run([
            'npx', 'playwright', 'test', 'tests/gui/netbox-hedgehog.spec.ts', 
            '--timeout=30000', '--workers=1'
        ], capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            print("✅ Basic GUI test passed")
            return True
        else:
            print(f"❌ GUI test failed (exit code: {result.returncode})")
            if result.stderr:
                print(f"   Error output: {result.stderr[:200]}...")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ GUI test timed out")
        return False
    except Exception as e:
        print(f"❌ Error running GUI test: {e}")
        return False

def main():
    """Main validation function"""
    print("=" * 60)
    print("GUI VALIDATION - COMPREHENSIVE CHECKS")
    print("=" * 60)
    
    checks = []
    
    # Check prerequisites
    checks.append(("Node.js Available", check_nodejs()))
    checks.append(("NetBox Accessible", check_netbox_accessibility()))
    
    # Check GUI testing framework
    checks.append(("Playwright Framework", check_playwright_framework()))
    
    # Check for known bugs
    checks.append(("HTML Comment Bug Check", basic_page_test()))
    
    # Run actual GUI test
    checks.append(("Basic GUI Test", run_basic_gui_test()))
    
    # Summary
    passed = sum(1 for _, result in checks if result)
    total = len(checks)
    
    print(f"\nSUMMARY: {passed}/{total} checks passed")
    
    if passed == total:
        print("✅ Comprehensive GUI validation passed")
        return 0
    else:
        print("❌ GUI validation failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())