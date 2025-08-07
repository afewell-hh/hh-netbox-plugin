# Ultra-Rigorous QAPM Requirements - Attempt 2

**QAPM**: Claude Code (Learning from Failed Attempt 1)  
**Project**: GitOps Sync Fix - REAL Implementation Required  
**Rigor Level**: ULTRA-HIGH (Due to agent false completion tendency)

## 🚨 DEFINITIVE EVIDENCE REQUIREMENTS

### MANDATORY BEFORE/AFTER GITHUB PROOF
Every agent MUST provide:

1. **BEFORE Screenshot**: Current GitHub raw/ directory showing 4 unprocessed files
   - URL: https://github.com/afewell-hh/gitops-test-1/tree/main/gitops/hedgehog/fabric-1/raw
   - Must show: .gitkeep, prepop.yaml, test-vpc-2.yaml, test-vpc.yaml
   - Timestamp required for verification

2. **AFTER Screenshot**: GitHub directories after sync operation
   - Raw/ directory: MUST be empty or only contain .gitkeep
   - Managed/ subdirectories: MUST contain processed YAML files
   - File timestamps: MUST show recent processing

3. **HNP Database Evidence**: Query results showing imported CRD records
   - Before: Count of existing records by type
   - After: Count showing new records from YAML import
   - Specific records: Show actual data from imported YAML files

### MANDATORY FUNCTIONAL TESTING
Every agent MUST:

1. **Actually Run the Sync Operation**
   - Start NetBox: `python3 manage.py runserver`
   - Navigate to fabric page
   - Click sync button or trigger sync API
   - Capture complete operation logs

2. **Verify File Processing**
   - Confirm YAML files parsed successfully
   - Show database records created from YAML content
   - Verify files moved/deleted from raw/ directory

3. **Document Complete Workflow**
   - User login → navigate → sync → results
   - Error handling if sync fails
   - Success confirmation if sync works

## 🛡️ QAPM PERSONAL VALIDATION REQUIREMENTS

**I (QAPM) will personally validate EVERY piece of evidence:**

1. **GitHub Repository Verification**
   - I will check GitHub repository state before agent work
   - I will check GitHub repository state after agent claims
   - I will compare before/after states myself

2. **Evidence Cross-Validation**
   - All screenshots must be independently verifiable
   - All database evidence must be reproducible
   - All claims must be backed by definitive proof

3. **Functional Testing by Me**
   - I will attempt to reproduce all agent claims
   - I will run the sync operation myself if needed
   - I will verify the end-to-end workflow personally

## 🚫 ZERO TOLERANCE POLICIES

### Automatic Rejection Triggers
- Any claim without definitive before/after GitHub evidence
- Any "should work" or "appears to work" language
- Any request for user to test without agent having tested first
- Any technical changes without functional validation proof
- Any completion claim without end-to-end workflow evidence

### Mandatory Evidence Standards
- Screenshots must include timestamps and full context
- Database queries must show exact record counts and content
- File operations must show complete directory listings
- Error logs must be complete and unexpurgated
- Success claims must be backed by verifiable results

## 🎯 SUCCESS CRITERIA - NO EXCEPTIONS

**The ONLY acceptable completion is when ALL of the following are true:**

1. **GitHub Repository State**:
   - Raw/ directory: Empty of processable YAML files (may contain .gitkeep)
   - Managed/ directories: Contain processed YAML files with recent timestamps
   - File evidence: Clear before/after comparison showing processing

2. **HNP Database State**:
   - New CRD records: Created from YAML file content
   - Record count: Increased by expected number from processed files
   - Data validation: Records contain data from YAML files

3. **User Workflow**:
   - Sync operation: Successfully triggers and completes
   - User feedback: Clear success/error messaging
   - Reproducible: Can be repeated with consistent results

## 📋 AGENT INSTRUCTION TEMPLATE

```markdown
CRITICAL: You MUST provide DEFINITIVE PROOF of completion before claiming success.

MANDATORY EVIDENCE REQUIREMENTS:
1. BEFORE GitHub Screenshot: Raw/ directory with 4 files - timestamp required
2. AFTER GitHub Screenshot: Raw/ empty, managed/ with processed files - timestamp required  
3. HNP Database Evidence: Before/after record counts with actual data
4. Complete Workflow Documentation: Login → sync → results with screenshots
5. Error/Success Logs: Complete output from sync operation

ABSOLUTE PROHIBITIONS:
- NO claims without GitHub before/after evidence
- NO "should work" or "appears working" language
- NO requests for others to test your work
- NO technical changes without functional proof
- NO completion claims without end-to-end validation

YOUR WORK IS NOT COMPLETE UNTIL:
- GitHub repository shows files actually processed
- HNP database shows records actually imported
- Complete user workflow actually functions
- All evidence is independently verifiable
```

## 🔄 QAPM VALIDATION CHECKLIST

Before accepting ANY agent work:
- [ ] GitHub before/after screenshots provided and verified
- [ ] Database evidence shows actual record creation
- [ ] Functional workflow documented completely
- [ ] All evidence independently verified by me
- [ ] End-to-end operation tested and confirmed
- [ ] No claims without definitive proof accepted

**This time we get it RIGHT with REAL evidence and REAL results.**