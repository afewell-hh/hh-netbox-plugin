# HNP Fabric Sync Test Suite Specification

**Mission**: Design comprehensive, fail-safe validation tests for HNP fabric/git synchronization that prevent false completion claims and ensure end-to-end user workflow validation.

## ARCHITECTURAL FINDINGS

Based on comprehensive architectural analysis, the fabric sync system has these critical components:

### Current State Analysis
- **Fabric ID**: 19 (HCKC)
- **Missing GitRepository FK**: `fabric.git_repository = None` (should link to GitRepository ID 6) 
- **Wrong Directory Path**: `gitops_directory = '/'` (should be `'gitops/hedgehog/fabric-1/'`)
- **Repository Available**: GitRepository ID 6 exists but has `connection_status = 'pending'`
- **Legacy Configuration**: Populated with `git_repository_url` but new architecture not linked
- **All CRD Counts**: 0 (expected >0 after successful sync)

### Expected Repository Content
- **Repository**: https://github.com/afewell-hh/gitops-test-1.git  
- **Branch**: main
- **Path**: gitops/hedgehog/fabric-1/ 
- **Files**: prepop.yaml (11KB), test-vpc.yaml, test-vpc-2.yaml
- **Expected CRDs**: VPCs, Connections, Switches from YAML files

## 1. PRE-CONDITION TESTS (Must Pass First)

### 1.1 Database Integrity Tests
```python
def test_fabric_exists():
    """Verify fabric record exists in database"""
    fabric = HedgehogFabric.objects.get(id=19)
    assert fabric.name == "HCKC"
    
def test_git_repository_exists():
    """Verify GitRepository record exists and is accessible"""
    repo = GitRepository.objects.get(id=6)
    assert repo.url == "https://github.com/afewell-hh/gitops-test-1"
    assert repo.name == "GitOps Test Repository 1"

def test_database_models_available():
    """Verify all required model classes can be imported"""
    from netbox_hedgehog.models.fabric import HedgehogFabric
    from netbox_hedgehog.models.git_repository import GitRepository
    from netbox_hedgehog.models.vpc_api import VPC
    from netbox_hedgehog.models.wiring_api import Connection, Switch
    # Must not raise ImportError
```

### 1.2 System State Tests
```python
def test_netbox_container_running():
    """Verify NetBox container is running and accessible"""
    result = subprocess.run(['docker', 'ps'], capture_output=True)
    assert 'netbox-docker-netbox-1' in result.stdout.decode()
    
def test_django_shell_accessible():
    """Verify Django shell commands can be executed"""
    cmd = ['docker', 'exec', 'netbox-docker-netbox-1', 'python3', 'manage.py', 'shell', '-c', 'print("test")']
    result = subprocess.run(cmd, capture_output=True)
    assert result.returncode == 0
```

## 2. CONFIGURATION TESTS

### 2.1 Git Repository Authentication Tests
```python
def test_git_repository_credentials_set():
    """Verify GitRepository has encrypted credentials"""
    repo = GitRepository.objects.get(id=6)
    assert repo.encrypted_credentials != "", "GitRepository must have encrypted credentials"
    
    # Test credential decryption
    credentials = repo.get_credentials()
    assert 'token' in credentials or 'username' in credentials, "Must have valid authentication"

def test_git_repository_connection():
    """Test actual Git repository connection"""
    repo = GitRepository.objects.get(id=6)
    result = repo.test_connection()
    assert result['success'] == True, f"Git connection failed: {result.get('error')}"
    assert result['authenticated'] == True, "Repository connection must be authenticated"
```

### 2.2 Fabric Configuration Tests  
```python
def test_fabric_git_repository_link():
    """CRITICAL: Verify fabric links to GitRepository correctly"""
    fabric = HedgehogFabric.objects.get(id=19)
    
    # This is the core bug - must be fixed before sync can work
    assert fabric.git_repository is not None, "Fabric must link to GitRepository (currently None)"
    assert fabric.git_repository.id == 6, "Fabric must link to correct GitRepository"

def test_fabric_gitops_directory():
    """CRITICAL: Verify fabric has correct GitOps directory path"""
    fabric = HedgehogFabric.objects.get(id=19)
    
    # This is another core bug - wrong path
    assert fabric.gitops_directory != "/", "GitOps directory cannot be root '/'"
    assert fabric.gitops_directory == "gitops/hedgehog/fabric-1/", "Must use correct directory path"
```

