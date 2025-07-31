# Hardcoded Environment Values Analysis

**Analysis Date**: July 31, 2025  
**Analysis Scope**: HNP Onboarding System Documentation  
**Purpose**: Identify all hardcoded environment values for .env variable replacement

## Executive Summary

Analysis identified 10+ files containing hardcoded environment values that need to be replaced with .env variables to ensure portability across different development environments.

## Hardcoded Values Identified

### 1. NetBox Environment Values
- **Value**: `localhost:8000`
- **Usage**: NetBox Docker container access URL
- **Proposed Variable**: `${NETBOX_URL}`
- **Files Affected**: 10 files (see below)

### 2. Authentication Credentials  
- **Value**: `admin/admin`
- **Usage**: NetBox default credentials
- **Proposed Variables**: `${NETBOX_USERNAME}/${NETBOX_PASSWORD}`
- **Files Affected**: Multiple template files

### 3. NetBox API Token
- **Value**: `ced6a3e0a978db0ad4de39cd66af4868372d7dd0`
- **Usage**: NetBox API authentication
- **Proposed Variable**: `${NETBOX_TOKEN}`
- **Files Affected**: Token file + references

### 4. Kubernetes Cluster Configuration
- **Value**: `127.0.0.1:6443`
- **Usage**: HCKC cluster access
- **Proposed Variable**: `${K8S_API_SERVER}`
- **Files Affected**: Multiple configuration references

### 5. GitOps Repository
- **Value**: `https://github.com/afewell-hh/gitops-test-1.git`
- **Usage**: GitOps repository reference
- **Proposed Variable**: `${GITOPS_REPOSITORY_URL}`
- **Files Affected**: 4 files

### 6. Project Root Path
- **Value**: `/home/ubuntu/cc/hedgehog-netbox-plugin/`
- **Usage**: Project root directory
- **Proposed Variable**: `${PROJECT_ROOT}`
- **Files Affected**: Multiple template files

## Files Requiring Updates

### Agent Instruction Templates
1. `/project_management/06_onboarding_system/99_templates/AGENT_INSTRUCTION_TEMPLATES.md`
   - Contains all hardcoded values in orchestrator, manager, and specialist templates
   - High priority - affects all agent spawning

### Foundation Documentation
2. `/project_management/06_onboarding_system/00_foundation/UNIVERSAL_FOUNDATION.md`
   - Base environment context for all agents

### Environment Mastery Module
3. `/project_management/06_onboarding_system/04_environment_mastery/ENVIRONMENT_MASTER.md`
4. `/project_management/06_onboarding_system/04_environment_mastery/kubernetes_systems/K8S_CRD_MASTERY.md`
5. `/project_management/06_onboarding_system/04_environment_mastery/TESTING_AUTHORITY_MODULE.md`

### Agent Orchestration Framework
6. `/project_management/06_onboarding_system/06_qapm_track/agent_orchestration/AGENT_INSTRUCTION_FRAMEWORK.md`

### Specialist Lead Instructions
7. `/project_management/06_onboarding_system/05_specialist_leads/COMPREHENSIVE_TESTING_LEAD_AGENT.md`
8. `/project_management/06_onboarding_system/05_specialist_leads/ENHANCED_QAPM_AGENT_V2.md`
9. `/project_management/06_onboarding_system/05_specialist_leads/UX_LEAD_REPLACEMENT_AGENT.md`

### Usage Documentation
10. `/project_management/06_onboarding_system/ONBOARDING_USAGE_GUIDE.md`

### Examples
11. `/project_management/06_onboarding_system/examples/GITOPS_SYNC_FIX_USING_ONBOARDING.md`

### Token File
12. `/project_management/06_onboarding_system/04_environment_mastery/development_tools/netbox.token`

## Implementation Priority

### Phase 1: Critical Templates
- `99_templates/AGENT_INSTRUCTION_TEMPLATES.md`
- `00_foundation/UNIVERSAL_FOUNDATION.md`

### Phase 2: Environment Mastery
- All files in `04_environment_mastery/`
- Token file replacement

### Phase 3: Specialist Instructions
- All files in `05_specialist_leads/`
- `06_qapm_track/agent_orchestration/AGENT_INSTRUCTION_FRAMEWORK.md`

### Phase 4: Documentation
- Usage guides and examples

## .env Schema Requirements

Based on analysis, the .env.example file should include:

```bash
# NetBox Configuration
NETBOX_URL=localhost:8000
NETBOX_USERNAME=admin
NETBOX_PASSWORD=admin
NETBOX_TOKEN=your_netbox_api_token_here

# Kubernetes Configuration  
K8S_API_SERVER=127.0.0.1:6443
K8S_CONFIG_PATH=~/.kube/config

# GitOps Configuration
GITOPS_REPOSITORY_URL=https://github.com/your-org/your-gitops-repo.git

# Project Configuration
PROJECT_ROOT=/path/to/hedgehog-netbox-plugin

# GitHub Configuration (if needed)
GITHUB_TOKEN=your_github_token_here
```

## Success Criteria

- All hardcoded environment values replaced with .env variable references
- .env.example file created with complete schema
- Documentation maintains clarity and usability
- Consistent variable naming conventions
- No hardcoded values remain in updated files

## Risk Assessment

- **Low Risk**: Documentation updates have no runtime impact
- **Medium Risk**: Must ensure all variable references are consistent
- **Mitigation**: Thorough validation of all updated references