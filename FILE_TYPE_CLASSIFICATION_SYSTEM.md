# Comprehensive File Type Classification System for HNP

**Document Classification Agent Report**  
**Date**: July 30, 2025  
**Version**: 1.0  

## Executive Summary

This comprehensive classification system addresses the critical file scattering problem identified in the HNP repository, where 222 files were recently cleaned from the root directory. The system provides clear categories, placement rules, and decision frameworks to prevent future file scattering while supporting effective agent workflows.

## File Type Taxonomy (Hierarchical Classification)

### 1. CODE FILES (Critical - Established Locations)
**Impact Level**: CRITICAL - Must be in correct locations  
**Organizational Principle**: Follow Django/NetBox plugin structure

#### 1.1 Production Code
- **Python Source Files** (`*.py`)
  - Location: `/netbox_hedgehog/` subdirectories by function
  - Examples: `models.py`, `views/*.py`, `forms/*.py`
  
#### 1.2 Templates
- **HTML Templates** (`*.html`)
  - Location: `/netbox_hedgehog/templates/netbox_hedgehog/`
  - Never in root or test directories

#### 1.3 Static Assets  
- **CSS/JS Files** (`*.css`, `*.js`)
  - Location: `/netbox_hedgehog/static/netbox_hedgehog/`
  - Never scattered in root

### 2. ARCHITECTURE DOCUMENTS (Critical - Centralized System)
**Impact Level**: CRITICAL - Architecture drift if misplaced  
**Organizational Principle**: Centralized in `/architecture_specifications/`

#### 2.1 System Architecture
- **Overview Documents** (`*_overview.md`, `*_architecture.md`)
  - Location: `/architecture_specifications/00_current_architecture/`
  
#### 2.2 Component Specifications
- **Technical Specs** (`*_specification.md`, `*_design.md`)
  - Location: `/architecture_specifications/00_current_architecture/component_architecture/`

#### 2.3 Architectural Decisions
- **ADRs** (`adr-*.md`)
  - Location: `/architecture_specifications/01_architectural_decisions/`
  - Status-based subdirectories: `active_decisions/`, `approved_decisions/`

### 3. PROJECT MANAGEMENT DOCUMENTS (Critical - Centralized System)
**Impact Level**: CRITICAL - Project chaos if scattered  
**Organizational Principle**: Centralized in `/project_management/`

#### 3.1 Current State Documents
- **Status Reports** (`*_STATUS.md`, `*_REPORT.md`)
  - Location: `/project_management/00_current_state/`
  
#### 3.2 Planning Documents
- **Sprint Plans** (`sprint_*.md`)
  - Location: `/project_management/01_planning/sprint_planning/`

#### 3.3 Agent Instructions
- **Agent Templates** (`*_AGENT.md`, `*_INSTRUCTIONS.md`)
  - Location: `/project_management/06_onboarding_system/` by track

### 4. TEST EVIDENCE FILES (Important - Needs Organization)
**Impact Level**: IMPORTANT - Quality tracking compromised if lost  
**Organizational Principle**: Time-based organization in designated directories

#### 4.1 Validation Results
- **JSON Evidence** (`*_evidence_*.json`, `*_validation_*.json`)
  - Location: `/project_management/02_execution/quality_assurance/test_results/YYYY-MM/`
  - Pattern: Include timestamp in filename

#### 4.2 HTML Captures
- **GUI Test Evidence** (`*_test.html`, `*_validation.html`)
  - Location: `/tmp/gui_validation_evidence/` during active testing
  - Archive to: `/project_management/02_execution/quality_assurance/test_results/YYYY-MM/`

#### 4.3 Test Reports
- **Validation Reports** (`*_VALIDATION_REPORT.md`)
  - Location: `/project_management/02_execution/quality_assurance/`

### 5. WORKING FILES (Workflow - Temporary Storage)
**Impact Level**: WORKFLOW - Needed during work only  
**Organizational Principle**: Designated working directories

#### 5.1 Investigation Scripts
- **Debug Scripts** (`debug_*.py`, `investigate_*.py`)
  - Location: `/tmp/investigations/` during active work
  - Delete after issue resolution

