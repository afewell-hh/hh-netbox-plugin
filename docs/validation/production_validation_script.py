#!/usr/bin/env python3
"""
FINAL PRODUCTION VALIDATION FOR ENHANCED HIVE ORCHESTRATION METHODOLOGY
Issue #50 - Independent Validation Script

This script performs comprehensive validation of all claimed functionality
from the Enhanced Hive Orchestration Methodology evidence packages.
"""

import json
import subprocess
import requests
import datetime
import sys
import os
from pathlib import Path

def log_result(test_name, status, details):
    """Log test results with timestamp"""
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    print(f"[{timestamp}] {test_name}: {status}")
    if details:
        print(f"  Details: {details}")

def run_command(cmd, description):
    """Run shell command and return result"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        return {
            'success': result.returncode == 0,
            'stdout': result.stdout.strip(),
            'stderr': result.stderr.strip(),
            'return_code': result.returncode
        }
    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'stdout': '',
            'stderr': 'Command timeout',
            'return_code': -1
        }

def validate_evidence_files():
    """Validate all evidence files exist and have consistent timestamps"""
    evidence_files = [
        "PHASE0_BASELINE_EVIDENCE_20250811_195512.json",
        "PHASE2_VALIDATION_CASCADE_FRAMEWORK_20250811_195612.json", 
        "PHASE3_PRODUCTION_TESTING_EVIDENCE_20250811_200702.json",
        "PHASE4_EMERGENCY_PROTOCOLS_20250811_200715.json"
    ]
    
    results = {}
    for filename in evidence_files:
        filepath = Path(filename)
        if filepath.exists():
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                    results[filename] = {
                        'exists': True,
                        'timestamp': data.get('timestamp'),
                        'phase': data.get('phase'),
                        'methodology': data.get('methodology'),
                        'file_size': filepath.stat().st_size
                    }
                log_result(f"Evidence File {filename}", "✅ VALID", f"Size: {filepath.stat().st_size} bytes")
            except Exception as e:
                results[filename] = {'exists': True, 'error': str(e)}
                log_result(f"Evidence File {filename}", "❌ INVALID", f"Parse error: {e}")
        else:
            results[filename] = {'exists': False}
            log_result(f"Evidence File {filename}", "❌ MISSING", "File not found")
    
    return results

def validate_container_health():
    """Validate container b05eb5eff181 is healthy and operational"""
    # Check container status
    cmd = "sudo docker ps | grep b05eb5eff181"
    result = run_command(cmd, "Container status check")
    
    if not result['success']:
        log_result("Container Health", "❌ FAILED", "Container b05eb5eff181 not found")
        return False
    
    # Verify it's marked as healthy
    if "healthy" not in result['stdout']:
        log_result("Container Health", "⚠️ WARNING", "Container not marked as healthy")
        return False
    
    log_result("Container Health", "✅ VALID", "Container b05eb5eff181 is healthy")
    return True

def validate_plugin_functionality():
    """Test NetBox plugin endpoints and functionality"""
    endpoints_to_test = [
        ("Plugin Dashboard", "http://localhost:8000/plugins/hedgehog/"),
        ("Fabrics List", "http://localhost:8000/plugins/hedgehog/fabrics/"),
        ("Fabric Detail", "http://localhost:8000/plugins/hedgehog/fabrics/35/")
    ]
    
    results = {}
    for name, url in endpoints_to_test:
        try:
            response = requests.head(url, timeout=10)
            if response.status_code == 200:
                results[name] = {
                    'status_code': response.status_code,
                    'content_length': response.headers.get('content-length', 'unknown'),
                    'content_type': response.headers.get('content-type', 'unknown')
                }
                log_result(f"Endpoint {name}", "✅ VALID", f"HTTP {response.status_code}, Size: {response.headers.get('content-length', 'unknown')} bytes")
            else:
                results[name] = {'status_code': response.status_code, 'error': 'Non-200 response'}
                log_result(f"Endpoint {name}", "❌ FAILED", f"HTTP {response.status_code}")
        except Exception as e:
            results[name] = {'error': str(e)}
            log_result(f"Endpoint {name}", "❌ FAILED", f"Request error: {e}")
    
    return results

def validate_database_models():
    """Test database model functionality as claimed in evidence"""
    model_tests = [
        {
            'name': 'Fabric Count',
            'command': 'sudo docker exec b05eb5eff181 bash -c "cd /opt/netbox/netbox && python manage.py shell -c \\"from netbox_hedgehog.models import HedgehogFabric; print(HedgehogFabric.objects.count())\\"',
            'expected_output': '1'
        },
        {
            'name': 'VPC Count', 
            'command': 'sudo docker exec b05eb5eff181 bash -c "cd /opt/netbox/netbox && python manage.py shell -c \\"from netbox_hedgehog.models import VPC; print(VPC.objects.count())\\"',
            'expected_output': '2'
        },
        {
            'name': 'Fabric Sync Status',
            'command': 'sudo docker exec b05eb5eff181 bash -c "cd /opt/netbox/netbox && python manage.py shell -c \\"from netbox_hedgehog.models import HedgehogFabric; fabric = HedgehogFabric.objects.first(); print(fabric.sync_status)\\"',
            'expected_output': 'synced'
        }
    ]
    
    results = {}
    for test in model_tests:
        result = run_command(test['command'], test['name'])
        if result['success']:
            # Extract the actual result from Django's verbose output
            output_lines = result['stdout'].split('\n')
            actual_output = output_lines[-1].strip()  # Last line should be the actual result
            
            if test['expected_output'] in actual_output:
                results[test['name']] = {'success': True, 'output': actual_output}
                log_result(f"Database Model {test['name']}", "✅ VALID", f"Output: {actual_output}")
            else:
                results[test['name']] = {'success': False, 'output': actual_output, 'expected': test['expected_output']}
                log_result(f"Database Model {test['name']}", "❌ FAILED", f"Expected: {test['expected_output']}, Got: {actual_output}")
        else:
            results[test['name']] = {'success': False, 'error': result['stderr']}
            log_result(f"Database Model {test['name']}", "❌ FAILED", f"Command error: {result['stderr']}")
    
    return results

def validate_no_regressions():
    """Check for any regressions from baseline state"""
    baseline_checks = [
        {
            'name': 'NetBox Main Page',
            'command': 'curl -s -I http://localhost:8000/',
            'success_indicator': '200 OK'
        },
        {
            'name': 'Container Logs Clean',
            'command': 'sudo docker logs b05eb5eff181 --tail 20',
            'failure_indicators': ['ERROR', 'CRITICAL', 'Exception', 'Traceback']
        }
    ]
    
    results = {}
    for check in baseline_checks:
        result = run_command(check['command'], check['name'])
        if result['success']:
            if 'success_indicator' in check and check['success_indicator'] in result['stdout']:
                results[check['name']] = {'success': True, 'details': 'Success indicator found'}
                log_result(f"Regression Check {check['name']}", "✅ VALID", "No regression detected")
            elif 'failure_indicators' in check:
                failures = [indicator for indicator in check['failure_indicators'] if indicator in result['stdout']]
                if failures:
                    results[check['name']] = {'success': False, 'failures': failures}
                    log_result(f"Regression Check {check['name']}", "❌ FAILED", f"Found: {failures}")
                else:
                    results[check['name']] = {'success': True, 'details': 'No failure indicators found'}
                    log_result(f"Regression Check {check['name']}", "✅ VALID", "No regression detected")
            else:
                results[check['name']] = {'success': True, 'details': 'Command executed successfully'}
                log_result(f"Regression Check {check['name']}", "✅ VALID", "Command successful")
        else:
            results[check['name']] = {'success': False, 'error': result['stderr']}
            log_result(f"Regression Check {check['name']}", "❌ FAILED", f"Command failed: {result['stderr']}")
    
    return results

def main():
    """Main validation execution"""
    print("=" * 80)
    print("FINAL PRODUCTION VALIDATION - Enhanced Hive Orchestration Methodology")
    print("Issue #50 - Independent Validation")
    print("=" * 80)
    
    validation_results = {
        'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'validation_type': 'Enhanced Hive Orchestration Methodology - Issue #50',
        'results': {}
    }
    
    # 1. Evidence File Validation
    print("\n1. EVIDENCE FILE VALIDATION")
    print("-" * 40)
    validation_results['results']['evidence_files'] = validate_evidence_files()
    
    # 2. Container Health Validation
    print("\n2. CONTAINER HEALTH VALIDATION")
    print("-" * 40)
    validation_results['results']['container_health'] = validate_container_health()
    
    # 3. Plugin Functionality Validation
    print("\n3. PLUGIN FUNCTIONALITY VALIDATION")
    print("-" * 40)
    validation_results['results']['plugin_functionality'] = validate_plugin_functionality()
    
    # 4. Database Model Validation
    print("\n4. DATABASE MODEL VALIDATION")
    print("-" * 40)
    validation_results['results']['database_models'] = validate_database_models()
    
    # 5. Regression Testing
    print("\n5. REGRESSION TESTING")
    print("-" * 40)
    validation_results['results']['regression_testing'] = validate_no_regressions()
    
    # Final Assessment
    print("\n" + "=" * 80)
    print("FINAL VALIDATION ASSESSMENT")
    print("=" * 80)
    
    # Determine overall pass/fail
    total_tests = 0
    passed_tests = 0
    
    for category, results in validation_results['results'].items():
        if isinstance(results, dict):
            for test_name, test_result in results.items():
                total_tests += 1
                if isinstance(test_result, dict) and test_result.get('success', test_result.get('exists', False)):
                    passed_tests += 1
    
    pass_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
    
    validation_results['summary'] = {
        'total_tests': total_tests,
        'passed_tests': passed_tests,
        'pass_rate': pass_rate,
        'overall_status': 'PASS' if pass_rate >= 90 else 'FAIL'
    }
    
    print(f"Total Tests: {total_tests}")
    print(f"Passed Tests: {passed_tests}")
    print(f"Pass Rate: {pass_rate:.1f}%")
    print(f"Overall Status: {validation_results['summary']['overall_status']}")
    
    if validation_results['summary']['overall_status'] == 'PASS':
        print("\n✅ VALIDATION PASSED - Enhanced Hive Orchestration Methodology implementation is verified")
    else:
        print("\n❌ VALIDATION FAILED - Implementation does not meet validation criteria")
    
    # Save detailed results
    with open('production_validation_results.json', 'w') as f:
        json.dump(validation_results, f, indent=2)
    
    print(f"\nDetailed results saved to: production_validation_results.json")
    
    return validation_results['summary']['overall_status'] == 'PASS'

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)