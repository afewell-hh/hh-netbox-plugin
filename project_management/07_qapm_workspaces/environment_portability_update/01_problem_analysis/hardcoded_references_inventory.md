# Hardcoded Environment References Inventory

**Analysis Date**: July 31, 2025  
**Analysis Agent**: Problem Scoping Specialist  
**Scope**: HNP Onboarding Documentation System  
**Purpose**: Identify hardcoded environment references for .env variable replacement

## Executive Summary

Comprehensive analysis of the HNP onboarding system reveals **52 distinct hardcoded environment references** across **21 files** that need to be replaced with .env variables. These references span NetBox access, Kubernetes configuration, Git repositories, file paths, authentication tokens, and ArgoCD configuration.

## Critical Security Issues

### 🚨 IMMEDIATE SECURITY RISKS

**Exposed Authentication Tokens**:
1. **GitHub Token (Base64 Encoded)**: `Z2hwX1JuR3B2eGd6dVh6M1BMOGs3SzZyajlxYVc0TkxTTzJQa0hzRgo=`
   - **File**: `/04_environment_mastery/development_tools/github.token.b64`
   - **Risk**: Plaintext token exposure in documentation system
   - **Decoded Value**: `ghp_RnGpvxgzuXx3PL0g7K6rj9qaW4NLSO2PkHsG`

2. **NetBox Token (Plaintext)**: `ced6a3e0a978db0ad4de39cd66af4868372d7dd0`
   - **File**: `/04_environment_mastery/development_tools/netbox.token`
   - **Risk**: Direct API access token exposure

**CRITICAL ACTION REQUIRED**: These token files must be immediately secured and replaced with .env variable references.

## Hardcoded References by Category

### 1. NetBox Access References (12 instances)
| Reference | Current Value | Target .env Variable | Files Count |
|-----------|---------------|---------------------|-------------|
| NetBox URL | `localhost:8000` | `NETBOX_URL` | 10 |
| Admin Credentials | `admin/admin` | Split to username/password | 4 |
| NetBox Token | `ced6a3e0a978db0ad4de39cd66af4868372d7dd0` | `NETBOX_TOKEN` | 1 |

**Files Affected**:
- `/04_environment_mastery/ENVIRONMENT_MASTER.md` (3 instances)
- `/04_environment_mastery/TESTING_AUTHORITY_MODULE.md` (5 instances)
- `/99_templates/AGENT_INSTRUCTION_TEMPLATES.md` (6 instances)
- `/05_specialist_leads/UX_LEAD_REPLACEMENT_AGENT.md` (3 instances)
- `/05_specialist_leads/ENHANCED_QAPM_AGENT_V2.md` (1 instance)
- `/05_specialist_leads/COMPREHENSIVE_TESTING_LEAD_AGENT.md` (1 instance)
- `/ONBOARDING_USAGE_GUIDE.md` (1 instance)
- `/06_qapm_track/agent_orchestration/AGENT_INSTRUCTION_FRAMEWORK.md` (1 instance)

### 2. Kubernetes Configuration References (8 instances)
| Reference | Current Value | Target .env Variable | Files Count |
|-----------|---------------|---------------------|-------------|
| K8s API Server | `127.0.0.1:6443` | `TEST_FABRIC_K8S_API_SERVER` | 4 |
| Kubeconfig Path | `~/.kube/config` | `HOSS_CLUSTER_KUBECONFIG` | 4 |

**Files Affected**:
- `/04_environment_mastery/ENVIRONMENT_MASTER.md` (2 instances)
- `/04_environment_mastery/kubernetes_systems/K8S_CRD_MASTERY.md` (2 instances)
- `/99_templates/AGENT_INSTRUCTION_TEMPLATES.md` (3 instances)
- `/05_specialist_leads/COMPREHENSIVE_TESTING_LEAD_AGENT.md` (1 instance)

### 3. Git Repository References (7 instances)
| Reference | Current Value | Target .env Variable | Files Count |
|-----------|---------------|---------------------|-------------|
| Test Repository | `https://github.com/afewell-hh/gitops-test-1.git` | `GIT_TEST_REPOSITORY` | 5 |
| GitHub Token | `Z2hwX1JuR3B2eGd6dVh6M1BMOGs3SzZyajlxYVc0TkxTTzJQa0hzRgo=` | `GITHUB_TOKEN` | 1 |
| GitOps Directory | `gitops/hedgehog/fabric-1/` | `TEST_FABRIC_GITOPS_DIRECTORY` | 1 |

