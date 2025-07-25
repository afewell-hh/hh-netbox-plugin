# Git Workflow Mastery Module

**PURPOSE**: Mandatory git practices for all HNP agents  
**AUTHORITY**: You MUST follow these git practices - no exceptions  
**VALIDATION**: Git compliance checked in every agent deliverable

---

## MANDATORY GIT WORKFLOW

### Before Starting ANY Work

```bash
# 1. Always start from latest develop
git checkout develop
git pull origin develop

# 2. Create feature branch with descriptive name
git checkout -b feature/fix-specific-issue-name

# 3. Verify clean starting state
git status  # Should show "working tree clean"
```

### During Work (COMMIT FREQUENTLY)

**Commit Requirements**:
- **Minimum**: Every 2 hours of work
- **After**: Each logical change or fix
- **Before**: Running tests or major changes
- **Always**: Before reporting work complete

```bash
# Stage changes
git add .

# Write descriptive commit message
git commit -m "fix: resolve sync button attribution issue

- Update git_file_path calculation logic
- Fix CRD attribution display in templates  
- Add validation for GitOps repository paths

Tested: GUI tests pass (71/71)
Evidence: CRDs now show 'From Git' correctly"
```

### Commit Message Standards

**Format Required**:
```
type: brief description (50 chars max)

- Detailed change description (if needed)
- What was changed and why
- Impact or benefits

Tested: [How you validated the change]
Evidence: [Proof that it works]
```

**Types**:
- `feat:` New feature or capability
- `fix:` Bug fix or issue resolution  
- `docs:` Documentation changes
- `test:` Test additions or improvements
- `refactor:` Code reorganization
- `style:` Formatting or style changes

### Before Completing Work

```bash
# 1. Commit all changes
git add .
git commit -m "feat: complete task implementation with validation"

# 2. Run GUI tests (MANDATORY)
./run_demo_tests.py
# Must show: 71/71 tests passing

# 3. Push to remote
git push origin feature/your-branch-name

# 4. Create evidence of working functionality
# Screenshots, logs, or test output proving success
```

---

## BRANCHING STRATEGY

### Branch Types and Naming

**Feature Branches**: `feature/descriptive-task-name`
```bash
# Examples:
feature/fix-vpc-list-pagination
feature/add-error-handling-sync
feature/improve-connection-testing
```

**Bug Fix Branches**: `fix/specific-bug-description`
```bash
# Examples:
fix/sync-button-not-responding
fix/crd-attribution-incorrect
fix/test-connection-timeout
```

**Documentation Branches**: `docs/area-being-documented`
```bash
# Examples:
docs/api-endpoint-guide
docs/troubleshooting-update
docs/user-workflow-guide
```

### Branch Lifecycle

**1. Create**: Always from latest `develop`
**2. Work**: Commit frequently with good messages
**3. Test**: GUI tests must pass before completion
**4. Push**: Make changes available for review
**5. Merge**: Only after validation and approval
**6. Cleanup**: Delete branch after successful merge

---

## MERGE REQUIREMENTS

### Before Any Merge

**Validation Checklist**:
- [ ] All commits have descriptive messages
- [ ] GUI tests pass (71/71) 
- [ ] No merge conflicts
- [ ] Evidence of working functionality provided
- [ ] No uncommitted changes

**Merge Command**:
```bash
# Switch to target branch
git checkout develop

# Ensure latest changes
git pull origin develop

# Merge feature branch
git merge feature/your-branch-name

# Validate merge
./run_demo_tests.py

# If tests pass:
git push origin develop

# If tests fail:
git reset --hard HEAD~1  # Undo merge
# Fix issues and try again
```

---

## AGENT RESPONSIBILITIES

### Daily Git Practices

**Morning**:
- Pull latest changes: `git pull origin develop`
- Check current branch: `git branch`
- Review any conflicts or updates

**During Work**:
- Commit every 2 hours minimum
- Write clear commit messages
- Push changes regularly

**End of Work**:
- Commit all changes
- Run GUI tests
- Push to remote
- Update manager on progress

### Git Status Reporting

