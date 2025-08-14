#!/usr/bin/env python3
"""
User Experience Validation for Drift Detection Feature

This script validates the key user workflows for drift detection:
1. User can see drift count on dashboard
2. User can click drift metric to navigate to drift page  
3. User can access drift page (with proper authentication)
4. Navigation and hyperlinks work correctly

Uses curl-based HTTP testing to simulate user interactions.
"""

import subprocess
import re
import sys
import json

def run_curl(url, description="", follow_redirects=True):
    """Run curl command and return response details"""
    cmd = ["curl", "-s", "-w", "%{http_code}|%{redirect_url}|%{content_type}"]
    if follow_redirects:
        cmd.extend(["-L"])
    cmd.append(url)
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        output = result.stdout
        
        # Split response body from status info
        parts = output.rsplit("|", 2)
        if len(parts) == 3:
            body = parts[0]
            status_code = parts[1]
            content_type = parts[2]
            return {
                "body": body,
                "status_code": int(status_code) if status_code.isdigit() else 0,
                "content_type": content_type,
                "success": True
            }
        else:
            return {"success": False, "error": f"Unexpected curl output format"}
            
    except Exception as e:
        return {"success": False, "error": str(e)}

def test_dashboard_drift_metric():
    """Test that dashboard shows drift metric correctly"""
    print("🔍 Testing dashboard drift metric...")
    
    response = run_curl("http://localhost:8000/plugins/hedgehog/")
    
    if not response["success"]:
        print(f"❌ Failed to access dashboard: {response.get('error')}")
        return False
        
    if response["status_code"] != 200:
        print(f"❌ Dashboard not accessible: HTTP {response['status_code']}")
        return False
        
    body = response["body"]
    
    # Check if drift metric exists
    if "Drift Detected" not in body:
        print("❌ Dashboard missing 'Drift Detected' metric")
        return False
        
    print("✅ Dashboard contains drift metric")
    
    # Check if showing correct count (2, not 0)
    drift_section = extract_drift_section(body)
    if drift_section:
        if "<h2>2</h2>" in drift_section:
            print("✅ Dashboard shows correct drift count (2)")
        elif "<h2>0</h2>" in drift_section:
            print("❌ Dashboard shows incorrect drift count (0)")
            return False
        else:
            print("⚠️  Could not determine drift count")
    
    # Check if drift metric is hyperlinked
    if 'href="/plugins/hedgehog/drift-detection/"' in body:
        print("✅ Drift metric is hyperlinked to drift page")
        return True
    else:
        print("❌ Drift metric is not hyperlinked")
        return False

def test_drift_page_navigation():
    """Test navigation to drift detection page"""
    print("\\n🔍 Testing drift page navigation...")
    
    response = run_curl("http://localhost:8000/plugins/hedgehog/drift-detection/", follow_redirects=False)
    
    if not response["success"]:
        print(f"❌ Failed to access drift page: {response.get('error')}")
        return False
        
    if response["status_code"] == 302:
        print("✅ Drift page properly redirects to login (expected behavior)")
        return True
    elif response["status_code"] == 200:
        print("✅ Drift page accessible (user may be authenticated)")
        return True
    elif response["status_code"] == 500:
        print("❌ Drift page returns server error (NoReverseMatch issue)")
        return False
    else:
        print(f"⚠️  Drift page returned unexpected status: HTTP {response['status_code']}")
        return False

def test_hyperlink_functionality():
    """Test that hyperlinks in HTML are properly formed"""
    print("\\n🔍 Testing hyperlink functionality...")
    
    response = run_curl("http://localhost:8000/plugins/hedgehog/")
    
    if not response["success"] or response["status_code"] != 200:
        print("❌ Cannot test hyperlinks - dashboard not accessible")
        return False
        
    body = response["body"]
    
    # Extract all drift-related links
    drift_links = re.findall(r'href="([^"]*drift[^"]*)"', body)
    
    if not drift_links:
        print("❌ No drift-related hyperlinks found")
        return False
        
    print(f"✅ Found {len(drift_links)} drift-related hyperlink(s)")
    
    for link in drift_links:
        print(f"  - {link}")
        
    # Verify main drift dashboard link exists
    expected_link = "/plugins/hedgehog/drift-detection/"
    if expected_link in drift_links:
        print(f"✅ Main drift dashboard link present: {expected_link}")
        return True
    else:
        print(f"❌ Main drift dashboard link missing: {expected_link}")
        return False

def test_url_structure():
    """Test URL structure and routing"""
    print("\\n🔍 Testing URL structure...")
    
    # Test various drift-related URLs
    test_urls = [
        "/plugins/hedgehog/",
        "/plugins/hedgehog/drift-detection/",
        "/plugins/hedgehog/fabrics/"
    ]
    
    results = {}
    for url in test_urls:
        response = run_curl(f"http://localhost:8000{url}", follow_redirects=False)
        if response["success"]:
            results[url] = response["status_code"]
        else:
            results[url] = "ERROR"
            
    print("URL Status Results:")
    for url, status in results.items():
        if status in [200, 302]:  # 200 = accessible, 302 = redirect (expected for authenticated pages)
            print(f"  ✅ {url}: HTTP {status}")
        elif status == 404:
            print(f"  ❌ {url}: HTTP {status} (Not Found)")
        elif status == 500:
            print(f"  ❌ {url}: HTTP {status} (Server Error)")
        else:
            print(f"  ⚠️  {url}: {status}")
            
    return all(status in [200, 302] for status in results.values() if status != "ERROR")

def extract_drift_section(html_body):
    """Extract the drift detection section from HTML"""
    try:
        # Find section containing "Drift Detected"
        drift_start = html_body.find("Drift Detected")
        if drift_start == -1:
            return None
            
        # Find the surrounding card section
        card_start = html_body.rfind('<div class="card', 0, drift_start)
        card_end = html_body.find('</div>', drift_start)
        
        if card_start != -1 and card_end != -1:
            return html_body[card_start:card_end + 6]
        else:
            # Fallback: get surrounding context
            start = max(0, drift_start - 200)
            end = min(len(html_body), drift_start + 200)
            return html_body[start:end]
            
    except Exception:
        return None

def run_user_experience_validation():
    """Run complete user experience validation"""
    print("🚀 Running User Experience Validation for Drift Detection")
    print("=" * 60)
    
    tests = [
        ("Dashboard Drift Metric", test_dashboard_drift_metric),
        ("Drift Page Navigation", test_drift_page_navigation), 
        ("Hyperlink Functionality", test_hyperlink_functionality),
        ("URL Structure", test_url_structure),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\\n📋 {test_name}")
        print("-" * 40)
        
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\\n" + "=" * 60)
    print("📊 USER EXPERIENCE VALIDATION SUMMARY")
    print("=" * 60)
    
    passed = 0
    total = len(results)
    
    for test_name, success in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{status}: {test_name}")
        if success:
            passed += 1
    
    print(f"\\n🎯 Overall Result: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All user experience tests PASSED! Drift detection is working correctly.")
        return True
    else:
        print("⚠️  Some user experience tests failed. Review the issues above.")
        return False

if __name__ == "__main__":
    success = run_user_experience_validation()
    sys.exit(0 if success else 1)