# Hedgehog NetBox Plugin - Quick Start Guide

**For New Claude Code Sessions**

## 🚀 **IMMEDIATE ORIENTATION (5 minutes)**

### **1. Project Context**
```
WHAT: NetBox plugin for managing Hedgehog fabric CRDs via web interface
WHY: Provide self-service catalog for Kubernetes CRD management  
WHERE: Local netbox-docker environment with live Hedgehog K8s cluster access
WHEN: Currently in CRD form development phase
WHO: NetBox users managing Hedgehog Ethernet fabric infrastructure
```

### **2. Current Working State**
✅ **NetBox Running**: Plugin installed, container healthy  
✅ **Kubernetes Connected**: Real connectivity to Hedgehog cluster working  
✅ **Basic Features**: Fabric CRUD, VPC forms, sync functionality working  
🔄 **In Progress**: Building forms for all 12 CRD types (currently 1/12 complete)  

### **3. What You Can Test Right Now**
```bash
# Access plugin
http://localhost:8000/plugins/hedgehog/

# Test working features:
- Navigate to Fabrics → Create/Edit fabric
- Test Connection button (connects to real K8s cluster)  
- Sync Now button (fetches real CRD counts)
- VPC management (create/edit VPCs)
```

---

## 🎯 **CURRENT MISSION**

### **Primary Objective**: Complete CRD Form Coverage
Build CRUD forms for remaining 11 CRD types to prepare for import functionality.

### **Next Immediate Task**: 
Check `TASK_TRACKING.md` for the 🔄 IN_PROGRESS task or first 🔲 TODO task.

**Most Likely**: Create External CRD forms following the VPC pattern.

---

## 🛠 **ESSENTIAL COMMANDS**

### **Environment Check**
```bash
# Verify everything is running
sudo docker ps | grep netbox                    # Should show healthy container
curl -I http://localhost:8000/plugins/hedgehog/ # Should return 200 OK  
git status                                       # Should be clean
git log --oneline -5                            # See recent commits
```

### **Development Loop**
```bash
# 1. Edit code files
# 2. Copy to container
sudo docker cp [local_file] netbox-docker-netbox-1:[container_path]

# 3. Test in browser
http://localhost:8000/plugins/hedgehog/

# 4. Commit working changes
git add [files]
git commit -S -m "feat: description"

# 5. Update task tracking
# Edit TASK_TRACKING.md, change 🔲 to ✅
git add TASK_TRACKING.md  
git commit -S -m "docs: update task tracking - completed [task]"
```

### **Quick File Access**
```bash
# Key development files
code netbox_hedgehog/forms/vpc_api.py          # VPC API forms (template to follow)
code netbox_hedgehog/forms/wiring_api.py       # Wiring API forms
code netbox_hedgehog/models/vpc_api.py         # VPC API models (see field definitions)
code netbox_hedgehog/models/wiring_api.py      # Wiring API models
code TASK_TRACKING.md                          # Task status and priorities
```

---

## 📊 **PROJECT STRUCTURE AT A GLANCE**

### **What's Working** ✅
```
Plugin Core           ✅ Installed and running
Fabric Management     ✅ Full CRUD, test connection, sync
VPC Forms            ✅ Create/edit forms working  
Kubernetes Client    ✅ Real cluster connectivity
Database Models      ✅ All 12 CRD types defined
UI Framework         ✅ Bootstrap 5, responsive design
```

### **What's Missing** 🔲
```
CRD Forms           🔲 11 of 12 CRD types need forms
Import Function     🔲 Sync doesn't create NetBox records yet
Apply Function      🔲 Can't apply CRDs to Kubernetes yet
Navigation          🔲 Full menu disabled due to URL conflicts
Detail Views        🔲 Individual CRD detail pages disabled
```

### **File Organization**
```
Forms:     netbox_hedgehog/forms/[vpc_api.py|wiring_api.py]
Models:    netbox_hedgehog/models/[vpc_api.py|wiring_api.py] 
Views:     netbox_hedgehog/views/[type]_views.py
Templates: netbox_hedgehog/templates/netbox_hedgehog/
URLs:      netbox_hedgehog/urls.py (be careful!)
Utils:     netbox_hedgehog/utils/kubernetes.py
```

---

## 🎯 **DEVELOPMENT PATTERN**

### **Standard CRD Form Development**
1. **Study VPC Implementation**:
   - Look at `forms/vpc_api.py` - `VPCForm` class
   - See how it handles model fields, widgets, validation
   - Note the Meta class pattern

2. **Find Target Model**:
   - Check `models/vpc_api.py` or `models/wiring_api.py`
   - Understand the fields that need form inputs

3. **Create Form Class**:
   ```python
   class ExternalForm(ModelForm):
       class Meta:
           model = External
           fields = ['name', 'fabric', 'spec', 'labels', 'annotations']
           widgets = {
               'spec': forms.Textarea(attrs={'rows': 8}),
               # ... other widgets
           }
   ```

4. **Test in Browser**:
   - Copy file to container
   - Navigate to creation form
   - Verify form displays and saves correctly

5. **Commit and Update**:
   - Commit working code
   - Update `TASK_TRACKING.md`

---

## 🚨 **CRITICAL SAFETY REMINDERS**

### **Always Before Coding**
- ✅ Read `TASK_TRACKING.md` to see current status
- ✅ Verify NetBox container is healthy
- ✅ Check git status is clean

### **Never Do This**
- ❌ Don't modify URL patterns without extreme care
- ❌ Don't commit broken code
- ❌ Don't work on multiple tasks simultaneously  
- ❌ Don't skip updating task tracking

### **Always Do This**
- ✅ Follow existing VPC pattern exactly
- ✅ Test every change in browser
- ✅ Commit frequently with good messages
- ✅ Update documentation after completing tasks

---

## 🔄 **IF THINGS GO WRONG**

### **Plugin Won't Load**
```bash
# Check container logs
sudo docker logs netbox-docker-netbox-1 --tail 20

# Common issues:
# - Python syntax errors in forms/views
# - Missing imports
# - URL pattern conflicts
```

### **Forms Don't Work**
```bash
# Check form definitions
# Compare to working VPC forms
# Verify model field names match form fields
# Test with minimal form first
```

### **Can't Access Pages**
```bash  
# Usually URL pattern issues
# Check urls.py carefully
# Verify view names match URL patterns
# Look for NoReverseMatch errors in logs
```

---

## 📚 **ESSENTIAL READING ORDER**

**New Session Checklist**:
1. ✅ Read this file (QUICK_START.md) 
2. ✅ Read PROJECT_STATUS.md for high-level overview
3. ✅ Read TASK_TRACKING.md for current task status  
4. ✅ Verify environment with essential commands above
5. ✅ Look at VPC form implementation as template
6. ✅ Start working on next 🔲 TODO or continue 🔄 IN_PROGRESS task

**Time to productivity**: ~10 minutes if environment is working

---

## 🎯 **SUCCESS CRITERIA**

**You're ready to be productive when you can**:
- ✅ Access http://localhost:8000/plugins/hedgehog/ successfully
- ✅ Navigate to fabric detail page and click Test Connection  
- ✅ See the VPC creation form working
- ✅ Understand which task you should work on next
- ✅ Know how to copy files to container and test changes

**Start here**: Find the next task in `TASK_TRACKING.md` and follow the `DEVELOPMENT_PROCESS.md` workflow.