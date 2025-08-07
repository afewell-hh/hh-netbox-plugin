# 🎯 HIVE MIND INSTRUCTIONS - ATTEMPT #14
## FGD Sync Resolution - Systematic Multi-Phase Analysis Required

**Context**: 13 consecutive agents have failed to resolve FGD sync, all falling into the same pattern of premature solution confidence and insufficient analysis depth.

**FUNDAMENTAL ASSUMPTION**: This is a COMPLEX, MULTI-ISSUE problem requiring SYSTEMATIC, THOROUGH analysis. Any agent believing they found "the solution" early is almost certainly wrong.

## 📋 MANDATORY EXECUTION FRAMEWORK

### 🚫 ANTI-PATTERN AWARENESS
**YOU MUST ASSUME**: Previous agents failed because they:
- Found one issue and stopped looking
- Underestimated problem complexity  
- Implemented solutions without complete analysis
- Claimed success without validation
- Ignored thorough analysis requirements

**CRITICAL**: If you feel confident you found "the solution" early in analysis, you are likely experiencing the same cognitive bias that caused 13 failures.

### 🔬 PHASE 1: SYSTEMATIC DISCOVERY (MANDATORY)
**REQUIREMENT**: Create a comprehensive analysis report as GitHub issue comment BEFORE any implementation.

#### 1A. Environment & Baseline Establishment
- **Delete all existing fabric records** from NetBox to ensure clean test environment
- Load environment from `/home/ubuntu/cc/hedgehog-netbox-plugin/.env` (not preloaded)
- Review `/home/ubuntu/cc/hedgehog-netbox-plugin/project_management/06_onboarding_system/04_environment_mastery` for lab details
- Run baseline tests:
  ```bash
  python3 test_fgd_presync_state_v2.py  # Should pass
  python3 test_fgd_postsync_state_v2.py # Should fail (no sync yet)
  ```

#### 1B. Multi-Layer Architecture Analysis
**EXPECTATION**: Find MULTIPLE issues, not just one. Analyze each layer:

1. **Django Integration Layer**
   - Are services properly registered/imported?
   - Are signal handlers connected correctly?  
   - Are there missing migrations or model issues?
   - What happens during Django startup?

2. **Service Implementation Layer**
   - Which services exist vs. which are actually called?
   - Are there circular import issues?
   - What's the actual execution path for sync operations?
   - Are there configuration/authentication failures?

3. **GitHub Integration Layer**
   - Is the GitHub API actually being called?
   - Are authentication tokens accessible and valid?
   - Are file operations succeeding or failing silently?
   - Is rate limiting or API versioning causing issues?

4. **Workflow Orchestration Layer**
   - When user creates/edits CRs, what actually executes?
   - Are there race conditions or async issues?
   - Which components are missing from the workflow?
   - Are there state management problems?

#### 1C. Failed Agent Retrospective Analysis
**REQUIRED READING**:
- Issue #3 comments: All previous agent attempts and retrospectives
- Focus on: What did each agent think they fixed vs. what actually remained broken

#### 1D. Evidence Collection Requirements
For EACH potential issue found:
- **Direct Evidence**: Logs, error messages, actual behavior
- **Test Validation**: How would you prove this specific issue is fixed?
- **Impact Scope**: What other components could this affect?
- **Fix Complexity**: Simple config change vs. architectural rework?

### 🎯 PHASE 1 DELIVERABLE: COMPREHENSIVE ANALYSIS REPORT
**POST AS GITHUB ISSUE COMMENT** containing:

```markdown
## SYSTEMATIC FGD SYNC ANALYSIS REPORT

### Executive Summary
- [Total issues identified]: X
- [Complexity assessment]: Low/Medium/High/Critical
- [Estimated fix phases]: X phases required

### Issue Catalog
For each issue:
#### Issue #X: [Title]
- **Layer**: Django/Service/GitHub/Workflow
- **Evidence**: [Direct evidence of this issue]
- **Test Plan**: [How to validate fix]
- **Dependencies**: [What must be fixed first]
- **Risk Assessment**: [Impact if not fixed]

### Implementation Strategy
- **Phase sequence**: What order to fix issues
- **Validation checkpoints**: Tests to run after each phase
- **Rollback plan**: How to undo if phase fails

### Success Criteria
- `test_fgd_presync_state_v2.py` passes initially
- After sync implementation: `test_fgd_postsync_state_v2.py` passes
- Actual GitHub repository shows 0 CRs in raw/, 48 CRs in managed/

**WAIT FOR HUMAN APPROVAL BEFORE PROCEEDING TO PHASE 2**
```

### 🔧 PHASE 2: SYSTEMATIC IMPLEMENTATION (ONLY AFTER APPROVAL)
**REQUIREMENT**: Fix issues in planned sequence with validation at each step.

#### 2A. Create Test Fabric
- Add new fabric record in NetBox using test FGD repository
- **Repository**: `https://github.com/afewell-hh/gitops-test-1`
- **FGD Path**: `gitops/hedgehog/fabric-1`
- **GitHub Token**: From `.env` file
- **Validation**: Fabric saves successfully and shows in NetBox UI

