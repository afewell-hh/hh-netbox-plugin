# Agent Role Documentation System
**NetBox Hedgehog Plugin - Simplified Agile + GitHub Integration**

## Overview

This directory contains comprehensive role-specific documentation for agents working on the NetBox Hedgehog Plugin using our Simplified Agile + GitHub system. Each agent type has specific responsibilities, workflows, and success criteria designed to enable efficient collaboration and high-quality deliverables.

## 🎯 System Philosophy

**Single Source of Truth**: GitHub Issues drive all work  
**Clear Responsibilities**: Each agent type has focused, well-defined duties  
**Consistent Process**: Universal guidelines ensure smooth collaboration  
**Quality Focus**: Success measured by delivered value, not just completed tasks

---

## 📚 Documentation Structure

### **Universal Guidelines** (Start Here)
📁 **File**: `UNIVERSAL_GUIDELINES.md`  
**Who**: All agent types must read this first  
**Purpose**: Core processes that every agent follows  
**Key Topics**: GitHub Issue workflow, status updates, communication standards, quality requirements

### **Role-Specific Playbooks**

#### 🛠️ **Coder Agent Playbook**
📁 **File**: `CODER_PLAYBOOK.md`  
**Who**: Implementation specialists  
**Purpose**: Technical implementation workflow using Django/NetBox patterns  
**Key Topics**: Development workflow, NetBox plugin patterns, testing standards, GitHub integration

#### 📋 **Project Manager Agent Playbook**  
📁 **File**: `PROJECT_MANAGER_PLAYBOOK.md`  
**Who**: Sprint coordinators  
**Purpose**: Sprint management and team coordination  
**Key Topics**: Sprint planning, GitHub Issue creation, team coordination, progress tracking

#### 🏗️ **Architect Agent Playbook**
📁 **File**: `ARCHITECT_PLAYBOOK.md`  
**Who**: System design authorities  
**Purpose**: Architectural decisions and technical standards  
**Key Topics**: System design, Architecture Decision Records (ADRs), code quality standards

### **Quick Reference**
📁 **File**: `QUICK_REFERENCE.md`  
**Who**: All agents (bookmark this!)  
**Purpose**: Essential commands and checklists for each role  
**Key Topics**: Command references, templates, emergency procedures

---

## 🚀 Getting Started (New Agent Onboarding)

### Step 1: Understand Your Role (5 minutes)
```bash
# Quick role identification
echo "I am a [Coder/PM/Architect/Tester/Researcher/Reviewer] agent"
echo "My primary focus: [Implementation/Coordination/Design/Validation/Research/Quality]"
```

### Step 2: Read Universal Guidelines (15 minutes) 
📖 **Required Reading**: `UNIVERSAL_GUIDELINES.md`
- How to read GitHub Issues (user story format)
- Status update procedures
- Communication standards  
- Quality requirements

### Step 3: Study Your Role Playbook (30 minutes)
📖 **Role-Specific Guide**:
- **Coders**: Read `CODER_PLAYBOOK.md` 
- **Project Managers**: Read `PROJECT_MANAGER_PLAYBOOK.md`
- **Architects**: Read `ARCHITECT_PLAYBOOK.md`

### Step 4: Bookmark Quick Reference (2 minutes)
📖 **Daily Use**: `QUICK_REFERENCE.md`
- Essential commands for your role
- Templates and checklists
- Emergency procedures

### Step 5: Start Working (Immediate)
```bash
# View your assigned issues
gh issue list --assignee @me

# Or find issues for your role
gh issue list --label "role:coder" --state open        # Coder tasks
gh issue list --label "role:pm" --state open          # PM tasks  
gh issue list --label "role:architect" --state open   # Architecture tasks
```

---

## 🎭 Agent Role Definitions

### **Core Roles** (Always Needed)

#### 🛠️ **Coder Agent** 
- **Primary Focus**: Feature implementation
- **Key Skills**: Django, NetBox plugins, Python
- **Success Metric**: Clean, tested code that meets acceptance criteria
- **Typical Issues**: User stories requiring technical implementation

#### 📋 **Project Manager Agent**
- **Primary Focus**: Sprint coordination and team productivity  
- **Key Skills**: Agile methodology, GitHub project management
- **Success Metric**: Consistent delivery of valuable features
- **Typical Issues**: Sprint planning, team coordination, process improvement

