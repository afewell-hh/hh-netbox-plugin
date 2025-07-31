# Agent Instruction Templates for HNP Fabric Sync Implementation

**Version**: 1.0  
**Date**: July 29, 2025  
**Purpose**: Comprehensive agent instructions with TDD enforcement and quality gate compliance

## Implementation Agent Instructions

### Role Definition
- **Primary Role**: Execute HNP fabric sync implementation according to phased plan
- **Authority**: Configuration changes, code fixes, database updates within scope
- **Restrictions**: MUST follow test-first development, cannot skip quality gates, cannot claim completion without evidence

### Core Responsibilities
1. **Test-First Development**: Run failing tests before implementing fixes
2. **Incremental Implementation**: Follow phased approach with quality gates
3. **Evidence Collection**: Provide comprehensive proof of all changes
4. **Regression Prevention**: Ensure no existing functionality broken
5. **Documentation**: Maintain clear record of all changes and decisions

### Mandatory Process Framework

#### Step 1: Pre-Implementation Analysis
```markdown
REQUIRED ACTIONS:
1. Read and understand the HNP_FABRIC_SYNC_IMPLEMENTATION_PLAN.md
2. Analyze current phase requirements and exit criteria
3. Review all relevant test failures for current phase
4. Identify specific root causes to address
5. Document understanding of required changes

EVIDENCE REQUIRED:
- Analysis document showing understanding of requirements
- List of specific tests that must pass in current phase
- Root cause analysis for failing functionality
- Change plan with specific actions and expected outcomes
```

#### Step 2: Test-First Development Cycle
```markdown
RED PHASE - Write/Run Failing Test:
1. Execute specific failing test for current requirement
2. Capture and document current failure output
3. Analyze failure to understand exact requirement
4. Confirm test failure is due to missing implementation
5. Document baseline failure state

GREEN PHASE - Implement Minimal Fix:
1. Make minimal changes to pass the specific test
2. Focus only on requirements for current test
3. Avoid over-engineering or additional features
4. Test implementation incrementally
5. Document each change made

REFACTOR PHASE - Clean Implementation:
1. Review code quality and maintainability
2. Clean up implementation while keeping tests passing
3. Add proper error handling and logging
4. Update documentation and comments
5. Validate no regressions introduced

EVIDENCE PHASE - Document Results:
1. Capture test execution showing PASS result
2. Document all code changes with explanations
3. Show database state changes where applicable
4. Prove no regressions in existing functionality
5. Prepare evidence package for validation
```

#### Step 3: Quality Gate Preparation
```markdown
VALIDATION PREPARATION:
1. Run complete test suite to check for regressions
2. Test actual user workflows affected by changes
3. Capture comprehensive evidence of functionality
4. Document any edge cases or limitations discovered
5. Prepare handoff documentation for validation agent

QUALITY GATE SUBMISSION:
1. Submit evidence package to validation agent
2. Provide clear explanation of changes made
3. Identify any risks or concerns discovered
4. Wait for independent validation before proceeding
5. Address any validation feedback promptly
```

### Phase-Specific Instructions

#### Phase 1: System Preparation
**Objective**: Establish stable implementation foundation

**Critical Actions**:
1. **Environment Verification**
   ```bash
   # Execute mandatory failing test suite
   python3 tests/mandatory_failing_tests.py
   
   # Document baseline failures
   # Verify Docker container synchronization
   # Confirm database schema consistency
   ```

2. **Authentication Architecture Analysis**
   ```python
   # Study GitRepository model encryption system
   from netbox_hedgehog.models.git_repository import GitRepository
   
   # Analyze connection test methodology
   # Document credential storage patterns
   # Map authentication API endpoints
   ```

**Evidence Requirements**:
- Test execution logs showing current failure state
- GitRepository model analysis documentation
- Authentication flow diagrams
- Environment stability confirmation

#### Phase 2: Configuration Correction
**Objective**: Fix fabric configuration issues

**Critical Actions**:
1. **GitRepository Foreign Key Fix**
   ```python
   # MUST run failing test first
   python3 tests/mandatory_failing_tests.py
   
   # Focus on test_fabric_git_repository_link failure
   # Expected: LINK_MISSING or LINK_WRONG
   
   # Implementation fix:
   from netbox_hedgehog.models.fabric import HedgehogFabric
   from netbox_hedgehog.models.git_repository import GitRepository
   
   fabric = HedgehogFabric.objects.get(id=19)
   repository = GitRepository.objects.get(id=6)
   fabric.git_repository = repository
   fabric.save()
   
   # Verify test now passes
   ```

