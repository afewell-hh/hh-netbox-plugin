# NetBox Hedgehog Plugin - Authentication Testing Protocol

## 🎯 Purpose
This protocol provides bulletproof authentication testing that accurately reproduces the user's browser experience with the drift detection page.

## 🚨 Current Error State (Verified)
- **URL**: http://localhost:8000/plugins/hedgehog/drift-detection/
- **HTTP Status**: 500 Server Error  
- **Error**: `'netbox_hedgehog' is not a registered namespace`
- **Exception Type**: Django NoReverseMatch

## ⚡ Quick Test (Recommended)

```bash
# Execute the quick test script
./quick_auth_test.sh
```

**Expected Output (Current Error State):**
```
🔐 Getting CSRF token and logging in...
✅ CSRF token: 2aSPibuE9G4x...
✅ Login successful
🧪 Testing drift detection page...
📊 Result: HTTP 500
❌ FAILED: Server error (namespace issue)
   Error: 'netbox_hedgehog' namespace not registered
```

## 🔧 Comprehensive Test

```bash
# Execute the full authentication test protocol
./auth_test_protocol.sh
```

This provides detailed step-by-step authentication verification with comprehensive error analysis.

## 📋 Manual curl Commands

### Step 1: Get CSRF Token and Login
```bash
# Get CSRF token and save cookies
CSRF_TOKEN=$(curl -s -c /tmp/netbox_cookies.txt http://localhost:8000/login/ | grep -o 'name="csrfmiddlewaretoken" value="[^"]*"' | cut -d'"' -f4)

# Login with credentials  
curl -s -b /tmp/netbox_cookies.txt -c /tmp/netbox_cookies.txt \
    -X POST \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -H "Referer: http://localhost:8000/login/" \
    -d "csrfmiddlewaretoken=$CSRF_TOKEN&username=admin&password=admin&next=%2F" \
    http://localhost:8000/login/
```

### Step 2: Test Drift Detection Page
```bash
# Test the target page
curl -b /tmp/netbox_cookies.txt -w "HTTP_STATUS:%{http_code}" \
    http://localhost:8000/plugins/hedgehog/drift-detection/
```

### Step 3: Cleanup
```bash
rm -f /tmp/netbox_cookies.txt
```

## 🎯 Success Criteria

### ✅ Working State (Target)
- **HTTP Status**: 200 OK
- **Content**: Contains "Drift Detection" page content
- **Authentication**: Session verified and working

### ❌ Failed State (Current)
- **HTTP Status**: 500 Server Error
- **Error**: NoReverseMatch exception
- **Cause**: 'netbox_hedgehog' namespace not registered

## 🔄 Testing Workflow for Developers

### 1. Before Making Changes
```bash
./quick_auth_test.sh
# Should show: HTTP 500 (namespace error)
```

### 2. After Making Changes
```bash
# Deploy changes
make deploy-dev

# Test again
./quick_auth_test.sh
# Should show: HTTP 200 (success)
```

### 3. Verify Fix is Complete
The test must show:
- ✅ Authentication successful
- ✅ HTTP 200 status
- ✅ Page loads without errors

## 🧪 Integration with Development Workflow

### For Coding Agents
```bash
# Before starting work
echo "Testing current state..."
./quick_auth_test.sh

# Make code changes
# ... (edit files)

# Deploy and test
make deploy-dev
./quick_auth_test.sh

# Verify success
if [ $? -eq 0 ]; then
    echo "✅ Fix successful!"
else
    echo "❌ Fix incomplete - continue debugging"
fi
```

### For Validation
```bash
# Complete validation sequence
./auth_test_protocol.sh > test_results.log 2>&1

# Check results
if grep -q "TEST PASSED" test_results.log; then
    echo "🎉 Page is fully working"
else
    echo "🔧 Debugging needed"
    cat test_results.log
fi
```

## 📊 Expected Test Results

### Current State (Broken)
```
HTTP Status: 500
Authentication: ✓ Success  
Page Status: ✗ Failed
Error: 'netbox_hedgehog' namespace not registered
```

### Target State (Fixed)
```
HTTP Status: 200
Authentication: ✓ Success
Page Status: ✓ Working
Content: Drift Detection page loaded successfully
```

## 🔍 Debugging Information

### Common Issues
1. **Container not running**: Run `make deploy-dev`
2. **Authentication fails**: Check admin/admin credentials
3. **CSRF token issues**: Clear cookies and retry
4. **Namespace errors**: Check URL patterns registration

### Debug Commands
```bash
# Check container status
sudo docker ps | grep netbox

# Check NetBox logs
sudo docker logs netbox-docker-netbox-1 --tail 50

# Check if plugin is loaded
curl -s http://localhost:8000/plugins/ | grep hedgehog
```

## 💡 Key Features

1. **🔐 Proper Authentication**: Handles Django CSRF tokens and session cookies
2. **🎯 Accurate Reproduction**: Matches exact browser experience
3. **📊 Clear Results**: Color-coded output with detailed error analysis
4. **⚡ Fast Execution**: Quick test completes in ~3 seconds
5. **🔄 Repeatable**: Consistent results across multiple runs
6. **🧪 Developer-Friendly**: Easy integration with development workflow

## 📁 Files
- `auth_test_protocol.sh` - Comprehensive authentication test
- `quick_auth_test.sh` - Fast authentication test
- `AUTHENTICATION_TESTING_PROTOCOL.md` - This documentation

## 🎯 Usage by Development Agents

This protocol ensures that any coding agent can:
1. **Verify current error state** before making changes
2. **Test fixes reliably** after implementation
3. **Confirm complete resolution** before task completion
4. **Provide proof** that the page works correctly

The protocol eliminates guesswork and provides definitive pass/fail results for the drift detection page functionality.