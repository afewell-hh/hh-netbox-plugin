# GitOps Sync Test Implementation Guide

## Test Framework Architecture

### 1. TEST ORGANIZATION STRUCTURE

```
netbox_hedgehog/tests/
├── gitops/
│   ├── __init__.py
│   ├── test_ingestion_service.py
│   ├── test_fabric_onboarding.py
│   ├── test_directory_manager.py
│   ├── test_edge_cases.py
│   ├── test_performance.py
│   └── fixtures/
│       ├── __init__.py
│       ├── yaml_fixtures.py
│       ├── directory_fixtures.py
│       └── mock_repositories.py
└── integration/
    ├── test_full_gitops_workflow.py
    └── test_fabric_initialization.py
```

### 2. BASE TEST CLASSES

#### 2.1 GitOps Test Base Class
```python
# netbox_hedgehog/tests/gitops/base.py
import tempfile
import shutil
from pathlib import Path
from django.test import TestCase
from unittest.mock import Mock, patch

class GitOpsTestCase(TestCase):
    """Base test case for GitOps functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.mock_fabric = self.create_mock_fabric()
        self.mock_repository = self.create_mock_repository()
    
    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def create_mock_fabric(self):
        """Create mock fabric for testing"""
        fabric = Mock()
        fabric.name = "test-fabric"
        fabric.kubernetes_namespace = "default"
        fabric.gitops_directory = "/fabrics/test-fabric/gitops/"
        return fabric
    
    def create_mock_repository(self):
        """Create mock Git repository"""
        repo = Mock()
        repo.url = "https://github.com/test/repo.git"
        repo.clone_repository.return_value = {
            'success': True,
            'repository_path': self.temp_dir
        }
        return repo
    
    def create_test_directory_structure(self):
        """Create standard GitOps directory structure"""
        base_path = Path(self.temp_dir) / "fabrics" / "test-fabric" / "gitops"
        directories = [
            "raw", "raw/pending", "raw/processed", "raw/errors",
            "unmanaged", "unmanaged/external-configs", "unmanaged/manual-overrides",
            "managed", "managed/vpcs", "managed/connections", "managed/switches",
            "managed/servers", "managed/switch-groups", "managed/metadata",
            ".hnp"
        ]
        
        for directory in directories:
            (base_path / directory).mkdir(parents=True, exist_ok=True)
        
        return base_path
    
    def create_yaml_file(self, content: str, filename: str, directory: str = "raw"):
        """Create a YAML file in the test directory"""
        base_path = Path(self.temp_dir) / "fabrics" / "test-fabric" / "gitops"
        file_path = base_path / directory / filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, 'w') as f:
            f.write(content)
        
        return file_path
```

### 3. YAML FIXTURES

#### 3.1 Valid YAML Fixtures
```python
# netbox_hedgehog/tests/gitops/fixtures/yaml_fixtures.py

VALID_VPC_YAML = """
apiVersion: vpc.hedgehog.io/v1beta1
kind: VPC
metadata:
  name: test-vpc
  namespace: default
  labels:
    environment: test
spec:
  vni: 1000
  subnets:
    - name: subnet-1
      cidr: "10.0.1.0/24"
"""

VALID_SWITCH_YAML = """
apiVersion: wiring.hedgehog.io/v1beta1
kind: Switch
metadata:
  name: leaf-switch-01
  namespace: default
spec:
  role: leaf
  group: leaf-group
  ports:
    - name: Ethernet1
      breakout: "4x25G"
"""

MULTI_DOCUMENT_YAML = """
apiVersion: vpc.hedgehog.io/v1beta1
kind: VPC
metadata:
  name: vpc-1
  namespace: default
spec:
  vni: 2000
---
apiVersion: wiring.hedgehog.io/v1beta1
kind: Switch
metadata:
  name: switch-1
  namespace: default
spec:
  role: leaf
---
apiVersion: wiring.hedgehog.io/v1beta1
kind: Connection
metadata:
  name: connection-1
  namespace: default
spec:
  from:
    device: server-01
    port: eth0
  to:
    device: switch-1
    port: Ethernet1/1
"""

INVALID_YAML_SYNTAX = """
apiVersion: vpc.hedgehog.io/v1beta1
kind: VPC
metadata:
  name: syntax-error-vpc
    invalid_indentation: true
spec:
  - invalid_list_syntax
"""

INVALID_MISSING_FIELDS = """
apiVersion: vpc.hedgehog.io/v1beta1
kind: VPC
metadata:
  # Missing name field
  namespace: default
spec:
  vni: 3000
"""

MIXED_VALID_INVALID = """
apiVersion: vpc.hedgehog.io/v1beta1
kind: VPC
metadata:
  name: valid-vpc
  namespace: default
spec:
  vni: 4000
---
apiVersion: vpc.hedgehog.io/v1beta1
kind: VPC
metadata:
  # Missing name - invalid
  namespace: default
spec:
  vni: 4001
---
apiVersion: wiring.hedgehog.io/v1beta1
kind: Switch
metadata:
  name: valid-switch
  namespace: default
spec:
  role: leaf
"""

EMPTY_YAML = ""

COMMENTS_ONLY_YAML = """
# This file contains only comments
# and no actual YAML content

---

# Another comment block
"""

UNSUPPORTED_KIND_YAML = """
apiVersion: v1
kind: ConfigMap
metadata:
  name: unsupported-config
  namespace: default
data:
  key: value
"""
```

