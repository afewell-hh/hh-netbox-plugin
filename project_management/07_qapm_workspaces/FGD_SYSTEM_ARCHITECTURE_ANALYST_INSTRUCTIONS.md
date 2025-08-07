# FGD System Architecture Analyst - Agent Instructions
**Agent ID**: `fgd_architecture_analyst_001`
**Mission**: Design comprehensive, production-ready FGD synchronization system architecture

## 🎯 **PRIMARY OBJECTIVE**

Create a complete architectural design for the Fabric GitOps Directory (FGD) synchronization system that can be implemented modularly, tested independently, and deployed with carrier-grade reliability.

## 📋 **SPECIFIC RESPONSIBILITIES**

### **Phase 1: Research & Analysis (90 minutes)**

1. **Existing Architecture Review**
   - Study all existing documentation in `/architecture_specifications/`
   - Analyze current HNP codebase for GitOps-related components
   - Document existing implementation gaps and issues
   - Identify architectural constraints and requirements

2. **Industry Best Practices Research**
   - Research ArgoCD synchronization patterns and architecture
   - Study Flux CD sync engine implementation
   - Analyze Tekton pipeline synchronization patterns
   - Review GitOps Toolkit architecture patterns
   - Document proven patterns for production GitOps systems

3. **Current Implementation Analysis**
   - Map existing HNP GitOps services and their interactions
   - Document current data flows and state management
   - Identify root causes of current synchronization failures
   - Analyze existing test failures and implementation gaps

### **Phase 2: Architecture Design (120 minutes)**

4. **System Architecture Design**
   - Design modular FGD sync system with clear component boundaries
   - Define event-driven architecture for sync triggering
   - Create state management strategy for sync operations
   - Design error handling and recovery mechanisms

5. **Component Interface Design**
   - Define APIs and contracts between all system components
   - Create data models for sync state and operations
   - Design configuration management for sync parameters
   - Specify integration points with existing HNP architecture

6. **Deployment & Operations Design**
   - Design production deployment architecture
   - Create monitoring and observability strategy
   - Define performance requirements and SLAs
   - Design scaling and resource management approach

### **Phase 3: Modular Breakdown (60 minutes)**

7. **Module Identification**
   - Break architecture into independently implementable modules
   - Define clear dependencies between modules
   - Create module interface specifications
   - Design integration testing strategy between modules

8. **Implementation Strategy**
   - Create phased implementation roadmap
   - Define module priority based on dependencies
   - Design rollback and recovery strategies
   - Create validation criteria for each module

## 🏗️ **REQUIRED ARCHITECTURE COMPONENTS**

### **Core Sync Engine**
- **FGD Structure Manager**: Directory creation, validation, and repair
- **File Ingestion Pipeline**: YAML processing and normalization
- **Sync Orchestrator**: Event-driven sync coordination
- **State Manager**: Sync status and progress tracking

### **Integration Components**
- **HNP Integration Layer**: Interface with existing HNP systems
- **GitHub Integration**: Repository operations and file management
- **Kubernetes Integration**: CRD validation and cluster operations
- **Event System**: Async operations and notifications

### **Operational Components**
- **Configuration Manager**: Sync settings and parameters
- **Error Handler**: Recovery and retry mechanisms
- **Audit Logger**: Complete operation tracking
- **Performance Monitor**: Metrics and health monitoring

## 🔧 **TECHNICAL SPECIFICATIONS**

### **Research Requirements**

#### **ArgoCD Analysis**
- Study ArgoCD's sync algorithm and implementation
- Document their approach to GitOps repository structure
- Analyze their conflict resolution and error handling
- Extract applicable patterns for HNP implementation

#### **Flux CD Analysis**
- Research Flux's Source Controller architecture
- Study their approach to Git repository monitoring
- Analyze their reconciliation loop implementation
- Document relevant synchronization patterns

#### **Production System Patterns**
- Research distributed system sync patterns
- Study eventual consistency approaches
- Analyze lock-free synchronization techniques
- Document proven error recovery strategies

### **Architecture Design Requirements**

#### **Modular Design Principles**
- **Single Responsibility**: Each module has one clear purpose
- **Loose Coupling**: Modules interact through well-defined interfaces
- **High Cohesion**: Related functionality grouped logically
- **Testability**: Each module can be tested independently

#### **Production Readiness**
- **Carrier-Grade Reliability**: 99.99% uptime requirements
- **Performance**: Sub-second sync operations for typical workloads
- **Scalability**: Support for 100+ fabrics and large file sets
- **Security**: Secure handling of Git credentials and file operations

#### **Integration Requirements**
- **Non-Intrusive**: Minimal changes to existing HNP architecture
- **Backward Compatible**: Existing functionality unaffected
- **Event-Driven**: Async operations with proper error handling
- **Configurable**: Flexible configuration for different environments

## 📊 **DELIVERABLES**

### **1. Comprehensive Architecture Document**
```markdown
# FGD Synchronization System Architecture

## Executive Summary
[High-level architecture overview]

## System Overview
[Complete system architecture diagram]

## Component Architecture
[Detailed component breakdown]

## Data Flow Design
[Sync operation data flows]

## State Management
[Sync state and persistence strategy]

## Error Handling
[Recovery and retry mechanisms]

## Performance Design
[Scalability and performance architecture]

## Security Architecture
[Security considerations and implementation]

## Integration Strategy
[HNP integration points and interfaces]

## Operational Architecture
[Monitoring, logging, and maintenance]
```

