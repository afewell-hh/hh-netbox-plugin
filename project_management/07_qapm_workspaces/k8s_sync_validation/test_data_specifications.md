# Test Data Specifications for GitOps Sync Testing

## Test File Structure

### 1. VALID SINGLE-DOCUMENT YAML FILES

#### 1.1 Basic VPC Configuration
**File**: `test_data/valid/single-vpc.yaml`
```yaml
apiVersion: vpc.hedgehog.io/v1beta1
kind: VPC
metadata:
  name: test-vpc
  namespace: default
  labels:
    environment: test
    fabric: test-fabric
spec:
  vni: 1000
  subnets:
    - name: subnet-1
      cidr: "10.0.1.0/24"
  dhcpRelay:
    enabled: true
```

#### 1.2 Basic Switch Configuration
**File**: `test_data/valid/single-switch.yaml`
```yaml
apiVersion: wiring.hedgehog.io/v1beta1
kind: Switch
metadata:
  name: leaf-switch-01
  namespace: default
  labels:
    role: leaf
    rack: rack-01
spec:
  role: leaf
  group: leaf-group
  ports:
    - name: Ethernet1
      breakout: "4x25G"
    - name: Ethernet2
      breakout: "4x25G"
```

#### 1.3 Basic Connection Configuration
**File**: `test_data/valid/single-connection.yaml`
```yaml
apiVersion: wiring.hedgehog.io/v1beta1
kind: Connection
metadata:
  name: server-to-leaf
  namespace: default
spec:
  from:
    device: server-01
    port: eth0
  to:
    device: leaf-switch-01
    port: Ethernet1/1
```

#### 1.4 Server Configuration
**File**: `test_data/valid/single-server.yaml`
```yaml
apiVersion: wiring.hedgehog.io/v1beta1
kind: Server
metadata:
  name: compute-server-01
  namespace: default
  labels:
    type: compute
    rack: rack-01
spec:
  type: compute
  ports:
    - name: eth0
      speed: "25G"
    - name: eth1
      speed: "25G"
```

### 2. VALID MULTI-DOCUMENT YAML FILES

#### 2.1 VPC and Switch Combination
**File**: `test_data/valid/multi-vpc-switch.yaml`
```yaml
apiVersion: vpc.hedgehog.io/v1beta1
kind: VPC
metadata:
  name: production-vpc
  namespace: production
spec:
  vni: 2000
  subnets:
    - name: web-subnet
      cidr: "10.1.0.0/24"
---
apiVersion: wiring.hedgehog.io/v1beta1
kind: Switch
metadata:
  name: spine-switch-01
  namespace: production
spec:
  role: spine
  group: spine-group
  ports:
    - name: Ethernet1
      breakout: "1x100G"
```

#### 2.2 Complete Fabric Configuration
**File**: `test_data/valid/complete-fabric.yaml`
```yaml
apiVersion: vpc.hedgehog.io/v1beta1
kind: VPC
metadata:
  name: fabric-vpc
  namespace: default
spec:
  vni: 3000
---
apiVersion: wiring.hedgehog.io/v1beta1
kind: Switch
metadata:
  name: leaf-01
  namespace: default
spec:
  role: leaf
  group: leaf-group
---
apiVersion: wiring.hedgehog.io/v1beta1
kind: Server
metadata:
  name: server-01
  namespace: default
spec:
  type: compute
---
apiVersion: wiring.hedgehog.io/v1beta1
kind: Connection
metadata:
  name: server-to-leaf-01
  namespace: default
spec:
  from:
    device: server-01
    port: eth0
  to:
    device: leaf-01
    port: Ethernet1/1
```

### 3. INVALID YAML FILES

#### 3.1 Syntax Error Files
**File**: `test_data/invalid/syntax-error.yaml`
```yaml
apiVersion: vpc.hedgehog.io/v1beta1
kind: VPC
metadata:
  name: syntax-error-vpc
    invalid_indentation: true  # Syntax error
spec:
  - invalid_list_syntax: true
```

