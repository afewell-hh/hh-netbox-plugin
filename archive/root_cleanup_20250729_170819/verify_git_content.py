#!/usr/bin/env python3
"""
Git Repository Content Verification
Get actual page content to verify functionality
"""

import requests
import re
from bs4 import BeautifulSoup

def verify_git_repository_content():
    """Verify actual content of git repository pages"""
    base_url = "http://localhost:8000"
    
    # Create session and login
    session = requests.Session()
    
    # Get login page and CSRF token
    login_page = session.get(f"{base_url}/login/")
    csrf_match = re.search(r'csrfmiddlewaretoken.*?value="([^"]+)"', login_page.text)
    csrf_token = csrf_match.group(1)
    
    # Login
    login_data = {
        'username': 'admin',
        'password': 'admin',
        'csrfmiddlewaretoken': csrf_token
    }
    session.post(f"{base_url}/login/", data=login_data, allow_redirects=False)
    
    print("=== Git Repository Content Verification ===")
    
    # Test list page content
    print("\n1. Git Repositories List Page Content:")
    list_response = session.get(f"{base_url}/plugins/hedgehog/git-repositories/")
    
    if list_response.status_code == 200:
        soup = BeautifulSoup(list_response.text, 'html.parser')
        
        # Check page title
        title = soup.find('title')
        print(f"   Page Title: {title.text if title else 'Not found'}")
        
        # Check for main heading
        h1 = soup.find('h1') or soup.find('h2') or soup.find('h3')
        print(f"   Main Heading: {h1.text.strip() if h1 else 'Not found'}")
        
        # Check for table or repository content
        table = soup.find('table')
        if table:
            rows = table.find_all('tr')
            print(f"   Table found with {len(rows)} rows")
            
            # Check for repository entries
            repo_links = soup.find_all('a', href=re.compile(r'/git-repositories/\d+/'))
            print(f"   Repository links found: {len(repo_links)}")
            
            for i, link in enumerate(repo_links[:3]):  # Show first 3
                print(f"     - Repository {i+1}: {link.text.strip()}")
        else:
            print("   No table found - checking for other repository content...")
            
            # Look for "no repositories" message
            if "no repositories" in list_response.text.lower():
                print("   ✅ Page shows 'no repositories' message")
            else:
                print("   ⚠️  No clear repository content or 'no repositories' message")
    
    # Test detail page content
    print("\n2. Git Repository Detail Page Content (ID 1):")
    detail_response = session.get(f"{base_url}/plugins/hedgehog/git-repositories/1/")
    
    if detail_response.status_code == 200:
        soup = BeautifulSoup(detail_response.text, 'html.parser')
        
        # Check page title
        title = soup.find('title')
        print(f"   Page Title: {title.text if title else 'Not found'}")
        
        # Check for repository information
        info_cards = soup.find_all('div', class_='card')
        print(f"   Information cards found: {len(info_cards)}")
        
        # Look for repository details
        repo_info = soup.find(text=re.compile(r'Repository Information'))
        if repo_info:
            print("   ✅ Found 'Repository Information' section")
        
        # Check for specific fields
        fields_to_check = ['Name', 'URL', 'Provider', 'Authentication Type']
        for field in fields_to_check:
            field_element = soup.find(text=re.compile(field))
            if field_element:
                print(f"   ✅ Found '{field}' field")
            else:
                print(f"   ⚠️  Missing '{field}' field")
                
        # Check for action buttons
        buttons = soup.find_all('a', class_='btn') + soup.find_all('button', class_='btn')
        print(f"   Action buttons found: {len(buttons)}")
        
        for button in buttons[:3]:  # Show first 3
            button_text = button.text.strip()
            if button_text:
                print(f"     - Button: {button_text}")
                
    elif detail_response.status_code == 404:
        print("   Repository ID 1 not found (404) - this may be expected if no repositories exist")
    else:
        print(f"   Error loading detail page: {detail_response.status_code}")
    
    print("\n=== CONTENT VERIFICATION COMPLETE ===")

if __name__ == "__main__":
    verify_git_repository_content()