## 3. AUTHENTICATION TESTS

### 3.1 Repository Access Tests
```python
def test_repository_clone_with_credentials():
    """Test repository can be cloned with current credentials"""
    repo = GitRepository.objects.get(id=6) 
    
    with tempfile.TemporaryDirectory() as temp_dir:
        result = repo.clone_repository(temp_dir)
        assert result['success'] == True, f"Clone failed: {result.get('error')}"
        
        # Verify expected directory structure exists
        gitops_path = Path(temp_dir) / "gitops" / "hedgehog" / "fabric-1"
        assert gitops_path.exists(), f"Expected GitOps path not found: {gitops_path}"

def test_yaml_files_accessible():
    """Test that expected YAML files exist in repository"""
    repo = GitRepository.objects.get(id=6)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        result = repo.clone_repository(temp_dir)
        assert result['success'] == True
        
        expected_files = ["prepop.yaml", "test-vpc.yaml", "test-vpc-2.yaml"]
        gitops_path = Path(temp_dir) / "gitops" / "hedgehog" / "fabric-1"
        
        for filename in expected_files:
            file_path = gitops_path / filename
            assert file_path.exists(), f"Expected file not found: {file_path}"
            assert file_path.stat().st_size > 0, f"File is empty: {file_path}"
```

### 3.2 Repository Content Validation Tests
```python
def test_yaml_files_parse_correctly():
    """Test that YAML files contain valid Hedgehog CRDs"""
    repo = GitRepository.objects.get(id=6)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        result = repo.clone_repository(temp_dir)
        assert result['success'] == True
        
        gitops_path = Path(temp_dir) / "gitops" / "hedgehog" / "fabric-1"
        yaml_files = list(gitops_path.glob("*.yaml"))
        assert len(yaml_files) >= 3, f"Expected at least 3 YAML files, found {len(yaml_files)}"
        
        crd_count = 0
        for yaml_file in yaml_files:
            with open(yaml_file, 'r') as f:
                docs = list(yaml.safe_load_all(f))
                for doc in docs:
                    if doc and 'kind' in doc and 'metadata' in doc:
                        kind = doc['kind']
                        # Verify it's a Hedgehog CRD
                        hedgehog_kinds = ['VPC', 'Connection', 'Switch', 'Server', 'External']
                        if kind in hedgehog_kinds:
                            crd_count += 1
                            
        assert crd_count > 0, f"No valid Hedgehog CRDs found in repository files"
```

## 4. SYNCHRONIZATION TESTS

### 4.1 Sync Mechanism Tests
```python
def test_fabric_sync_method_exists():
    """Verify fabric has working sync method"""
    fabric = HedgehogFabric.objects.get(id=19)
    assert hasattr(fabric, 'trigger_gitops_sync'), "Fabric must have trigger_gitops_sync method"
    
def test_git_directory_sync_import():
    """Verify Git sync utility can be imported"""
    from netbox_hedgehog.utils.git_directory_sync import sync_fabric_from_git
    # Must not raise ImportError

def test_sync_with_minimal_config():
    """Test sync fails gracefully with current broken config"""
    fabric = HedgehogFabric.objects.get(id=19)
    
    # This should fail because git_repository FK is None
    result = fabric.trigger_gitops_sync()
    assert result['success'] == False, "Sync should fail with broken configuration"
    assert 'git repository' in result.get('error', '').lower(), "Error should mention Git repository"
```

