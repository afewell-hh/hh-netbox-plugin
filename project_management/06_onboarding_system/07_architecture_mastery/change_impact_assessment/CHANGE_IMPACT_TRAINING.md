# Change Impact Assessment Training - Level 3 (Technical Agents)

**CRITICAL MISSION**: Ensure technical agents systematically assess architectural implications before making changes, preventing regression cycles caused by uncoordinated modifications.

## 🎯 Training Objectives

**PRIMARY COMPETENCY**: Review current architecture documentation and assess potential impacts on related components before making any technical changes.

**SECONDARY COMPETENCIES**:
- Document architectural implications of proposed changes
- Coordinate changes with architectural requirements
- Identify cross-component dependencies and integration points
- Escalate complex architectural implications appropriately

## 📚 Change Impact Assessment Framework

### Pre-Change Architecture Review Process

**MANDATORY ASSESSMENT STEPS**:
1. **Current State Analysis**: Review existing architecture documentation
2. **Component Dependency Mapping**: Identify affected system components  
3. **Integration Point Analysis**: Assess impacts on component interfaces
4. **Architectural Constraint Review**: Verify compliance with architectural decisions
5. **Risk Assessment**: Evaluate potential for regression or system issues

### Impact Assessment Categories

**CATEGORY 1: Component-Internal Changes**
- Changes affecting single component without external interfaces
- Implementation details within established architectural patterns
- Low risk but still requires architectural awareness

**CATEGORY 2: Cross-Component Changes**  
- Changes affecting interfaces between system components
- Modifications to data flow or communication patterns
- Medium risk requiring coordination analysis

**CATEGORY 3: System-Wide Changes**
- Changes affecting multiple components or system architecture
- Modifications to core patterns or integration approaches
- High risk requiring comprehensive impact assessment

**CATEGORY 4: Architectural Pattern Changes**
- Changes to fundamental system patterns or approaches
- Modifications requiring new ADRs or ADR updates
- Highest risk requiring architectural decision process

## 🔍 Impact Assessment Methodology

### Step 1: Current Architecture Analysis

**REQUIRED REVIEW PROCESS**:
```markdown
1. System Overview Review: /architecture_specifications/00_current_architecture/system_overview.md
2. Component Analysis: Navigate to relevant component specifications
3. Integration Review: Check component interaction patterns
4. ADR Review: Review relevant architectural decisions
5. Operational Status: Verify current system health and status
```

**DOCUMENTATION REQUIRED**:
```markdown
Current State Assessment:
- Component(s) being modified: [List]
- Current architecture patterns: [Description]
- Existing integration points: [List]
- Relevant ADRs: [References]
- Current operational status: [Status]
```

### Step 2: Change Scope Analysis

**SCOPE IDENTIFICATION PROCESS**:
```markdown
Direct Impact: What components will be directly modified?
Interface Impact: What component interfaces will change?
Data Flow Impact: How will data flow patterns be affected?
Integration Impact: What integration points will be modified?
Pattern Impact: Will this change established architectural patterns?
```

**IMPACT MATRIX CREATION**:
```markdown
| Component | Direct Impact | Interface Changes | Integration Points | Risk Level |
|-----------|---------------|-------------------|-------------------|------------|
| [Name]    | [Yes/No]      | [Description]     | [List]            | [H/M/L]    |
```

### Step 3: Risk Assessment Framework

**RISK EVALUATION CRITERIA**:

**HIGH RISK INDICATORS**:
- Changes to core system patterns
- Modifications affecting multiple components
- Interface changes requiring coordination
- Security or authentication modifications
- Performance-critical path changes

**MEDIUM RISK INDICATORS**:
- Single component changes with external interfaces
- Data model modifications
- UI changes affecting user workflows
- Configuration changes affecting multiple environments

**LOW RISK INDICATORS**:
- Internal component implementation details
- Cosmetic changes without functional impact
- Bug fixes within established patterns
- Documentation updates without code changes

## 🧭 Impact Assessment Exercises

### Exercise 1: Component-Internal Change Assessment
**Scenario**: Optimize database query performance in GitRepository model.

**Required Assessment Process**:
1. **Current State**: Review `/00_current_architecture/component_architecture/netbox_plugin_layer.md`
2. **Component Analysis**: Identify GitRepository model usage patterns
3. **Interface Review**: Check if query changes affect external interfaces
4. **Risk Assessment**: Evaluate impact on system performance and stability
5. **Documentation**: Record assessment findings and risk mitigation

**Success Criteria**: Complete impact assessment identifying optimization as low-risk component-internal change.

### Exercise 2: Cross-Component Change Assessment  
**Scenario**: Add new authentication method for GitOps repositories.

**Required Assessment Process**:
1. **System Review**: Analyze authentication architecture across components
2. **ADR Review**: Review ADR-003: Repository Separation Design
3. **Integration Analysis**: Map authentication touchpoints across system
4. **Interface Impact**: Assess changes to authentication interfaces
5. **Coordination Requirements**: Identify required component coordination

**Success Criteria**: Comprehensive assessment identifying all affected components and coordination requirements.

