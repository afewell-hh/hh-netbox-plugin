#!/usr/bin/env python3
"""
Deep analysis of why sync still reports 0 YAML files
"""

deep_analysis = """
from netbox_hedgehog.models import HedgehogFabric
from netbox_hedgehog.services.gitops_onboarding_service import GitOpsOnboardingService
import inspect

print("=== DEEP SYNC ANALYSIS ===")

fabric = HedgehogFabric.objects.get(name="Test Fabric for GitOps Initialization")
print(f"Fabric: {fabric.name}")
print(f"GitOps directory: '{fabric.gitops_directory}'")

onboarding_service = GitOpsOnboardingService(fabric)
github_client = onboarding_service._get_github_client(fabric.git_repository)

# Test raw directory access
raw_path = f"{fabric.gitops_directory}/raw"
raw_contents = github_client.get_directory_contents(raw_path)

print(f"\\nRaw directory contents ({len(raw_contents)} items):")
for item in raw_contents:
    name = item.get('name')
    item_type = item.get('type')
    print(f"  - {name} ({item_type})")
    
    # Test file content for YAML files
    if name.endswith('.yaml') and item_type == 'file':
        try:
            file_path = f"{raw_path}/{name}"
            content = github_client.get_file_content(file_path)
            print(f"    Content: {len(content)} bytes")
            print(f"    First 100 chars: {content[:100]}...")
        except Exception as e:
            print(f"    Failed to get content: {e}")

print("\\n=== ANALYZING SYNC METHOD ===")

# Let's inspect the sync method to see why it reports 0 files
try:
    sync_method = onboarding_service.sync_github_repository
    source_lines = inspect.getsourcelines(sync_method)
    
    print(f"Sync method has {len(source_lines[0])} lines")
    
    # Look for the specific logic that counts files
    source_code = ''.join(source_lines[0])
    
    if 'analyze_fabric_directory' in source_code:
        print("✅ Found analyze_fabric_directory call")
    
    if 'YAML files found' in source_code:
        print("✅ Found YAML files counting logic")
    
    # Let's trace what analyze_fabric_directory actually does
    print("\\n=== TESTING analyze_fabric_directory DIRECTLY ===")
    
    analysis = github_client.analyze_fabric_directory(fabric.gitops_directory)
    print(f"Analysis result: {analysis}")
    
    # Check if the method is looking in the right place
    print("\\n=== CHECKING EXPECTED VS ACTUAL ===")
    
    # What does the method expect to find?
    # Let's see if it's looking for files in the root vs raw directory
    
    # Test root directory
    root_contents = github_client.get_directory_contents(fabric.gitops_directory)
    yaml_in_root = [f for f in root_contents if f.get('name', '').endswith('.yaml')]
    print(f"YAML files in root directory: {len(yaml_in_root)}")
    
    # Test raw directory
    yaml_in_raw = [f for f in raw_contents if f.get('name', '').endswith('.yaml')]
    print(f"YAML files in raw directory: {len(yaml_in_raw)}")
    
    print("\\n=== HYPOTHESIS ===")
    if len(yaml_in_raw) > 0 and len(yaml_in_root) == 0:
        print("ISSUE: Sync method may be looking in root directory instead of raw directory")
        print("The files are in raw/ but the sync is scanning the root of gitops_directory")
    
except Exception as e:
    print(f"Analysis failed: {e}")
    import traceback
    traceback.print_exc()

print("\\n=== TESTING MANUAL FILE PROCESSING ===")

# Let's try to manually process a file to see what should happen
try:
    yaml_files = [f for f in raw_contents if f.get('name', '').endswith('.yaml') and f.get('name') != '.gitkeep']
    
    if yaml_files:
        test_file = yaml_files[0]
        filename = test_file['name']
        file_path = f"{raw_path}/{filename}"
        
        print(f"Testing manual processing of: {filename}")
        
        # Get file content
        content = github_client.get_file_content(file_path)
        print(f"File content ({len(content)} bytes):")
        print(content[:200] + "..." if len(content) > 200 else content)
        
        # Check if it's valid YAML
        import yaml
        try:
            yaml_data = yaml.safe_load(content)
            print(f"✅ Valid YAML with {len(yaml_data) if isinstance(yaml_data, dict) else 'unknown'} top-level keys")
        except yaml.YAMLError as e:
            print(f"❌ Invalid YAML: {e}")
    
except Exception as e:
    print(f"Manual processing failed: {e}")
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
    print("DEEP ANALYSIS OF SYNC LOGIC")
    print("=" * 80)
    
    stdout, stderr, code = run_django_command(deep_analysis)
    print(stdout)
    if stderr:
        print(f"STDERR: {stderr}")
    
    print("\n" + "=" * 80)
    print("DEEP ANALYSIS COMPLETE")
    print("=" * 80)