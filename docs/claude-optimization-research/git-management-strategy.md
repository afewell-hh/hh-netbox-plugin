# 🔀 Git Management Strategy for Multi-Agent Development

## **Adaptive Git Workflow Based on Task Classification**

### **🎯 Core Principle: Task Complexity Determines Git Strategy**

The git workflow adapts based on the automatic task classification (SIMPLE/MEDIUM/COMPLEX) from `.claude/helpers/task-classifier.py`.

---

## **📊 Git Strategy Matrix**

### **🟢 SIMPLE Tasks (Direct Commit Pattern)**

**Scope**: Single file edits, documentation updates, configuration changes

```bash
# Git workflow for SIMPLE tasks
git status                                    # Baseline check
git add <specific-files>                      # Stage only changed files
git commit -m "fix: update configuration parameter"  # Conventional commit
make deploy-dev                               # Validate deployment
git push                                      # Push to current branch
```

**Branch Strategy**: 
- Work on current feature branch
- No new branches needed
- Direct commits with descriptive messages

**Commit Frequency**: After each logical change (1-3 files)

---

### **🟡 MEDIUM Tasks (Feature Branch Pattern)**

**Scope**: Multi-file changes, feature additions, bug fixes

```bash
# Git workflow for MEDIUM tasks
ISSUE_NUMBER=$(echo "$TASK" | grep -oP 'issue[# ]*\K\d+' || echo "misc")
BRANCH_NAME="feature/issue-${ISSUE_NUMBER}-$(echo "$TASK" | head -c 30 | tr ' ' '-' | tr -cd '[:alnum:]-')"

git checkout -b "$BRANCH_NAME"               # Create feature branch
git add -A                                    # Stage all changes
git commit -m "feat: implement $TASK_DESCRIPTION"
make deploy-dev                               # Validate in container
git push -u origin "$BRANCH_NAME"            # Push feature branch
gh pr create --title "feat: $TASK" --body "Implements Issue #$ISSUE_NUMBER"
```

**Branch Strategy**:
- Create feature branches from main/develop
- One branch per medium task
- PR workflow for integration

**Commit Frequency**: After each component completion (5-10 files)

---

### **🔴 COMPLEX Tasks (Hierarchical Branch Pattern)**

**Scope**: Architecture changes, major features, system refactoring

```bash
# Git workflow for COMPLEX tasks
EPIC_BRANCH="epic/issue-${ISSUE_NUMBER}-$(echo "$EPIC_NAME" | tr ' ' '-')"
git checkout -b "$EPIC_BRANCH"               # Create epic branch

# For each sub-task
SUB_BRANCH="${EPIC_BRANCH}/component-${COMPONENT_NAME}"
git checkout -b "$SUB_BRANCH"                # Create sub-branch
git commit -m "feat(${COMPONENT}): implement core logic"
git push -u origin "$SUB_BRANCH"            

# Create PR for review
gh pr create --base "$EPIC_BRANCH" --title "feat(${COMPONENT}): $DESCRIPTION"

# After all sub-tasks complete
git checkout "$EPIC_BRANCH"
git merge --no-ff "$SUB_BRANCH"              # Preserve history
gh pr create --base main --title "epic: $EPIC_NAME"
```

**Branch Strategy**:
- Epic branches for major features
- Sub-branches for components
- Hierarchical PR reviews

**Commit Frequency**: Atomic commits for each logical unit

---

## **🤖 Agent-Specific Git Responsibilities**

### **Researcher Agent**
```yaml
git_permissions: read-only
responsibilities:
  - Analyze existing code
  - Document findings
  - No commits required
```

### **Coder Agent**
```yaml
git_permissions: write
responsibilities:
  - Create feature branches
  - Commit with conventional messages
  - Push changes for review
commit_pattern: |
  type(scope): description
  
  Types: feat, fix, docs, style, refactor, test, chore
  Scope: component affected
  Description: imperative mood, present tense
```

