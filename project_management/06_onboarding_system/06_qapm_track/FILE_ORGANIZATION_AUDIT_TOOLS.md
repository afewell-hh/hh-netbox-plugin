# File Organization Audit Tools and Validation Procedures

**Purpose**: Automated and manual tools for validating file organization compliance  
**Version**: 1.0  
**Created**: July 30, 2025  
**Usage**: Daily, weekly, and project completion audits

## Overview

These tools and procedures ensure consistent compliance with file management protocols and provide early detection of file scattering issues before they accumulate into major cleanup efforts.

## Automated Audit Scripts

### Daily Repository Organization Check

```bash
#!/bin/bash
# Daily repository organization audit
# Save as: /project_management/07_qapm_workspaces/audit_tools/daily_org_check.sh

REPO_ROOT="/home/ubuntu/cc/hedgehog-netbox-plugin"
DATE=$(date +%Y%m%d_%H%M%S)
AUDIT_LOG="/tmp/daily_org_audit_$DATE.log"

echo "=== DAILY REPOSITORY ORGANIZATION AUDIT ===" | tee "$AUDIT_LOG"
echo "Date: $(date)" | tee -a "$AUDIT_LOG"
echo "Repository: $REPO_ROOT" | tee -a "$AUDIT_LOG"
echo "" | tee -a "$AUDIT_LOG"

# Check repository root file count
echo "=== Repository Root Analysis ===" | tee -a "$AUDIT_LOG"
ROOT_FILE_COUNT=$(find "$REPO_ROOT" -maxdepth 1 -type f | wc -l)
echo "Files in repository root: $ROOT_FILE_COUNT (target: < 20)" | tee -a "$AUDIT_LOG"

if [ "$ROOT_FILE_COUNT" -gt 20 ]; then
    echo "WARNING: Excessive files in repository root!" | tee -a "$AUDIT_LOG"
    echo "Files:" | tee -a "$AUDIT_LOG"
    find "$REPO_ROOT" -maxdepth 1 -type f | sort | tee -a "$AUDIT_LOG"
fi

# Check for scattered test artifacts
echo "" | tee -a "$AUDIT_LOG"
echo "=== Test Artifact Analysis ===" | tee -a "$AUDIT_LOG"

# Python test scripts outside /tests/
SCATTERED_TEST_SCRIPTS=$(find "$REPO_ROOT" -name "*test*.py" -not -path "*/tests/*" -not -path "*/netbox_hedgehog/*" -type f)
if [ -n "$SCATTERED_TEST_SCRIPTS" ]; then
    echo "WARNING: Test scripts outside /tests/ directory:" | tee -a "$AUDIT_LOG"
    echo "$SCATTERED_TEST_SCRIPTS" | tee -a "$AUDIT_LOG"
else
    echo "GOOD: No scattered test scripts found" | tee -a "$AUDIT_LOG"
fi

# HTML captures outside designated locations
SCATTERED_HTML=$(find "$REPO_ROOT" -name "*.html" -not -path "*/tests/evidence/captures/*" -not -path "*/netbox_hedgehog/templates/*" -not -path "*/temp/*" -type f)
if [ -n "$SCATTERED_HTML" ]; then
    echo "WARNING: HTML files outside designated locations:" | tee -a "$AUDIT_LOG"
    echo "$SCATTERED_HTML" | tee -a "$AUDIT_LOG"
else
    echo "GOOD: No scattered HTML captures found" | tee -a "$AUDIT_LOG"
fi

# JSON validation files outside designated locations
SCATTERED_JSON=$(find "$REPO_ROOT" -name "*validation*.json" -not -path "*/tests/evidence/validation/*" -not -path "*/temp/*" -type f)
if [ -n "$SCATTERED_JSON" ]; then
    echo "WARNING: JSON validation files outside designated locations:" | tee -a "$AUDIT_LOG"
    echo "$SCATTERED_JSON" | tee -a "$AUDIT_LOG"
else
    echo "GOOD: No scattered JSON validation files found" | tee -a "$AUDIT_LOG"
fi

# Check for temporary files that should be gitignored
echo "" | tee -a "$AUDIT_LOG"
echo "=== Temporary File Analysis ===" | tee -a "$AUDIT_LOG"

TEMP_FILES=$(find "$REPO_ROOT" -name "*temp*" -o -name "*debug*" -o -name "*scratch*" -o -name "*.tmp" | grep -v gitignore | grep -v temp/)
if [ -n "$TEMP_FILES" ]; then
    echo "WARNING: Temporary files that should be gitignored:" | tee -a "$AUDIT_LOG"
    echo "$TEMP_FILES" | tee -a "$AUDIT_LOG"
else
    echo "GOOD: No unmanaged temporary files found" | tee -a "$AUDIT_LOG"
fi

# Check git status for untracked files
echo "" | tee -a "$AUDIT_LOG"
echo "=== Git Status Analysis ===" | tee -a "$AUDIT_LOG"

cd "$REPO_ROOT"
UNTRACKED_FILES=$(git status --porcelain | grep "^??" | wc -l)
echo "Untracked files: $UNTRACKED_FILES" | tee -a "$AUDIT_LOG"

if [ "$UNTRACKED_FILES" -gt 10 ]; then
    echo "WARNING: High number of untracked files - check for scattering:" | tee -a "$AUDIT_LOG"
    git status --porcelain | grep "^??" | head -20 | tee -a "$AUDIT_LOG"
fi

# Summary
echo "" | tee -a "$AUDIT_LOG"
echo "=== AUDIT SUMMARY ===" | tee -a "$AUDIT_LOG"

ISSUES=0
if [ "$ROOT_FILE_COUNT" -gt 20 ]; then ((ISSUES++)); fi
if [ -n "$SCATTERED_TEST_SCRIPTS" ]; then ((ISSUES++)); fi
if [ -n "$SCATTERED_HTML" ]; then ((ISSUES++)); fi
if [ -n "$SCATTERED_JSON" ]; then ((ISSUES++)); fi
if [ -n "$TEMP_FILES" ]; then ((ISSUES++)); fi
if [ "$UNTRACKED_FILES" -gt 10 ]; then ((ISSUES++)); fi

if [ "$ISSUES" -eq 0 ]; then
    echo "RESULT: EXCELLENT - Repository organization is clean" | tee -a "$AUDIT_LOG"
elif [ "$ISSUES" -le 2 ]; then
    echo "RESULT: GOOD - Minor organization issues detected" | tee -a "$AUDIT_LOG"
elif [ "$ISSUES" -le 4 ]; then
    echo "RESULT: WARNING - Multiple organization issues need attention" | tee -a "$AUDIT_LOG"
else
    echo "RESULT: CRITICAL - Major organization problems require immediate cleanup" | tee -a "$AUDIT_LOG"
fi

echo "Issues detected: $ISSUES" | tee -a "$AUDIT_LOG"
echo "Audit log saved: $AUDIT_LOG" | tee -a "$AUDIT_LOG"
echo "" | tee -a "$AUDIT_LOG"

# Return appropriate exit code
exit $ISSUES
```

