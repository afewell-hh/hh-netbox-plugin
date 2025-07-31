# Proof Standards: The QAPM Evidence Benchmark

**Purpose**: Define the quality bar for acceptable evidence  
**Principle**: Evidence must be indisputable, reproducible, and comprehensive

## The QAPM Evidence Hierarchy

### Level 1: Indisputable Technical Proof
**Standard**: Evidence that cannot be argued against or misinterpreted

**Requirements**:
- Actual code with file paths and line numbers
- Git commits with hashes and timestamps
- Syntax validation results
- Unit test outputs with coverage metrics

**Example of Excellent Proof**:
```markdown
CODE CHANGE PROOF:
- File: /netbox_hedgehog/views/vpc.py
- Lines: 436-441
- Git commit: c7059e1
- Diff:
  ```python
  - def get_object(self):
  -     return self.model.objects.get(pk=self.kwargs['pk'])
  + def get_object(self):
  +     if self.model is not None:
  +         return self.model.objects.get(pk=self.kwargs['pk'])
  +     raise ValueError("Model not initialized")
  ```
- Syntax check: ✓ No errors
- Unit test: test_fabric_edit_none_check() PASSED
```

**Example of Insufficient Proof**:
```markdown
"Fixed the bug in the view file"  // No specifics
"Tests are passing"              // Which tests?
"Code looks good"               // No evidence
```

### Level 2: Verifiable Functional Proof
**Standard**: Evidence that can be independently reproduced

**Requirements**:
- Screenshots with full browser context
- HTTP request/response logs
- Console output with timestamps
- Database state verification
- Step-by-step reproduction guides

**Example of Excellent Proof**:
```markdown
FUNCTIONAL PROOF:
- Screenshot: fabric_edit_working.png
  - Shows: Full form rendered at /fabrics/1/edit/
  - Browser: Chrome 120.0.6099.130
  - Timestamp: 2025-01-23 14:23:45 UTC
  
- HTTP Transaction:
  GET /plugins/netbox_hedgehog/fabrics/1/edit/
  Response: 200 OK
  Headers: Content-Type: text/html; charset=utf-8
  Time: 234ms
  
- Console: No errors (console_clean.png)

- Database Query Log:
  SELECT * FROM hedgehog_fabric WHERE id=1;
  Result: 1 row returned in 0.003s
```

**Example of Insufficient Proof**:
```markdown
"Page loads fine"              // No screenshot
"No errors"                   // No console evidence
"Form works"                  // No interaction proof
```

### Level 3: Comprehensive User Journey Proof
**Standard**: Evidence showing end-to-end user success

**Requirements**:
- Complete workflow documentation
- Multiple user persona testing
- Cross-browser validation
- Performance metrics
- Accessibility compliance

**Example of Excellent Proof**:
```markdown
USER JOURNEY PROOF:

Admin User Workflow:
1. Login: admin/*** → Dashboard (screenshot_1.png)
2. Navigate: Plugins → Hedgehog → Fabrics (screenshot_2.png)
3. Select: "Production Fabric" → Detail page (screenshot_3.png)
4. Click: Edit button → Edit form loads (screenshot_4.png)
5. Modify: Change description field (screenshot_5.png)
6. Save: Click save → Success message (screenshot_6.png)
7. Verify: Detail page shows updated data (screenshot_7.png)

Time: 8.3 seconds total
Browsers tested: Chrome ✓, Firefox ✓, Safari ✓
Mobile tested: iOS Safari ✓, Chrome Android ✓

Read-Only User Test:
- Edit button correctly hidden (screenshot_8.png)
- Direct URL access denied (403_forbidden.png)
```

**Example of Insufficient Proof**:
```markdown
"Users can edit fabrics"       // No workflow shown
"Tested on Chrome"            // Only one browser
"Permissions work"            // No evidence
```

### Level 4: Integration Ecosystem Proof
**Standard**: Evidence of proper system-wide functionality

**Requirements**:
- API endpoint verification
- External system integration
- Event propagation confirmation
- Cache invalidation proof
- Monitoring system validation

**Example of Excellent Proof**:
```markdown
INTEGRATION PROOF:

NetBox API:
- GET /api/plugins/hedgehog/fabrics/1/
  Response: 200 OK, JSON payload correct
- PUT /api/plugins/hedgehog/fabrics/1/
  Response: 200 OK, Data updated

Kubernetes Sync:
- CRD Update triggered: timestamp 14:24:01
- Git commit created: abc123f
- ArgoCD sync: Successful at 14:24:15

Cache Layer:
- Redis key hedgehog:fabric:1 invalidated
- New data fetched on next request
- TTL properly set to 3600s

Monitoring:
- No error spike in Grafana
- Response time within SLA
- No alerts triggered
```

### Level 5: Regression Prevention Proof
**Standard**: Evidence that quality is maintained

**Requirements**:
- Full test suite execution
- Performance benchmarks
- Security scan results
- Backward compatibility verification
- Load testing results

**Example of Excellent Proof**:
```markdown
REGRESSION PREVENTION PROOF:

Test Suite:
- Total tests: 345
- Passed: 345
- Failed: 0
- Coverage: 94.2%
- New tests added: 3

Performance:
- Page load: 234ms (baseline: 230ms) ✓
- API response: 45ms (baseline: 50ms) ✓
- Memory usage: 128MB (baseline: 125MB) ✓

Security:
- OWASP ZAP scan: No new vulnerabilities
- SQL injection test: Protected
- XSS test: Properly escaped

Compatibility:
- NetBox 4.3.3: ✓
- Python 3.11: ✓
- PostgreSQL 15: ✓
```