#### 5.2 Test Scripts  
- **Validation Scripts** (`test_*.py`, `validate_*.py`)
  - Location: `/tests/` if permanent test suite
  - Location: `/tmp/test_scripts/` if temporary

#### 5.3 Authentication Artifacts
- **Session Files** (`csrf_token.txt`, `cookies.txt`)
  - Location: `/tmp/` only
  - Never commit to repository

### 6. TEMPORARY FILES (Disposable - Auto-cleanup)
**Impact Level**: DISPOSABLE - Can be deleted anytime  
**Organizational Principle**: Never in repository

#### 6.1 Cache Files
- **Temporary Data** (`*.tmp`, `*.cache`, `scratch.txt`)
  - Location: `/tmp/` only
  - Auto-cleanup after 24 hours

#### 6.2 Build Artifacts
- **Docker/Build Files** (`Dockerfile.working`, `*.log`)
  - Location: Build directories only
  - Never commit working versions

## Placement Decision Matrix

### Decision Tree for File Placement

```
START: What type of file are you creating?
│
├─> Is it production code?
│   └─> YES: Place in `/netbox_hedgehog/` following Django structure
│
├─> Is it architecture documentation?
│   └─> YES: Place in `/architecture_specifications/` by category
│
├─> Is it project management related?
│   └─> YES: Place in `/project_management/` by lifecycle stage
│
├─> Is it test evidence?
│   ├─> Active testing? → `/tmp/gui_validation_evidence/`
│   └─> Archival? → `/project_management/02_execution/quality_assurance/`
│
├─> Is it a working/debug file?
│   ├─> Permanent test? → `/tests/`
│   └─> Temporary? → `/tmp/investigations/`
│
└─> Is it temporary?
    └─> YES: Place in `/tmp/` - NEVER in repository
```

### Quick Reference Rules

| File Type | Primary Location | Alternative | Never Place In |
|-----------|-----------------|-------------|----------------|
| Python source | `/netbox_hedgehog/` | - | Root, `/tmp/` |
| HTML templates | `/netbox_hedgehog/templates/` | - | Root, test dirs |
| Architecture docs | `/architecture_specifications/` | - | Root, project dirs |
| Project docs | `/project_management/` | - | Root, code dirs |
| Test evidence | `/tmp/gui_validation_evidence/` | Archive after sprint | Root directory |
| Debug scripts | `/tmp/investigations/` | `/tests/` if permanent | Root directory |
| Session files | `/tmp/` | - | Anywhere in repo |

## Risk Impact Assessment

### Critical Risk Files (Misplacement = System Failure)
1. **Architecture Documents**
   - Risk: Architecture drift, conflicting designs
   - Impact: Entire system coherence compromised
   - Prevention: Strict `/architecture_specifications/` enforcement

2. **Project Planning Documents**
   - Risk: Duplicate/conflicting plans
   - Impact: Project chaos, wasted effort
   - Prevention: Centralized `/project_management/` only

3. **Production Code**
   - Risk: Code not deployed, functionality missing
   - Impact: System doesn't work
   - Prevention: Django structure compliance

### Important Risk Files (Misplacement = Quality Issues)
1. **Test Evidence**
   - Risk: Can't prove functionality works
   - Impact: False completion claims accepted
   - Prevention: Organized evidence directories

2. **Agent Instructions**
   - Risk: Agents receive conflicting instructions
   - Impact: Inconsistent work quality
   - Prevention: Onboarding system structure

### Low Risk Files (Misplacement = Clutter Only)
1. **Temporary Files**
   - Risk: Repository clutter
   - Impact: Confusing navigation
   - Prevention: `/tmp/` usage, .gitignore

2. **Debug Scripts**
   - Risk: Confusion about purpose
   - Impact: Wasted investigation time
   - Prevention: Clear `/tmp/investigations/`

## Agent Workflow Mapping

### QAPM Agents
**Typical File Creation**:
- Sprint status documents → `/project_management/00_current_state/`
- Agent coordination plans → `/project_management/03_coordination/`
- Evidence validation reports → `/project_management/02_execution/quality_assurance/`

**Common Mistakes**: Creating project docs in root

### Problem Scoping Specialists
**Typical File Creation**:
- Investigation scripts → `/tmp/investigations/`
- Problem analysis reports → `/project_management/00_current_state/`
- Debug evidence → `/tmp/gui_validation_evidence/`

