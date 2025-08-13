# Comprehensive Testing Plan - Authentication Fix

## Overview

This testing plan validates the authentication fix for Django views that handle both AJAX and regular HTTP requests. The fix removes blocking `@method_decorator(login_required, name='dispatch')` decorators and implements proper authentication handling within custom dispatch methods.

## Test Environment Setup

### Prerequisites
```bash
# Ensure Django development server is running
python manage.py runserver 8000

# Create test users with different permission levels
python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()

# Create admin user
admin = User.objects.create_superuser('testadmin', 'admin@test.com', 'testpass123')

# Create limited user without fabric permissions  
limited = User.objects.create_user('testlimited', 'limited@test.com', 'testpass123')

# Create fabric user with proper permissions
from django.contrib.auth.models import Permission
fabric_user = User.objects.create_user('testfabric', 'fabric@test.com', 'testpass123')
perm = Permission.objects.get(codename='change_hedgehogfabric')
fabric_user.user_permissions.add(perm)
"

# Create test fabric for endpoint testing
python manage.py shell -c "
from netbox_hedgehog.models import HedgehogFabric
fabric = HedgehogFabric.objects.create(
    name='Test Fabric',
    description='Test fabric for authentication testing'
)
print(f'Created test fabric with ID: {fabric.id}')
"
```

### Test Data
- **Test Fabric ID**: 1 (created above)
- **Admin User**: testadmin/testpass123 (all permissions)
- **Fabric User**: testfabric/testpass123 (change_hedgehogfabric permission)
- **Limited User**: testlimited/testpass123 (no fabric permissions)

## Critical Test Endpoints

| Endpoint | URL Pattern | View Class |
|----------|-------------|------------|
| Connection Test | `/fabrics/1/test-connection/` | FabricTestConnectionView |
| Kubernetes Sync | `/fabrics/1/sync/` | FabricSyncView |
| GitHub Sync | `/fabrics/1/github-sync/` | FabricGitHubSyncView |

## Test Categories

### Category 1: Authentication Tests

#### Test 1.1: Unauthenticated AJAX Requests
**Objective**: Verify unauthenticated AJAX requests receive JSON 401 responses

```bash
# Test all sync endpoints
for endpoint in "test-connection" "sync" "github-sync"; do
  echo "Testing /fabrics/1/${endpoint}/"
  curl -s -w "\nStatus: %{http_code}\nContent-Type: %{content_type}\n\n" \
       -H "X-Requested-With: XMLHttpRequest" \
       -X POST "http://localhost:8000/plugins/netbox_hedgehog/fabrics/1/${endpoint}/"
done
```

**Expected Results**:
- Status Code: 401 Unauthorized
- Content-Type: application/json  
- Response Body: `{"success": false, "error": "Authentication required...", "action": "redirect_to_login", "login_url": "/login/"}`

#### Test 1.2: Unauthenticated Regular Requests  
**Objective**: Verify unauthenticated regular requests redirect to login

```bash  
# Test all sync endpoints without AJAX header
for endpoint in "test-connection" "sync" "github-sync"; do
  echo "Testing /fabrics/1/${endpoint}/"
  curl -s -w "\nStatus: %{http_code}\nLocation: %{redirect_url}\n\n" \
       -X POST "http://localhost:8000/plugins/netbox_hedgehog/fabrics/1/${endpoint}/"
done
```

**Expected Results**:
- Status Code: 302 Found
- Location Header: Contains `/login/`
- Response: HTML redirect to login page

#### Test 1.3: Authenticated Requests (Admin User)
**Objective**: Verify authenticated admin user can access all endpoints

```bash
# First login to get session cookie
SESSION_COOKIE=$(curl -s -c - -b - -X POST \
  -d "username=testadmin&password=testpass123&csrfmiddlewaretoken=dummy" \
  "http://localhost:8000/login/" | grep sessionid | cut -f7)

# Test AJAX requests with authentication
for endpoint in "test-connection" "sync" "github-sync"; do
  echo "Testing authenticated /fabrics/1/${endpoint}/"
  curl -s -w "\nStatus: %{http_code}\n\n" \
       -H "X-Requested-With: XMLHttpRequest" \
       -H "Cookie: sessionid=${SESSION_COOKIE}" \
       -X POST "http://localhost:8000/plugins/netbox_hedgehog/fabrics/1/${endpoint}/"
done
```

**Expected Results**:
- Status Code: 200 OK (or appropriate success response)
- Content-Type: application/json
- Response: Actual sync operation results

### Category 2: Authorization Tests

#### Test 2.1: Limited User (No Fabric Permissions)
**Objective**: Verify users without fabric permissions get 403 errors

