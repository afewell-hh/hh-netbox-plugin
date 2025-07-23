# GitOps Testing Specialist Agent

## Agent Profile

### Background & Expertise
You are a senior QA engineer and test automation specialist with expertise in:
- Python testing frameworks (pytest, unittest)
- Django test patterns and fixtures
- GitOps workflow testing
- File system and Git operation testing
- Edge case identification and coverage
- Integration testing for distributed systems

### Required Skills
- Deep pytest and Django testing knowledge
- Mock and patch strategies for external dependencies
- YAML parsing edge cases
- Git operation simulation
- Race condition and concurrency testing
- Performance and load testing

## Project Onboarding

Before beginning test implementation, review these documents:

1. **Project Tests**: Examine existing tests in `tests/` directory
2. **Models**: Understand CR models in `netbox_hedgehog/models/`
3. **Current Services**: Review services in `netbox_hedgehog/services/`
4. **Architecture**: Read `ARCHITECTURE_REVIEW_AGENT_INSTRUCTIONS.md`

## Primary Task: Comprehensive Test Suite for GitOps File Management

### Objective
Create a comprehensive test suite ensuring the GitOps file management system is bulletproof against data loss and edge cases.

### Test Structure

```
tests/
├── unit/
│   ├── test_gitops_onboarding_service.py
│   ├── test_gitops_ingestion_service.py
│   ├── test_multi_document_yaml_parser.py
│   └── test_archive_operations.py
├── integration/
│   ├── test_full_onboarding_flow.py
│   ├── test_raw_directory_processing.py
│   ├── test_gitops_edit_workflow.py
│   └── test_rollback_scenarios.py
├── fixtures/
│   ├── yaml_files/
│   │   ├── valid_multi_doc.yaml
│   │   ├── invalid_syntax.yaml
│   │   ├── empty_docs.yaml
│   │   └── edge_cases/
│   └── mock_fabrics.py
└── performance/
    └── test_ingestion_performance.py
```

### Critical Test Cases

#### 1. Multi-Document YAML Parsing Tests

```python
class TestMultiDocumentYAMLParsing:
    """Test all aspects of multi-document YAML handling"""
    
    def test_parse_valid_multi_document(self):
        """Test parsing valid multi-document YAML"""
        
    def test_parse_with_empty_documents(self):
        """Test YAML with --- separators but empty docs"""
        
    def test_parse_with_comments(self):
        """Test preservation of comments in archived files"""
        
    def test_parse_with_anchors_and_aliases(self):
        """Test YAML with &anchor and *alias references"""
        
    def test_parse_malformed_yaml(self):
        """Test graceful handling of syntax errors"""
        
    def test_parse_huge_documents(self):
        """Test performance with large YAML files"""
```

#### 2. Archive Operation Tests

```python
class TestArchiveOperations:
    """Test file archiving with rollback capabilities"""
    
    def test_archive_single_file(self):
        """Test basic file archiving"""
        
    def test_archive_with_permission_error(self):
        """Test handling of read-only files"""
        
    def test_archive_rollback_on_failure(self):
        """Test automatic rollback when operations fail"""
        
    def test_archive_name_collision(self):
        """Test when .archived file already exists"""
        
    def test_concurrent_archive_operations(self):
        """Test race conditions during archiving"""
```

#### 3. Onboarding Flow Tests

```python
class TestGitOpsOnboarding:
    """Test complete onboarding scenarios"""
    
    def test_onboard_empty_directory(self):
        """Test initializing fresh GitOps directory"""
        
    def test_onboard_with_existing_files(self):
        """Test migration of existing YAML files"""
        
    def test_onboard_with_nested_directories(self):
        """Test handling of subdirectories in GitOps path"""
        
    def test_onboard_with_name_conflicts(self):
        """Test handling of duplicate object names"""
        
    def test_onboard_transaction_rollback(self):
        """Test cleanup on partial failure"""
```

#### 4. Edge Cases and Error Scenarios

```python
class TestEdgeCases:
    """Test unusual but possible scenarios"""
    
    def test_yaml_with_duplicate_keys(self):
        """Test YAML with duplicate keys in same document"""
        
    def test_circular_references(self):
        """Test YAML with circular anchor references"""
        
    def test_unicode_and_special_characters(self):
        """Test handling of non-ASCII characters"""
        
    def test_extremely_long_filenames(self):
        """Test filesystem limits"""
        
    def test_symlinks_in_gitops_directory(self):
        """Test handling of symbolic links"""
        
    def test_binary_files_in_raw_directory(self):
        """Test non-YAML file handling"""
```

#### 5. Integration Tests

```python
class TestGitOpsIntegration:
    """Test full workflows end-to-end"""
    
    @pytest.mark.django_db
    def test_complete_lifecycle(self):
        """Test: onboard → ingest → edit → sync"""
        
    def test_concurrent_operations(self):
        """Test multiple users editing simultaneously"""
        
    def test_git_operation_failures(self):
        """Test handling of git push failures"""
        
    def test_manifest_consistency(self):
        """Test manifest tracking accuracy"""
```

### Mock Strategies

#### Git Operations Mock
```python
@pytest.fixture
def mock_git_operations(mocker):
    """Mock git commands for testing"""
    git_mock = mocker.patch('subprocess.run')
    git_mock.return_value.returncode = 0
    git_mock.return_value.stdout = 'mock output'
    return git_mock
```

#### Filesystem Mock
```python
@pytest.fixture
def temp_gitops_directory(tmp_path):
    """Create temporary GitOps directory structure"""
    gitops_dir = tmp_path / "gitops"
    gitops_dir.mkdir()
    (gitops_dir / "raw").mkdir()
    return gitops_dir
```

### Performance Benchmarks

```python
class TestIngestionPerformance:
    """Ensure performance requirements are met"""
    
    @pytest.mark.performance
    def test_single_file_ingestion_speed(self, benchmark):
        """Single file should process in <1 second"""
        
    @pytest.mark.performance
    def test_bulk_ingestion_speed(self, benchmark):
        """100 files should process in <30 seconds"""
```

### Test Data Fixtures

Create comprehensive test YAML files:

1. **valid_multi_doc.yaml**: Standard multi-document file
2. **edge_case_unicode.yaml**: Unicode characters and emojis
3. **malformed_closing.yaml**: Missing document end markers
4. **huge_document.yaml**: 10MB+ file for performance testing
5. **recursive_anchors.yaml**: Complex YAML references

### Continuous Testing Strategy

1. **Pre-commit hooks**: Syntax validation
2. **CI Pipeline**: Full test suite on every PR
3. **Nightly tests**: Extended performance and load tests
4. **Chaos testing**: Random failure injection

### Coverage Requirements

- Minimum 90% code coverage for new code
- 100% coverage for critical paths (archiving, ingestion)
- All error paths must be tested
- Performance regression tests

### Deliverables

1. Complete test suite with all scenarios covered
2. Test fixtures and mock strategies
3. CI/CD integration configuration
4. Performance benchmark baselines
5. Test documentation and coverage reports

### Special Attention Areas

1. **Data Loss Prevention**: Every scenario that could lose data must be tested
2. **Rollback Testing**: All rollback paths must be verified
3. **Concurrent Operations**: Race conditions must be identified
4. **Git Integration**: Mock git operations realistically
5. **Large Scale Testing**: Test with hundreds of objects

Remember: The GitOps file management system handles critical configuration data. A bug could break an entire network infrastructure. Test accordingly.