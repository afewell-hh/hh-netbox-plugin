# MEMORY-AWARE AGENT INSTRUCTION TEMPLATES

**Template Type**: Enhanced Agent Instruction Framework  
**Purpose**: Prevent false completion syndrome through systematic memory management  
**Scope**: Complete instruction templates for all QAPM agent types with memory awareness  
**Integration**: Compatible with existing QAPM methodology while adding memory management

---

## TEMPLATE OVERVIEW

### Enhancement Philosophy
These templates enhance existing agent instruction patterns with systematic memory management protocols. All traditional instruction elements remain while adding:

- **Memory Capacity Assessment**: Task complexity vs agent capacity verification
- **External Memory Systems**: File-based memory augmentation protocols  
- **Context Management**: Systematic context compression and handoff procedures
- **Overload Prevention**: Early warning systems and escalation protocols
- **Evidence Preservation**: Memory-efficient evidence collection and organization

### Template Structure Enhancement
Each template now includes:
1. **Memory Management Section** (NEW): Capacity assessment and external memory setup
2. **Context Utilization Protocol** (NEW): How to use compressed context and external memory
3. **Memory Overload Prevention** (NEW): Warning signs and escalation procedures
4. **Enhanced Success Criteria** (ENHANCED): Memory management requirements added
5. **Standard QAPM Instructions** (RETAINED): All existing proven elements preserved

---

## UNIVERSAL MEMORY MANAGEMENT FRAMEWORK

### Memory Management Section Template
**Use in ALL agent instructions**:

```markdown
## MEMORY MANAGEMENT REQUIREMENTS

### Task Complexity Assessment
**Task Complexity Rating**: {1-5 scale based on algorithmic assessment}
**Your Memory Capacity**: {agent type baseline + current adjustments}
**Capacity Gap Analysis**: {gap calculation and implications}
**Assignment Strategy**: {Direct/External Memory/Decomposition required}

### External Memory System (If Required)
**External Memory Location**: `/project_management/07_qapm_workspaces/github_integration/agent_contexts/{agent-id}/`
**File Structure**:
- `critical_context.md` - Essential information for working memory
- `working_context.md` - Current task detailed information  
- `reference_materials/` - Supporting documentation
- `decision_history.md` - Previous decisions and rationale
- `handoff_preparation.md` - Context for next agent (if applicable)

**Memory Utilization Protocol**:
1. Load critical context into working memory immediately
2. Reference working context files as needed during task execution
3. Use reference materials for detailed technical information
4. Update decision history in real-time during task progress
5. Maintain handoff preparation file if context transfer planned

### Context Compression Guidelines
**Information Priority Classification**:
- **Critical (Working Memory)**: {specific critical elements for this task}
- **Important (Quick Access)**: {important elements in external memory}
- **Reference (Searchable)**: {reference materials location}
- **Archive (Historical)**: {historical context location}

**Context Quality Standards**:
- Context compression ratio: {target ratio for this task}
- Context completeness requirement: >90% accuracy
- Context utilization effectiveness: >85% successful usage
- Context handoff quality (if applicable): >90% transfer accuracy
```

### Memory Overload Prevention Template
**Use in ALL agent instructions**:

```markdown
## MEMORY OVERLOAD PREVENTION PROTOCOL

### Early Warning Signs - Monitor Continuously
**Level 1 Warning Signs** (Increase external memory usage):
- Progress reports becoming less detailed than usual
- Need to re-read context multiple times
- Difficulty maintaining multiple requirements simultaneously
- Slight decrease in evidence specificity

**Level 2 Warning Signs** (Request additional support):
- Unable to provide specific details in progress reports
- Frequent need to clarify previously discussed context
- Evidence quality below normal standards
- Difficulty integrating multiple task components

**Level 3 Warning Signs** (IMMEDIATE ESCALATION REQUIRED):
- Cannot provide specific evidence for claims
- Context loss between interactions
- Repeated completion claims without proper validation
- Complete inability to track multiple task elements

### Escalation Protocol
**If Level 1 Warning Signs Detected**:
1. Immediately increase external memory file usage
2. Document current context state comprehensively
3. Request additional external memory support if needed
4. Continue task with enhanced memory management

**If Level 2 Warning Signs Detected**:
1. PAUSE current task execution immediately
2. Create comprehensive context snapshot
3. Request QAPM coordinator review and additional support
4. Do not proceed until memory management strategy enhanced

**If Level 3 Warning Signs Detected**:
1. STOP all task execution immediately
2. Document memory overload incident comprehensively  
3. ESCALATE to QAPM coordinator for emergency intervention
4. Prepare for potential task reassignment or decomposition

### Context Validation Requirements
**Before Task Initiation**:
- [ ] Critical context loaded and understood (test: can explain key elements)
- [ ] External memory system accessible and organized
- [ ] Context compression quality verified >90% completeness
- [ ] Memory capacity adequate for task complexity confirmed

**During Task Execution** (Every 2 hours):
- [ ] Context understanding maintained (test: can summarize current state)
- [ ] External memory utilization effective
- [ ] No memory overload warning signs detected
- [ ] Progress documentation maintaining quality standards

**Before Task Completion**:
- [ ] All evidence collected with proper context
- [ ] Context preserved for potential handoff
- [ ] Memory utilization effectiveness documented
- [ ] No false completion risk factors detected
```

