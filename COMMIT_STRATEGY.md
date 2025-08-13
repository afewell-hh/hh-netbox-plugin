# Git Commit Strategy for Devcontainer Deployment

## Overview
This document outlines the strategic approach for cleaning up the repository and preparing logical commits that preserve essential plugin improvements while removing test artifacts.

## Current State Analysis
- **Branch**: flowtest
- **Modified Files**: 26 essential plugin files
- **Untracked Files**: 400+ test/validation artifacts
- **Test Artifacts**: 424 Python files, 227 JSON files, 191 MD files

## Essential vs Test Artifacts Classification

### ✅ ESSENTIAL FILES (Must Preserve)
These files contain core plugin functionality improvements:

#### Core Plugin Files
- `netbox_hedgehog/__init__.py` - Plugin configuration updates
- `netbox_hedgehog/celery.py` - Async task improvements
- `setup.py` - Package configuration updates
- `Makefile` - Build system improvements

#### Models & Database
- `netbox_hedgehog/models/fabric.py` - Fabric model enhancements
- `netbox_hedgehog/models/gitops.py` - GitOps integration improvements
- `netbox_hedgehog/models/__init__.py` - Model exports
- `netbox_hedgehog/migrations/0021_bidirectional_sync_extensions.py` - Database schema

#### Views & Controllers
- `netbox_hedgehog/views/fabric_views.py` - Fabric management views
- `netbox_hedgehog/views/sync_views.py` - Sync functionality views

#### Templates & UI
- `netbox_hedgehog/templates/netbox_hedgehog/base.html` - Base template improvements
- `netbox_hedgehog/templates/netbox_hedgehog/fabric_detail.html` - Fabric detail UI
- `netbox_hedgehog/templates/netbox_hedgehog/fabric_detail_simple.html` - Simplified UI

#### Static Assets
- `netbox_hedgehog/static/netbox_hedgehog/js/gitops-dashboard.js` - Dashboard functionality

#### Utils & Services
- `netbox_hedgehog/utils/kubernetes.py` - K8s integration utilities
- `netbox_hedgehog/mixins/__init__.py` - Shared mixins
- `netbox_hedgehog/management/commands/diagnostic_fgd_ingestion.py` - Management commands

#### Configuration & Documentation
- `CLAUDE.md` - Updated project documentation
- `.claude/settings.json` - Claude configuration updates

### ❌ TEST ARTIFACTS (To Remove)
Files that should be excluded and added to .gitignore:

#### Test Scripts (424 files)
- All files matching `*test*.py`, `*validation*.py`, `*evidence*.py`
- Standalone test scripts like `comprehensive_*.py`, `manual_*.py`
- Diagnostic scripts like `diagnose_*.py`, `validate_*.py`

#### Test Results (227 JSON files)
- All files matching `*evidence*.json`, `*validation*.json`, `*results*.json`
- Report data like `*_report_*.json`, `*_analysis_*.json`

#### Documentation Artifacts (191 MD files)
- All files matching `*REPORT*.md`, `*ANALYSIS*.md`, `*SUMMARY*.md`
- Evidence documentation like `*EVIDENCE*.md`, `*COMPLETE*.md`

#### HTML Test Files
- Browser test outputs like `*test*.html`, `*validation*.html`
- Page captures like `*baseline*.html`, `*verification*.html`

#### Configuration Artifacts
- Backup files like `*.backup`, `CLAUDE.md.backup.*`
- Test configurations like `claude-flow.config.json.back*`

#### Directories
- `test-results/`, `tests/`, `analysis/`, `backups/`
- `containerized_validation_*/`, `simple_validation_*/`
- `hemk/poc_development/`, various evidence directories

## Logical Commit Grouping Strategy

### Commit 1: Database & Models
**Message**: "Enhance database models and migrations for improved fabric management"
**Files**:
- `netbox_hedgehog/models/fabric.py`
- `netbox_hedgehog/models/gitops.py`
- `netbox_hedgehog/models/__init__.py`
- `netbox_hedgehog/migrations/0021_bidirectional_sync_extensions.py`

### Commit 2: Views & Controllers
**Message**: "Improve fabric and sync view functionality"
**Files**:
- `netbox_hedgehog/views/fabric_views.py`
- `netbox_hedgehog/views/sync_views.py`

