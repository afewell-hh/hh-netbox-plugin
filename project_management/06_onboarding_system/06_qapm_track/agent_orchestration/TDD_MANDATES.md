# Test-Driven Development Mandates: The QAPM Non-Negotiable

**Purpose**: Enforce TDD as the only acceptable development approach  
**Principle**: No fix without a failing test first—EVER

## The TDD Mandate

As a QAPM, you do not suggest TDD—you REQUIRE it. This mandate, proven in the fabric edit investigation, ensures every fix is verifiable, reproducible, and regression-proof.

## Core TDD Requirements

### The Three Laws of TDD (QAPM Enforced)

1. **Law 1**: You may not write production code until you have written a failing test
2. **Law 2**: You may not write more of a test than is sufficient to fail
3. **Law 3**: You may not write more production code than is sufficient to pass the test

### The QAPM Addition: Evidence Law

**Law 4**: Every test must be accompanied by evidence of:
- The test failing before the fix
- The test passing after the fix
- No other tests broken by the change

## TDD Mandate Framework

### Mandate 1: The Failing Test First

**Requirement**: Before ANY code change, a failing test must exist

**Agent Instruction Template**:
```markdown
MANDATORY TDD APPROACH:

Step 1: Write a test that reproduces the reported issue
- The test MUST fail with the current code
- Capture the failure output as evidence
- The test must be meaningful, not trivial

Step 2: Run the test and document failure
- Show the exact error message
- Include the stack trace
- Timestamp the failure

Step 3: Only then begin implementing the fix

EXAMPLE:
```python
def test_fabric_edit_handles_none_model():
    """Test that edit view handles None model gracefully"""
    view = FabricEditView()
    view.model = None  # This is the reported issue
    
    # This should raise the TypeError we're seeing
    with pytest.raises(TypeError):
        view.get_object()
```

Evidence: Test fails with "TypeError: 'NoneType' object is not callable"
```

### Mandate 2: Minimal Implementation

**Requirement**: Write ONLY enough code to make the test pass

**Agent Instruction Template**:
```markdown
MINIMAL FIX REQUIREMENT:

After confirming test fails:
1. Implement the SMALLEST change that makes the test pass
2. Do not add extra features
3. Do not refactor unrelated code
4. Do not optimize prematurely

EXAMPLE:
```python
# MINIMAL FIX - Just enough to pass the test
def get_object(self):
    if self.model is not None:
        return self.model.objects.get(pk=self.kwargs['pk'])
    raise ValueError("Model not initialized")
```

Evidence: Test now passes, no other changes made
```

### Mandate 3: Verification Evidence

**Requirement**: Prove the TDD cycle was followed correctly

**Required Evidence**:
```markdown
TDD EVIDENCE CHECKLIST:

□ Test failure before fix:
  - Test name: test_fabric_edit_handles_none_model
  - Error: TypeError: 'NoneType' object is not callable
  - Timestamp: 2025-01-23 14:22:15

□ Test success after fix:
  - Same test now: PASSED
  - Execution time: 0.03s
  - Timestamp: 2025-01-23 14:28:42

□ No regressions:
  - Full suite before: 342 passed
  - Full suite after: 343 passed (new test added)
  - No failures introduced
```

### Mandate 4: Test Quality Standards

**Requirement**: Tests must be high-quality and meaningful

**Quality Criteria**:
```markdown
TEST QUALITY REQUIREMENTS:

1. Descriptive Name:
   ✗ test_fix()
   ✓ test_fabric_edit_handles_none_model()

2. Clear Assertion:
   ✗ assert result is not None
   ✓ assert fabric.name == "Updated Fabric Name"

3. Isolated Scope:
   - Test ONE thing
   - No external dependencies
   - Predictable results

4. Documentation:
   """Test that edit view handles None model gracefully.
   
   This reproduces the TypeError reported in issue #123
   where model is None during view initialization.
   """
```

## TDD Enforcement Protocols

### Protocol 1: Agent Instruction Enforcement

```markdown
TDD ENFORCEMENT IN INSTRUCTIONS:

"You MUST follow Test-Driven Development:
1. DO NOT write any fix until you have a failing test
2. If you cannot write a failing test, you don't understand the problem
3. Evidence of test failure is MANDATORY
4. Skipping TDD will result in task rejection

This is not a suggestion—it is a requirement."
```