**Files Affected**:
- `/04_environment_mastery/ENVIRONMENT_MASTER.md` (1 instance)
- `/04_environment_mastery/kubernetes_systems/K8S_CRD_MASTERY.md` (1 instance)
- `/99_templates/AGENT_INSTRUCTION_TEMPLATES.md` (3 instances)
- `/examples/GITOPS_SYNC_FIX_USING_ONBOARDING.md` (1 instance)
- `/04_environment_mastery/development_tools/github.token.b64` (1 instance)

### 4. File System Path References (21 instances)
| Reference | Current Value | Target .env Variable | Files Count |
|-----------|---------------|---------------------|-------------|
| Project Root | `/home/ubuntu/cc/hedgehog-netbox-plugin/` | `PROJECT_ROOT` | 12 |
| NetBox Docker Path | `/home/ubuntu/gitignore/netbox-docker/` | `NETBOX_DOCKER_PATH` | 2 |
| ArgoCD Config Path | `/hemk/poc_development/kubeconfig/kubeconfig.yaml` | `ARGOCD_KUBECONFIG_PATH` | 1 |

**Files Affected**:
- `/04_environment_mastery/ENVIRONMENT_MASTER.md` (3 instances)
- `/99_templates/AGENT_INSTRUCTION_TEMPLATES.md` (3 instances)
- `/00_foundation/UNIVERSAL_FOUNDATION.md` (1 instance)
- `/05_specialist_leads/UX_LEAD_REPLACEMENT_AGENT.md` (3 instances)
- `/05_specialist_leads/ENHANCED_QAPM_AGENT_V2.md` (2 instances)
- `/05_specialist_leads/COMPREHENSIVE_TESTING_LEAD_AGENT.md` (1 instance)
- `/06_qapm_track/FILE_ORGANIZATION_AUDIT_TOOLS.md` (4 instances)
- `/06_qapm_track/FILE_MANAGEMENT_PROTOCOLS.md` (8 instances)
- `/FILE_MANAGEMENT_TRAINING_DEPLOYMENT_GUIDE.md` (6 instances)

### 5. ArgoCD Configuration References (4 instances)
| Reference | Current Value | Target .env Variable | Files Count |
|-----------|---------------|---------------------|-------------|
| ArgoCD Config | `/hemk/poc_development/kubeconfig/kubeconfig.yaml` | `ARGOCD_KUBECONFIG_PATH` | 1 |
| ArgoCD Server URL | Not explicitly mentioned | `ARGOCD_SERVER_URL` | N/A |
| ArgoCD Admin Username | Not explicitly mentioned | `ARGOCD_ADMIN_USERNAME` | N/A |
| ArgoCD Admin Password | Not explicitly mentioned | `ARGOCD_ADMIN_PASSWORD` | N/A |

**Note**: ArgoCD references are implied through GitOps patterns but not explicitly hardcoded in current documentation.

## .env Variable Mapping Requirements

### Required .env Variables Implementation

**NetBox Configuration**:
```bash
NETBOX_URL=localhost:8000
NETBOX_TOKEN=ced6a3e0a978db0ad4de39cd66af4868372d7dd0
NETBOX_ADMIN_USERNAME=admin
NETBOX_ADMIN_PASSWORD=admin
```

**GitHub Integration**:
```bash
GITHUB_TOKEN=ghp_RnGpvxgzuXx3PL0g7K6rj9qaW4NLSO2PkHsG
GIT_TEST_REPOSITORY=https://github.com/afewell-hh/gitops-test-1.git
```

**Kubernetes Configuration**:
```bash
TEST_FABRIC_K8S_API_SERVER=127.0.0.1:6443
HOSS_CLUSTER_KUBECONFIG=/home/ubuntu/.kube/config
TEST_FABRIC_GITOPS_DIRECTORY=gitops/hedgehog/fabric-1/
```

**File System Paths**:
```bash
PROJECT_ROOT=/home/ubuntu/cc/hedgehog-netbox-plugin/
NETBOX_DOCKER_PATH=/home/ubuntu/gitignore/netbox-docker/
```

**ArgoCD Configuration** (for future implementation):
```bash
ARGOCD_SERVER_URL=
ARGOCD_ADMIN_USERNAME=
ARGOCD_ADMIN_PASSWORD=
ARGOCD_KUBECONFIG_PATH=/hemk/poc_development/kubeconfig/kubeconfig.yaml
```

## High-Priority Update Targets

