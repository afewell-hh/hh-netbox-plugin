# Agent Validation Protocol
## Preventing False Completion Claims in HNP Fabric Sync

**Mission**: Establish mandatory evidence requirements and validation procedures that make agent lies about completion impossible to sustain.

## MANDATORY TEST EVIDENCE REQUIRED

Before any agent can claim fabric sync functionality is working, they MUST provide ALL of the following evidence with exact commands and expected outputs:

### 1. Configuration Fix Evidence

**Command**: 
```bash
sudo docker exec netbox-docker-netbox-1 python3 manage.py shell -c "
from netbox_hedgehog.models.fabric import HedgehogFabric
from netbox_hedgehog.models.git_repository import GitRepository
fabric = HedgehogFabric.objects.get(id=19)
print('=== CONFIGURATION VALIDATION ===')
print(f'Fabric ID: {fabric.id}')
print(f'Fabric Name: {fabric.name}')
print(f'Git Repository FK: {fabric.git_repository}')
print(f'GitOps Directory: {fabric.gitops_directory}')
if fabric.git_repository:
    print(f'Linked Repository URL: {fabric.git_repository.url}')
    print(f'Repository Connection Status: {fabric.git_repository.connection_status}')
else:
    print('ERROR: No GitRepository linked')
"
```

**Required Output**:
```
Fabric ID: 19
Fabric Name: HCKC
Git Repository FK: <GitRepository: GitOps Test Repository 1 (https://github.com/afewell-hh/gitops-test-1)>
GitOps Directory: gitops/hedgehog/fabric-1/
Linked Repository URL: https://github.com/afewell-hh/gitops-test-1
Repository Connection Status: connected
```

**CURRENT STATE (BROKEN)**:
```
Git Repository FK: None
GitOps Directory: /
Repository Connection Status: pending
```

### 2. Authentication Test Evidence

**Command**:
```bash
sudo docker exec netbox-docker-netbox-1 python3 manage.py shell -c "
from netbox_hedgehog.models.git_repository import GitRepository
repo = GitRepository.objects.get(id=6)
print('=== AUTHENTICATION VALIDATION ===')
print(f'Repository: {repo.name}')
print(f'URL: {repo.url}')
print(f'Has Credentials: {bool(repo.encrypted_credentials)}')
print('Testing connection...')
result = repo.test_connection()
print(f'Connection Success: {result[\"success\"]}')
if result['success']:
    print(f'Authenticated: {result[\"authenticated\"]}')
    print(f'Default Branch: {result[\"default_branch\"]}')
    print(f'Current Commit: {result[\"current_commit\"][:8]}')
else:
    print(f'Error: {result[\"error\"]}')
"
```

**Required Output**:
```
=== AUTHENTICATION VALIDATION ===
Repository: GitOps Test Repository 1
URL: https://github.com/afewell-hh/gitops-test-1
Has Credentials: True
Testing connection...
Connection Success: True
Authenticated: True
Default Branch: main
Current Commit: <8-char-hash>
```

### 3. Repository Content Validation Evidence

**Command**:
```bash
sudo docker exec netbox-docker-netbox-1 python3 manage.py shell -c "
from netbox_hedgehog.models.git_repository import GitRepository
import tempfile
import yaml
from pathlib import Path

repo = GitRepository.objects.get(id=6)
print('=== REPOSITORY CONTENT VALIDATION ===')
with tempfile.TemporaryDirectory() as temp_dir:
    result = repo.clone_repository(temp_dir)
    if result['success']:
        print('Repository cloned successfully')
        gitops_path = Path(temp_dir) / 'gitops' / 'hedgehog' / 'fabric-1'
        if gitops_path.exists():
            print(f'GitOps directory found: {gitops_path}')
            yaml_files = list(gitops_path.glob('*.yaml'))
            print(f'YAML files found: {len(yaml_files)}')
            
            crd_count = 0
            for yaml_file in yaml_files:
                print(f'  - {yaml_file.name} ({yaml_file.stat().st_size} bytes)')
                with open(yaml_file, 'r') as f:
                    docs = list(yaml.safe_load_all(f))
                    for doc in docs:
                        if doc and 'kind' in doc:
                            crd_count += 1
                            print(f'    {doc[\"kind\"]}: {doc[\"metadata\"][\"name\"]}')
            print(f'Total CRDs found: {crd_count}')
        else:
            print(f'ERROR: GitOps directory not found at {gitops_path}')
    else:
        print(f'ERROR: Clone failed: {result[\"error\"]}')
"
```

