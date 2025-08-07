# Minimal Validation Design: FGD Sync Testing

**Enhanced QAPM v2.5 Agent**: qapm_20250804_171200_awaiting_assignment  
**Design Date**: 2025-08-04  
**Task Complexity**: 2/5 (within single agent capacity)

## Validation Strategy Overview

**Purpose**: Establish definitive proof of system functionality through minimal, verifiable testing that cannot produce false completion claims.

**Core Principle**: Test only the smallest possible unit that produces observable change in GitHub repository state.

## Minimal Test Design

### Test 1: Baseline State Verification

**Objective**: Document current GitHub repository state as baseline
**Duration**: 5 minutes
**Complexity**: 1/5

**Steps**:
1. Use GitHub API to capture current raw/ directory state
2. Document file count, names, and SHA hashes
3. Take screenshot of GitHub web interface
4. Save state as baseline evidence

**Success Criteria**: Baseline state documented with timestamps and API evidence

### Test 2: UI Sync Button Test

**Objective**: Test actual sync button functionality
**Duration**: 10 minutes  
**Complexity**: 2/5

**Steps**:
1. Access NetBox HNP interface
2. Navigate to fabric detail page
3. Locate and click sync button
4. Capture any response messages or errors
5. Document exact UI behavior

**Success Criteria**: Sync button behavior documented with screenshots

### Test 3: Post-Sync State Verification

**Objective**: Verify GitHub repository state after sync attempt
**Duration**: 5 minutes
**Complexity**: 1/5

**Steps**:
1. Re-query GitHub API for raw/ directory state
2. Compare file count, names, and SHA hashes to baseline
3. Check for any new managed directories
4. Take screenshot of GitHub web interface
5. Document any state changes

**Success Criteria**: Post-sync state comparison shows measurable change or confirms no change

### Test 4: Failure Point Identification

**Objective**: If no change detected, identify where sync fails
**Duration**: 15 minutes
**Complexity**: 2/5

**Steps**:
1. Check Django admin logs for sync attempt
2. Check browser console for JavaScript errors
3. Check network tab for API calls during sync
4. Document any error messages or failed requests
5. Note exact point where sync process stops

**Success Criteria**: Specific failure point identified with evidence

## Evidence Collection Framework

### Mandatory Evidence Items

1. **API State Evidence**:
   ```bash
   # Before sync
   gh api repos/afewell-hh/gitops-test-1/contents/gitops/hedgehog/fabric-1/raw
   
   # After sync  
   gh api repos/afewell-hh/gitops-test-1/contents/gitops/hedgehog/fabric-1/raw
   ```

2. **Screenshot Evidence**:
   - GitHub web interface before sync
   - NetBox fabric detail page
   - Sync button click operation
   - Any response messages
   - GitHub web interface after sync

3. **Console/Log Evidence**:
   - Browser console during sync operation
   - Django admin logs (if accessible)
   - Network requests during sync

4. **Timestamp Evidence**:
   - Exact time of sync button click
   - API query timestamps
   - Any file modification timestamps

### Evidence Organization

**File Structure**:
```
/02_implementation/minimal_validation_evidence/
├── baseline_state/
│   ├── github_api_response.json
│   ├── github_web_screenshot.png
│   └── timestamp.txt
├── sync_operation/
│   ├── netbox_interface_screenshots/
│   ├── browser_console_logs.txt
│   └── network_requests.har
└── post_sync_state/
    ├── github_api_response.json
    ├── github_web_screenshot.png
    ├── state_comparison.md
    └── change_detection.json
```

## Test Execution Requirements

### Pre-Test Environment Validation

1. **NetBox Access**: Verify can access fabric detail page
2. **GitHub Access**: Verify API access to repository
3. **Browser Tools**: Ensure can capture console logs and network requests
4. **Screenshot Capability**: Verify can capture and save screenshots

### Test Execution Protocol

1. **Single Session**: All tests in one browser session to maintain consistency
2. **Fresh Page Load**: Reload pages between tests to avoid cache issues
3. **Immediate Evidence**: Capture evidence immediately after each action
4. **Atomic Testing**: Complete one test fully before starting next

