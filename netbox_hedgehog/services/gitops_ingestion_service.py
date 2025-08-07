"""
GitOps Ingestion Service

Handles ingestion of multi-document YAML files from the raw/ directory.
Parses, normalizes, and moves files to the managed/ directory structure.
"""

import os
import logging
import yaml
import json
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime
from django.utils import timezone
from django.db import transaction

logger = logging.getLogger(__name__)


class GitOpsIngestionService:
    """
    Service for ingesting and processing YAML files from raw/ directory.
    
    Responsibilities:
    1. Parse multi-document YAML files safely
    2. Normalize into single-document files
    3. Archive original files
    4. Update tracking manifests
    5. Handle errors and rollback on failures
    """
    
    def __init__(self, fabric):
        self.fabric = fabric
        self.raw_path = None
        self.managed_path = None
        self.metadata_path = None
        
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
            'started_at': timezone.now(),
            'files_processed': [],
            'documents_extracted': [],
            'files_created': [],
            'files_archived': [],
            'errors': [],
            'warnings': []
        }
    
    def process_raw_directory(self) -> Dict[str, Any]:
        """
        Process all YAML files in the raw/ directory.
        
        Returns:
            Dict with processing results
        """
        try:
            logger.info(f"=== INGESTION DIAGNOSTIC: Starting raw directory processing for fabric {self.fabric.name} ===")
            logger.info(f"INGESTION DIAGNOSTIC: Fabric ID: {self.fabric.id}")
            logger.info(f"INGESTION DIAGNOSTIC: Initial ingestion_result: {self.ingestion_result}")
            
            # Initialize paths
            logger.info("INGESTION DIAGNOSTIC: Calling _initialize_paths()...")
            try:
                self._initialize_paths()
                logger.info(f"INGESTION DIAGNOSTIC: Paths initialized - raw: {self.raw_path}, managed: {self.managed_path}, metadata: {self.metadata_path}")
            except Exception as init_e:
                logger.error(f"INGESTION DIAGNOSTIC: Path initialization failed: {init_e}")
                import traceback
                logger.error(f"INGESTION DIAGNOSTIC: Path init traceback: {traceback.format_exc()}")
                raise
            
            # Validate structure exists
            logger.info("INGESTION DIAGNOSTIC: Calling _validate_structure()...")
            try:
                structure_valid = self._validate_structure()
                logger.info(f"INGESTION DIAGNOSTIC: Structure validation result: {structure_valid}")
                if not structure_valid:
                    raise Exception("GitOps structure not properly initialized")
            except Exception as val_e:
                logger.error(f"INGESTION DIAGNOSTIC: Structure validation failed: {val_e}")
                import traceback
                logger.error(f"INGESTION DIAGNOSTIC: Structure validation traceback: {traceback.format_exc()}")
                raise
            
            # Find all YAML files in raw directory
            logger.info("INGESTION DIAGNOSTIC: Calling _find_yaml_files_in_raw()...")
            try:
                yaml_files = self._find_yaml_files_in_raw()
                logger.info(f"INGESTION DIAGNOSTIC: Found {len(yaml_files)} YAML files: {[str(f) for f in yaml_files]}")
            except Exception as find_e:
                logger.error(f"INGESTION DIAGNOSTIC: File finding failed: {find_e}")
                import traceback
                logger.error(f"INGESTION DIAGNOSTIC: File finding traceback: {traceback.format_exc()}")
                raise
            
            if not yaml_files:
                logger.info("INGESTION DIAGNOSTIC: No files found, returning success early")
                self.ingestion_result['success'] = True
                self.ingestion_result['message'] = "No files to process in raw directory"
                self.ingestion_result['completed_at'] = timezone.now()
                logger.info(f"INGESTION DIAGNOSTIC: Early return result: {self.ingestion_result}")
                return self.ingestion_result
            
            # Process each file
            logger.info("INGESTION DIAGNOSTIC: Starting database transaction...")
            try:
                with transaction.atomic():
                    logger.info(f"INGESTION DIAGNOSTIC: Processing {len(yaml_files)} files...")
                    for i, yaml_file in enumerate(yaml_files):
                        logger.info(f"INGESTION DIAGNOSTIC: Processing file {i+1}/{len(yaml_files)}: {yaml_file}")
                        try:
                            self._process_yaml_file(yaml_file)
                            logger.info(f"INGESTION DIAGNOSTIC: Successfully processed file {yaml_file}")
                        except Exception as proc_e:
                            logger.error(f"INGESTION DIAGNOSTIC: Failed to process file {yaml_file}: {proc_e}")
                            import traceback
                            logger.error(f"INGESTION DIAGNOSTIC: File processing traceback: {traceback.format_exc()}")
                            raise
                    
                    # Update archive log
                    logger.info("INGESTION DIAGNOSTIC: Updating archive log...")
                    try:
                        self._update_archive_log()
                        logger.info("INGESTION DIAGNOSTIC: Archive log updated successfully")
                    except Exception as arch_e:
                        logger.error(f"INGESTION DIAGNOSTIC: Archive log update failed: {arch_e}")
                        import traceback
                        logger.error(f"INGESTION DIAGNOSTIC: Archive log traceback: {traceback.format_exc()}")
                        raise
                    
                    self.ingestion_result['success'] = True
                    self.ingestion_result['completed_at'] = timezone.now()
                    self.ingestion_result['message'] = f"Successfully processed {len(yaml_files)} files, extracted {len(self.ingestion_result['documents_extracted'])} documents"
                    
                    logger.info(f"INGESTION DIAGNOSTIC: Transaction completed successfully")
                    logger.info(f"INGESTION DIAGNOSTIC: Final result: {self.ingestion_result}")
                    logger.info(f"INGESTION DIAGNOSTIC: Raw directory processing completed for fabric {self.fabric.name}")
                    return self.ingestion_result
                    
            except Exception as trans_e:
                logger.error(f"INGESTION DIAGNOSTIC: Transaction failed: {trans_e}")
                import traceback
                logger.error(f"INGESTION DIAGNOSTIC: Transaction traceback: {traceback.format_exc()}")
                raise
                
        except Exception as e:
            logger.error(f"INGESTION DIAGNOSTIC: Raw directory processing failed for fabric {self.fabric.name}: {str(e)}")
            import traceback
            logger.error(f"INGESTION DIAGNOSTIC: Main exception traceback: {traceback.format_exc()}")
            
            self.ingestion_result['success'] = False
            self.ingestion_result['error'] = str(e)
            self.ingestion_result['completed_at'] = timezone.now()
            
            # Attempt rollback
            logger.info("INGESTION DIAGNOSTIC: Attempting rollback...")
            try:
                self._rollback_changes()
                logger.info("INGESTION DIAGNOSTIC: Rollback completed")
            except Exception as rollback_e:
                logger.error(f"INGESTION DIAGNOSTIC: Rollback failed: {rollback_e}")
            
            logger.info(f"INGESTION DIAGNOSTIC: Final error result: {self.ingestion_result}")
            return self.ingestion_result
    
    def process_single_file(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Process a single YAML file.
        
        Args:
            file_path: Path to the YAML file to process
            
        Returns:
            Dict with processing results
        """
        try:
            file_path = Path(file_path)
            logger.info(f"Processing single file: {file_path}")
            
            self._initialize_paths()
            
            if not self._validate_structure():
                raise Exception("GitOps structure not properly initialized")
            
            with transaction.atomic():
                self._process_yaml_file(file_path)
                self._update_archive_log()
                
                return {
                    'success': True,
                    'file_path': str(file_path),
                    'documents_extracted': len(self.ingestion_result['documents_extracted']),
                    'files_created': self.ingestion_result['files_created'],
                    'completed_at': timezone.now()
                }
                
        except Exception as e:
            logger.error(f"Single file processing failed for {file_path}: {str(e)}")
            self._rollback_changes()
            return {
                'success': False,
                'error': str(e),
                'file_path': str(file_path)
            }
    
    def _initialize_paths(self):
        """Initialize directory paths from fabric configuration."""
        if hasattr(self.fabric, 'raw_directory_path') and self.fabric.raw_directory_path:
            self.raw_path = Path(self.fabric.raw_directory_path)
        else:
            # Fallback path construction
            base_path = self._get_base_directory_path()
            self.raw_path = base_path / 'raw'
        
        if hasattr(self.fabric, 'managed_directory_path') and self.fabric.managed_directory_path:
            self.managed_path = Path(self.fabric.managed_directory_path)
        else:
            base_path = self._get_base_directory_path()
            self.managed_path = base_path / 'managed'
        
        base_path = self.raw_path.parent if self.raw_path else self._get_base_directory_path()
        self.metadata_path = base_path / '.hnp'
    
    def _get_base_directory_path(self) -> Path:
        """Get the base directory path for this fabric's GitOps structure."""
        # Use existing Git repository path if available
        if hasattr(self.fabric, 'git_repository') and self.fabric.git_repository:
            git_path = getattr(self.fabric.git_repository, 'local_path', None)
            if git_path:
                return Path(git_path) / 'fabrics' / self.fabric.name / 'gitops'
        
        # Fall back to legacy Git configuration
        if self.fabric.git_repository_url:
            repo_name = self.fabric.name.lower().replace(' ', '-').replace('_', '-')
            return Path(f"/tmp/hedgehog-repos/{repo_name}/fabrics/{self.fabric.name}/gitops")
        
        # Default fallback
        return Path(f"/var/lib/hedgehog/fabrics/{self.fabric.name}/gitops")
    
    def _validate_structure(self) -> bool:
        """Validate that required directory structure exists."""
        required_paths = [self.raw_path, self.managed_path, self.metadata_path]
        for path in required_paths:
            if not path or not path.exists():
                logger.error(f"Required path does not exist: {path}")
                return False
        return True
    
    def _find_yaml_files_in_raw(self) -> List[Path]:
        """Find all YAML files in the raw directory."""
        yaml_files = []
        try:
            # Look for both .yaml and .yml files
            for pattern in ['*.yaml', '*.yml']:
                yaml_files.extend(self.raw_path.glob(pattern))
            
            # Sort by modification time (oldest first)
            yaml_files.sort(key=lambda x: x.stat().st_mtime)
            
        except Exception as e:
            logger.error(f"Error scanning raw directory: {str(e)}")
            self.ingestion_result['errors'].append(f"Failed to scan raw directory: {str(e)}")
        
        return yaml_files
    
    def _process_yaml_file(self, file_path: Path):
        """Process a single YAML file, handling multi-document content."""
        try:
            logger.info(f"Processing YAML file: {file_path}")
            
            # Skip obvious non-Kubernetes files
            if file_path.name in ['mkdocs.yml', 'docker-compose.yml', '.pre-commit-config.yaml']:
                logger.info(f"Skipping non-Kubernetes file: {file_path}")
                self.ingestion_result['warnings'].append(f"Skipped non-Kubernetes file: {file_path}")
                return
            
            # Parse multi-document YAML
            documents = self._parse_multi_document_yaml(file_path)
            
            if not documents:
                self.ingestion_result['warnings'].append(f"No valid documents found in {file_path}")
                return
            
            # Track the file being processed
            file_info = {
                'original_path': str(file_path),
                'document_count': len(documents),
                'processed_at': timezone.now().isoformat(),
                'documents': []
            }
            
            # Process each document
            for i, document in enumerate(documents):
                try:
                    normalized_file = self._normalize_document_to_file(document, file_path, i)
                    if normalized_file:
                        file_info['documents'].append(normalized_file)
                        self.ingestion_result['documents_extracted'].append(normalized_file)
                        
                except Exception as e:
                    error_msg = f"Failed to normalize document {i} from {file_path}: {str(e)}"
                    logger.error(error_msg)
                    self.ingestion_result['errors'].append(error_msg)
            
            # Archive original file after successful processing
            if file_info['documents']:
                archived_path = self._archive_file(file_path)
                file_info['archived_to'] = str(archived_path)
                self.ingestion_result['files_archived'].append({
                    'original': str(file_path),
                    'archived_to': str(archived_path)
                })
            
            self.ingestion_result['files_processed'].append(file_info)
            
        except Exception as e:
            error_msg = f"Failed to process YAML file {file_path}: {str(e)}"
            logger.warning(error_msg)
            self.ingestion_result['warnings'].append(error_msg)
            # Don't raise - continue processing other files
    
    def _parse_multi_document_yaml(self, file_path: Path) -> List[Dict[str, Any]]:
        """Safely parse multi-document YAML files."""
        documents = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                # Use yaml.safe_load_all for multi-document support
                for doc in yaml.safe_load_all(f):
                    if doc and isinstance(doc, dict):
                        # Validate document has required Kubernetes fields
                        if self._is_valid_k8s_document(doc):
                            documents.append(doc)
                        else:
                            logger.warning(f"Skipping invalid document in {file_path}: missing required fields")
                    elif doc:
                        logger.warning(f"Skipping non-dict document in {file_path}: {type(doc)}")
                        
        except yaml.YAMLError as e:
            raise Exception(f"YAML parsing error: {str(e)}")
        except Exception as e:
            raise Exception(f"File reading error: {str(e)}")
        
        return documents
    
    def _is_valid_k8s_document(self, document: Dict[str, Any]) -> bool:
        """Validate that document has required Kubernetes fields."""
        required_fields = ['apiVersion', 'kind', 'metadata']
        
        for field in required_fields:
            if field not in document:
                return False
        
        # Check metadata has name
        metadata = document.get('metadata', {})
        if not isinstance(metadata, dict) or 'name' not in metadata:
            return False
        
        return True
    
    def _normalize_document_to_file(self, document: Dict[str, Any], original_file: Path, doc_index: int) -> Optional[Dict[str, Any]]:
        """
        Normalize a single document into a standalone file in managed/ directory.
        
        Args:
            document: The parsed YAML document
            original_file: Original file this document came from
            doc_index: Index of document within original file
            
        Returns:
            Dict with information about the created file, or None if skipped
        """
        try:
            logger.debug(f"Processing document {doc_index} from {original_file}")
            
            # Extract document metadata
            kind = document.get('kind')
            metadata = document.get('metadata', {})
            name = metadata.get('name')
            namespace = metadata.get('namespace', self.fabric.kubernetes_namespace or 'default')
            
            logger.debug(f"Document details - Kind: {kind}, Name: {name}, Namespace: {namespace}")
            
            # Validate basic document structure
            if not kind:
                logger.warning(f"Document {doc_index} from {original_file} has no 'kind' field")
                return None
                
            if not name:
                logger.warning(f"Document {doc_index} from {original_file} has no 'metadata.name' field")
                return None
            
            # Validate we can handle this kind
            if kind not in self.kind_to_directory:
                logger.warning(f"Unsupported kind '{kind}' in document {doc_index} from {original_file}")
                logger.debug(f"Supported kinds: {list(self.kind_to_directory.keys())}")
                return None
            
            # Validate managed path exists
            if not self.managed_path:
                error_msg = f"Managed path is not initialized for fabric {self.fabric.name}"
                logger.error(error_msg)
                raise Exception(error_msg)
            
            # Create managed path if it doesn't exist
            if not self.managed_path.exists():
                logger.info(f"Creating managed path: {self.managed_path}")
                try:
                    self.managed_path.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    error_msg = f"Failed to create managed path {self.managed_path}: {str(e)}"
                    logger.error(error_msg)
                    raise Exception(error_msg)
            
            # Determine target directory and file path
            target_dir = self.managed_path / self.kind_to_directory[kind]
            logger.debug(f"Target directory: {target_dir}")
            
            try:
                target_dir.mkdir(parents=True, exist_ok=True)
                logger.debug(f"Created/verified target directory: {target_dir}")
            except Exception as e:
                error_msg = f"Failed to create target directory {target_dir}: {str(e)}"
                logger.error(error_msg)
                raise Exception(error_msg)
            
            # Generate filename (handle conflicts)
            try:
                target_file = self._generate_managed_filename(target_dir, name, namespace)
                logger.debug(f"Generated target file: {target_file}")
            except Exception as e:
                error_msg = f"Failed to generate filename for {kind}/{name}: {str(e)}"
                logger.error(error_msg)
                raise Exception(error_msg)
            
            # Add HNP tracking annotations
            try:
                self._add_hnp_annotations(document, original_file, doc_index)
                logger.debug(f"Added HNP annotations to {kind}/{name}")
            except Exception as e:
                error_msg = f"Failed to add HNP annotations to {kind}/{name}: {str(e)}"
                logger.error(error_msg)
                raise Exception(error_msg)
            
            # Write normalized YAML file
            try:
                self._write_normalized_yaml(document, target_file)
                logger.debug(f"Wrote normalized YAML to {target_file}")
            except Exception as e:
                error_msg = f"Failed to write normalized YAML to {target_file}: {str(e)}"
                logger.error(error_msg)
                raise Exception(error_msg)
            
            # Verify file was actually created
            if not target_file.exists():
                error_msg = f"File {target_file} was not created despite successful write operation"
                logger.error(error_msg)
                raise Exception(error_msg)
            
            file_size = target_file.stat().st_size
            logger.debug(f"Created file {target_file} with size {file_size} bytes")
            
            # Track the created file
            created_file_info = {
                'kind': kind,
                'name': name,
                'namespace': namespace,
                'original_file': str(original_file),
                'original_document_index': doc_index,
                'managed_file': str(target_file),
                'file_size': file_size,
                'created_at': timezone.now().isoformat()
            }
            
            self.ingestion_result['files_created'].append(created_file_info)
            
            logger.info(f"Successfully normalized {kind}/{name} to {target_file} ({file_size} bytes)")
            return created_file_info
            
        except Exception as e:
            error_msg = f"Failed to normalize document {doc_index} from {original_file}: {str(e)}"
            logger.error(error_msg)
            # Don't raise here - let the calling code handle the error and continue with other documents
            return None
    
    def _generate_managed_filename(self, target_dir: Path, name: str, namespace: str) -> Path:
        """Generate a unique filename in the managed directory."""
        # Base filename
        if namespace and namespace != 'default':
            base_name = f"{namespace}-{name}.yaml"
        else:
            base_name = f"{name}.yaml"
        
        target_file = target_dir / base_name
        
        # Handle naming conflicts
        counter = 1
        while target_file.exists():
            if namespace and namespace != 'default':
                conflict_name = f"{namespace}-{name}-{counter}.yaml"
            else:
                conflict_name = f"{name}-{counter}.yaml"
            target_file = target_dir / conflict_name
            counter += 1
        
        return target_file
    
    def _add_hnp_annotations(self, document: Dict[str, Any], original_file: Path, doc_index: int):
        """Add HNP tracking annotations to the document."""
        if 'metadata' not in document:
            document['metadata'] = {}
        
        if 'annotations' not in document['metadata']:
            document['metadata']['annotations'] = {}
        
        annotations = document['metadata']['annotations']
        
        # Add HNP tracking annotations
        annotations['hnp.githedgehog.com/managed-by'] = 'hedgehog-netbox-plugin'
        annotations['hnp.githedgehog.com/fabric'] = self.fabric.name
        annotations['hnp.githedgehog.com/original-file'] = str(original_file.name)
        annotations['hnp.githedgehog.com/original-document-index'] = str(doc_index)
        annotations['hnp.githedgehog.com/ingested-at'] = timezone.now().isoformat()
        annotations['hnp.githedgehog.com/ingestion-version'] = '1.0'
    
    def _write_normalized_yaml(self, document: Dict[str, Any], target_file: Path):
        """Write a normalized YAML document to file."""
        try:
            # Validate target file path
            if not target_file.parent.exists():
                raise Exception(f"Target directory {target_file.parent} does not exist")
            
            # Check write permissions
            try:
                target_file.parent.resolve().stat()
            except Exception as e:
                raise Exception(f"Cannot access target directory {target_file.parent}: {str(e)}")
            
            # Create header comment
            kind = document.get('kind', 'Unknown')
            name = document.get('metadata', {}).get('name', 'unknown')
            
            header = f"# {kind}: {name}\n"
            header += f"# Normalized by Hedgehog NetBox Plugin\n"
            header += f"# Generated: {timezone.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
            header += "---\n"
            
            # Write file with explicit error handling
            try:
                with open(target_file, 'w', encoding='utf-8') as f:
                    f.write(header)
                    yaml.safe_dump(
                        document,
                        f,
                        default_flow_style=False,
                        sort_keys=False,
                        allow_unicode=True,
                        width=120
                    )
                    f.flush()  # Ensure data is written to disk
                    
            except PermissionError as e:
                raise Exception(f"Permission denied writing to {target_file}: {str(e)}")
            except OSError as e:
                raise Exception(f"OS error writing to {target_file}: {str(e)}")
            except yaml.YAMLError as e:
                raise Exception(f"YAML serialization error for {kind}/{name}: {str(e)}")
            except Exception as e:
                raise Exception(f"Unexpected error writing to {target_file}: {str(e)}")
                
        except Exception as e:
            # Re-raise with context
            raise Exception(f"Failed to write normalized YAML to {target_file}: {str(e)}")
    
    def _archive_file(self, file_path: Path) -> Path:
        """Archive a file by moving it to .archived extension."""
        archived_path = file_path.with_suffix(file_path.suffix + '.archived')
        
        # Handle conflicts
        counter = 1
        while archived_path.exists():
            archived_path = file_path.with_suffix(f"{file_path.suffix}.archived.{counter}")
            counter += 1
        
        try:
            file_path.rename(archived_path)
            return archived_path
        except Exception as e:
            # If rename fails, try copying and removing
            shutil.copy2(file_path, archived_path)
            file_path.unlink()
            return archived_path
    
    def _update_archive_log(self):
        """Update the archive log with ingestion operations."""
        try:
            archive_log_path = self.metadata_path / 'archive-log.yaml'
            
            # Load existing log or create new one
            if archive_log_path.exists():
                with open(archive_log_path, 'r') as f:
                    archive_log = yaml.safe_load(f) or {}
            else:
                archive_log = {
                    'version': '1.0',
                    'created_at': timezone.now().isoformat(),
                    'operations': []
                }
            
            # Add ingestion operations
            for file_info in self.ingestion_result['files_processed']:
                operation = {
                    'operation': 'ingestion',
                    'timestamp': timezone.now().isoformat(),
                    'original_file': file_info['original_path'],
                    'document_count': file_info['document_count'],
                    'documents_created': [doc['managed_file'] for doc in file_info['documents']],
                    'archived_to': file_info.get('archived_to')
                }
                archive_log['operations'].append(operation)
            
            # Write updated log
            with open(archive_log_path, 'w') as f:
                yaml.safe_dump(archive_log, f, default_flow_style=False, sort_keys=False)
                
        except Exception as e:
            logger.error(f"Failed to update archive log: {str(e)}")
            self.ingestion_result['warnings'].append(f"Failed to update archive log: {str(e)}")
    
    def _rollback_changes(self):
        """Attempt to rollback changes on failure."""
        try:
            logger.info("Attempting to rollback ingestion changes")
            
            # Remove created files
            for file_info in self.ingestion_result['files_created']:
                try:
                    file_path = Path(file_info['managed_file'])
                    if file_path.exists():
                        file_path.unlink()
                        logger.info(f"Rolled back created file: {file_path}")
                except Exception as e:
                    logger.warning(f"Failed to rollback file {file_info['managed_file']}: {str(e)}")
            
            # Restore archived files
            for archive_info in self.ingestion_result['files_archived']:
                try:
                    original_path = Path(archive_info['original'])
                    archived_path = Path(archive_info['archived_to'])
                    
                    if archived_path.exists() and not original_path.exists():
                        archived_path.rename(original_path)
                        logger.info(f"Restored archived file: {original_path}")
                except Exception as e:
                    logger.warning(f"Failed to restore archived file {archive_info['original']}: {str(e)}")
                    
        except Exception as e:
            logger.error(f"Rollback failed: {str(e)}")
    
    def get_ingestion_status(self) -> Dict[str, Any]:
        """Get the current ingestion status and statistics."""
        self._initialize_paths()
        
        # Count files in directories
        raw_file_count = 0
        managed_file_count = 0
        
        try:
            if self.raw_path and self.raw_path.exists():
                raw_file_count = len(list(self.raw_path.glob('*.yaml')) + list(self.raw_path.glob('*.yml')))
            
            if self.managed_path and self.managed_path.exists():
                for crd_dir in self.kind_to_directory.values():
                    crd_path = self.managed_path / crd_dir
                    if crd_path.exists():
                        managed_file_count += len(list(crd_path.glob('*.yaml')))
        except Exception as e:
            logger.error(f"Error counting files: {str(e)}")
        
        return {
            'fabric_name': self.fabric.name,
            'fabric_id': self.fabric.id,
            'raw_files_pending': raw_file_count,
            'managed_files_count': managed_file_count,
            'last_ingestion': self.ingestion_result.get('completed_at'),
            'paths': {
                'raw_directory': str(self.raw_path) if self.raw_path else None,
                'managed_directory': str(self.managed_path) if self.managed_path else None,
                'metadata_directory': str(self.metadata_path) if self.metadata_path else None
            }
        }