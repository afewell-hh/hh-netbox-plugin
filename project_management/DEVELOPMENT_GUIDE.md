# Hedgehog NetBox Plugin - Development Guide

**Last Updated**: 2025-07-03

## 🚀 Quick Start for New Sessions

### 1. Verify Environment (2 minutes)
```bash
# Check NetBox is running
sudo docker ps | grep netbox

# Test plugin is accessible
curl -I http://localhost:8000/plugins/hedgehog/

# Verify Kubernetes access
kubectl get nodes

# Check git status
git status
```

### 2. Read Current State (3 minutes)
```bash
# In order of importance:
cat project_management/CURRENT_STATUS.md
cat project_management/TASK_TRACKING.md
cat project_management/PROJECT_OVERVIEW.md
```

### 3. Start Working (5 minutes)
- Find next task in TASK_TRACKING.md
- Update task status to IN_PROGRESS
- Follow development workflow below

---

## 🛠 Development Workflow

### Before Starting ANY Task

1. **Update Task Status**
   ```bash
   # Edit TASK_TRACKING.md - change task from 🔲 to 🔄
   # Commit the change
   git add project_management/TASK_TRACKING.md
   git commit -m "docs: start working on [task name]"
   ```

2. **Verify Clean State**
   ```bash
   git status  # Should be clean
   sudo docker logs netbox-docker-netbox-1 --tail 20  # No errors
   ```

### During Development

1. **Make Code Changes**
   - Follow existing patterns (use VPC implementation as template)
   - Test incrementally
   - Keep changes focused on one task

2. **Test in NetBox**
   ```bash
   # Copy changed files to container
   sudo docker cp [local_file] netbox-docker-netbox-1:[path]
   
   # If needed, restart container
   sudo docker restart netbox-docker-netbox-1
   
   # Test in browser
   http://localhost:8000/plugins/hedgehog/
   ```

3. **Commit Working Code**
   ```bash
   git add [specific files]
   git commit -m "feat: implement [feature]
   
   - Add specific change details
   - Note any important decisions
   - Reference task if applicable"
   ```

### After Completing Task

1. **Update Documentation**
   ```bash
   # Edit TASK_TRACKING.md - change 🔄 to ✅
   # Update progress percentages
   # Add any notes about issues found
   ```

2. **Commit Documentation**
   ```bash
   git add project_management/TASK_TRACKING.md
   git commit -m "docs: complete [task name]"
   ```

---

## 📁 Code Organization

### Key Directories
```
netbox_hedgehog/
├── models/
│   ├── base.py          # BaseCRD abstract model
│   ├── fabric.py        # HedgehogFabric model
│   ├── vpc_api.py       # VPC API CRD models (7 types)
│   └── wiring_api.py    # Wiring API CRD models (5 types)
│
├── forms/
│   ├── fabric_forms.py  # Fabric forms (don't edit)
│   ├── vpc_api.py       # VPC API CRD forms
│   └── wiring_api.py    # Wiring API CRD forms
│
├── views/
│   ├── fabric_views.py  # Fabric views (working)
│   ├── vpc_views.py     # VPC CRUD views
│   ├── vpc_api.py       # Other VPC API views
│   ├── wiring_views.py  # Wiring CRUD views
│   ├── wiring_api.py    # Wiring API views
│   └── sync_views.py    # Sync operations
│
├── templates/netbox_hedgehog/
│   ├── fabric_*.html    # Fabric templates
│   ├── vpc_*.html       # VPC templates
│   └── [type]_*.html    # Other CRD templates
│
├── utils/
│   ├── kubernetes.py    # K8s client & sync
│   └── reconciliation.py # Sync logic
│
└── urls.py              # URL patterns (be careful!)
```

### Import Patterns
```python
# Models
from ..models.fabric import HedgehogFabric
from ..models.vpc_api import VPC, External, ...

# Forms
from ..forms.vpc_api import VPCForm, ExternalForm, ...

# Views - use class-based views
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from netbox.views.generic import ObjectView
```

---

## 🔧 Common Development Tasks

### Adding a New CRD Form
```python
# In forms/vpc_api.py or forms/wiring_api.py
from django import forms
from ..models.vpc_api import MyCRD

class MyCRDForm(forms.ModelForm):
    class Meta:
        model = MyCRD
        fields = ['name', 'fabric', 'spec', 'labels', 'annotations']
        widgets = {
            'spec': forms.Textarea(attrs={'rows': 10, 'class': 'form-control'}),
            'labels': forms.Textarea(attrs={'rows': 3}),
            'annotations': forms.Textarea(attrs={'rows': 3}),
        }
```

### Testing Kubernetes Integration
```python
# Test in Django shell
sudo docker exec -it netbox-docker-netbox-1 python manage.py shell

from netbox_hedgehog.models import HedgehogFabric
from netbox_hedgehog.utils.kubernetes import KubernetesClient

fabric = HedgehogFabric.objects.first()
k8s = KubernetesClient(fabric)
result = k8s.test_connection()
print(result)
```

### Debugging Issues
```bash
# Check container logs
sudo docker logs netbox-docker-netbox-1 --tail 50

# Check Python syntax
python -m py_compile netbox_hedgehog/forms/vpc_api.py

# Test specific URL
curl -I http://localhost:8000/plugins/hedgehog/vpcs/
```

---

## 🚨 Safety Guidelines

### DO NOT
- ❌ Modify URL patterns without extreme care
- ❌ Change working code without understanding it
- ❌ Commit without testing
- ❌ Work on multiple tasks simultaneously
- ❌ Skip documentation updates

### ALWAYS
- ✅ Test every change in the browser
- ✅ Follow existing code patterns
- ✅ Commit working code frequently
- ✅ Update task tracking immediately
- ✅ Ask for clarification when unsure

---

## 🔍 Troubleshooting

### Plugin Won't Load
```bash
# Usually syntax error
sudo docker logs netbox-docker-netbox-1 --tail 100 | grep -i error

# Common causes:
# - Missing imports
# - Syntax errors in Python files
# - URL pattern conflicts
```

### Forms Don't Save
```python
# Check form validation
# In view, add debugging:
if form.is_valid():
    form.save()
else:
    print(form.errors)  # Check container logs
```

### JavaScript Not Working
```javascript
// Check browser console
// Verify CSRF token is present
// Check URL paths are correct
console.log('Debug:', variable);
```

---

## 📋 Git Commit Standards

### Format
```
type: short description

- Detailed change #1
- Detailed change #2
- Any breaking changes or notes

Fixes #issue (if applicable)
```

### Types
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation only
- `refactor:` Code restructuring
- `test:` Test additions/changes
- `chore:` Maintenance tasks

### Examples
```bash
git commit -m "feat: implement import functionality for VPC CRDs

- Add import method to KubernetesSync class
- Create NetBox records for discovered CRDs
- Handle update conflicts gracefully
- Show import statistics in UI"

git commit -m "fix: resolve navigation menu conflicts

- Re-enable full navigation menu
- Fix fabric_crds URL reference
- Update menu item permissions"

git commit -m "docs: update task tracking - complete import functionality"
```

---

## 🔄 Session Handoff Protocol

### Before Ending Session
1. Commit all working code
2. Update TASK_TRACKING.md with current progress
3. Add notes about any blockers or decisions
4. Push changes if appropriate

### Starting New Session
1. Pull latest changes
2. Read project_management documents
3. Check for any IN_PROGRESS tasks
4. Continue where previous session left off

---

**Remember**: Quality over speed. It's better to complete one task well than to half-finish multiple tasks.