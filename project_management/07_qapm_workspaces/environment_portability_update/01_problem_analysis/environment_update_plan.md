# Environment Portability Update Plan

**Plan Date**: July 31, 2025  
**Planning Agent**: Problem Scoping Specialist  
**Scope**: HNP Onboarding Documentation System  
**Objective**: Replace hardcoded environment references with .env variable usage

## Executive Summary

This plan outlines a systematic approach to eliminate 52 hardcoded environment references across 21 files in the HNP onboarding system. The plan prioritizes security-critical items, implements comprehensive .env variable substitution, and ensures documentation portability across different development environments.

## Implementation Strategy

### Phase-Based Approach

**Phase 1: Security Remediation** (Immediate - 1 day)
- Remove exposed authentication tokens
- Secure token files
- Update security-critical documentation

**Phase 2: Core Environment Framework** (2-3 days)
- Create comprehensive .env template
- Update environment master documentation
- Implement variable substitution patterns

**Phase 3: Template and Training Updates** (3-4 days)
- Update all agent instruction templates
- Modify training and foundation materials
- Update specialist lead instructions

**Phase 4: Tool and Management Updates** (2-3 days)
- Update file organization tools
- Modify management protocols
- Update deployment guides

**Phase 5: Validation and Testing** (1-2 days)
- Comprehensive documentation testing
- Agent training validation
- Environment portability verification

**Total Timeline**: 9-13 days with systematic implementation

## Phase 1: Security Remediation (IMMEDIATE)

### Critical Security Actions

**1.1 Remove Exposed Token Files**
```bash
# IMMEDIATE ACTION REQUIRED
rm /home/ubuntu/cc/hedgehog-netbox-plugin/project_management/06_onboarding_system/04_environment_mastery/development_tools/github.token.b64
rm /home/ubuntu/cc/hedgehog-netbox-plugin/project_management/06_onboarding_system/04_environment_mastery/development_tools/netbox.token
```

**1.2 Create Secure Token Reference Documentation**
Replace token files with:
```markdown
# Authentication Tokens (Reference Only)

**GitHub Token**: Available via `${GITHUB_TOKEN}` environment variable
**NetBox Token**: Available via `${NETBOX_TOKEN}` environment variable

**Security Note**: Actual tokens are managed through .env configuration.
Never commit actual tokens to documentation files.
```

**1.3 Update Token References in Documentation**
Files requiring immediate security updates:
- `/04_environment_mastery/ENVIRONMENT_MASTER.md`
- `/05_specialist_leads/COMPREHENSIVE_TESTING_LEAD_AGENT.md`

### Security Implementation Tasks

- [ ] Remove exposed token files
- [ ] Create secure token reference documentation
- [ ] Update all references to token files
- [ ] Add security warnings about token management
- [ ] Verify no other exposed credentials in documentation

## Phase 2: Core Environment Framework

### 2.1 Create Comprehensive .env Template

**File**: `/project_management/06_onboarding_system/04_environment_mastery/.env.template`

```bash
# HNP Environment Configuration Template
# Copy to .env and update with your specific values

# NetBox Configuration
NETBOX_URL=localhost:8000
NETBOX_TOKEN=your_netbox_api_token_here
NETBOX_ADMIN_USERNAME=admin
NETBOX_ADMIN_PASSWORD=admin

# GitHub Integration
GITHUB_TOKEN=your_github_personal_access_token_here
GIT_TEST_REPOSITORY=https://github.com/afewell-hh/gitops-test-1.git

# Kubernetes Configuration
TEST_FABRIC_K8S_API_SERVER=127.0.0.1:6443
TEST_FABRIC_K8S_TOKEN=your_k8s_service_account_token_here
TEST_FABRIC_K8S_API_SERVER_CA=your_k8s_ca_certificate_here
HOSS_CLUSTER_KUBECONFIG=/home/ubuntu/.kube/config
TEST_FABRIC_GITOPS_DIRECTORY=gitops/hedgehog/fabric-1/

# File System Paths
PROJECT_ROOT=/home/ubuntu/cc/hedgehog-netbox-plugin/
NETBOX_DOCKER_PATH=/home/ubuntu/gitignore/netbox-docker/

# ArgoCD Configuration (Optional)
ARGOCD_SERVER_URL=your_argocd_server_url_here
ARGOCD_ADMIN_USERNAME=admin
ARGOCD_ADMIN_PASSWORD=your_argocd_password_here
ARGOCD_KUBECONFIG_PATH=/hemk/poc_development/kubeconfig/kubeconfig.yaml
```

### 2.2 Update Environment Master Documentation

**Primary Target**: `/04_environment_mastery/ENVIRONMENT_MASTER.md`

**Updates Required**:
1. Replace all hardcoded URLs with `${NETBOX_URL}`
2. Replace authentication with `${NETBOX_ADMIN_USERNAME}/${NETBOX_ADMIN_PASSWORD}`
3. Replace file paths with `${PROJECT_ROOT}` and related variables
4. Add .env configuration section
5. Update all command examples to use environment variables

