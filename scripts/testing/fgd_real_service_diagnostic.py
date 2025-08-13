#!/usr/bin/env python3
"""
Real Service FGD Ingestion Diagnostic Script

This script directly calls the actual GitOpsIngestionService methods
to identify where the exact failure occurs.
"""

import os
import sys
import logging
from pathlib import Path

# Set up comprehensive logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/tmp/fgd_real_service_diagnostic.log')
    ]
)

logger = logging.getLogger(__name__)

# Add project path for imports
sys.path.insert(0, '/home/ubuntu/cc/hedgehog-netbox-plugin')

def test_service_imports():
    """Test if we can import the real service"""
    logger.info("=== TESTING SERVICE IMPORTS ===")
    
    try:
        # Mock Django for imports
        sys.modules['django.utils.timezone'] = type('module', (), {
            'timezone': type('timezone', (), {'now': lambda: 'mock_time'})()
        })()
        sys.modules['django.db.transaction'] = type('module', (), {
            'transaction': type('transaction', (), {'atomic': lambda: type('atomic', (), {'__enter__': lambda self: self, '__exit__': lambda self, *args: None})()})()
        })()
        
        from netbox_hedgehog.services.gitops_ingestion_service import GitOpsIngestionService
        logger.info("✅ Successfully imported GitOpsIngestionService")
        return GitOpsIngestionService
        
    except ImportError as e:
        logger.error(f"❌ Failed to import GitOpsIngestionService: {e}")
        return None
    except Exception as e:
        logger.error(f"❌ Unexpected error importing service: {e}")
        return None

def test_service_initialization(service_class):
    """Test if we can initialize the service"""
    logger.info("=== TESTING SERVICE INITIALIZATION ===")
    
    try:
        # Mock fabric
        mock_fabric = type('MockFabric', (), {
            'name': 'Test Fabric for GitOps Initialization',
            'id': 31,
            'kubernetes_namespace': 'default'
        })()
        
        service = service_class(mock_fabric)
        logger.info("✅ Successfully created GitOpsIngestionService instance")
        logger.info(f"Service fabric: {service.fabric.name}")
        logger.info(f"Service kind_to_directory keys: {list(service.kind_to_directory.keys())}")
        return service
        
    except Exception as e:
        logger.error(f"❌ Failed to create service instance: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return None

def test_path_initialization(service):
    """Test path initialization"""
    logger.info("=== TESTING PATH INITIALIZATION ===")
    
    try:
        # Set base path manually to our test directory
        service.base_path = "/tmp/hedgehog-repos/test-fabric-gitops-mvp2/fabrics/test-fabric-gitops-mvp2/gitops"
        
        # Call _initialize_paths
        service._initialize_paths()
        
        logger.info(f"✅ Paths initialized successfully")
        logger.info(f"Raw path: {service.raw_path}")
        logger.info(f"Managed path: {service.managed_path}")
        logger.info(f"Metadata path: {service.metadata_path}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Path initialization failed: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

def test_yaml_file_processing(service):
    """Test processing of actual YAML files"""
    logger.info("=== TESTING YAML FILE PROCESSING ===")
    
    try:
        test_file = Path("/tmp/hedgehog-repos/test-fabric-gitops-mvp2/fabrics/test-fabric-gitops-mvp2/gitops/raw/test-vpc.yaml")
        
        if not test_file.exists():
            logger.error(f"❌ Test file not found: {test_file}")
            return False
        
        logger.info(f"Testing with file: {test_file}")
        
        # Parse the file
        documents = service._parse_multi_document_yaml(test_file)
        logger.info(f"✅ Parsed {len(documents)} documents")
        
        for i, doc in enumerate(documents):
            logger.info(f"Document {i+1}: {doc.get('kind', 'Unknown')} - {doc.get('metadata', {}).get('name', 'Unnamed')}")
            
            # Test document validation
            is_valid = service._is_valid_k8s_document(doc)
            logger.info(f"  Valid K8s document: {is_valid}")
            
            # Test normalization
            try:
                normalized = service._normalize_document_to_file(doc, test_file, i)
                if normalized:
                    logger.info(f"✅ Successfully normalized document {i+1}")
                    logger.info(f"  Created file info: {normalized}")
                else:
                    logger.warning(f"⚠️  Document {i+1} returned None from normalization")
                    
            except Exception as norm_e:
                logger.error(f"❌ Normalization failed for document {i+1}: {norm_e}")
                import traceback
                logger.error(f"Normalization traceback: {traceback.format_exc()}")
        
        # Check ingestion result
        logger.info(f"Files created in result: {len(service.ingestion_result['files_created'])}")
        for created_file in service.ingestion_result['files_created']:
            logger.info(f"  - {created_file}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ YAML processing failed: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

def test_file_creation_methods(service):
    """Test the file creation methods directly"""
    logger.info("=== TESTING FILE CREATION METHODS ===")
    
    try:
        # Test managed directory creation
        target_dir = Path(service.managed_path) / "vpcs"
        logger.info(f"Testing directory creation: {target_dir}")
        
        target_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"✅ Directory created: {target_dir.exists()}")
        
        # Test filename generation
        test_filename = service._generate_managed_filename(target_dir, "test-vpc", "default")
        logger.info(f"✅ Generated filename: {test_filename}")
        
        # Test YAML writing with a simple document
        test_doc = {
            'apiVersion': 'test/v1',
            'kind': 'VPC',
            'metadata': {'name': 'test-vpc', 'namespace': 'default'},
            'spec': {'vlan': 100}
        }
        
        # Add annotations
        service._add_hnp_annotations(test_doc, Path("test.yaml"), 0)
        logger.info(f"✅ Added annotations to document")
        
        # Write YAML (test with temporary file)
        temp_file = target_dir / "diagnostic-test.yaml"
        service._write_normalized_yaml(test_doc, temp_file)
        
        if temp_file.exists():
            logger.info(f"✅ YAML file written successfully: {temp_file}")
            with open(temp_file, 'r') as f:
                content = f.read()
                logger.info(f"File content length: {len(content)} chars")
        else:
            logger.error(f"❌ YAML file was not created: {temp_file}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ File creation methods failed: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

def main():
    """Execute real service diagnostic test"""
    logger.info("=== REAL SERVICE FGD INGESTION DIAGNOSTIC TEST STARTING ===")
    
    # Test 1: Service imports
    service_class = test_service_imports()
    if not service_class:
        return False
    
    # Test 2: Service initialization
    service = test_service_initialization(service_class)
    if not service:
        return False
    
    # Test 3: Path initialization
    if not test_path_initialization(service):
        return False
    
    # Test 4: File creation methods
    if not test_file_creation_methods(service):
        return False
    
    # Test 5: YAML file processing
    if not test_yaml_file_processing(service):
        return False
    
    logger.info("=== REAL SERVICE DIAGNOSTIC TEST COMPLETED ===")
    logger.info("📄 Full diagnostic log saved to: /tmp/fgd_real_service_diagnostic.log")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)