```bash
# Login as limited user
LIMITED_SESSION=$(curl -s -c - -b - -X POST \
  -d "username=testlimited&password=testpass123&csrfmiddlewaretoken=dummy" \
  "http://localhost:8000/login/" | grep sessionid | cut -f7)

# Test AJAX requests with limited user
for endpoint in "test-connection" "sync" "github-sync"; do
  echo "Testing limited user /fabrics/1/${endpoint}/"
  curl -s -w "\nStatus: %{http_code}\n\n" \
       -H "X-Requested-With: XMLHttpRequest" \
       -H "Cookie: sessionid=${LIMITED_SESSION}" \
       -X POST "http://localhost:8000/plugins/netbox_hedgehog/fabrics/1/${endpoint}/"
done
```

**Expected Results**:
- Status Code: 403 Forbidden  
- Content-Type: application/json
- Response Body: `{"success": false, "error": "Permission denied"}`

#### Test 2.2: Fabric User (Proper Permissions)
**Objective**: Verify users with fabric permissions can access endpoints

```bash
# Login as fabric user
FABRIC_SESSION=$(curl -s -c - -b - -X POST \
  -d "username=testfabric&password=testpass123&csrfmiddlewaretoken=dummy" \
  "http://localhost:8000/login/" | grep sessionid | cut -f7)

# Test AJAX requests with fabric user
for endpoint in "test-connection" "sync" "github-sync"; do
  echo "Testing fabric user /fabrics/1/${endpoint}/"
  curl -s -w "\nStatus: %{http_code}\n\n" \
       -H "X-Requested-With: XMLHttpRequest" \
       -H "Cookie: sessionid=${FABRIC_SESSION}" \
       -X POST "http://localhost:8000/plugins/netbox_hedgehog/fabrics/1/${endpoint}/"
done
```

**Expected Results**:
- Status Code: 200 OK (or appropriate success response)
- Content-Type: application/json  
- Response: Actual sync operation results

### Category 3: CSRF Protection Tests

#### Test 3.1: Missing CSRF Token
**Objective**: Verify CSRF protection remains active

```bash
# Test with valid session but no CSRF token
curl -s -w "\nStatus: %{http_code}\n\n" \
     -H "Cookie: sessionid=${SESSION_COOKIE}" \
     -X POST "http://localhost:8000/plugins/netbox_hedgehog/fabrics/1/sync/"
```

**Expected Results**:
- Status Code: 403 Forbidden
- Response: CSRF verification failed error

#### Test 3.2: Valid CSRF Token
**Objective**: Verify requests with proper CSRF tokens work

```bash
# Get CSRF token first
CSRF_TOKEN=$(curl -s -H "Cookie: sessionid=${SESSION_COOKIE}" \
  "http://localhost:8000/plugins/netbox_hedgehog/" | \
  grep -o 'csrfmiddlewaretoken.*value="[^"]*"' | \
  sed 's/.*value="\([^"]*\)".*/\1/')

# Test with proper CSRF token
curl -s -w "\nStatus: %{http_code}\n\n" \
     -H "X-Requested-With: XMLHttpRequest" \
     -H "Cookie: sessionid=${SESSION_COOKIE}" \
     -H "X-CSRFToken: ${CSRF_TOKEN}" \
     -X POST "http://localhost:8000/plugins/netbox_hedgehog/fabrics/1/sync/"
```

**Expected Results**:
- Status Code: 200 OK
- Content-Type: application/json
- Response: Actual sync results

### Category 4: Edge Cases and Error Handling

#### Test 4.1: Invalid Session IDs
**Objective**: Test behavior with malformed session cookies

```bash
# Test with invalid session ID
curl -s -w "\nStatus: %{http_code}\n\n" \
     -H "X-Requested-With: XMLHttpRequest" \
     -H "Cookie: sessionid=invalid_session_12345" \
     -X POST "http://localhost:8000/plugins/netbox_hedgehog/fabrics/1/sync/"
```

**Expected Results**:
- Status Code: 401 Unauthorized
- Response: JSON authentication required error

#### Test 4.2: Expired Sessions
**Objective**: Test behavior with expired session cookies

```bash
# Test with expired session (would need actual expired session)
# This test requires manual session expiration setup
```

#### Test 4.3: Non-existent Fabric
**Objective**: Test behavior with invalid fabric IDs

```bash
# Test with non-existent fabric ID
curl -s -w "\nStatus: %{http_code}\n\n" \
     -H "X-Requested-With: XMLHttpRequest" \
     -H "Cookie: sessionid=${SESSION_COOKIE}" \
     -H "X-CSRFToken: ${CSRF_TOKEN}" \
     -X POST "http://localhost:8000/plugins/netbox_hedgehog/fabrics/99999/sync/"
```