### QAPM Workspace Compliance Audit

```bash
#!/bin/bash
# QAPM workspace organization audit
# Save as: /project_management/07_qapm_workspaces/audit_tools/workspace_audit.sh

WORKSPACE_PATH="/home/ubuntu/cc/hedgehog-netbox-plugin/project_management/07_qapm_workspaces"
DATE=$(date +%Y%m%d_%H%M%S)
AUDIT_LOG="/tmp/workspace_audit_$DATE.log"

echo "=== QAPM WORKSPACE ORGANIZATION AUDIT ===" | tee "$AUDIT_LOG"
echo "Date: $(date)" | tee -a "$AUDIT_LOG"
echo "Workspace path: $WORKSPACE_PATH" | tee -a "$AUDIT_LOG"
echo "" | tee -a "$AUDIT_LOG"

if [ ! -d "$WORKSPACE_PATH" ]; then
    echo "ERROR: QAPM workspace directory does not exist!" | tee -a "$AUDIT_LOG"
    exit 1
fi

TOTAL_ISSUES=0

# Check each workspace
for project in "$WORKSPACE_PATH"/*; do
    if [ -d "$project" ] && [ "$(basename "$project")" != "TEMPLATE_WORKSPACE" ]; then
        project_name=$(basename "$project")
        echo "=== Auditing project: $project_name ===" | tee -a "$AUDIT_LOG"
        
        PROJECT_ISSUES=0
        
        # Check required directory structure
        required_dirs=("00_project_overview" "01_problem_analysis" "02_process_design" "03_execution_artifacts" "04_evidence_collection" "05_quality_validation" "06_completion_documentation" "temp")
        
        for dir in "${required_dirs[@]}"; do
            if [ ! -d "$project/$dir" ]; then
                echo "WARNING: Missing required directory: $dir" | tee -a "$AUDIT_LOG"
                ((PROJECT_ISSUES++))
            fi
        done
        
        # Check for README file
        if [ ! -f "$project/README.md" ]; then
            echo "WARNING: Missing project README.md" | tee -a "$AUDIT_LOG"
            ((PROJECT_ISSUES++))
        fi
        
        # Check for scattered files in workspace root
        file_count=$(find "$project" -maxdepth 1 -type f | wc -l)
        if [ "$file_count" -gt 3 ]; then
            echo "WARNING: Too many files in workspace root ($file_count files)" | tee -a "$AUDIT_LOG"
            find "$project" -maxdepth 1 -type f | tee -a "$AUDIT_LOG"
            ((PROJECT_ISSUES++))
        fi
        
        # Check .gitignore for temp directory
        if [ ! -f "$project/.gitignore" ]; then
            echo "WARNING: Missing .gitignore file" | tee -a "$AUDIT_LOG"
            ((PROJECT_ISSUES++))
        elif ! grep -q "temp/" "$project/.gitignore"; then
            echo "WARNING: .gitignore does not ignore temp/ directory" | tee -a "$AUDIT_LOG"
            ((PROJECT_ISSUES++))
        fi
        
        # Check for files in temp that should be gitignored
        if [ -d "$project/temp" ]; then
            temp_file_count=$(find "$project/temp" -type f | wc -l)
            if [ "$temp_file_count" -gt 0 ]; then
                echo "INFO: Temporary files found in temp/ directory ($temp_file_count files)" | tee -a "$AUDIT_LOG"
                # This is OK if properly gitignored, just informational
            fi
        fi
        
        if [ "$PROJECT_ISSUES" -eq 0 ]; then
            echo "RESULT: Project $project_name is compliant" | tee -a "$AUDIT_LOG"
        else
            echo "RESULT: Project $project_name has $PROJECT_ISSUES compliance issues" | tee -a "$AUDIT_LOG"
        fi
        
        TOTAL_ISSUES=$((TOTAL_ISSUES + PROJECT_ISSUES))
        echo "" | tee -a "$AUDIT_LOG"
    fi
done

# Check if template workspace exists
if [ ! -d "$WORKSPACE_PATH/TEMPLATE_WORKSPACE" ]; then
    echo "WARNING: TEMPLATE_WORKSPACE missing - should be available for new projects" | tee -a "$AUDIT_LOG"
    ((TOTAL_ISSUES++))
fi

echo "=== WORKSPACE AUDIT SUMMARY ===" | tee -a "$AUDIT_LOG"
if [ "$TOTAL_ISSUES" -eq 0 ]; then
    echo "RESULT: EXCELLENT - All workspaces are compliant" | tee -a "$AUDIT_LOG"
elif [ "$TOTAL_ISSUES" -le 3 ]; then
    echo "RESULT: GOOD - Minor compliance issues detected" | tee -a "$AUDIT_LOG"
elif [ "$TOTAL_ISSUES" -le 8 ]; then
    echo "RESULT: WARNING - Multiple compliance issues need attention" | tee -a "$AUDIT_LOG"
else
    echo "RESULT: CRITICAL - Major compliance problems require immediate attention" | tee -a "$AUDIT_LOG"
fi

echo "Total issues detected: $TOTAL_ISSUES" | tee -a "$AUDIT_LOG"
echo "Audit log saved: $AUDIT_LOG" | tee -a "$AUDIT_LOG"

exit $TOTAL_ISSUES
```