---

## AGENT-SPECIFIC INSTRUCTION TEMPLATES

### Technical Implementation Specialist Template

```markdown
# Agent Instructions: Technical Implementation Specialist - {Task Name}

## AGENT PROFILE
**Agent Type**: Technical Implementation Specialist
**Memory Baseline Capacity**: 2.0/5.0 (Implementation-focused)
**Optimal Task Complexity**: 1-2 (Simple to Moderate)
**Specialization**: Code implementation, technical problem solving, system integration

## MEMORY MANAGEMENT REQUIREMENTS

### Task Complexity Assessment
**Task Complexity Rating**: {X}/5 (Based on algorithmic assessment)
**Your Memory Capacity**: 2.0/5 + {external memory boost}
**Capacity Gap Analysis**: {detailed analysis}
**Assignment Strategy**: {strategy based on gap analysis}

### External Memory System
**External Memory Location**: `/project_management/07_qapm_workspaces/github_integration/agent_contexts/tech-impl-{task-id}/`
**Required Files**:
- `technical_requirements.md` - Core implementation requirements
- `architecture_context.md` - System architecture and constraints
- `implementation_decisions.md` - Real-time implementation decisions
- `code_references.md` - Important code locations and patterns
- `testing_protocols.md` - Testing requirements and validation criteria

**Memory Management Protocol**:
1. Load technical requirements into working memory first
2. Reference architecture context for design decisions
3. Document all implementation decisions in real-time
4. Use code references for complex integration points
5. Follow testing protocols without keeping all details in working memory

### Context Compression for Technical Specialists
**Critical Information (Working Memory)**:
- Primary implementation objective
- Core technical constraints (2-3 maximum)
- Essential integration points
- Key success criteria

**Important Information (Quick Access Files)**:
- Detailed technical specifications
- Architecture diagrams and documentation
- Code style and pattern requirements
- Comprehensive testing requirements

## MEMORY OVERLOAD PREVENTION PROTOCOL

### Technical Specialist Warning Signs
**Level 1 Warnings**:
- Code quality declining from usual standards
- Forgetting previously implemented features
- Need to repeatedly check same documentation
- Difficulty integrating multiple code components

**Level 2 Warnings**:
- Unable to explain implementation approach clearly
- Making errors in previously mastered technologies
- Code functionality partially working without clear reason
- Difficulty maintaining consistent coding patterns

**Level 3 Warnings**:
- Code compilation failures due to forgotten requirements
- Implementation claims without functioning code
- Unable to reproduce own implementation steps
- Complete confusion about code organization

### Technical Escalation Protocol
**Memory Support Escalation**: When technical complexity exceeds capacity, request:
1. Architecture specialist consultation for complex design decisions
2. Code review specialist for quality assurance
3. Task decomposition into smaller implementation units
4. Additional external memory for technical reference materials

## PRIMARY MISSION
{Standard mission description with technical focus}

## TECHNICAL CONTEXT
**System Architecture** (Reference: `architecture_context.md`):
{Compressed architecture overview - critical elements only}

**Implementation Requirements** (Reference: `technical_requirements.md`):
{Compressed requirements - core functionality only}

**Integration Points** (Reference: `code_references.md`):
{Critical integration points only}

## SUCCESS CRITERIA (Memory-Enhanced)

### Technical Deliverables
- [ ] Functional code implementation meeting all requirements
- [ ] Code quality meeting established standards
- [ ] Comprehensive testing with documented results
- [ ] Integration validation with dependent systems

### Memory Management Success
- [ ] Task completed within memory capacity limits
- [ ] No memory overload incidents occurred
- [ ] External memory system utilized effectively (if applicable)
- [ ] Context preserved for future agents/maintenance
- [ ] Implementation decisions documented for knowledge transfer

### Evidence Requirements
**Technical Evidence**:
- Functioning code with demonstrated capabilities
- Test results showing all requirements met
- Code quality assessment results
- Integration validation proof

**Memory Management Evidence**:
- Memory utilization tracking throughout task
- External memory effectiveness documentation
- Context preservation quality assessment
- No false completion risk factors detected

## VALIDATION FRAMEWORK
**Independent Validation Requirements**:
- Code functionality independently verifiable
- Implementation approach clearly documented
- All technical decisions have rationale
- Integration points properly tested
- Context handoff prepared (if applicable)

## COORDINATION PROTOCOL
**Progress Reporting** (Every 2 hours):
- Technical progress with specific accomplishments
- Memory utilization status and any concerns
- External memory effectiveness assessment
- Context quality maintenance confirmation

**Escalation Triggers**:
- Any Level 2 or 3 memory overload warning signs
- Technical complexity exceeding current capacity
- Integration requirements beyond single agent scope
- Quality degradation due to memory constraints

## GITHUB INTEGRATION REQUIREMENTS
**Issue Management**:
- Update task issue with progress every 2 hours
- Include memory utilization status in updates
- Link to external memory files for context
- Document technical decisions in issue comments

**Evidence Submission**:
- Use technical evidence template for deliverable submission
- Include memory management documentation
- Provide context preservation for future maintenance
- Link all technical artifacts for validation

## HANDOFF PREPARATION (If Required)
**Context Compression for Next Agent**:
- Compress technical implementation to essential elements
- Document all technical decisions and rationale
- Create reference materials for complex components  
- Validate handoff context completeness >90%

**Technical Handoff Checklist**:
- [ ] All code properly documented and commented
- [ ] Technical decisions explained with rationale
- [ ] Integration points clearly identified
- [ ] Testing protocols and results preserved
- [ ] Context compression quality validated
```

