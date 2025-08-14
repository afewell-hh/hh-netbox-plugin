# 🔀 Git Integration Enhancement for .claude Files

## **Seamless Git Management Integration**

This document shows how to integrate git management into our existing enhanced .claude files for cohesive workflow automation.

---

## **📝 Enhanced Task Classifier with Git Strategy**

### **Addition to `/helpers/task-classifier.py`**

```python
def get_git_strategy(classification: str) -> Dict[str, Any]:
    """
    Determine git strategy based on task classification.
    
    Returns git workflow parameters for the classified task.
    """
    strategies = {
        "SIMPLE": {
            "branch_required": False,
            "branch_pattern": None,
            "commit_frequency": "immediate",
            "commit_prefix": "fix|docs|style|chore",
            "pr_required": False,
            "merge_strategy": "fast-forward",
            "validation_level": "basic",
            "deploy_required": True,
            "example_workflow": """
                git add <files>
                git commit -m "fix: correct typo in configuration"
                make deploy-dev
                git push
            """
        },
        "MEDIUM": {
            "branch_required": True,
            "branch_pattern": "feature/issue-{number}-{description}",
            "commit_frequency": "component_complete",
            "commit_prefix": "feat|fix|refactor|test",
            "pr_required": True,
            "merge_strategy": "squash-merge",
            "validation_level": "comprehensive",
            "deploy_required": True,
            "example_workflow": """
                git checkout -b feature/issue-50-enhanced-sync
                git add -A
                git commit -m "feat(sync): implement bidirectional synchronization"
                make deploy-dev
                git push -u origin feature/issue-50-enhanced-sync
                gh pr create --title "feat: Enhanced synchronization" --body "Closes #50"
            """
        },
        "COMPLEX": {
            "branch_required": True,
            "branch_pattern": "epic/issue-{number}-{epic_name}",
            "commit_frequency": "atomic",
            "commit_prefix": "feat|refactor|perf|build|ci",
            "pr_required": True,
            "merge_strategy": "merge-commit",
            "validation_level": "exhaustive",
            "deploy_required": True,
            "sub_branches": True,
            "example_workflow": """
                git checkout -b epic/issue-50-hive-orchestration
                git checkout -b epic/issue-50-hive-orchestration/validation-framework
                git commit -m "feat(validation): implement 5-phase validation cascade"
                make deploy-dev
                gh pr create --base epic/issue-50-hive-orchestration
                # After all sub-features complete:
                gh pr create --base main --title "epic: Enhanced Hive Orchestration"
            """
        }
    }
    
    return strategies.get(classification, strategies["SIMPLE"])

# Enhanced output in main():
if __name__ == "__main__":
    # ... existing code ...
    result = classifier.classify_task(task_description)
    git_strategy = get_git_strategy(result['classification'])
    
    # Output git strategy along with classification
    print(f"GIT_STRATEGY: {git_strategy['branch_pattern'] or 'current_branch'}")
    print(f"COMMIT_PREFIX: {git_strategy['commit_prefix']}")
    print(f"PR_REQUIRED: {git_strategy['pr_required']}")
```

---

## **🚨 Enhanced Hive Queen Process with Git Integration**

### **Addition to `/agents/hive-queen-process.md`**

```markdown
## **🔀 MANDATORY GIT WORKFLOW PROTOCOL**

### **CHECKPOINT 0: Git Initialization**
**BEFORE starting ANY task:**

```bash
# Ensure clean working directory
git status
if [ -n "$(git status --porcelain)" ]; then
    echo "⚠️ WARNING: Uncommitted changes detected"
    git stash push -m "Auto-stash before task $(date +%s)"
fi

# Fetch latest changes
git fetch origin
git pull --rebase origin main
```

### **CHECKPOINT 1.5: Branch Management**
**After task classification:**

```bash
CLASSIFICATION=$(python3 .claude/helpers/task-classifier.py "$TASK")

case "$CLASSIFICATION" in
  SIMPLE)
    echo "📝 Working on current branch: $(git branch --show-current)"
    ;;
  MEDIUM)
    ISSUE_NUM=$(echo "$TASK" | grep -oP '\d+')
    BRANCH="feature/issue-${ISSUE_NUM}-$(date +%s)"
    git checkout -b "$BRANCH"
    echo "🔀 Created feature branch: $BRANCH"
    ;;
  COMPLEX)
    ISSUE_NUM=$(echo "$TASK" | grep -oP '\d+')
    EPIC_BRANCH="epic/issue-${ISSUE_NUM}-$(date +%s)"
    git checkout -b "$EPIC_BRANCH"
    echo "🎯 Created epic branch: $EPIC_BRANCH"
    ;;
