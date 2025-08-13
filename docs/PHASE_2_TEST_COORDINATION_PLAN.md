# PHASE 2 TEST COORDINATION PLAN - AUTH-FIX-ORCHESTRATOR
## Live HTTP Workflow Testing Strategy

### **HTTP-WORKFLOW-TESTER COORDINATION**

#### **Mission Briefing**
Validate Phase 1 theoretical findings through comprehensive live testing of authentication flows on sync endpoints.

#### **Test Execution Framework**

**PRIMARY ENDPOINTS TO TEST**:
1. `/plugins/hedgehog/fabrics/35/sync/` (Kubernetes sync)
2. `/plugins/hedgehog/fabrics/35/github-sync/` (GitHub sync) 
3. `/plugins/hedgehog/fabrics/35/test-connection/` (Connection test)

#### **Test Scenario Matrix**

| Scenario | Authentication | Request Type | Expected Result | Current Result |
|----------|----------------|--------------|-----------------|----------------|
| T1 | None | AJAX POST | JSON 401 | HTML 403/302 |
| T2 | None | Non-AJAX POST | HTML redirect | HTML 403/302 |
| T3 | Valid Session | AJAX POST | JSON success/error | JSON success/error |
| T4 | Expired Session | AJAX POST | JSON 401 | HTML 403/302 |
| T5 | Valid Session | Non-AJAX POST | Success/redirect | Success/redirect |

#### **Detailed Test Scripts**

**TEST 1: Unauthenticated AJAX Request** (Critical validation)
```bash
#!/bin/bash
echo "=== TEST 1: Unauthenticated AJAX Request ==="
response=$(curl -s -X POST "http://localhost:8000/plugins/hedgehog/fabrics/35/sync/" \
  -H "X-Requested-With: XMLHttpRequest" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{}' \
  -w "HTTPCODE:%{http_code}\nCONTENT_TYPE:%{content_type}\n")

echo "Response: $response"
echo "Expected: JSON 401 with auth error"
echo "Status: $(echo "$response" | grep HTTPCODE)"
echo "Content-Type: $(echo "$response" | grep CONTENT_TYPE)"
```

**TEST 2: Non-AJAX Unauthenticated Request**
```bash
#!/bin/bash
echo "=== TEST 2: Non-AJAX Unauthenticated Request ==="
response=$(curl -s -X POST "http://localhost:8000/plugins/hedgehog/fabrics/35/sync/" \
  -H "Content-Type: application/json" \
  -d '{}' \
  -w "HTTPCODE:%{http_code}\nREDIRECT:%{redirect_url}\n")

echo "Response: $response"
echo "Expected: HTML redirect to login"
```

**TEST 3: Authenticated Request Simulation**
```bash
#!/bin/bash
echo "=== TEST 3: Authenticated Request Test ==="
# First get CSRF token and session
csrf_response=$(curl -s -c cookies.txt "http://localhost:8000/login/")
csrf_token=$(echo "$csrf_response" | grep -oP 'csrfmiddlewaretoken.*?value="\K[^"]*')

# Attempt login (would need valid credentials)
curl -s -b cookies.txt -c cookies.txt \
  -H "X-CSRFToken: $csrf_token" \
  -d "username=testuser&password=testpass&csrfmiddlewaretoken=$csrf_token" \
  "http://localhost:8000/login/"

# Test sync with session
response=$(curl -s -b cookies.txt -X POST \
  "http://localhost:8000/plugins/hedgehog/fabrics/35/sync/" \
  -H "X-Requested-With: XMLHttpRequest" \
  -H "X-CSRFToken: $csrf_token" \
  -H "Content-Type: application/json" \
  -d '{}' \
  -w "HTTPCODE:%{http_code}\n")

echo "Authenticated response: $response"
```

#### **Expected vs Actual Validation**

**VALIDATION CRITERIA**:

1. **AJAX Authentication Failure** (TEST 1):
   ```json
   // Expected JSON Response:
   {
     "success": false,
     "error": "Authentication required. Please login to perform sync operations.",
     "action": "redirect_to_login", 
     "login_url": "/login/"
   }
   
   // Current HTML Response:
   // HTML login page content with 403/302 status
   ```

2. **Non-AJAX Authentication Failure** (TEST 2):
   ```
   Expected: 302 redirect to /login/
   Current: 403 HTML page or 302 redirect (behavior varies)
   ```

3. **Authenticated Requests** (TEST 3):
   ```
   Expected: JSON success/error based on sync operation
   Current: Should work correctly
   ```

#### **Response Analysis Framework**