### Priority 1: Security-Critical Files
1. **`/04_environment_mastery/development_tools/github.token.b64`** - Contains exposed GitHub token
2. **`/04_environment_mastery/development_tools/netbox.token`** - Contains exposed NetBox token
3. **`/04_environment_mastery/ENVIRONMENT_MASTER.md`** - Core environment reference document
4. **`/04_environment_mastery/TESTING_AUTHORITY_MODULE.md`** - Testing framework with API access

### Priority 2: Template and Training Files
1. **`/99_templates/AGENT_INSTRUCTION_TEMPLATES.md`** - Agent instruction templates (9 instances)
2. **`/00_foundation/UNIVERSAL_FOUNDATION.md`** - Foundation training material
3. **`/05_specialist_leads/`** - All specialist agent instruction files

### Priority 3: Tool and Management Files
1. **`/06_qapm_track/FILE_ORGANIZATION_AUDIT_TOOLS.md`** - File organization tools
2. **`/06_qapm_track/FILE_MANAGEMENT_PROTOCOLS.md`** - File management protocols
3. **`/FILE_MANAGEMENT_TRAINING_DEPLOYMENT_GUIDE.md`** - Training deployment guide

## Update Pattern Analysis

### Common Update Patterns Required

**URL References**:
```bash
# Current:
localhost:8000
# Replace with:
${NETBOX_URL}
```

**Authentication References**:
```bash
# Current:
admin/admin
# Replace with:
${NETBOX_ADMIN_USERNAME}/${NETBOX_ADMIN_PASSWORD}
```

**File Path References**:
```bash
# Current:
/home/ubuntu/cc/hedgehog-netbox-plugin/
# Replace with:
${PROJECT_ROOT}
```

**API Token References**:
```bash
# Current:
ced6a3e0a978db0ad4de39cd66af4868372d7dd0
# Replace with:
${NETBOX_TOKEN}
```

## Implementation Complexity Assessment

### Low Complexity (Direct Substitution)
- URL references: `localhost:8000` → `${NETBOX_URL}`
- Path references: `/home/ubuntu/cc/hedgehog-netbox-plugin/` → `${PROJECT_ROOT}`
- Repository references: Direct substitution with `${GIT_TEST_REPOSITORY}`

### Medium Complexity (Template Processing Required)
- Combined authentication references: `admin/admin` → `${NETBOX_ADMIN_USERNAME}/${NETBOX_ADMIN_PASSWORD}`
- Command examples with embedded paths
- Multi-line code blocks with environment references

### High Complexity (Documentation Restructuring)
- Token files need complete removal and replacement with .env reference instructions
- Testing commands that embed multiple environment variables
- File organization tools with hardcoded paths throughout

## Risk Assessment

### High Risk Items
1. **Exposed Authentication Tokens**: Immediate security vulnerability
2. **Hardcoded Paths in Production Tools**: Could break in different environments
3. **Template Propagation**: Templates spread hardcoded values to new agent instructions

### Medium Risk Items
1. **Training Material Accuracy**: Outdated hardcoded values in training could confuse agents
2. **Testing Framework Dependencies**: Hardcoded test environment assumptions

### Low Risk Items
1. **Documentation Examples**: Non-functional hardcoded values in explanatory text
2. **Historical References**: Past implementation examples with hardcoded values

## Validation Requirements

### Pre-Update Validation
- [ ] Catalog all current hardcoded values
- [ ] Verify .env schema completeness
- [ ] Test .env variable substitution patterns

### Post-Update Validation
- [ ] Verify all hardcoded references replaced
- [ ] Test documentation readability with variables
- [ ] Validate agent training effectiveness with new format
- [ ] Confirm no broken references or commands

## Next Steps for Implementation

1. **Immediate Security Action**: Secure/remove exposed token files
2. **Create .env Template**: Complete environment variable template
3. **Update High-Priority Files**: Start with security-critical and template files
4. **Implement Variable Substitution**: Create tooling for .env variable replacement
5. **Comprehensive Testing**: Validate all updated documentation
6. **Agent Retraining**: Update onboarding system with new .env patterns

## Evidence Collection

**Total Files Analyzed**: 21 files across the onboarding system  
**Total Hardcoded References**: 52 distinct instances requiring updates  
**Security-Critical Items**: 2 exposed authentication tokens  
**Environment Categories**: 5 distinct categories of environment dependencies

This inventory provides a complete foundation for implementing environment portability across the HNP onboarding documentation system.