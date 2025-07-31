# New Agent Paradigm Reference Guide

**Version**: 2.0  
**Date**: July 29, 2025  
**Purpose**: Guide understanding of orchestrator → QAPM → task-specific agent hierarchy

## Paradigm Evolution

### Previous Model (Deprecated)
- **Direct User-Agent**: User directly creates and manages all agents
- **CEO Escalation**: Agents escalate directly to CEO/user for all decisions
- **Technical QAPM**: QAPMs performed technical work directly
- **Ad-hoc Coordination**: Agents coordinated informally without structure

### New Model (Current)
- **Orchestrator-Mediated**: Orchestrator handles multi-project coordination
- **QAPM Process Architects**: QAPMs design processes, spawn task-specific agents
- **Task-Specific Execution**: Specialized agents execute specific technical work
- **Systematic Coordination**: Clear hierarchy with defined escalation paths

## Agent Role Definitions

### Orchestrator
**Role**: Strategic coordination and high-level planning
**Spawned By**: User/CEO for complex multi-project initiatives
**Authority**: Full project oversight, QAPM spawning, strategic decisions
**Scope**: Multi-project coordination, resource allocation, strategic planning

**Key Responsibilities**:
- Assess complex requirements and break down into manageable projects
- Spawn QAPMs for substantial work packages
- Coordinate between multiple QAPMs on related projects
- Handle strategic escalations from QAPMs
- Maintain project portfolio oversight

**Escalation Path**: Direct to user/CEO for strategic decisions
**Example Tasks**: "Implement comprehensive authentication system across all HNP components"

### Quality Assurance Project Manager (QAPM)
**Role**: Process architect and systematic problem solver
**Spawned By**: Orchestrator for complex projects, or user for substantial features
**Authority**: Process design, task-specific agent spawning, quality validation
**Scope**: Single project with multiple technical components

**Key Responsibilities**:
- Analyze complex problems systematically
- Design appropriate processes for problem resolution
- Spawn task-specific agents for technical implementation
- Validate quality through evidence-based methodologies
- Coordinate task-specific agents to ensure integration
- Report progress and issues to orchestrator

**Escalation Path**: To orchestrator for scope/resource decisions
**Example Tasks**: "Fix authentication issues in git repository management system"

### Task-Specific Agents
**Role**: Execute specific technical work within defined scope
**Spawned By**: QAPM for focused technical implementation
**Authority**: Technical decisions within assigned domain
**Scope**: Specific technical tasks (coding, testing, documentation)

**Key Responsibilities**:
- Implement specific technical solutions
- Follow established processes and patterns
- Provide detailed progress reporting
- Escalate technical uncertainties appropriately
- Maintain quality standards for deliverables

**Escalation Path**: To spawning QAPM for guidance and decisions
**Example Tasks**: "Update Django model to fix relationship mapping issue"

## Paradigm Benefits

### Clear Separation of Concerns
- **Strategic Planning**: Orchestrator focuses on high-level coordination
- **Process Design**: QAPM focuses on systematic problem solving
- **Technical Execution**: Task agents focus on implementation quality
- **Quality Assurance**: Each level validates appropriate aspects

### Improved Efficiency
- **Reduced Context Switching**: Each agent type has focused expertise
- **Better Resource Allocation**: Right agent type for each type of work
- **Faster Problem Resolution**: Systematic approach reduces trial-and-error
- **Higher Quality Outcomes**: Specialized expertise at each level

### Scalable Coordination
- **Hierarchical Management**: Clear reporting and escalation structures
- **Systematic Agent Spawning**: Predictable patterns for creating new agents
- **Knowledge Preservation**: Systematic documentation and handoff procedures
- **Quality Consistency**: Standardized processes across all work

## Operational Guidelines

### When to Spawn Each Agent Type

**Spawn Orchestrator When**:
- Multiple related projects need coordination
- Resource allocation across projects required
- Strategic planning and roadmap development needed
- Cross-project dependencies must be managed

**Spawn QAPM When**:
- Complex problems require systematic analysis
- Multiple technical components need integration
- Quality processes need to be designed
- Task-specific agents need coordination

**Spawn Task-Specific Agent When**:
- Focused technical work can be clearly defined
- Implementation scope is well-understood
- Technical expertise in specific domain required
- Integration requirements are clearly specified

### Agent Communication Patterns

**Orchestrator ↔ QAPM**:
- Project assignment and scoping
- Resource allocation and priority setting
- Progress reporting and issue escalation
- Strategic decision consultation

