# Onboarding System Usage Guide for Managers

**PURPOSE**: How to actually USE the onboarding system when creating agents

---

## Quick Start: Creating Agent Instructions

### Step 1: Use the Template
Start with the appropriate template from `99_templates/AGENT_INSTRUCTION_TEMPLATES.md`

### Step 2: Reference Standard Modules
Instead of rewriting common instructions, use these references:

```markdown
## Environment Setup
See: @onboarding/04_environment_mastery/ENVIRONMENT_MASTER.md

## Testing Requirements  
See: @onboarding/04_environment_mastery/TESTING_AUTHORITY_MODULE.md

## Git Workflow
See: @onboarding/00_foundation/UNIVERSAL_FOUNDATION.md#git-workflow

## Success Validation
See: @onboarding/03_specialist_track/SPECIALIST_MASTERY.md#testing-and-verification
```

### Step 3: Focus on Task-Specific Content
Write ONLY what's unique to this agent's task:
- Specific problem to solve
- Unique context or constraints
- Custom success criteria
- Special considerations

---

## Standard Module References

### Always Include These Core Modules:

**1. Environment Access**
```markdown
## Environment Setup
Refer to: @onboarding/04_environment_mastery/ENVIRONMENT_MASTER.md
- NetBox Docker operations
- Kubernetes cluster access  
- GitOps repository details
- Testing environment setup
```

**2. Testing Authority**
```markdown
## Testing Requirements
Refer to: @onboarding/04_environment_mastery/TESTING_AUTHORITY_MODULE.md
- You have FULL docker command authority
- You MUST test all changes yourself
- NEVER ask user to validate your work
```

**3. Process Compliance**
```markdown
## Process Requirements
Refer to: @onboarding/00_foundation/UNIVERSAL_FOUNDATION.md
- Git workflow and commit standards
- Documentation requirements
- Quality gates and validation
```

---

## Example: Efficient Agent Instructions

### BEFORE (Writing Everything Custom):
```markdown
# Fix Login Bug Agent

You need to fix the login bug in the authentication system.

First, let me explain the environment setup. The NetBox Docker 
environment is running at localhost:8000 with credentials admin/admin.
To restart it, use sudo docker restart netbox-docker-netbox-1...
[500+ lines of repeated environment setup]

For testing, you have full authority to run docker commands...
[300+ lines of testing procedures]

When making changes, follow our git workflow...
[200+ lines of git standards]
```

### AFTER (Using Onboarding Modules):
```markdown
# Fix Login Bug Agent

## Task: Fix Authentication System Login Bug
- Issue: Users report "Invalid credentials" despite correct password
- Location: /netbox_hedgehog/auth/views.py
- Success: Users can login with correct credentials

## Standard Setup
- Environment: @onboarding/04_environment_mastery/ENVIRONMENT_MASTER.md
- Testing: @onboarding/04_environment_mastery/TESTING_AUTHORITY_MODULE.md  
- Process: @onboarding/00_foundation/UNIVERSAL_FOUNDATION.md

## Task-Specific Context
The authentication system uses Django's built-in auth with custom
middleware for token validation. Check the token expiry logic.
```

**Result**: 1000+ lines → 15 lines, same effectiveness!

---

## Benefits Tracking

### Token Savings
- Custom instructions: ~2000 tokens per agent
- With onboarding refs: ~200 tokens per agent
- **Savings**: 90% token reduction

### Consistency Metrics
- All agents get identical environment setup
- Testing procedures standardized
- Process compliance uniform

### Continuous Improvement
When an agent fails, update the centralized module ONCE:
- All future agents benefit
- No need to track which agents got which instructions
- Single source of truth for best practices

---

## Manager Self-Check

Before dispatching an agent, verify:
- [ ] Used appropriate template from 99_templates/
- [ ] Referenced standard onboarding modules
- [ ] Wrote ONLY task-specific instructions
- [ ] Didn't duplicate common content
- [ ] Included testing authority module reference