### 4. UNIT TESTS

#### 4.1 GitOps Ingestion Service Tests
```python
# netbox_hedgehog/tests/gitops/test_ingestion_service.py
from django.test import TestCase
from netbox_hedgehog.services.gitops_ingestion_service import GitOpsIngestionService
from .base import GitOpsTestCase
from .fixtures.yaml_fixtures import *

class GitOpsIngestionServiceTest(GitOpsTestCase):
    """Test GitOps ingestion service functionality"""
    
    def setUp(self):
        super().setUp()
        self.ingestion_service = GitOpsIngestionService(self.mock_fabric)
        self.base_path = self.create_test_directory_structure()
    
    def test_process_single_valid_yaml(self):
        """Test processing single valid YAML file"""
        # Create test file
        yaml_file = self.create_yaml_file(VALID_VPC_YAML, "test-vpc.yaml")
        
        # Process file
        result = self.ingestion_service.process_single_file(yaml_file)
        
        # Assertions
        self.assertTrue(result['success'])
        self.assertEqual(result['documents_extracted'], 1)
        self.assertEqual(len(result['files_created']), 1)
        
        created_file = result['files_created'][0]
        self.assertEqual(created_file['kind'], 'VPC')
        self.assertEqual(created_file['name'], 'test-vpc')
        self.assertEqual(created_file['namespace'], 'default')
        
        # Verify managed file created
        managed_file_path = self.base_path / "managed/vpcs/test-vpc.yaml"
        self.assertTrue(managed_file_path.exists())
        
        # Verify original file archived
        archived_file_path = yaml_file.with_suffix('.yaml.archived')
        self.assertTrue(archived_file_path.exists())
    
    def test_process_multi_document_yaml(self):
        """Test processing multi-document YAML file"""
        yaml_file = self.create_yaml_file(MULTI_DOCUMENT_YAML, "multi-doc.yaml")
        
        result = self.ingestion_service.process_single_file(yaml_file)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['documents_extracted'], 3)
        
        # Verify managed files created
        expected_files = [
            "managed/vpcs/vpc-1.yaml",
            "managed/switches/switch-1.yaml", 
            "managed/connections/connection-1.yaml"
        ]
        
        for expected_file in expected_files:
            file_path = self.base_path / expected_file
            self.assertTrue(file_path.exists(), f"Expected file {expected_file} not created")
    
    def test_process_invalid_yaml_syntax(self):
        """Test handling of YAML syntax errors"""
        yaml_file = self.create_yaml_file(INVALID_YAML_SYNTAX, "invalid-syntax.yaml")
        
        result = self.ingestion_service.process_single_file(yaml_file)
        
        self.assertFalse(result['success'])
        self.assertIn('YAML parsing error', result['error'])
        
        # Verify file not archived (remains in raw)
        self.assertTrue(yaml_file.exists())
        archived_file = yaml_file.with_suffix('.yaml.archived')
        self.assertFalse(archived_file.exists())
    
    def test_process_missing_required_fields(self):
        """Test handling of documents missing required fields"""
        yaml_file = self.create_yaml_file(INVALID_MISSING_FIELDS, "missing-fields.yaml")
        
        result = self.ingestion_service.process_single_file(yaml_file)
        
        # Should succeed but with warnings
        self.assertTrue(result['success'])
        self.assertEqual(result['documents_extracted'], 0)
        
        # File should be archived even though no documents processed
        archived_file = yaml_file.with_suffix('.yaml.archived')
        self.assertTrue(archived_file.exists())
    
    def test_process_mixed_valid_invalid(self):
        """Test processing file with mix of valid and invalid documents"""
        yaml_file = self.create_yaml_file(MIXED_VALID_INVALID, "mixed-validity.yaml")
        
        result = self.ingestion_service.process_single_file(yaml_file)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['documents_extracted'], 2)  # Only valid documents
        
        # Verify only valid documents created managed files
        vpc_file = self.base_path / "managed/vpcs/valid-vpc.yaml"
        switch_file = self.base_path / "managed/switches/valid-switch.yaml"
        
        self.assertTrue(vpc_file.exists())
        self.assertTrue(switch_file.exists())
    
    def test_process_empty_file(self):
        """Test handling of empty YAML file"""
        yaml_file = self.create_yaml_file(EMPTY_YAML, "empty.yaml")
        
        result = self.ingestion_service.process_single_file(yaml_file)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['documents_extracted'], 0)
        
        # Empty file should be archived
        archived_file = yaml_file.with_suffix('.yaml.archived')
        self.assertTrue(archived_file.exists())
    
    def test_process_comments_only_file(self):
        """Test handling of file with only comments"""
        yaml_file = self.create_yaml_file(COMMENTS_ONLY_YAML, "comments-only.yaml")
        
        result = self.ingestion_service.process_single_file(yaml_file)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['documents_extracted'], 0)
    
    def test_process_unsupported_kind(self):
        """Test handling of unsupported Kubernetes kinds"""
        yaml_file = self.create_yaml_file(UNSUPPORTED_KIND_YAML, "unsupported.yaml")
        
        result = self.ingestion_service.process_single_file(yaml_file)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['documents_extracted'], 0)  # Unsupported kind skipped
    
    def test_hnp_annotations_added(self):
        """Test that HNP tracking annotations are added to managed files"""
        yaml_file = self.create_yaml_file(VALID_VPC_YAML, "annotation-test.yaml")
        
        result = self.ingestion_service.process_single_file(yaml_file)
        
        # Read managed file and verify annotations
        managed_file = self.base_path / "managed/vpcs/test-vpc.yaml"
        
        import yaml
        with open(managed_file, 'r') as f:
            # Skip header comments
            content = f.read()
            yaml_content = yaml.safe_load(content.split('---\n', 1)[1])
        
        annotations = yaml_content['metadata']['annotations']
        
        self.assertEqual(annotations['hnp.githedgehog.com/managed-by'], 'hedgehog-netbox-plugin')
        self.assertEqual(annotations['hnp.githedgehog.com/fabric'], 'test-fabric')
        self.assertEqual(annotations['hnp.githedgehog.com/original-file'], 'annotation-test.yaml')
        self.assertEqual(annotations['hnp.githedgehog.com/original-document-index'], '0')
        self.assertIn('hnp.githedgehog.com/ingested-at', annotations)
    
    def test_naming_conflict_resolution(self):
        """Test handling of file naming conflicts in managed directory"""
        # Create initial file
        vpc_content = VALID_VPC_YAML
        managed_dir = self.base_path / "managed/vpcs"
        managed_dir.mkdir(parents=True, exist_ok=True)
        
        # Create existing file with same name
        existing_file = managed_dir / "test-vpc.yaml"
        with open(existing_file, 'w') as f:
            f.write(vpc_content)
        
        # Process new file with same VPC name
        yaml_file = self.create_yaml_file(vpc_content, "conflict-test.yaml")
        result = self.ingestion_service.process_single_file(yaml_file)
        
        self.assertTrue(result['success'])
        
        # Verify conflict resolution - should create test-vpc-1.yaml
        conflict_file = managed_dir / "test-vpc-1.yaml"
        self.assertTrue(conflict_file.exists())
    
    def test_batch_processing_order(self):
        """Test that files are processed in modification time order"""
        import time
        
        # Create files with different modification times
        file1 = self.create_yaml_file(VALID_VPC_YAML.replace("test-vpc", "vpc-1"), "first.yaml")
        time.sleep(0.1)
        file2 = self.create_yaml_file(VALID_VPC_YAML.replace("test-vpc", "vpc-2"), "second.yaml")
        time.sleep(0.1)
        file3 = self.create_yaml_file(VALID_VPC_YAML.replace("test-vpc", "vpc-3"), "third.yaml")
        
        # Process raw directory
        result = self.ingestion_service.process_raw_directory()
        
        self.assertTrue(result['success'])
        self.assertEqual(len(result['files_processed']), 3)
        
        # Verify processing order (oldest first)
        processed_files = [f['original_path'] for f in result['files_processed']]
        self.assertEqual(processed_files[0], str(file1))
        self.assertEqual(processed_files[1], str(file2))
        self.assertEqual(processed_files[2], str(file3))
```