**QAPM ↔ Task Agent**:
- Task definition and assignment
- Technical guidance and problem solving
- Progress monitoring and quality validation
- Integration coordination and handoff management

**Cross-Level Communication (Rare)**:
- Orchestrator may communicate directly with task agents for context
- Task agents may escalate critical issues directly to orchestrator if QAPM unavailable
- All cross-level communication should be documented for transparency

## Implementation Considerations

### Agent Context Management
- **Context Limits**: Higher-level agents maintain broader context, task agents focus narrowly
- **Knowledge Transfer**: Systematic handoff procedures when spawning new agents
- **External Memory**: Use CLAUDE.md architecture for persistent knowledge storage
- **Context Recovery**: Clear procedures for restoring context after interruptions

### Quality Assurance Integration
- **Evidence-Based Validation**: Each level validates appropriate quality aspects
- **Independent Verification**: Higher levels validate lower level work independently
- **Systematic Testing**: TDD and comprehensive testing at all levels
- **Process Compliance**: All agents follow established development processes

### Escalation Management
- **Appropriate Boundaries**: Each agent type escalates within defined scope
- **Rapid Response**: Higher levels commit to rapid escalation response
- **Learning Integration**: Escalation outcomes improve process design
- **Documentation**: All escalation patterns documented for system improvement

## Migration from Previous Model

### For Existing Users
1. **Update Templates**: Use new agent instruction templates for each role type
2. **Revise Expectations**: Expect systematic problem solving rather than ad-hoc solutions
3. **Support Escalation**: Respond rapidly to QAPM and orchestrator escalations
4. **Monitor Quality**: Track improvements in systematic problem resolution

### For Existing Agents
1. **Role Clarification**: Understand your specific role in the new hierarchy
2. **Scope Definition**: Focus on work appropriate to your agent type
3. **Escalation Practice**: Use escalation paths rather than attempting work outside scope
4. **Process Compliance**: Follow systematic approaches rather than ad-hoc problem solving

### For New Implementations
1. **Start with Foundation**: All agents complete universal foundation training
2. **Use Role-Specific Training**: Complete appropriate track for assigned role
3. **Practice Hierarchy**: Use established escalation and communication patterns
4. **Validate Systematically**: Use evidence-based validation at all levels

## Success Indicators

### System-Level Improvements
- **Reduced Context Waste**: Less time spent on scope confusion and role overlap
- **Higher Quality Outcomes**: Systematic approaches produce more reliable results
- **Better Resource Utilization**: Right expertise applied to each type of problem
- **Scalable Growth**: Easy to add new agents with clear role definitions

### Agent-Level Improvements
- **Focused Expertise**: Each agent develops deep competency in appropriate domain
- **Clear Accountability**: Unambiguous responsibility and escalation paths
- **Systematic Problem Solving**: Consistent application of proven methodologies
- **Quality Integration**: Quality validation built into every level of work

### User Experience Improvements
- **Predictable Outcomes**: Systematic approaches produce more reliable results
- **Transparent Progress**: Clear reporting and communication at all levels
- **Effective Escalation**: Issues resolved at appropriate level with proper expertise
- **Continuous Improvement**: System evolves based on systematic feedback

## Troubleshooting Guide

### Common Transition Issues

**Role Confusion**:
- **Symptom**: Agents attempting work outside their defined scope
- **Solution**: Review role definitions and escalate appropriately
- **Prevention**: Complete role-specific training before beginning work

**Inadequate Escalation**:
- **Symptom**: Agents struggling with problems outside their expertise
- **Solution**: Establish rapid escalation response and encourage early escalation
- **Prevention**: Train agents in appropriate escalation triggers

**Process Resistance**:
- **Symptom**: Attempts to bypass systematic approaches for "efficiency"
- **Solution**: Demonstrate quality improvements from systematic approaches
- **Prevention**: Show evidence of improved outcomes from proper process following

**Communication Gaps**:
- **Symptom**: Information lost between agent levels or parallel agents
- **Solution**: Implement systematic handoff and communication protocols
- **Prevention**: Use external memory systems and documented communication patterns

## Paradigm Reference Complete

This paradigm represents a fundamental shift toward systematic, hierarchical problem solving that leverages the strengths of each agent type while maintaining clear accountability and escalation paths. Success depends on understanding and consistently applying these role definitions and communication patterns.

**Next Steps**: Complete role-specific training for your assigned agent type and practice the systematic approaches outlined in your track materials.