# HEMK Project Brief - Hedgehog External Management Kubernetes

**Project Name**: HEMK (Hedgehog External Management Kubernetes)  
**Parent Project**: Hedgehog NetBox Plugin (HNP)  
**Project Type**: Greenfield Infrastructure Automation Project  
**Target Completion**: 6-8 weeks (Design + Implementation)

---

## Executive Summary

The HEMK project addresses a critical gap in the Hedgehog NetBox Plugin ecosystem: providing a comprehensive, user-friendly solution for customers to deploy and manage the external Kubernetes infrastructure required to support their Hedgehog ONF fabric deployments.

**Problem Statement**: Hedgehog customers need external Kubernetes clusters to run GitOps tools (ArgoCD/Flux) and Hedgehog monitoring components (Prometheus/Grafana), but many customers come from traditional enterprise networking backgrounds and lack Kubernetes expertise.

**Solution Vision**: Create a comprehensive, opinionated platform that enables non-Kubernetes experts to easily deploy and manage a dedicated external management cluster with all necessary Hedgehog support components.

---

## Project Context & Background

### Parent Project Integration
This project is a strategic evolution of the Hedgehog NetBox Plugin (HNP), which has successfully completed MVP2 with revolutionary Git-first GitOps capabilities. The HEMK project addresses the external infrastructure dependencies that HNP requires to deliver its full value proposition.

### Previous Work Context
A previous attempt at GitOps infrastructure automation focused narrowly on ArgoCD setup wizard functionality. This approach was identified as misguided because it failed to address the broader infrastructure requirements customers need. The HEMK project takes a holistic approach to external infrastructure management.

### Technical Architecture Context
The Hedgehog ecosystem consists of multiple Kubernetes environments:

- **HCKC (Hedgehog Controller Kubernetes Cluster)**: The K8s cluster running on the Hedgehog controller, exclusively for controlling Hedgehog ONF fabrics
- **HEMK (Hedgehog External Management Kubernetes)**: External K8s cluster for running operational support tools
- **HEMCs (Hedgehog External Management Components)**: Components like GitOps tools and monitoring that may run on HEMK or customer's own infrastructure

**Critical Design Principle**: HNP must only depend on HEMCs being installed and reachable somewhere, not on how or where they are deployed.

---

## Strategic Objectives

### Primary Objectives
1. **Research & Identify**: Comprehensive identification of all HEMCs and supporting tools required for optimal Hedgehog operations
2. **Design Architecture**: Create modular, scalable architecture for HEMK deployment and management
3. **Simplify User Experience**: Enable non-Kubernetes experts to successfully deploy and operate Hedgehog external infrastructure
4. **Maintain Flexibility**: Ensure HNP works whether customers use HEMK or deploy HEMCs on their own infrastructure

### Secondary Objectives
1. **Reduce Barriers to Adoption**: Lower the technical expertise threshold for Hedgehog adoption
2. **Standardize Operations**: Provide opinionated, tested configurations for common deployment scenarios
3. **Enable Self-Service**: Allow customers to deploy and manage infrastructure through guided processes
4. **Future-Proof Design**: Create extensible foundation for additional operational tooling

---

## Technical Requirements