#### 4.2 Directory Manager Tests
```python
# netbox_hedgehog/tests/gitops/test_directory_manager.py
from netbox_hedgehog.services.bidirectional_sync.gitops_directory_manager import GitOpsDirectoryManager
from .base import GitOpsTestCase

class GitOpsDirectoryManagerTest(GitOpsTestCase):
    """Test GitOps directory manager functionality"""
    
    def setUp(self):
        super().setUp()
        self.mock_fabric.git_repository = self.mock_repository
        self.directory_manager = GitOpsDirectoryManager(self.mock_fabric)
    
    def test_initialize_directory_structure(self):
        """Test initialization of complete directory structure"""
        result = self.directory_manager.initialize_directory_structure()
        
        self.assertTrue(result.success)
        self.assertGreater(len(result.directories_created), 10)
        
        # Verify all standard directories created
        base_path = Path(self.temp_dir) / "fabrics" / "test-fabric" / "gitops"
        
        expected_dirs = [
            "raw", "raw/pending", "raw/processed", "raw/errors",
            "unmanaged", "unmanaged/external-configs", "unmanaged/manual-overrides",
            "managed", "managed/vpcs", "managed/connections", "managed/switches",
            "managed/servers", "managed/switch-groups", "managed/metadata"
        ]
        
        for expected_dir in expected_dirs:
            dir_path = base_path / expected_dir
            self.assertTrue(dir_path.exists(), f"Directory {expected_dir} not created")
    
    def test_validate_directory_structure_valid(self):
        """Test validation of valid directory structure"""
        # Initialize structure first
        self.directory_manager.initialize_directory_structure()
        
        # Validate structure
        result = self.directory_manager.validate_directory_structure()
        
        self.assertTrue(result.valid)
        self.assertEqual(len(result.issues), 0)
        self.assertEqual(len(result.missing_directories), 0)
    
    def test_validate_directory_structure_missing_dirs(self):
        """Test validation with missing directories"""
        # Create incomplete structure
        base_path = Path(self.temp_dir) / "fabrics" / "test-fabric" / "gitops"
        (base_path / "raw").mkdir(parents=True, exist_ok=True)
        
        result = self.directory_manager.validate_directory_structure()
        
        self.assertFalse(result.valid)
        self.assertGreater(len(result.missing_directories), 0)
        self.assertGreater(len(result.issues), 0)
    
    def test_get_directory_status(self):
        """Test directory status reporting"""
        # Initialize and add some test files
        self.directory_manager.initialize_directory_structure()
        base_path = Path(self.temp_dir) / "fabrics" / "test-fabric" / "gitops"
        
        # Add test files
        (base_path / "raw" / "test.yaml").write_text("test: content")
        (base_path / "managed" / "vpcs" / "vpc.yaml").write_text("vpc: content")
        
        status = self.directory_manager.get_directory_status()
        
        self.assertTrue(status['initialized'])
        self.assertTrue(status['structure_valid'])
        self.assertGreater(status['directories']['raw']['file_count'], 0)
        self.assertGreater(status['directories']['managed']['file_count'], 0)
```

