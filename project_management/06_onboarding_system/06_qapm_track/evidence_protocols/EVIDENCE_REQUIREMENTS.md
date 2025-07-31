# Evidence Requirements: The QAPM Standard

**Purpose**: Define what constitutes valid evidence for task completion  
**Principle**: No trust without proof, no completion without evidence

## Evidence Categories

### 1. Technical Implementation Evidence

**Definition**: Proof that code changes were made correctly and function as intended.

**Required Elements**:
- **File paths** with specific line numbers modified
- **Git commits** with descriptive messages
- **Code diffs** showing before and after states
- **Syntax validation** proving no errors introduced
- **Unit test results** for modified components

**Example from Fabric Edit**:
```markdown
EVIDENCE PROVIDED:
- Modified: /netbox_hedgehog/views/vpc.py line 437
- Git commit: c7059e1 "Fix critical TypeError in fabric edit page"
- Added null check: if self.model is not None
- Unit tests: test_fabric_edit_view.py passing (5 tests)
- No Python syntax errors in modified files
```

**Red Flags**:
- Vague descriptions like "fixed the bug"
- Missing file paths or line numbers
- No test results provided
- Commits without descriptive messages

### 2. Functional Validation Evidence

**Definition**: Proof that the feature/fix works as intended in the runtime environment.

**Required Elements**:
- **Screenshots** of working functionality
- **HTTP responses** showing success codes
- **Console output** demonstrating no errors
- **Database queries** confirming data persistence
- **API responses** with correct data

**Example from Fabric Edit**:
```markdown
EVIDENCE PROVIDED:
- Screenshot: Fabric edit form fully rendered with all fields
- HTTP GET /plugins/netbox_hedgehog/fabrics/1/edit/ → 200 OK
- Console: No JavaScript errors, all resources loaded
- Database: Fabric object id=1 loaded successfully
- Form submission: POST successful, data persisted
```

**Quality Standards**:
- Screenshots must show full context (URL bar, full form)
- HTTP responses must include headers and status
- Console output must be complete, not filtered
- Timestamps must be visible for correlation

### 3. User Experience Evidence

**Definition**: Proof that real users can successfully complete their intended tasks.

**Required Elements**:
- **Complete workflow testing** from login to task completion
- **Authentication validation** ensuring proper access control
- **Form interaction** proving all inputs work correctly
- **Error handling** showing graceful failure modes
- **Performance metrics** confirming acceptable response times

**Example from Fabric Edit**:
```markdown
EVIDENCE PROVIDED:
- User login → Navigate to Fabrics → Click Edit → Form loads: SUCCESS
- All form fields accept input and validate correctly
- Save button enabled and functional
- Success message displayed after save
- Redirected to fabric detail page with updated data
- Entire workflow completed in <3 seconds
```

**Validation Checklist**:
- [ ] Can a new user complete the task?
- [ ] Do all interactive elements work?
- [ ] Are error messages helpful?
- [ ] Is the workflow intuitive?
- [ ] Does it work on different browsers?

### 4. Integration Validation Evidence

**Definition**: Proof that the feature works correctly with all connected systems.

**Required Elements**:
- **API integration tests** with external systems
- **Database transaction logs** showing data flow
- **Event propagation** to message queues or webhooks
- **Cache invalidation** confirming data freshness
- **Monitoring alerts** showing no degradation

**Example from Fabric Edit**:
```markdown
EVIDENCE PROVIDED:
- NetBox API: GET/PUT operations successful
- PostgreSQL: Transactions completed without rollback
- Redis cache: Fabric data invalidated after edit
- Webhook: Change notification sent to monitoring
- No performance degradation in APM metrics
```

### 5. Regression Prevention Evidence

**Definition**: Proof that the fix doesn't break existing functionality.

**Required Elements**:
- **Full test suite execution** with 100% pass rate
- **New test cases** specifically for the fixed issue
- **Adjacent feature testing** confirming no side effects
- **Performance benchmarks** showing no degradation
- **Backward compatibility** verification