### Exercise 3: System-Wide Change Assessment
**Scenario**: Implement real-time drift detection with WebSocket notifications.

**Required Assessment Process**:
1. **Architecture Analysis**: Review drift detection and notification patterns
2. **Multi-Component Impact**: Assess frontend, backend, and K8s integration changes
3. **Pattern Analysis**: Evaluate need for new architectural patterns
4. **ADR Requirements**: Determine if new ADRs are needed
5. **Risk Mitigation**: Plan phased implementation to manage system-wide impact

**Success Criteria**: Complete system-wide impact assessment with risk mitigation strategy.

## ⚠️ Critical Assessment Rules

### Rule 1: NEVER Skip Pre-Change Architecture Review
**VIOLATION CONSEQUENCES**:
- Changes break existing architectural patterns
- Regression cycles from uncoordinated modifications  
- Integration failures due to interface mismatches
- Performance degradation from architectural conflicts

**COMPLIANCE REQUIREMENT**: Complete architecture review before any technical changes.

### Rule 2: Document All Architectural Implications
**INSUFFICIENT ASSESSMENT**:
- Casual impact consideration without documentation
- Focus only on immediate change without broader implications
- Missing cross-component dependency analysis

**COMPLIANCE REQUIREMENT**: Document comprehensive impact assessment for all changes.

### Rule 3: Escalate Complex Impact Scenarios
**ESCALATION TRIGGERS**:
- High-risk changes affecting multiple components
- Uncertainty about architectural implications
- Potential conflicts with existing ADRs
- System-wide performance or security implications

**COMPLIANCE REQUIREMENT**: Escalate complex architectural impacts for guidance.

## 🔍 Assessment Validation Framework

### Validation Test 1: Risk Classification Accuracy
**Challenge**: Correctly classify impact risk level for various change scenarios.
**Pass Criteria**: 100% accurate risk classification with proper rationale.
**Failure Action**: Review risk criteria and practice with additional scenarios.

### Validation Test 2: Component Dependency Identification
**Challenge**: Identify all components affected by proposed changes.
**Pass Criteria**: Complete dependency mapping with no missed components.
**Failure Action**: Practice system architecture navigation and dependency tracing.

### Validation Test 3: Impact Documentation Quality
**Challenge**: Create comprehensive impact assessment documentation.
**Pass Criteria**: Complete assessment covering all required elements.
**Failure Action**: Review assessment framework and documentation requirements.

## 📊 Change Impact Mastery Evidence

### Assessment Process Indicators
- **Pre-Change Review**: Always reviews architecture before technical changes
- **Comprehensive Analysis**: Covers all impact categories systematically
- **Risk Awareness**: Correctly identifies and classifies change risks
- **Documentation Quality**: Creates complete impact assessments

### Coordination Indicators  
- **Cross-Component Awareness**: Identifies dependencies across system components
- **Integration Planning**: Plans for interface and integration changes
- **ADR Compliance**: Ensures changes align with architectural decisions
- **Escalation Appropriateness**: Escalates complex impacts appropriately

## 🚀 Advanced Impact Assessment Skills

### Skill Enhancement: Complex System Analysis
**ADVANCED CAPABILITIES**:
- Multi-layer impact analysis across application tiers
- Performance impact assessment for high-scale scenarios
- Security impact analysis for authentication and authorization changes
- Backward compatibility assessment for API and interface changes

### Skill Enhancement: Impact Mitigation Planning
**RISK MANAGEMENT SKILLS**:
- Phased implementation planning for high-risk changes
- Rollback strategy development for critical system changes
- Testing strategy alignment with impact assessment findings
- Change coordination planning across multiple development teams

## ⚡ Impact Assessment Quick Reference

### Pre-Change Review Checklist
```markdown
Architecture Review:
□ Current system architecture documentation reviewed
□ Relevant ADRs identified and analyzed
□ Component specifications reviewed for affected areas
□ Integration points and interfaces mapped
□ Current operational status verified
```

### Impact Analysis Checklist
```markdown
Impact Assessment:
□ Direct component impacts identified
□ Cross-component dependencies mapped
□ Interface changes documented
□ Integration point modifications assessed
□ Risk level classified with rationale
□ Mitigation strategies identified
```

### Documentation Checklist
```markdown
Assessment Documentation:
□ Current state analysis completed
□ Change scope clearly defined
□ Impact matrix created for affected components
□ Risk assessment with mitigation strategies
□ Coordination requirements identified
□ Escalation triggers documented
```

### Risk Classification Reference
```markdown
HIGH RISK:
✓ Multiple component changes
✓ Core pattern modifications
✓ Security/authentication changes
✓ Performance-critical modifications

MEDIUM RISK:
✓ Single component with external interfaces
✓ Data model changes
✓ User workflow modifications

LOW RISK:
✓ Internal implementation details
✓ Cosmetic changes only
✓ Documentation updates
✓ Bug fixes within patterns
```

**CHANGE IMPACT ASSESSMENT TRAINING COMPLETE**: Agent can systematically assess architectural implications before making changes, preventing regression cycles through comprehensive impact analysis.