### 4.2 Database Creation Tests
```python
def test_sync_creates_crd_records():
    """CRITICAL: Test that sync actually creates CRD records in database"""
    fabric = HedgehogFabric.objects.get(id=19)
    
    # Fix the configuration first (this is what implementation must do)
    repo = GitRepository.objects.get(id=6)
    fabric.git_repository = repo
    fabric.gitops_directory = "gitops/hedgehog/fabric-1/"
    fabric.save()
    
    # Clear existing CRDs for clean test
    from netbox_hedgehog.models.vpc_api import VPC
    from netbox_hedgehog.models.wiring_api import Connection, Switch
    VPC.objects.filter(fabric=fabric).delete()
    Connection.objects.filter(fabric=fabric).delete()
    Switch.objects.filter(fabric=fabric).delete()
    
    # Run sync
    result = fabric.trigger_gitops_sync()
    
    # Verify sync succeeded
    assert result['success'] == True, f"Sync failed: {result.get('error')}"
    
    # Verify CRDs were created
    vpc_count = VPC.objects.filter(fabric=fabric).count()
    connection_count = Connection.objects.filter(fabric=fabric).count()
    switch_count = Switch.objects.filter(fabric=fabric).count()
    
    total_crds = vpc_count + connection_count + switch_count
    assert total_crds > 0, f"No CRDs created after sync. VPCs: {vpc_count}, Connections: {connection_count}, Switches: {switch_count}"
    
    # Verify fabric counts were updated
    fabric.refresh_from_db()
    assert fabric.cached_crd_count > 0, f"Fabric cached_crd_count not updated: {fabric.cached_crd_count}"
```

## 5. END-USER WORKFLOW TESTS

### 5.1 GUI Authentication Tests
```python
def test_netbox_login_works():
    """Test user can log into NetBox GUI"""
    import requests
    
    session = requests.Session()
    
    # Get login page
    login_url = "http://localhost:8000/login/"
    response = session.get(login_url)
    assert response.status_code == 200, f"Cannot access login page: {response.status_code}"
    
    # Extract CSRF token  
    csrf_token = extract_csrf_token(response.text)
    assert csrf_token, "CSRF token not found in login page"
    
    # Login with admin credentials
    login_data = {
        'username': 'admin',
        'password': 'admin',
        'csrfmiddlewaretoken': csrf_token
    }
    
    response = session.post(login_url, data=login_data)
    assert response.status_code in [200, 302], f"Login failed: {response.status_code}"
    
    # Verify we can access protected pages
    dashboard_response = session.get("http://localhost:8000/plugins/hedgehog/")
    assert dashboard_response.status_code == 200, "Cannot access plugin dashboard after login"
```

### 5.2 Fabric Detail Page Tests
```python
def test_fabric_detail_page_loads():
    """Test fabric detail page loads correctly"""
    session = get_authenticated_session()
    
    fabric_url = "http://localhost:8000/plugins/hedgehog/fabrics/19/"
    response = session.get(fabric_url)
    
    assert response.status_code == 200, f"Fabric detail page failed: {response.status_code}"
    assert "HCKC" in response.text, "Fabric name not found on page"
    assert "Sync Now" in response.text, "Sync button not found on page"

def test_sync_button_exists():
    """Test Sync Now button exists and is clickable"""
    session = get_authenticated_session()
    
    fabric_url = "http://localhost:8000/plugins/hedgehog/fabrics/19/"
    response = session.get(fabric_url)
    
    # Parse HTML to find sync button
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(response.text, 'html.parser')
    sync_button = soup.find('button', text='Sync Now') or soup.find('a', text='Sync Now')
    
    assert sync_button is not None, "Sync Now button not found in fabric detail page"
    
    # Check if button has correct action
    if sync_button.name == 'button':
        form = sync_button.find_parent('form')
        assert form is not None, "Sync button not inside a form"
    else:  # It's a link
        href = sync_button.get('href')
        assert href and 'sync' in href, f"Sync button has invalid href: {href}"
```