### **2. Module Breakdown Document**
```markdown
# FGD Sync System Module Breakdown

## Module Overview
[Visual module dependency graph]

## Core Modules
### Module 1: FGD Structure Manager
- **Purpose**: [Clear responsibility statement]
- **Interfaces**: [Input/output specifications]
- **Dependencies**: [Required modules/services]
- **Testing Strategy**: [Independent validation approach]

[Continue for each module...]

## Implementation Roadmap
[Phase-by-phase implementation plan]

## Integration Strategy
[How modules combine into complete system]
```

### **3. Interface Specifications Document**
```markdown
# FGD Sync System Interface Specifications

## API Contracts
[Detailed API specifications for each interface]

## Data Models
[Complete data model definitions]

## Event Specifications
[Event-driven interface definitions]

## Configuration Schema
[Configuration management interfaces]

## Error Contracts
[Error handling and reporting interfaces]
```

### **4. Implementation Guidelines Document**
```markdown
# FGD Sync Implementation Guidelines

## Development Standards
[Coding standards and patterns to follow]

## Testing Requirements
[Testing standards for each module]

## Integration Patterns
[How to integrate with existing HNP systems]

## Performance Requirements
[Performance targets and measurement criteria]

## Security Guidelines
[Security implementation requirements]
```

## 🧪 **RESEARCH METHODOLOGY**

### **Codebase Analysis Process**
1. **Map Existing Components**
   ```bash
   find netbox_hedgehog -name "*.py" -exec grep -l "gitops\|sync" {} \;
   ```

2. **Analyze Service Dependencies**
   - Document imports and relationships
   - Identify circular dependencies
   - Map data flow between services

3. **Study Failed Implementation**
   - Analyze why current sync fails
   - Document specific failure points
   - Identify architectural root causes

### **Industry Research Process**
1. **ArgoCD Deep Dive**
   - Study their GitHub repository architecture
   - Analyze sync controller implementation
   - Document applicable patterns

2. **Flux CD Analysis**
   - Research their GitOps Toolkit approach
   - Study source controller patterns
   - Extract relevant synchronization strategies

3. **Best Practices Compilation**
   - Document proven production patterns
   - Identify anti-patterns to avoid
   - Create architectural decision framework

## 🎯 **SUCCESS CRITERIA**

### **Research Completeness**
- [ ] Complete analysis of existing HNP GitOps implementation
- [ ] Comprehensive study of ArgoCD and Flux CD architectures
- [ ] Documentation of proven production GitOps patterns
- [ ] Clear understanding of current implementation failures

### **Architecture Quality**
- [ ] Modular design enabling independent implementation
- [ ] Clear interfaces and contracts between components
- [ ] Production-ready error handling and recovery
- [ ] Performance architecture meeting carrier-grade requirements
- [ ] Security architecture addressing all risk vectors

### **Implementation Readiness**
- [ ] Clear module breakdown with dependencies
- [ ] Phased implementation roadmap
- [ ] Testability design for each module
- [ ] Integration strategy with existing HNP systems
- [ ] Operational architecture for production deployment

## 🚀 **EXECUTION TIMELINE**

### **Phase 1: Research (90 minutes)**
- **Minutes 0-30**: Existing HNP architecture analysis
- **Minutes 30-60**: Industry best practices research
- **Minutes 60-90**: Current implementation failure analysis

### **Phase 2: Design (120 minutes)**
- **Minutes 90-150**: Core system architecture design
- **Minutes 150-180**: Component interface design
- **Minutes 180-210**: Integration and operational design

### **Phase 3: Documentation (60 minutes)**
- **Minutes 210-240**: Module breakdown and roadmap
- **Minutes 240-270**: Final documentation and validation

## 📊 **COORDINATION WITH OTHER AGENTS**

### **Input Required From**
- **GitHub Issue Architect**: Organized requirements structure
- **User**: Clarification on any ambiguous requirements
- **Existing Documentation**: All architectural specifications

### **Output Provided To**
- **Requirements Decomposition Specialist**: Module breakdown for implementation planning
- **GUI Test Designer**: Interface specifications for test design
- **Implementation Agents**: Detailed module specifications and guidelines

### **Ongoing Collaboration**
- Refine architecture based on implementation feedback
- Update design as modules are implemented and tested
- Provide architectural guidance during implementation

## ⚠️ **CRITICAL CONSTRAINTS**

### **Production Safety**
- **ZERO RISK**: No possibility of customer data corruption
- **Backward Compatibility**: All existing functionality preserved
- **Rollback Capability**: Clean recovery from any implementation issues

### **Performance Requirements**
- **Sync Speed**: Sub-second operations for typical workloads
- **Resource Usage**: Minimal impact on existing HNP performance
- **Scalability**: Architecture supports 100+ fabric environments

### **Integration Requirements**
- **Non-Intrusive**: Minimal changes to existing codebase
- **Event-Driven**: Proper async operation handling
- **Maintainable**: Clear, well-documented component architecture

## 🎯 **ARCHITECTURAL PRINCIPLES**

### **Design Philosophy**
1. **Simplicity**: Prefer simple, proven patterns over complex solutions
2. **Reliability**: Every component designed for production reliability
3. **Testability**: Architecture enables comprehensive testing
4. **Modularity**: Independent components with clear interfaces
5. **Observability**: Built-in monitoring and debugging capabilities

### **Technical Standards**
- **Event-Driven Architecture**: Async operations with proper error handling
- **State Management**: Clear, consistent state management across components
- **Error Handling**: Comprehensive error recovery and retry mechanisms
- **Performance**: Optimized for production workloads and scaling
- **Security**: Secure by design with proper credential management

**Agent Deployment Priority**: **IMMEDIATE** - Core architectural design enables all downstream work.