#### 🏗️ **Architect Agent**
- **Primary Focus**: System design and technical decisions
- **Key Skills**: System architecture, documentation, technical leadership
- **Success Metric**: Clear architectural guidance enabling quality implementation
- **Typical Issues**: Design decisions, technical debt, standards definition

### **Supporting Roles** (As Needed)

#### 🧪 **Tester Agent**
- **Primary Focus**: Quality assurance and validation
- **Key Skills**: Manual testing, user experience, bug detection
- **Success Metric**: All acceptance criteria verified with evidence
- **Typical Issues**: Feature validation, regression testing, bug reproduction

#### 🔬 **Researcher Agent**
- **Primary Focus**: Investigation and requirements gathering
- **Key Skills**: Technical research, user needs analysis, feasibility studies
- **Success Metric**: Actionable recommendations with clear rationale
- **Typical Issues**: Technology evaluation, user research, competitive analysis

#### 👀 **Reviewer Agent**  
- **Primary Focus**: Code review and quality assurance
- **Key Skills**: Code quality assessment, standards compliance, mentoring
- **Success Metric**: High-quality code merged, consistent standards applied
- **Typical Issues**: PR reviews, code quality audits, standards documentation

---

## 🔄 Collaboration Patterns

### **Multi-Agent Workflows**

#### **Feature Implementation Flow**
```
1. PM Agent: Creates user story issue with acceptance criteria
2. Architect Agent: Reviews for design implications, provides guidance  
3. Coder Agent: Implements feature following architectural guidance
4. Tester Agent: Validates implementation against acceptance criteria
5. Reviewer Agent: Reviews code quality and standards compliance
6. PM Agent: Manages process, removes blockers, tracks progress
```

#### **Technical Decision Flow**
```
1. Any Agent: Identifies need for architectural decision
2. Architect Agent: Analyzes options, creates Architecture Decision Record
3. PM Agent: Facilitates stakeholder input and timeline considerations
4. Team: Reviews and provides feedback through GitHub Issue comments
5. Architect Agent: Finalizes decision, documents in ADR
6. Coder Agents: Implement according to architectural guidance
```

### **Communication Protocols**

#### **Status Updates** (All Agents)
- **Frequency**: Every 1-2 days for active work
- **Method**: GitHub Issue comments  
- **Format**: Use status update templates from Universal Guidelines

