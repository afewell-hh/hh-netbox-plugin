# Systematic Drift Detection Fix Plan
## Quality Assurance Action Plan for Namespace Mismatch Resolution

### 🚨 CRITICAL ROOT CAUSE CONFIRMED
- **App Name**: `netbox_hedgehog` (Django app internal name)
- **Base URL**: `hedgehog` (NetBox plugin URL namespace)
- **Navigation Links**: Uses `plugins:hedgehog:*` pattern
- **URL Patterns**: Expects `plugins:netbox_hedgehog:*` namespace
- **Current Status**: HTTP 500 error confirmed via baseline test
- **Error Type**: Django URL resolution failure at framework level

---

## 📋 COMPREHENSIVE INVENTORY AUDIT RESULTS

### Files Requiring Fixes (Priority Order)

#### **PRIORITY 1: CRITICAL SYSTEM FILES**
1. **`netbox_hedgehog/navigation.py`** ⚠️ URGENT
   - 15 instances of `plugins:hedgehog:*` patterns
   - Controls main plugin navigation menu
   - **Impact**: All navigation links broken

2. **`netbox_hedgehog/urls.py`** ⚠️ URGENT
   - `app_name = 'netbox_hedgehog'` (line 38)
   - URL namespace definition
   - **Impact**: Core URL routing configuration

#### **PRIORITY 2: TEMPLATE FILES**
3. **Template Files with URL tags** (865+ files identified)
   - All `{% url 'plugins:netbox_hedgehog:...' %}` patterns
   - Must be changed to `{% url 'plugins:hedgehog:...' %}`
   - **Key templates identified**:
     - `netbox_hedgehog/templates/netbox_hedgehog/server_list.html`
     - All other templates using URL template tags

#### **PRIORITY 3: VIEW REFERENCES**
4. **Python files with reverse() calls**
   - Search pattern: `reverse('plugins-api:netbox_hedgehog-api:*')`
   - Update to: `reverse('plugins-api:hedgehog-api:*')`

---

## 🔧 SYSTEMATIC FIX STRATEGY

### **Phase 1: Core Configuration Fix**
**Objective**: Fix the fundamental namespace mismatch

**Steps**:
1. **Fix URL namespace in `urls.py`**
   - Change `app_name = 'netbox_hedgehog'` to `app_name = 'hedgehog'`
   - **Agent Assignment**: URL Validator agent
   - **Testing**: Run authentication test after change
   - **Success Criteria**: No change in error (still needs template fixes)

2. **Deploy and test**
   - Run `make deploy-dev`
   - Run `./test-drift-page.sh`
   - Document exact error state

### **Phase 2: Navigation Fix**
**Objective**: Fix navigation menu references

**Steps**:
1. **Update `navigation.py`**
   - Replace all `plugins:hedgehog:*` with `plugins:netbox_hedgehog:*`
   - **Agent Assignment**: Template Auditor agent
   - **Testing**: Check navigation menu loads
   - **Success Criteria**: Navigation menu displays without errors

2. **Deploy and test**
   - Run `make deploy-dev`
   - Run `./test-drift-page.sh`
   - Verify navigation links work

### **Phase 3: Template Systematic Fixes**
**Objective**: Fix all template URL references

**Steps**:
1. **Audit all template files**
   ```bash
   find netbox_hedgehog/templates -name "*.html" -exec grep -l "{% url.*hedgehog" {} \;
   ```

2. **Systematic template updates**
   - **Agent Assignment**: Template Auditor agent
   - **Pattern**: Replace `{% url 'plugins:netbox_hedgehog:*' %}` with `{% url 'plugins:hedgehog:*' %}`
   - **Testing**: After each template fix, test specific functionality

3. **Priority template order**:
   - `server_list.html` first (has 6 URL references)
   - All templates in `netbox_hedgehog/templates/netbox_hedgehog/`
   - Any templates in subdirectories

### **Phase 4: Python Code Fixes**
**Objective**: Fix reverse() calls and Python URL references

**Steps**:
1. **Search for reverse() patterns**
   ```bash
   grep -r "reverse.*netbox_hedgehog" netbox_hedgehog/
   ```

2. **Update Python files**
   - **Agent Assignment**: URL Validator agent
   - **Pattern**: Update reverse() calls to use correct namespace
   - **Testing**: Test affected functionality after each fix

---

## 🧪 TESTING PROTOCOL INTEGRATION

### **Testing Requirements for Each Step**

#### **Mandatory Testing After Each Fix**:
1. **Authentication Test**: `./test-drift-page.sh`
   - Must pass before proceeding to next fix
   - No agent declares success without running this test

2. **Container Deployment**: `make deploy-dev`
   - Required before any testing
   - Local changes are NOT live until deployed

3. **Specific Functionality Tests**:
   - Navigation menu loading
   - Individual page access
   - URL resolution verification

