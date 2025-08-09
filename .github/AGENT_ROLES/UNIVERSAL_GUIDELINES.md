# Universal Agent Guidelines
**NetBox Hedgehog Plugin - Simplified Agile + GitHub System**

## Quick Start (30 seconds)
**Purpose**: Every agent follows these core processes for consistent GitHub-driven project management.

**Your Mission**: Help deliver high-quality NetBox Hedgehog Plugin features using GitHub Issues as your single source of truth.

---

## Core Responsibilities

### 1. Read GitHub Issues (User Story Format)
**Every task starts with a GitHub Issue. Issues follow this format:**

```
Title: [User Story] As a [user type], I want [capability] so that [benefit]

Description:
## Acceptance Criteria
- [ ] Specific testable requirement 1
- [ ] Specific testable requirement 2
- [ ] Specific testable requirement 3

## Technical Context
- Brief context about implementation approach
- Links to related issues/documentation

## Definition of Done
- [ ] Code implemented and tested
- [ ] Documentation updated
- [ ] PR merged and deployed
```

**How to Read Issues:**
- **Title tells you WHO and WHAT** (user story format)
- **Acceptance Criteria = Success Requirements** (must all be met)
- **Technical Context = Implementation Guidance** (your roadmap)
- **Definition of Done = Quality Gate** (when you're truly finished)

### 2. Update Task Status
**Always keep GitHub Issues current:**

**Status Updates via Comments:**
```markdown
## Status Update - [Your Role]
**Current State**: [In Progress/Blocked/Testing/Complete]
**Progress**: [Brief description of what you've done]
**Next Steps**: [What you'll do next]
**Blockers**: [Any issues preventing progress]
**ETA**: [Realistic completion estimate]
```

**When to Update:**
- When you start working (mark as "In Progress")
- After significant progress (daily for multi-day tasks)
- When blocked (immediately with details)
- When complete (with evidence/links)

### 3. Ask for Help/Clarification
**Don't work in isolation. Ask questions early:**

**Use Issue Comments for Questions:**
```markdown
## Clarification Needed - [Your Role]
**Question**: [Specific question about requirements/approach]
**Context**: [Why this matters for implementation]
**Options Considered**: [Different approaches you're evaluating]
**Recommendation**: [Your preferred approach with reasoning]
```

**When to Ask:**
- Requirements are ambiguous
- Technical approach has multiple valid options
- Dependencies on other work are unclear
- Timeline conflicts with quality expectations

### 4. Handle Blockers
**Blockers kill project momentum. Address immediately:**

**Blocker Report Format:**
```markdown
## BLOCKER - [Your Role]
**Issue**: [Clear description of what's preventing progress]
**Impact**: [How this affects timeline/deliverables]
**Attempted Solutions**: [What you've tried]
**Help Needed**: [Specific assistance required]
**Workaround Available**: [Yes/No - if yes, describe]
```

**Common Blockers:**
- Missing information or requirements
- Technical dependencies not ready
- Access/permission issues
- Conflicting requirements from stakeholders

---

## GitHub Interaction Patterns

### Issue Management
```bash
# View assigned issues
gh issue list --assignee @me

# Add yourself to issue
gh issue edit [number] --add-assignee @me

# Comment on issue
gh issue comment [number] --body "Status update message"

# Close completed issue
gh issue close [number] --comment "Implementation complete - PR #XXX merged"
```

### Branch and PR Workflow
```bash
# Create feature branch from issue
git checkout -b issue-[number]-[brief-description]

# Regular commits with issue reference
git commit -m "feat: implement user authentication

Addresses #[issue-number]
- Add login form validation
- Implement session management
- Update user dashboard"

# Create PR linking to issue
gh pr create --title "Fix #[number]: [brief description]" \
  --body "Closes #[number]

## Changes Made
- Specific change 1
- Specific change 2

## Testing Done
- Test scenario 1
- Test scenario 2

## Screenshots/Evidence
[If applicable]"
```

### Communication Standards
**All communication through GitHub:**
- **Issues**: Requirements, clarifications, status updates
- **PRs**: Implementation details, code review discussions  
- **Discussions**: High-level planning, architectural decisions
- **Wiki**: Persistent documentation and guides

**Response Time Expectations:**
- **Critical blockers**: Within 4 hours
- **Questions/clarifications**: Within 1 business day
- **Code reviews**: Within 2 business days
- **Status updates**: At least every 2 days for active work

---

## Quality Standards

### Definition of Done Checklist
**Every task must meet these criteria:**

- [ ] **Acceptance criteria met**: All issue requirements implemented
- [ ] **Code quality**: Follows project coding standards
- [ ] **Testing**: Manual testing completed, evidence provided
- [ ] **Documentation**: README/docs updated as needed
- [ ] **Code review**: PR approved by appropriate reviewer(s)
- [ ] **Integration**: Changes don't break existing functionality
- [ ] **Evidence**: Screenshots/logs demonstrate working implementation

### Code Quality Requirements
```python
# Good commit message
git commit -m "feat: add VPC creation form validation

Addresses #123
- Add client-side validation for required fields
- Implement backend validation with proper error messages
- Update form styling for better UX
- Add unit tests for validation logic

Tested: Manual form submission with valid/invalid data"

# Bad commit message  
git commit -m "fix stuff"
```

### Documentation Standards
**Update these when relevant:**
- **README.md**: Installation/setup if you changed requirements
- **API docs**: If you added/changed API endpoints
- **User guides**: If you changed user-facing functionality
- **Developer docs**: If you changed development workflow

---

## Common Pitfalls to Avoid

### ❌ Working Without Clear Requirements
**Problem**: Starting work before understanding acceptance criteria
**Solution**: Always ask questions before coding

### ❌ Going Silent During Work  
**Problem**: No status updates while working on multi-day tasks
**Solution**: Comment on issues with progress every 1-2 days

### ❌ Scope Creep
**Problem**: Adding features not in acceptance criteria
**Solution**: Stick to requirements or create new issues for additional work

### ❌ Poor Testing Evidence
**Problem**: Claiming "it works" without demonstrating it
**Solution**: Provide screenshots, logs, or test results

### ❌ Ignoring Integration Impact
**Problem**: Breaking existing features while adding new ones
**Solution**: Test full user workflows, not just new features

---

## Emergency Procedures

### Critical Bug (Production Down)
1. **Immediate**: Comment on issue with "CRITICAL BUG - Production Impact"
2. **Create hotfix branch**: `hotfix-[issue-number]-[description]`
3. **Fix with minimal change**: Don't refactor, just fix the immediate issue
4. **Test thoroughly**: Verify fix doesn't introduce new issues
5. **Fast-track review**: Request immediate review and merge
6. **Follow-up**: Create separate issue for root cause analysis

### Missed Deadline
1. **Early warning**: Update issue 24 hours before deadline if at risk
2. **Clear communication**: Explain exactly what's complete vs incomplete
3. **Provide options**: Suggest scope reduction or timeline adjustment
4. **Get approval**: Don't just extend deadline unilaterally

---

## Local Test/Dev Environment Access

### Critical Environment Setup
**MANDATORY**: All code changes MUST be tested in the local test/dev NetBox installation. Guessing or assumptions lead to failures.

**Environment Credentials Location:**
```bash
# Load environment variables from .env file
source /home/ubuntu/cc/hedgehog-netbox-plugin/.env

# Key variables available:
# NETBOX_URL="http://localhost:8000/"
# NETBOX_TOKEN="ced6a3e0a978db0ad4de39cd66af4868372d7dd0"
# GITHUB_TOKEN="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"
```

**Local NetBox Access:**
- **URL**: http://localhost:8000/
- **Admin Access**: Use the NETBOX_TOKEN from .env file
- **Plugin URL**: http://localhost:8000/plugins/hedgehog/
- **Container Name**: `netbox-docker-netbox-1`

**Docker Environment Status Check:**
```bash
# Check all containers running
sudo docker ps | grep netbox

# Check NetBox logs
sudo docker logs netbox-docker-netbox-1 --tail 50

# Copy files to container for testing
sudo docker cp /path/to/file netbox-docker-netbox-1:/opt/netbox/netbox/path/to/destination

# Restart NetBox after changes
sudo docker restart netbox-docker-netbox-1
```

**Kubernetes Test Environment:**
```bash
# Load kubeconfig
export KUBECONFIG=/home/ubuntu/cc/hedgehog-netbox-plugin/hemk/poc_development/kubeconfig/kubeconfig.yaml

# Test K8s access
kubectl get nodes
kubectl get crds | grep hedgehog

# Test fabric API server access (from .env)
# TEST_FABRIC_K8S_API_SERVER="https://172.18.0.8:6443"
```

**Validation Requirements:**
1. **Load .env first**: `source .env` before any testing
2. **Test in NetBox UI**: Access http://localhost:8000/plugins/hedgehog/ 
3. **Verify functionality**: Navigate through your changes manually
4. **Check logs**: Review docker logs for errors
5. **Test K8s integration**: If applicable, verify CRD operations work

**Environment Documentation Reference:**
- **Complete Setup Guide**: `/home/ubuntu/cc/hedgehog-netbox-plugin/project_management/06_onboarding_system/04_environment_mastery/ENVIRONMENT_MASTER.md`
- **Failure Recovery**: Docker restart procedures in environment guide

**Common Testing Commands:**
```bash
# Quick environment validation
source .env
curl -H "Authorization: Token $NETBOX_TOKEN" $NETBOX_URL/api/
sudo docker ps | grep netbox
kubectl get nodes
```

---

## Success Metrics

### Individual Agent Success
**You're successful when:**
- ✅ Issues assigned to you are completed on time
- ✅ Your PRs pass review without major changes needed
- ✅ Stakeholders can track your progress through GitHub
- ✅ You proactively communicate blockers and risks
- ✅ Your work integrates smoothly with other agents' work

### Project Success Indicators  
**The project succeeds when:**
- 🎯 **User stories deliver real value** (not just technical features)
- 🚀 **Features ship regularly** (weekly releases)
- 🔄 **Process runs smoothly** (minimal coordination overhead)
- 🧪 **Quality stays high** (few bugs, happy users)
- 📈 **Team velocity increases** (better estimation over time)

---

**Remember**: These guidelines exist to make collaboration efficient and deliverables reliable. When in doubt, over-communicate rather than work in isolation.