### Project Completion Organization Audit

```bash
#!/bin/bash
# Project completion organization audit
# Usage: completion_audit.sh [project_name]
# Save as: /project_management/07_qapm_workspaces/audit_tools/completion_audit.sh

if [ $# -ne 1 ]; then
    echo "Usage: $0 [project_name]"
    echo "Example: $0 git_auth_fix"
    exit 1
fi

PROJECT_NAME="$1"
WORKSPACE_PATH="/home/ubuntu/cc/hedgehog-netbox-plugin/project_management/07_qapm_workspaces"
PROJECT_PATH="$WORKSPACE_PATH/$PROJECT_NAME"
REPO_ROOT="/home/ubuntu/cc/hedgehog-netbox-plugin"
DATE=$(date +%Y%m%d_%H%M%S)
AUDIT_LOG="/tmp/completion_audit_${PROJECT_NAME}_$DATE.log"

echo "=== PROJECT COMPLETION ORGANIZATION AUDIT ===" | tee "$AUDIT_LOG"
echo "Project: $PROJECT_NAME" | tee -a "$AUDIT_LOG"
echo "Date: $(date)" | tee -a "$AUDIT_LOG"
echo "Project path: $PROJECT_PATH" | tee -a "$AUDIT_LOG"
echo "" | tee -a "$AUDIT_LOG"

if [ ! -d "$PROJECT_PATH" ]; then
    echo "ERROR: Project workspace does not exist: $PROJECT_PATH" | tee -a "$AUDIT_LOG"
    exit 1
fi

TOTAL_ISSUES=0

# Check workspace organization
echo "=== Workspace Organization Check ===" | tee -a "$AUDIT_LOG"

# Required completion documentation
completion_docs=("solution_summary.md" "lessons_learned.md" "handoff_documentation.md")
for doc in "${completion_docs[@]}"; do
    if [ ! -f "$PROJECT_PATH/06_completion_documentation/$doc" ]; then
        echo "WARNING: Missing completion document: $doc" | tee -a "$AUDIT_LOG"
        ((TOTAL_ISSUES++))
    fi
done

# Check for evidence collection
evidence_dirs=("implementation_evidence" "test_results" "user_workflow_validation")
for dir in "${evidence_dirs[@]}"; do
    if [ ! -d "$PROJECT_PATH/04_evidence_collection/$dir" ] || [ -z "$(ls -A "$PROJECT_PATH/04_evidence_collection/$dir" 2>/dev/null)" ]; then
        echo "WARNING: Missing or empty evidence directory: $dir" | tee -a "$AUDIT_LOG"
        ((TOTAL_ISSUES++))
    fi
done

# Check for temporary file cleanup
if [ -d "$PROJECT_PATH/temp" ]; then
    temp_files=$(find "$PROJECT_PATH/temp" -type f | wc -l)
    if [ "$temp_files" -gt 0 ]; then
        echo "WARNING: Temporary files not cleaned ($temp_files files remaining)" | tee -a "$AUDIT_LOG"
        echo "Temporary files:" | tee -a "$AUDIT_LOG"
        find "$PROJECT_PATH/temp" -type f | tee -a "$AUDIT_LOG"
        ((TOTAL_ISSUES++))
    else
        echo "GOOD: Temporary files properly cleaned" | tee -a "$AUDIT_LOG"
    fi
fi

# Check repository root cleanliness
echo "" | tee -a "$AUDIT_LOG"
echo "=== Repository Root Cleanliness Check ===" | tee -a "$AUDIT_LOG"

cd "$REPO_ROOT"
untracked_in_root=$(git status --porcelain | grep "^??" | grep -v "/" | wc -l)
if [ "$untracked_in_root" -gt 0 ]; then
    echo "WARNING: Untracked files in repository root:" | tee -a "$AUDIT_LOG"
    git status --porcelain | grep "^??" | grep -v "/" | tee -a "$AUDIT_LOG"
    ((TOTAL_ISSUES++))
else
    echo "GOOD: Repository root is clean" | tee -a "$AUDIT_LOG"
fi

# Check for project-related scattered files
echo "" | tee -a "$AUDIT_LOG"
echo "=== Project-Related Scatter Check ===" | tee -a "$AUDIT_LOG"

# Look for files that might be related to this project outside the workspace
project_related_files=$(find "$REPO_ROOT" -type f -name "*${PROJECT_NAME}*" -not -path "$PROJECT_PATH/*" -not -path "*/\.git/*")
if [ -n "$project_related_files" ]; then
    echo "WARNING: Project-related files found outside workspace:" | tee -a "$AUDIT_LOG"
    echo "$project_related_files" | tee -a "$AUDIT_LOG"
    ((TOTAL_ISSUES++))
else
    echo "GOOD: No project-related files scattered outside workspace" | tee -a "$AUDIT_LOG"
fi

# Validate quality validation completed
echo "" | tee -a "$AUDIT_LOG"
echo "=== Quality Validation Check ===" | tee -a "$AUDIT_LOG"

validation_dirs=("independent_validation" "regression_testing")
for dir in "${validation_dirs[@]}"; do
    if [ ! -d "$PROJECT_PATH/05_quality_validation/$dir" ] || [ -z "$(ls -A "$PROJECT_PATH/05_quality_validation/$dir" 2>/dev/null)" ]; then
        echo "WARNING: Missing or empty quality validation: $dir" | tee -a "$AUDIT_LOG"
        ((TOTAL_ISSUES++))
    fi
done

# Final summary
echo "" | tee -a "$AUDIT_LOG"
echo "=== PROJECT COMPLETION AUDIT SUMMARY ===" | tee -a "$AUDIT_LOG"

if [ "$TOTAL_ISSUES" -eq 0 ]; then
    echo "RESULT: EXCELLENT - Project is ready for completion and archival" | tee -a "$AUDIT_LOG"
    echo "✓ All completion documentation present" | tee -a "$AUDIT_LOG"
    echo "✓ Evidence collection complete" | tee -a "$AUDIT_LOG"
    echo "✓ Temporary files cleaned" | tee -a "$AUDIT_LOG"
    echo "✓ Repository root clean" | tee -a "$AUDIT_LOG"
    echo "✓ No scattered files detected" | tee -a "$AUDIT_LOG"
    echo "✓ Quality validation complete" | tee -a "$AUDIT_LOG"
elif [ "$TOTAL_ISSUES" -le 3 ]; then
    echo "RESULT: GOOD - Minor issues need resolution before completion" | tee -a "$AUDIT_LOG"
elif [ "$TOTAL_ISSUES" -le 6 ]; then
    echo "RESULT: WARNING - Multiple issues must be resolved before completion" | tee -a "$AUDIT_LOG"
else
    echo "RESULT: CRITICAL - Project not ready for completion - major issues detected" | tee -a "$AUDIT_LOG"
fi

echo "Total issues: $TOTAL_ISSUES" | tee -a "$AUDIT_LOG"
echo "Audit log: $AUDIT_LOG" | tee -a "$AUDIT_LOG"

exit $TOTAL_ISSUES
```