**Example from Fabric Edit**:
```markdown
EVIDENCE PROVIDED:
- Full test suite: 342 tests passed, 0 failed
- New test: test_fabric_edit_handles_none_model()
- Related features tested: Fabric create, delete, list all working
- Page load time: 250ms (baseline: 245ms) - acceptable
- API compatibility: v1 and v2 endpoints both functional
```

## Evidence Collection Best Practices

### 1. Contemporaneous Documentation

**Principle**: Collect evidence as you work, not after

**Practice**:
- Take screenshots immediately upon success
- Save console output before clearing
- Commit code with descriptive messages in real-time
- Document test results as they complete

### 2. Independent Verification

**Principle**: Evidence should be reproducible by others

**Practice**:
- Include all steps to reproduce results
- Use incognito/private browsing for clean tests
- Test with different user accounts
- Verify on multiple environments

### 3. Comprehensive Coverage

**Principle**: Evidence should cover all aspects of completion

**Practice**:
- Technical + Functional + UX + Integration
- Happy path + Error cases
- Different user personas
- Various data scenarios

### 4. Clear Presentation

**Principle**: Evidence should be easily understood

**Practice**:
- Use descriptive filenames for screenshots
- Annotate images to highlight key elements
- Format logs for readability
- Summarize key findings

## Evidence Quality Rubric

### Excellent Evidence
- Comprehensive coverage of all aspects
- Clear, annotated screenshots with context
- Complete test results with coverage metrics
- User journey documentation with timings
- Reproduction steps for verification

### Acceptable Evidence
- Covers main functionality proof
- Basic screenshots provided
- Key test results included
- User workflow validated
- Some context provided

### Insufficient Evidence
- Vague descriptions without proof
- Missing key validation aspects
- No user experience validation
- Incomplete test coverage
- Cannot be independently verified

## Common Evidence Failures

### 1. The "Works on My Machine" Syndrome
**Problem**: Evidence from development environment only  
**Solution**: Always validate in environment matching production

### 2. The "Happy Path Only" Testing
**Problem**: Only testing successful scenarios  
**Solution**: Include error cases and edge conditions

### 3. The "Technical Only" Validation
**Problem**: Proving code works but not user experience  
**Solution**: Always include end-to-end user testing

### 4. The "Trust Me" Report
**Problem**: Claims without supporting evidence  
**Solution**: No claim accepted without proof

## Evidence Templates

### Bug Fix Evidence Template
```markdown
## Bug Fix Evidence

### 1. Problem Reproduction
- Steps to reproduce: [detailed steps]
- Error observed: [screenshot/logs]
- Environment: [where reproduced]

### 2. Root Cause Analysis
- Code investigation: [file:line with issue]
- Why it failed: [technical explanation]
- Test proving failure: [test name and result]

### 3. Solution Implementation
- Code changes: [files modified with diffs]
- Git commit: [commit hash and message]
- Test now passing: [test results]

### 4. Validation
- Screenshot of fixed functionality: [image]
- User workflow test: [step-by-step validation]
- No regressions: [full test suite results]
```

### Feature Implementation Evidence Template
```markdown
## Feature Implementation Evidence

### 1. Technical Implementation
- Files created/modified: [complete list]
- Database changes: [migrations/schema]
- API endpoints: [new/modified endpoints]
- Tests created: [test files and coverage]

### 2. Functional Validation
- Feature demo: [screenshots/video]
- API testing: [request/response examples]
- Data persistence: [database verification]
- Integration points: [external system validation]

### 3. User Experience
- User journey: [complete workflow test]
- Performance: [load time metrics]
- Accessibility: [WCAG compliance check]
- Cross-browser: [tested browsers/versions]

### 4. Production Readiness
- Monitoring configured: [metrics/alerts]
- Documentation updated: [user/API docs]
- Rollback plan: [how to revert if needed]
- Feature flags: [gradual rollout strategy]
```

## Conclusion

Evidence is the currency of trust in the QAPM role. Without it, we have only promises and hopes. With it, we have proof of excellence and user success. Always err on the side of over-documentation—it's better to have too much evidence than to face a false completion claim.

Remember: If it's not documented with evidence, it didn't happen.