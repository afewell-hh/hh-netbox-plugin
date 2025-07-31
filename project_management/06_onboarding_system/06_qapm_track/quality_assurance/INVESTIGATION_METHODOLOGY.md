# Investigation Methodology: The QAPM Systematic Approach

**Purpose**: Master systematic investigation techniques that uncover root causes  
**Principle**: Trust nothing, verify everything, document all findings

## The QAPM Investigation Philosophy

> "The first report is always wrong. The second might be incomplete. Only systematic investigation reveals truth."

This methodology, proven in the fabric edit investigation, ensures you find the real problems, not just the reported symptoms.

## The Five Phases of Investigation

### Phase 1: Initial Assessment (Trust Nothing)

**Objective**: Establish ground truth independent of all reports

**Steps**:
```markdown
1. IGNORE ALL PREVIOUS REPORTS (temporarily)
2. Test the system yourself
3. Document what actually happens
4. Compare with reported behavior
5. Identify discrepancies
```

**Fabric Edit Example**:
```markdown
Reported: "Fabric edit page throws error"
Actual Testing:
- Page loads initially
- Error occurs during form render
- Specific error: TypeError: 'NoneType' object is not callable
- Different from report: Error in render, not page load
- Console shows model=None at initialization
```

**Key Tools**:
- Browser Developer Console
- Network Inspector
- Python Debugger
- Application Logs

### Phase 2: Evidence Collection (Document Everything)

**Objective**: Gather comprehensive evidence before forming theories

**Evidence Categories**:
```markdown
1. Error Evidence
   - Full stack traces
   - Error messages verbatim
   - Timestamp of occurrence
   - User actions that trigger

2. System State Evidence
   - Configuration files
   - Database state
   - Memory usage
   - Active processes

3. Code Evidence
   - Recent commits
   - Deployment history
   - Related pull requests
   - Code coverage gaps

4. Environmental Evidence
   - OS and versions
   - Dependencies installed
   - Network connectivity
   - Resource availability
```

**Documentation Template**:
```markdown
## Investigation Evidence Log

### Error Occurrence
- Time: 2025-01-23 14:22:15 UTC
- User: admin
- Action: Navigate to /fabrics/1/edit/
- Result: TypeError in console
- Screenshot: error_console_142215.png

### Stack Trace
```
File "/app/views/vpc.py", line 437, in get_object
  return self.model.objects.get(pk=self.kwargs['pk'])
AttributeError: 'NoneType' object has no attribute 'objects'
```

### System State
- Python: 3.11.4
- Django: 4.2.1
- NetBox: 4.3.3
- Memory: 4.2GB/8GB
- CPU: 23% utilization
```

### Phase 3: Hypothesis Formation (Multiple Theories)

**Objective**: Develop multiple theories based on evidence, not assumptions

**Hypothesis Framework**:
```markdown
HYPOTHESIS TEMPLATE:

Theory A: [Most Likely]
- Evidence supporting: [List]
- Evidence against: [List]
- Test to confirm: [Specific test]
- Effort to verify: [Low/Medium/High]

Theory B: [Alternative]
- Evidence supporting: [List]
- Evidence against: [List]
- Test to confirm: [Specific test]
- Effort to verify: [Low/Medium/High]

Theory C: [Edge Case]
- Evidence supporting: [List]
- Evidence against: [List]
- Test to confirm: [Specific test]
- Effort to verify: [Low/Medium/High]
```

**Fabric Edit Hypotheses**:
```markdown
Theory A: Model Not Initialized (MOST LIKELY)
- Supporting: self.model is None in traceback
- Against: Other views work fine
- Test: Add debug print for self.model
- Effort: Low

Theory B: Database Connection Issue
- Supporting: Occurs on object fetch
- Against: Other pages load data fine
- Test: Direct database query
- Effort: Medium

Theory C: Permission/Authentication Issue
- Supporting: Happens for some users
- Against: Admin user also affected
- Test: Check with different users
- Effort: Low
```

### Phase 4: Systematic Verification (Test Each Theory)

**Objective**: Methodically test each hypothesis to find root cause

**Verification Protocol**:
```markdown
FOR EACH HYPOTHESIS:

1. Design Specific Test
   - Isolates single variable
   - Produces clear result
   - Reproducible by others

2. Execute Test
   - Document exact steps
   - Capture all output
   - Note unexpected findings

3. Analyze Results
   - Does it confirm/refute hypothesis?
   - What new information emerged?
   - Are there follow-up questions?

4. Document Findings
   - Test performed
   - Results obtained
   - Conclusion reached
   - Next steps identified
```

