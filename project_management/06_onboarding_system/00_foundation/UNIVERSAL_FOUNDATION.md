# Universal Foundation - All Agents Must Complete

**CRITICAL**: This foundation prevents 90% of agent failures. Complete before role-specific training.

## Level 0: Essential Survival Knowledge

### Project Mission (15 seconds to internalize)
- **What**: Self-service Kubernetes CRD management via NetBox interface
- **Status**: MVP Complete - 12 CRD types operational  
- **Branch**: `feature/mvp2-database-foundation`
- **Success**: 49 CRDs synced, GitOps operational

### Environment Reality Check (30 seconds to verify)
```bash
# These MUST work immediately:
docker ps | grep netbox              # NetBox running on localhost:8000
kubectl get nodes                    # HCKC cluster accessible
git status                          # Clean working directory
python -m pytest --version         # Testing framework ready
```

### Non-Negotiable Process Requirements
1. **Git Workflow**: Feature branch → test → commit → PR (NEVER skip)
2. **Testing Mandate**: All code changes require passing tests
3. **Documentation**: Update docs with every feature change
4. **Escalation Trigger**: When uncertain, ASK - never guess destructively

## Level 1: Project Context Integration

### Technical Stack (Claude 4 needs explicit context)
- **Backend**: Django 4.2 with NetBox 4.3.3 plugin architecture
- **Frontend**: Bootstrap 5 with progressive disclosure UI patterns  
- **Integration**: Kubernetes Python client + ArgoCD GitOps
- **Database**: PostgreSQL shared with NetBox core
- **API**: REST endpoints for all 12 CRD types

### File System DNA (eliminate discovery waste)
```
/home/ubuntu/cc/hedgehog-netbox-plugin/  # Project root - MEMORIZE THIS
├── netbox_hedgehog/                     # Plugin core implementation
├── project_management/                  # Coordination hub (YOU ARE HERE)
├── architecture_specifications/         # Technical design docs
├── claude_memory/                       # External memory system
└── README.md                           # Project overview
```

### CRD Architecture (12 types operational)
- **VPC API**: VPCPeering, VPCAttachment, IPv4Namespace, Connection, SwitchPort, Location
- **Wiring API**: Switch, ServerFacingConnector, FabricLink, Fabric, ConnectionRequirement, PortGroup
- **Sync Pattern**: NetBox Django models ↔ Kubernetes CRDs ↔ GitOps repository

## Level 2: Process Compliance DNA

### Git Workflow (Built into agent behavior)
```bash
# Standard workflow - NEVER deviate:
git checkout -b feature/descriptive-name
# ... make changes ...
python -m pytest                       # MUST pass
git add .
git commit -m "descriptive message"
git push origin feature/descriptive-name
# Create PR via GitHub or gh cli
```

### Testing Requirements (TDD mandatory)
- **Unit Tests**: All new functions/methods require tests
- **Integration Tests**: API endpoints require integration testing
- **Manual Testing**: UI changes require manual validation
- **Success Criteria**: ALL tests pass before declaring task complete

### Documentation Standards
- **Code Comments**: Minimal - only complex business logic
- **README Updates**: Feature additions require README updates
- **Architecture Docs**: Significant changes require architecture updates
- **CLAUDE.md**: Keep external memory current with project state

### Quality Gates (Cannot be bypassed)
1. ✅ All tests pass (`python -m pytest`)
2. ✅ Code follows project conventions  
3. ✅ Documentation updated appropriately
4. ✅ Git commit with descriptive message
5. ✅ PR created for code review

## Level 3: Failure Prevention Protocols

### Context Management (Prevent 200K context overflow)
- **External Memory**: Use CLAUDE.md files for project state
- **Fresh Contexts**: Spawn new agents when context approaches limit
- **Reference Patterns**: @project_management/CLAUDE.md prevents redundancy
- **Context Recovery**: Use /compact if context degrades

### Escalation Triggers (When to ask for help)
- ❓ **Environment Issues**: NetBox/K8s/ArgoCD not responding as expected
- ❓ **Test Failures**: Cannot resolve failing tests within 30 minutes
- ❓ **Architectural Decisions**: Significant design changes needed
- ❓ **Data Loss Risk**: Any operation that might destroy existing data
- ❓ **Uncertainty**: When you're not 100% confident in the approach

### Emergency Procedures  
- **Context Loss**: Refer to CLAUDE.md architecture for project recovery
- **Environment Failure**: Use ENVIRONMENT_MASTER.md for quick recovery
- **Test Failures**: Check existing test patterns before making changes
- **Git Issues**: Never force push; ask for guidance on conflicts

## Success Validation Checklist

### Before Starting Any Task:
- [ ] Environment verified (NetBox + K8s + Git)  
- [ ] Project context internalized (mission + current state)
- [ ] Task requirements clearly understood
- [ ] Success criteria defined explicitly

### Before Declaring Task Complete:
- [ ] All tests pass without modification
- [ ] Code follows project conventions
- [ ] Documentation updated appropriately  
- [ ] Git commit with descriptive message
- [ ] Changes validated in development environment

### Before Escalating Issues:
- [ ] Attempted standard troubleshooting procedures
- [ ] Checked existing documentation for guidance
- [ ] Identified specific blocker requiring human input
- [ ] Prepared clear description of issue and attempted solutions

**FOUNDATION COMPLETE**: Agent demonstrates environment mastery, process compliance, and appropriate escalation behavior.

**NEXT STEP**: Proceed to role-specific track (Orchestrator/Manager/Specialist) based on assignment.