### Commit 3: Templates & UI
**Message**: "Enhance fabric management UI templates and layouts"
**Files**:
- `netbox_hedgehog/templates/netbox_hedgehog/base.html`
- `netbox_hedgehog/templates/netbox_hedgehog/fabric_detail.html`
- `netbox_hedgehog/templates/netbox_hedgehog/fabric_detail_simple.html`

### Commit 4: JavaScript & Frontend
**Message**: "Update GitOps dashboard JavaScript functionality"
**Files**:
- `netbox_hedgehog/static/netbox_hedgehog/js/gitops-dashboard.js`

### Commit 5: Services & Utilities
**Message**: "Improve Kubernetes integration and plugin services"
**Files**:
- `netbox_hedgehog/utils/kubernetes.py`
- `netbox_hedgehog/mixins/__init__.py`
- `netbox_hedgehog/celery.py`
- `netbox_hedgehog/management/commands/diagnostic_fgd_ingestion.py`

### Commit 6: Plugin Configuration
**Message**: "Update plugin configuration and package setup"
**Files**:
- `netbox_hedgehog/__init__.py`
- `setup.py`
- `Makefile`

### Commit 7: Documentation & Configuration
**Message**: "Update project documentation and development configuration"
**Files**:
- `CLAUDE.md`
- `.claude/settings.json`

### Commit 8: Repository Cleanup
**Message**: "Add comprehensive .gitignore patterns for test artifacts"
**Files**:
- `.gitignore`

## Pre-Cleanup Checklist

### ✅ Safety Measures
1. **Backup Branch Created**: `backup-before-cleanup-YYYYMMDD-HHMMSS`
2. **Backup Commit**: All current state committed to backup branch
3. **Script Safety**: Cleanup script has exclusion patterns for essential files
4. **Manual Review**: All patterns verified before execution

### ✅ Essential File Preservation
1. **Core Plugin**: All essential NetBox plugin files identified
2. **Database**: Migration files and model changes preserved
3. **UI/UX**: Template and static asset improvements kept
4. **Documentation**: Updated project docs maintained

### ✅ Test Artifact Identification
1. **Pattern Matching**: Comprehensive patterns for test file removal
2. **Directory Cleanup**: Test directories identified for removal
3. **Exclusions**: Essential test files (like `conftest.py`) excluded
4. **Validation**: Patterns tested to avoid false positives

## Execution Steps

### Step 1: Create Backup
```bash
git branch backup-before-cleanup-$(date +%Y%m%d-%H%M%S)
git add -A
git commit -m "BACKUP: Complete state before cleanup"
```

### Step 2: Run Cleanup Script
```bash
./git-cleanup.sh
```

### Step 3: Review Changes
```bash
git diff --cached --name-only
git diff --cached --stat
```

### Step 4: Execute Commit Strategy
Create commits in logical order as outlined above.

### Step 5: Final Verification
```bash
git log --oneline -10
git status
```

## Recovery Plan

If anything goes wrong during cleanup:

### Immediate Recovery
```bash
git reset --hard HEAD
git checkout backup-before-cleanup-YYYYMMDD-HHMMSS
```

### Selective Recovery
```bash
git checkout backup-branch -- path/to/specific/file
```

### Complete Restoration
```bash
git branch -f flowtest backup-before-cleanup-YYYYMMDD-HHMMSS
git checkout flowtest
```

## Post-Cleanup Validation

### Essential Files Check
- Verify all 26 essential files are still present
- Check that plugin functionality is intact
- Ensure templates render correctly
- Validate JavaScript functionality

### Test Artifact Removal
- Confirm 400+ test files removed
- Verify .gitignore patterns working
- Check no test artifacts in git status
- Validate clean working directory

### Repository Health
- Ensure git history is clean
- Verify backup branch exists
- Check commit messages are descriptive
- Validate logical grouping

## Notes for Devcontainer Deployment

1. **Clean State**: Repository will be in optimal state for containerization
2. **No Test Artifacts**: Devcontainer won't include test noise
3. **Essential Only**: Only production-relevant code included
4. **Proper Gitignore**: Future test artifacts automatically excluded
5. **Logical History**: Git history tells clear story of plugin development

## Risk Mitigation

- **Multiple Backups**: Branch + commit + documented recovery steps
- **Incremental Process**: Step-by-step with validation points
- **Exclusion Patterns**: Careful file pattern matching
- **Manual Review**: Human verification before execution
- **Rollback Plan**: Clear recovery procedures documented