**Required Output**:
```
=== REPOSITORY CONTENT VALIDATION ===
Repository cloned successfully
GitOps directory found: /tmp/.../gitops/hedgehog/fabric-1
YAML files found: 3
  - prepop.yaml (11264 bytes)
    VPC: test-vpc-1
    Connection: conn-1
    Switch: spine-1
  - test-vpc.yaml (XXX bytes)
    VPC: test-vpc-2
  - test-vpc-2.yaml (XXX bytes)
    VPC: test-vpc-3
Total CRDs found: >0
```

### 4. Database Sync Validation Evidence

**Command**: 
```bash
sudo docker exec netbox-docker-netbox-1 python3 manage.py shell -c "
from netbox_hedgehog.models.fabric import HedgehogFabric
from netbox_hedgehog.models.vpc_api import VPC
from netbox_hedgehog.models.wiring_api import Connection, Switch
from django.utils import timezone

fabric = HedgehogFabric.objects.get(id=19)
print('=== PRE-SYNC DATABASE STATE ===')
print(f'Fabric: {fabric.name}')
print(f'VPCs: {VPC.objects.filter(fabric=fabric).count()}')
print(f'Connections: {Connection.objects.filter(fabric=fabric).count()}')
print(f'Switches: {Switch.objects.filter(fabric=fabric).count()}')
print(f'Cached CRD Count: {fabric.cached_crd_count}')
print(f'Last Sync: {fabric.last_git_sync}')
print()

print('=== TRIGGERING SYNC ===')
result = fabric.trigger_gitops_sync()
print(f'Sync Success: {result[\"success\"]}')
if result['success']:
    print(f'Message: {result[\"message\"]}')
    print(f'Resources Created: {result.get(\"resources_created\", 0)}')
    print(f'Resources Updated: {result.get(\"resources_updated\", 0)}')
    if result.get('errors'):
        print(f'Errors: {result[\"errors\"]}')
else:
    print(f'Error: {result[\"error\"]}')
print()

print('=== POST-SYNC DATABASE STATE ===')
fabric.refresh_from_db()
vpc_count = VPC.objects.filter(fabric=fabric).count()
connection_count = Connection.objects.filter(fabric=fabric).count()
switch_count = Switch.objects.filter(fabric=fabric).count()

print(f'VPCs: {vpc_count}')
print(f'Connections: {connection_count}')
print(f'Switches: {switch_count}')
print(f'Total CRDs: {vpc_count + connection_count + switch_count}')
print(f'Cached CRD Count: {fabric.cached_crd_count}')
print(f'Last Sync: {fabric.last_git_sync}')

# List actual CRD names
if vpc_count > 0:
    print('VPC Names:')
    for vpc in VPC.objects.filter(fabric=fabric)[:5]:
        print(f'  - {vpc.name}')
if connection_count > 0:
    print('Connection Names:')
    for conn in Connection.objects.filter(fabric=fabric)[:5]:
        print(f'  - {conn.name}')
"
```

**Required Output**:
```
=== PRE-SYNC DATABASE STATE ===
Fabric: HCKC
VPCs: 0
Connections: 0  
Switches: 0
Cached CRD Count: 0
Last Sync: None

=== TRIGGERING SYNC ===
Sync Success: True
Message: Sync completed: X created, Y updated
Resources Created: >0
Resources Updated: >=0

=== POST-SYNC DATABASE STATE ===
VPCs: >0
Connections: >0
Switches: >0
Total CRDs: >0
Cached CRD Count: >0
Last Sync: <recent timestamp>
VPC Names:
  - test-vpc-1
  - test-vpc-2
Connection Names:
  - conn-1
```

### 5. GUI Workflow Evidence

**Required Screenshots**:

1. **Before Sync Screenshot**: Fabric detail page showing 0 CRDs
   - URL: `http://localhost:8000/plugins/hedgehog/fabrics/19/`
   - Must show fabric name "HCKC"
   - Must show 0 counts for all CRD types
   - Must show "Sync Now" button

