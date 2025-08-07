# Universal Foundation Learning - QAPM Agent Training

**Agent ID**: qapm_20250731_153550_awaiting_assignment  
**Training Date**: July 31, 2025  
**Training Level**: Level 0 - Universal Foundation

## Key Learnings Internalized

### Project Mission (Internalized)
- **What**: Self-service Kubernetes CRD management via NetBox interface
- **Status**: MVP Complete - 12 CRD types operational  
- **Branch**: `feature/mvp2-database-foundation`
- **Success**: 49 CRDs synced, GitOps operational

### Technical Stack Understanding
- **Backend**: Django 4.2 with NetBox 4.3.3 plugin architecture
- **Frontend**: Bootstrap 5 with progressive disclosure UI patterns  
- **Integration**: Kubernetes Python client + ArgoCD GitOps
- **Database**: PostgreSQL shared with NetBox core
- **API**: REST endpoints for all 12 CRD types

### File Organization DNA (Critical for QAPM Role)
**ABSOLUTE RULE**: Repository root is for essential configuration files ONLY

**Decision Tree for File Placement** (Memorized):
1. **Temporary/Working file?** → Use QAPM workspace temp/ directory (gitignored)
2. **Test artifact?** → Use /tests/ directory structure
3. **Project documentation?** → Use centralized /project_management/ or /architecture_specifications/
4. **Essential configuration?** → Repository root (with explicit justification ONLY)

### QAPM Workspace Structure (My Workspace)
```
/project_management/07_qapm_workspaces/qapm_20250731_153550_awaiting_assignment/
├── 00_project_coordination/        # Agent management and project tracking
├── 01_investigation/              # Research and analysis coordination (NOT direct technical investigation)
├── 02_implementation/             # Development work coordination through specialists
├── 03_validation/                 # Quality assurance and independent validation coordination
├── 04_sub_agent_work/            # Individual agent workspaces and coordination
├── 05_temporary_files/           # Session artifacts (automatically cleaned)
├── 06_project_archive/           # Completed work preservation
```

### CRD Architecture (12 Types Operational)
- **VPC API**: VPCPeering, VPCAttachment, IPv4Namespace, Connection, SwitchPort, Location
- **Wiring API**: Switch, ServerFacingConnector, FabricLink, Fabric, ConnectionRequirement, PortGroup
- **Sync Pattern**: NetBox Django models ↔ Kubernetes CRDs ↔ GitOps repository

### Agent Hierarchy Understanding (Critical for QAPM Role)
- **Orchestrator**: Central coordination, spawns QAPMs for complex tasks
- **Quality Assurance Project Manager (QAPM)**: Process architect, spawns task-specific agents
- **Task-specific Agents**: Execute specific technical work (coding, testing, documentation)
- **Escalation Flow**: Task agent → QAPM → Orchestrator (when appropriate)

### Quality Gates (Cannot be bypassed)
1. ✅ All tests pass (`python -m pytest`)
2. ✅ Code follows project conventions  
3. ✅ Documentation updated appropriately
4. ✅ **File organization maintained (no scattered files in repository root)**
5. ✅ **Temporary files cleaned or properly archived**
6. ✅ Git commit with descriptive message
7. ✅ PR created for code review

### Escalation Triggers (When to ask for help)
- ❓ **Environment Issues**: NetBox/K8s/ArgoCD not responding as expected
- ❓ **Test Failures**: Cannot resolve failing tests within 30 minutes
- ❓ **Architectural Decisions**: Significant design changes needed
- ❓ **Data Loss Risk**: Any operation that might destroy existing data
- ❓ **File Placement Uncertainty**: Unclear where files should be placed
- ❓ **Repository Root Creation**: Any need to create files in repository root
- ❓ **Uncertainty**: When you're not 100% confident in the approach
- ❓ **Role Boundary**: Task exceeds your agent type's designated scope

## Environment Verification Results

**Status**: Partial Success - Issues Identified

### Environment Check Results:
1. **NetBox Container**: ❌ ISSUE - Docker permission denied (socket access)
2. **HCKC Cluster**: ✅ SUCCESS - Kubernetes cluster accessible (control-1 node ready)
3. **Git Status**: ⚠️ PARTIAL - Working directory not clean (multiple untracked files including my workspace)
4. **Testing Framework**: ❌ ISSUE - pytest not available in current environment

### Issues Requiring Attention:
- Docker socket permission issue preventing NetBox verification
- pytest module not installed in current Python environment
- Repository has multiple untracked files (expected for training phase)

### Critical Finding:
Environment may require setup/configuration before proceeding with technical work. This aligns with QAPM role as process architect - I should identify environment setup needs rather than directly fixing technical issues.

## Universal Foundation Mastery Status: COMPLETE
- ✅ Project mission internalized
- ✅ Technical stack understood
- ✅ File organization DNA memorized
- ✅ QAPM workspace structure implemented
- ✅ CRD architecture comprehended
- ✅ Agent hierarchy clarified
- ✅ Quality gates defined
- ✅ Escalation triggers identified
- ✅ Environment verification attempted (issues noted for escalation)