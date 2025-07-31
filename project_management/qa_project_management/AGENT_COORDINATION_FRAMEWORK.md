# Agent Coordination Framework
**Quality Assurance Project Management System**

**Purpose**: Systematic agent creation and supervision ensuring consistent quality results  
**Based On**: Proven success patterns from fabric edit, ArgoCD removal, git repositories investigation, and GUI assessment  
**Success Rate**: 100% completion accuracy when framework followed completely  

---

## Framework Philosophy

### Core Principle
**Agents are tools that produce verifiable results when given comprehensive instructions and proper supervision**

### Success Pattern Recognition
Our proven successes share these characteristics:
- **Comprehensive Instructions**: Complete context, environment training, authority grants
- **Evidence Requirements**: Mandatory five-level validation before completion claims
- **User Experience Focus**: Real authentication testing and workflow validation
- **Independent Verification**: Never trust first agent's claims without validation
- **Systematic Approach**: Phased investigation → analysis → implementation → validation

### Anti-Success Pattern Prevention
❌ **Avoid These Failure Modes**:
- Vague mission statements
- Missing environment context
- No evidence requirements
- Trusting completion claims without verification
- Technical-only success metrics

---

## Agent Creation Framework

### 1. Mission Definition Template

```markdown
## MISSION: [Single, Specific, Measurable Objective]

### Context: [Why this matters to the project]
### Success Criteria: [Exact evidence required for completion]
### Failure Criteria: [What constitutes failure or insufficient completion]
```

**Examples from Successful Agents**:
- ✅ "Investigate and restore git repositories page functionality" (clear, specific)
- ❌ "Fix the repository stuff" (vague, unmeasurable)

### 2. Role Definition Template

```markdown
You are a **[Specialist Type]** with [specific expertise area] and full testing authority for [scope of work].

### Role Boundaries:
- **In Scope**: [Exactly what agent should handle]
- **Out of Scope**: [What to escalate to QA Manager] 
- **Authority Level**: [What agent can do without asking]
```

**Authority Grant Pattern** (Critical for Success):
```markdown
### CRITICAL: You Have FULL Testing Authority
- Execute ANY docker commands needed
- Restart services to test changes
- Run curl tests, API validation, browser testing
- Check logs, debug issues, validate user experience
- NEVER ask user to test your work - that's YOUR responsibility
```

### 3. Environment Mastery Integration

**Mandatory for Every Agent**:
```markdown
## REQUIRED ONBOARDING TRAINING

### Environment Setup (MEMORIZE THIS):
- **NetBox**: localhost:8000 (admin/admin) - running in Docker
- **HCKC Cluster**: K3s at 127.0.0.1:6443 (kubectl available)
- **Project Root**: /home/ubuntu/cc/hedgehog-netbox-plugin/
- **Plugin Location**: netbox_hedgehog/ directory
- **Docker Container**: netbox-docker-netbox-1
```

**Additional Context Based on Task Type**:
- **Architecture Context**: For complex system changes
- **Integration Context**: For cross-component work
- **User Workflow Context**: For GUI-related tasks

### 4. Systematic Approach Framework

**Phase-Based Investigation Template**:
```markdown
## SYSTEMATIC [TASK TYPE] STRATEGY

### Phase 1: Current State Analysis
1. **Test [functionality] immediately**
2. **Document actual state** (not assumptions)
3. **Identify specific issues** with evidence

### Phase 2: Root Cause Analysis
1. **Investigate without bias** (don't trust previous reports)
2. **Examine technical implementation**
3. **Identify exact failure points**

### Phase 3: Test-Driven [Implementation/Fix]
1. **Write test that reproduces issue** (if applicable)
2. **Implement minimal solution**
3. **Verify test passes and functionality works**

### Phase 4: Comprehensive Validation
1. **User experience testing** with real authentication
2. **Regression prevention testing**
3. **Integration point validation**
```

### 5. Evidence Requirements Integration

**Mandatory for All Agents**:
```markdown
## MANDATORY EVIDENCE REQUIREMENTS

### Before Claiming Completion, Provide ALL:

**1. Technical Implementation Proof**
- [ ] Specific files modified with line numbers
- [ ] Git commit with descriptive message
- [ ] No syntax errors or compilation issues

**2. Functional Validation Proof**
- [ ] HTTP response codes (200 for success pages)
- [ ] API endpoints returning expected data
- [ ] Database operations working correctly

**3. User Workflow Validation** ⭐ **CRITICAL**
- [ ] Complete user journeys tested with real authentication
- [ ] All form submissions and interactions working
- [ ] Navigation and UI elements functional

**4. Regression Prevention Proof**
- [ ] Existing functionality still working
- [ ] No broken integrations or dependencies
- [ ] Test suite passing (if applicable)

**5. Integration Validation**
- [ ] External system connections working
- [ ] Cross-component interactions functional
- [ ] Data synchronization successful
```

---

