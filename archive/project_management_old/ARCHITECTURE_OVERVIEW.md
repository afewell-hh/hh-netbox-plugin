# Hedgehog NetBox Plugin - Architecture Overview

**Last Updated**: 2025-07-02

## 🏗 **SYSTEM ARCHITECTURE**

### **High-Level Components**
```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   NetBox UI     │    │  Hedgehog Plugin │    │ Kubernetes API  │
│  (Web Browser)  │◄──►│    (Django)      │◄──►│ (Hedgehog CRDs) │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │  PostgreSQL DB  │
                       │ (NetBox Models) │
                       └─────────────────┘
```

### **Plugin Integration**
- **Type**: NetBox Plugin (Django App)
- **Installation**: Integrated into netbox-docker environment
- **Database**: Shares PostgreSQL with NetBox core
- **Authentication**: Uses NetBox's authentication system
- **UI**: Integrates with NetBox's navigation and styling

---

## 📊 **DATA MODEL ARCHITECTURE**

### **Core Entities**
```
HedgehogFabric (1) ──────┐
    │                    │
    │ (1:N)              │ (1:N)
    ▼                    ▼
VPC API Models      Wiring API Models
├── VPC             ├── Connection
├── External        ├── Server  
├── ExternalAtt.    ├── Switch
├── ExternalPeer.   ├── SwitchGroup
├── IPv4Namespace   └── VLANNamespace
├── VPCAttachment
└── VPCPeering
```

### **Model Inheritance**
```python
BaseCRD (Abstract)
├── name: CharField
├── fabric: ForeignKey(HedgehogFabric)
├── spec: JSONField
├── labels: JSONField  
├── annotations: JSONField
├── kubernetes_status: CharField
├── kubernetes_uid: CharField
└── last_synced: DateTimeField
```

### **Status Tracking**
```python
HedgehogFabric
├── connection_status: [unknown|connected|disconnected|error]
├── sync_status: [never_synced|in_sync|out_of_sync|syncing|error]
├── connection_error: TextField
├── sync_error: TextField
├── last_sync: DateTimeField
└── cached_[type]_count: PositiveIntegerField
```

---

## 🔧 **TECHNICAL IMPLEMENTATION**

### **Django App Structure**
```
netbox_hedgehog/
├── __init__.py              # Plugin config
├── models/
│   ├── __init__.py         # Model exports
│   ├── fabric.py           # Fabric model
│   ├── base.py             # BaseCRD abstract model
│   ├── vpc_api.py          # VPC API CRD models
│   └── wiring_api.py       # Wiring API CRD models
├── forms/
│   ├── __init__.py         # Form exports
│   ├── vpc_api.py          # VPC API forms ✅
│   └── wiring_api.py       # Wiring API forms 🔲
├── views/
│   ├── fabric_views.py     # Fabric CRUD views ✅
│   ├── sync_views.py       # K8s sync operations ✅
│   ├── vpc_views.py        # VPC CRUD views ✅
│   └── wiring_views.py     # Wiring CRUD views 🔲
├── templates/
│   └── netbox_hedgehog/    # HTML templates
├── static/
│   └── netbox_hedgehog/    # CSS/JS assets
├── utils/
│   └── kubernetes.py       # K8s client ✅
├── urls.py                 # URL routing
└── navigation.py           # Menu structure
```

### **Kubernetes Integration**
```python
KubernetesClient
├── __init__(fabric)        # Fabric-specific configuration
├── test_connection()       # Validate cluster access ✅
├── apply_crd()            # Apply CRD to cluster 🔲
├── get_crd_status()       # Get CRD status from cluster 🔲
└── delete_crd()           # Delete CRD from cluster 🔲

KubernetesSync  
├── sync_all_crds()        # Sync all CRDs for fabric ✅
├── fetch_crds_from_k8s()  # Fetch existing CRDs ✅
└── import_crd_data()      # Create NetBox records 🔲
```

---

## 🎯 **USER INTERFACE ARCHITECTURE**

### **Navigation Structure**
```
Hedgehog Plugin
├── Overview
│   ├── Dashboard              ✅
│   └── Network Topology       ✅
└── Management  
    ├── Fabrics               ✅
    └── VPCs                  ✅

Future Full Navigation:
├── VPC API
│   ├── VPCs                  ✅
│   ├── Externals             🔲
│   └── IPv4 Namespaces       🔲
└── Wiring API
    ├── Connections           🔲
    ├── Switches              🔲
    └── Servers               🔲
```