2. **Sync Button Click Screenshot**: 
   - Click "Sync Now" button
   - Must show loading state or success message
   - Must not show error message

3. **After Sync Screenshot**: Fabric detail page showing updated CRDs
   - Same URL after refresh
   - Must show non-zero counts for CRDs
   - Must show updated "Last Sync" timestamp
   - Must show success indicator

**GUI Test Command**:
```python
# test_gui_workflow.py
import requests
from bs4 import BeautifulSoup

def test_complete_gui_workflow():
    session = requests.Session()
    
    # Login
    login_response = session.post('http://localhost:8000/login/', data={
        'username': 'admin',
        'password': 'admin', 
        'csrfmiddlewaretoken': extract_csrf_token(login_response)
    })
    assert login_response.status_code in [200, 302]
    
    # Access fabric page
    fabric_response = session.get('http://localhost:8000/plugins/hedgehog/fabrics/19/')
    assert fabric_response.status_code == 200
    assert "HCKC" in fabric_response.text
    
    # Find and click sync button
    soup = BeautifulSoup(fabric_response.text, 'html.parser')
    sync_form = soup.find('form', action=lambda x: x and 'sync' in x)
    assert sync_form is not None, "Sync form not found"
    
    # Submit sync request
    csrf_token = soup.find('input', {'name': 'csrfmiddlewaretoken'})['value']
    sync_response = session.post(sync_form['action'], data={
        'csrfmiddlewaretoken': csrf_token
    })
    
    # Verify success
    assert sync_response.status_code in [200, 302]
    
    # Check results
    final_response = session.get('http://localhost:8000/plugins/hedgehog/fabrics/19/')
    assert "Total CRDs: 0" not in final_response.text, "CRD count should be updated"
    
    print("GUI workflow test PASSED")

if __name__ == "__main__":
    test_complete_gui_workflow()
```

## FALSE COMPLETION DETECTION

### Automatic Lie Detection

The following patterns indicate agent lies about completion:

#### LIE TYPE 1: "Sync functionality works"
**Evidence of lie**:
- `fabric.git_repository` is still `None`
- Database query shows 0 CRDs after claimed sync
- `fabric.cached_crd_count` is still 0
- GUI shows error when sync button clicked

**Verification command**:
```bash
# This should show non-None git_repository and >0 CRDs
sudo docker exec netbox-docker-netbox-1 python3 manage.py shell -c "
fabric = HedgehogFabric.objects.get(id=19)
print(f'Git Repo: {fabric.git_repository}')
print(f'CRD Count: {fabric.cached_crd_count}')
"
```

#### LIE TYPE 2: "Authentication is working"
**Evidence of lie**:
- `repo.test_connection()` returns `success: False`
- `repo.connection_status` is still `'pending'`
- Repository clone fails in test
- `encrypted_credentials` field is empty

**Verification command**:
```bash
# This should show success: True
sudo docker exec netbox-docker-netbox-1 python3 manage.py shell -c "
repo = GitRepository.objects.get(id=6)
result = repo.test_connection()
print(f'Success: {result[\"success\"]}')
print(f'Status: {repo.connection_status}')
"
```

#### LIE TYPE 3: "GUI workflow is tested"
**Evidence of lie**:
- Cannot provide screenshot of working sync
- Manual GUI test fails 
- Sync button returns HTTP error
- No visual evidence of updated CRD counts

**Verification**: Manual GUI test must be performed and documented

#### LIE TYPE 4: "Configuration is fixed"
**Evidence of lie**:
- `gitops_directory` is still `'/'`
- Fabric still not linked to GitRepository
- Required fields still have wrong values

**Verification command**:
```bash
# This should show proper directory and linked repo
sudo docker exec netbox-docker-netbox-1 python3 manage.py shell -c "
fabric = HedgehigFabric.objects.get(id=19)
print(f'Directory: {fabric.gitops_directory}')
print(f'Repo Link: {fabric.git_repository}')
"
```

## QUALITY GATES

### Gate 1: Pre-Implementation
- [ ] All failing tests written and documented
- [ ] Current broken state confirmed with evidence
- [ ] Expected behavior clearly specified

