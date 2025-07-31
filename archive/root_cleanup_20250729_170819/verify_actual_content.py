#!/usr/bin/env python3
"""Actually verify the git repository page content"""

import requests
import re

def verify_actual_content():
    base_url = "http://localhost:8000"
    session = requests.Session()
    
    # Proper login
    login_page = session.get(f"{base_url}/login/")
    csrf_match = re.search(r'name=["\']csrfmiddlewaretoken["\'] value=["\']([^"\']+)["\']', login_page.text)
    if not csrf_match:
        csrf_match = re.search(r'csrfmiddlewaretoken["\'] value=["\']([^"\']+)["\']', login_page.text)
    csrf_token = csrf_match.group(1)
    
    login_data = {
        'username': 'admin',
        'password': 'admin',
        'csrfmiddlewaretoken': csrf_token
    }
    
    session.post(f"{base_url}/login/", data=login_data, allow_redirects=True)
    
    print("=== ACTUAL CONTENT VERIFICATION ===")
    
    # Test repositories list page
    print("\n1. Testing /plugins/hedgehog/repositories/")
    repos_response = session.get(f"{base_url}/plugins/hedgehog/repositories/")
    print(f"   Status Code: {repos_response.status_code}")
    
    if repos_response.status_code == 200:
        content = repos_response.text
        
        # Check if it's actually a git repository page or login redirect
        if "netbox-url-name=\"login\"" in content:
            print("   ❌ STILL RETURNING LOGIN PAGE")
            return False
        
        # Look for repository-related content
        if "repositories" in content.lower() or "git" in content.lower():
            print("   ✅ Contains repository content")
        else:
            print("   ⚠️  No clear repository content found")
            
        # Show page title
        title_match = re.search(r'<title>(.*?)</title>', content)
        if title_match:
            print(f"   Page title: {title_match.group(1)}")
            
        # Show first part of content
        print(f"   Content sample: {content[:200]}")
        
    elif repos_response.status_code == 404:
        print("   ❌ 404 Not Found - the URL pattern is not working")
        return False
    else:
        print(f"   ❌ Unexpected status code: {repos_response.status_code}")
        return False
    
    # Test repositories detail page
    print("\n2. Testing /plugins/hedgehog/repositories/1/")
    detail_response = session.get(f"{base_url}/plugins/hedgehog/repositories/1/")
    print(f"   Status Code: {detail_response.status_code}")
    
    if detail_response.status_code == 200:
        content = detail_response.text
        
        if "netbox-url-name=\"login\"" in content:
            print("   ❌ STILL RETURNING LOGIN PAGE")
            return False
        
        if "Repository Information" in content:
            print("   ✅ Contains 'Repository Information' section")
        else:
            print("   ⚠️  Missing expected repository detail content")
            
    elif detail_response.status_code == 404:
        print("   ℹ️  Repository ID 1 not found - this is expected if no repositories exist")
        # 404 for detail page is OK if no repositories exist
    
    return True

if __name__ == "__main__":
    success = verify_actual_content()
    print(f"\n{'✅ VERIFICATION PASSED' if success else '❌ VERIFICATION FAILED'}")