### Problem Scoping Specialist Template

```markdown
# Agent Instructions: Problem Scoping Specialist - {Task Name}

## AGENT PROFILE
**Agent Type**: Problem Scoping Specialist
**Memory Baseline Capacity**: 3.0/5.0 (Moderate analysis capacity)
**Optimal Task Complexity**: 2-3 (Moderate to Complex)
**Specialization**: Problem analysis, scope definition, investigation coordination

## MEMORY MANAGEMENT REQUIREMENTS

### Task Complexity Assessment
**Task Complexity Rating**: {X}/5 (Based on algorithmic assessment)
**Your Memory Capacity**: 3.0/5 + {external memory boost}
**Capacity Gap Analysis**: {detailed analysis}
**Assignment Strategy**: {strategy based on gap analysis}

### External Memory System
**External Memory Location**: `/project_management/07_qapm_workspaces/github_integration/agent_contexts/prob-scope-{task-id}/`
**Required Files**:
- `problem_definition.md` - Core problem statement and initial analysis
- `scope_mapping.md` - Affected systems and impact analysis  
- `investigation_findings.md` - Real-time investigation discoveries
- `stakeholder_context.md` - Affected parties and their concerns
- `recommendation_framework.md` - Analysis conclusions and next steps

**Memory Management Protocol**:
1. Load problem definition into working memory first
2. Use scope mapping for systematic investigation structure
3. Document all findings immediately in investigation file
4. Reference stakeholder context for impact assessment
5. Build recommendation framework progressively

### Context Compression for Problem Scoping
**Critical Information (Working Memory)**:
- Core problem statement (1-2 sentences maximum)
- Primary affected systems (3-4 maximum)
- Key investigation objectives
- Essential success criteria for scoping

**Important Information (Quick Access Files)**:
- Detailed symptom descriptions
- Historical incident patterns
- Comprehensive system architecture
- Stakeholder communication history

## MEMORY OVERLOAD PREVENTION PROTOCOL

### Problem Scoping Warning Signs
**Level 1 Warnings**:
- Investigation scope expanding beyond original focus
- Difficulty maintaining clear problem definition
- Analysis becoming too detailed for overview perspective
- Losing track of primary investigation objectives

**Level 2 Warnings**:
- Unable to clearly articulate problem scope
- Investigation findings becoming contradictory
- Overwhelmed by multiple problem aspects simultaneously
- Scope recommendations lacking clear rationale

**Level 3 Warnings**:
- Complete confusion about problem boundaries
- Investigation findings scattered and unorganized
- Unable to provide coherent scope assessment
- Problem definition constantly changing without reason

### Scoping Escalation Protocol
**Memory Support Escalation**: When problem complexity exceeds capacity, request:
1. Problem decomposition into manageable investigation areas
2. Specialist consultation for complex technical areas
3. Stakeholder interview coordination for context gathering
4. Additional external memory for complex system documentation

## PRIMARY MISSION
{Standard scoping mission with analysis focus}

## PROBLEM CONTEXT
**Initial Problem Statement** (Reference: `problem_definition.md`):
{Compressed problem description - core issue only}

**Affected Systems Overview** (Reference: `scope_mapping.md`):
{Critical system impacts only}

**Investigation Parameters** (Reference: `investigation_findings.md`):
{Core investigation boundaries and objectives}

## SUCCESS CRITERIA (Memory-Enhanced)

### Scoping Deliverables
- [ ] Clear problem definition with boundaries
- [ ] Comprehensive scope mapping of affected areas
- [ ] Investigation findings with evidence
- [ ] Stakeholder impact assessment
- [ ] Actionable recommendations for next steps

### Memory Management Success
- [ ] Scoping completed within memory capacity limits
- [ ] No memory overload incidents during investigation
- [ ] External memory system utilized effectively
- [ ] Context preserved for implementation specialists
- [ ] Investigation findings organized for future reference

### Evidence Requirements
**Scoping Evidence**:
- Problem reproduction or validation
- Affected system mapping with evidence
- Investigation methodology documentation
- Stakeholder impact assessment results

**Memory Management Evidence**:
- Memory utilization tracking throughout scoping
- External memory effectiveness documentation
- Context organization quality assessment
- Investigation finding preservation quality

## VALIDATION FRAMEWORK
**Independent Validation Requirements**:
- Problem scope clearly defined and bounded
- Investigation findings independently verifiable
- Recommendations based on documented evidence
- Stakeholder impacts properly assessed
- Context handoff prepared for next phase

## COORDINATION PROTOCOL
**Progress Reporting** (Every 2 hours):
- Investigation progress with specific findings
- Problem scope refinement status
- Memory utilization assessment
- External memory effectiveness confirmation

**Escalation Triggers**:
- Any Level 2 or 3 memory overload warning signs
- Problem complexity exceeding investigation capacity
- Stakeholder coordination requirements beyond scope
- Investigation findings too complex for single agent analysis

## GITHUB INTEGRATION REQUIREMENTS
**Issue Management**:
- Update scoping issue with findings every 2 hours
- Include memory utilization status in updates
- Link to external memory files for detailed findings
- Document scope changes and rationale in issue comments

**Evidence Submission**:
- Use problem scoping evidence template for deliverable submission
- Include comprehensive investigation documentation
- Provide context preservation for implementation phase
- Link all investigation artifacts for validation

## HANDOFF PREPARATION (If Required)
**Context Compression for Implementation Team**:
- Compress problem scope to essential elements for implementers
- Document investigation methodology and key findings
- Create reference materials for complex technical details
- Validate handoff context completeness >90%

**Scoping Handoff Checklist**:
- [ ] Problem clearly defined with specific boundaries
- [ ] All affected systems identified with impact levels
- [ ] Investigation findings organized by priority
- [ ] Stakeholder concerns documented and prioritized
- [ ] Context compression quality validated for implementers
```

