# Agent Role Quick Reference Cards
**NetBox Hedgehog Plugin - Simplified Agile + GitHub System**

---

## 🛠️ Coder Agent - Quick Reference

### **Purpose**: Implement features from GitHub Issues using Django/NetBox patterns

#### **Essential Commands**
```bash
# Start work
git checkout -b issue-[number]-[description]
gh issue comment [number] --body "Starting implementation - [brief plan]"

# Test changes  
sudo docker cp file.py netbox-docker-netbox-1:/opt/netbox/netbox/[path]
sudo docker restart netbox-docker-netbox-1  # if needed
curl -I http://localhost:8000/plugins/hedgehog/[endpoint]/

# Submit work
gh pr create --title "Fix #[number]: [summary]" --body-file pr-template.md
```

#### **Implementation Checklist** 
- [ ] Read issue acceptance criteria thoroughly
- [ ] Follow existing NetBox plugin patterns (models → forms → views → templates)
- [ ] Test all acceptance criteria + error conditions  
- [ ] Provide screenshots/evidence of working functionality
- [ ] Update GitHub Issue with progress regularly

#### **NetBox Plugin Pattern**
```python
# Standard structure to follow
models/[feature].py → forms/[feature].py → views/[feature].py → templates/[feature]_*.html → urls.py
```

#### **When to Ask for Help**
- Requirements unclear or conflicting
- Multiple technical approaches possible
- Stuck on implementation for >4 hours
- Breaking existing functionality

---

## 📋 Project Manager Agent - Quick Reference

### **Purpose**: Orchestrate sprints, manage GitHub Issues, ensure team productivity

#### **Essential Commands**
```bash
# Sprint planning
gh milestone create --title "Sprint $(date +%Y-%m-%d)" --due-date "$(date -d '+14 days' -Iseconds)"
gh issue edit [number] --add-label "effort/medium" --milestone "Sprint-Name"

# Progress tracking
gh issue list --milestone "current-sprint" --state open
gh project item-list [project-id]

# Team coordination
gh issue list --label "blocked" --state open
gh pr list --review-requested @me --state open
```

#### **User Story Template**
```markdown
Title: [User Story] As a [user type], I want [capability] so that [benefit]

## Acceptance Criteria
- [ ] Specific testable requirement 1
- [ ] Specific testable requirement 2

## Definition of Done
- [ ] Code implemented and tested
- [ ] PR merged and deployed
```

#### **Daily Tracking**
- Review sprint progress (daily)
- Update milestone completion rates
- Identify and resolve blockers immediately  
- Facilitate team communication through GitHub

#### **Sprint Success Metrics**
- 80%+ sprint goal completion
- Predictable velocity over time
- Minimal scope changes mid-sprint
- Team satisfaction in retrospectives

---

## 🏗️ Architect Agent - Quick Reference

### **Purpose**: Design system architecture and document technical decisions

#### **Essential Commands**
```bash
# Architecture analysis
find . -name "*.py" -path "*/models/*" | head -5
grep -r "class.*ViewSet" netbox_hedgehog/views/

# Documentation
ls -la netbox_hedgehog/docs/architecture/ 2>/dev/null
find . -name "ADR-*.md"
```

#### **Architecture Decision Record (ADR) Template**
```markdown
# ADR-XXX: [Title]
## Status: [Accepted/Proposed/Deprecated]
## Context: [Problem we're solving]
## Decision: [What we decided]
## Alternatives Considered: [Other options]
## Consequences: [Positive/Negative impacts]
```

#### **Review Responsibilities**  
- Analyze requirements for architectural impact
- Design data models and API contracts
- Create system diagrams (C4 model preferred)
- Review complex PRs for architectural compliance
- Document major technical decisions in ADRs

#### **NetBox Plugin Architecture Standards**
```python
# Preferred patterns
BaseCRD → Domain Models → Forms → Views → APIs
Django ModelViewSet for APIs
NetBox ObjectView patterns for UI
Celery for background tasks
```

