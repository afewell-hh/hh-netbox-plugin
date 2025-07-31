#!/usr/bin/env python3
"""Verify NetBox restart and test various URLs"""

import requests
import re

def verify_restart():
    base_url = "http://localhost:8000"
    session = requests.Session()
    
    # Login
    print("=== POST-RESTART VERIFICATION ===")
    login_page = session.get(f"{base_url}/login/")
    csrf_match = re.search(r'name=["\']csrfmiddlewaretoken["\'] value=["\']([^"\']+)["\']', login_page.text)
    csrf_token = csrf_match.group(1)
    
    login_data = {
        'username': 'admin',
        'password': 'admin',
        'csrfmiddlewaretoken': csrf_token
    }
    
    session.post(f"{base_url}/login/", data=login_data, allow_redirects=True)
    
    # Test basic functionality
    test_urls = [
        ("", "Plugin overview"),
        ("fabrics/", "Fabrics (known working)"),
        ("vpcs/", "VPCs (known working)"),
        ("git-management/", "Git management (new URL)"),
        ("git-repos/", "Git repos (alternative URL)"),
        ("git-repositories/", "Git repositories (original problematic URL)"),
    ]
    
    print("\nTesting URLs after restart:")
    for url, desc in test_urls:
        full_url = f"{base_url}/plugins/hedgehog/{url}"
        response = session.get(full_url)
        
        if response.status_code == 200:
            is_login = "netbox-url-name=\"login\"" in response.text
            status = "LOGIN PAGE" if is_login else "CONTENT"
        else:
            status = str(response.status_code)
            
        print(f"   {desc:35} {status}")
        
    return True

if __name__ == "__main__":
    verify_restart()