### Protocol 2: Validation Checklist

```markdown
TDD VALIDATION CHECKLIST:

Before accepting any fix:
□ Is there a new test?
□ Did the test fail first? (evidence required)
□ Does the test pass now? (evidence required)  
□ Is the test meaningful?
□ Are all existing tests still passing?

If any checkbox is not satisfied, REJECT the submission.
```

### Protocol 3: Rejection Template

```markdown
SUBMISSION REJECTED - TDD VIOLATION

Your submission has been rejected because:
□ No failing test was written first
□ No evidence of test failure provided
□ Test appears to be written after the fix
□ Test is trivial/meaningless

REQUIRED ACTIONS:
1. Revert your code changes
2. Write a test that fails with current code
3. Provide evidence of failure
4. Then implement your fix
5. Show test passing after fix

Remember: TDD is not optional in this project.
```

## Real-World TDD Success: Fabric Edit Case Study

### The Problem
```python
# Users reported: TypeError on fabric edit page
# Previous attempts: Fixed symptoms without tests
# Result: Problem persisted
```

### The TDD Solution

**Step 1: Failing Test First**
```python
def test_fabric_edit_view_initialization():
    """Test that FabricEditView handles model initialization correctly"""
    view = FabricEditView()
    view.model = None  # Simulate the error condition
    
    # This test MUST fail first
    with pytest.raises(AttributeError):
        view.get_object()  # This will raise TypeError currently

# Evidence: Test output showing TypeError, not AttributeError
```

**Step 2: Minimal Fix**
```python
def get_object(self):
    """Get object with proper None checking"""
    if self.model is not None:
        return self.model.objects.get(pk=self.kwargs['pk'])
    raise ValueError("Model not initialized")

# Evidence: Test now passes with ValueError as expected
```

**Step 3: Verification**
```bash
# Before fix:
$ pytest test_fabric_edit_view_initialization -v
FAILED - TypeError: 'NoneType' object is not callable

# After fix:
$ pytest test_fabric_edit_view_initialization -v  
PASSED

# Full suite:
$ pytest
343 passed in 12.4s
```

### Why TDD Succeeded

1. **Problem Understanding**: Writing the test forced understanding of the real issue
2. **Focused Fix**: Only changed what was needed to pass the test
3. **Regression Prevention**: Test ensures this specific issue never returns
4. **Evidence Trail**: Clear proof of the problem and solution

## TDD Patterns for Common Scenarios

### Pattern 1: Bug Fix TDD

```markdown
BUG FIX TDD PATTERN:

1. Reproduce bug with failing test
   - Use exact user steps
   - Verify you see same error

2. Make test expectations correct
   - Test should expect success
   - Currently sees failure

3. Fix code minimally
   - Change only what makes test pass
   - No "while we're here" changes

4. Verify and document
   - Test passes
   - Bug cannot recur
   - Evidence collected
```

### Pattern 2: Feature TDD

```markdown
FEATURE TDD PATTERN:

1. Write test for new behavior
   - Test the user need
   - Not implementation details

2. See test fail correctly
   - Should fail because feature missing
   - Not due to syntax errors

3. Implement feature incrementally
   - Make test pass step by step
   - Refactor after green

4. Add edge case tests
   - Error conditions
   - Boundary values
   - Security concerns
```

### Pattern 3: Refactoring TDD

```markdown
REFACTORING TDD PATTERN:

1. Ensure existing tests pass
   - Full suite green
   - Baseline established

2. Refactor with confidence
   - Tests catch any breaks
   - Small incremental changes

3. Keep tests green throughout
   - Run after each change
   - Revert if tests fail

4. Add tests for new structure
   - If refactoring reveals gaps
   - Maintain coverage
```

## TDD Anti-Patterns to Prevent

### Anti-Pattern 1: Test After Development

**Signs**:
- Test passes on first run
- Test mirrors implementation exactly
- No evidence of test failure

**Prevention**:
```markdown
Require screenshot/output of test failing before accepting any code
```

### Anti-Pattern 2: Trivial Tests

**Signs**:
```python
def test_truth():
    assert True  # Meaningless

def test_function_exists():
    assert callable(my_function)  # Not useful
```