2. **GitOps Directory Path Fix**
   ```python
   # MUST run failing test first
   # Focus on test_fabric_gitops_directory failure
   # Expected: GITOPS_DIR:/
   
   # Implementation fix:
   fabric = HedgehogFabric.objects.get(id=19)
   fabric.gitops_directory = 'gitops/hedgehog/fabric-1/'
   fabric.save()
   
   # Verify test now passes
   ```

**Evidence Requirements**:
- Before/after test execution logs
- Database queries showing FK relationship
- Directory path verification
- No regression in related functionality

#### Phase 3: Authentication Setup
**Objective**: Configure working Git authentication

**Critical Actions**:
1. **Encrypted Credentials Setup**
   ```python
   # MUST run failing test first
   # Focus on test_git_repository_authentication failure
   # Expected: HAS_CREDENTIALS:False or CONNECTION_SUCCESS:False
   
   # Implementation fix:
   repository = GitRepository.objects.get(id=6)
   
   # Set up encrypted credentials (example)
   credentials = {
       'token': 'github_pat_xxxxx',  # Real PAT required
       'username': 'afewell-hh'
   }
   
   # Use repository's encryption system
   repository.set_credentials(credentials)
   result = repository.test_connection()
   
   # Verify connection successful
   ```

**Evidence Requirements**:
- Authentication test passing
- Connection status updated to 'connected'
- Repository clone operation successful
- No credential exposure in logs

#### Phase 4: Synchronization Implementation
**Objective**: Implement working sync operation

**Critical Actions**:
1. **Repository Content Access**
   ```python
   # MUST run failing test first
   # Focus on test_repository_content_accessible failure
   
   # Test repository clone and content access
   repository = GitRepository.objects.get(id=6)
   with tempfile.TemporaryDirectory() as temp_dir:
       result = repository.clone_repository(temp_dir)
       # Verify gitops/hedgehog/fabric-1/ directory exists
       # Enumerate YAML files and validate CRD content
   ```

2. **Sync Operation Implementation**
   ```python
   # MUST run failing test first
   # Focus on test_sync_creates_crd_records failure
   # Expected: SYNC_SUCCESS:False or TOTAL_CRDS_CREATED:0
   
   # Fix trigger_gitops_sync() method
   fabric = HedgehogFabric.objects.get(id=19)
   result = fabric.trigger_gitops_sync()
   
   # Verify CRD records created in database
   # Verify fabric cached counts updated
   ```

**Evidence Requirements**:
- Repository content accessible with proper authentication
- Sync operation creates VPC, Connection, Switch records
- Fabric cached_crd_count updated correctly
- Complete sync workflow functional

#### Phase 5: End-User Validation
**Objective**: Ensure GUI integration functional

**Critical Actions**:
1. **GUI Integration Testing**
   ```bash
   # Test fabric detail page loading
   curl -s http://localhost:8000/plugins/hedgehog/fabrics/19/ | grep "HCKC"
   
   # Verify sync button exists
   # Test CRD count display accuracy
   # Execute complete user workflow via browser
   ```

**Evidence Requirements**:
- All 10 mandatory tests passing
- GUI functionality verified through actual browser testing
- Complete user workflows operational
- No regressions in existing functionality

### Mandatory Evidence Standards

#### Code Changes Evidence
```markdown
REQUIRED FOR ALL CODE CHANGES:
1. Before/after code diffs with clear explanations
2. Reason for each change tied to specific test requirement
3. Database migration scripts if schema changes required
4. Configuration file updates with validation
5. Dependency changes with justification
```

#### Test Evidence
```markdown
REQUIRED FOR ALL TEST-RELATED WORK:
1. Complete test execution logs showing before/after states
2. Screenshots of test results for visual confirmation
3. Test output analysis explaining why tests now pass
4. Regression test results showing no functionality broken
5. Performance impact assessment if applicable
```

#### Database Evidence
```markdown
REQUIRED FOR ALL DATABASE CHANGES:
1. SQL queries showing before/after state
2. Foreign key relationship verification
3. Data integrity checks completed successfully
4. Migration rollback testing if applicable
5. Backup and recovery validation
```

#### User Interface Evidence
```markdown
REQUIRED FOR ALL GUI CHANGES:
1. Screenshots of functional user interface elements
2. Browser network request logs showing API calls
3. User workflow completion evidence
4. Cross-browser compatibility testing
5. Accessibility compliance verification
```

### Error Handling Requirements

#### Expected Error Scenarios
1. **Test Execution Failures**
   - Document exact error messages and stack traces
   - Analyze root cause and provide fix plan
   - Show corrective actions taken
   - Prove error resolution with passing tests

2. **Authentication Failures**
   - Document authentication error patterns
   - Show credential validation and fix
   - Prove connection establishment
   - Test authentication persistence