**Expected Results**:
- Status Code: 404 Not Found
- Response: JSON error indicating fabric not found

### Category 5: Integration Tests

#### Test 5.1: Frontend JavaScript Integration
**Objective**: Test actual JavaScript AJAX calls from browser

```javascript
// Run in browser console after login
fetch('/plugins/netbox_hedgehog/fabrics/1/sync/', {
    method: 'POST',
    headers: {
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
    }
}).then(response => {
    console.log('Status:', response.status);
    return response.json();
}).then(data => {
    console.log('Response:', data);
});
```

#### Test 5.2: Session Timeout Handling
**Objective**: Test frontend handling of session timeout

```javascript
// Simulate session timeout by clearing cookies, then retry request
document.cookie = 'sessionid=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;';

fetch('/plugins/netbox_hedgehog/fabrics/1/sync/', {
    method: 'POST',
    headers: {
        'X-Requested-With': 'XMLHttpRequest'
    }
}).then(response => {
    console.log('Status:', response.status); // Should be 401
    return response.json();
}).then(data => {
    console.log('Response:', data); // Should contain login redirect info
});
```

## Automated Test Script

```python
#!/usr/bin/env python3
"""Comprehensive authentication fix test suite"""

import requests
import json
import time
from urllib.parse import urljoin

class AuthenticationTestSuite:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.plugin_base = urljoin(base_url, "/plugins/netbox_hedgehog")
        self.endpoints = [
            "/fabrics/1/test-connection/",
            "/fabrics/1/sync/", 
            "/fabrics/1/github-sync/"
        ]
        self.test_results = []

    def login_user(self, username, password):
        """Login and return session cookie"""
        login_url = urljoin(self.base_url, "/login/")
        
        # Get login page to extract CSRF token
        session = requests.Session()
        login_page = session.get(login_url)
        
        # Extract CSRF token (simplified)
        csrf_token = "dummy"  # In real test, parse from login page
        
        # Submit login
        login_data = {
            'username': username,
            'password': password, 
            'csrfmiddlewaretoken': csrf_token
        }
        
        response = session.post(login_url, data=login_data)
        
        if response.status_code == 302:  # Successful login redirect
            return session.cookies.get('sessionid')
        return None

    def test_unauthenticated_ajax(self):
        """Test unauthenticated AJAX requests"""
        for endpoint in self.endpoints:
            url = urljoin(self.plugin_base, endpoint.lstrip('/'))
            
            response = requests.post(
                url,
                headers={'X-Requested-With': 'XMLHttpRequest'}
            )
            
            result = {
                'test': 'unauthenticated_ajax',
                'endpoint': endpoint,
                'status_code': response.status_code,
                'content_type': response.headers.get('content-type', ''),
                'is_json': 'application/json' in response.headers.get('content-type', ''),
                'expected_status': 401,
                'passed': response.status_code == 401 and 'application/json' in response.headers.get('content-type', '')
            }
            
            if result['is_json']:
                try:
                    result['response_data'] = response.json()
                except:
                    result['response_data'] = None
            
            self.test_results.append(result)

    def test_unauthenticated_regular(self):
        """Test unauthenticated regular requests"""  
        for endpoint in self.endpoints:
            url = urljoin(self.plugin_base, endpoint.lstrip('/'))
            
            response = requests.post(url, allow_redirects=False)
            
            result = {
                'test': 'unauthenticated_regular',
                'endpoint': endpoint,
                'status_code': response.status_code,
                'location': response.headers.get('Location', ''),
                'expected_status': 302,
                'passed': response.status_code in [302, 301] and 'login' in response.headers.get('Location', '').lower()
            }
            
            self.test_results.append(result)

    def test_authenticated_admin(self):
        """Test authenticated admin user"""
        session_id = self.login_user('testadmin', 'testpass123')
        
        if not session_id:
            self.test_results.append({
                'test': 'authenticated_admin',
                'endpoint': 'LOGIN',
                'passed': False,
                'error': 'Failed to login admin user'
            })
            return
            
        for endpoint in self.endpoints:
            url = urljoin(self.plugin_base, endpoint.lstrip('/'))
            
            response = requests.post(
                url,
                headers={'X-Requested-With': 'XMLHttpRequest'},
                cookies={'sessionid': session_id}
            )
            
            result = {
                'test': 'authenticated_admin', 
                'endpoint': endpoint,
                'status_code': response.status_code,
                'expected_status': 200,
                'passed': response.status_code in [200, 201]  # Allow success codes
            }
            
            self.test_results.append(result)

    def test_limited_user(self):
        """Test user without fabric permissions"""
        session_id = self.login_user('testlimited', 'testpass123')
        
        if not session_id:
            self.test_results.append({
                'test': 'limited_user',
                'endpoint': 'LOGIN',
                'passed': False,
                'error': 'Failed to login limited user'
            })
            return
            
        for endpoint in self.endpoints:
            url = urljoin(self.plugin_base, endpoint.lstrip('/'))
            
            response = requests.post(
                url,
                headers={'X-Requested-With': 'XMLHttpRequest'},
                cookies={'sessionid': session_id}
            )
            
            result = {
                'test': 'limited_user',
                'endpoint': endpoint, 
                'status_code': response.status_code,
                'expected_status': 403,
                'passed': response.status_code == 403
            }
            
            self.test_results.append(result)

    def run_all_tests(self):
        """Execute complete test suite"""
        print("Running authentication fix test suite...")
        
        self.test_unauthenticated_ajax()
        print("✓ Unauthenticated AJAX tests completed")
        
        self.test_unauthenticated_regular() 
        print("✓ Unauthenticated regular tests completed")
        
        self.test_authenticated_admin()
        print("✓ Authenticated admin tests completed")
        
        self.test_limited_user()
        print("✓ Limited user tests completed")
        
        return self.test_results

    def generate_report(self):
        """Generate comprehensive test report"""
        passed_tests = sum(1 for result in self.test_results if result.get('passed', False))
        total_tests = len(self.test_results)
        
        report = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'summary': {
                'total_tests': total_tests,
                'passed_tests': passed_tests,
                'failed_tests': total_tests - passed_tests,
                'success_rate': f"{(passed_tests/total_tests)*100:.1f}%" if total_tests > 0 else "0%"
            },
            'test_results': self.test_results,
            'overall_status': 'PASS' if passed_tests == total_tests else 'FAIL'
        }
        
        return report

if __name__ == "__main__":
    suite = AuthenticationTestSuite()
    suite.run_all_tests()
    report = suite.generate_report()
    
    print("\n" + "="*60)
    print("AUTHENTICATION FIX TEST REPORT")
    print("="*60)
    
    print(f"Total Tests: {report['summary']['total_tests']}")
    print(f"Passed: {report['summary']['passed_tests']}")
    print(f"Failed: {report['summary']['failed_tests']}")  
    print(f"Success Rate: {report['summary']['success_rate']}")
    
    print(f"\nOverall Status: {report['overall_status']}")
    
    if report['overall_status'] == 'FAIL':
        print("\nFAILED TESTS:")
        for result in report['test_results']:
            if not result.get('passed', False):
                print(f"  - {result['test']} / {result['endpoint']}: Status {result.get('status_code', 'N/A')}")
    
    # Save detailed report
    with open('authentication_fix_test_report.json', 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\nDetailed report saved to: authentication_fix_test_report.json")
    
    exit(0 if report['overall_status'] == 'PASS' else 1)
```