## Specialized Agent Templates

### Investigation Agent Template

```markdown
You are a **[System Component] Investigation Specialist** with deep expertise in [technical domain] and full testing authority.

## MISSION: Investigate [specific issue] and provide comprehensive analysis

## INVESTIGATION STRATEGY

### Phase 1: Current State Assessment
[Specific commands and tests to run]

### Phase 2: Architecture Analysis  
[Understanding system design and relationships]

### Phase 3: Root Cause Identification
[Systematic debugging approach]

### Phase 4: Solution Recommendation
[Evidence-based recommendations for resolution]

## MANDATORY EVIDENCE REQUIREMENTS
[Full five-level evidence hierarchy]

## FAILURE RECOVERY PROTOCOLS
If investigation reveals [specific scenarios]:
1. [Escalation procedure]
2. [Alternative analysis methods]
3. [Documentation requirements for complex issues]

## REPORTING REQUIREMENTS
[Interim reporting schedule and final report format]
```

### Implementation Agent Template

```markdown
You are a **[Feature/Fix] Implementation Specialist** with expertise in [technology stack] and full testing authority.

## MISSION: Implement [specific functionality] with complete user experience validation

## IMPLEMENTATION STRATEGY

### Phase 1: Requirements Confirmation
[Verify understanding of what needs to be built/fixed]

### Phase 2: Test-Driven Development
[Write failing tests first, then implement]

### Phase 3: User Experience Validation
[Real authentication and workflow testing]

### Phase 4: Integration Confirmation
[Ensure no regressions and proper system integration]

## MANDATORY EVIDENCE REQUIREMENTS
[Full five-level evidence hierarchy]

## QUALITY ASSURANCE PROTOCOL
[Specific testing commands and validation procedures]

## ARCHITECTURAL COMPLIANCE
[Relevant design principles and integration requirements]
```

### Validation Agent Template

```markdown
You are a **[Component] Validation Specialist** responsible for independently verifying claimed functionality.

## MISSION: Independently verify that [claimed functionality] actually works

## VALIDATION SCOPE
You will test [specific functionality] without coordinating with implementation agent.

## VALIDATION PROTOCOL
1. **Functional Testing**: [Specific user actions to test]
2. **Technical Verification**: [Backend/API validation required]
3. **Integration Testing**: [Cross-component validation]
4. **Evidence Collection**: [Documentation requirements]

## SUCCESS = Confirmation
**FAILURE = Detailed Issue Report** (no soft failures accepted)

## INDEPENDENCE REQUIREMENT
Do not communicate with implementation agent - test purely based on claimed functionality.
```

---

## Agent Supervision Framework

### 1. Pre-Deployment Checklist

**Before Creating Any Agent**:
- [ ] **Mission clearly defined** - single, specific, measurable objective
- [ ] **Success criteria explicit** - exact evidence required for completion
- [ ] **Environment context provided** - all necessary technical details
- [ ] **Authority boundaries clear** - what agent can do independently
- [ ] **Evidence requirements specified** - five-level validation mandatory
- [ ] **Failure recovery planned** - escalation procedures defined

### 2. Active Supervision Protocol

**During Agent Execution**:

**Progress Monitoring**:
- Expect interim progress reports for complex tasks
- Watch for systematic approach following vs random attempts
- Monitor evidence quality in progress updates

**Red Flag Indicators**:
- ❌ Agent claiming "almost done" without evidence
- ❌ Technical implementation claims without user testing
- ❌ "Works for me" statements without authentication testing
- ❌ Requests to "please test this" (abdicating testing responsibility)
- ❌ Vague progress reports without specific findings

**Intervention Triggers**:
- Agent not following systematic approach
- Evidence quality below standards
- Deviation from user experience focus
- Requests for user to validate agent work

### 3. Completion Validation Process

**Never Accept Completion Without**:

1. **Evidence Completeness Check**
   - All five validation levels addressed
   - Specific artifacts provided (screenshots, logs, test results)
   - Clear before/after comparisons where applicable

2. **Independent Verification Deployment**
   ```markdown
   Deploy **[Original Task] Validation Agent** to independently verify:
   - Claimed functionality actually works
   - User workflows complete successfully  
   - No gaps between claims and reality
   ```

3. **Quality Gate Review**
   - Technical implementation sound
   - User experience actually works
   - No regressions introduced
   - Evidence supports all claims

### 4. Agent Performance Analysis

**Document for Each Agent**:
```markdown
## Agent Performance Analysis

### Task: [Original mission]
### Agent Type: [Specialist category]
### Outcome: SUCCESS / PARTIAL / FAILURE

### Strengths Demonstrated:
- [What worked well]
- [Evidence quality]  
- [Approach effectiveness]

### Areas for Improvement:
- [What could be better]
- [Evidence gaps]
- [Process deviations]

### Pattern Recognition:
- [Reusable success elements]
- [Failure modes to avoid]
- [Instruction refinements needed]

### Impact on Framework:
- [Updates to agent templates]
- [Process improvements identified]
- [Training enhancements needed]
```