## Proof Quality Rubric

### Platinum Standard (Score: 10/10)
- All five levels of proof provided
- Evidence is timestamped and annotated
- Reproduction steps included
- Multiple validation perspectives
- Archived for future reference

### Gold Standard (Score: 8/10)
- Technical and functional proof complete
- User journey validated
- Some integration testing shown
- Good screenshot quality
- Clear documentation

### Silver Standard (Score: 6/10)
- Basic technical proof provided
- Functional evidence present
- Limited user testing
- Some screenshots included
- Acceptable for low-risk items

### Bronze Standard (Score: 4/10)
- Minimal evidence provided
- Key aspects covered
- Requires follow-up validation
- Only acceptable for trivial changes

### Unacceptable (Score: <4/10)
- Vague or missing evidence
- Cannot be independently verified
- No user perspective
- Trust-based claims

## Evidence Presentation Standards

### Screenshot Requirements
```markdown
SCREENSHOT STANDARDS:
- Full browser window visible
- URL bar must be shown
- Timestamp overlay or system clock visible
- Annotations for key elements
- Descriptive filename: feature_action_result_timestamp.png
```

### Log Output Requirements
```markdown
LOG STANDARDS:
- Include timestamp for each entry
- Show complete error messages
- Include stack traces if present
- Highlight relevant sections
- Provide context before/after
```

### Test Result Requirements
```markdown
TEST RESULT STANDARDS:
- Show command used to run tests
- Include full output, not summary
- Coverage metrics required
- New tests highlighted
- Failure details if any
```

### Code Evidence Requirements
```markdown
CODE EVIDENCE STANDARDS:
- Full file path from project root
- Line numbers for changes
- Before/after comparison
- Syntax highlighting preferred
- Context around changes (±5 lines)
```

## Common Proof Failures and Remedies

### Failure: "Works For Me" Syndrome
**Issue**: Evidence from developer environment only  
**Remedy**: Always provide evidence from staging/production-like environment

### Failure: Cherry-Picked Evidence
**Issue**: Only showing successful cases  
**Remedy**: Include edge cases and error scenarios

### Failure: Outdated Evidence
**Issue**: Screenshots from previous versions  
**Remedy**: Always capture fresh evidence with timestamps

### Failure: Incomplete Context
**Issue**: Cropped screenshots hiding problems  
**Remedy**: Show full browser/application context

### Failure: Unverifiable Claims
**Issue**: "I tested it" without proof  
**Remedy**: Document every test with evidence

## Proof Collection Workflow

### 1. Plan Evidence Collection
```markdown
Before starting work:
□ Identify what proof will be needed
□ Set up recording tools
□ Prepare test data
□ Clear previous artifacts
```

### 2. Collect During Work
```markdown
While working:
□ Screenshot each major step
□ Save console output regularly
□ Commit with descriptive messages
□ Run tests and save results
□ Document decisions made
```

### 3. Organize Evidence
```markdown
After completion:
□ Create evidence folder structure
□ Name files descriptively
□ Add README with overview
□ Compress if needed
□ Upload to shared location
```

### 4. Present Evidence
```markdown
For review:
□ Summarize key findings
□ Link to detailed evidence
□ Highlight critical proofs
□ Provide reproduction steps
□ Archive for future reference
```

## Evidence Archive Structure

```
evidence/
├── YYYY-MM-DD_feature_name/
│   ├── README.md              # Overview and index
│   ├── 01_technical/          # Code and test evidence
│   │   ├── code_changes.diff
│   │   ├── test_results.txt
│   │   └── coverage_report.html
│   ├── 02_functional/         # Runtime evidence
│   │   ├── screenshots/
│   │   ├── http_traces/
│   │   └── console_logs/
│   ├── 03_user_validation/    # UX evidence
│   │   ├── workflow_videos/
│   │   ├── persona_tests/
│   │   └── accessibility/
│   ├── 04_integration/        # System evidence
│   │   ├── api_tests/
│   │   ├── monitoring/
│   │   └── external_systems/
│   └── 05_regression/         # Quality evidence
│       ├── full_test_suite/
│       ├── performance/
│       └── security_scans/
```

## Special Proof Requirements

### Critical Bug Fixes
- Before state clearly documented
- Root cause analysis evidence
- Fix verification from multiple angles
- Regression test proof
- User impact assessment

### Security Fixes
- Vulnerability proof (sanitized)
- Fix verification
- Penetration test results
- No new vulnerabilities introduced
- Audit trail complete

### Performance Improvements
- Baseline metrics documented
- Improvement measurements
- Load test results
- Resource usage comparison
- Sustained performance proof

### User Experience Changes
- A/B test results if applicable
- User feedback documentation
- Accessibility audit results
- Cross-device testing proof
- Analytics showing improvement

## The QAPM Proof Manifesto

As a QAPM, your evidence is your reputation. Every piece of proof you collect and present reflects your commitment to excellence and user success. 

**Remember**:
1. Evidence prevents arguments
2. Proof builds trust
3. Documentation enables learning
4. Quality evidence ensures quality delivery

The fabric edit investigation succeeded because we demanded real proof, not promises. That TypeError was hiding behind claims of "it works" until proper evidence revealed the truth.

**Your standard**: If you wouldn't accept it as proof in a court of law, don't accept it as proof of completion.

---

*"The good news about computers is that they do what you tell them to do. The bad news is that they do what you tell them to do."* - Ted Nelson

Document what they actually do, not what you hope they do.