#!/usr/bin/env python3
"""
Simple GUI check for sync status display
Uses requests to validate HTML output
"""

import requests
from bs4 import BeautifulSoup


def test_fabric_status_display():
    """Test fabric status display via HTML parsing"""
    
    print("=" * 80)
    print("SIMPLE GUI STATUS CHECK - Issue #40")
    print("=" * 80)
    
    # Setup session
    session = requests.Session()
    
    # Get login page first for CSRF token
    login_page = session.get("http://localhost:8000/login/")
    soup = BeautifulSoup(login_page.content, 'html.parser')
    csrf_token = soup.find('input', {'name': 'csrfmiddlewaretoken'})['value']
    
    # Login
    login_data = {
        'username': 'admin',
        'password': 'admin',
        'csrfmiddlewaretoken': csrf_token
    }
    
    session.post("http://localhost:8000/login/", data=login_data)
    
    # Get fabrics list
    fabrics_page = session.get("http://localhost:8000/plugins/hedgehog/fabrics/")
    if fabrics_page.status_code != 200:
        print(f"❌ Could not access fabrics page: {fabrics_page.status_code}")
        return False
    
    soup = BeautifulSoup(fabrics_page.content, 'html.parser')
    fabric_links = soup.find_all('a', href=lambda x: x and '/fabrics/' in x and x.endswith('/'))
    
    print(f"Found {len(fabric_links)} fabric(s)")
    
    if not fabric_links:
        print("No fabrics found")
        return False
    
    # Check first fabric detail page
    fabric_url = fabric_links[0]['href']
    print(f"Checking fabric: {fabric_url}")
    
    fabric_page = session.get(f"http://localhost:8000{fabric_url}")
    
    if fabric_page.status_code != 200:
        print(f"❌ Could not access fabric page: {fabric_page.status_code}")
        return False
    
    soup = BeautifulSoup(fabric_page.content, 'html.parser')
    
    # Look for status indicators
    status_found = False
    
    # Check for various status displays
    status_elements = [
        soup.find_all('span', class_='badge'),
        soup.find_all('div', class_='status-indicator'),
        soup.find_all('td', string=lambda x: x and any(s in str(x) for s in ['Not Configured', 'Never Synced', 'In Sync', 'Out of Sync', 'Disabled'])),
    ]
    
    for element_list in status_elements:
        for element in element_list:
            text = element.get_text().strip()
            if any(status in text for status in ['Not Configured', 'Never Synced', 'In Sync', 'Out of Sync', 'Disabled']):
                print(f"✅ Found status display: '{text}'")
                print(f"   Element: {element.name} with class='{element.get('class')}'")
                status_found = True
                break
        if status_found:
            break
    
    if not status_found:
        print("❌ No sync status display found")
        
        # Debug: Show some page content
        print("\\nDebug - looking for sync-related content:")
        page_text = soup.get_text()
        sync_lines = [line.strip() for line in page_text.split('\\n') if 'sync' in line.lower() or 'status' in line.lower()]
        for line in sync_lines[:10]:
            if line:
                print(f"  {line}")
        
        return False
    
    # Check for Kubernetes configuration display
    k8s_found = False
    k8s_text = ""
    
    # Look for Kubernetes server display
    th_elements = soup.find_all('th')
    for th in th_elements:
        if 'kubernetes' in th.get_text().lower() and 'server' in th.get_text().lower():
            td = th.find_next_sibling('td')
            if td:
                k8s_text = td.get_text().strip()
                k8s_found = True
                print(f"✅ Found K8s config: '{k8s_text}'")
                break
    
    if not k8s_found:
        print("⚠️  Kubernetes configuration display not found")
    
    print("\\n✅ Basic GUI status display validation complete")
    return True


if __name__ == "__main__":
    success = test_fabric_status_display()
    exit(0 if success else 1)