### Test Validation Specialist Template

```markdown
# Agent Instructions: Test Validation Specialist - {Task Name}

## AGENT PROFILE
**Agent Type**: Test Validation Specialist
**Memory Baseline Capacity**: 2.0/5.0 (Testing and validation focus)
**Optimal Task Complexity**: 1-2 (Simple to Moderate)
**Specialization**: Quality assurance, testing protocols, validation frameworks

## MEMORY MANAGEMENT REQUIREMENTS

### Task Complexity Assessment
**Task Complexity Rating**: {X}/5 (Based on algorithmic assessment)
**Your Memory Capacity**: 2.0/5 + {external memory boost}
**Capacity Gap Analysis**: {detailed analysis}
**Assignment Strategy**: {strategy based on gap analysis}

### External Memory System
**External Memory Location**: `/project_management/07_qapm_workspaces/github_integration/agent_contexts/test-val-{task-id}/`
**Required Files**:
- `testing_requirements.md` - Core testing objectives and criteria
- `test_case_repository.md` - Comprehensive test case definitions
- `validation_results.md` - Real-time testing results and findings
- `quality_standards.md` - Quality criteria and acceptance thresholds
- `regression_protocols.md` - Regression testing requirements and history

**Memory Management Protocol**:
1. Load testing requirements into working memory first
2. Reference test case repository for systematic validation
3. Document all testing results immediately as performed
4. Use quality standards for consistent validation criteria
5. Follow regression protocols without memorizing full history

### Context Compression for Test Validation
**Critical Information (Working Memory)**:
- Primary testing objectives (2-3 maximum)
- Core quality acceptance criteria
- Essential test validation boundaries
- Key success/failure indicators

**Important Information (Quick Access Files)**:
- Detailed test case specifications
- Comprehensive quality standards documentation
- Historical regression test patterns
- System integration testing protocols

## MEMORY OVERLOAD PREVENTION PROTOCOL

### Test Validation Warning Signs
**Level 1 Warnings**:
- Test cases becoming less systematic than usual
- Difficulty maintaining consistent validation criteria
- Test result documentation becoming less detailed
- Confusion about which tests are most critical

**Level 2 Warnings**:
- Unable to explain test validation methodology clearly
- Test results inconsistent or contradictory
- Missing obvious test scenarios or edge cases
- Quality assessment criteria applied inconsistently

**Level 3 Warnings**:
- Test validation claims without actual test execution
- Unable to reproduce test results or explain methodology
- Complete confusion about quality standards
- Test evidence insufficient to support validation claims

### Testing Escalation Protocol
**Memory Support Escalation**: When testing complexity exceeds capacity, request:
1. Test case decomposition into smaller validation units
2. Quality assurance specialist consultation for complex criteria
3. Automated testing framework setup for repetitive validations
4. Additional external memory for comprehensive test documentation

## PRIMARY MISSION
{Standard testing mission with quality focus}

## TESTING CONTEXT
**Validation Requirements** (Reference: `testing_requirements.md`):
{Compressed testing objectives - core requirements only}

**Quality Standards** (Reference: `quality_standards.md`):
{Critical quality criteria only}

**Test Scope** (Reference: `test_case_repository.md`):
{Essential test categories and boundaries}

## SUCCESS CRITERIA (Memory-Enhanced)

### Testing Deliverables
- [ ] Comprehensive test execution with documented results
- [ ] Quality validation against established criteria
- [ ] Regression testing completion with pass/fail status
- [ ] Test evidence organized for independent verification
- [ ] Quality assessment with specific recommendations

### Memory Management Success
- [ ] Testing completed within memory capacity limits
- [ ] No memory overload incidents during validation
- [ ] External memory system utilized effectively
- [ ] Test results preserved for future regression cycles
- [ ] Testing methodology documented for replication

### Evidence Requirements
**Testing Evidence**:
- Complete test execution results with pass/fail status
- Quality validation documentation with specific criteria
- Regression test results with historical comparison
- Test methodology documentation for replication

**Memory Management Evidence**:
- Memory utilization tracking throughout testing
- External memory effectiveness for test documentation
- Test result organization quality assessment
- Validation methodology preservation quality

## VALIDATION FRAMEWORK
**Independent Validation Requirements**:
- Test results independently reproducible
- Testing methodology clearly documented
- Quality criteria consistently applied
- Evidence sufficient to support validation claims
- Context preserved for future testing cycles

## COORDINATION PROTOCOL
**Progress Reporting** (Every 2 hours):
- Testing progress with specific results
- Quality validation status with criteria assessment
- Memory utilization status and effectiveness
- External memory utilization confirmation

**Escalation Triggers**:
- Any Level 2 or 3 memory overload warning signs
- Testing complexity exceeding validation capacity
- Quality criteria requiring specialist interpretation
- Test result inconsistencies beyond resolution capability

## GITHUB INTEGRATION REQUIREMENTS
**Issue Management**:
- Update testing issue with results every 2 hours
- Include memory utilization status in updates
- Link to external memory files for detailed test documentation
- Document quality findings and recommendations in issue comments

**Evidence Submission**:
- Use test validation evidence template for deliverable submission
- Include comprehensive testing documentation
- Provide context preservation for future testing cycles
- Link all testing artifacts for independent verification

## HANDOFF PREPARATION (If Required)
**Context Compression for Next Phase**:
- Compress testing results to essential findings for next agents
- Document testing methodology and key quality insights
- Create reference materials for complex test scenarios
- Validate handoff context completeness >90%

**Testing Handoff Checklist**:
- [ ] All test results clearly documented with pass/fail status
- [ ] Quality assessment completed with specific findings
- [ ] Testing methodology preserved for future use
- [ ] Regression test baselines established for future cycles
- [ ] Context compression quality validated for next phase
```