## Manual Audit Procedures

### Daily QAPM Organization Checklist

**MORNING SETUP AUDIT** (5 minutes):
```
□ Check repository root for any new scattered files
□ Review active workspaces for organization compliance
□ Verify temporary directories are properly gitignored
□ Plan file organization requirements for today's agent spawning
□ Review any overnight automated audit alerts
```

**AGENT SPAWNING AUDIT** (per agent):
```
□ Agent instruction includes comprehensive file organization section
□ Workspace setup complete before agent starts work
□ Agent understands specific file placement requirements
□ Cleanup validation requirements clearly specified
□ Agent has escalation path for unclear file placement
```

**EVENING REVIEW AUDIT** (10 minutes):
```
□ All files created today in appropriate locations
□ Temporary files cleaned or properly archived
□ Git status shows only intended changes
□ Agent compliance with file organization verified
□ Repository root remains clean (essential files only)
```

### Weekly Comprehensive Audit

**REPOSITORY HEALTH ASSESSMENT** (30 minutes):
```
□ Run automated daily audit script and review results
□ Perform manual scan of repository root for organization
□ Check all active QAPM workspaces for compliance
□ Review file scattering trends and patterns
□ Audit centralized documentation integration
□ Verify test artifacts properly organized in /tests/
□ Check .gitignore effectiveness for temporary files
□ Review agent compliance with file organization requirements
```