## Test Execution Schedule

### Phase 1: Pre-Implementation Baseline Tests
- [ ] Run current system tests to establish baseline
- [ ] Document current behavior for comparison
- [ ] Verify test environment setup

### Phase 2: Post-Implementation Validation
- [ ] Execute full test suite immediately after code changes
- [ ] Verify all tests pass before deployment
- [ ] Document any unexpected results

### Phase 3: Production Validation  
- [ ] Execute limited smoke tests in production
- [ ] Monitor for authentication errors
- [ ] Validate user experience improvements

## Success Criteria

### Must Pass (Critical)
- All unauthenticated AJAX requests return JSON 401 responses
- All unauthenticated regular requests redirect to login
- All authenticated users with permissions can access sync endpoints
- All authenticated users without permissions get 403 errors
- CSRF protection remains functional

### Should Pass (Important)  
- Error responses contain helpful user messaging
- Session timeout handling works gracefully
- Frontend JavaScript integration functions properly

### Could Pass (Nice to Have)
- Performance metrics show no degradation
- Logging and monitoring capture proper events
- User experience is improved over previous behavior

## Rollback Testing

### Rollback Procedure Test
1. Apply authentication fix
2. Run full test suite (should pass)
3. Rollback changes (re-add decorators)
4. Run baseline tests (should return to original behavior)
5. Re-apply fix and validate

### Rollback Success Criteria
- System returns to exact previous behavior after rollback
- No new errors or broken functionality introduced
- Re-application of fix works identically to first application

---

This comprehensive testing plan ensures the authentication fix works correctly while maintaining security and not breaking existing functionality.