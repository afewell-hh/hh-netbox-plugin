# Hedgehog NetBox Plugin - Testing Checklist

**Last Updated**: 2025-07-02

## 🎯 **TESTING PHILOSOPHY**

### **Test Early, Test Often**
- ✅ Test every change immediately in browser
- ✅ Verify no regressions in existing functionality
- ✅ Test both success and error scenarios
- ✅ Validate all user workflows end-to-end

### **Test Categories**
1. **Smoke Tests**: Basic functionality works
2. **Feature Tests**: Specific functionality works correctly
3. **Integration Tests**: Components work together
4. **User Workflow Tests**: Complete user journeys

---

## 🚀 **SMOKE TESTS (Run After Any Change)**

### **1. System Health**
```bash
# Container running and healthy
sudo docker ps | grep netbox
# Should show: (healthy) status

# Plugin loads without errors
curl -I http://localhost:8000/plugins/hedgehog/
# Should return: HTTP/1.1 200 OK

# No errors in logs
sudo docker logs netbox-docker-netbox-1 --tail 10
# Should show no ERROR or CRITICAL messages
```

### **2. Basic Navigation**
- [ ] ✅ Plugin homepage loads: `http://localhost:8000/plugins/hedgehog/`
- [ ] ✅ Fabric list loads: Navigate to Fabrics
- [ ] ✅ VPC list loads: Navigate to VPCs  
- [ ] ✅ Menu items work: All navigation links respond

### **3. Core CRUD Operations**
- [ ] ✅ Create fabric: Fabrics → Add → Fill form → Save
- [ ] ✅ View fabric: Click on fabric name → Detail page loads
- [ ] ✅ Edit fabric: Edit button → Form loads → Save
- [ ] ✅ Create VPC: VPCs → Add → Fill form → Save

**If any smoke test fails, STOP and fix before continuing.**

---

## 🔧 **FEATURE-SPECIFIC TESTS**

### **Fabric Management Tests**
```
Test: Create New Fabric
Steps:
1. Navigate to Fabrics → Add  
2. Fill required fields: name, description
3. Add Kubernetes config (server, token, namespace)
4. Click Save
Expect: Success message, redirected to fabric list, fabric appears

Test: Kubernetes Connection
Steps:  
1. Open fabric detail page
2. Click "Test Connection" button
3. Wait for response
Expect: Success popup with cluster details OR clear error message

Test: Kubernetes Sync
Steps:
1. Ensure connection test passes first
2. Click "Sync Now" button  
3. Wait for response
Expect: Success popup with CRD counts OR clear error message
```

### **VPC Management Tests**
```
Test: Create VPC
Steps:
1. Navigate to VPCs → Add
2. Fill required fields: name, fabric, spec
3. Click Save
Expect: Success message, redirected to VPC list, VPC appears

Test: Edit VPC
Steps:
1. Open VPC detail page
2. Click Edit button
3. Modify spec field
4. Click Save  
Expect: Changes saved, success message

Test: Delete VPC
Steps:
1. Open VPC detail page  
2. Click Delete button
3. Confirm deletion
Expect: VPC removed from list
```

### **Form Validation Tests**
```
Test: Required Field Validation
Steps:
1. Open any create form
2. Leave required fields empty
3. Submit form
Expect: Validation errors shown, form not submitted

Test: JSON Field Validation
Steps:
1. Open VPC create form
2. Enter invalid JSON in spec field
3. Submit form
Expect: JSON validation error shown

Test: Unique Name Validation
Steps:
1. Create fabric with name "test"
2. Try to create another fabric with name "test"
Expect: Unique constraint error
```

---

## 🔄 **INTEGRATION TESTS**

### **Kubernetes Integration**
```
Test: Real Cluster Connectivity
Prerequisites: Live Hedgehog cluster accessible via kubectl
Steps:
1. Create fabric with correct K8s credentials
2. Test connection - should succeed
3. Run sync - should fetch real CRD counts
4. Verify counts match `kubectl get [crd-type] -n [namespace]`
Expect: Real data from cluster displayed

Test: Error Handling
Steps:
1. Create fabric with invalid K8s credentials
2. Test connection - should fail gracefully
3. Try sync without connection - should show clear error
Expect: Clear error messages, no crashes
```

### **Database Integration**
```
Test: Data Persistence
Steps:
1. Create fabric and VPC
2. Restart NetBox container
3. Verify data still exists
Expect: All data persists across restarts

Test: Relationship Integrity
Steps:
1. Create fabric
2. Create VPC linked to fabric
3. Try to delete fabric
Expect: Should prevent deletion OR cascade properly
```