**WORKSPACE COMPLIANCE REVIEW**:
```
□ All active workspaces follow template structure
□ README files provide clear navigation
□ Evidence collection properly organized
□ Temporary files appropriately managed
□ Agent coordination documented in proper locations
□ Quality validation materials properly stored
□ Completion documentation standards met
```

### Project Completion Audit

**COMPREHENSIVE PROJECT ORGANIZATION REVIEW** (45 minutes):
```
□ All project artifacts in designated workspace locations
□ Completion documentation comprehensive and well-organized
□ Evidence collection complete and accessible
□ Quality validation properly documented
□ Temporary files cleaned or archived
□ Repository root impact assessed and cleaned
□ Integration with centralized systems complete
□ Handoff materials prepared and organized
□ Lessons learned documented for process improvement
□ Archive plan prepared for long-term storage
```

**HANDOFF PREPARATION CHECKLIST**:
```
□ Navigation guide to all project materials prepared
□ File location documentation complete
□ Integration points with other projects documented
□ Archive and maintenance instructions prepared
□ Knowledge transfer materials organized
□ Quality validation evidence compiled
□ Project impact on repository organization assessed
```

## Alert and Escalation Procedures

### Automated Alert Thresholds

**DAILY AUDIT ALERTS**:
- Repository root files > 25: CRITICAL alert
- Scattered test artifacts detected: WARNING alert
- Unmanaged temporary files > 10: WARNING alert
- Untracked files > 15: INVESTIGATION alert

