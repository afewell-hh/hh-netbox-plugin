#!/usr/bin/env python3
"""
Standalone FGD Ingestion Diagnostic Script

This script tests the FGD ingestion process without requiring Django setup.
It directly tests the ingestion flow to identify the exact failure point.

Target: "Test Fabric for GitOps Initialization" test data
"""

import os
import sys
import logging
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

# Set up comprehensive logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/tmp/fgd_standalone_diagnostic.log')
    ]
)

logger = logging.getLogger(__name__)

# Mock fabric object for testing
class MockFabric:
    def __init__(self, name: str, gitops_directory: str):
        self.name = name
        self.id = 31  # Test fabric ID
        self.gitops_directory = gitops_directory
        self.kubernetes_namespace = 'default'
        
    @property
    def created(self):
        return datetime.now()

class MockTimezone:
    @staticmethod
    def now():
        return datetime.now()

# Mock transaction for testing
class MockTransaction:
    @staticmethod
    def atomic():
        return MockAtomic()

class MockAtomic:
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

# Create mock modules
sys.modules['django.utils.timezone'] = type('module', (), {'timezone': MockTimezone()})()
sys.modules['django.db.transaction'] = type('module', (), {'transaction': MockTransaction()})()

def test_fabric_directory_structure():
    """Test different possible fabric directory locations"""
    logger.info("=== TESTING FABRIC DIRECTORY STRUCTURE ===")
    
    possible_paths = [
        "/tmp/hedgehog-repos/test-fabric-gitops-mvp2/fabrics/test-fabric-gitops-mvp2/gitops",
        "/tmp/hedgehog-repos/Test Fabric for GitOps Initialization/fabrics/Test Fabric for GitOps Initialization/gitops", 
        "/tmp/hedgehog-repos/gitops/hedgehog/fabric-1",
        "/tmp/gitops/hedgehog/fabric-1",
        "/home/ubuntu/gitops/hedgehog/fabric-1",
        "/var/tmp/gitops/hedgehog/fabric-1"
    ]
    
    found_paths = []
    for path in possible_paths:
        p = Path(path)
        if p.exists():
            logger.info(f"✅ Found directory: {path}")
            raw_path = p / "raw"
            managed_path = p / "managed"
            logger.info(f"  Raw path exists: {raw_path.exists()}")
            logger.info(f"  Managed path exists: {managed_path.exists()}")
            
            if raw_path.exists():
                raw_files = list(raw_path.glob('*.yaml')) + list(raw_path.glob('*.yml'))
                logger.info(f"  Raw files: {len(raw_files)}")
                for f in raw_files:
                    logger.info(f"    - {f.name} ({f.stat().st_size} bytes)")
                found_paths.append(path)
        else:
            logger.info(f"❌ Not found: {path}")
    
    return found_paths