esac
```

### **CHECKPOINT 4: Git Validation**
**AFTER task completion:**

```bash
# Mandatory git workflow completion
git add -A
git status

# Generate conventional commit message based on changes
COMMIT_MSG=$(python3 .claude/helpers/generate-commit-message.py)

# Validate deployment before commit
make deploy-dev || {
    echo "❌ Deployment validation failed - cannot commit"
    git reset
    exit 1
}

# Commit with validation evidence
git commit -m "$COMMIT_MSG" \
           -m "Deployment validated: $(date)" \
           -m "Task classification: $CLASSIFICATION"

# Push and create PR if needed
if [ "$CLASSIFICATION" != "SIMPLE" ]; then
    git push -u origin "$(git branch --show-current)"
    gh pr create --fill
fi
```

### **🚫 GIT VIOLATIONS (IMMEDIATE REJECTION)**

1. **Commits without deployment validation**
2. **Direct pushes to main branch**
3. **Force pushes to shared branches**
4. **Commits with generic messages** ("fix", "update", "change")
5. **Uncommitted changes after task completion**
```

---

## **🤖 Agent-Specific Git Instructions**

### **Enhanced `agents/coder.md`**

```yaml
git_workflow:
  initialize:
    - command: "git status"
      validate: "working directory clean"
    - command: "git fetch origin"
      validate: "up to date with remote"
  
  during_work:
    simple_task:
      - "git add <specific-files>"
      - "git diff --staged"  # Review changes
      - "git commit -m 'type: description'"
    
    medium_task:
      - "git checkout -b feature/issue-NUM-description"
      - "git add -A"
      - "git commit -m 'feat(scope): implement feature'"
      - "git push -u origin BRANCH"
    
    complex_task:
      - "git checkout -b epic/issue-NUM-name"
      - "git checkout -b epic/issue-NUM-name/component"
      - "git commit --verbose"  # Detailed commit messages
      - "git push -u origin BRANCH"
  
  completion:
    validation:
      - "make deploy-dev"  # Required before push
      - "git log --oneline -5"  # Verify commit history
      - "git diff origin/main --stat"  # Review scope
    
    pr_creation:
      - "gh pr create --title 'type: description' --body 'Closes #NUM'"
      - "gh pr view --web"  # Open for review
```

### **Enhanced `agents/coordinator.md`**

```yaml
git_orchestration:
  branch_management:
    - Monitor active branches across agents
    - Coordinate epic branch hierarchies
    - Prevent conflicting feature branches
    - Schedule merges to avoid conflicts
  
  merge_coordination:
    simple_tasks:
      strategy: "fast-forward"
      validation: "make deploy-dev"
      
    medium_tasks:
      strategy: "squash-merge"
      validation: "PR review + deploy-dev"
      
    complex_tasks:
      strategy: "merge-commit"
      validation: "Multi-stage review + integration tests"
  
  conflict_resolution:
    detection: "git diff --check && git merge --dry-run"
    automatic: "Simple conflicts in docs/configs"
    escalation: "Complex conflicts in core logic"
    
  health_monitoring:
    - Branch age (warn >7 days, critical >14 days)
    - Uncommitted changes detection
    - Divergence from main branch
    - PR queue length
```

---

## **📊 Git Metrics Integration**

### **Addition to Performance Monitoring**

```python
# /helpers/git-health-monitor.py
def monitor_git_health():
    """Monitor git repository health metrics."""
    metrics = {
        "uncommitted_changes": count_uncommitted(),
        "stale_branches": find_stale_branches(days=7),
        "pending_prs": count_pending_prs(),
        "conflict_rate": calculate_conflict_rate(),
        "commit_frequency": analyze_commit_frequency(),
        "branch_lifetime": calculate_avg_branch_lifetime(),
        "deploy_validation_rate": check_deploy_validation_rate()
    }
    
    # Alert on issues
    if metrics["uncommitted_changes"] > 0:
        alert("⚠️ Uncommitted changes detected")
    
    if metrics["stale_branches"] > 5:
        alert("🔀 Multiple stale branches need cleanup")
    
    if metrics["deploy_validation_rate"] < 1.0:
        alert("❌ Commits without deployment validation detected")
    
    return metrics
```

---

## **🔄 Automated Git Workflow Helper**