### Failure Recovery Protocol

**If Sync Button Not Found**:
- Document exact interface layout
- Search for alternative sync triggers
- Check fabric status for requirements

**If GitHub API Fails**:
- Use web interface screenshots as backup
- Document API error messages
- Check authentication and permissions

**If No State Change Detected**:
- Proceed to failure point identification
- Do not attempt fixes - only document findings
- Provide specific next steps for debugging agent

## Success/Failure Determination

### Clear Success Indicators

1. **File Count Change**: Raw directory file count decreases
2. **File Movement**: Files appear in managed directories
3. **SHA Hash Changes**: File modifications or deletions detected
4. **UI Confirmation**: Success message in NetBox interface

### Clear Failure Indicators

1. **No State Change**: GitHub repository identical before/after
2. **Error Messages**: Explicit error messages in UI or console
3. **Failed Requests**: Network requests return error status
4. **Process Interruption**: Sync operation fails to complete

### Ambiguous Results Protocol

**If results unclear**:
- Document all evidence
- Mark as "inconclusive" not "failed"
- Provide specific additional tests needed
- Do not attempt interpretation beyond evidence

## Handoff Requirements

### For Success Result

**Evidence Package**:
- Complete state change documentation
- Verification that sync worked correctly
- Evidence that problem is already resolved
- Recommendation for comprehensive testing

### For Failure Result

**Evidence Package**:
- Exact failure point identification
- All error messages and logs
- Specific debugging recommendations
- Next specialist agent requirements

### Context Compression for Next Agent

**Critical Information Only**:
- Specific failure point (UI, API, authentication, etc.)
- Error messages and codes
- Working vs. non-working components
- Exact steps to reproduce failure

**External Memory Files**:
- Complete evidence collection
- Detailed API responses
- Full screenshot documentation
- Comprehensive logs and traces

## Agent Specification

### Recommended Agent Type: Test Validation Specialist

**Task Complexity**: 2/5 (within standard capacity)
**Duration**: 35 minutes (well within capacity limits)
**Memory Requirements**: Minimal (step-by-step execution)
**External Memory**: Evidence files for handoff context

### Agent Instructions Template

```markdown
# MINIMAL VALIDATION TASK: FGD Sync Button Testing

## CRITICAL CONTEXT
Previous agents claimed completion without GitHub verification.
Files remain unprocessed in GitHub: prepop.yaml, test-vpc.yaml, test-vpc-2.yaml
Must provide actual evidence of state change or specific failure point.

## TASK SCOPE
Test ONLY the sync button functionality. Do NOT attempt fixes.
Provide evidence-based determination of working vs. failing.

## SUCCESS CRITERIA
- GitHub repository state change documented with API evidence
- OR exact failure point identified with error messages
- All evidence collected and organized per framework

## MANDATORY EVIDENCE
1. Before/after GitHub API responses
2. Screenshots of sync operation  
3. Browser console logs during sync
4. Specific error messages or success indicators

## FAILURE PREVENTION
- Do NOT claim success without GitHub state change proof
- Do NOT attempt code analysis or fixes
- Do NOT assume functionality works based on UI behavior
- Do provide exact failure point if sync doesn't work
```

## Expected Timeline

**Total Duration**: 35-45 minutes
- Test 1: 5 minutes  
- Test 2: 10 minutes
- Test 3: 5 minutes
- Test 4: 15 minutes (if needed)
- Evidence organization: 5 minutes

**Risk Level**: LOW (simple testing, no modifications)
**Success Probability**: HIGH (clear success/failure criteria)

## Next Steps After Validation

**If Tests Show Success**: Verify comprehensive functionality and close issue
**If Tests Show Failure**: Deploy targeted debugging specialist based on specific failure point
**If Tests Inconclusive**: Design additional minimal tests to clarify state

This minimal validation design prevents false completions by requiring actual GitHub state change evidence and provides clear foundation for subsequent debugging if needed.

---

**Status**: Minimal validation design complete  
**Ready for**: Test Validation Specialist deployment  
**Evidence Requirement**: GitHub API verification mandatory for all claims