### **Coordinator Agent**
```yaml
git_permissions: admin
responsibilities:
  - Create epic branches
  - Manage PR workflow
  - Coordinate merges
  - Resolve conflicts
merge_strategy:
  simple: fast-forward
  medium: squash-merge
  complex: merge-commit
```

### **Reviewer Agent**
```yaml
git_permissions: read + comment
responsibilities:
  - PR code review
  - Suggest changes
  - Approve/request changes
  - No direct commits
```

---

## **🔄 Automated Git Workflow Integration**

### **Pre-Commit Validation**
```python
# .claude/helpers/git-pre-commit.py
def validate_commit():
    """Validate before allowing commit."""
    checks = [
        ("make deploy-dev", "Deployment validation"),
        ("git diff --check", "Whitespace errors"),
        ("grep -r 'TODO\\|FIXME'", "Unresolved TODOs"),
        ("python -m pytest", "Test suite passes")
    ]
    
    for cmd, description in checks:
        if not run_command(cmd):
            raise CommitError(f"Failed: {description}")
```

### **Branch Protection Rules**
```yaml
main:
  protection:
    - require_pr_reviews: 1
    - dismiss_stale_reviews: true
    - require_status_checks: ["deploy-dev", "tests"]
    - enforce_admins: false
    - restrict_push: ["coordinator-agent"]

feature/*:
  protection:
    - require_status_checks: ["deploy-dev"]
    - allow_force_push: false
```

---

## **📝 Conventional Commit Message Format**

### **Structure**
```
<type>(<scope>): <subject>

<body>

<footer>
```

### **Types**
- **feat**: New feature
- **fix**: Bug fix
- **docs**: Documentation only
- **style**: Formatting, missing semi-colons, etc
- **refactor**: Code change that neither fixes a bug nor adds a feature
- **test**: Adding missing tests
- **chore**: Changes to build process or auxiliary tools

### **Examples**
```bash
# SIMPLE task
git commit -m "docs: update README installation instructions"

# MEDIUM task
git commit -m "feat(sync): add bidirectional GitOps synchronization

Implements automatic sync between NetBox and Kubernetes
- Added sync orchestrator
- Integrated with GitOps workflow
- Added error recovery

Closes #50"

# COMPLEX task
git commit -m "refactor(architecture): implement Enhanced Hive Orchestration

BREAKING CHANGE: New orchestration pattern requires migration

Major architectural changes:
- Implemented 6-phase validation cascade
- Added fraud detection framework
- Integrated neural pattern training
- Enhanced agent coordination protocols

Migration guide: docs/migration/v2.md
Performance impact: 2.8-4.4x improvement

Closes #50, #51, #52"
```

---

## **🚨 Conflict Resolution Protocol**

### **Automatic Resolution (SIMPLE conflicts)**
```bash
# For simple conflicts in documentation/configs
git fetch origin
git rebase origin/main
# Auto-resolve with theirs for docs
git checkout --theirs README.md CHANGELOG.md
git add .
git rebase --continue
```

### **Guided Resolution (MEDIUM conflicts)**
```bash
# For code conflicts requiring logic preservation
git fetch origin
git merge origin/main --no-commit
# Analyze conflicts
git diff --name-only --diff-filter=U | while read file; do
    echo "Conflict in: $file"
    # Attempt smart merge
    git checkout --ours "$file"
    make deploy-dev  # Test our version
    if [ $? -ne 0 ]; then
        git checkout --theirs "$file"
        make deploy-dev  # Test their version
    fi
done
```

### **Escalation (COMPLEX conflicts)**
```bash
# For architectural conflicts requiring human intervention
git status > /tmp/conflict_report.txt
git diff >> /tmp/conflict_report.txt
echo "🚨 HUMAN INTERVENTION REQUIRED" | tee -a /tmp/conflict_report.txt
echo "Conflict involves architectural changes that require manual review"
# Create issue for human review
gh issue create --title "Merge conflict requires review" \
                --body "$(cat /tmp/conflict_report.txt)"
```