3. **Sync Operation Failures**
   - Document sync error messages and causes
   - Show repository access validation
   - Prove YAML parsing and CRD creation
   - Test complete sync workflow

4. **Database Constraint Violations**
   - Document constraint violation errors
   - Show foreign key relationship fixes
   - Prove data integrity maintenance
   - Test transaction rollback scenarios

### Quality Assurance Integration

#### Mandatory QA Checkpoints
1. **Before Starting**: Confirm understanding of requirements and test framework
2. **After Each Fix**: Provide evidence package for validation
3. **Before Quality Gate**: Complete regression testing
4. **After Validation Feedback**: Address all concerns promptly
5. **Before Final Completion**: Comprehensive system validation

#### Evidence Validation Standards
- All evidence must be independently verifiable
- Screenshots must include timestamps and system information
- Code changes must be traceable to specific requirements
- Test results must be reproducible by validation agent
- Documentation must be complete and accurate

### Risk Mitigation Requirements

#### Agent Performance Monitoring
- **False Completion Detection**: Never claim work complete without passing tests
- **Evidence Integrity**: All evidence must match claimed functionality
- **Process Compliance**: Follow TDD methodology strictly
- **Quality Gate Respect**: Wait for validation approval before proceeding
- **Regression Prevention**: Test all related functionality after changes

## Validation Agent Instructions

### Role Definition
- **Primary Role**: Independent validation of implementation agent work
- **Authority**: Quality gate approval/rejection, evidence verification
- **Restrictions**: Cannot modify implementation, must verify independently

### Core Responsibilities
1. **Independent Testing**: Execute tests without implementation agent assistance
2. **Evidence Validation**: Verify all provided evidence matches claims
3. **Functionality Testing**: Test actual user workflows and system behavior
4. **Regression Detection**: Identify any broken existing functionality
5. **Quality Gate Decisions**: Approve or reject based on objective criteria

### Mandatory Validation Process

#### Step 1: Evidence Review
```markdown
EVIDENCE ANALYSIS:
1. Review all evidence provided by implementation agent
2. Verify evidence completeness against phase requirements
3. Check evidence validity and accuracy
4. Identify any gaps or inconsistencies
5. Document evidence assessment results

VALIDATION CRITERIA:
- Evidence matches claimed functionality
- All required evidence types present
- Evidence is independently verifiable
- No false or misleading information detected
- Evidence supports quality gate criteria
```

#### Step 2: Independent Testing
```markdown
INDEPENDENT TEST EXECUTION:
1. Execute all tests without implementation agent assistance
2. Use fresh environment or reset state as needed
3. Follow exact test procedures from mandatory test suite
4. Compare results to implementation agent claims
5. Document any discrepancies discovered

FUNCTIONALITY VALIDATION:
- All specified tests pass independently
- User workflows complete successfully
- System behavior matches requirements
- No regressions in existing functionality
- Performance within acceptable parameters
```

#### Step 3: Quality Gate Decision
```markdown
GATE APPROVAL CRITERIA:
1. All tests pass independently without agent assistance
2. Evidence is comprehensive, valid, and verifiable
3. Functionality works as claimed in real user scenarios  
4. No regressions detected in existing system features
5. Implementation follows established standards and patterns

GATE REJECTION CRITERIA:
- Any test failures in independent execution
- Evidence gaps, inconsistencies, or inaccuracies
- Functionality doesn't work in real user scenarios
- Regressions detected in existing functionality
- Implementation violates established standards
```

### Phase-Specific Validation Procedures

#### Phase 1 Validation: System Preparation
**Validation Focus**: Foundation stability and understanding

**Independent Tests**:
1. Execute mandatory failing test suite independently
2. Verify Docker container synchronization status
3. Confirm database schema and data consistency
4. Test GitRepository and Fabric record existence
5. Validate authentication architecture understanding

**Approval Criteria**:
- All 6 pre-condition tests pass
- Implementation agent demonstrates clear understanding
- System environment is stable and ready
- No environmental issues affecting implementation

#### Phase 2 Validation: Configuration Correction
**Validation Focus**: Fabric configuration fixes

**Independent Tests**:
1. Run test_fabric_git_repository_link() independently
2. Run test_fabric_gitops_directory() independently
3. Verify database foreign key relationship
4. Test GitOps directory path accessibility
5. Check for regressions in fabric functionality

**Approval Criteria**:
- Both configuration tests pass independently
- Database relationships correctly established
- No regressions in existing fabric operations
- Configuration changes persist across container restarts

#### Phase 3 Validation: Authentication Setup
**Validation Focus**: Git authentication functionality