### 5.3 End-to-End Sync Workflow Tests
```python
def test_complete_user_sync_workflow():
    """CRITICAL: Test complete user workflow from GUI click to data update"""
    session = get_authenticated_session()
    
    # Step 1: Access fabric detail page
    fabric_url = "http://localhost:8000/plugins/hedgehog/fabrics/19/"
    response = session.get(fabric_url)
    assert response.status_code == 200
    
    # Step 2: Record initial CRD counts
    initial_crd_count = get_fabric_crd_count(19)
    
    # Step 3: Click Sync Now button
    csrf_token = extract_csrf_token(response.text)
    sync_url = "http://localhost:8000/plugins/hedgehog/fabrics/19/sync/"
    
    sync_response = session.post(sync_url, data={'csrfmiddlewaretoken': csrf_token})
    
    # Step 4: Verify sync was triggered (should redirect or show success)
    assert sync_response.status_code in [200, 302], f"Sync request failed: {sync_response.status_code}"
    
    # Step 5: Wait for sync to complete and verify results
    import time
    time.sleep(2)  # Allow sync to complete
    
    final_crd_count = get_fabric_crd_count(19)
    assert final_crd_count > initial_crd_count, f"CRD count not increased: {initial_crd_count} -> {final_crd_count}"
    
    # Step 6: Verify fabric detail page shows updated counts
    final_response = session.get(fabric_url)
    assert str(final_crd_count) in final_response.text, "Updated CRD count not shown on page"
```

## 6. REGRESSION PREVENTION TESTS

### 6.1 Configuration Validation Tests
```python
def test_fabric_git_configuration_validation():
    """Test fabric validates Git configuration correctly"""
    fabric = HedgehogFabric.objects.get(id=19)
    
    # Test with missing GitRepository FK
    fabric.git_repository = None
    with pytest.raises(ValidationError):
        fabric.clean()
    
    # Test with invalid gitops_directory
    fabric.gitops_directory = ""
    with pytest.raises(ValidationError):
        fabric.clean()

def test_sync_fails_without_credentials():
    """Test sync fails gracefully without Git credentials"""
    repo = GitRepository.objects.get(id=6)
    
    # Remove credentials
    repo.encrypted_credentials = ""
    repo.save()
    
    fabric = HedgehogFabric.objects.get(id=19) 
    fabric.git_repository = repo
    fabric.gitops_directory = "gitops/hedgehog/fabric-1/"
    fabric.save()
    
    result = fabric.trigger_gitops_sync()
    assert result['success'] == False, "Sync should fail without credentials"
    assert 'auth' in result.get('error', '').lower(), "Error should mention authentication"
```

### 6.2 Data Consistency Tests
```python
def test_sync_updates_fabric_counts():
    """Test sync properly updates fabric cached counts"""
    fabric = HedgehogFabric.objects.get(id=19)
    
    # Fix configuration and run sync
    repo = GitRepository.objects.get(id=6)
    fabric.git_repository = repo  
    fabric.gitops_directory = "gitops/hedgehog/fabric-1/"
    fabric.save()
    
    result = fabric.trigger_gitops_sync()
    assert result['success'] == True
    
    # Verify counts are updated
    fabric.refresh_from_db()
    actual_vpc_count = VPC.objects.filter(fabric=fabric).count()
    actual_connection_count = Connection.objects.filter(fabric=fabric).count()
    
    assert fabric.vpcs_count == actual_vpc_count, f"VPC count mismatch: cached={fabric.vpcs_count}, actual={actual_vpc_count}"
    assert fabric.connections_count == actual_connection_count, f"Connection count mismatch: cached={fabric.connections_count}, actual={actual_connection_count}"

def test_sync_idempotent():
    """Test multiple syncs don't create duplicate records"""
    fabric = HedgehogFabric.objects.get(id=19)
    
    # Run sync twice
    fabric.trigger_gitops_sync()
    first_count = VPC.objects.filter(fabric=fabric).count()
    
    fabric.trigger_gitops_sync()
    second_count = VPC.objects.filter(fabric=fabric).count()
    
    assert first_count == second_count, f"Sync not idempotent: {first_count} -> {second_count}"
```

## AGENT VALIDATION PROTOCOL

### Mandatory Test Evidence Required

Before any agent can claim sync functionality is working, they MUST provide:

1. **Database Query Evidence**:
   ```bash
   # Show fabric is properly linked to GitRepository
   docker exec netbox-docker-netbox-1 python3 manage.py shell -c "
   from netbox_hedgehog.models.fabric import HedgehogFabric
   fabric = HedgehogFabric.objects.get(id=19)
   print(f'Git Repository FK: {fabric.git_repository}')
   print(f'GitOps Directory: {fabric.gitops_directory}')
   "
   ```

