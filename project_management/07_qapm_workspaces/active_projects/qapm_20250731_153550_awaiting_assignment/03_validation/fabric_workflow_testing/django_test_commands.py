#!/usr/bin/env python3
"""
Commands to run in Django shell to test GitOps sync
"""

# Test 1: Find fabric for gitops-test-1
test1_cmd = """
from netbox_hedgehog.models import HedgehogFabric

print("=== TEST 1: FABRIC CONFIGURATION ===")
fabrics = HedgehogFabric.objects.all()
print(f"Total fabrics: {fabrics.count()}")

target_fabric = None
for fabric in fabrics:
    print(f"Fabric: {fabric.name}")
    if fabric.git_repository:
        print(f"  Repo: {fabric.git_repository.url}")
        print(f"  GitOps Dir: {fabric.gitops_directory}")
        if 'gitops-test-1' in fabric.git_repository.url:
            target_fabric = fabric
            print("  *** TARGET FABRIC FOUND ***")
    else:
        print("  No repository")

if target_fabric:
    print(f"Success: Found fabric {target_fabric.name}")
    print(f"GitOps directory: {target_fabric.gitops_directory}")
    fabric_id = target_fabric.id
else:
    print("ERROR: No target fabric found")
    fabric_id = None
"""

# Test 2: GitHub access
test2_cmd = """
from netbox_hedgehog.models import HedgehogFabric
from netbox_hedgehog.services.gitops_onboarding_service import GitOpsOnboardingService

print("=== TEST 2: GITHUB ACCESS ===")

# Get the fabric (you may need to adjust the ID)
try:
    fabric = HedgehogFabric.objects.filter(git_repository__url__contains='gitops-test-1').first()
    if not fabric:
        print("ERROR: No target fabric found")
    else:
        print(f"Testing fabric: {fabric.name}")
        
        # Create onboarding service
        onboarding_service = GitOpsOnboardingService(fabric)
        github_client = onboarding_service._get_github_client(fabric.git_repository)
        
        # Check raw directory
        raw_path = f"{fabric.gitops_directory}/raw"
        print(f"Checking: {raw_path}")
        
        raw_contents = github_client.get_directory_contents(raw_path)
        print(f"Files found: {len(raw_contents)}")
        
        for file_info in raw_contents:
            print(f"  - {file_info.get('name')} ({file_info.get('type')})")
        
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
"""

# Test 3: Sync execution
test3_cmd = """
from netbox_hedgehog.models import HedgehogFabric
from netbox_hedgehog.services.gitops_onboarding_service import GitOpsOnboardingService

print("=== TEST 3: SYNC EXECUTION ===")

try:
    fabric = HedgehogFabric.objects.filter(git_repository__url__contains='gitops-test-1').first()
    if not fabric:
        print("ERROR: No target fabric found")
    else:
        print(f"Running sync for: {fabric.name}")
        
        onboarding_service = GitOpsOnboardingService(fabric)
        
        # Validation only
        print("Running validation...")
        validation_result = onboarding_service.sync_github_repository(validate_only=True)
        print(f"Validation success: {validation_result.get('success')}")
        if validation_result.get('error'):
            print(f"Validation error: {validation_result['error']}")
        
        # Actual sync
        print("Running actual sync...")
        sync_result = onboarding_service.sync_github_repository(validate_only=False)
        print(f"Sync success: {sync_result.get('success')}")
        print(f"Files processed: {sync_result.get('files_processed', 0)}")
        
        if sync_result.get('error'):
            print(f"Sync error: {sync_result['error']}")
        
        operations = sync_result.get('github_operations', [])
        print(f"Operations: {len(operations)}")
        for op in operations:
            print(f"  - {op}")
        
        print("=== DIAGNOSIS ===")
        if sync_result.get('success') and sync_result.get('files_processed', 0) == 0:
            print("ISSUE: Sync succeeded but no files processed")
            print("Files exist in GitHub but are not being processed by sync")
        
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
"""

import subprocess

def run_django_command(cmd):
    """Run a Django shell command"""
    # Write command to temporary file
    with open('/tmp/django_cmd.py', 'w') as f:
        f.write(cmd)
    
    # Copy to container
    subprocess.run(['sudo', 'docker', 'cp', '/tmp/django_cmd.py', 'netbox-docker-netbox-1:/tmp/django_cmd.py'])
    
    # Execute in Django shell
    result = subprocess.run(
        ['sudo', 'docker', 'exec', 'netbox-docker-netbox-1', 'python', '/opt/netbox/netbox/manage.py', 'shell', '-c', 'exec(open("/tmp/django_cmd.py").read())'],
        capture_output=True, text=True
    )
    
    return result.stdout, result.stderr, result.returncode

if __name__ == "__main__":
    print("CRITICAL MISSION: Test actual FGD synchronization")
    print("Repository: https://github.com/afewell-hh/gitops-test-1.git")
    print("=" * 80)
    
    # Test 1: Fabric configuration
    print("Running Test 1...")
    stdout, stderr, code = run_django_command(test1_cmd)
    print(stdout)
    if stderr:
        print(f"STDERR: {stderr}")
    
    # Test 2: GitHub access
    print("\nRunning Test 2...")
    stdout, stderr, code = run_django_command(test2_cmd)
    print(stdout)
    if stderr:
        print(f"STDERR: {stderr}")
    
    # Test 3: Sync execution
    print("\nRunning Test 3...")
    stdout, stderr, code = run_django_command(test3_cmd)
    print(stdout)
    if stderr:
        print(f"STDERR: {stderr}")
    
    print("\n" + "=" * 80)
    print("TESTING COMPLETE")
    print("=" * 80)