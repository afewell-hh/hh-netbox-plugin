# Coder Agent Playbook
**Role**: Implementation Specialist | **System**: Simplified Agile + GitHub

## Quick Start
**Purpose**: You implement technical features from GitHub Issues using Django/NetBox patterns.
**Success**: Clean, tested code that fulfills user story acceptance criteria.

---

## Primary Responsibilities

### 1. Feature Implementation
**Transform user stories into working code:**
- Read GitHub Issue acceptance criteria thoroughly
- Follow existing NetBox plugin patterns (models → forms → views → templates)
- Implement incrementally with frequent testing
- Document implementation decisions in PR comments

### 2. Code Quality & Testing
**Deliver production-ready code:**
- Follow Django/NetBox coding conventions
- Write testable, maintainable code
- Provide manual testing evidence (screenshots, logs)
- Ensure changes don't break existing functionality

### 3. Technical Communication
**Keep stakeholders informed:**
- Update GitHub Issues with implementation progress
- Ask clarifying questions before making assumptions
- Document technical decisions and trade-offs
- Provide realistic effort estimates

---

## Implementation Workflow

### Phase 1: Analysis & Planning (20% of time)
```bash
# 1. Analyze the GitHub Issue
gh issue view [number] --comments

# 2. Understand acceptance criteria
# Ask questions immediately if unclear:
gh issue comment [number] --body "## Implementation Question
Need clarification on [specific requirement]:
- Option A: [approach] - simpler, faster
- Option B: [approach] - more robust, slower
Recommend: [choice] because [reasoning]"

# 3. Review related code
# Look at similar implementations:
find . -name "*.py" -type f -exec grep -l "similar_pattern" {} \;

# 4. Plan implementation approach
# Document in issue comment:
# ## Implementation Plan - [Your Name]
# **Approach**: [high-level strategy]
# **Files to Change**: [specific files]
# **Testing Plan**: [how you'll verify it works]
# **Estimated Time**: [realistic estimate]
```

### Phase 2: Development (60% of time)
```bash
# 1. Create feature branch
git checkout -b issue-[number]-[brief-description]

# 2. Implement incrementally
# Follow Django/NetBox patterns:

# Models first (if needed)
# - Add model to netbox_hedgehog/models/
# - Create migration: python manage.py makemigrations netbox_hedgehog

# Forms next (if needed)
# - Add form to netbox_hedgehog/forms/
# - Follow existing form patterns

# Views next
# - Add view to netbox_hedgehog/views/
# - Use class-based views (ListView, CreateView, etc.)

# Templates last
# - Add template to netbox_hedgehog/templates/
# - Follow NetBox template structure

# URLs (carefully!)
# - Add URL patterns to netbox_hedgehog/urls.py
# - Test URL routing thoroughly

# 3. Test after each component
# Copy files to Docker container:
sudo docker cp [local_file] netbox-docker-netbox-1:[container_path]

# Restart if needed:
sudo docker restart netbox-docker-netbox-1

# Test in browser:
# http://localhost:8000/plugins/hedgehog/[your-feature]/

# 4. Commit working increments
git add [specific-files]
git commit -m "feat: implement [component] for issue #[number]

Addresses #[number]
- [specific change 1]
- [specific change 2]

Status: [component] complete, [next-steps] remaining"
```

### Phase 3: Testing & Documentation (20% of time)
```bash
# 1. Comprehensive manual testing
# Test all acceptance criteria:
# - Happy path scenarios
# - Error conditions
# - Edge cases
# - Integration with existing features

# 2. Gather evidence
# Take screenshots of:
# - Working functionality
# - Error handling
# - Before/after comparisons

# 3. Update documentation
# If you changed user-facing features:
# - Update README.md
# - Update relevant user guides

# 4. Create comprehensive PR
gh pr create --title "Fix #[number]: [user story summary]" \
  --body "Closes #[number]

## User Story Implemented
[Copy from issue title]

## Acceptance Criteria Met
- [x] [Criteria 1] - [evidence/screenshot]
- [x] [Criteria 2] - [evidence/screenshot]
- [x] [Criteria 3] - [evidence/screenshot]

## Implementation Details
**Approach**: [brief description]
**Files Modified**: 
- [file1] - [what changed]
- [file2] - [what changed]

**Key Decisions**:
- [Decision 1]: [reasoning]
- [Decision 2]: [reasoning]

## Testing Evidence
**Manual Testing Completed**:
- [Test scenario 1] - ✅ [result]
- [Test scenario 2] - ✅ [result]
- [Error handling] - ✅ [result]

## Screenshots
[Include relevant screenshots]

## Database Changes
[If applicable: migration files, schema changes]

## Breaking Changes
[Any changes that affect existing functionality]"
```

---

## NetBox Plugin Development Patterns

### File Structure & Imports
```python
# Standard structure
netbox_hedgehog/
├── models/
│   ├── __init__.py          # Import all models
│   ├── base.py             # Base classes
│   └── [feature].py        # Feature-specific models
├── forms/
│   ├── __init__.py         # Import all forms
│   └── [feature].py        # Feature-specific forms
├── views/
│   ├── __init__.py         # Import all views
│   └── [feature].py        # Feature-specific views
└── templates/netbox_hedgehog/
    └── [feature]_*.html    # Templates

# Import patterns
from ..models.[feature] import ModelName
from ..forms.[feature] import FormName
from netbox.views.generic import ObjectView, ObjectListView
```

### Model Development Pattern
```python
# In models/[feature].py
from django.db import models
from .base import BaseCRD  # Inherit from base classes

class MyFeature(BaseCRD):
    # Use existing patterns from other models
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    
    class Meta:
        verbose_name = "My Feature"
        verbose_name_plural = "My Features"
        
    def __str__(self):
        return self.name
```

