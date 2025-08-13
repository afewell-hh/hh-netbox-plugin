#!/usr/bin/env python3
"""
Validate the session timeout hypothesis for sync failure
"""

import requests
import json
import time
from bs4 import BeautifulSoup
from datetime import datetime

def test_session_timeout_pattern():
    """Test if sync failure is due to session timeout"""
    
    print("🔬 VALIDATING SESSION TIMEOUT HYPOTHESIS")
    print("=" * 60)
    
    session = requests.Session()
    base_url = "http://localhost:8000"
    login_url = f"{base_url}/login/"
    fabric_url = f"{base_url}/plugins/hedgehog/fabrics/35/"
    sync_url = f"{base_url}/plugins/hedgehog/fabrics/35/sync/"
    
    results = {
        "hypothesis": "sync_failure_due_to_session_timeout",
        "tests": [],
        "conclusion": None
    }
    
    try:
        # Test 1: Login and immediate sync (should work)
        print("\n🔵 TEST 1: Login and immediate sync")
        
        # Login
        login_page = session.get(login_url)
        soup = BeautifulSoup(login_page.text, 'html.parser')
        csrf_token = soup.find('input', {'name': 'csrfmiddlewaretoken'})['value']
        
        login_data = {
            'username': 'admin',
            'password': 'admin',
            'csrfmiddlewaretoken': csrf_token
        }
        
        login_response = session.post(login_url, data=login_data)
        print(f"   Login status: {login_response.status_code}")
        
        # Immediate sync attempt
        fabric_response = session.get(fabric_url)
        soup = BeautifulSoup(fabric_response.text, 'html.parser')
        csrf_token = soup.find('input', {'name': 'csrfmiddlewaretoken'})
        if csrf_token:
            csrf_token = csrf_token['value']
        else:
            csrf_token = ""
        
        headers = {'X-CSRFToken': csrf_token, 'Referer': fabric_url}
        sync_response = session.post(sync_url, headers=headers)
        
        test1_result = {
            "test": "immediate_sync_after_login",
            "login_status": login_response.status_code,
            "sync_status": sync_response.status_code,
            "sync_content_length": len(sync_response.text),
            "is_html_response": sync_response.text.strip().startswith('<!DOCTYPE html>'),
            "timestamp": datetime.now().isoformat()
        }
        
        results["tests"].append(test1_result)
        
        print(f"   Sync status: {sync_response.status_code}")
        print(f"   Response length: {len(sync_response.text)}")
        print(f"   Is HTML: {sync_response.text.strip().startswith('<!DOCTYPE html>')}")
        
        # Test 2: Check if session is still valid
        print("\n🟡 TEST 2: Session validity check")
        
        # Try to access fabric page again
        fabric_check = session.get(fabric_url)
        is_logged_in = "Log In" not in fabric_check.text and fabric_check.status_code == 200
        
        test2_result = {
            "test": "session_validity_check",
            "fabric_status": fabric_check.status_code,
            "is_logged_in": is_logged_in,
            "timestamp": datetime.now().isoformat()
        }
        
        results["tests"].append(test2_result)
        
        print(f"   Fabric page status: {fabric_check.status_code}")
        print(f"   Still logged in: {is_logged_in}")
        
        # Test 3: Another sync attempt (should work if session valid)
        print("\n🟢 TEST 3: Second sync attempt")
        
        # Get fresh CSRF
        soup = BeautifulSoup(fabric_check.text, 'html.parser')
        csrf_token = soup.find('input', {'name': 'csrfmiddlewaretoken'})
        if csrf_token:
            csrf_token = csrf_token['value']
        else:
            csrf_token = ""
        
        headers = {'X-CSRFToken': csrf_token, 'Referer': fabric_url}
        sync_response2 = session.post(sync_url, headers=headers)
        
        test3_result = {
            "test": "second_sync_attempt",
            "sync_status": sync_response2.status_code,
            "sync_content_length": len(sync_response2.text),
            "is_html_response": sync_response2.text.strip().startswith('<!DOCTYPE html>'),
            "has_login_form": "Log In" in sync_response2.text,
            "timestamp": datetime.now().isoformat()
        }
        
        results["tests"].append(test3_result)
        
        print(f"   Second sync status: {sync_response2.status_code}")
        print(f"   Response length: {len(sync_response2.text)}")
        print(f"   Is HTML: {sync_response2.text.strip().startswith('<!DOCTYPE html>')}")
        print(f"   Has login form: {'Log In' in sync_response2.text}")
        
        # Test 4: Examine session cookies
        print("\n🔍 TEST 4: Session cookie analysis")
        
        cookies_info = []
        for cookie in session.cookies:
            cookies_info.append({
                "name": cookie.name,
                "value": cookie.value[:20] + "..." if len(cookie.value) > 20 else cookie.value,
                "domain": cookie.domain,
                "path": cookie.path,
                "expires": cookie.expires
            })
        
        test4_result = {
            "test": "session_cookie_analysis", 
            "cookies_count": len(session.cookies),
            "cookies": cookies_info,
            "has_sessionid": any(c.name == 'sessionid' for c in session.cookies),
            "has_csrftoken": any(c.name == 'csrftoken' for c in session.cookies),
            "timestamp": datetime.now().isoformat()
        }
        
        results["tests"].append(test4_result)
        
        print(f"   Cookie count: {len(session.cookies)}")
        print(f"   Has sessionid: {any(c.name == 'sessionid' for c in session.cookies)}")
        print(f"   Has csrftoken: {any(c.name == 'csrftoken' for c in session.cookies)}")
        
        # Analyze results
        print("\n🧠 ANALYSIS")
        print("-" * 40)
        
        # Check if both syncs worked
        sync1_worked = (test1_result["sync_status"] == 200 and 
                       not test1_result["is_html_response"] and
                       test1_result["sync_content_length"] < 1000)
        
        sync2_worked = (test3_result["sync_status"] == 200 and 
                       not test3_result["is_html_response"] and
                       test3_result["sync_content_length"] < 1000)
        
        print(f"   First sync worked: {sync1_worked}")
        print(f"   Second sync worked: {sync2_worked}")
        print(f"   Session valid: {is_logged_in}")
        
        if sync1_worked and sync2_worked and is_logged_in:
            results["conclusion"] = "HYPOTHESIS_REJECTED: Both syncs worked, no session timeout issue"
        elif not sync1_worked and test1_result["is_html_response"]:
            results["conclusion"] = "HYPOTHESIS_CONFIRMED: First sync failed due to auth redirect"
        elif sync1_worked and not sync2_worked and test3_result["is_html_response"]:
            results["conclusion"] = "HYPOTHESIS_CONFIRMED: Session expired between syncs"
        elif not is_logged_in:
            results["conclusion"] = "HYPOTHESIS_CONFIRMED: Session timeout detected"
        else:
            results["conclusion"] = "INCONCLUSIVE: Mixed results require further investigation"
            
        print(f"\n🎯 CONCLUSION: {results['conclusion']}")
        
    except Exception as e:
        results["error"] = str(e)
        results["conclusion"] = f"TEST_ERROR: {e}"
        print(f"\n❌ ERROR: {e}")
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"session_timeout_validation_{timestamp}.json"
    
    with open(filename, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n💾 Results saved to: {filename}")
    return results

if __name__ == "__main__":
    test_session_timeout_pattern()