def create_test_ingestion_service(fabric, base_path):
    """Create a test version of GitOpsIngestionService with diagnostic logging"""
    
    class TestGitOpsIngestionService:
        def __init__(self, fabric):
            self.fabric = fabric
            self.raw_path = None
            self.managed_path = None  
            self.metadata_path = None
            self.base_path = base_path
            
            # CRD kind to directory mapping
            self.kind_to_directory = {
                'VPC': 'vpcs',
                'External': 'externals',
                'ExternalAttachment': 'externalattachments',
                'ExternalPeering': 'externalpeerings',
                'IPv4Namespace': 'ipv4namespaces',
                'VPCAttachment': 'vpcattachments',
                'VPCPeering': 'vpcpeerings',
                'Connection': 'connections',
                'Server': 'servers',
                'Switch': 'switches',
                'SwitchGroup': 'switchgroups',
                'VLANNamespace': 'vlannamespaces'
            }
            
            self.ingestion_result = {
                'success': False,
                'fabric_name': fabric.name,
                'started_at': datetime.now(),
                'files_processed': [],
                'documents_extracted': [],
                'files_created': [],
                'files_archived': [],
                'errors': [],
                'warnings': []
            }
        
        def _initialize_paths(self):
            """Initialize all required paths"""
            logger.info("TEST DIAGNOSTIC: Initializing paths...")
            try:
                base_path = Path(self.base_path)
                self.raw_path = base_path / "raw"
                self.managed_path = base_path / "managed"
                self.metadata_path = base_path / "metadata"
                
                logger.info(f"TEST DIAGNOSTIC: Base path: {base_path}")
                logger.info(f"TEST DIAGNOSTIC: Raw path: {self.raw_path}")
                logger.info(f"TEST DIAGNOSTIC: Managed path: {self.managed_path}")
                logger.info(f"TEST DIAGNOSTIC: Metadata path: {self.metadata_path}")
                
            except Exception as e:
                logger.error(f"TEST DIAGNOSTIC: Path initialization failed: {e}")
                raise
        
        def _validate_structure(self) -> bool:
            """Validate GitOps directory structure exists"""
            logger.info("TEST DIAGNOSTIC: Validating structure...")
            try:
                raw_exists = Path(self.raw_path).exists()
                managed_exists = Path(self.managed_path).exists()
                logger.info(f"TEST DIAGNOSTIC: Raw exists: {raw_exists}")
                logger.info(f"TEST DIAGNOSTIC: Managed exists: {managed_exists}")
                return raw_exists and managed_exists
            except Exception as e:
                logger.error(f"TEST DIAGNOSTIC: Structure validation failed: {e}")
                return False
        
        def _find_yaml_files_in_raw(self) -> List[Path]:
            """Find all YAML files in raw directory"""
            logger.info("TEST DIAGNOSTIC: Finding YAML files...")
            try:
                raw_path = Path(self.raw_path)
                yaml_files = list(raw_path.glob('*.yaml')) + list(raw_path.glob('*.yml'))
                logger.info(f"TEST DIAGNOSTIC: Found {len(yaml_files)} YAML files")
                for f in yaml_files:
                    logger.info(f"TEST DIAGNOSTIC: File - {f.name} ({f.stat().st_size} bytes)")
                return yaml_files
            except Exception as e:
                logger.error(f"TEST DIAGNOSTIC: File finding failed: {e}")
                return []
        
        def _process_yaml_file(self, file_path: Path):
            """Process a single YAML file"""
            logger.info(f"TEST DIAGNOSTIC: Processing file {file_path}")
            try:
                with open(file_path, 'r') as f:
                    content = f.read()
                    logger.info(f"TEST DIAGNOSTIC: File content length: {len(content)} chars")
                    
                # Try to parse YAML
                documents = list(yaml.safe_load_all(content))
                logger.info(f"TEST DIAGNOSTIC: Parsed {len(documents)} YAML documents")
                
                for i, doc in enumerate(documents):
                    if doc:
                        logger.info(f"TEST DIAGNOSTIC: Document {i+1}: {doc.get('kind', 'Unknown')} - {doc.get('metadata', {}).get('name', 'Unnamed')}")
                        self.ingestion_result['documents_extracted'].append({
                            'kind': doc.get('kind', 'Unknown'),
                            'name': doc.get('metadata', {}).get('name', 'Unnamed'),
                            'file': str(file_path)
                        })
                
                self.ingestion_result['files_processed'].append(str(file_path))
                logger.info(f"TEST DIAGNOSTIC: Successfully processed {file_path}")
                
            except Exception as e:
                logger.error(f"TEST DIAGNOSTIC: Failed to process {file_path}: {e}")
                raise
        
        def _update_archive_log(self):
            """Mock archive log update"""
            logger.info("TEST DIAGNOSTIC: Updating archive log (mock)")
            pass
        
        def _rollback_changes(self):
            """Mock rollback"""
            logger.info("TEST DIAGNOSTIC: Rolling back changes (mock)")
            pass
        
        def process_raw_directory(self) -> Dict[str, Any]:
            """
            Process all YAML files in the raw/ directory with full diagnostic logging
            """
            try:
                logger.info(f"=== TEST INGESTION DIAGNOSTIC: Starting raw directory processing for fabric {self.fabric.name} ===")
                logger.info(f"TEST INGESTION DIAGNOSTIC: Fabric ID: {self.fabric.id}")
                logger.info(f"TEST INGESTION DIAGNOSTIC: Initial ingestion_result: {self.ingestion_result}")
                
                # Initialize paths
                logger.info("TEST INGESTION DIAGNOSTIC: Calling _initialize_paths()...")
                try:
                    self._initialize_paths()
                    logger.info(f"TEST INGESTION DIAGNOSTIC: Paths initialized - raw: {self.raw_path}, managed: {self.managed_path}, metadata: {self.metadata_path}")
                except Exception as init_e:
                    logger.error(f"TEST INGESTION DIAGNOSTIC: Path initialization failed: {init_e}")
                    raise
                
                # Validate structure exists
                logger.info("TEST INGESTION DIAGNOSTIC: Calling _validate_structure()...")
                try:
                    structure_valid = self._validate_structure()
                    logger.info(f"TEST INGESTION DIAGNOSTIC: Structure validation result: {structure_valid}")
                    if not structure_valid:
                        raise Exception("GitOps structure not properly initialized")
                except Exception as val_e:
                    logger.error(f"TEST INGESTION DIAGNOSTIC: Structure validation failed: {val_e}")
                    raise
                
                # Find all YAML files in raw directory
                logger.info("TEST INGESTION DIAGNOSTIC: Calling _find_yaml_files_in_raw()...")
                try:
                    yaml_files = self._find_yaml_files_in_raw()
                    logger.info(f"TEST INGESTION DIAGNOSTIC: Found {len(yaml_files)} YAML files: {[str(f) for f in yaml_files]}")
                except Exception as find_e:
                    logger.error(f"TEST INGESTION DIAGNOSTIC: File finding failed: {find_e}")
                    raise
                
                if not yaml_files:
                    logger.info("TEST INGESTION DIAGNOSTIC: No files found, returning success early")
                    self.ingestion_result['success'] = True
                    self.ingestion_result['message'] = "No files to process in raw directory"
                    self.ingestion_result['completed_at'] = datetime.now()
                    logger.info(f"TEST INGESTION DIAGNOSTIC: Early return result: {self.ingestion_result}")
                    return self.ingestion_result
                
                # Process each file
                logger.info("TEST INGESTION DIAGNOSTIC: Starting mock transaction...")
                try:
                    with MockTransaction.atomic():
                        logger.info(f"TEST INGESTION DIAGNOSTIC: Processing {len(yaml_files)} files...")
                        for i, yaml_file in enumerate(yaml_files):
                            logger.info(f"TEST INGESTION DIAGNOSTIC: Processing file {i+1}/{len(yaml_files)}: {yaml_file}")
                            try:
                                self._process_yaml_file(yaml_file)
                                logger.info(f"TEST INGESTION DIAGNOSTIC: Successfully processed file {yaml_file}")
                            except Exception as proc_e:
                                logger.error(f"TEST INGESTION DIAGNOSTIC: Failed to process file {yaml_file}: {proc_e}")
                                raise
                        
                        # Update archive log
                        logger.info("TEST INGESTION DIAGNOSTIC: Updating archive log...")
                        try:
                            self._update_archive_log()
                            logger.info("TEST INGESTION DIAGNOSTIC: Archive log updated successfully")
                        except Exception as arch_e:
                            logger.error(f"TEST INGESTION DIAGNOSTIC: Archive log update failed: {arch_e}")
                            raise
                        
                        self.ingestion_result['success'] = True
                        self.ingestion_result['completed_at'] = datetime.now()
                        self.ingestion_result['message'] = f"Successfully processed {len(yaml_files)} files, extracted {len(self.ingestion_result['documents_extracted'])} documents"
                        
                        logger.info(f"TEST INGESTION DIAGNOSTIC: Transaction completed successfully")
                        logger.info(f"TEST INGESTION DIAGNOSTIC: Final result: {self.ingestion_result}")
                        logger.info(f"TEST INGESTION DIAGNOSTIC: Raw directory processing completed for fabric {self.fabric.name}")
                        return self.ingestion_result
                        
                except Exception as trans_e:
                    logger.error(f"TEST INGESTION DIAGNOSTIC: Transaction failed: {trans_e}")
                    raise
                    
            except Exception as e:
                logger.error(f"TEST INGESTION DIAGNOSTIC: Raw directory processing failed for fabric {self.fabric.name}: {str(e)}")
                import traceback
                logger.error(f"TEST INGESTION DIAGNOSTIC: Main exception traceback: {traceback.format_exc()}")
                
                self.ingestion_result['success'] = False
                self.ingestion_result['error'] = str(e)
                self.ingestion_result['completed_at'] = datetime.now()
                
                # Attempt rollback
                logger.info("TEST INGESTION DIAGNOSTIC: Attempting rollback...")
                try:
                    self._rollback_changes()
                    logger.info("TEST INGESTION DIAGNOSTIC: Rollback completed")
                except Exception as rollback_e:
                    logger.error(f"TEST INGESTION DIAGNOSTIC: Rollback failed: {rollback_e}")
                
                logger.info(f"TEST INGESTION DIAGNOSTIC: Final error result: {self.ingestion_result}")
                return self.ingestion_result
    
    return TestGitOpsIngestionService(fabric)