---

## **🔐 Git Security Rules**

### **Forbidden Operations**
```bash
# NEVER allow these operations
git push --force main              # ❌ FORBIDDEN
git reset --hard origin/main       # ❌ FORBIDDEN without backup
git clean -fdx                     # ❌ FORBIDDEN without confirmation
git commit --amend                 # ❌ FORBIDDEN on pushed commits
```

### **Required Validations**
```bash
# ALWAYS perform before push
make deploy-dev                    # ✅ REQUIRED
git diff origin/main --stat        # ✅ REQUIRED (review scope)
git log --oneline -5              # ✅ REQUIRED (verify commits)
```

---

## **📊 Branch Lifecycle Management**

### **Branch Creation Rules**
```python
def should_create_branch(task_classification, current_branch):
    """Determine if new branch needed."""
    if task_classification == "SIMPLE":
        return False  # Use current branch
    
    if task_classification == "MEDIUM":
        if current_branch == "main":
            return True  # Create feature branch
        return False  # Use current feature branch
    
    if task_classification == "COMPLEX":
        return True  # Always create epic branch
```

### **Branch Cleanup Policy**
```bash
# Automated cleanup after merge
gh pr list --state merged --json number,headRefName | \
  jq -r '.[] | .headRefName' | \
  xargs -I {} git push origin --delete {}

# Archive old branches
git for-each-ref --format='%(refname:short) %(committerdate)' refs/remotes/origin | \
  awk '$2 < "'$(date -d '30 days ago' '+%Y-%m-%d')'" {print $1}' | \
  sed 's/origin\///' > /tmp/old_branches.txt
```

---

## **🎯 Integration with Enhanced Hive Orchestration**

### **Task-to-Git Mapping**
```yaml
task_classification:
  SIMPLE:
    branch_strategy: current_branch
    commit_frequency: immediate
    review_required: false
    merge_strategy: fast_forward
    
  MEDIUM:
    branch_strategy: feature_branch
    commit_frequency: component_complete
    review_required: true
    merge_strategy: squash_merge
    
  COMPLEX:
    branch_strategy: epic_hierarchical
    commit_frequency: atomic_changes
    review_required: multi_stage
    merge_strategy: merge_commit
```

### **Validation Checkpoints**
```bash
# Integrated with existing validation checkpoints
CHECKPOINT_1="git status && git diff"
CHECKPOINT_2="make deploy-dev && git add -A"
CHECKPOINT_3="git commit && git push && gh pr create"
```

---

## **📈 Success Metrics**

### **Git Health Indicators**
- **Commit frequency**: 1-5 commits per task (optimal)
- **Branch lifetime**: <7 days for feature branches
- **Conflict rate**: <5% of merges require intervention
- **PR review time**: <4 hours for SIMPLE/MEDIUM
- **Deploy validation**: 100% commits pass `make deploy-dev`

### **Anti-Patterns to Detect**
- ❌ Commits without deploy validation
- ❌ Force pushes to shared branches
- ❌ Commits with "WIP" or "temp" messages
- ❌ Branches older than 30 days
- ❌ Direct commits to main branch

---

## **🚀 Implementation Checklist**

- [ ] Add git strategy to task classifier output
- [ ] Update agent configurations with git responsibilities
- [ ] Create git-pre-commit.py helper script
- [ ] Configure branch protection rules
- [ ] Document conventional commit format
- [ ] Train agents on conflict resolution
- [ ] Implement automated branch cleanup
- [ ] Add git health monitoring
- [ ] Create escalation procedures
- [ ] Test with parallel agent scenarios

---

*This git management strategy ensures code quality, prevents conflicts, and maintains a clean repository while enabling efficient multi-agent development.*