# Hedgehog NetBox Plugin - Development Process

**Last Updated**: 2025-07-02

## 🎯 **CRITICAL SUCCESS PRINCIPLES**

### **1. INCREMENTAL DEVELOPMENT**
- ✅ **Small Steps**: Complete one CRD type at a time
- ✅ **Test Early**: Test each component before moving to next
- ✅ **Frequent Commits**: Commit working code frequently with descriptive messages
- ✅ **Document Progress**: Update tracking documents after each task

### **2. GIT COMMIT STANDARDS**
- ✅ **Convention**: Use conventional commit format: `type: description`
- ✅ **Frequency**: Commit after each logical unit of work (not daily/hourly)
- ✅ **Descriptive**: Include what was done and why
- ✅ **Atomic**: One feature/fix per commit when possible

### **3. VALIDATION APPROACH**
- ✅ **Test Before Commit**: Always verify functionality works
- ✅ **No Regression**: Ensure existing features still work
- ✅ **Document Issues**: Record any problems in tracking documents

---

## 🛠 **DEVELOPMENT WORKFLOW**

### **Before Starting ANY Task**

1. **Read Current State**:
   ```bash
   # Read these files in order:
   cat PROJECT_STATUS.md
   cat TASK_TRACKING.md
   cat QUICK_START.md
   ```

2. **Check Git Status**:
   ```bash
   git status
   git log --oneline -5
   ```

3. **Verify NetBox Running**:
   ```bash
   sudo docker ps | grep netbox
   curl -I http://localhost:8000/plugins/hedgehog/
   ```

4. **Update Task Status**:
   - Edit `TASK_TRACKING.md`
   - Change task from 🔲 to 🔄
   - Commit the status change

### **During Development**

5. **Follow File Organization**:
   ```
   Forms: netbox_hedgehog/forms/[vpc_api.py|wiring_api.py]
   Views: netbox_hedgehog/views/[crd_type]_views.py
   Templates: netbox_hedgehog/templates/netbox_hedgehog/
   URLs: netbox_hedgehog/urls.py (be careful with URL patterns)
   ```

6. **Testing Protocol**:
   - Test form creation/editing in NetBox UI
   - Verify no server errors in logs
   - Check that forms save properly
   - Test navigation works

7. **Commit Standards**:
   ```bash
   # Stage specific files
   git add [specific files only]
   
   # Use conventional commit format
   git commit -S -m "feat: add External CRD forms and views
   
   - Create ExternalForm class with all required fields
   - Add External CRUD views following VPC pattern  
   - Add templates for External create/edit/list/detail
   - Test forms work without errors
   
   🤖 Generated with [Claude Code](https://claude.ai/code)
   
   Co-Authored-By: Claude <noreply@anthropic.com>"
   ```

### **After Completing Task**

8. **Update Documentation**:
   - Edit `TASK_TRACKING.md` 
   - Change 🔄 to ✅
   - Update progress percentages
   - Add any notes or issues discovered

9. **Commit Documentation**:
   ```bash
   git add TASK_TRACKING.md
   git commit -S -m "docs: update task tracking - completed External CRD forms"
   ```

---

## 📋 **CRD FORM DEVELOPMENT PATTERN**

### **Standard Process for Each CRD Type**

1. **Review Model Definition**:
   ```python
   # Look at the model in models/vpc_api.py or models/wiring_api.py
   # Understand fields, relationships, validation requirements
   ```

2. **Create Form Class**:
   ```python
   # In forms/vpc_api.py or forms/wiring_api.py
   class ExternalForm(ModelForm):
       class Meta:
           model = External
           fields = ['name', 'fabric', 'spec', 'labels', 'annotations']
           # Add widgets, help_texts, validation as needed
   ```

3. **Add Views** (if not already present):
   ```python
   # In views/[type]_views.py
   # Follow VPC pattern for ListView, CreateView, UpdateView, DeleteView
   ```

4. **Create Templates** (if not already present):
   ```html
   <!-- Follow VPC template patterns -->
   <!-- [type]_list.html, [type]_detail.html, [type]_edit.html -->
   ```

5. **Update URLs** (carefully):
   ```python
   # Only add if necessary - check existing patterns first
   # Follow established naming conventions
   ```