### Core Technology Stack
- **Kubernetes Distribution**: k3s (aligns with HCKC choice by Hedgehog ONF)
- **Package Management**: Helm charts for HEMC installation (enables reuse for customer's own clusters)
- **Configuration Management**: Environment-aware configuration for different deployment scenarios
- **Automation**: Simplified bootstrapping process for non-experts

### GitOps Integration Requirements
**Complex Multi-Repository Support**:
- Each fabric in HNP associates with exactly one GitOps directory
- Any-to-any relationship between GitOps directories and GitHub repositories
- Separate mechanisms required for:
  1. Authenticating HNP to N git repositories
  2. Associating specific GitOps directory with specific fabric

### Modular Design Requirements
- **Component Independence**: Each HEMC should be installable independently
- **Infrastructure Flexibility**: Support for HEMK or customer's own K8s clusters
- **Selective Installation**: Allow customers to choose which HEMCs to install on HEMK
- **Deployment Options**: Support different infrastructure scenarios while remaining opinionated

---

## Target Audience

### Primary Users
- **Traditional Enterprise Network Engineers**: Experts in networking who are new to Kubernetes
- **Small-to-Medium Enterprises**: Organizations without dedicated DevOps/Platform teams
- **Hedgehog Evaluators**: Teams testing Hedgehog without existing GitOps infrastructure

### User Characteristics
- Strong networking background (switching, routing, VLANs, etc.)
- Limited Kubernetes operational experience
- Preference for guided, step-by-step processes
- Need for comprehensive documentation and troubleshooting guidance
- Expectation of enterprise-grade reliability and security

---

## Research Objectives

### Phase 1: HEMC Identification Research
**Agent Profile Required**: Kubernetes expert with deep knowledge of cloud-native operational tooling

**Research Questions**:
1. What are ALL Hedgehog External Management Components that should run on HEMK?
2. What operational tools enhance the management of HEMCs on a dedicated cluster?
3. What are the dependencies and integration patterns between these components?
4. What are the security, networking, and storage requirements for each component?

**Known HEMCs to Research**:
- GitOps Tools: ArgoCD, Flux
- Monitoring Stack: Hedgehog Prometheus/Grafana dashboards and related components

**Unknown HEMCs to Discover**:
- Additional Hedgehog ONF operational tools
- Complementary cloud-native tooling that enhances Hedgehog operations
- Integration tooling for enterprise environments

### Phase 2: Operational Tooling Research
**Research Scope**: General Kubernetes operational tools that enhance HEMK management

**Categories to Investigate**:
- **Certificate Management**: LetsEncrypt, cert-manager
- **Ingress Controllers**: For web UI access to HEMCs
- **Storage Management**: Persistent volume solutions for k3s
- **Security Tooling**: Network policies, pod security standards
- **Backup and Recovery**: Cluster and application backup solutions
- **Monitoring and Observability**: Cluster health monitoring (separate from Hedgehog monitoring)

---

## Design Constraints

### Scope Limitations
**Opinionated Approach**: Focus on 1-2 well-tested deployment patterns rather than comprehensive coverage of all possible scenarios.

**Excluded Scenarios**:
- Complex multi-cloud deployments
- Advanced Kubernetes distributions (OpenShift, Tanzu) - customers with these can deploy HEMCs independently
- Bare-metal multi-node clusters requiring advanced networking
- Custom security frameworks requiring specialized configuration

**Included Scenarios**:
- Single-node k3s on VM (hypervisor-agnostic)
- Simple multi-node k3s cluster
- Cloud-managed Kubernetes (AWS EKS, Azure AKS, GCP GKE) - basic configurations only

### Resource Constraints
- **Development Time**: Limited resources for comprehensive scenario coverage
- **Maintenance Burden**: Must avoid creating maintenance overhead for edge cases
- **Documentation Scope**: Focus on common deployment patterns with comprehensive guidance

---

## Success Criteria

### Technical Success Metrics
1. **Comprehensive HEMC Catalog**: Complete identification and documentation of all required external management components
2. **Simplified Deployment**: Single-command or wizard-driven HEMK deployment process
3. **Modular Installation**: Ability to selectively install HEMCs based on customer needs
4. **Integration Testing**: Successful integration with HNP GitOps workflows
5. **Documentation Quality**: Complete user guides for target audience skill level

### User Experience Success Metrics
1. **Time to Value**: Non-Kubernetes expert can deploy functional HEMK in under 2 hours
2. **Self-Service Capability**: Minimal support required for standard deployment scenarios
3. **Error Recovery**: Clear troubleshooting guidance for common failure scenarios
4. **Maintenance Simplicity**: Straightforward upgrade and management processes

### Business Success Metrics
1. **Adoption Enablement**: Reduces technical barriers for Hedgehog evaluation and adoption
2. **Support Reduction**: Decreases support burden for external infrastructure issues
3. **Customer Satisfaction**: Positive feedback on simplified deployment experience

---

## Project Phases

### Phase 1: Research & Discovery (2-3 weeks)
- Comprehensive HEMC identification
- Operational tooling research
- Architecture requirements analysis
- User experience design principles

### Phase 2: Architecture & Design (1-2 weeks)
- Technical architecture specification
- Deployment pattern definition
- Integration point design
- Security and compliance framework

### Phase 3: Implementation Planning (1 week)
- Development task breakdown
- Resource allocation
- Testing strategy definition
- Documentation planning

### Phase 4: Implementation (2-3 weeks)
- Core platform development
- HEMC integration implementation
- User experience development
- Testing and validation

---

## Dependencies & Relationships

### HNP Integration Points
- Must maintain compatibility with existing HNP GitOps workflows
- Should enhance but not replace existing HNP functionality
- Must support customer choice between HEMK and independent HEMC deployment

### External Dependencies
- Kubernetes ecosystem tool compatibility
- Cloud provider integration requirements
- Hypervisor platform considerations
- Enterprise networking integration needs

### Deliverable Dependencies
- Research findings inform architecture decisions
- Architecture drives implementation planning
- Implementation requires comprehensive testing strategy
- User experience depends on complete documentation

---

**Project Manager Role**: Lead comprehensive research, design, and implementation planning phases. Coordinate with specialized agents for technical research and development tasks. Ensure deliverables meet strategic objectives while maintaining flexibility for diverse customer environments.

**Next Immediate Action**: Begin Phase 1 research by dispatching Kubernetes expert agent for comprehensive HEMC identification and operational tooling analysis.