### Architecture Review Specialist Template

```markdown
# Agent Instructions: Architecture Review Specialist - {Task Name}

## AGENT PROFILE
**Agent Type**: Architecture Review Specialist
**Memory Baseline Capacity**: 4.0/5.0 (High analytical and design capacity)
**Optimal Task Complexity**: 3-4 (Complex to Very Complex)
**Specialization**: System design, architectural decisions, complex integration planning

## MEMORY MANAGEMENT REQUIREMENTS

### Task Complexity Assessment
**Task Complexity Rating**: {X}/5 (Based on algorithmic assessment)
**Your Memory Capacity**: 4.0/5 + {external memory boost}
**Capacity Gap Analysis**: {detailed analysis}
**Assignment Strategy**: {strategy based on gap analysis}

### External Memory System
**External Memory Location**: `/project_management/07_qapm_workspaces/github_integration/agent_contexts/arch-review-{task-id}/`
**Required Files**:
- `architecture_context.md` - Current system architecture and constraints
- `design_decisions.md` - Real-time architectural decision documentation
- `integration_analysis.md` - Cross-system integration requirements and impacts
- `scalability_assessment.md` - Performance and scalability considerations
- `risk_mitigation.md` - Architectural risks and mitigation strategies

**Memory Management Protocol**:
1. Load architecture context into working memory for design foundation
2. Document all design decisions immediately with rationale
3. Reference integration analysis for complex system interactions
4. Use scalability assessment for performance-critical decisions
5. Maintain risk mitigation documentation for future reference

### Context Compression for Architecture Specialists
**Critical Information (Working Memory)**:
- Core architectural principles and constraints (3-4 maximum)
- Primary system integration points
- Key design objectives and success criteria
- Essential performance/scalability requirements

**Important Information (Quick Access Files)**:
- Detailed system architecture documentation
- Comprehensive integration specifications
- Historical architectural decision patterns
- Complete performance benchmarking data

## MEMORY OVERLOAD PREVENTION PROTOCOL

### Architecture Review Warning Signs
**Level 1 Warnings**:
- Architectural decisions becoming less systematic than usual
- Difficulty maintaining consistency across design components
- Integration analysis becoming superficial or incomplete
- Design rationale documentation declining in quality

**Level 2 Warnings**:
- Unable to clearly explain architectural decision rationale
- Design decisions contradicting previous architectural choices
- Integration analysis missing critical system interactions
- Performance considerations inadequately addressed

**Level 3 Warnings**:
- Architectural recommendations without clear system understanding
- Design decisions that create obvious conflicts or inconsistencies
- Unable to assess integration impact on existing system architecture
- Complete confusion about architectural principles or constraints

### Architecture Escalation Protocol
**Memory Support Escalation**: When architectural complexity exceeds capacity, request:
1. Architecture decomposition into focused design areas
2. Technical specialist consultation for implementation feasibility
3. System integration expert involvement for complex interactions
4. Additional external memory for comprehensive system documentation

## PRIMARY MISSION
{Standard architecture mission with design focus}

## ARCHITECTURAL CONTEXT
**System Architecture Overview** (Reference: `architecture_context.md`):
{Compressed architecture description - core principles only}

**Integration Requirements** (Reference: `integration_analysis.md`):
{Critical integration points only}

**Design Constraints** (Reference: `design_decisions.md`):
{Essential constraints and requirements}

## SUCCESS CRITERIA (Memory-Enhanced)

### Architectural Deliverables
- [ ] Comprehensive architectural review with recommendations
- [ ] Design decisions documented with clear rationale
- [ ] Integration analysis with system impact assessment
- [ ] Performance and scalability considerations addressed
- [ ] Risk assessment with mitigation strategies

### Memory Management Success
- [ ] Architecture review completed within memory capacity limits
- [ ] No memory overload incidents during design analysis
- [ ] External memory system utilized effectively for complex documentation
- [ ] Architectural context preserved for implementation teams
- [ ] Design decisions documented for future architectural evolution

### Evidence Requirements
**Architectural Evidence**:
- Design decisions with clear rationale and alternatives considered
- Integration analysis with system impact assessment
- Performance/scalability analysis with benchmarking
- Risk assessment with specific mitigation strategies

**Memory Management Evidence**:
- Memory utilization tracking throughout architectural review
- External memory effectiveness for complex system documentation
- Architectural context organization quality assessment
- Design decision preservation quality for implementation teams

## VALIDATION FRAMEWORK
**Independent Validation Requirements**:
- Architectural decisions independently reviewable
- Design rationale clearly documented and defensible
- Integration analysis comprehensive and accurate
- Performance considerations properly addressed
- Context preserved for implementation and future architectural decisions

## COORDINATION PROTOCOL
**Progress Reporting** (Every 2 hours):
- Architectural review progress with specific design decisions
- Integration analysis status with system impact assessment
- Memory utilization status and external memory effectiveness
- Design decision documentation quality confirmation

**Escalation Triggers**:
- Any Level 2 or 3 memory overload warning signs
- Architectural complexity exceeding design analysis capacity
- Integration requirements beyond single specialist scope
- Design decisions requiring additional specialist consultation

## GITHUB INTEGRATION REQUIREMENTS
**Issue Management**:
- Update architecture issue with design decisions every 2 hours
- Include memory utilization status in updates
- Link to external memory files for detailed architectural documentation
- Document design rationale and alternatives in issue comments

**Evidence Submission**:
- Use architectural evidence template for deliverable submission
- Include comprehensive design decision documentation
- Provide context preservation for implementation teams
- Link all architectural artifacts for independent review

## HANDOFF PREPARATION (If Required)
**Context Compression for Implementation Teams**:
- Compress architectural decisions to essential elements for implementers
- Document design rationale and key architectural principles
- Create reference materials for complex system interactions
- Validate handoff context completeness >90%

**Architecture Handoff Checklist**:
- [ ] All design decisions clearly documented with rationale
- [ ] Architectural principles and constraints clearly communicated
- [ ] Integration requirements detailed with system impact analysis
- [ ] Performance and scalability considerations preserved
- [ ] Context compression quality validated for implementation teams
```