2. **CRD Count Evidence**:
   ```bash
   # Show CRDs were actually created
   docker exec netbox-docker-netbox-1 python3 manage.py shell -c "
   from netbox_hedgehog.models.fabric import HedgehogFabric
   from netbox_hedgehog.models.vpc_api import VPC
   from netbox_hedgehog.models.wiring_api import Connection, Switch
   fabric = HedgehogFabric.objects.get(id=19)
   print(f'VPCs: {VPC.objects.filter(fabric=fabric).count()}')
   print(f'Connections: {Connection.objects.filter(fabric=fabric).count()}')
   print(f'Switches: {Switch.objects.filter(fabric=fabric).count()}')
   print(f'Cached Count: {fabric.cached_crd_count}')
   "
   ```

3. **GUI Screenshot Evidence**:
   - Screenshot of fabric detail page showing non-zero CRD counts
   - Screenshot of Sync Now button working
   - Screenshot of success message after sync

4. **End-to-End Test Evidence**:
   ```python
   # Complete user workflow test must pass
   def test_complete_user_workflow():
       # Login -> Navigate -> Click Sync -> Verify Results
       pass
   ```

### False Completion Detection

The following are signs of agent lies and incomplete work:

**LIE**: "Sync worked" but:
- `fabric.git_repository` is still `None`
- `gitops_directory` is still `'/'`
- All CRD counts are still 0
- GitRepository `connection_status` is still `'pending'`

**LIE**: "Authentication works" but:
- `repo.test_connection()` returns `success: False`
- Repository clone fails in test
- `encrypted_credentials` field is empty

**LIE**: "GUI workflow tested" but:
- Cannot provide screenshot of working sync button
- Cannot demonstrate actual CRD count increase
- Sync button returns error when clicked

**LIE**: "Database updated" but:
- CRD model queries return 0 results
- `fabric.cached_crd_count` is still 0
- No database records created with `fabric_id=19`

### Quality Gates

All tests in this specification must pass before claiming completion:

1. **Pre-Condition Gate**: All pre-condition tests pass
2. **Configuration Gate**: Fabric properly linked to GitRepository  
3. **Authentication Gate**: Repository connection test succeeds
4. **Sync Gate**: Actual CRD records created in database
5. **GUI Gate**: End-to-end user workflow completes successfully

### Independent Verification Steps

Quality Assurance Project Manager will verify agent claims by:

1. **Direct Database Inspection**: Run queries to verify actual data changes
2. **GUI Testing**: Manually test user workflow with screenshots
3. **Code Review**: Verify all configuration bugs are actually fixed
4. **Regression Testing**: Run full test suite to catch any new issues

## SUCCESS CRITERIA

This test suite succeeds when:

1. **All Tests Pass**: Every test in this specification passes
2. **User Workflow Works**: Complete GUI sync workflow functions end-to-end
3. **Data Actually Created**: Real CRD records exist in database after sync
4. **Configuration Fixed**: All architectural bugs identified are resolved
5. **False Claims Impossible**: Comprehensive validation prevents agent lies

## IMPLEMENTATION REQUIREMENTS

### Test-Driven Development Mandates

Before any implementation work begins:

1. **Write Failing Tests First**: Create failing tests for all functionality
2. **Red-Green-Refactor**: Classic TDD cycle must be followed
3. **No Code Without Tests**: All implementation must have corresponding tests
4. **Evidence-Based Completion**: Only test passage proves completion

### Implementation Order

1. **Fix Configuration Bugs**:
   - Link fabric to GitRepository (set `git_repository` FK)
   - Fix GitOps directory path (set to `gitops/hedgehog/fabric-1/`)
   - Set up repository authentication (ensure credentials work)

2. **Implement Sync Functionality**:
   - Ensure `trigger_gitops_sync()` method works
   - Fix `git_directory_sync.py` to handle new architecture
   - Update CRD creation logic

3. **Update GUI**:
   - Ensure Sync Now button triggers actual sync
   - Display real CRD counts after sync
   - Show success/error messages

4. **Validate End-to-End**:
   - Run complete user workflow tests
   - Verify all data is actually created
   - Confirm GUI shows updated information

This test suite represents the gold standard for fabric sync functionality. No agent can claim completion without passing every test with documented evidence.