#### 2B. Implementation Protocol
For EACH issue from Phase 1:
1. **Implement fix** for single issue only
2. **Test immediately**: Run validation tests
3. **Document result**: What changed in repository state
4. **Log evidence**: Capture actual behavior changes
5. **Continue or rollback**: Only proceed if test shows progress

#### 2C. Final Validation Requirements
**MANDATORY SUCCESS CRITERIA**:
```bash
# 1. Pre-sync test passes
python3 test_fgd_presync_state_v2.py
# Output: 5/5 tests passed

# 2. Trigger sync by creating/editing CR in NetBox GUI

# 3. Post-sync test passes  
python3 test_fgd_postsync_state_v2.py
# Output: 4/4 tests passed

# 4. GitHub repository verification
# Visit: https://github.com/afewell-hh/gitops-test-1/tree/main/gitops/hedgehog/fabric-1
# Verify: raw/ contains only .gitkeep, managed/ contains 48 YAML files
```

## 🚨 COGNITIVE BIAS COUNTERMEASURES

### Anti-Pattern #1: "Found The Solution" Early
**COUNTER**: If you think you found "the solution" in first 30 minutes, you are wrong. This problem has stumped 13 competent agents. Keep analyzing.

### Anti-Pattern #2: Skipping Analysis Phase  
**COUNTER**: Phase 2 (implementation) is BLOCKED until Phase 1 (analysis report) is approved. No exceptions.

### Anti-Pattern #3: Assuming Simple Fix
**COUNTER**: Plan for MULTIPLE issues. If your analysis finds only 1-2 issues, you haven't looked deep enough.

### Anti-Pattern #4: Implementation Without Validation
**COUNTER**: Every fix must show measurable progress in test results. No "it looks right in code" validations.

## 📊 VALIDATED TEST FRAMEWORK
**Use these proven tests** (created in Issue #3):
- `test_fgd_presync_state_v2.py` - Validates starting state
- `test_fgd_postsync_state_v2.py` - Validates success state  
- `fgd_cr_counter.py` - Fuzzy CR counting logic

**DO NOT** create new tests. Use these validated ones.

## 🎯 SUCCESS DEFINITION
**ONLY claim success when**:
1. ✅ Phase 1 analysis report completed and approved
2. ✅ NetBox fabric configured with test FGD  
3. ✅ CR create/edit in NetBox triggers sync
4. ✅ `test_fgd_postsync_state_v2.py` passes (4/4 tests)
5. ✅ GitHub repository shows actual file migration (raw/ → managed/)

## 📖 REFERENCE MATERIALS
- **Previous Failures**: Issue #3 (13 agent attempts and retrospectives)
- **Environment Details**: `project_management/06_onboarding_system/04_environment_mastery`
- **Test Framework**: Files in root directory with `test_fgd_*` prefix
- **Validated FGD**: `https://github.com/afewell-hh/gitops-test-1/tree/main/gitops/hedgehog/fabric-1`

## 🔥 MISSION CRITICAL
This is attempt #14. The previous 13 agents all failed the same way. **DO NOT** repeat their mistakes. **DO NOT** claim success without passing the validated test framework. **DO NOT** underestimate the complexity of this problem.

Your success depends on systematic, thorough analysis followed by careful, validated implementation.

## 💡 WHY PREVIOUS INSTRUCTIONS FAILED

### The Pattern That Must Be Broken:
1. Agent reads issue, thinks "this looks straightforward"
2. Finds one plausible issue (like broken GitOpsEditService) 
3. Gets excited about "finding the solution"
4. Rushes to implement without thorough analysis
5. Ignores instructions about comprehensive analysis
6. Claims success based on code quality, not test results
7. Never validates against actual repository state

### How These Instructions Counter The Pattern:
1. **Explicit Cognitive Bias Warning**: Tell agents they will feel overconfident
2. **Mandatory Phases**: Cannot skip to implementation without approval
3. **Multiple Issue Expectation**: Must find MULTIPLE problems, not just one
4. **Evidence Requirements**: Must provide direct proof for each issue
5. **Test-Driven Success**: Only test results count, not code inspection
6. **Human Approval Gate**: Cannot proceed without oversight
7. **Validated Framework**: Use proven tests, don't create new ones

### Key Psychological Elements:
- **Humility Induction**: "13 competent agents failed" - you're not special
- **Complexity Emphasis**: This is HARD, not simple
- **Expectation Setting**: Plan for multiple issues and phases  
- **Validation Obsession**: Tests are the only truth
- **Progress Gates**: Cannot skip ahead to "fun" implementation phase

## 🎯 INSTRUCTIONS DESIGNED TO SUCCEED

These instructions are crafted to force systematic, thorough analysis and prevent the cognitive biases that caused 13 consecutive failures. The key is separating analysis from implementation and requiring human approval before proceeding to "fix" anything.