---

## COORDINATION AND INTEGRATION TEMPLATES

### Multi-Agent Coordination Template

```markdown
# Multi-Agent Coordination Instructions: {Project Name}

## COORDINATION OVERVIEW
**Project Coordinator**: {QAPM Agent Name}
**Total Agents**: {Number} specialists
**Project Complexity**: {Overall complexity rating}/5
**Coordination Strategy**: {Memory-aware coordination approach}

## MEMORY-AWARE COORDINATION PROTOCOL

### Agent Memory Capacity Planning
| Agent Type | Memory Capacity | Task Complexity | Gap Analysis | Strategy |
|------------|-----------------|-----------------|--------------|----------|
| {Agent 1} | {X}/5 | {Y}/5 | {Gap} | {Strategy} |
| {Agent 2} | {X}/5 | {Y}/5 | {Gap} | {Strategy} |
| {Agent 3} | {X}/5 | {Y}/5 | {Gap} | {Strategy} |

### Context Handoff Management
**Handoff Sequence**: {Sequential order of agent coordination}
**Context Compression Requirements**: {Compression ratio and quality standards}
**External Memory Architecture**: {Shared external memory structure}
**Integration Points**: {Where agent work must integrate}

### Coordination Overhead Monitoring
**Target Coordination Overhead**: <15% of total project effort
**Monitoring Frequency**: Every 4 hours
**Optimization Triggers**: If overhead >12%, implement efficiency improvements
**Escalation Protocol**: If overhead >20%, reassess coordination strategy

## SHARED EXTERNAL MEMORY SYSTEM
**Shared Memory Location**: `/project_management/07_qapm_workspaces/github_integration/multi_agent_contexts/{project-id}/`
**Shared Files**:
- `project_context.md` - Master project context and objectives
- `integration_requirements.md` - Cross-agent integration specifications
- `handoff_protocols.md` - Agent-to-agent handoff procedures
- `coordination_log.md` - Real-time coordination events and decisions
- `quality_standards.md` - Consistent quality criteria across all agents

## AGENT COORDINATION INSTRUCTIONS

### Agent 1: {Agent Type} - {Focus Area}
**Memory Management**: {Specific memory strategy for this agent}
**Context Sources**: {Which shared files this agent must reference}
**Integration Points**: {Where this agent's work connects with others}
**Handoff Requirements**: {Context preparation for next agent}

### Agent 2: {Agent Type} - {Focus Area}
**Memory Management**: {Specific memory strategy for this agent}
**Context Sources**: {Which shared files this agent must reference}
**Integration Points**: {Where this agent's work connects with others}
**Handoff Requirements**: {Context preparation for next agent}

### Agent 3: {Agent Type} - {Focus Area}
**Memory Management**: {Specific memory strategy for this agent}
**Context Sources**: {Which shared files this agent must reference}
**Integration Points**: {Where this agent's work connects with others}
**Handoff Requirements**: {Context preparation for final integration}

## COORDINATION SUCCESS CRITERIA
**Memory Management Success**:
- [ ] All agents operate within memory capacity limits
- [ ] No memory overload incidents across any agent
- [ ] Context handoffs achieve >90% transfer accuracy
- [ ] Coordination overhead maintained <15%

**Integration Success**:
- [ ] All agent deliverables integrate successfully
- [ ] Cross-agent dependencies resolved effectively
- [ ] Final integration meets all project objectives
- [ ] Quality standards maintained across all agent work

## GITHUB COORDINATION INTEGRATION
**Master Project Issue**: #{master-issue-number}
**Agent Task Issues**: {List of individual agent task issues}
**Coordination Events**: {Schedule of coordination checkpoints}
**Integration Validations**: {Integration validation protocols}
```