### **Page Workflow**
```
1. Dashboard ──→ 2. Fabric List ──→ 3. Fabric Detail
                      │                    │
                      ▼                    ▼
                 4. Create Fabric    5. Test Connection
                      │                    │
                      ▼                    ▼
                 6. Configure K8s     7. Sync CRDs
                      │                    │
                      ▼                    ▼
                 8. Import CRDs      9. Manage CRDs
```

### **Form Architecture**
```python
# Pattern for all CRD forms
class CRDForm(ModelForm):
    class Meta:
        model = CRDModel
        fields = ['name', 'fabric', 'spec', 'labels', 'annotations']
        widgets = {
            'spec': forms.Textarea(attrs={'rows': 8}),
            'labels': forms.Textarea(attrs={'rows': 3}),
            'annotations': forms.Textarea(attrs={'rows': 3}),
        }
        help_texts = {
            'spec': 'CRD specification as JSON',
            'labels': 'Kubernetes labels as JSON',
            'annotations': 'Kubernetes annotations as JSON',
        }
```

---

## 🔄 **DATA FLOW ARCHITECTURE**

### **Sync Operation Flow**
```
1. User clicks "Sync Now"
         │
2. FabricSyncView.post()
         │
3. KubernetesSync.sync_all_crds()
         │
4. KubernetesSync.fetch_crds_from_kubernetes()
         │
5. Kubernetes API ──→ Return CRD data
         │
6. Update cached counts in fabric
         │
7. Return success/error to UI
         │
8. Update status badges dynamically
```

### **Future Apply Operation Flow**
```
1. User clicks "Apply VPC"
         │
2. VPCApplyView.post()
         │
3. KubernetesClient.apply_crd()
         │
4. Generate K8s manifest from NetBox data
         │
5. POST to Kubernetes API
         │
6. Update VPC status in NetBox
         │
7. Return result to user
```

### **Future Import Operation Flow**
```
1. Fabric onboarding/sync
         │
2. Fetch existing CRDs from cluster
         │
3. For each CRD not in NetBox:
         │
4. Create NetBox model instance
         │
5. Set kubernetes_status = 'live'
         │
6. Show import summary to user
```

---

## 🛡 **SECURITY ARCHITECTURE**

### **Authentication & Authorization**
- **NetBox Users**: Inherits NetBox user system
- **Permissions**: Uses Django/NetBox permission framework
- **K8s Access**: Service account or kubeconfig per fabric

### **Data Validation**
- **Form Validation**: Django form validation
- **JSON Schema**: CRD spec validation (future)
- **K8s Validation**: Kubernetes API validates on apply

### **Error Handling**
- **Form Errors**: Django form error display
- **K8s Errors**: Captured and displayed to user
- **System Errors**: Logged, generic error to user

---

## 🔧 **DEPLOYMENT ARCHITECTURE**

### **Current Environment**
```
Host System
├── netbox-docker/
│   ├── docker-compose.yml
│   ├── netbox container ──→ Port 8000
│   ├── postgres container
│   └── redis container
├── hedgehog-netbox-plugin/    # Development directory
└── kubectl config            # K8s cluster access
```

### **Plugin Installation**
1. **Development Mode**: Files copied manually to container
2. **Production Mode**: Install via pip/setup.py (future)

### **Database Integration**
- **Tables**: Prefixed with `netbox_hedgehog_`
- **Migrations**: Standard Django migrations
- **Relationships**: Foreign keys to NetBox core models where needed

---

## 📊 **PERFORMANCE CONSIDERATIONS**

### **Current Optimizations**
- **Cached Counts**: Fabric CRD counts cached in database
- **Lazy Loading**: Templates load data on demand
- **Efficient Queries**: Use select_related/prefetch_related where possible

### **Future Optimizations**
- **Background Sync**: Celery tasks for large sync operations
- **Caching**: Redis cache for frequently accessed data
- **Pagination**: Large CRD lists with pagination
- **Bulk Operations**: Efficient bulk create/update operations

---

## 🔍 **DEBUGGING ARCHITECTURE**

### **Logging Locations**
```bash
# NetBox container logs
sudo docker logs netbox-docker-netbox-1

# Plugin-specific logs  
# Look for lines containing 'hedgehog' or error tracebacks
```

### **Common Debug Points**
- **Form Errors**: Check form.errors in templates
- **URL Routing**: NoReverseMatch usually URL pattern issues
- **K8s Connectivity**: Connection test shows detailed error info
- **Database Issues**: Django migration problems

### **Development Tools**
- **Django Debug**: Debug mode enabled in development
- **Browser DevTools**: Network tab for AJAX debugging
- **Container Access**: `docker exec` for direct debugging