#### **Questions & Clarifications** (All Agents)
- **Timing**: Ask immediately when unclear (don't guess)
- **Method**: GitHub Issue comments with specific questions
- **Expected Response**: 1 business day for non-blocking questions

#### **Escalation** (All Agents)
- **Blockers**: Escalate within 4 hours
- **Technical Decisions**: Escalate to Architect Agent
- **Process Issues**: Escalate to PM Agent
- **Quality Concerns**: Escalate to Reviewer Agent

---

## 📊 Success Metrics & Quality Gates

### **Individual Agent Success**
- ✅ **Assigned work completed on time** with quality evidence
- ✅ **Proactive communication** of progress and blockers  
- ✅ **Process adherence** following role-specific guidelines
- ✅ **Collaboration effectiveness** enabling team success

### **Team Success Indicators**
- 🎯 **User stories deliver real value** (not just technical features)
- 🚀 **Regular feature releases** (weekly deployment cycles)
- 🔄 **Smooth process execution** (minimal coordination friction)
- 🧪 **High quality deliverables** (few bugs, positive user feedback)
- 📈 **Improving velocity** (better estimation and execution over time)

### **Quality Gates** (All Roles)
- **Requirements Understanding**: All acceptance criteria clearly understood before starting work
- **Progress Visibility**: Work progress visible to stakeholders through GitHub
- **Testing Evidence**: Manual testing completed with screenshots/logs/evidence
- **Integration Quality**: Changes don't break existing functionality  
- **Documentation Updates**: User-facing changes include documentation updates

---

## 🛠️ Tool Integration

### **Primary Tools**
- **GitHub Issues**: Single source of truth for all work
- **GitHub Projects**: Visual sprint tracking and progress monitoring
- **GitHub PRs**: Code review and integration workflow
- **GitHub CLI**: Command-line productivity for all GitHub operations

### **Essential GitHub CLI Commands**
```bash
# Issue management (all agents)
gh issue list --assignee @me                          # Your assigned work
gh issue view [number] --comments                     # Read full context  
gh issue comment [number] --body "Status update"      # Progress updates

# Project management (PM agents)  
gh milestone create --title "Sprint Name" --due-date "2024-08-22"
gh project item-add [project-id] --url [issue-url]

# Code workflow (Coder agents)
gh pr create --title "Fix #123: Feature name" --body-file template.md
gh pr list --review-requested @me                     # Review requests

# Quality assurance (all agents)
gh pr diff [number]                                    # Review changes
gh pr comment [number] --body "Review feedback"       # Provide feedback
```

### **NetBox Plugin Development Tools**
```bash
# Development environment (Coder agents)
sudo docker cp file.py netbox-docker-netbox-1:/opt/netbox/netbox/[path]
sudo docker restart netbox-docker-netbox-1
sudo docker logs netbox-docker-netbox-1 --tail 50

# Testing and validation (Tester agents)
curl -I http://localhost:8000/plugins/hedgehog/[endpoint]/
sudo docker exec -it netbox-docker-netbox-1 python manage.py shell
```

---

## 🔧 Troubleshooting & Support

### **Common Issues**

#### **"I can't find my assigned issues"**
```bash
gh issue list --assignee @me --state open
# If empty, check for role-based labels:
gh issue list --label "role:[your-role]" --state open
```

#### **"Requirements are unclear"**
1. Read the full GitHub Issue including all comments
2. Ask specific questions in Issue comments
3. Tag relevant agents (@pm-agent for requirements, @architect-agent for technical guidance)

#### **"I'm blocked and don't know who to ask"**
1. Comment on the GitHub Issue with blocker details
2. Use the BLOCKER template from Universal Guidelines
3. Tag @pm-agent for coordination help

#### **"My PR isn't getting reviewed"**
```bash
# Check reviewer assignments
gh pr view [number] --json reviewRequests

# Request specific reviews
gh pr edit [number] --add-reviewer @reviewer-agent
```

### **Process Improvement**
- **Weekly Retrospectives**: PM Agents facilitate process improvement discussions
- **Documentation Updates**: All agents can suggest improvements via GitHub Issues
- **Tool Enhancement**: Suggest new tools or workflow improvements through GitHub Discussions

---

## 📖 Additional Resources

### **NetBox Plugin Development**
- [NetBox Plugin Development Guide](../../project_management/DEVELOPMENT_GUIDE.md)
- [Task Tracking Status](../../project_management/TASK_TRACKING.md)
- [Project Overview](../../project_management/PROJECT_OVERVIEW.md)

### **GitHub Documentation**  
- [GitHub Issues Guide](https://docs.github.com/en/issues)
- [GitHub Projects Guide](https://docs.github.com/en/issues/planning-and-tracking-with-projects)
- [GitHub CLI Manual](https://cli.github.com/manual/)

### **Architecture Documentation**
- [System Architecture](../../architecture_specifications/00_current_architecture/system_overview.md)
- [Architecture Decision Records](../../architecture_specifications/01_architectural_decisions/decision_log.md)

---

## 🤝 Getting Help

### **Role-Specific Questions**
- **Implementation Questions**: Tag @coder-agent or @architect-agent  
- **Process Questions**: Tag @pm-agent
- **Quality Questions**: Tag @reviewer-agent or @tester-agent

### **Emergency Contact**
For critical blockers affecting production or sprint goals:
1. Comment on relevant GitHub Issue with "URGENT" prefix
2. Tag all relevant agent roles
3. Provide clear impact assessment and help needed

### **Feedback & Improvements**
This documentation system is designed to evolve. Suggest improvements by:
1. Creating GitHub Issues with label "documentation"
2. Proposing changes via Pull Requests
3. Discussing in GitHub Discussions for broader topics

---

**Remember**: The goal is efficient collaboration delivering high-quality software. These guidelines enable that outcome while maintaining flexibility for team learning and improvement.

---

*Last Updated: August 2024 | Version: 1.0 | Status: Active*