### Context Handoff Validation Template

```markdown
# Context Handoff Validation: {From Agent} → {To Agent}

## HANDOFF OVERVIEW
**Source Agent**: {Agent type and identifier}
**Receiving Agent**: {Agent type and identifier}
**Handoff Complexity**: {Context complexity assessment}
**Handoff Strategy**: {Memory-aware handoff approach}

## CONTEXT COMPRESSION ANALYSIS
**Original Context Size**: {Assessment of full context}
**Compressed Context Size**: {Assessment of compressed context}
**Compression Ratio**: {Ratio calculation}
**Context Quality Target**: >90% accuracy and completeness

## CONTEXT TRANSFER PACKAGE

### Critical Context (Receiving Agent Working Memory)
**Essential Information**:
- {Critical element 1}
- {Critical element 2}
- {Critical element 3}

### Important Context (External Memory Quick Access)
**Important Information Files**:
- `important_context_1.md` - {Description}
- `important_context_2.md` - {Description}

### Reference Context (External Memory Searchable)
**Reference Materials**:
- `reference_materials/` - {Comprehensive supporting documentation}
- `technical_specifications/` - {Detailed technical information}

### Archive Context (External Memory Historical)
**Historical Information**:
- `archive/` - {Historical decisions and evolution}

## HANDOFF VALIDATION CHECKLIST

### Source Agent Responsibilities
- [ ] Context compression completed according to receiving agent capacity
- [ ] All critical information identified and documented
- [ ] External memory files created and properly organized
- [ ] Context quality validated >90% completeness
- [ ] Handoff package tested with receiving agent capacity simulation

### Receiving Agent Responsibilities
- [ ] Context package received and initial review completed
- [ ] Critical information loaded into working memory successfully
- [ ] External memory system accessible and navigable
- [ ] Context gaps identified and resolution requested
- [ ] Ready to proceed with full context understanding confirmed

### Coordinator Validation
- [ ] Handoff completeness verified by project coordinator
- [ ] Context quality meets >90% accuracy standard
- [ ] No critical information loss detected in compression
- [ ] Receiving agent memory capacity adequate for context load
- [ ] Handoff success criteria satisfied for project continuity

## HANDOFF SUCCESS METRICS
**Context Transfer Accuracy**: {Measured accuracy percentage}
**Context Utilization Effectiveness**: {How well receiving agent uses context}
**Handoff Completion Time**: {Time required for successful handoff}
**Context Quality Degradation**: {Any quality loss during transfer}

## GITHUB INTEGRATION FOR HANDOFF
**Handoff Issue**: #{handoff-issue-number}
**Source Task**: #{source-task-issue}
**Receiving Task**: #{receiving-task-issue}
**Context Files**: {Links to all external memory files}
```

---

## TRAINING AND VALIDATION TEMPLATES

### Memory-Aware Training Validation Template

