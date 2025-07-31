#!/bin/bash
# Daily repository organization audit
# Usage: ./daily_org_check.sh
# Creates audit log in /tmp/ directory

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