**Prevention**:
```markdown
Tests must verify behavior, not existence
Tests must relate to user-facing functionality
```

### Anti-Pattern 3: Test-Driving the Wrong Thing

**Signs**:
- Testing implementation details
- Testing framework functionality
- Testing getters/setters

**Prevention**:
```markdown
Test behavior that users care about
Test at the right level of abstraction
```

### Anti-Pattern 4: Skipping Red Phase

**Signs**:
- No evidence of test failure
- "I knew it would fail"
- Test and implementation in same commit

**Prevention**:
```markdown
Separate commits:
1. "Add failing test for issue #123"
2. "Implement fix for issue #123"
```

## TDD Metrics and Enforcement

### Success Metrics

```markdown
TDD COMPLIANCE DASHBOARD:

Week of Jan 23, 2025:
- Fixes with failing test first: 42/42 (100%)
- Average test-to-fix time: 8 minutes
- Tests that caught regressions: 7
- False positives: 0

Non-Compliance:
- Attempts to skip TDD: 3
- All rejected and re-done with TDD
```

### Enforcement Escalation

```markdown
ESCALATION PROTOCOL:

First Violation:
- Education and coaching
- Pair with TDD expert
- Document learning

Second Violation:
- Formal warning
- TDD training required
- Supervised work

Third Violation:
- Removed from critical paths
- Extensive retraining
- Performance plan
```

## TDD Tools and Resources

### Testing Frameworks
```markdown
APPROVED TESTING TOOLS:

Python:
- pytest (preferred)
- unittest (acceptable)
- doctest (for examples)

JavaScript:
- Jest (preferred)
- Mocha + Chai (acceptable)

Coverage:
- Minimum 80% required
- 90%+ for critical paths
```

### TDD Workflow Tools
```markdown
WORKFLOW OPTIMIZATION:

1. Test Runners:
   - Watch mode for continuous feedback
   - Parallel execution for speed
   - Failure-first ordering

2. IDE Integration:
   - Red/green indicators
   - Inline test running
   - Coverage highlighting

3. Evidence Collection:
   - Screenshot tools
   - Console capture
   - Git hooks for enforcement
```

## Creating a TDD Culture

### Daily Practices

```markdown
DAILY TDD RITUALS:

Morning:
- Review yesterday's TDD evidence
- Plan today's test-first work
- Share TDD wins in standup

During Work:
- Red-Green-Refactor cycle
- Commit tests separately
- Document test failures

Evening:
- Verify all work has tests
- Archive TDD evidence
- Update coverage metrics
```

### Team Reinforcement

```markdown
TDD TEAM PRACTICES:

1. TDD Pair Programming:
   - Navigator ensures test first
   - Driver implements minimal fix
   - Switch roles frequently

2. Code Review Checklist:
   - [ ] Test present and meaningful
   - [ ] Evidence of test failure
   - [ ] Minimal implementation
   - [ ] No test, no merge

3. TDD Champions:
   - Recognize TDD excellence
   - Share success stories
   - Mentor struggling members
```

## The TDD Mandate Contract

Every agent and developer agrees to:

```markdown
TDD MANDATE CONTRACT:

I understand and agree that:

1. I will write no production code without a failing test
2. I will provide evidence of test failure before fixes
3. I will implement only enough to make tests pass
4. I will maintain and improve test coverage
5. I understand TDD is mandatory, not optional

Violation of this mandate will result in:
- Work rejection
- Required resubmission with TDD
- Additional training if patterns persist

Signed: _________________
Date: ___________________
```

## Conclusion

Test-Driven Development is not a nice-to-have in QAPM-managed projects—it's the foundation of quality. The fabric edit success proved that TDD catches issues others miss and provides confidence in solutions.

As a QAPM, your role is to be the unwavering champion of TDD. No exceptions, no excuses, no compromise. Every fix starts with a failing test, period.

Remember: Code without tests is legacy code the moment it's written. Don't let legacy code be written on your watch.

---

*"Test-Driven Development is a way of managing fear during programming... TDD is an awareness of the gap between decision and feedback during programming, and control over that gap."* - Kent Beck

Make that gap as small as possible. Test first, always.