#!/usr/bin/env python3
"""
Capture the exact sync error by simulating user clicking sync button
"""

import requests
import sys
import json
from bs4 import BeautifulSoup

def capture_sync_error():
    """Capture the exact error message from sync button click"""
    
    # Session to maintain cookies
    session = requests.Session()
    
    # Base URL
    base_url = "http://localhost:8000"
    login_url = f"{base_url}/login/"
    fabric_url = f"{base_url}/plugins/hedgehog/fabrics/35/"
    sync_url = f"{base_url}/plugins/hedgehog/fabrics/35/sync/"
    
    print("🔍 CAPTURING SYNC ERROR MESSAGE")
    print("=" * 50)
    
    try:
        # Step 1: Get login page
        print("1. Getting login page...")
        login_page = session.get(login_url)
        soup = BeautifulSoup(login_page.text, 'html.parser')
        csrf_token = soup.find('input', {'name': 'csrfmiddlewaretoken'})['value']
        print(f"   CSRF token: {csrf_token[:20]}...")
        
        # Step 2: Login (assuming admin/admin)
        print("2. Logging in...")
        login_data = {
            'username': 'admin',
            'password': 'admin',
            'csrfmiddlewaretoken': csrf_token,
            'next': fabric_url
        }
        
        login_response = session.post(login_url, data=login_data)
        if login_response.status_code != 200:
            print(f"   Login failed: {login_response.status_code}")
            return None
            
        print("   Login successful")
        
        # Step 3: Get fabric page
        print("3. Getting fabric page...")
        fabric_response = session.get(fabric_url)
        if fabric_response.status_code != 200:
            print(f"   Failed to get fabric page: {fabric_response.status_code}")
            return None
            
        print("   Fabric page loaded")
        
        # Step 4: Get fresh CSRF token from fabric page
        soup = BeautifulSoup(fabric_response.text, 'html.parser')
        csrf_token = soup.find('input', {'name': 'csrfmiddlewaretoken'})
        if csrf_token:
            csrf_token = csrf_token['value']
        else:
            # Try to find it in script tag or meta tag
            meta_csrf = soup.find('meta', {'name': 'csrf-token'})
            if meta_csrf:
                csrf_token = meta_csrf.get('content')
            else:
                print("   Warning: No CSRF token found on fabric page")
                csrf_token = ""
        
        print(f"   Fresh CSRF token: {csrf_token[:20]}..." if csrf_token else "   No CSRF token")
        
        # Step 5: Attempt sync (POST request)
        print("4. Attempting sync...")
        headers = {
            'X-CSRFToken': csrf_token,
            'Referer': fabric_url,
            'X-Requested-With': 'XMLHttpRequest',  # AJAX request
        }
        
        sync_response = session.post(sync_url, headers=headers)
        
        print(f"   Sync response status: {sync_response.status_code}")
        print(f"   Sync response headers: {dict(sync_response.headers)}")
        print(f"   Sync response content length: {len(sync_response.text)}")
        
        # Step 6: Analyze the response
        if sync_response.status_code == 200:
            try:
                json_response = sync_response.json()
                print("   ✅ JSON Response:")
                print(f"   {json.dumps(json_response, indent=4)}")
                return json_response
            except:
                print("   📄 HTML Response:")
                print(f"   {sync_response.text[:500]}...")
                return sync_response.text
                
        elif sync_response.status_code == 403:
            print("   ❌ 403 Forbidden - CSRF or Authentication issue")
            print(f"   Response: {sync_response.text[:200]}...")
            return {"error": "403 Forbidden", "response": sync_response.text}
            
        elif sync_response.status_code == 302:
            print("   🔄 302 Redirect")
            print(f"   Location: {sync_response.headers.get('Location')}")
            return {"error": "302 Redirect", "location": sync_response.headers.get('Location')}
            
        else:
            print(f"   ❌ Unexpected status: {sync_response.status_code}")
            print(f"   Response: {sync_response.text[:200]}...")
            return {"error": f"Status {sync_response.status_code}", "response": sync_response.text}
    
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return {"error": str(e)}

if __name__ == "__main__":
    result = capture_sync_error()
    
    # Save result to file
    timestamp = "20250811_215900"
    filename = f"sync_error_capture_{timestamp}.json"
    
    with open(filename, 'w') as f:
        json.dump({
            "timestamp": timestamp,
            "result": result,
            "analysis": "Captured sync error attempt"
        }, f, indent=2, default=str)
    
    print(f"\n💾 Results saved to: {filename}")