### 2.3 Create Environment Variable Usage Guide

**New File**: `/04_environment_mastery/ENVIRONMENT_VARIABLE_GUIDE.md`

Content includes:
- .env file setup instructions
- Variable substitution patterns
- Environment-specific configuration examples
- Troubleshooting common environment issues

### Phase 2 Implementation Tasks

- [ ] Create comprehensive .env template
- [ ] Update ENVIRONMENT_MASTER.md with variable substitution
- [ ] Create environment variable usage guide
- [ ] Update testing authority module with .env patterns
- [ ] Validate environment setup procedures

## Phase 3: Template and Training Updates

### 3.1 Agent Instruction Templates

**Primary Target**: `/99_templates/AGENT_INSTRUCTION_TEMPLATES.md`

**9 instances requiring updates**:
1. NetBox URL references (3 instances) → `${NETBOX_URL}`
2. Kubernetes endpoint references (3 instances) → `${TEST_FABRIC_K8S_API_SERVER}`
3. Git repository references (3 instances) → `${GIT_TEST_REPOSITORY}`

**Template Pattern Implementation**:
```markdown
## Environment Configuration

Your development environment uses the following configuration:

- **NetBox Instance**: `${NETBOX_URL}` (credentials: `${NETBOX_ADMIN_USERNAME}/${NETBOX_ADMIN_PASSWORD}`)
- **HCKC Cluster**: `${TEST_FABRIC_K8S_API_SERVER}` via `${HOSS_CLUSTER_KUBECONFIG}`
- **GitOps Repository**: `${GIT_TEST_REPOSITORY}`
- **Project Root**: `${PROJECT_ROOT}`

**Environment Setup**: Ensure your `.env` file is configured with appropriate values for your environment.
```

### 3.2 Foundation Training Materials

**Primary Target**: `/00_foundation/UNIVERSAL_FOUNDATION.md`

**Updates Required**:
- Replace project root path with `${PROJECT_ROOT}`
- Update environment verification commands with variables
- Add .env configuration as prerequisite

### 3.3 Specialist Lead Instructions

**Files Requiring Updates**:
1. `/05_specialist_leads/UX_LEAD_REPLACEMENT_AGENT.md` (4 instances)
2. `/05_specialist_leads/ENHANCED_QAPM_AGENT_V2.md` (3 instances)
3. `/05_specialist_leads/COMPREHENSIVE_TESTING_LEAD_AGENT.md` (3 instances)

**Standard Update Pattern**:
- Replace `localhost:8000` with `${NETBOX_URL}`
- Replace `/home/ubuntu/cc/hedgehog-netbox-plugin/` with `${PROJECT_ROOT}`
- Update testing commands with environment variables
- Add environment prerequisite sections

### Phase 3 Implementation Tasks

- [ ] Update agent instruction templates (9 instances)
- [ ] Update foundation training materials
- [ ] Update all specialist lead instruction files
- [ ] Create template validation procedures
- [ ] Test template effectiveness with sample agent instructions

## Phase 4: Tool and Management Updates

### 4.1 File Organization Audit Tools

**Primary Target**: `/06_qapm_track/FILE_ORGANIZATION_AUDIT_TOOLS.md`

**4 instances requiring updates**:
1. `REPO_ROOT="/home/ubuntu/cc/hedgehog-netbox-plugin"` → `REPO_ROOT="${PROJECT_ROOT}"`
2. `WORKSPACE_PATH="/home/ubuntu/cc/hedgehog-netbox-plugin/project_management/07_qapm_workspaces"` → `WORKSPACE_PATH="${PROJECT_ROOT}/project_management/07_qapm_workspaces"`

**Tool Update Pattern**:
```bash
#!/bin/bash
# Load environment configuration
source .env

# Use environment variables in tools
REPO_ROOT="${PROJECT_ROOT}"
WORKSPACE_PATH="${PROJECT_ROOT}/project_management/07_qapm_workspaces"
```

### 4.2 File Management Protocols

**Primary Target**: `/06_qapm_track/FILE_MANAGEMENT_PROTOCOLS.md`

**8 instances requiring updates**:
- Multiple `find` commands with hardcoded `/home/ubuntu/cc/hedgehog-netbox-plugin/` paths
- Workspace path definitions
- Archive directory creation commands

### 4.3 Training Deployment Guide

**Primary Target**: `/FILE_MANAGEMENT_TRAINING_DEPLOYMENT_GUIDE.md`

**6 instances requiring updates**:
- All file system operations need variable substitution
- Path validation commands
- Directory creation scripts

### Phase 4 Implementation Tasks

- [ ] Update file organization audit tools
- [ ] Update file management protocols (8 instances)
- [ ] Update training deployment guide (6 instances)
- [ ] Test all modified tools with environment variables
- [ ] Validate tool functionality across different environments