**In Progress Updates**:
```
Status: Working on feature/fix-sync-attribution
Commits: 3 commits pushed to remote
Last Commit: "fix: update CRD attribution logic with validation"
Tests: GUI tests passing (71/71)
```

**Completion Report**:
```
Complete: feature/fix-sync-attribution
Branch: Pushed to origin with 5 commits
Tests: GUI tests pass (71/71) 
Evidence: [Screenshot/output showing working functionality]
Ready for merge: Yes
```

---

## COMMON GIT SCENARIOS

### Starting New Work
```bash
git checkout develop
git pull origin develop
git checkout -b feature/my-new-task
# Begin work with first commit
```

### Saving Work in Progress
```bash
git add .
git commit -m "wip: partial implementation of sync fix

- Updated base classes
- TODO: Complete validation logic
- TODO: Add error handling"
git push origin feature/my-branch
```

### Handling Conflicts
```bash
git pull origin develop
# If conflicts:
# 1. Edit conflicted files
# 2. Remove conflict markers
# 3. Test functionality
./run_demo_tests.py
git add .
git commit -m "resolve: merge conflicts with develop"
```

### Emergency Fixes
```bash
git checkout main
git pull origin main
git checkout -b hotfix/critical-issue-name
# Make fix
git commit -m "hotfix: resolve critical issue"
./run_demo_tests.py
git push origin hotfix/critical-issue-name
# Immediate merge to main and develop
```

---

## VALIDATION AND ENFORCEMENT

### Manager Validation

**Every Agent Deliverable Must Show**:
- Git branch name and commit history
- Evidence of regular commits (not just one final commit)
- GUI test results (71/71 passing)
- Clear commit messages following standards

### Red Flags (Immediate Training Needed)

- Agent reports work complete without any commits
- Single commit with all changes ("final implementation")
- Commit messages like "update", "fix", "changes"
- Work done directly on develop/main branch
- GUI tests not run before claiming completion

### Success Indicators

- Regular commits throughout work period
- Clear, descriptive commit messages
- Clean git history with logical progression
- GUI tests consistently passing
- Evidence-based completion reporting

---

## TROUBLESHOOTING

### "I Forgot to Commit"
```bash
# Save current work
git add .
git commit -m "save: current work in progress"

# Create proper commits for logical chunks
git reset --soft HEAD~1  # Undo last commit, keep changes
# Make proper commits with clear messages
```

### "GUI Tests Failed After Merge"
```bash
# Immediately revert
git reset --hard HEAD~1

# Fix issues on branch
git checkout feature/your-branch
# Fix problems
./run_demo_tests.py  # Must pass
git commit -m "fix: resolve test failures"

# Try merge again
git checkout develop
git merge feature/your-branch
./run_demo_tests.py
```

### "Branch is Behind Develop"
```bash
git checkout feature/your-branch
git merge develop
# Resolve conflicts if any
./run_demo_tests.py
git commit -m "merge: sync with latest develop"
```

---

## SUCCESS METRICS

### Individual Agent Success
- **Commit Frequency**: Minimum every 2 hours of work
- **Message Quality**: Clear, descriptive, follows format
- **Test Compliance**: GUI tests pass before every merge
- **Branch Hygiene**: Clean history, logical progression

### Project Success  
- **Merge Safety**: No merges break GUI tests
- **Branch Management**: Short-lived feature branches
- **History Clarity**: Git log tells clear story of development
- **Risk Reduction**: No large, risky merges

---

## CRITICAL REMINDERS

**Git is Not Optional**:
- Every agent must commit regularly
- No work accepted without proper git practices
- GUI tests must pass before any merge
- Clean commit history is required

**Process Enforcement**:
- Managers validate git practices for every agent
- CEO may reject work with poor git hygiene
- Agents showing poor git practices need additional training

**Quality Focus**:
- Good git practices prevent lost work
- Clear history helps debugging and collaboration
- Regular commits enable better coordination
- Testing integration prevents breaking changes

---

**REMEMBER: Good git practices are not optional - they're essential for project success and team coordination!**