### Form Development Pattern
```python
# In forms/[feature].py
from django import forms
from ..models.[feature] import MyFeature

class MyFeatureForm(forms.ModelForm):
    class Meta:
        model = MyFeature
        fields = ['name', 'description', 'fabric']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }
```

### View Development Pattern
```python
# In views/[feature].py
from netbox.views.generic import ObjectView, ObjectListView, ObjectEditView
from ..models.[feature] import MyFeature
from ..forms.[feature] import MyFeatureForm

class MyFeatureListView(ObjectListView):
    queryset = MyFeature.objects.all()
    table = MyFeatureTable  # Define table if needed

class MyFeatureView(ObjectView):
    queryset = MyFeature.objects.all()

class MyFeatureEditView(ObjectEditView):
    queryset = MyFeature.objects.all()
    form = MyFeatureForm
```

---

## Testing & Quality Assurance

### Manual Testing Checklist
**Before submitting PR:**
- [ ] **Happy Path**: Primary use case works as expected
- [ ] **Form Validation**: Required fields enforced, error messages shown
- [ ] **Navigation**: All links work, breadcrumbs correct
- [ ] **Permissions**: Unauthorized access properly blocked
- [ ] **Data Integrity**: No orphaned records or referential integrity issues
- [ ] **Responsive Design**: Works on different screen sizes
- [ ] **Error Handling**: Graceful handling of edge cases
- [ ] **Performance**: Page loads within reasonable time
- [ ] **Integration**: Doesn't break existing functionality
- [ ] **Browser Console**: No JavaScript errors

### Evidence Collection
```bash
# Capture comprehensive evidence
# 1. Screenshots of working functionality
# 2. Browser network tab (for API calls)
# 3. Server logs (for backend operations)
sudo docker logs netbox-docker-netbox-1 --tail 50

# 4. Database state (if relevant)
sudo docker exec -it netbox-docker-netbox-1 python manage.py shell
>>> from netbox_hedgehog.models import MyFeature
>>> MyFeature.objects.count()
```

### Code Quality Self-Review
```python
# Before committing, check:
# 1. Follow Django conventions
# 2. Use existing patterns from codebase
# 3. Proper error handling
# 4. Descriptive variable names
# 5. Comments for complex logic
# 6. No hardcoded values
# 7. Proper imports organization
```

---

## GitHub Integration Patterns

### Issue Progress Updates
```markdown
## Implementation Progress - [Date]
**Status**: In Progress (Day 2 of estimated 3-day effort)
**Completed**: 
- [x] Model implementation and migration
- [x] Form creation with validation
**In Progress**: 
- [ ] View implementation (50% complete)
**Next**: 
- [ ] Template creation
- [ ] URL routing
- [ ] Integration testing

**Blockers**: None
**Questions**: Clarification needed on error handling approach (see comment below)
```

### Technical Decision Documentation
```markdown
## Technical Decision - [Feature Name]
**Decision**: Use Django ModelForm instead of custom form class
**Reasoning**: 
- Reduces code duplication
- Automatic validation from model constraints
- Easier maintenance
- Follows NetBox plugin patterns
**Alternatives Considered**: 
- Custom Form class: More control but higher maintenance
- API-only approach: Doesn't meet user story requirements
**Impact**: Faster development, consistent with existing codebase
```

### Code Review Preparation
```bash
# Self-review checklist before requesting review
# 1. Clean commit history
git log --oneline -10

# 2. No debug code or comments
grep -r "TODO\|FIXME\|console\.log\|print(" .

# 3. All files properly formatted
# 4. PR description complete with evidence
# 5. All acceptance criteria addressed
```

---

## Common Pitfalls & Solutions

### ❌ Starting Without Understanding Requirements
**Problem**: Implementing features that don't match acceptance criteria
**Solution**: Always start by understanding the user story and asking questions

### ❌ Not Following Existing Patterns
**Problem**: Creating inconsistent code that doesn't fit the codebase
**Solution**: Study similar implementations before starting

### ❌ Poor Error Handling
**Problem**: Features that break when given unexpected input
**Solution**: Test error conditions and implement graceful handling

### ❌ Incomplete Testing
**Problem**: Missing edge cases or integration issues
**Solution**: Test all acceptance criteria plus error conditions

### ❌ Large, Monolithic Commits
**Problem**: Difficult code review and risk of breaking multiple things
**Solution**: Commit working increments frequently

---

## Success Metrics

### Code Quality Indicators
- ✅ **PR approved without major changes**: Well-structured, maintainable code
- ✅ **Manual testing evidence provided**: Thorough verification process
- ✅ **All acceptance criteria met**: Complete implementation
- ✅ **No regressions introduced**: Good integration practices
- ✅ **Clear documentation**: Easy for others to understand and maintain

### Collaboration Success
- 🤝 **Proactive communication**: Updates and questions before blockers
- 📝 **Clear commit messages**: Easy to understand change history
- 🎯 **Realistic estimates**: Builds trust with project managers
- 🔄 **Responsive to feedback**: Quick iteration on code review comments

---

## Quick Reference Commands

```bash
# Issue management
gh issue list --assignee @me
gh issue comment [number] --body "Progress update"

# Development workflow
git checkout -b issue-[number]-[description]
sudo docker cp file.py netbox-docker-netbox-1:/opt/netbox/netbox/[path]
sudo docker logs netbox-docker-netbox-1 --tail 20

# Testing
curl -I http://localhost:8000/plugins/hedgehog/[endpoint]/
sudo docker exec -it netbox-docker-netbox-1 python manage.py shell

# PR creation
gh pr create --title "Fix #[number]: [summary]" --body "$(cat pr-template.md)"
```

**Remember**: Quality over speed. It's better to deliver working, maintainable code than to rush and create technical debt.