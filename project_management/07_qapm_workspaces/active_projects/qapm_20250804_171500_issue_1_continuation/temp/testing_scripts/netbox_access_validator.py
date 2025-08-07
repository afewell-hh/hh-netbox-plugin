#!/usr/bin/env python3
"""
NetBox Access Validator
Simple tool to test NetBox accessibility and authentication
"""

import requests
import json

def test_netbox_access():
    """Test basic NetBox access and look for fabric information."""
    session = requests.Session()
    base_url = "http://localhost:8000"
    
    print("Testing NetBox accessibility...")
    
    # Test basic access
    try:
        response = session.get(base_url)
        print(f"Base URL response: {response.status_code}")
        print(f"Final URL after redirects: {response.url}")
        
        # Try to access login page
        login_response = session.get(f"{base_url}/login/")
        print(f"Login page response: {login_response.status_code}")
        
        # Try to access plugins page
        plugins_response = session.get(f"{base_url}/plugins/")
        print(f"Plugins page response: {plugins_response.status_code}")
        
        # Try to access hedgehog plugin
        hedgehog_response = session.get(f"{base_url}/plugins/hedgehog/")
        print(f"Hedgehog plugin response: {hedgehog_response.status_code}")
        
        # Try to access fabrics
        fabrics_response = session.get(f"{base_url}/plugins/hedgehog/fabrics/")
        print(f"Fabrics page response: {fabrics_response.status_code}")
        
        if fabrics_response.status_code == 302:
            print("Fabrics page redirects - probably requires authentication")
        elif fabrics_response.status_code == 200:
            print("Fabrics page accessible - checking for fabric data...")
            if 'fabric' in fabrics_response.text.lower():
                print("✅ Fabric data found in response")
            
    except Exception as e:
        print(f"Error testing NetBox access: {e}")

def test_management_commands():
    """Test if Django management commands are available."""
    import os
    os.chdir("/home/ubuntu/cc/hedgehog-netbox-plugin")
    
    print("\nTesting Django management commands...")
    
    # Test basic manage.py access
    import subprocess
    
    try:
        result = subprocess.run(["python", "manage.py", "help"], 
                              capture_output=True, text=True, timeout=10)
        print(f"manage.py help: {result.returncode}")
        if result.returncode == 0:
            print("✅ Django management available")
            
            # Look for custom commands
            if 'sync_fabric' in result.stdout:
                print("✅ sync_fabric command found")
            if 'ingest_raw_files' in result.stdout:
                print("✅ ingest_raw_files command found")
                
        else:
            print(f"❌ Django management error: {result.stderr}")
            
    except Exception as e:
        print(f"Error testing management commands: {e}")

if __name__ == "__main__":
    test_netbox_access()
    test_management_commands()