**JSON Response Validation**:
```python
import json
import requests

def validate_json_auth_error(response):
    """Validate that response is proper JSON auth error"""
    try:
        data = response.json()
        required_fields = ['success', 'error', 'action']
        
        assert all(field in data for field in required_fields)
        assert data['success'] == False
        assert 'login' in data['error'].lower()
        assert data['action'] == 'redirect_to_login'
        
        return True, "Valid JSON auth error response"
    except Exception as e:
        return False, f"Invalid JSON response: {e}"

def validate_html_redirect(response):
    """Validate that response is HTML redirect to login"""
    is_redirect = response.status_code in [302, 301]
    is_html = 'text/html' in response.headers.get('content-type', '')
    
    return is_redirect or is_html, f"Status: {response.status_code}, Type: {response.headers.get('content-type')}"
```

#### **Test Environment Requirements**

**Setup Prerequisites**:
1. NetBox development server running on localhost:8000
2. Hedgehog plugin installed and configured
3. Fabric with ID 35 exists in database
4. Test user credentials available
5. CSRF middleware enabled

**Environment Validation**:
```bash
# Verify server is running
curl -s "http://localhost:8000/" | grep -q "NetBox" && echo "✅ Server running"

# Verify fabric exists
curl -s "http://localhost:8000/plugins/hedgehog/fabrics/35/" | grep -q "fabric" && echo "✅ Fabric 35 exists"

# Verify sync endpoint exists  
curl -s -X OPTIONS "http://localhost:8000/plugins/hedgehog/fabrics/35/sync/" && echo "✅ Sync endpoint exists"
```

#### **Data Collection Requirements**

**HTTP-WORKFLOW-TESTER Must Collect**:
1. **HTTP Status Codes**: 200, 401, 403, 302, etc.
2. **Content-Type Headers**: application/json vs text/html
3. **Response Bodies**: JSON structure vs HTML content
4. **Cookie Handling**: Session persistence
5. **CSRF Token Validation**: Required headers
6. **Timing Data**: Response latency
7. **Error Messages**: Exact error text returned

#### **Test Result Documentation Format**

```json
{
  "test_execution_id": "phase2_auth_test_001",
  "timestamp": "2025-01-12T10:30:00Z",
  "test_scenarios": {
    "T1_unauthenticated_ajax": {
      "status": "FAILED",
      "expected": {
        "status_code": 401,
        "content_type": "application/json",
        "response_structure": "JSON auth error"
      },
      "actual": {
        "status_code": 403,
        "content_type": "text/html",
        "response_content": "HTML login page"
      },
      "validation": "CONFIRMS Phase 1 theory - decorator prevents AJAX handling"
    },
    "T2_unauthenticated_non_ajax": {
      "status": "SUCCESS",
      "note": "Non-AJAX redirects work as expected"
    },
    "T3_authenticated_ajax": {
      "status": "SUCCESS", 
      "note": "Valid authentication works correctly"
    }
  },
  "phase1_theory_validation": "CONFIRMED",
  "ready_for_phase4": true
}
```

#### **Coordination Checkpoints**

**HTTP-WORKFLOW-TESTER Reporting Schedule**:
- **Initial Setup**: Confirm test environment ready
- **Test 1 Results**: Critical AJAX auth failure validation
- **Full Test Suite**: Complete scenario matrix results  
- **Final Analysis**: Ready/not ready for Phase 4 implementation

**Communication Protocol**:
- Real-time updates during critical tests
- Detailed results documentation
- Issue escalation for unexpected results
- Go/no-go decision for Phase 4

#### **Success Criteria for Phase 2**

✅ **Phase 2 Success Requirements**:
1. **Theory Confirmation**: Unauthenticated AJAX returns HTML instead of JSON
2. **Behavior Mapping**: Complete understanding of current vs expected flows
3. **Environment Validation**: Confirm test setup works for Phase 4 validation
4. **Edge Case Discovery**: Identify any unexpected authentication behaviors
5. **Phase 4 Readiness**: Clear go/no-go decision for implementation

❌ **Failure Conditions**:
- Cannot reproduce authentication issues
- Test environment problems prevent validation
- Unexpected behaviors that contradict Phase 1 findings
- Infrastructure issues blocking testing

#### **Risk Mitigation**

**Test Environment Risks**:
- **Backup Plan**: Use containerized environment if localhost issues
- **Fallback**: Manual browser testing if curl tests fail
- **Alternative**: Network packet capture for detailed analysis

**Data Collection Risks**:
- **Multiple Test Runs**: Ensure consistent results
- **Error Logging**: Capture all failure modes
- **Edge Case Testing**: Test unusual request patterns

### **COORDINATION STATUS**

🔄 **Active Coordination**: HTTP-WORKFLOW-TESTER briefed and equipped  
⏳ **Awaiting Results**: Critical Test 1 (unauthenticated AJAX) validation  
🎯 **Target Timeline**: Complete Phase 2 within 30 minutes  
📊 **Success Metrics**: Theory confirmation + environment validation  

**Next Steps**: Monitor HTTP-WORKFLOW-TESTER progress and prepare Phase 4 implementation based on results.

---
**ORCHESTRATOR**: Ready to receive test results and coordinate Phase 4  
**PRIORITY**: High - Critical path validation for authentication fix