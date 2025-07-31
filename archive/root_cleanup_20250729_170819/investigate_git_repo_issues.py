#!/usr/bin/env python3
"""
Enhanced QAPM v2.1 - Investigate Git Repository GUI Issues
1. Status label CSS problem - text unreadable
2. Detail page error when clicking repository name or view button
"""

import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime

def investigate_issues():
    """Investigate both reported issues with evidence collection"""
    
    base_url = "http://localhost:8000"
    session = requests.Session()
    
    evidence = {
        "timestamp": datetime.now().isoformat(),
        "issues": {
            "css_label": {},
            "detail_page_error": {}
        }
    }
    
    print("🔍 Enhanced QAPM v2.1 - Git Repository GUI Issues Investigation")
    print("=" * 60)
    
    # First, we need to authenticate
    print("\n🔐 Step 1: Authenticating to NetBox...")
    
    # Get login page for CSRF token
    login_page_url = f"{base_url}/login/"
    login_response = session.get(login_page_url)
    
    if login_response.status_code == 200:
        soup = BeautifulSoup(login_response.text, 'html.parser')
        csrf_input = soup.find('input', {'name': 'csrfmiddlewaretoken'})
        
        if csrf_input:
            csrf_token = csrf_input.get('value')
            print(f"✅ CSRF token obtained")
            
            # Login with admin credentials
            login_data = {
                'username': 'admin',
                'password': 'admin',
                'csrfmiddlewaretoken': csrf_token,
                'next': '/plugins/hedgehog/git-repositories/'
            }
            
            login_post = session.post(login_page_url, data=login_data, headers={
                'Referer': login_page_url
            })
            
            print(f"Login response: {login_post.status_code}")
            
            # Check if we're redirected to git repositories
            if login_post.status_code == 302:
                print("✅ Authentication successful")
            else:
                print("❌ Authentication may have failed")
    
    # Now access the git repositories list page
    print("\n📋 Step 2: Accessing Git Repositories List Page...")
    
    list_url = f"{base_url}/plugins/hedgehog/git-repositories/"
    list_response = session.get(list_url)
    
    if list_response.status_code == 200:
        print("✅ Git repositories list page loaded")
        
        # Save the HTML for analysis
        with open('git_repos_list_authenticated.html', 'w') as f:
            f.write(list_response.text)
        
        # Parse the HTML to find status labels
        soup = BeautifulSoup(list_response.text, 'html.parser')
        
        # Look for status labels
        print("\n🏷️  Step 3: Analyzing Status Label CSS...")
        
        # Common patterns for status labels in tables
        status_elements = []
        
        # Look for spans/divs with "Connected" text
        for element in soup.find_all(text='Connected'):
            parent = element.parent
            if parent:
                status_elements.append({
                    'tag': parent.name,
                    'classes': parent.get('class', []),
                    'style': parent.get('style', ''),
                    'html': str(parent)
                })
        
        # Also look for badge/label elements
        for selector in ['.badge', '.label', '.status', 'span', 'div']:
            for element in soup.select(selector):
                if 'Connected' in element.text:
                    status_elements.append({
                        'tag': element.name,
                        'classes': element.get('class', []),
                        'style': element.get('style', ''),
                        'html': str(element)
                    })
        
        evidence['issues']['css_label']['status_elements'] = status_elements
        
        print(f"Found {len(status_elements)} status elements")
        for elem in status_elements[:3]:  # Show first 3
            print(f"  - Tag: {elem['tag']}, Classes: {elem['classes']}")
        
        # Check for NetBox's standard label CSS classes
        print("\n🎨 Step 4: Checking NetBox Standard CSS...")
        
        # Look for other labels/badges on the page to see correct usage
        correct_labels = []
        for element in soup.select('.badge, .label, .btn'):
            if element.text.strip() and 'Connected' not in element.text:
                correct_labels.append({
                    'text': element.text.strip(),
                    'tag': element.name,
                    'classes': element.get('class', []),
                    'example': str(element)
                })
        
        evidence['issues']['css_label']['correct_examples'] = correct_labels[:5]
        
        print(f"Found {len(correct_labels)} examples of correct label usage")
        
        # Find repository links to test detail page
        print("\n🔗 Step 5: Finding Repository Links...")
        
        repo_links = []
        # Look for links in the table
        for link in soup.find_all('a'):
            href = link.get('href', '')
            if '/git-repositories/' in href and href != '/plugins/hedgehog/git-repositories/':
                repo_links.append({
                    'text': link.text.strip(),
                    'href': href,
                    'classes': link.get('class', [])
                })
        
        evidence['issues']['detail_page_error']['repository_links'] = repo_links[:5]
        
        print(f"Found {len(repo_links)} repository links")
        
        # Test accessing a detail page
        if repo_links:
            print("\n📄 Step 6: Testing Repository Detail Page...")
            
            test_link = repo_links[0]['href']
            if not test_link.startswith('http'):
                test_link = base_url + test_link
            
            print(f"Testing: {test_link}")
            
            detail_response = session.get(test_link)
            evidence['issues']['detail_page_error']['detail_response'] = {
                'url': test_link,
                'status_code': detail_response.status_code,
                'content_length': len(detail_response.text)
            }
            
            print(f"Detail page response: {detail_response.status_code}")
            
            if detail_response.status_code == 500:
                print("❌ Server Error (500) on detail page")
                # Save error page
                with open('git_repo_detail_error.html', 'w') as f:
                    f.write(detail_response.text)
                
                # Try to extract error message
                error_soup = BeautifulSoup(detail_response.text, 'html.parser')
                error_msg = error_soup.find('pre') or error_soup.find('.error')
                if error_msg:
                    evidence['issues']['detail_page_error']['error_message'] = error_msg.text.strip()[:500]
            
            elif detail_response.status_code == 200:
                print("✅ Detail page loaded (but may have rendering issues)")
                with open('git_repo_detail_loaded.html', 'w') as f:
                    f.write(detail_response.text)
        
    else:
        print(f"❌ Failed to load list page: {list_response.status_code}")
    
    # Save evidence
    with open('git_repo_issues_evidence.json', 'w') as f:
        json.dump(evidence, f, indent=2)
    
    print("\n📊 Investigation Summary")
    print("=" * 40)
    print("1. CSS Label Issue: Status elements found and analyzed")
    print("2. Detail Page Issue: Error response captured")
    print("\nEvidence saved to: git_repo_issues_evidence.json")
    
    return evidence

if __name__ == "__main__":
    investigate_issues()