"""
File Ingestion Pipeline

This module processes files from the raw/ directory through validation to the
managed/ directory, implementing comprehensive YAML validation, classification,
and error handling with rollback capabilities.
"""

import os
import yaml
import logging
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Custom validation error for file processing"""
    pass


class IngestionStage:
    """Represents a stage in the ingestion pipeline"""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.files_processed = 0
        self.files_success = 0
        self.files_failed = 0
        self.errors = []
        self.warnings = []
    
    def add_success(self, file_path: str):
        """Record successful file processing"""
        self.files_processed += 1
        self.files_success += 1
        logger.debug(f"Stage {self.name}: Successfully processed {file_path}")
    
    def add_failure(self, file_path: str, error: str):
        """Record failed file processing"""
        self.files_processed += 1
        self.files_failed += 1
        self.errors.append(f"{file_path}: {error}")
        logger.error(f"Stage {self.name}: Failed to process {file_path}: {error}")
    
    def add_warning(self, file_path: str, warning: str):
        """Record warning during file processing"""
        self.warnings.append(f"{file_path}: {warning}")
        logger.warning(f"Stage {self.name}: Warning for {file_path}: {warning}")
    
    def get_summary(self) -> Dict[str, Any]:
        """Get stage summary"""
        return {
            'name': self.name,
            'description': self.description,
            'files_processed': self.files_processed,
            'files_success': self.files_success,
            'files_failed': self.files_failed,
            'success_rate': (self.files_success / self.files_processed * 100) if self.files_processed > 0 else 0,
            'errors': self.errors,
            'warnings': self.warnings
        }


class ProcessedFile:
    """Information about a processed file"""
    
    def __init__(self, original_path: str, target_path: str = None, 
                 resource_type: str = None, resource_name: str = None,
                 validation_status: str = 'pending', error_message: str = None):
        self.original_path = original_path
        self.target_path = target_path
        self.resource_type = resource_type
        self.resource_name = resource_name
        self.validation_status = validation_status
        self.error_message = error_message
        self.processed_at = timezone.now()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'original_path': self.original_path,
            'target_path': self.target_path,
            'resource_type': self.resource_type,
            'resource_name': self.resource_name,
            'validation_status': self.validation_status,
            'error_message': self.error_message,
            'processed_at': self.processed_at.isoformat()
        }


class FileIngestionPipeline:
    """
    Processes files from raw/ directory through validation to managed/ directory.
    
    This pipeline implements a five-stage process:
    1. Discovery: Scan raw/ directory for new files
    2. Validation: Parse and validate YAML content
    3. Classification: Determine resource type and target location
    4. Processing: Create/update database records
    5. Archive: Move processed files and update metadata
    """
    
    # Supported Kubernetes resource kinds
    SUPPORTED_KINDS = {
        'VPC': 'vpcs',
        'External': 'externals',
        'ExternalAttachment': 'external-attachments',
        'ExternalPeering': 'external-peerings',
        'IPv4Namespace': 'ipv4-namespaces',
        'VPCAttachment': 'vpc-attachments',
        'VPCPeering': 'vpc-peerings',
        'Connection': 'connections',
        'Server': 'servers',
        'Switch': 'switches',
        'SwitchGroup': 'switch-groups',
        'VLANNamespace': 'vlan-namespaces'
    }
    
    # Required fields for validation
    REQUIRED_FIELDS = ['apiVersion', 'kind', 'metadata', 'spec']
    REQUIRED_METADATA_FIELDS = ['name']
    
    def __init__(self, fabric):
        """Initialize ingestion pipeline for specified fabric"""
        self.fabric = fabric
        self.git_repository = fabric.git_repository
        
        if not self.git_repository:
            raise ValueError(f"Fabric {fabric.name} has no Git repository configured")
        
        # Initialize stages
        self.stages = {
            'discovery': IngestionStage('Discovery', 'Scan raw/ directory for new files'),
            'validation': IngestionStage('Validation', 'Parse and validate YAML content'),
            'classification': IngestionStage('Classification', 'Determine resource type and target location'),
            'processing': IngestionStage('Processing', 'Create/update database records'),
            'archive': IngestionStage('Archive', 'Move processed files and update metadata')
        }
        
        self.processed_files = []
        self.total_files_discovered = 0
        self.total_files_ingested = 0
        self.total_files_archived = 0
    
    def process_raw_directory(self) -> Dict[str, Any]:
        """
        Main entry point for processing raw/ directory.
        
        Returns:
            Dictionary with processing results
        """
        logger.info(f"Starting file ingestion for fabric {self.fabric.name}")
        
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                # Clone repository
                clone_result = self.git_repository.clone_repository(temp_dir)
                
                if not clone_result['success']:
                    return {
                        'success': False,
                        'error': f"Failed to clone repository: {clone_result['error']}"
                    }
                
                repo_path = Path(temp_dir)
                gitops_path = repo_path / self.fabric.gitops_directory.strip('/')
                raw_path = gitops_path / 'raw'
                
                if not raw_path.exists():
                    return {
                        'success': False,
                        'error': f"Raw directory {raw_path} does not exist"
                    }
                
                # Process through all stages
                with transaction.atomic():
                    files_to_process = self._discovery_stage(raw_path)
                    validated_files = self._validation_stage(files_to_process)
                    classified_files = self._classification_stage(validated_files)
                    processed_files = self._processing_stage(classified_files)
                    archived_files = self._archive_stage(processed_files, gitops_path)
                
                # Generate final results
                return self._generate_results()
        
        except Exception as e:
            logger.error(f"File ingestion failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'stages': {name: stage.get_summary() for name, stage in self.stages.items()}
            }
    
    def _discovery_stage(self, raw_path: Path) -> List[Path]:
        """
        Stage 1: Discover files in raw/ directory.
        
        Args:
            raw_path: Path to raw/ directory
            
        Returns:
            List of file paths to process
        """
        logger.info("Starting discovery stage")
        stage = self.stages['discovery']
        
        files_to_process = []
        
        try:
            # Look in raw/pending/ first
            pending_path = raw_path / 'pending'
            if pending_path.exists():
                for file_path in pending_path.glob('*.yaml'):
                    files_to_process.append(file_path)
                    stage.add_success(str(file_path))
                
                for file_path in pending_path.glob('*.yml'):
                    files_to_process.append(file_path)
                    stage.add_success(str(file_path))
            
            # Also check root raw/ directory
            for file_path in raw_path.glob('*.yaml'):
                if file_path.parent.name == 'raw':  # Only direct children
                    files_to_process.append(file_path)
                    stage.add_success(str(file_path))
            
            for file_path in raw_path.glob('*.yml'):
                if file_path.parent.name == 'raw':  # Only direct children
                    files_to_process.append(file_path)
                    stage.add_success(str(file_path))
            
            self.total_files_discovered = len(files_to_process)
            logger.info(f"Discovery stage completed: {self.total_files_discovered} files found")
            
            return files_to_process
        
        except Exception as e:
            stage.add_failure('discovery', str(e))
            raise
    
    def _validation_stage(self, files_to_process: List[Path]) -> List[Tuple[Path, Dict[str, Any]]]:
        """
        Stage 2: Validate YAML content.
        
        Args:
            files_to_process: List of file paths to validate
            
        Returns:
            List of tuples (file_path, parsed_content)
        """
        logger.info("Starting validation stage")
        stage = self.stages['validation']
        
        validated_files = []
        
        for file_path in files_to_process:
            try:
                # Parse YAML content
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Handle multi-document YAML
                documents = list(yaml.safe_load_all(content))
                
                for i, doc in enumerate(documents):
                    if not doc or not isinstance(doc, dict):
                        stage.add_warning(str(file_path), f"Document {i+1} is empty or not a dictionary")
                        continue
                    
                    # Validate required fields
                    validation_errors = self._validate_document(doc)
                    
                    if validation_errors:
                        stage.add_failure(str(file_path), f"Validation errors: {'; '.join(validation_errors)}")
                        self._move_to_errors(file_path, validation_errors)
                        continue
                    
                    # Document is valid
                    validated_files.append((file_path, doc))
                    stage.add_success(str(file_path))
            
            except yaml.YAMLError as e:
                stage.add_failure(str(file_path), f"YAML parsing error: {str(e)}")
                self._move_to_errors(file_path, [f"YAML parsing error: {str(e)}"])
            
            except Exception as e:
                stage.add_failure(str(file_path), f"Unexpected error: {str(e)}")
                self._move_to_errors(file_path, [f"Unexpected error: {str(e)}"])
        
        logger.info(f"Validation stage completed: {len(validated_files)} valid documents")
        return validated_files
    
    def _validation_rules(self, doc: Dict[str, Any]) -> List[str]:
        """Additional validation rules for documents"""
        errors = []
        
        # Check API version format
        api_version = doc.get('apiVersion', '')
        if not api_version or '/' not in api_version:
            errors.append("apiVersion must be in format 'group/version'")
        
        # Check if it's a Hedgehog resource
        if 'hedgehog' not in api_version.lower() and doc.get('kind') not in self.SUPPORTED_KINDS:
            errors.append(f"Unsupported resource kind: {doc.get('kind')}")
        
        # Validate metadata
        metadata = doc.get('metadata', {})
        name = metadata.get('name', '')
        
        if not name or not isinstance(name, str):
            errors.append("metadata.name is required and must be a string")
        elif not self._is_valid_k8s_name(name):
            errors.append("metadata.name must be a valid Kubernetes name (DNS-1123 compliant)")
        
        # Validate namespace if present
        namespace = metadata.get('namespace')
        if namespace and not self._is_valid_k8s_name(namespace):
            errors.append("metadata.namespace must be a valid Kubernetes name")
        
        # Validate spec exists and is not empty
        spec = doc.get('spec')
        if not spec or not isinstance(spec, dict):
            errors.append("spec is required and must be a dictionary")
        
        return errors
    
    def _validate_document(self, doc: Dict[str, Any]) -> List[str]:
        """Validate a single document"""
        errors = []
        
        # Check required top-level fields
        for field in self.REQUIRED_FIELDS:
            if field not in doc:
                errors.append(f"Missing required field: {field}")
        
        # Check required metadata fields
        metadata = doc.get('metadata', {})
        for field in self.REQUIRED_METADATA_FIELDS:
            if field not in metadata:
                errors.append(f"Missing required metadata field: {field}")
        
        # Additional validation rules
        errors.extend(self._validation_rules(doc))
        
        return errors
    
    def _classification_stage(self, validated_files: List[Tuple[Path, Dict[str, Any]]]) -> List[Tuple[Path, Dict[str, Any], str]]:
        """
        Stage 3: Classify documents and determine target locations.
        
        Args:
            validated_files: List of validated files with parsed content
            
        Returns:
            List of tuples (file_path, document, target_path)
        """
        logger.info("Starting classification stage")
        stage = self.stages['classification']
        
        classified_files = []
        
        for file_path, doc in validated_files:
            try:
                kind = doc.get('kind')
                name = doc.get('metadata', {}).get('name')
                
                if kind not in self.SUPPORTED_KINDS:
                    stage.add_failure(str(file_path), f"Unsupported resource kind: {kind}")
                    continue
                
                # Determine target directory
                target_dir = self.SUPPORTED_KINDS[kind]
                target_filename = f"{name}.yaml"
                target_path = f"managed/{target_dir}/{target_filename}"
                
                classified_files.append((file_path, doc, target_path))
                stage.add_success(str(file_path))
                
                # Create ProcessedFile record
                processed_file = ProcessedFile(
                    original_path=str(file_path),
                    target_path=target_path,
                    resource_type=kind,
                    resource_name=name,
                    validation_status='classified'
                )
                self.processed_files.append(processed_file)
            
            except Exception as e:
                stage.add_failure(str(file_path), f"Classification error: {str(e)}")
        
        logger.info(f"Classification stage completed: {len(classified_files)} files classified")
        return classified_files
    
    def _processing_stage(self, classified_files: List[Tuple[Path, Dict[str, Any], str]]) -> List[Tuple[Path, Dict[str, Any], str]]:
        """
        Stage 4: Create/update database records.
        
        Args:
            classified_files: List of classified files
            
        Returns:
            List of successfully processed files
        """
        logger.info("Starting processing stage")
        stage = self.stages['processing']
        
        processed_files = []
        
        for file_path, doc, target_path in classified_files:
            try:
                # Create or update HedgehogResource record
                success = self._create_or_update_resource(doc, str(file_path), target_path)
                
                if success:
                    processed_files.append((file_path, doc, target_path))
                    stage.add_success(str(file_path))
                    self.total_files_ingested += 1
                    
                    # Update ProcessedFile record
                    for pf in self.processed_files:
                        if pf.original_path == str(file_path):
                            pf.validation_status = 'processed'
                            break
                else:
                    stage.add_failure(str(file_path), "Failed to create/update database record")
            
            except Exception as e:
                stage.add_failure(str(file_path), f"Processing error: {str(e)}")
        
        logger.info(f"Processing stage completed: {len(processed_files)} files processed")
        return processed_files
    
    def _archive_stage(self, processed_files: List[Tuple[Path, Dict[str, Any], str]], gitops_path: Path) -> List[str]:
        """
        Stage 5: Archive processed files.
        
        Args:
            processed_files: List of successfully processed files
            gitops_path: Path to GitOps directory
            
        Returns:
            List of archived file paths
        """
        logger.info("Starting archive stage")
        stage = self.stages['archive']
        
        archived_files = []
        processed_dir = gitops_path / 'raw' / 'processed'
        processed_dir.mkdir(exist_ok=True)
        
        for file_path, doc, target_path in processed_files:
            try:
                # Generate archived filename with timestamp
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                archived_name = f"{file_path.stem}_{timestamp}.yaml"
                archived_path = processed_dir / archived_name
                
                # Move file to processed directory
                shutil.move(str(file_path), str(archived_path))
                
                archived_files.append(str(archived_path))
                stage.add_success(str(file_path))
                self.total_files_archived += 1
                
                # Update ProcessedFile record
                for pf in self.processed_files:
                    if pf.original_path == str(file_path):
                        pf.validation_status = 'archived'
                        break
            
            except Exception as e:
                stage.add_failure(str(file_path), f"Archive error: {str(e)}")
        
        logger.info(f"Archive stage completed: {len(archived_files)} files archived")
        return archived_files
    
    def _create_or_update_resource(self, doc: Dict[str, Any], original_path: str, target_path: str) -> bool:
        """Create or update HedgehogResource from document"""
        try:
            from ..models.gitops import HedgehogResource
            
            kind = doc.get('kind')
            metadata = doc.get('metadata', {})
            name = metadata.get('name')
            namespace = metadata.get('namespace', 'default')
            spec = doc.get('spec', {})
            
            # Create or update HedgehogResource
            resource, created = HedgehogResource.objects.update_or_create(
                fabric=self.fabric,
                kind=kind,
                name=name,
                namespace=namespace,
                defaults={
                    'api_version': doc.get('apiVersion'),
                    'desired_spec': spec,
                    'managed_file_path': target_path,
                    'desired_file_path': original_path,
                    'desired_updated': timezone.now(),
                    'labels': metadata.get('labels', {}),
                    'annotations': metadata.get('annotations', {}),
                    'sync_direction': 'bidirectional'
                }
            )
            
            # Calculate and set file hash
            yaml_content = yaml.dump(doc, default_flow_style=False)
            import hashlib
            content_hash = hashlib.sha256(yaml_content.encode('utf-8')).hexdigest()
            resource.file_hash = content_hash
            resource.last_file_sync = timezone.now()
            resource.save()
            
            logger.debug(f"{'Created' if created else 'Updated'} resource {kind}/{name}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to create/update resource: {e}")
            return False
    
    def _move_to_errors(self, file_path: Path, errors: List[str]):
        """Move file to errors directory with error information"""
        try:
            errors_dir = file_path.parent.parent / 'errors'
            errors_dir.mkdir(exist_ok=True)
            
            # Create error info file
            error_info = {
                'original_file': str(file_path),
                'errors': errors,
                'timestamp': timezone.now().isoformat(),
                'fabric': self.fabric.name
            }
            
            error_filename = f"{file_path.stem}_error.json"
            error_path = errors_dir / error_filename
            
            with open(error_path, 'w') as f:
                json.dump(error_info, f, indent=2)
            
            # Move original file
            moved_path = errors_dir / file_path.name
            shutil.move(str(file_path), str(moved_path))
            
            logger.info(f"Moved file with errors to {moved_path}")
        
        except Exception as e:
            logger.error(f"Failed to move file to errors directory: {e}")
    
    def _is_valid_k8s_name(self, name: str) -> bool:
        """Validate Kubernetes resource name (DNS-1123 compliant)"""
        if not name:
            return False
        
        import re
        pattern = r'^[a-z0-9]([-a-z0-9]*[a-z0-9])?$'
        return bool(re.match(pattern, name)) and len(name) <= 253
    
    def _generate_results(self) -> Dict[str, Any]:
        """Generate final processing results"""
        total_success = sum(stage.files_success for stage in self.stages.values())
        total_failed = sum(stage.files_failed for stage in self.stages.values())
        total_processed = total_success + total_failed
        
        success = total_failed == 0
        
        return {
            'success': success,
            'message': f"File ingestion completed: {self.total_files_ingested} files ingested, {self.total_files_archived} archived",
            'summary': {
                'files_discovered': self.total_files_discovered,
                'files_ingested': self.total_files_ingested,
                'files_archived': self.total_files_archived,
                'total_processed': total_processed,
                'total_success': total_success,
                'total_failed': total_failed,
                'success_rate': (total_success / total_processed * 100) if total_processed > 0 else 0
            },
            'stages': {name: stage.get_summary() for name, stage in self.stages.items()},
            'processed_files': [pf.to_dict() for pf in self.processed_files],
            'fabric': self.fabric.name
        }