def main():
    """Execute standalone diagnostic test"""
    try:
        logger.info("=== STANDALONE FGD INGESTION DIAGNOSTIC TEST STARTING ===")
        
        # Test directory structure first
        found_paths = test_fabric_directory_structure()
        
        if not found_paths:
            logger.error("❌ No GitOps directories found!")
            logger.info("Creating test directory structure...")
            test_dir = "/tmp/test-gitops-diagnostic"
            os.makedirs(f"{test_dir}/raw", exist_ok=True)
            os.makedirs(f"{test_dir}/managed", exist_ok=True)
            
            # Create test YAML file
            test_yaml = """---
apiVersion: hedgehog.network/v1alpha1
kind: VPC
metadata:
  name: test-vpc
  namespace: default
spec:
  vlan: 100
---
apiVersion: hedgehog.network/v1alpha1  
kind: External
metadata:
  name: test-external
  namespace: default
spec:
  port: eth0
"""
            with open(f"{test_dir}/raw/test-resources.yaml", 'w') as f:
                f.write(test_yaml)
            
            logger.info(f"Created test directory: {test_dir}")
            found_paths = [test_dir]
        
        # Test with first found path
        test_path = found_paths[0]
        logger.info(f"Testing with path: {test_path}")
        
        # Create mock fabric
        fabric = MockFabric("Test Fabric for GitOps Initialization", "gitops/hedgehog/fabric-1")
        logger.info(f"Created mock fabric: {fabric.name} (ID: {fabric.id})")
        
        # Test ingestion service
        logger.info("Creating test ingestion service...")
        ingestion_service = create_test_ingestion_service(fabric, test_path)
        
        # Execute test
        logger.info("=== EXECUTING INGESTION TEST ===")
        result = ingestion_service.process_raw_directory()
        
        logger.info(f"=== TEST RESULTS ===")
        logger.info(f"Success: {result.get('success')}")
        logger.info(f"Message: {result.get('message', 'N/A')}")
        logger.info(f"Error: {result.get('error', 'N/A')}")
        logger.info(f"Files processed: {len(result.get('files_processed', []))}")
        logger.info(f"Documents extracted: {len(result.get('documents_extracted', []))}")
        
        for doc in result.get('documents_extracted', []):
            logger.info(f"  - {doc['kind']}: {doc['name']} (from {doc['file']})")
        
        logger.info("=== STANDALONE FGD INGESTION DIAGNOSTIC TEST COMPLETED ===")
        logger.info("📄 Full diagnostic log saved to: /tmp/fgd_standalone_diagnostic.log")
        
        return result.get('success', False)
        
    except Exception as e:
        logger.error(f"Diagnostic test failed: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)