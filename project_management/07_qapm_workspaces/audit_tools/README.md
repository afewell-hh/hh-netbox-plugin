# QAPM File Organization Audit Tools

**Purpose**: Automated and manual tools for validating file organization compliance  
**Version**: 1.0  
**Created**: July 30, 2025  
**Usage**: Daily, weekly, and project completion audits

## Available Tools

### daily_org_check.sh
**Purpose**: Daily repository organization audit  
**Usage**: `./daily_org_check.sh`  
**Output**: Audit log in `/tmp/daily_org_audit_[timestamp].log`  
**Schedule**: Run daily (morning recommended)

**Checks Performed**:
- Repository root file count (target: < 20)
- Test artifacts outside /tests/ directory
- HTML captures outside designated locations
- JSON validation files outside proper locations
- Temporary files that should be gitignored
- Git untracked file count analysis

**Exit Codes**:
- 0: Excellent - No issues detected
- 1-2: Good - Minor issues detected
- 3-4: Warning - Multiple issues need attention
- 5+: Critical - Major cleanup required

### workspace_audit.sh
**Purpose**: QAPM workspace compliance audit  
**Usage**: `./workspace_audit.sh`  
**Output**: Audit log in `/tmp/workspace_audit_[timestamp].log`  
**Schedule**: Run weekly

**Implementation**: See FILE_ORGANIZATION_AUDIT_TOOLS.md for complete script

### completion_audit.sh
**Purpose**: Project completion organization audit  
**Usage**: `./completion_audit.sh [project_name]`  
**Output**: Audit log in `/tmp/completion_audit_[project]_[timestamp].log`  
**Schedule**: Run before project completion

**Implementation**: See FILE_ORGANIZATION_AUDIT_TOOLS.md for complete script

## Quick Usage Examples

### Daily Morning Check
```bash
cd /project_management/07_qapm_workspaces/audit_tools/
./daily_org_check.sh
echo "Exit code: $?"
```

### Check Specific Project for Completion
```bash
cd /project_management/07_qapm_workspaces/audit_tools/
./completion_audit.sh my_project_name
```

### Automated Daily Scheduling (Optional)
Add to crontab for automated daily checks:
```bash
# Daily repository organization check at 9 AM
0 9 * * * /home/ubuntu/cc/hedgehog-netbox-plugin/project_management/07_qapm_workspaces/audit_tools/daily_org_check.sh
```

## Alert Thresholds

### Critical Alerts (Immediate Action Required)
- Repository root files > 25
- Multiple critical compliance failures
- Audit script failures

### Warning Alerts (Address Within 24 Hours)
- Repository root files 20-25
- Scattered test artifacts detected
- Multiple workspace compliance issues

### Information Alerts (Monitor Trend)
- Repository root files 15-20
- Occasional scattered files
- Minor workspace compliance issues

## Integration with QAPM Workflow

### Morning Setup
1. Run daily organization check
2. Review any issues detected
3. Plan file organization for today's work
4. Brief agents on any organization priorities

### Project Completion
1. Run completion audit for project
2. Address any issues detected
3. Verify clean repository status
4. Document organization compliance

### Weekly Review
1. Run workspace compliance audit
2. Review organization trends
3. Update protocols based on findings
4. Plan process improvements

## Support and Documentation

- **Complete Documentation**: See FILE_ORGANIZATION_AUDIT_TOOLS.md
- **Protocol Reference**: See FILE_MANAGEMENT_PROTOCOLS.md
- **Training Materials**: Available in QAPM onboarding system
- **Issue Escalation**: Contact QAPM leads for audit tool issues

---

**Remember**: These tools support systematic organization - use them consistently to prevent file scattering and maintain repository cleanliness.