---

## 👤 **USER WORKFLOW TESTS**

### **New User Onboarding Workflow**
```
Scenario: User wants to onboard existing Hedgehog fabric
Steps:
1. User accesses NetBox Hedgehog plugin
2. Navigates to Fabrics → Add
3. Enters fabric name and description
4. Configures Kubernetes connection details
5. Tests connection (should succeed)
6. Runs sync to import existing CRDs
7. Views imported CRD counts
8. Navigates to VPCs to see imported VPCs

Current Status: Steps 1-6 work, Step 7-8 pending import functionality
```

### **VPC Management Workflow**
```
Scenario: User wants to create and manage VPC
Steps:
1. User has onboarded fabric (above workflow)
2. Navigates to VPCs → Add
3. Fills VPC configuration form
4. Saves VPC (creates in NetBox)
5. Applies VPC to Kubernetes (future)
6. Monitors VPC status (future)

Current Status: Steps 1-4 work, Steps 5-6 pending apply functionality
```

---

## 🚨 **ERROR SCENARIO TESTS**

### **Network/Connectivity Errors**
```
Test: Kubernetes Cluster Unreachable
Steps:
1. Configure fabric with unreachable K8s server
2. Test connection
Expect: Clear timeout/connection error message

Test: Invalid Credentials
Steps:
1. Configure fabric with invalid token
2. Test connection
Expect: Clear authentication error message
```

### **Data Validation Errors**
```
Test: Invalid JSON in CRD Spec
Steps:
1. Create VPC with malformed JSON in spec
2. Submit form
Expect: JSON validation error, form not submitted

Test: Missing Required Fields
Steps:
1. Try to create fabric without name
2. Submit form
Expect: Required field validation error
```

### **Browser/UI Errors**
```
Test: JavaScript Errors
Steps:
1. Open browser developer tools
2. Navigate through plugin pages
3. Click all interactive buttons
Expect: No JavaScript errors in console

Test: Responsive Design
Steps:
1. Test plugin on mobile/tablet viewport
2. Verify forms and navigation work
Expect: Responsive layout, usable on all screen sizes
```

---

## 📊 **PERFORMANCE TESTS**

### **Load Time Tests**
```
Test: Page Load Performance
Steps:
1. Time fabric list page load with 10+ fabrics
2. Time VPC list page load with 20+ VPCs
3. Time sync operation with large cluster
Expect: All pages load within 3 seconds

Test: Database Query Efficiency
Steps:
1. Check Django debug toolbar (if enabled)
2. Verify list pages don't have N+1 query problems
3. Ensure sync operations batch API calls
Expect: Efficient database and API usage
```

---

## 🔍 **DEBUGGING TEST FAILURES**

### **Common Failure Patterns**
```
Form doesn't save:
- Check form validation errors
- Verify model field constraints
- Check database permissions

Page shows 500 error:
- Check NetBox container logs
- Look for Python tracebacks
- Verify template syntax

Kubernetes operations fail:
- Test kubectl access manually
- Verify credentials format
- Check cluster accessibility

JavaScript not working:
- Check browser console for errors
- Verify static files loaded correctly
- Test with browser cache cleared
```

### **Debug Information Collection**
```bash
# Collect debug info when reporting issues
git log --oneline -5                              # Recent commits
sudo docker logs netbox-docker-netbox-1 --tail 20 # Container logs
curl -I http://localhost:8000/plugins/hedgehog/   # Basic connectivity
kubectl cluster-info                               # K8s cluster status
```

---

## ✅ **TEST COMPLETION CRITERIA**

### **Before Committing Code**
- [ ] All smoke tests pass
- [ ] Relevant feature tests pass  
- [ ] No new JavaScript console errors
- [ ] No new Python exceptions in logs
- [ ] Existing functionality still works

### **Before Releasing Feature**
- [ ] Complete user workflow tests pass
- [ ] Error scenarios handled gracefully
- [ ] Performance acceptable
- [ ] Documentation updated
- [ ] Integration tests with real cluster pass

### **Test Documentation**
```bash
# Record test results in commit messages
git commit -m "feat: add External CRD forms

- Create ExternalForm with all required fields
- Add CRUD views and templates
- Tested: form creation, validation, save/edit workflows
- Verified: no regressions in existing VPC functionality

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

**Remember**: Testing is not optional. Every change must be verified to work correctly before committing.