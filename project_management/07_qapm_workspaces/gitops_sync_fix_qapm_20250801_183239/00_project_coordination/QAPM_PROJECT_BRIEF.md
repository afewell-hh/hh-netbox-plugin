# QAPM Project Brief: GitOps Synchronization Fix

**QAPM**: Claude Code (Quality Assurance Project Manager)  
**Project ID**: gitops_sync_fix_qapm_20250801_183239  
**Priority**: P0 - MISSION CRITICAL  
**Date**: August 1, 2025  

## Critical Problem Statement

**EVIDENCE OF FAILURE**: Unprocessed YAML files remain in GitHub raw directory despite claims of completion by previous agents.

**GitHub Repository**: https://github.com/afewell-hh/gitops-test-1  
**Raw Directory**: gitops/hedgehog/fabric-1/raw/  
**Unprocessed Files**:
- .gitkeep
- prepop.yaml
- test-vpc-2.yaml  
- test-vpc.yaml

**This is a FALSE COMPLETION by previous agents - the core functionality is NOT working.**

## QAPM Systematic Problem Approach

### Phase 1: Problem Systematization + Workspace Setup ✅
**Status**: COMPLETE  
**Evidence**: Proper QAPM workspace created with organized structure

### Phase 2: Process Architecture Design
**Next Step**: Spawn Problem Scoping Specialist to map the real issue scope

### Phase 3: Agent Orchestration with Evidence Requirements
**Agents Required**:
1. Problem Scoping Specialist - Map actual vs claimed functionality
2. Technical Implementation Specialist - Fix the real GitOps sync code
3. Test Validation Specialist - Independent verification with live GitHub testing

### Phase 4: Quality Validation with Real Evidence
**Evidence Required**:
- Before: Screenshots showing unprocessed files in GitHub raw directory
- After: Screenshots showing files moved from raw/ to appropriate directories
- Test logs: Actual sync operation success
- GitHub API proof: Files processed and moved

## Anti-False-Completion Framework

**ZERO TOLERANCE FOR**:
- "Should work" without testing
- "Probably fixed" without evidence  
- "Tests pass" without user validation
- "Works locally" without GitHub testing
- Claims without screenshots

**MANDATORY EVIDENCE**:
- Live GitHub repository testing
- Before/after directory comparisons
- API logs showing file processing
- Screenshots of actual functionality
- Real user workflow validation

## Success Criteria (Evidence-Based)

1. **GitHub Raw Directory**: EMPTY of processable YAML files
2. **Managed Directory**: Contains processed CRD files
3. **HNP Database**: Shows imported CRD records
4. **Sync Logs**: Show successful processing operations
5. **User Workflow**: Sync button works and shows results

## File Management Protocol

**Workspace**: `/project_management/07_qapm_workspaces/gitops_sync_fix_qapm_20250801_183239/`

**Mandatory File Locations**:
- Investigation → `01_problem_analysis/`
- Implementation → `02_implementation/`  
- Testing → `03_validation/`
- Evidence → `04_evidence_collection/`

**Prohibited**: Creating files in repository root without workspace justification

## Next Actions

1. Complete workspace setup
2. Spawn Problem Scoping Specialist with comprehensive evidence requirements
3. Design systematic fix approach based on real problem analysis
4. Implement with TDD and live GitHub testing
5. Validate with independent specialist using real GitHub repository

This is a REAL problem requiring REAL solutions with REAL evidence.