## Phase 5: Validation and Testing

### 5.1 Documentation Validation

**Validation Criteria**:
- [ ] All hardcoded references replaced with variables
- [ ] No broken references in updated documentation
- [ ] Command examples work with environment variables
- [ ] Templates generate valid agent instructions

**Validation Process**:
1. **Automated Scanning**: Search for remaining hardcoded patterns
2. **Template Testing**: Generate sample agent instructions from templates
3. **Command Validation**: Test all command examples with variables
4. **Cross-Reference Validation**: Verify all internal documentation links work

### 5.2 Environment Portability Testing

**Test Scenarios**:
1. **Fresh Environment Setup**: New developer following updated documentation
2. **Different Path Structure**: Non-standard installation paths
3. **Alternative Credentials**: Different authentication configurations
4. **Multiple Environment Support**: Development/staging/production configurations

### 5.3 Agent Training Effectiveness

**Training Validation**:
- Test agent comprehension with variable-based instructions
- Verify no confusion from variable substitution patterns
- Validate training effectiveness across different environment configurations
- Test troubleshooting procedures with environment variables

### Phase 5 Implementation Tasks

- [ ] Comprehensive documentation scanning for remaining hardcoded values
- [ ] Environment portability testing with multiple configurations
- [ ] Agent training effectiveness validation
- [ ] Documentation quality assurance review
- [ ] Final security review of all changes

## Implementation Guidelines

### Variable Substitution Standards

**Standard Patterns**:
```bash
# URLs
localhost:8000 → ${NETBOX_URL}

# Paths
/home/ubuntu/cc/hedgehog-netbox-plugin/ → ${PROJECT_ROOT}/

# Authentication
admin/admin → ${NETBOX_ADMIN_USERNAME}/${NETBOX_ADMIN_PASSWORD}

# Repository References
https://github.com/afewell-hh/gitops-test-1.git → ${GIT_TEST_REPOSITORY}

# Kubernetes Configuration
127.0.0.1:6443 → ${TEST_FABRIC_K8S_API_SERVER}
~/.kube/config → ${HOSS_CLUSTER_KUBECONFIG}
```

### Documentation Quality Standards

**Requirements for Updated Documentation**:
1. **Readability**: Variables clearly identified and explained
2. **Completeness**: All environment dependencies documented
3. **Consistency**: Uniform variable usage patterns
4. **Security**: No exposed credentials or tokens
5. **Portability**: Works across different environment configurations

### Change Management Process

**For Each File Update**:
1. **Pre-Update Analysis**: Document current hardcoded references
2. **Variable Mapping**: Create specific variable substitution plan
3. **Update Implementation**: Apply systematic variable substitution
4. **Validation Testing**: Test updated documentation functionality
5. **Quality Review**: Verify readability and completeness

## Risk Mitigation

### High-Priority Risks

**1. Documentation Breakage**
- **Risk**: Variable substitution breaks existing documentation links
- **Mitigation**: Comprehensive cross-reference validation

**2. Agent Training Disruption**
- **Risk**: Variable patterns confuse agent training
- **Mitigation**: Gradual rollout with training effectiveness testing

**3. Environment Compatibility**
- **Risk**: New variable patterns don't work in all environments
- **Mitigation**: Multi-environment testing before deployment

### Risk Monitoring

**Success Metrics**:
- [ ] Zero hardcoded references remain in documentation
- [ ] All documentation examples work with environment variables
- [ ] Agent training effectiveness maintained or improved
- [ ] Environment setup time reduced for new developers

## Completion Criteria

### Technical Completion
- [ ] All 52 hardcoded references replaced with appropriate .env variables
- [ ] Comprehensive .env template created and documented
- [ ] All tools and scripts updated to use environment variables
- [ ] Security-critical token exposures eliminated

### Quality Completion
- [ ] Documentation maintains readability and clarity
- [ ] All command examples tested and verified
- [ ] Agent instruction templates generate valid instructions
- [ ] Cross-environment portability verified

### Training Completion
- [ ] Agent training materials updated with .env patterns
- [ ] Environment setup procedures validated
- [ ] Troubleshooting guides updated for variable-based configuration
- [ ] Training effectiveness validated with test scenarios

## Resource Requirements

**Implementation Team**:
- **Lead Implementation Agent**: File updates and variable substitution
- **Quality Assurance Agent**: Documentation testing and validation
- **Training Validation Agent**: Agent instruction effectiveness testing

**Timeline Allocation**:
- **Week 1**: Phases 1-3 (Security + Core Framework + Templates)
- **Week 2**: Phases 4-5 (Tools + Validation)

**Tools Required**:
- Text processing tools for systematic variable substitution
- Environment testing framework for multi-configuration validation
- Documentation quality assurance tools

This comprehensive plan ensures systematic, secure, and effective transition from hardcoded environment references to a fully portable .env-based configuration system.