**Fabric Edit Verification**:
```markdown
Testing Theory A: Model Not Initialized

Test Design:
1. Add logging to view initialization
2. Print self.model value
3. Trace where model should be set

Execution:
```python
class FabricEditView(ObjectEditView):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        print(f"DEBUG: self.model = {self.model}")  # None!
```

Result:
- self.model is None during __init__
- Model not set by parent class as expected
- Found: model set in dispatch() method
- Problem: get_object() called before dispatch()

CONFIRMED: Theory A is root cause
```

### Phase 5: Root Cause Analysis (Go Deep)

**Objective**: Understand not just what failed, but why

**Root Cause Framework**:
```markdown
THE FIVE WHYS:

1. Why did the error occur?
   - self.model was None when accessed

2. Why was self.model None?
   - get_object() called before dispatch()

3. Why was get_object() called early?
   - Template context processor invoked it

4. Why did the context processor invoke it?
   - Recent refactoring changed initialization order

5. Why wasn't this caught in testing?
   - No test for this initialization path

ROOT CAUSE: Initialization order dependency not documented or tested
```

**Documentation Requirements**:
```markdown
ROOT CAUSE REPORT:

Summary:
- Issue: TypeError in fabric edit view
- Root Cause: Model initialization race condition
- Trigger: Context processor calling get_object() early
- Impact: All model edit views potentially affected

Technical Details:
- File: /app/views/vpc.py line 437
- Method: get_object() assumes self.model exists
- Reality: self.model not set until dispatch()
- Fix: Add None check before access

Contributing Factors:
- No defensive programming
- Missing initialization test
- Undocumented method dependencies
```

## Investigation Patterns and Anti-Patterns

### Pattern 1: The Breadcrumb Trail

**Description**: Follow errors systematically back to their source

```markdown
BREADCRUMB INVESTIGATION:

1. Start at the error
   - TypeError at line 437

2. Work backwards
   - What called this method?
   - When is it called?
   - What state is expected?

3. Find the divergence
   - Where reality != expectation
   - Document the gap
   - Identify fix location

4. Verify understanding
   - Can you reproduce reliably?
   - Does fix address root cause?
   - Are there similar issues?
```

### Pattern 2: The Differential Diagnosis

**Description**: Compare working vs. broken to isolate issues

```markdown
DIFFERENTIAL INVESTIGATION:

Working Case: Fabric List View
- URL: /fabrics/
- Model: Set correctly
- Result: Page loads

Broken Case: Fabric Edit View
- URL: /fabrics/1/edit/
- Model: None
- Result: TypeError

Difference Analysis:
- Edit view has different init
- Edit view uses get_object()
- List view doesn't need object

Conclusion: Object fetching is the issue
```

### Pattern 3: The Binary Search

**Description**: Systematically narrow down problem location

```markdown
BINARY SEARCH INVESTIGATION:

1. Does basic page load work? YES
2. Does view initialization work? YES
3. Does model get set? NO - Found issue level
4. First half of init? YES
5. Second half of init? NO
6. Line by line in second half...
7. Found: Line 437 is the culprit
```

### Anti-Pattern 1: The Assumption Jump

**Wrong Approach**:
"User says login is broken, must be authentication system"

**Right Approach**:
"Let me test login myself and see what actually happens"

### Anti-Pattern 2: The First Theory Fixation

**Wrong Approach**:
"It's probably a cache issue" *spends hours on cache*

**Right Approach**:
"Here are three theories, let me test each systematically"

### Anti-Pattern 3: The Fix Without Understanding

**Wrong Approach**:
"Adding try/except fixed it, ship it!"

**Right Approach**:
"Why was the exception happening? What's the root cause?"

## Investigation Tools and Techniques

### Debugging Tools Arsenal

```markdown
ESSENTIAL INVESTIGATION TOOLS:

Python Debugging:
- pdb.set_trace() - Interactive debugging
- print() debugging - Quick visibility
- logging module - Persistent traces
- traceback module - Stack analysis

Django Specific:
- Django Debug Toolbar
- django-extensions shell_plus
- Django logging configuration
- Management command debugging

Browser Tools:
- Console for JavaScript errors
- Network tab for requests
- Elements for DOM inspection
- Performance for timing issues

System Tools:
- htop - Process monitoring
- tail -f - Live log viewing
- tcpdump - Network analysis
- strace - System call tracing
```