### 5. INTEGRATION TESTS

#### 5.1 Full Workflow Integration Test
```python
# netbox_hedgehog/tests/integration/test_full_gitops_workflow.py
from django.test import TransactionTestCase
from netbox_hedgehog.models import HedgehogFabric, GitRepository
from netbox_hedgehog.services.gitops_ingestion_service import GitOpsIngestionService
from netbox_hedgehog.services.bidirectional_sync.gitops_directory_manager import GitOpsDirectoryManager

class FullGitOpsWorkflowTest(TransactionTestCase):
    """Integration test for complete GitOps workflow"""
    
    def setUp(self):
        """Set up integration test environment"""
        self.git_repo = GitRepository.objects.create(
            name="test-repo",
            url="https://github.com/test/repo.git",
            # Add other required fields
        )
        
        self.fabric = HedgehogFabric.objects.create(
            name="integration-test-fabric",
            git_repository=self.git_repo,
            gitops_directory="/fabrics/integration-test-fabric/gitops/",
            # Add other required fields
        )
    
    def test_complete_fabric_initialization_workflow(self):
        """Test complete workflow from fabric creation to YAML processing"""
        # Step 1: Initialize directory structure
        directory_manager = GitOpsDirectoryManager(self.fabric)
        init_result = directory_manager.initialize_directory_structure()
        
        self.assertTrue(init_result.success)
        
        # Step 2: Add test YAML files to raw directory
        # This would typically be done by user or external process
        # For testing, we'll mock this step
        
        # Step 3: Run ingestion process
        ingestion_service = GitOpsIngestionService(self.fabric)
        ingestion_result = ingestion_service.process_raw_directory()
        
        # Verify end-to-end workflow
        self.assertTrue(ingestion_result['success'])
        
        # Step 4: Verify final state
        final_status = directory_manager.get_directory_status()
        self.assertTrue(final_status['initialized'])
        self.assertTrue(final_status['structure_valid'])
```