### **New: `/helpers/git-workflow-manager.py`**

```python
#!/usr/bin/env python3
"""
Automated Git Workflow Manager
Integrates with task classification for seamless git operations
"""

import subprocess
import re
from datetime import datetime
from typing import Optional, Dict, Any

class GitWorkflowManager:
    """Manages git workflow based on task classification."""
    
    def __init__(self, task_description: str):
        self.task = task_description
        self.classification = self._classify_task()
        self.issue_number = self._extract_issue_number()
        self.branch_name = None
        
    def _classify_task(self) -> str:
        """Run task classifier."""
        result = subprocess.run(
            ["python3", ".claude/helpers/task-classifier.py", self.task],
            capture_output=True, text=True
        )
        # Parse classification from output
        return result.stdout.split("CLASSIFICATION: ")[1].split("\n")[0]
    
    def _extract_issue_number(self) -> Optional[int]:
        """Extract issue number from task description."""
        match = re.search(r'#?(\d+)', self.task)
        return int(match.group(1)) if match else None
    
    def setup_branch(self) -> str:
        """Create appropriate branch based on classification."""
        if self.classification == "SIMPLE":
            # Stay on current branch
            current = subprocess.run(
                ["git", "branch", "--show-current"],
                capture_output=True, text=True
            ).stdout.strip()
            self.branch_name = current
            return f"Continuing on branch: {current}"
        
        elif self.classification == "MEDIUM":
            # Create feature branch
            desc = re.sub(r'[^a-z0-9-]', '-', self.task.lower())[:30]
            self.branch_name = f"feature/issue-{self.issue_number}-{desc}"
            subprocess.run(["git", "checkout", "-b", self.branch_name])
            return f"Created feature branch: {self.branch_name}"
        
        elif self.classification == "COMPLEX":
            # Create epic branch
            desc = re.sub(r'[^a-z0-9-]', '-', self.task.lower())[:20]
            self.branch_name = f"epic/issue-{self.issue_number}-{desc}"
            subprocess.run(["git", "checkout", "-b", self.branch_name])
            return f"Created epic branch: {self.branch_name}"
    
    def validate_and_commit(self, message: str) -> bool:
        """Validate changes and create commit."""
        # Run deployment validation
        deploy_result = subprocess.run(
            ["make", "deploy-dev"],
            capture_output=True
        )
        
        if deploy_result.returncode != 0:
            print("❌ Deployment validation failed")
            return False
        
        # Stage and commit
        subprocess.run(["git", "add", "-A"])
        subprocess.run(["git", "commit", "-m", message])
        return True
    
    def create_pr_if_needed(self) -> Optional[str]:
        """Create PR for medium/complex tasks."""
        if self.classification == "SIMPLE":
            return None
        
        # Push branch
        subprocess.run(["git", "push", "-u", "origin", self.branch_name])
        
        # Create PR
        title = f"{'feat' if self.classification == 'MEDIUM' else 'epic'}: {self.task[:50]}"
        body = f"Closes #{self.issue_number}" if self.issue_number else "Automated PR"
        
        result = subprocess.run(
            ["gh", "pr", "create", "--title", title, "--body", body],
            capture_output=True, text=True
        )
        
        return result.stdout

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: git-workflow-manager.py '<task description>'")
        sys.exit(1)
    
    manager = GitWorkflowManager(sys.argv[1])
    print(manager.setup_branch())
    
    # Example commit workflow
    if manager.validate_and_commit("feat: implement task"):
        pr_url = manager.create_pr_if_needed()
        if pr_url:
            print(f"PR created: {pr_url}")
```

---

## **📋 Integration Checklist**

### **Immediate Implementation**
- [ ] Update task-classifier.py with git strategy output
- [ ] Add git workflow to hive-queen-process.md
- [ ] Enhance coder.md with git instructions
- [ ] Create git-workflow-manager.py helper

### **Phase 2 Enhancements**
- [ ] Add coordinator.md git orchestration rules
- [ ] Implement git-health-monitor.py
- [ ] Create automated branch cleanup
- [ ] Add conflict resolution procedures

### **Validation Steps**
- [ ] Test SIMPLE task git workflow
- [ ] Test MEDIUM task with feature branch
- [ ] Test COMPLEX task with epic branches
- [ ] Verify PR creation automation
- [ ] Validate deployment checks before commits

---

*This integration ensures git management is seamlessly woven into the existing Enhanced Hive Orchestration workflow, preventing the commit chaos while maintaining development velocity.*