#### **Testing Command Reference**:
```bash
# Baseline authentication test
./test-drift-page.sh

# Deploy changes to container
make deploy-dev

# Verify specific URL endpoints
curl -b /tmp/nb.jar http://localhost:8000/plugins/hedgehog/
curl -b /tmp/nb.jar http://localhost:8000/plugins/hedgehog/drift-detection/

# Check navigation menu
curl -s -b /tmp/nb.jar http://localhost:8000/ | grep -A 50 "Hedgehog"
```

---

## 👥 AGENT VALIDATION CHAINS

### **Quality Assurance Agent Roles**

#### **Primary Implementation Agents**:
1. **Template Auditor Agent** (`agent-1755214252591`)
   - **Responsibility**: All template file modifications
   - **Validation**: Must run authentication test after each template fix
   - **Hand-off**: To URL Validator agent for verification

2. **URL Validator Agent** (`agent-1755214252779`)
   - **Responsibility**: URLs.py fixes and Python reverse() calls
   - **Validation**: Must verify URL resolution manually
   - **Hand-off**: To Authentication Validator for final testing

#### **Validation Chain Process**:
1. **Primary Agent** implements fix
2. **Secondary Agent** independently verifies fix
3. **Authentication Validator** (`agent-1755214252966`) runs comprehensive test
4. **Fix Coordinator** (`agent-1755214253165`) approves progression to next phase

#### **Validation Requirements**:
- **No agent declares success without running `./test-drift-page.sh`**
- **Each fix must be validated by a different agent than who implemented it**
- **Final validation requires sign-off from Authentication Validator**

---

## 🔄 ROLLBACK PROCEDURES

### **Immediate Rollback Triggers**:
1. Authentication test fails with new error type
2. Navigation completely breaks
3. Core NetBox functionality affected
4. Database errors introduced

### **Rollback Process**:
1. **Git revert** to last known working state
2. **Container redeploy**: `make deploy-dev`
3. **Verify rollback**: Run authentication test
4. **Document issue** in QA memory
5. **Revised approach** before retry

---

## 📊 SUCCESS CRITERIA FRAMEWORK

### **Phase Completion Criteria**:

#### **Phase 1 Complete When**:
- [ ] `urls.py` namespace updated
- [ ] Deployment successful
- [ ] Error type may change but documented

#### **Phase 2 Complete When**:
- [ ] Navigation.py updated
- [ ] Navigation menu loads without errors
- [ ] All navigation links resolve (may still error on page load)

#### **Phase 3 Complete When**:
- [ ] All template URL references updated
- [ ] `./test-drift-page.sh` returns HTTP 200
- [ ] Drift detection page loads successfully

#### **Phase 4 Complete When**:
- [ ] All Python reverse() calls updated
- [ ] End-to-end functionality validated
- [ ] Full authentication workflow passes

### **Final Success Validation**:
```bash
# Must all pass:
./test-drift-page.sh                           # HTTP 200
curl -b /tmp/nb.jar http://localhost:8000/plugins/hedgehog/  # HTTP 200
# Navigation menu displays all links correctly
# Drift detection page renders fully
```

---

## 🎯 EXECUTION ORDER SUMMARY

### **Step-by-Step Implementation**:

1. **Initialize**: Deploy baseline and confirm HTTP 500 error
2. **Phase 1**: Fix `urls.py` namespace, deploy, test
3. **Phase 2**: Fix `navigation.py` references, deploy, test
4. **Phase 3**: Systematically fix all template files, deploy and test after each batch
5. **Phase 4**: Fix Python reverse() calls, deploy, test
6. **Final Validation**: Complete end-to-end testing with authentication protocol

### **Quality Gates**:
- **No phase proceeds without successful deployment**
- **No agent declares success without running authentication test**
- **Secondary validation required for each fix**
- **Final orchestrating agent must verify all components**

### **Documentation Requirements**:
- **Log all test results** in QA memory
- **Document exact error messages** before and after each fix
- **Track which agent performed each fix** for accountability
- **Record deployment timestamps** for troubleshooting

---

## 🚀 IMPLEMENTATION READINESS CHECKLIST

- [x] **Swarm Initialized**: Hierarchical topology with specialized agents
- [x] **Root Cause Confirmed**: Namespace mismatch between app_name and base_url
- [x] **Inventory Complete**: 865+ files audited, priorities identified
- [x] **Testing Protocol**: Authentication testing script validated
- [x] **Agent Assignments**: Clear role definitions for each specialist
- [x] **Rollback Plan**: Git revert procedures documented
- [x] **Success Criteria**: Clear metrics for each phase completion

### **Ready to Execute**: ✅ ALL PREREQUISITES MET

**Next Action**: Begin Phase 1 with URL Validator agent fixing `urls.py` namespace configuration.

---

*Generated by Quality Assurance Manager with ruv-swarm coordination*
*Swarm ID: swarm-1755214252223 | Task ID: task-1755214274119*