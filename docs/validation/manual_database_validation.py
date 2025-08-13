#!/usr/bin/env python3
"""
Manual Database Validation for Enhanced Hive Orchestration Methodology
"""

import subprocess
import json
import datetime

def run_docker_command(command):
    """Run a command in the NetBox container"""
    full_command = f'sudo docker exec b05eb5eff181 bash -c "cd /opt/netbox/netbox && {command}"'
    try:
        result = subprocess.run(full_command, shell=True, capture_output=True, text=True, timeout=30)
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

def main():
    print("MANUAL DATABASE VALIDATION")
    print("=" * 50)
    
    # Test 1: Fabric Count
    print("1. Testing Fabric Count...")
    fabric_cmd = 'python manage.py shell -c "from netbox_hedgehog.models import HedgehogFabric; print(HedgehogFabric.objects.count())"'
    result1 = run_docker_command(fabric_cmd)
    
    if result1['success']:
        output_lines = result1['stdout'].split('\n')
        actual_count = output_lines[-1].strip()
        print(f"   Result: {actual_count}")
        fabric_success = actual_count == '1'
    else:
        print(f"   Error: {result1['stderr']}")
        fabric_success = False
    
    # Test 2: VPC Count
    print("2. Testing VPC Count...")
    vpc_cmd = 'python manage.py shell -c "from netbox_hedgehog.models import VPC; print(VPC.objects.count())"'
    result2 = run_docker_command(vpc_cmd)
    
    if result2['success']:
        output_lines = result2['stdout'].split('\n')
        actual_count = output_lines[-1].strip()
        print(f"   Result: {actual_count}")
        vpc_success = actual_count == '2'
    else:
        print(f"   Error: {result2['stderr']}")
        vpc_success = False
    
    # Test 3: Fabric Sync Status
    print("3. Testing Fabric Sync Status...")
    sync_cmd = 'python manage.py shell -c "from netbox_hedgehog.models import HedgehogFabric; fabric = HedgehogFabric.objects.first(); print(f\'{fabric.name}|{fabric.sync_status}|{fabric.last_sync}\')"'
    result3 = run_docker_command(sync_cmd)
    
    if result3['success']:
        output_lines = result3['stdout'].split('\n')
        actual_output = output_lines[-1].strip()
        print(f"   Result: {actual_output}")
        sync_success = 'synced' in actual_output and 'Test Lab K3s Cluster' in actual_output
    else:
        print(f"   Error: {result3['stderr']}")
        sync_success = False
    
    # Summary
    print("\nSUMMARY")
    print("-" * 20)
    total_tests = 3
    passed_tests = sum([fabric_success, vpc_success, sync_success])
    
    print(f"Fabric Count Test: {'✅ PASS' if fabric_success else '❌ FAIL'}")
    print(f"VPC Count Test: {'✅ PASS' if vpc_success else '❌ FAIL'}")
    print(f"Sync Status Test: {'✅ PASS' if sync_success else '❌ FAIL'}")
    print(f"\nPassed: {passed_tests}/{total_tests}")
    
    # Save results
    validation_data = {
        'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'tests': {
            'fabric_count': {'success': fabric_success, 'details': result1},
            'vpc_count': {'success': vpc_success, 'details': result2},
            'sync_status': {'success': sync_success, 'details': result3}
        },
        'summary': {
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'pass_rate': (passed_tests / total_tests * 100),
            'overall_pass': passed_tests == total_tests
        }
    }
    
    with open('manual_database_validation_results.json', 'w') as f:
        json.dump(validation_data, f, indent=2)
    
    print(f"\nDetailed results saved to: manual_database_validation_results.json")
    return passed_tests == total_tests

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)