---

## Multi-Agent Coordination Strategies

### Sequential Agent Deployment

**For Complex Problems** (Like Git Repositories Investigation):

1. **Investigation Agent** → Analyze and understand problem
2. **Implementation Agent** → Fix based on investigation findings  
3. **Validation Agent** → Independently verify the fix works
4. **Integration Agent** → Ensure broader system compatibility

**Handoff Protocol**:
```markdown
## Phase [N] → Phase [N+1] Handoff

### Deliverables from Phase [N]:
- [Specific artifacts and findings]
- [Evidence documentation]
- [Recommendations for next phase]

### Requirements for Phase [N+1]:
- [What next agent must accomplish]
- [Evidence standards to maintain]
- [Integration points to verify]
```

### Parallel Agent Deployment

**For Independent Tasks**:
- Multiple agents working on different components simultaneously
- Coordination through shared evidence requirements
- Final integration validation after parallel completion

**Coordination Requirements**:
- Shared evidence repository
- Cross-agent impact assessment
- Integration testing protocols

### Validation Agent Deployment

**Always Deploy for Critical Tasks**:
```markdown
Deploy **Independent Validation Agent** for:
- Any agent claiming GUI functionality works
- Database or model changes
- API endpoint modifications
- User workflow alterations
- Integration point changes
```

---

## Success Pattern Library

### Pattern 1: Technical Investigation Success
**From Git Repositories Investigation**:

```markdown
**What Made It Work**:
1. Comprehensive environment context provided
2. Systematic phase-based approach required
3. Evidence collection at each phase
4. No assumptions about previous work
5. Independent verification of all findings

**Reusable Template Elements**:
- Current state assessment before any analysis
- Root cause identification with evidence
- Technical solution recommendations
- Validation requirements for implementation
```

### Pattern 2: User Experience Validation Success  
**From Fabric Edit Investigation**:

```markdown
**What Made It Work**:
1. Real authentication testing required (admin/admin)
2. Complete user workflow validation mandatory
3. Browser-based evidence collection
4. Test-driven development approach
5. No acceptance of "works technically" without user proof

**Reusable Template Elements**:
- Authentication setup in all instructions
- User workflow testing requirements
- Evidence format specifications
- Browser validation commands
```

### Pattern 3: Architectural Compliance Success
**From ArgoCD Removal**:

```markdown
**What Made It Work**:
1. Clear architectural principles provided
2. Vendor neutrality requirements specified
3. Functionality preservation mandated
4. Complete testing of preserved features
5. Evidence of architectural compliance

**Reusable Template Elements**:
- Architectural context in instructions
- Principle compliance requirements
- Feature preservation validation
- Integration testing protocols
```

---

## Quality Metrics and Improvement

### Agent Success Metrics

**Track These KPIs**:
- **First-Time Success Rate**: % of agents completing correctly on first attempt
- **Evidence Quality Score**: Completeness of validation documentation
- **User Experience Success Rate**: % of claims that actually work for users
- **Regression Prevention Rate**: % of changes with no negative side effects
- **Independent Verification Pass Rate**: % of claims confirmed by validation agents

### Framework Evolution Process

**Monthly Framework Review**:
1. **Pattern Analysis**: Which agent patterns consistently succeed/fail
2. **Template Refinement**: Update templates based on field results
3. **Evidence Standard Updates**: Strengthen requirements based on gaps found
4. **Training Enhancement**: Improve onboarding based on agent performance

**Continuous Improvement Triggers**:
- Any false completion claim → immediate template enhancement
- Pattern of similar failures → systematic template update
- New technology integration → environment context updates
- User experience feedback → validation requirement strengthening

---

## Emergency Protocols

### When Agents Fail to Follow Framework

**Immediate Actions**:
1. **Stop Agent Work**: Prevent continued incorrect approach
2. **Deploy Validation Agent**: Assess actual current state
3. **Framework Analysis**: Identify where framework wasn't followed
4. **Template Enhancement**: Update templates to prevent recurrence

### When Evidence Standards Not Met

**Escalation Process**:
1. **Evidence Gap Documentation**: Specifically identify missing validation
2. **Completion Rejection**: Do not accept insufficient evidence
3. **Re-deployment with Enhanced Instructions**: Stronger evidence requirements
4. **Framework Update**: Prevent similar evidence gaps in future

### When User Experience Fails

**Quality Recovery**:
1. **User Impact Assessment**: Document exactly what doesn't work
2. **Emergency Fix Deployment**: Restore user functionality immediately
3. **Root Cause Analysis**: Why did validation miss the user experience issue
4. **Process Strengthening**: Enhanced user experience validation requirements

---

**Remember**: This framework transforms inconsistent agent performance into predictable quality results. Every element exists because skipping it has caused real problems. Follow completely for guaranteed success.