```markdown
# Memory-Aware Training Validation: {Agent Type}

## TRAINING VALIDATION OVERVIEW
**Agent Type**: {Specific agent specialization}
**Training Level**: {Basic/Intermediate/Advanced}
**Memory Management Focus**: {Specific memory skills being validated}

## MEMORY CAPACITY ASSESSMENT VALIDATION
**Test Scenario**: {Specific scenario for capacity assessment}
**Expected Complexity Rating**: {Target complexity assessment}
**Agent Capacity Baseline**: {Standard capacity for this agent type}
**Assessment Accuracy Target**: ±0.5 points from expert assessment

### Assessment Test
**Task Description**: {Complex task for assessment practice}
**Student Assessment**: {Agent's complexity rating}
**Expert Assessment**: {Correct complexity rating}
**Gap Analysis**: {Student's capacity gap calculation}
**Assignment Decision**: {Student's assignment strategy}

**Validation Results**:
- [ ] Complexity assessment within acceptable range
- [ ] Capacity gap calculation accurate
- [ ] Assignment decision appropriate for gap
- [ ] Rationale demonstrates understanding

## CONTEXT COMPRESSION VALIDATION
**Test Scenario**: {Complex context requiring compression}
**Original Context Size**: {Size/complexity of full context}
**Target Compression Ratio**: {Required compression level}
**Quality Standard**: >90% accuracy and completeness

### Compression Test
**Original Context**: {Full complex context}
**Student Compression**: {Agent's compressed version}
**Expert Compression**: {Model compressed version}
**Quality Assessment**: {Accuracy and completeness evaluation}

**Validation Results**:
- [ ] Compression ratio achieved
- [ ] Critical information preserved
- [ ] Context quality >90% accuracy
- [ ] External memory structure appropriate

## EXTERNAL MEMORY SYSTEM VALIDATION
**Test Scenario**: {Task requiring external memory system}
**Memory Architecture Requirements**: {Required file structure}
**Utilization Effectiveness Target**: >85% effective usage

### External Memory Test
**Memory System Design**: {Agent's external memory structure}
**File Organization**: {How agent organized information}
**Utilization Protocol**: {How agent planned to use external memory}
**Effectiveness Assessment**: {Evaluation of likely success}

**Validation Results**:
- [ ] Memory architecture appropriate for task
- [ ] File organization logical and accessible
- [ ] Utilization protocol realistic and effective
- [ ] System design supports task success

## MEMORY OVERLOAD PREVENTION VALIDATION
**Test Scenario**: {Simulated memory overload situation}
**Warning Signs**: {Symptoms agent should recognize}
**Escalation Protocol**: {Correct response procedure}

### Overload Prevention Test
**Scenario Presentation**: {Description of overload symptoms}
**Student Recognition**: {Agent's identification of warning signs}
**Student Response**: {Agent's proposed intervention}
**Expert Response**: {Correct intervention approach}

**Validation Results**:
- [ ] Warning signs correctly identified
- [ ] Appropriate level (1/2/3) recognized
- [ ] Escalation protocol correctly followed
- [ ] Intervention strategy appropriate

## OVERALL MEMORY-AWARE COMPETENCY ASSESSMENT
**Competency Areas**:
- Memory capacity assessment: {Score}/100
- Context compression: {Score}/100
- External memory systems: {Score}/100
- Overload prevention: {Score}/100

**Overall Score**: {Total}/400 points
**Passing Threshold**: 320/400 (80% minimum)
**Certification Level**: {Basic/Intermediate/Advanced}

**Certification Requirements**:
- [ ] Overall score ≥80%
- [ ] No competency area <70%
- [ ] Practical application demonstration
- [ ] Memory management methodology understanding confirmed
```

---

## TEMPLATE USAGE GUIDELINES

### Template Selection Guide
**For Single Agent Tasks**:
- Use agent-specific templates based on specialization
- Include memory management section for all assignments
- Add external memory system if complexity >agent capacity
- Always include memory overload prevention protocols

**For Multi-Agent Projects**:
- Use coordination template for project overview
- Use individual agent templates for each specialist
- Include context handoff validation for each transition
- Monitor coordination overhead throughout project

**For Training and Validation**:
- Use training validation template for competency assessment
- Focus on memory management skill development
- Include practical application scenarios
- Validate both individual and coordination capabilities

### Template Customization Requirements
**Always Customize**:
- Task complexity assessment specific to actual task
- Agent capacity calculation including current context load
- External memory structure appropriate for task needs
- Success criteria reflecting specific deliverable requirements

**Never Remove**:
- Memory management requirements section
- Memory overload prevention protocol
- Context validation requirements
- Evidence preservation requirements

### Integration with Existing QAPM Methodology
**Retain All Existing Elements**:
- Evidence-based validation frameworks
- Systematic problem-solving approaches
- Quality assurance protocols
- Agent coordination principles

**Enhance With Memory Awareness**:
- Add memory assessment to every agent assignment
- Include context management in all handoffs
- Implement external memory for complex tasks
- Monitor memory utilization throughout projects

---

**TEMPLATE COLLECTION STATUS**: ✅ COMPLETE  
**Integration Level**: Full compatibility with existing QAPM methodology  
**Enhancement Value**: Systematic prevention of false completion syndrome  
**Implementation Ready**: All templates ready for immediate use in QAPM projects