#### 3.2 Missing Required Fields
**File**: `test_data/invalid/missing-fields.yaml`
```yaml
apiVersion: vpc.hedgehog.io/v1beta1
kind: VPC
metadata:
  # Missing name field
  namespace: default
spec:
  vni: 4000
```

#### 3.3 Invalid API Version
**File**: `test_data/invalid/invalid-api-version.yaml`
```yaml
apiVersion: invalid.api/v999
kind: VPC
metadata:
  name: invalid-api-vpc
  namespace: default
spec:
  vni: 5000
```

#### 3.4 Unsupported Kind
**File**: `test_data/invalid/unsupported-kind.yaml`
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: unsupported-config
  namespace: default
data:
  key: value
```

### 4. EDGE CASE FILES

#### 4.1 Empty File
**File**: `test_data/edge_cases/empty-file.yaml`
```
```

#### 4.2 Comments Only
**File**: `test_data/edge_cases/comments-only.yaml`
```yaml
# This file contains only comments
# and no actual YAML content

---

# Another comment block
```

#### 4.3 Mixed Valid/Invalid Documents
**File**: `test_data/edge_cases/mixed-validity.yaml`
```yaml
apiVersion: vpc.hedgehog.io/v1beta1
kind: VPC
metadata:
  name: valid-vpc
  namespace: default
spec:
  vni: 6000
---
apiVersion: vpc.hedgehog.io/v1beta1
kind: VPC
metadata:
  # Missing name - invalid
  namespace: default
spec:
  vni: 6001
---
apiVersion: wiring.hedgehog.io/v1beta1
kind: Switch
metadata:
  name: valid-switch
  namespace: default
spec:
  role: leaf
```

#### 4.4 Large Multi-Document File
**File**: `test_data/edge_cases/large-multi-doc.yaml`
```yaml
# Generate 100 VPC documents programmatically
# Document template:
apiVersion: vpc.hedgehog.io/v1beta1
kind: VPC
metadata:
  name: vpc-001
  namespace: default
spec:
  vni: 10001
---
# ... repeat for vpc-002 through vpc-100
```

#### 4.5 Special Characters in Names
**File**: `test_data/edge_cases/special-characters.yaml`
```yaml
apiVersion: vpc.hedgehog.io/v1beta1
kind: VPC
metadata:
  name: vpc-with-üñîçödé-chars
  namespace: default
spec:
  vni: 7000
```

#### 4.6 Null Documents
**File**: `test_data/edge_cases/null-documents.yaml`
```yaml
apiVersion: vpc.hedgehog.io/v1beta1
kind: VPC
metadata:
  name: before-null
  namespace: default
spec:
  vni: 8000
---
null
---

---
apiVersion: vpc.hedgehog.io/v1beta1
kind: VPC
metadata:
  name: after-null
  namespace: default
spec:
  vni: 8001
```

### 5. PERFORMANCE TEST FILES

#### 5.1 Large Single Document
**File**: `test_data/performance/large-single-doc.yaml`
```yaml
apiVersion: vpc.hedgehog.io/v1beta1
kind: VPC
metadata:
  name: large-vpc
  namespace: default
  annotations:
    # Large annotation with 10KB of data
    large-data: |
      # 10KB of Lorem ipsum text...
spec:
  vni: 9000
  # Large spec with many subnets
  subnets:
    # Generate 1000 subnets programmatically
```

#### 5.2 Many Small Files
**Directory**: `test_data/performance/many_small_files/`
- 100 files: `vpc-001.yaml` through `vpc-100.yaml`
- Each file contains single small VPC configuration

### 6. DIRECTORY STRUCTURE TESTS

#### 6.1 Deep Nested Structure
```
test_data/directory_structures/deep_nested/
└── raw/
    └── level1/
        └── level2/
            └── level3/
                └── level4/
                    └── level5/
                        └── deep-vpc.yaml