**Common Mistakes**: Leaving debug scripts in root

### Architecture Review Specialists  
**Typical File Creation**:
- Architecture assessments → `/architecture_specifications/00_current_architecture/`
- Design documents → `/architecture_specifications/02_design_specifications/`
- ADRs → `/architecture_specifications/01_architectural_decisions/`

**Common Mistakes**: Creating architecture docs outside centralized system

### Test Validation Specialists
**Typical File Creation**:
- Test scripts → `/tests/` or `/tmp/test_scripts/`
- Validation evidence → `/tmp/gui_validation_evidence/`
- Test reports → `/project_management/02_execution/quality_assurance/`

**Common Mistakes**: Scattering test files throughout repository

### Implementation Specialists
**Typical File Creation**:
- Python code → `/netbox_hedgehog/` proper subdirectories
- Templates → `/netbox_hedgehog/templates/netbox_hedgehog/`
- Migration files → `/netbox_hedgehog/migrations/`

**Common Mistakes**: Creating test implementations in root

## Organizational Principle Guidelines

### Core Principles for Agents

1. **Centralization First**
   - Architecture → `/architecture_specifications/`
   - Project Management → `/project_management/`
   - Never create competing systems

2. **Temporary is Temporary**
   - Working files → `/tmp/`
   - Never commit temporary files
   - Clean up after completion

3. **Evidence Has a Home**
   - Active testing → `/tmp/gui_validation_evidence/`
   - Archival → Organized by date in QA directories
   - Always include timestamps

4. **Follow Established Patterns**
   - Django structure for code
   - NetBox conventions for plugins
   - Project structure for management

5. **When in Doubt**
   - Check existing similar files
   - Use designated working directories
   - Ask for placement guidance

### File Naming Conventions

1. **Include Context**
   - Bad: `test.py`
   - Good: `test_fabric_edit_authentication.py`

2. **Add Timestamps to Evidence**
   - Bad: `validation_results.json`
   - Good: `validation_results_20250730_143022.json`

3. **Use Clear Prefixes**
   - Investigation: `investigate_*`
   - Debug: `debug_*`
   - Test: `test_*`
   - Validation: `validate_*`

## Prevention Strategies

### For Agents
1. **Start with Placement Decision**
   - Before creating file, decide location
   - Check decision matrix
   - Verify similar files location

2. **Use Working Directories**
   - `/tmp/` for all temporary work
   - Never "just quickly" put in root
   - Clean up immediately after

3. **Follow the Patterns**
   - Architecture docs together
   - Project docs together
   - Code in proper structure

### For QAPM Training
1. **Emphasize Organization Early**
   - Include file placement in onboarding
   - Show consequences of scattering
   - Provide clear examples

2. **Enforce Through Review**
   - Check file placement in validations
   - Reject scattered implementations
   - Require proper organization

3. **Provide Tools**
   - Quick reference cards
   - Decision matrices
   - Clear directory purposes

## Metrics for Success

### Organizational Health Metrics
- **Root Directory Files**: ≤ 15 files (only essential)
- **Untracked Files**: < 10 at any time
- **Evidence Organization**: 100% in designated directories
- **Architecture Centralization**: 100% in specifications

### Agent Performance Metrics  
- **Correct Placement Rate**: > 95%
- **Cleanup Completion**: 100% after task
- **Documentation Location**: 100% centralized

## Implementation Checklist

### For New File Creation
- [ ] Identified file type category
- [ ] Checked decision matrix
- [ ] Verified similar file locations
- [ ] Created in correct directory
- [ ] Added to .gitignore if temporary
- [ ] Included timestamp if evidence
- [ ] Cleaned up working files

### For File Organization Review
- [ ] Root directory contains only essentials
- [ ] Architecture docs centralized
- [ ] Project docs centralized  
- [ ] Test evidence organized by date
- [ ] Working files in `/tmp/`
- [ ] No scattered duplicates

## Conclusion

This classification system provides comprehensive guidance for preventing file scattering in the HNP repository. By following these categories, placement rules, and organizational principles, agents can maintain a clean, navigable repository structure while effectively completing their work.

The key to success is establishing file placement habits early and enforcing them consistently through the QAPM framework and agent training systems.