6. **Test Thoroughly**:
   - Create new CRD via form
   - Edit existing CRD  
   - View CRD details
   - Delete CRD
   - Verify no errors in NetBox logs

---

## 🔧 **TECHNICAL STANDARDS**

### **Code Quality**
- ✅ **Follow Existing Patterns**: Use VPC implementation as template
- ✅ **Error Handling**: All forms should handle validation errors gracefully
- ✅ **User Feedback**: Provide clear success/error messages
- ✅ **Consistent Styling**: Use Bootstrap 5 classes consistently

### **Form Standards**
- ✅ **Required Fields**: Mark required fields clearly
- ✅ **Help Text**: Provide helpful descriptions for complex fields
- ✅ **Validation**: Client-side and server-side validation
- ✅ **Widget Selection**: Use appropriate input types

### **View Standards**  
- ✅ **Permissions**: Check user permissions appropriately
- ✅ **Error Pages**: Handle 404, 403, 500 gracefully
- ✅ **Success URLs**: Redirect to appropriate page after operations
- ✅ **Context Data**: Provide necessary data to templates

---

## 🚨 **CRITICAL SAFETY CHECKS**

### **Before ANY Code Changes**
1. **Backup Check**: Ensure recent commits are pushed
2. **Container Status**: Verify NetBox container is healthy
3. **Database State**: Check no pending migrations

### **Before Committing**
1. **Syntax Check**: Ensure Python files compile
2. **No Errors**: NetBox must start without errors
3. **Basic Functionality**: Core features still work
4. **Documentation Updated**: Task tracking reflects changes

### **Testing Container Changes**
```bash
# Copy files to container for testing
sudo docker cp [local_file] netbox-docker-netbox-1:[container_path]

# Restart if needed  
sudo docker restart netbox-docker-netbox-1

# Check logs for errors
sudo docker logs netbox-docker-netbox-1 --tail 20
```

---

## 📁 **FILE STRUCTURE REFERENCE**

### **Key Files and Their Purpose**
```
PROJECT_STATUS.md           # High-level project overview
TASK_TRACKING.md           # Detailed task status and progress
DEVELOPMENT_PROCESS.md     # This file - how to develop
QUICK_START.md             # For new sessions to get up to speed

netbox_hedgehog/
├── models/
│   ├── vpc_api.py         # VPC API CRD models
│   └── wiring_api.py      # Wiring API CRD models
├── forms/
│   ├── vpc_api.py         # Forms for VPC API CRDs  
│   └── wiring_api.py      # Forms for Wiring API CRDs
├── views/
│   ├── vpc_views.py       # VPC CRUD views
│   ├── wiring_views.py    # Wiring CRUD views
│   └── sync_views.py      # Kubernetes sync operations
├── templates/netbox_hedgehog/
│   ├── [type]_list.html   # List views for each CRD type
│   ├── [type]_detail.html # Detail views for each CRD type
│   └── [type]_edit.html   # Create/edit forms for each CRD type
└── utils/
    └── kubernetes.py      # Kubernetes client integration
```

---

## 🔄 **SESSION RESTART PROTOCOL**

### **If Claude Code Session Crashes**

1. **Read Documentation**:
   ```bash
   cat QUICK_START.md          # Get oriented quickly
   cat PROJECT_STATUS.md       # Understand current state  
   cat TASK_TRACKING.md        # See what's in progress
   ```

2. **Verify Environment**:
   ```bash
   sudo docker ps | grep netbox
   git status
   git log --oneline -5
   ```

3. **Continue Work**:
   - Find the 🔄 IN_PROGRESS task in TASK_TRACKING.md
   - Continue from where previous session left off
   - Follow the development workflow above

4. **Update Status**:
   - Update TASK_TRACKING.md with current progress
   - Commit documentation changes

---

## 💡 **BEST PRACTICES REMINDERS**

- 🔄 **Always read existing code before writing new code**
- 🔄 **Test each change in the browser before committing**
- 🔄 **Commit working code frequently with good messages**
- 🔄 **Update documentation immediately after completing tasks**
- 🔄 **Follow the established patterns rather than creating new ones**
- 🔄 **Ask for guidance if unsure about approach**