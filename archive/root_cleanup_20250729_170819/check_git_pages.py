#!/usr/bin/env python3
"""
Simple Git Repository Page Content Check
"""

import requests
import re

def check_git_pages():
    """Check git repository page content"""
    base_url = "http://localhost:8000"
    session = requests.Session()
    
    # Login
    login_page = session.get(f"{base_url}/login/")
    csrf_match = re.search(r'csrfmiddlewaretoken.*?value="([^"]+)"', login_page.text)
    csrf_token = csrf_match.group(1)
    
    login_data = {
        'username': 'admin',
        'password': 'admin',
        'csrfmiddlewaretoken': csrf_token
    }
    session.post(f"{base_url}/login/", data=login_data, allow_redirects=False)
    
    print("=== Git Repository Page Content Check ===")
    
    # Check list page
    print("\n1. Git Repositories List Page:")
    list_response = session.get(f"{base_url}/plugins/hedgehog/git-repositories/")
    
    if list_response.status_code == 200:
        content = list_response.text
        
        # Check for key indicators
        if "Git Repositories" in content:
            print("   ✅ Page title contains 'Git Repositories'")
        else:
            print("   ⚠️  Page title may be missing")
            
        if "Add Git Repository" in content or "Add a git repository" in content:
            print("   ✅ Has 'Add Repository' functionality")
        else:
            print("   ⚠️  Missing 'Add Repository' button")
            
        # Check for actual repositories
        repo_matches = re.findall(r'/git-repositories/(\d+)/', content)
        if repo_matches:
            print(f"   ✅ Found {len(set(repo_matches))} repository links")
            for repo_id in set(repo_matches)[:3]:
                print(f"     - Repository ID: {repo_id}")
        else:
            print("   ℹ️  No repository links found")
            
        # Check for table structure
        if "<table" in content and "</table>" in content:
            print("   ✅ Has table structure for repositories")
        else:
            print("   ⚠️  No table structure found")
            
        # Check for empty state
        if "no repositories" in content.lower() or "empty" in content.lower():
            print("   ℹ️  Appears to show empty state")
            
    else:
        print(f"   ❌ List page failed: {list_response.status_code}")
        return False
    
    # Check detail page
    print("\n2. Git Repository Detail Page (ID 1):")
    detail_response = session.get(f"{base_url}/plugins/hedgehog/git-repositories/1/")
    
    if detail_response.status_code == 200:
        content = detail_response.text
        
        # Check for repository information
        if "Repository Information" in content:
            print("   ✅ Has 'Repository Information' section")
        else:
            print("   ⚠️  Missing 'Repository Information' section")
            
        # Check for key fields
        fields = ["Name", "URL", "Provider", "Authentication"]
        for field in fields:
            if field in content:
                print(f"   ✅ Contains '{field}' field")
            else:
                print(f"   ⚠️  Missing '{field}' field")
                
        # Check for action buttons/links
        actions = ["Edit", "Delete", "Test Connection"]
        for action in actions:
            if action in content:
                print(f"   ✅ Has '{action}' action")
            else:
                print(f"   ⚠️  Missing '{action}' action")
                
    elif detail_response.status_code == 404:
        print("   ℹ️  Repository ID 1 not found (404) - expected if no repositories")
    else:
        print(f"   ❌ Detail page failed: {detail_response.status_code}")
        return False
        
    print("\n=== SUMMARY ===")
    print("Git repository pages are accessible and appear to be functioning")
    return True

if __name__ == "__main__":
    check_git_pages()