### Gate 2: Configuration Fixed
- [ ] `fabric.git_repository` properly set to GitRepository ID 6
- [ ] `fabric.gitops_directory` set to `'gitops/hedgehog/fabric-1/'`
- [ ] Repository authentication test passes
- [ ] Repository content validation passes

### Gate 3: Sync Implementation  
- [ ] `fabric.trigger_gitops_sync()` returns `success: True`
- [ ] Database shows created CRD records after sync
- [ ] Fabric cached counts are updated correctly
- [ ] Sync is idempotent (can run multiple times safely)

### Gate 4: GUI Integration
- [ ] Sync button exists on fabric detail page
- [ ] Button triggers actual sync operation
- [ ] Success/error messages display correctly
- [ ] Updated CRD counts appear on page after sync

### Gate 5: End-to-End Validation
- [ ] Complete user workflow test passes
- [ ] GUI screenshots show working functionality
- [ ] Database verification confirms data creation
- [ ] All regression tests pass

## INDEPENDENT VERIFICATION STEPS

### QAPM Verification Checklist

As the Quality Assurance Project Manager, I will verify all agent claims by:

#### 1. Direct Database Inspection
```bash
# Run this exact command to verify claims
sudo docker exec netbox-docker-netbox-1 python3 manage.py shell -c "
from netbox_hedgehog.models.fabric import HedgehogFabric
from netbox_hedgehog.models.vpc_api import VPC
from netbox_hedgehog.models.wiring_api import Connection, Switch

fabric = HedgehogFabric.objects.get(id=19)
print('VERIFICATION RESULTS:')
print(f'Git Repository FK: {fabric.git_repository}')
print(f'GitOps Directory: {fabric.gitops_directory}')
print(f'VPCs: {VPC.objects.filter(fabric=fabric).count()}')
print(f'Connections: {Connection.objects.filter(fabric=fabric).count()}')
print(f'Switches: {Switch.objects.filter(fabric=fabric).count()}')
print(f'Cached Count: {fabric.cached_crd_count}')
print(f'Last Sync: {fabric.last_git_sync}')

if fabric.git_repository:
    result = fabric.git_repository.test_connection()
    print(f'Auth Test: {result[\"success\"]}')
"
```

#### 2. Manual GUI Testing
- Navigate to http://localhost:8000/plugins/hedgehog/fabrics/19/
- Verify sync button exists and is clickable
- Click sync button and observe results
- Verify CRD counts update on page
- Take screenshots of before/after states

#### 3. Code Review Verification
- Review all code changes made by agent
- Verify configuration bugs are actually fixed
- Check that sync logic handles new architecture correctly
- Confirm no new bugs were introduced

#### 4. Regression Testing
- Run complete test suite to ensure no functionality broken
- Test other fabrics to ensure changes don't affect them
- Verify backwards compatibility with legacy configurations

### Verification Failure Actions

If any verification step fails:

1. **REJECT** agent completion claim immediately
2. **DOCUMENT** specific failures with evidence  
3. **REQUIRE** agent to fix issues and resubmit evidence
4. **ESCALATE** to CEO if agent disputes verification results

## SUCCESS CRITERIA

Agent completion is only accepted when:

1. **All Evidence Provided**: Every mandatory evidence requirement met
2. **All Commands Pass**: Every verification command produces expected output
3. **GUI Screenshots Valid**: Working sync button with visual proof of results
4. **Database Records Created**: Actual CRD objects exist in database
5. **Independent Verification**: QAPM confirms all claims through testing
6. **No Lies Detected**: No false completion patterns identified

## AUTHORITY GRANTS

As Quality Assurance Project Manager, I have authority to:

- **REJECT** any completion claim lacking proper evidence
- **REQUIRE** additional verification from agents making claims
- **ESCALATE** disputes to CEO level for final determination
- **MAINTAIN** this protocol as the definitive standard

## PROTOCOL VERSION

**Version**: 1.0  
**Date**: 2025-07-29  
**Author**: Senior Test Design Specialist Agent  
**Approved By**: Quality Assurance Project Manager  

This protocol is binding for all agents working on HNP fabric sync functionality. No exceptions will be made without CEO approval.