#### **Quality Gates**
- New components follow NetBox plugin patterns  
- All major decisions documented
- API designs are RESTful and consistent
- Performance/security requirements met

---

## 👥 Universal Guidelines - All Agents

### **Core Process**
1. **Read GitHub Issue** (user story format with acceptance criteria)
2. **Update Status** (comment with progress/blockers regularly)
3. **Ask Questions** (when requirements unclear)
4. **Handle Blockers** (escalate immediately)

### **Communication Standards**
```markdown
## Status Update Template
**Current State**: [In Progress/Blocked/Testing/Complete]
**Progress**: [What you've accomplished]
**Next Steps**: [What you're doing next] 
**Blockers**: [Any impediments]
**ETA**: [Realistic completion estimate]
```

### **GitHub Workflow**
```bash
# Issue management
gh issue list --assignee @me
gh issue comment [number] --body "Status update"

# Branch workflow  
git checkout -b issue-[number]-[description]
git commit -m "feat: implement [feature] - addresses #[number]"

# PR process
gh pr create --title "Fix #[number]: [summary]"
```

### **Quality Standards**
- All acceptance criteria must be met
- Manual testing with evidence (screenshots)
- Code follows project patterns/conventions
- Documentation updated for user-facing changes
- No regressions in existing functionality

### **When to Escalate**
- **Critical bugs** (production impact)
- **Blockers** lasting >1 business day
- **Scope changes** affecting sprint goals
- **Technical decisions** with broad impact

---

## 🔧 Additional Agent Types - Quick Reference

### **Tester Agent**
- **Purpose**: Validate completed work against acceptance criteria
- **Key Activities**: Manual testing, regression testing, evidence collection
- **Success Metrics**: All acceptance criteria verified with evidence

### **Researcher Agent**  
- **Purpose**: Investigate solutions and gather requirements
- **Key Activities**: Technology research, user needs analysis, feasibility studies
- **Success Metrics**: Actionable recommendations with clear rationale

### **Reviewer Agent**
- **Purpose**: Code review and quality assurance  
- **Key Activities**: PR reviews, code quality checks, standards compliance
- **Success Metrics**: High-quality code merged, consistent standards applied

---

## 🆘 Emergency Procedures

### **Critical Bug (Production Down)**
1. Comment on issue: "CRITICAL BUG - Production Impact"
2. Create hotfix branch: `hotfix-[issue]-[description]` 
3. Minimal fix only (no refactoring)
4. Request immediate review and fast-track merge
5. Follow up with root cause analysis issue

### **Missed Deadline**
1. Update issue 24 hours before deadline if at risk
2. Provide clear status: what's complete vs incomplete
3. Suggest scope reduction or timeline adjustment
4. Get explicit approval before extending deadline

### **Blocked Work**
```markdown
## BLOCKER - [Agent Role]
**Issue**: [What's preventing progress]
**Impact**: [Effect on timeline/deliverables]  
**Attempted Solutions**: [What you've tried]
**Help Needed**: [Specific assistance required]
```

---

## 📊 Success Indicators

### **Individual Agent Success**
- ✅ Assigned issues completed on time
- ✅ PRs approved without major revision
- ✅ Proactive communication of progress/blockers
- ✅ Work integrates smoothly with team efforts

### **Project Success**
- 🎯 User stories deliver real value (not just features)
- 🚀 Regular feature releases (weekly cycles)
- 🔄 Smooth process with minimal coordination overhead  
- 🧪 High quality delivery (few bugs, positive user feedback)

### **Process Health**
- **Communication**: All work visible through GitHub
- **Velocity**: Predictable delivery over time
- **Quality**: Consistent standards across all agents
- **Collaboration**: Effective cross-functional teamwork

**Remember**: These are guidelines to enable smooth collaboration. When in doubt, over-communicate and follow the Universal Guidelines.