**WORKSPACE AUDIT ALERTS**:
- Workspace missing required directories: CRITICAL alert
- Multiple workspaces non-compliant: WARNING alert
- Template workspace missing: MAINTENANCE alert

### Escalation Triggers

**IMMEDIATE ESCALATION**:
- Repository root files > 50 (emergency cleanup needed)
- Multiple QAPMs creating scattered files (training issue)
- Workspace template corruption (system integrity issue)
- Automated audit system failure (tool maintenance needed)

**WEEKLY ESCALATION**:
- Consistent file scattering patterns (process improvement needed)
- Agent non-compliance trends (training enhancement needed)
- Workspace adoption resistance (change management needed)

### Response Procedures

**CRITICAL ALERT RESPONSE** (within 2 hours):
1. **Stop Current Work**: Halt all file creation until issue resolved
2. **Assess Scope**: Determine extent of organization breakdown
3. **Emergency Cleanup**: Use emergency cleanup procedures
4. **Root Cause Analysis**: Identify why organization failed
5. **Process Correction**: Implement immediate preventive measures
6. **Documentation**: Record incident and prevention measures

**WARNING ALERT RESPONSE** (within 24 hours):
1. **Investigation**: Determine cause of organization issues
2. **Targeted Cleanup**: Address specific scattered files
3. **Agent Notification**: Inform responsible agents of compliance issues
4. **Process Reinforcement**: Review and reinforce file management protocols
5. **Monitoring**: Increase audit frequency until resolved

## Quality Metrics and Reporting

### Organization Quality Metrics

**PRIMARY METRICS**:
- Repository root file count (target: < 20)
- Scattered file incidents per week (target: < 3)
- QAPM workspace compliance rate (target: 100%)
- Agent file organization compliance (target: 95%+)
- Time to locate project artifacts (target: < 2 minutes)

**SECONDARY METRICS**:
- Emergency cleanup incidents (target: < 1 per month)
- File organization training completion (target: 100%)
- Automated audit success rate (target: 95%+)
- Agent file placement escalations (target: < 5 per week)

### Weekly Organization Report Template

```markdown
# Weekly File Organization Report

**Week of**: [Date Range]
**Reporting QAPM**: [Name]
**Report Date**: [Date]

## Summary Metrics
- Repository root files: [count] (target: < 20)
- Scattered files detected: [count] (target: < 3)
- Workspace compliance: [percentage] (target: 100%)
- Agent compliance: [percentage] (target: 95%+)

## Issues Identified
- [List of specific organization issues]
- [Root cause analysis for major issues]
- [Impact assessment]

## Corrective Actions Taken
- [Specific actions taken to address issues]
- [Process improvements implemented]
- [Training reinforcement provided]

## Process Improvements
- [Improvements to audit procedures]
- [Template updates]
- [Training enhancements]

## Recommendations
- [Suggestions for preventing future issues]
- [Process optimization opportunities]
- [Tool improvements needed]

## Next Week Focus
- [Specific areas for increased attention]
- [Follow-up actions required]
- [Monitoring priorities]
```

---

**Implementation Status**: READY FOR DEPLOYMENT  
**Tool Location**: Save scripts to `/project_management/07_qapm_workspaces/audit_tools/`  
**Training Integration**: Include in QAPM onboarding and ongoing training  
**Monitoring Schedule**: Daily automated + weekly manual + project completion audits