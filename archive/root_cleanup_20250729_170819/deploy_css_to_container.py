#!/usr/bin/env python3
"""
Deploy CSS changes to running NetBox Docker container

This script attempts to copy the updated hedgehog.css file to the running
NetBox container and collect static files to apply the badge readability improvements.
"""

import subprocess
import sys
from pathlib import Path

def deploy_css_to_container():
    """Deploy CSS to Docker container"""
    
    print("=" * 60)
    print("DEPLOYING CSS CHANGES TO NETBOX CONTAINER")
    print("=" * 60)
    
    # Check if CSS file exists
    css_file = Path("/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/static/netbox_hedgehog/css/hedgehog.css")
    
    if not css_file.exists():
        print("❌ CSS file not found:", css_file)
        return False
        
    print("✅ CSS file found:", css_file)
    print(f"   File size: {css_file.stat().st_size:,} bytes")
    
    try:
        # Find running NetBox containers
        print("\n🔍 Looking for NetBox containers...")
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}", "--filter", "name=netbox"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            print("⚠️  Could not access Docker daemon")
            print("   This might be due to permissions or Docker not running")
            print("   Manual deployment required:")
            print(f"   1. Copy {css_file}")
            print("   2. To: /opt/netbox/netbox/static/netbox_hedgehog/css/hedgehog.css in container")
            print("   3. Run: python manage.py collectstatic --no-input")
            return False
            
        containers = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
        netbox_containers = [c for c in containers if 'netbox' in c.lower()]
        
        if not netbox_containers:
            print("⚠️  No NetBox containers found running")
            print("   Available containers:")
            all_containers = subprocess.run(
                ["docker", "ps", "--format", "{{.Names}}"],
                capture_output=True,
                text=True
            )
            if all_containers.returncode == 0:
                for container in all_containers.stdout.strip().split('\n'):
                    if container.strip():
                        print(f"     - {container.strip()}")
            return False
            
        container_name = netbox_containers[0]
        print(f"✅ Found NetBox container: {container_name}")
        
        # Create target directory in container if it doesn't exist
        print("\n📁 Ensuring target directory exists in container...")
        mkdir_result = subprocess.run(
            ["docker", "exec", container_name, "mkdir", "-p", "/opt/netbox/netbox/static/netbox_hedgehog/css"],
            capture_output=True,
            text=True
        )
        
        if mkdir_result.returncode == 0:
            print("✅ Target directory ready")
        else:
            print("⚠️  Could not create directory, trying to copy anyway...")
        
        # Copy CSS file to container
        print("\n📋 Copying CSS file to container...")
        css_dest = f"{container_name}:/opt/netbox/netbox/static/netbox_hedgehog/css/hedgehog.css"
        
        copy_result = subprocess.run(
            ["docker", "cp", str(css_file), css_dest],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if copy_result.returncode != 0:
            print("❌ Failed to copy CSS file:")
            print(f"   Error: {copy_result.stderr}")
            return False
            
        print("✅ CSS file copied successfully")
        
        # Verify file was copied
        print("\n🔍 Verifying file in container...")
        verify_result = subprocess.run(
            ["docker", "exec", container_name, "ls", "-la", "/opt/netbox/netbox/static/netbox_hedgehog/css/hedgehog.css"],
            capture_output=True,
            text=True
        )
        
        if verify_result.returncode == 0:
            print("✅ File verified in container:")
            print(f"   {verify_result.stdout.strip()}")
        else:
            print("⚠️  Could not verify file, but copy may have succeeded")
        
        # Collect static files
        print("\n📦 Collecting static files...")
        collectstatic_result = subprocess.run(
            ["docker", "exec", container_name, "python", "/opt/netbox/netbox/manage.py", "collectstatic", "--no-input"],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if collectstatic_result.returncode == 0:
            print("✅ Static files collected successfully")
            print("   CSS changes should now be active in NetBox")
            
            # Show relevant output
            if collectstatic_result.stdout:
                lines = collectstatic_result.stdout.strip().split('\n')
                relevant_lines = [line for line in lines if 'hedgehog' in line.lower() or 'copied' in line.lower() or 'static' in line.lower()]
                if relevant_lines:
                    print("   Relevant output:")
                    for line in relevant_lines[-5:]:  # Show last 5 relevant lines
                        print(f"     {line}")
        else:
            print("⚠️  Static file collection had issues:")
            print(f"   Error: {collectstatic_result.stderr}")
            print("   However, CSS file was copied and may still work")
            
        # Final verification - check if file exists in collected static files
        print("\n🔍 Final verification...")
        final_check = subprocess.run(
            ["docker", "exec", container_name, "find", "/opt/netbox", "-name", "hedgehog.css", "-type", "f"],
            capture_output=True,
            text=True
        )
        
        if final_check.returncode == 0 and final_check.stdout.strip():
            print("✅ Final verification successful:")
            for path in final_check.stdout.strip().split('\n'):
                if path.strip():
                    print(f"   Found: {path.strip()}")
        else:
            print("⚠️  Final verification inconclusive")
            
        print("\n" + "=" * 60)
        print("✅ DEPLOYMENT COMPLETED")
        print("=" * 60)
        print("Next steps:")
        print("1. Refresh NetBox web page (Ctrl+F5 to force refresh)")
        print("2. Check fabric detail pages for improved badge readability")
        print("3. Verify no localhost URLs are displayed")
        print("4. Confirm error counts display without server errors")
        
        return True
        
    except subprocess.TimeoutExpired:
        print("❌ Docker command timed out")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    success = deploy_css_to_container()
    if success:
        print("\n✅ Deployment successful!")
        sys.exit(0)
    else:
        print("\n⚠️  Deployment had issues - manual intervention may be required")
        sys.exit(1)