**Independent Tests**:
1. Run test_git_repository_authentication() independently
2. Test repository connection without agent assistance
3. Verify encrypted credentials storage
4. Test repository clone operation
5. Validate connection status accuracy

**Approval Criteria**:
- Authentication test passes independently
- Repository connection succeeds with proper credentials
- Connection status reflects actual connectivity
- Authentication persists across system restarts

#### Phase 4 Validation: Synchronization Implementation
**Validation Focus**: Sync operation functionality

**Independent Tests**:
1. Run test_repository_content_accessible() independently
2. Run test_sync_creates_crd_records() independently
3. Execute complete sync workflow without agent assistance
4. Verify CRD record creation in database
5. Test fabric count updates

**Approval Criteria**:
- Both sync tests pass independently
- Sync operation creates expected database records
- Fabric cached counts update correctly
- Complete sync workflow operational

#### Phase 5 Validation: End-User Validation
**Validation Focus**: Complete system functionality

**Independent Tests**:
1. Run all 10 mandatory tests independently
2. Test complete user workflows via browser
3. Verify GUI elements and functionality
4. Test system under various user scenarios
5. Comprehensive regression testing

**Approval Criteria**:
- All 10 mandatory tests pass independently
- Complete user workflows functional
- GUI accurately reflects system state
- No regressions in any system functionality

### Evidence Verification Standards

#### Code Evidence Verification
- Review all code changes for correctness and safety
- Verify changes address specific test requirements
- Check for proper error handling and logging
- Validate code follows established patterns
- Ensure no security vulnerabilities introduced

#### Test Evidence Verification
- Execute all tests independently to confirm results
- Verify test output matches provided evidence
- Check test execution environment consistency
- Validate test covers actual requirements
- Ensure no test manipulation or false results

#### Database Evidence Verification
- Execute independent database queries to verify state
- Check foreign key relationships and constraints
- Validate data integrity and consistency
- Test database changes under various scenarios
- Verify migration and rollback procedures

#### User Interface Evidence Verification
- Test GUI functionality independently in browser
- Verify all claimed UI elements exist and function
- Test user workflows from fresh browser session
- Check GUI responsiveness and error handling
- Validate accessibility and usability standards

## Quality Gate Agent Instructions

### Role Definition
- **Primary Role**: QAPM oversight and process enforcement
- **Authority**: Final quality gate approval, process compliance enforcement
- **Restrictions**: Cannot implement or validate directly, focused on quality assurance oversight

### Core Responsibilities
1. **Process Enforcement**: Ensure all agents follow established procedures
2. **Quality Standards**: Maintain high standards for evidence and testing
3. **Risk Management**: Identify and mitigate implementation risks
4. **Gate Decisions**: Make final approval/rejection decisions for quality gates
5. **Continuous Improvement**: Enhance processes based on lessons learned

### Quality Gate Oversight Process

#### Gate Review Framework
```markdown
GATE REVIEW CHECKLIST:
□ Implementation agent followed TDD methodology
□ All required tests pass independently
□ Evidence is comprehensive and verifiable
□ Validation agent completed independent verification
□ No false completion patterns detected
□ Risk mitigation strategies implemented
□ Process compliance maintained throughout
□ Quality standards met or exceeded
```

#### Gate Decision Matrix
| Criteria | Pass | Conditional Pass | Fail |
|----------|------|------------------|------|
| Test Results | All tests pass independently | Minor test issues with clear fix plan | Any test failures |
| Evidence Quality | Comprehensive, valid, verifiable | Minor gaps with quick resolution | Significant gaps or invalid evidence |
| Process Compliance | Full TDD and quality gate compliance | Minor deviations with justification | Major process violations |
| Risk Assessment | All risks mitigated | Acceptable residual risk | Unacceptable risk levels |
| Validation Results | Independent validation confirms all claims | Minor discrepancies resolved | Validation contradicts claims |

#### Continuous Monitoring Requirements
- Monitor for agent false completion patterns
- Track quality metrics across phases
- Identify process improvement opportunities
- Escalate significant issues promptly
- Maintain comprehensive audit trail

### Success Validation Framework

This comprehensive agent instruction framework ensures:

1. **Test-Driven Development Enforcement**: All agents must follow TDD methodology strictly
2. **Quality Gate Compliance**: No shortcuts allowed, all gates must be passed with evidence
3. **Independent Validation**: Separate validation prevents false completion claims
4. **Comprehensive Evidence**: All work must be backed by verifiable evidence
5. **Risk Mitigation**: Common failure patterns addressed proactively
6. **User Focus**: Real user workflows must work, not just tests
7. **Process Integrity**: Quality assurance maintained throughout implementation

These instructions provide the framework for successful implementation of HNP fabric sync functionality while preventing the false completion patterns that have affected previous projects.