### 6. PERFORMANCE TESTS

#### 6.1 Large File Processing Performance
```python
# netbox_hedgehog/tests/gitops/test_performance.py
import time
from .base import GitOpsTestCase
from .fixtures.yaml_fixtures import VALID_VPC_YAML

class GitOpsPerformanceTest(GitOpsTestCase):
    """Performance tests for GitOps operations"""
    
    def test_large_multi_document_processing(self):
        """Test performance with large multi-document files"""
        # Generate large multi-document YAML
        large_yaml = self._generate_large_multi_document(100)
        yaml_file = self.create_yaml_file(large_yaml, "large-multi.yaml")
        
        start_time = time.time()
        result = self.ingestion_service.process_single_file(yaml_file)
        processing_time = time.time() - start_time
        
        self.assertTrue(result['success'])
        self.assertEqual(result['documents_extracted'], 100)
        self.assertLess(processing_time, 30)  # Should complete within 30 seconds
    
    def test_many_small_files_processing(self):
        """Test performance with many small files"""
        # Create 100 small YAML files
        file_count = 100
        for i in range(file_count):
            yaml_content = VALID_VPC_YAML.replace("test-vpc", f"vpc-{i:03d}")
            self.create_yaml_file(yaml_content, f"vpc-{i:03d}.yaml")
        
        start_time = time.time()
        result = self.ingestion_service.process_raw_directory()
        processing_time = time.time() - start_time
        
        self.assertTrue(result['success'])
        self.assertEqual(len(result['files_processed']), file_count)
        self.assertLess(processing_time, 120)  # Should complete within 2 minutes
    
    def _generate_large_multi_document(self, doc_count):
        """Generate large multi-document YAML for testing"""
        documents = []
        for i in range(doc_count):
            doc = VALID_VPC_YAML.replace("test-vpc", f"vpc-{i:03d}")
            doc = doc.replace("vni: 1000", f"vni: {1000 + i}")
            documents.append(doc.strip())
        
        return "\n---\n".join(documents)
```

### 7. TEST EXECUTION AND REPORTING

#### 7.1 Test Runner Configuration
```python
# pytest.ini
[tool:pytest]
DJANGO_SETTINGS_MODULE = netbox.settings
python_files = tests.py test_*.py *_tests.py
python_classes = Test* *Tests
python_functions = test_*
addopts = 
    --verbose
    --tb=short
    --strict-markers
    --disable-warnings
    --cov=netbox_hedgehog.services
    --cov=netbox_hedgehog.utils
    --cov-report=html
    --cov-report=term-missing
markers =
    unit: Unit tests
    integration: Integration tests
    performance: Performance tests
    slow: Slow-running tests
```

#### 7.2 Test Coverage Requirements
- **Unit Tests**: >90% code coverage for GitOps services
- **Integration Tests**: All major workflows covered
- **Edge Cases**: All documented edge cases tested
- **Performance**: Baseline performance metrics established

#### 7.3 Continuous Integration
```yaml
# .github/workflows/gitops-tests.yml
name: GitOps Tests
on: [push, pull_request]

jobs:
  test-gitops:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.9
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-django pytest-cov
      
      - name: Run GitOps unit tests
        run: pytest netbox_hedgehog/tests/gitops/ -m "unit" --cov
      
      - name: Run GitOps integration tests
        run: pytest netbox_hedgehog/tests/integration/ -m "integration"
      
      - name: Run performance tests
        run: pytest netbox_hedgehog/tests/gitops/ -m "performance"
```

This comprehensive test implementation guide provides the framework for thorough testing of all GitOps synchronization functionality, ensuring robust and reliable operation across all scenarios and edge cases.