```

#### 6.2 Mixed File Types
```
test_data/directory_structures/mixed_types/
└── raw/
    ├── valid-vpc.yaml
    ├── config.json
    ├── README.md
    ├── docker-compose.yml
    ├── mkdocs.yml
    └── script.py
```

#### 6.3 Hidden Files
```
test_data/directory_structures/hidden_files/
└── raw/
    ├── .hidden-vpc.yaml
    ├── .DS_Store
    ├── Thumbs.db
    └── visible-vpc.yaml
```

## Mock Directory Structures

### 1. Complete GitOps Structure
```
mock_repositories/complete_structure/
└── fabrics/
    └── test-fabric/
        └── gitops/
            ├── raw/
            │   ├── pending/
            │   ├── processed/
            │   └── errors/
            ├── unmanaged/
            │   ├── external-configs/
            │   └── manual-overrides/
            ├── managed/
            │   ├── vpcs/
            │   ├── connections/
            │   ├── switches/
            │   ├── servers/
            │   ├── switch-groups/
            │   └── metadata/
            └── .hnp/
```

### 2. Minimal Structure
```
mock_repositories/minimal_structure/
└── fabrics/
    └── test-fabric/
        └── gitops/
            └── raw/
                └── test-file.yaml
```

### 3. Corrupted Structure
```
mock_repositories/corrupted_structure/
└── fabrics/
    └── test-fabric/
        └── gitops/
            ├── raw/
            │   └── test-file.yaml
            └── incomplete-managed/  # Missing required subdirectories
```

## Test Data Generation Scripts

### 1. Large File Generator
```python
# generate_large_files.py
def generate_large_multi_doc(num_docs=1000):
    """Generate large multi-document YAML file"""
    with open('test_data/edge_cases/large-multi-doc.yaml', 'w') as f:
        for i in range(1, num_docs + 1):
            f.write(f'''apiVersion: vpc.hedgehog.io/v1beta1
kind: VPC
metadata:
  name: vpc-{i:03d}
  namespace: default
spec:
  vni: {10000 + i}
''')
            if i < num_docs:
                f.write('---\n')
```

### 2. Many Small Files Generator
```python
# generate_many_files.py
def generate_many_small_files(count=100):
    """Generate many small YAML files"""
    import os
    os.makedirs('test_data/performance/many_small_files', exist_ok=True)
    
    for i in range(1, count + 1):
        with open(f'test_data/performance/many_small_files/vpc-{i:03d}.yaml', 'w') as f:
            f.write(f'''apiVersion: vpc.hedgehog.io/v1beta1
kind: VPC
metadata:
  name: vpc-{i:03d}
  namespace: default
spec:
  vni: {20000 + i}
''')
```

### 3. Invalid File Generator
```python
# generate_invalid_files.py
def generate_syntax_errors():
    """Generate files with various syntax errors"""
    syntax_errors = [
        'invalid-indentation.yaml',
        'missing-colon.yaml', 
        'unclosed-quote.yaml',
        'invalid-unicode.yaml'
    ]
    
    for error_type in syntax_errors:
        # Generate specific syntax error patterns
        pass
```

## Test Data Validation

### Expected File Counts After Processing
- **Valid single docs**: 4 managed files created
- **Valid multi-docs**: 6 managed files created (4 from complete-fabric.yaml, 2 from multi-vpc-switch.yaml)
- **Invalid files**: 0 managed files, errors logged
- **Mixed validity**: Partial success, valid documents processed

### Expected Directory Mappings
- VPC CRs → `managed/vpcs/`
- Switch CRs → `managed/switches/`
- Connection CRs → `managed/connections/`
- Server CRs → `managed/servers/`
- SwitchGroup CRs → `managed/switch-groups/`

### Expected Archive Patterns
- Original files → `.archived` extension
- Conflict resolution → `-1`, `-2`, etc. suffixes
- Namespace handling → `namespace-name.yaml` format

This comprehensive test data specification ensures thorough validation of all GitOps synchronization scenarios with realistic and edge-case data.