### Investigation Notebooks

**Purpose**: Document investigation in reproducible format

```markdown
# Investigation Notebook: Fabric Edit Error

## Setup
```python
from netbox_hedgehog.views.vpc import FabricEditView
from django.test import RequestFactory
```

## Test 1: Direct Instantiation
```python
view = FabricEditView()
print(f"Model after init: {view.model}")
# Result: None
```

## Test 2: With Request Context
```python
factory = RequestFactory()
request = factory.get('/fabrics/1/edit/')
view = FabricEditView()
view.setup(request, pk=1)
print(f"Model after setup: {view.model}")
# Result: Still None
```

## Test 3: Full Dispatch
```python
response = view.dispatch(request, pk=1)
print(f"Model after dispatch: {view.model}")
# Result: <class 'netbox_hedgehog.models.Fabric'>
```

## Conclusion
Model is set during dispatch(), not init or setup
```

### Evidence Archive Structure

```markdown
investigations/
├── 2025-01-23_fabric_edit_error/
│   ├── 01_initial_assessment/
│   │   ├── error_screenshot.png
│   │   ├── console_output.txt
│   │   └── user_report.md
│   ├── 02_evidence_collection/
│   │   ├── stack_traces/
│   │   ├── system_state/
│   │   └── code_history/
│   ├── 03_hypothesis_testing/
│   │   ├── theory_a_test.py
│   │   ├── theory_b_results.md
│   │   └── theory_c_eliminated.md
│   ├── 04_root_cause/
│   │   ├── five_whys.md
│   │   ├── technical_details.md
│   │   └── fix_approach.md
│   └── 05_resolution/
│       ├── implemented_fix.diff
│       ├── test_results.txt
│       └── validation_evidence/
```

## Creating an Investigation Culture

### Team Practices

```markdown
INVESTIGATION TEAM STANDARDS:

1. Blameless Post-Mortems
   - Focus on systems, not people
   - Share learning openly
   - Document for future

2. Investigation Pairing
   - Two perspectives find more
   - Knowledge transfer
   - Built-in verification

3. Investigation Time-Boxing
   - 2-hour initial investigation
   - Decision: continue or escalate
   - Avoid rabbit holes

4. Evidence Sharing Sessions
   - Weekly investigation reviews
   - Share interesting findings
   - Build team knowledge
```

### Investigation Metrics

```markdown
INVESTIGATION KPIs:

Efficiency Metrics:
- Time to root cause: < 4 hours
- First theory accuracy: > 60%
- Evidence completeness: 100%

Quality Metrics:
- Root cause found: > 95%
- Recurrence rate: < 5%
- Fix effectiveness: > 98%

Learning Metrics:
- New patterns documented
- Team knowledge shared
- Process improvements made
```

## The Investigation Checklist

```markdown
□ PHASE 1: INITIAL ASSESSMENT
  □ Tested issue personally
  □ Documented actual behavior
  □ Compared with reports
  □ Identified discrepancies

□ PHASE 2: EVIDENCE COLLECTION
  □ Gathered error evidence
  □ Captured system state
  □ Reviewed code history
  □ Checked environment

□ PHASE 3: HYPOTHESIS FORMATION
  □ Created multiple theories
  □ Listed supporting evidence
  □ Designed verification tests
  □ Prioritized by likelihood

□ PHASE 4: SYSTEMATIC VERIFICATION
  □ Tested each hypothesis
  □ Documented results
  □ Eliminated false paths
  □ Confirmed root cause

□ PHASE 5: ROOT CAUSE ANALYSIS
  □ Applied Five Whys
  □ Documented technical details
  □ Identified contributing factors
  □ Created fix approach

□ RESOLUTION
  □ Implemented fix
  □ Verified solution
  □ Prevented recurrence
  □ Shared learnings
```

## Conclusion

Great investigations are systematic, evidence-based, and thorough. They question everything, assume nothing, and document all findings. The fabric edit investigation succeeded because we didn't trust the initial report—we dug deeper and found the real issue.

As a QAPM, your investigation skills determine whether issues get truly fixed or merely patched. Use this methodology to uncover root causes, not just symptoms.

Remember: Every bug has a story. Your job is to be the detective who uncovers it.

---

*"It is a capital mistake to theorize before one has data. Insensibly one begins to twist facts to suit theories, instead of theories to suit facts."* - Sherlock Holmes (Arthur Conan Doyle)

Let evidence lead your investigation, not assumptions.