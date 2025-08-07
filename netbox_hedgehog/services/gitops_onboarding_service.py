"""
GitOps Onboarding Service

Handles initialization of GitOps directory structure and migration of existing files.
Creates the proper directory layout for the new bidirectional file management system.
"""

import os
import logging
import yaml
import shutil
import requests
import base64
import threading
import time
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import transaction
from django.conf import settings

logger = logging.getLogger(__name__)


class GitOpsOnboardingService:
    """
    Service for initializing GitOps directory structure and onboarding existing files.
    
    Directory structure created:
    fabrics/{fabric-name}/gitops/
    ├── raw/                        # User drops files here
    ├── managed/                    # HNP manages these
    │   ├── connections/
    │   ├── servers/
    │   ├── switches/
    │   ├── switchgroups/
    │   ├── vlannamespaces/
    │   ├── vpcs/
    │   ├── externals/
    │   ├── externalattachments/
    │   ├── externalpeerings/
    │   ├── ipv4namespaces/
    │   ├── vpcattachments/
    │   └── vpcpeerings/
    └── .hnp/                      # HNP metadata
        ├── manifest.yaml
        └── archive-log.yaml
    """
    
    def __init__(self, fabric):
        self.fabric = fabric
        self.base_path = None
        self.raw_path = None
        self.managed_path = None
        self.unmanaged_path = None
        self.metadata_path = None
        
        # CRD types and their managed directory names
        self.crd_directories = [
            'connections',
            'servers', 
            'switches',
            'switchgroups',
            'vlannamespaces',
            'vpcs',
            'externals',
            'externalattachments',
            'externalpeerings',
            'ipv4namespaces',
            'vpcattachments',
            'vpcpeerings'
        ]
        
        self.onboarding_result = {
            'success': False,
            'fabric_name': fabric.name,
            'started_at': timezone.now(),
            'directories_created': [],
            'files_migrated': [],
            'files_archived': [],
            'errors': [],
            'warnings': []
        }
    
    def initialize_gitops_structure(self, base_directory: Optional[str] = None) -> Dict[str, Any]:
        """
        Initialize the complete GitOps directory structure for a fabric.
        
        Args:
            base_directory: Optional base directory override (for testing)
            
        Returns:
            Dict with initialization results
        """
        try:
            logger.info(f"Starting GitOps onboarding for fabric {self.fabric.name}")
            
            # Determine base directory path
            self.base_path = self._get_base_directory_path(base_directory)
            self.raw_path = self.base_path / 'raw'
            self.managed_path = self.base_path / 'managed'
            self.unmanaged_path = self.base_path / 'unmanaged'
            self.metadata_path = self.base_path / '.hnp'
            
            with transaction.atomic():
                # Step 1: Create directory structure
                self._create_directory_structure()
                
                # Step 2: Scan for existing files and migrate them
                existing_files = self._scan_existing_files()
                self.onboarding_result['existing_files_found'] = len(existing_files)
                if existing_files:
                    self._migrate_existing_files(existing_files)
                
                # Step 2.5: Ensure directory structure exists before processing
                self._ensure_directory_structure()
                
                # Step 2.5: Process raw directory to ingest migrated files
                if existing_files or self._has_files_in_raw():
                    logger.info(f"Processing files through raw directory ingestion")
                    ingestion_result = self._execute_ingestion_with_validation()
                    
                    if not ingestion_result.get('success'):
                        error_msg = f"File ingestion failed: {ingestion_result.get('error', 'Unknown error')}"
                        self.onboarding_result['success'] = False
                        self.onboarding_result['error'] = error_msg
                        logger.error(f"GitOps ingestion failed for fabric {self.fabric.name}: {error_msg}")
                        raise Exception(error_msg)
                    
                    self.onboarding_result['ingestion_attempted'] = True
                    self.onboarding_result['ingestion_success'] = ingestion_result.get('success', False)
                    self.onboarding_result['documents_extracted'] = ingestion_result.get('documents_extracted', [])
                    self.onboarding_result['files_created'] = ingestion_result.get('files_created', [])
                
                # Step 3: Create initial manifests
                self._create_initial_manifests()
                
                # Step 4: Push to GitHub if repository is configured
                github_result = self._push_to_github()
                
                # Step 5: Update fabric model
                self._update_fabric_model()
                
                self.onboarding_result['success'] = True
                self.onboarding_result['completed_at'] = timezone.now()
                
                if github_result and github_result.get('success'):
                    self.onboarding_result['message'] = f"Successfully initialized GitOps structure for fabric {self.fabric.name} and pushed to GitHub"
                    self.onboarding_result['github_push'] = github_result
                else:
                    self.onboarding_result['message'] = f"Successfully initialized local GitOps structure for fabric {self.fabric.name} (GitHub push failed)"
                    self.onboarding_result['github_push_error'] = github_result.get('error') if github_result else 'No GitHub repository configured'
                
                logger.info(f"GitOps onboarding completed for fabric {self.fabric.name}")
                return self.onboarding_result
                
        except Exception as e:
            logger.error(f"GitOps onboarding failed for fabric {self.fabric.name}: {str(e)}")
            self.onboarding_result['success'] = False
            self.onboarding_result['error'] = str(e)
            self.onboarding_result['completed_at'] = timezone.now()
            return self.onboarding_result
    
    def _get_base_directory_path(self, base_directory: Optional[str] = None) -> Path:
        """Get the base directory path for this fabric's GitOps structure."""
        if base_directory:
            return Path(base_directory)
        
        # Use existing Git repository path if available
        if hasattr(self.fabric, 'git_repository') and self.fabric.git_repository:
            # For new architecture with GitRepository model
            git_path = getattr(self.fabric.git_repository, 'local_path', None)
            if git_path:
                return Path(git_path) / 'fabrics' / self.fabric.name / 'gitops'
        
        # Fall back to legacy Git configuration
        if self.fabric.git_repository_url:
            # Use temporary directory structure for now
            repo_name = self.fabric.name.lower().replace(' ', '-').replace('_', '-')
            return Path(f"/tmp/hedgehog-repos/{repo_name}/fabrics/{self.fabric.name}/gitops")
        
        # Default fallback
        return Path(f"/var/lib/hedgehog/fabrics/{self.fabric.name}/gitops")
    
    def _create_directory_structure(self):
        """Create the complete directory structure."""
        directories_to_create = [
            self.base_path,
            self.raw_path,
            self.managed_path,
            self.unmanaged_path,
            self.metadata_path
        ]
        
        # Add managed subdirectories
        for crd_dir in self.crd_directories:
            directories_to_create.append(self.managed_path / crd_dir)
        
        for directory in directories_to_create:
            try:
                directory.mkdir(parents=True, exist_ok=True)
                self.onboarding_result['directories_created'].append(str(directory))
                logger.debug(f"Created directory: {directory}")
            except Exception as e:
                error_msg = f"Failed to create directory {directory}: {str(e)}"
                self.onboarding_result['errors'].append(error_msg)
                logger.error(error_msg)
                raise
    
    def _scan_existing_files(self) -> List[Path]:
        """Scan for existing YAML files that need to be migrated."""
        existing_files = []
        
        # Look in the fabric's gitops directory if it exists
        if hasattr(self.fabric, 'gitops_directory') and self.fabric.gitops_directory:
            legacy_path = Path(self.fabric.gitops_directory)
            if legacy_path.exists():
                existing_files.extend(self._find_yaml_files(legacy_path))
        
        # Look in the base directory for any loose files
        if self.base_path.exists():
            for item in self.base_path.iterdir():
                if item.is_file() and item.suffix.lower() in ['.yaml', '.yml']:
                    existing_files.append(item)
        
        # CRITICAL FIX: Also scan the raw/ directory for pre-existing files
        # This ensures that any YAML files placed in raw/ before initialization are processed
        if self.raw_path and self.raw_path.exists():
            logger.info(f"GitOps: Scanning raw directory for pre-existing files: {self.raw_path}")
            existing_files.extend(self._find_yaml_files(self.raw_path))
        
        return existing_files
    
    def _find_yaml_files(self, directory: Path) -> List[Path]:
        """Recursively find all YAML files in a directory."""
        yaml_files = []
        try:
            for pattern in ['**/*.yaml', '**/*.yml']:
                yaml_files.extend(directory.glob(pattern))
        except Exception as e:
            logger.warning(f"Error scanning directory {directory}: {str(e)}")
        return yaml_files
    
    def _migrate_existing_files(self, existing_files: List[Path]):
        """Migrate existing files to the raw directory and archive originals."""
        for file_path in existing_files:
            try:
                # Skip files already in our new structure
                if self._is_in_new_structure(file_path):
                    continue
                
                # Copy to raw directory
                raw_destination = self.raw_path / file_path.name
                
                # Handle naming conflicts
                if raw_destination.exists():
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    name_parts = file_path.stem, timestamp, file_path.suffix
                    raw_destination = self.raw_path / f"{name_parts[0]}_{name_parts[1]}{name_parts[2]}"
                
                shutil.copy2(file_path, raw_destination)
                self.onboarding_result['files_migrated'].append({
                    'original': str(file_path),
                    'migrated_to': str(raw_destination)
                })
                
                # Archive original file
                archived_path = self._archive_file(file_path)
                self.onboarding_result['files_archived'].append({
                    'original': str(file_path),
                    'archived_to': str(archived_path)
                })
                
                logger.info(f"Migrated {file_path} to {raw_destination}, archived original")
                
            except Exception as e:
                error_msg = f"Failed to migrate file {file_path}: {str(e)}"
                self.onboarding_result['errors'].append(error_msg)
                logger.error(error_msg)
    
    def _is_in_new_structure(self, file_path: Path) -> bool:
        """Check if a file is already in the new directory structure."""
        try:
            # Check if file is within our new structure paths
            return (
                self.raw_path in file_path.parents or
                self.managed_path in file_path.parents or
                self.metadata_path in file_path.parents
            )
        except:
            return False
    
    def _archive_file(self, file_path: Path) -> Path:
        """Archive a file by renaming it with .archived extension."""
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
    
    def _create_initial_manifests(self):
        """Create initial manifest and tracking files."""
        try:
            # Create main manifest
            manifest_content = {
                'version': '1.0',
                'fabric_name': self.fabric.name,
                'fabric_id': self.fabric.id,
                'structure_version': '1.0',
                'created_at': timezone.now().isoformat(),
                'directories': {
                    'raw': str(self.raw_path.relative_to(self.base_path)),
                    'managed': str(self.managed_path.relative_to(self.base_path)),
                    'metadata': str(self.metadata_path.relative_to(self.base_path))
                },
                'crd_directories': self.crd_directories,
                'archive_strategy': 'rename_with_extension',
                'onboarding_completed': True
            }
            
            manifest_path = self.metadata_path / 'manifest.yaml'
            with open(manifest_path, 'w') as f:
                yaml.safe_dump(manifest_content, f, default_flow_style=False, sort_keys=False)
            
            # Create archive log
            archive_log = {
                'version': '1.0',
                'created_at': timezone.now().isoformat(),
                'operations': []
            }
            
            # Add migration operations to log
            for migration in self.onboarding_result['files_migrated']:
                archive_log['operations'].append({
                    'operation': 'migration',
                    'timestamp': timezone.now().isoformat(),
                    'original_file': migration['original'],
                    'migrated_to': migration['migrated_to'],
                    'archived_to': None  # Will be filled if archiving was done
                })
            
            for archive in self.onboarding_result['files_archived']:
                # Find corresponding operation and update it
                for op in archive_log['operations']:
                    if op['original_file'] == archive['original']:
                        op['archived_to'] = archive['archived_to']
                        break
            
            archive_log_path = self.metadata_path / 'archive-log.yaml'
            with open(archive_log_path, 'w') as f:
                yaml.safe_dump(archive_log, f, default_flow_style=False, sort_keys=False)
            
            logger.info(f"Created manifests at {self.metadata_path}")
            
        except Exception as e:
            error_msg = f"Failed to create manifests: {str(e)}"
            self.onboarding_result['errors'].append(error_msg)
            logger.error(error_msg)
            raise
    
    def _update_fabric_model(self):
        """Update the fabric model with GitOps configuration."""
        try:
            self.fabric.gitops_initialized = True
            self.fabric.archive_strategy = 'rename_with_extension'
            self.fabric.raw_directory_path = str(self.raw_path)
            self.fabric.managed_directory_path = str(self.managed_path)
            self.fabric.save(update_fields=[
                'gitops_initialized', 
                'archive_strategy',
                'raw_directory_path',
                'managed_directory_path'
            ])
            
            logger.info(f"Updated fabric {self.fabric.name} with GitOps configuration")
            
        except Exception as e:
            error_msg = f"Failed to update fabric model: {str(e)}"
            self.onboarding_result['errors'].append(error_msg)
            logger.error(error_msg)
            raise
    
    def _push_to_github(self) -> Optional[Dict[str, Any]]:
        """
        Push the created directory structure to GitHub repository.
        
        Returns:
            Dict with push results or None if no GitHub repository configured
        """
        try:
            # Check if fabric has a Git repository configured
            if not hasattr(self.fabric, 'git_repository') or not self.fabric.git_repository:
                logger.info(f"No Git repository configured for fabric {self.fabric.name}, skipping GitHub push")
                return None
            
            git_repo = self.fabric.git_repository
            
            # Check if it's a GitHub repository
            if 'github.com' not in git_repo.url:
                logger.info(f"Repository {git_repo.url} is not GitHub, skipping GitHub push")
                return None
                
            from .github_push_service import GitHubPushService
            
            # Create GitHub push service
            github_service = GitHubPushService(git_repo)
            
            # Test connection first
            connection_test = github_service.test_connection()
            if not connection_test['success']:
                logger.error(f"GitHub connection test failed: {connection_test['error']}")
                return {
                    'success': False,
                    'error': f"GitHub connection test failed: {connection_test['error']}"
                }
            
            # Determine the path in the repository
            gitops_path = getattr(self.fabric, 'gitops_directory', 'gitops/hedgehog/fabric-1')
            if gitops_path.startswith('/'):
                gitops_path = gitops_path[1:]  # Remove leading slash
            if gitops_path.endswith('/'):
                gitops_path = gitops_path[:-1]  # Remove trailing slash
            
            # Create directory structure
            directories = ['raw', 'managed', 'unmanaged', '.hnp']
            structure_result = github_service.create_directory_structure(
                base_path=gitops_path,
                directories=directories,
                commit_message=f"Initialize GitOps directory structure for fabric {self.fabric.name}"
            )
            
            if not structure_result['success']:
                logger.error(f"Failed to create GitHub directory structure: {structure_result['error']}")
                return structure_result
            
            # Create manifest files
            manifest_result = github_service.create_manifest_files(
                base_path=gitops_path,
                fabric_name=self.fabric.name,
                fabric_id=self.fabric.id
            )
            
            if not manifest_result['success']:
                logger.error(f"Failed to create GitHub manifest files: {manifest_result['error']}")
                # Don't fail completely if manifests fail, but log it
                structure_result['manifest_warning'] = manifest_result['error']
            else:
                structure_result['manifest_success'] = True
                structure_result['manifest_files'] = manifest_result.get('created_files', [])
            
            logger.info(f"Successfully pushed GitOps structure to GitHub for fabric {self.fabric.name}")
            return structure_result
            
        except Exception as e:
            logger.error(f"Failed to push to GitHub: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def validate_structure(self) -> Dict[str, Any]:
        """Validate that the GitOps structure is properly set up."""
        validation_result = {
            'valid': True,
            'fabric_name': self.fabric.name,
            'checks': [],
            'errors': [],
            'warnings': []
        }
        
        try:
            # Check if base paths exist
            paths_to_check = [
                ('base_directory', self.base_path or self._get_base_directory_path()),
                ('raw_directory', self.raw_path or self._get_base_directory_path() / 'raw'),
                ('managed_directory', self.managed_path or self._get_base_directory_path() / 'managed'),
                ('metadata_directory', self.metadata_path or self._get_base_directory_path() / '.hnp')
            ]
            
            for name, path in paths_to_check:
                if path.exists():
                    validation_result['checks'].append(f"✓ {name} exists: {path}")
                else:
                    validation_result['valid'] = False
                    validation_result['errors'].append(f"✗ {name} missing: {path}")
            
            # Check managed subdirectories
            managed_base = self.managed_path or self._get_base_directory_path() / 'managed'
            for crd_dir in self.crd_directories:
                crd_path = managed_base / crd_dir
                if crd_path.exists():
                    validation_result['checks'].append(f"✓ managed/{crd_dir} exists")
                else:
                    validation_result['errors'].append(f"✗ managed/{crd_dir} missing")
                    validation_result['valid'] = False
            
            # Check manifest files
            metadata_base = self.metadata_path or self._get_base_directory_path() / '.hnp'
            manifest_files = ['manifest.yaml', 'archive-log.yaml']
            for manifest_file in manifest_files:
                manifest_path = metadata_base / manifest_file
                if manifest_path.exists():
                    validation_result['checks'].append(f"✓ {manifest_file} exists")
                else:
                    validation_result['warnings'].append(f"⚠ {manifest_file} missing (will be created)")
            
            # Check fabric model
            if hasattr(self.fabric, 'gitops_initialized') and self.fabric.gitops_initialized:
                validation_result['checks'].append("✓ Fabric model updated")
            else:
                validation_result['warnings'].append("⚠ Fabric model not yet updated")
            
        except Exception as e:
            validation_result['valid'] = False
            validation_result['errors'].append(f"Validation error: {str(e)}")
        
        return validation_result
    
    def sync_raw_directory(self, validate_only: bool = False) -> Dict[str, Any]:
        """
        Unified synchronization method for processing raw directory files.
        
        This method combines initialization and validation logic to ensure:
        1. Raw directory is properly processed
        2. Unknown files are moved to unmanaged/
        3. Valid CRs are processed for ingestion
        4. FGD structure is validated and repaired
        
        Args:
            validate_only: If True, only validate without making changes
            
        Returns:
            Dict with sync results
        """
        sync_result = {
            'success': False,
            'fabric_name': self.fabric.name,
            'started_at': timezone.now(),
            'validate_only': validate_only,
            'files_processed': 0,
            'files_moved_to_raw': 0,
            'files_moved_to_unmanaged': 0,
            'validation_errors': [],
            'structure_repairs': [],
            'errors': []
        }
        
        try:
            logger.info(f"Starting unified sync for fabric {self.fabric.name} (validate_only={validate_only})")
            
            # Initialize paths if not already done
            if not self.base_path:
                self.base_path = self._get_base_directory_path()
                self.raw_path = self.base_path / 'raw'
                self.managed_path = self.base_path / 'managed'
                self.unmanaged_path = self.base_path / 'unmanaged'
                self.metadata_path = self.base_path / '.hnp'
            
            # Step 1: Validate and repair FGD structure
            structure_validation = self._validate_and_repair_fgd_structure(validate_only)
            sync_result['structure_repairs'] = structure_validation.get('repairs', [])
            sync_result['validation_errors'].extend(structure_validation.get('errors', []))
            
            if not structure_validation['valid']:
                raise Exception(f"FGD structure validation failed: {'; '.join(structure_validation['errors'])}")
            
            # Step 2: Process files in raw directory (includes pre-existing)
            raw_processing = self._process_raw_directory_comprehensive(validate_only)
            sync_result.update({
                'files_processed': raw_processing['files_processed'],
                'files_moved_to_raw': raw_processing.get('files_moved_to_raw', 0),
                'files_moved_to_unmanaged': raw_processing.get('files_moved_to_unmanaged', 0)
            })
            sync_result['errors'].extend(raw_processing.get('errors', []))
            
            # Step 3: Handle race conditions with file locking
            if not validate_only:
                self._handle_concurrent_access_safely()
            
            # Step 4: Update sync metadata
            if not validate_only:
                self._update_sync_metadata(sync_result)
            
            sync_result['success'] = True
            sync_result['completed_at'] = timezone.now()
            sync_result['message'] = f"Sync completed: {sync_result['files_processed']} files processed"
            
            logger.info(f"Unified sync completed for fabric {self.fabric.name}")
            return sync_result
            
        except Exception as e:
            logger.error(f"Unified sync failed for fabric {self.fabric.name}: {str(e)}")
            sync_result['success'] = False
            sync_result['error'] = str(e)
            sync_result['completed_at'] = timezone.now()
            return sync_result
    
    def _validate_and_repair_fgd_structure(self, validate_only: bool) -> Dict[str, Any]:
        """
        Validate and optionally repair Fabric GitOps Directory (FGD) structure.
        
        Args:
            validate_only: If True, only validate without making repairs
            
        Returns:
            Dict with validation results and repairs made
        """
        validation_result = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'repairs': []
        }
        
        try:
            # Check required directories exist
            required_dirs = [
                (self.base_path, 'base_directory'),
                (self.raw_path, 'raw_directory'),
                (self.managed_path, 'managed_directory'),
                (self.unmanaged_path, 'unmanaged_directory'),
                (self.metadata_path, 'metadata_directory')
            ]
            
            for dir_path, dir_name in required_dirs:
                if not dir_path.exists():
                    if validate_only:
                        validation_result['valid'] = False
                        validation_result['errors'].append(f"Missing {dir_name}: {dir_path}")
                    else:
                        # Repair: create missing directory
                        dir_path.mkdir(parents=True, exist_ok=True)
                        validation_result['repairs'].append(f"Created missing {dir_name}: {dir_path}")
                        logger.info(f"Repaired FGD: Created {dir_name} at {dir_path}")
            
            # Check managed subdirectories
            for crd_dir in self.crd_directories:
                crd_path = self.managed_path / crd_dir
                if not crd_path.exists():
                    if validate_only:
                        validation_result['warnings'].append(f"Missing managed subdirectory: {crd_dir}")
                    else:
                        # Repair: create missing CRD directory
                        crd_path.mkdir(parents=True, exist_ok=True)
                        validation_result['repairs'].append(f"Created managed subdirectory: {crd_dir}")
                        logger.info(f"Repaired FGD: Created managed/{crd_dir}")
            
            # Validate manifest files
            manifest_path = self.metadata_path / 'manifest.yaml'
            if not manifest_path.exists():
                if validate_only:
                    validation_result['warnings'].append("Missing manifest.yaml")
                else:
                    # Repair: create manifest
                    self._create_initial_manifests()
                    validation_result['repairs'].append("Created missing manifest.yaml")
                    logger.info("Repaired FGD: Created manifest.yaml")
            
            return validation_result
            
        except Exception as e:
            validation_result['valid'] = False
            validation_result['errors'].append(f"FGD validation error: {str(e)}")
            return validation_result
    
    def _process_raw_directory_comprehensive(self, validate_only: bool) -> Dict[str, Any]:
        """
        Comprehensive processing of raw directory including pre-existing files.
        
        This method ensures ALL files in raw/ are properly processed:
        1. Valid Hedgehog CRs are prepared for ingestion
        2. Invalid files are moved to unmanaged/
        3. Race conditions are handled with file locking
        
        Args:
            validate_only: If True, only validate without making changes
            
        Returns:
            Dict with processing results
        """
        processing_result = {
            'files_processed': 0,
            'files_moved_to_raw': 0,
            'files_moved_to_unmanaged': 0,
            'valid_crs_found': 0,
            'invalid_files_found': 0,
            'errors': [],
            'processing_details': []
        }
        
        try:
            # CRITICAL FIX: Ensure raw directory exists and scan for ALL files
            if not self.raw_path.exists():
                if not validate_only:
                    self.raw_path.mkdir(parents=True, exist_ok=True)
                    logger.info(f"Created raw directory: {self.raw_path}")
                else:
                    processing_result['errors'].append(f"Raw directory does not exist: {self.raw_path}")
                    return processing_result
            
            # Find ALL files in raw directory (including pre-existing)
            raw_files = self._find_all_files_in_raw()
            logger.info(f"Found {len(raw_files)} files in raw directory for processing")
            
            if not raw_files:
                logger.info("No files found in raw directory")
                return processing_result
            
            # Process each file with proper validation
            for file_path in raw_files:
                file_result = self._process_single_raw_file(file_path, validate_only)
                processing_result['files_processed'] += 1
                processing_result['processing_details'].append(file_result)
                
                # Update counters based on result
                if file_result['action'] == 'moved_to_unmanaged':
                    processing_result['files_moved_to_unmanaged'] += 1
                    processing_result['invalid_files_found'] += 1
                elif file_result['action'] == 'ready_for_ingestion':
                    processing_result['valid_crs_found'] += 1
                elif file_result['action'] == 'moved_to_raw':
                    processing_result['files_moved_to_raw'] += 1
                
                if file_result.get('errors'):
                    processing_result['errors'].extend(file_result['errors'])
            
            logger.info(f"Raw directory processing completed: {processing_result['files_processed']} files, {processing_result['valid_crs_found']} valid CRs, {processing_result['invalid_files_found']} invalid files")
            return processing_result
            
        except Exception as e:
            processing_result['errors'].append(f"Raw directory processing error: {str(e)}")
            logger.error(f"Raw directory processing failed: {str(e)}")
            return processing_result
    
    def _find_all_files_in_raw(self) -> List[Path]:
        """
        Find ALL files in raw directory, including subdirectories.
        CRITICAL FIX: Ensures no files are missed during processing.
        """
        all_files = []
        
        try:
            # Use recursive globbing to find all YAML files
            for pattern in ['**/*.yaml', '**/*.yml']:
                all_files.extend(self.raw_path.glob(pattern))
            
            # Also check for files directly in raw/ (non-recursive)
            for pattern in ['*.yaml', '*.yml']:
                direct_files = list(self.raw_path.glob(pattern))
                for file in direct_files:
                    if file not in all_files:
                        all_files.append(file)
            
            # Sort by modification time (oldest first) for consistent processing
            all_files.sort(key=lambda x: x.stat().st_mtime)
            
            logger.debug(f"Found {len(all_files)} files in raw directory: {[f.name for f in all_files]}")
            return all_files
            
        except Exception as e:
            logger.error(f"Error finding files in raw directory: {str(e)}")
            return []
    
    def _process_single_raw_file(self, file_path: Path, validate_only: bool) -> Dict[str, Any]:
        """
        Process a single file from raw directory with proper validation.
        
        Args:
            file_path: Path to the file to process
            validate_only: If True, only validate without making changes
            
        Returns:
            Dict with processing result for this file
        """
        file_result = {
            'file_path': str(file_path),
            'file_name': file_path.name,
            'action': 'none',
            'valid_crs': [],
            'invalid_docs': [],
            'errors': []
        }
        
        try:
            # Read and validate file content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Validate YAML format first
            validation_result = self._validate_yaml_content(content)
            
            if not validation_result['valid']:
                # Invalid YAML - move to unmanaged
                file_result['errors'].append(validation_result['error'])
                
                if not validate_only:
                    self._move_file_to_unmanaged(file_path, f"Invalid YAML: {validation_result['error']}")
                    file_result['action'] = 'moved_to_unmanaged'
                else:
                    file_result['action'] = 'should_move_to_unmanaged'
                
                return file_result
            
            # Check if contains valid Hedgehog CRs
            cr_validation = self._validate_hedgehog_crs(validation_result['documents'])
            file_result['valid_crs'] = cr_validation['valid_crs']
            file_result['invalid_docs'] = cr_validation['invalid_docs']
            
            if cr_validation['valid_crs']:
                # Valid CRs found - ready for ingestion
                file_result['action'] = 'ready_for_ingestion'
                logger.info(f"File {file_path.name} contains {len(cr_validation['valid_crs'])} valid Hedgehog CRs")
            else:
                # No valid CRs - move to unmanaged
                if not validate_only:
                    self._move_file_to_unmanaged(file_path, "No valid Hedgehog CRs found")
                    file_result['action'] = 'moved_to_unmanaged'
                else:
                    file_result['action'] = 'should_move_to_unmanaged'
            
            return file_result
            
        except Exception as e:
            error_msg = f"Error processing file {file_path}: {str(e)}"
            file_result['errors'].append(error_msg)
            logger.error(error_msg)
            return file_result
    
    def _validate_yaml_content(self, content: str) -> Dict[str, Any]:
        """
        Validate YAML content and parse documents.
        
        Returns:
            Dict with validation result and parsed documents
        """
        try:
            documents = list(yaml.safe_load_all(content))
            # Filter out None documents
            documents = [doc for doc in documents if doc is not None]
            
            return {
                'valid': True,
                'documents': documents,
                'document_count': len(documents)
            }
            
        except yaml.YAMLError as e:
            return {
                'valid': False,
                'error': f'YAML parsing error: {str(e)}',
                'documents': [],
                'document_count': 0
            }
    
    def _validate_hedgehog_crs(self, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validate documents as Hedgehog Custom Resources.
        
        Returns:
            Dict with valid and invalid document lists
        """
        valid_crs = []
        invalid_docs = []
        
        for i, doc in enumerate(documents):
            if not isinstance(doc, dict):
                invalid_docs.append({
                    'index': i,
                    'reason': f'Not a dictionary: {type(doc)}',
                    'document': doc
                })
                continue
            
            # Check required Kubernetes fields
            if not all(field in doc for field in ['apiVersion', 'kind', 'metadata']):
                invalid_docs.append({
                    'index': i,
                    'reason': 'Missing required fields (apiVersion, kind, metadata)',
                    'document': doc
                })
                continue
            
            # Check if it's a Hedgehog CR
            api_version = doc.get('apiVersion', '')
            if 'githedgehog.com' not in api_version:
                invalid_docs.append({
                    'index': i,
                    'reason': f'Not a Hedgehog CR: {api_version}',
                    'document': doc
                })
                continue
            
            # Check metadata has name
            metadata = doc.get('metadata', {})
            if not isinstance(metadata, dict) or 'name' not in metadata:
                invalid_docs.append({
                    'index': i,
                    'reason': 'Invalid metadata: missing name field',
                    'document': doc
                })
                continue
            
            # Valid Hedgehog CR
            valid_crs.append({
                'index': i,
                'kind': doc.get('kind'),
                'name': metadata.get('name'),
                'apiVersion': api_version,
                'document': doc
            })
        
        return {
            'valid_crs': valid_crs,
            'invalid_docs': invalid_docs
        }
    
    def _move_file_to_unmanaged(self, file_path: Path, reason: str):
        """
        Move a file to the unmanaged directory with proper error handling.
        
        Args:
            file_path: Path to the file to move
            reason: Reason for moving to unmanaged
        """
        try:
            # Ensure unmanaged directory exists
            self.unmanaged_path.mkdir(parents=True, exist_ok=True)
            
            # Generate unique filename in unmanaged directory
            target_path = self.unmanaged_path / file_path.name
            counter = 1
            while target_path.exists():
                name_parts = file_path.stem, counter, file_path.suffix
                target_path = self.unmanaged_path / f"{name_parts[0]}_{name_parts[1]}{name_parts[2]}"
                counter += 1
            
            # Move file with metadata
            shutil.move(str(file_path), str(target_path))
            
            # Create metadata file explaining why it was moved
            metadata_path = target_path.with_suffix(target_path.suffix + '.metadata')
            metadata = {
                'moved_at': timezone.now().isoformat(),
                'original_path': str(file_path),
                'reason': reason,
                'fabric': self.fabric.name
            }
            
            with open(metadata_path, 'w') as f:
                yaml.safe_dump(metadata, f, default_flow_style=False)
            
            logger.info(f"Moved file to unmanaged: {file_path.name} -> {target_path.name} (reason: {reason})")
            
        except Exception as e:
            error_msg = f"Failed to move file {file_path} to unmanaged: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)
    
    def _handle_concurrent_access_safely(self):
        """
        Handle concurrent access to raw directory with file locking.
        CRITICAL FIX: Prevents race conditions during file processing.
        """
        try:
            # Create lock file to prevent concurrent processing
            lock_file = self.metadata_path / 'processing.lock'
            
            if lock_file.exists():
                # Check if lock is stale (older than 5 minutes)
                lock_age = time.time() - lock_file.stat().st_mtime
                if lock_age > 300:  # 5 minutes
                    logger.warning(f"Removing stale lock file: {lock_file}")
                    lock_file.unlink()
                else:
                    raise Exception(f"Another sync process is already running (lock age: {lock_age:.1f}s)")
            
            # Create lock file
            with open(lock_file, 'w') as f:
                json.dump({
                    'pid': os.getpid(),
                    'started_at': timezone.now().isoformat(),
                    'fabric': self.fabric.name
                }, f)
            
            # Register cleanup on exit
            import atexit
            atexit.register(lambda: lock_file.unlink() if lock_file.exists() else None)
            
        except Exception as e:
            logger.error(f"Concurrent access handling failed: {str(e)}")
            raise
    
    def _update_sync_metadata(self, sync_result: Dict[str, Any]):
        """
        Update sync metadata with operation results.
        
        Args:
            sync_result: Results from sync operation
        """
        try:
            sync_log_path = self.metadata_path / 'sync-log.yaml'
            
            # Load existing log or create new one
            if sync_log_path.exists():
                with open(sync_log_path, 'r') as f:
                    sync_log = yaml.safe_load(f) or {}
            else:
                sync_log = {
                    'version': '1.0',
                    'created_at': timezone.now().isoformat(),
                    'sync_operations': []
                }
            
            # Add this sync operation
            sync_operation = {
                'timestamp': sync_result['started_at'].isoformat(),
                'completed_at': sync_result.get('completed_at', timezone.now()).isoformat(),
                'success': sync_result['success'],
                'files_processed': sync_result['files_processed'],
                'files_moved_to_unmanaged': sync_result['files_moved_to_unmanaged'],
                'structure_repairs': len(sync_result.get('structure_repairs', [])),
                'validation_errors': len(sync_result.get('validation_errors', [])),
                'validate_only': sync_result.get('validate_only', False)
            }
            
            if not sync_result['success']:
                sync_operation['error'] = sync_result.get('error', 'Unknown error')
            
            sync_log['sync_operations'].append(sync_operation)
            sync_log['last_sync'] = sync_operation
            
            # Keep only last 50 operations
            if len(sync_log['sync_operations']) > 50:
                sync_log['sync_operations'] = sync_log['sync_operations'][-50:]
            
            # Write updated log
            with open(sync_log_path, 'w') as f:
                yaml.safe_dump(sync_log, f, default_flow_style=False, sort_keys=False)
            
            logger.info(f"Updated sync metadata: {sync_operation}")
            
        except Exception as e:
            logger.error(f"Failed to update sync metadata: {str(e)}")
    
    def schedule_periodic_sync(self, interval_minutes: int = 60) -> Dict[str, Any]:
        """
        Schedule periodic sync validation with configurable intervals.
        
        Args:
            interval_minutes: Minutes between sync validations (default: 60)
            
        Returns:
            Dict with scheduling result
        """
        try:
            logger.info(f"Scheduling periodic sync for fabric {self.fabric.name} every {interval_minutes} minutes")
            
            # Create scheduler metadata
            scheduler_config = {
                'fabric_name': self.fabric.name,
                'fabric_id': self.fabric.id,
                'interval_minutes': interval_minutes,
                'enabled': True,
                'created_at': timezone.now().isoformat(),
                'next_run': (timezone.now() + timedelta(minutes=interval_minutes)).isoformat()
            }
            
            # Store scheduler config
            scheduler_path = self.metadata_path / 'periodic-sync.yaml'
            with open(scheduler_path, 'w') as f:
                yaml.safe_dump(scheduler_config, f, default_flow_style=False)
            
            # Start background thread for periodic sync
            sync_thread = threading.Thread(
                target=self._periodic_sync_worker,
                args=(interval_minutes,),
                daemon=True
            )
            sync_thread.start()
            
            return {
                'success': True,
                'message': f"Periodic sync scheduled every {interval_minutes} minutes",
                'config': scheduler_config
            }
            
        except Exception as e:
            logger.error(f"Failed to schedule periodic sync: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _periodic_sync_worker(self, interval_minutes: int):
        """
        Background worker for periodic sync validation.
        
        Args:
            interval_minutes: Minutes between sync validations
        """
        logger.info(f"Started periodic sync worker for fabric {self.fabric.name}")
        
        while True:
            try:
                time.sleep(interval_minutes * 60)  # Convert to seconds
                
                # Check if periodic sync is still enabled
                scheduler_path = self.metadata_path / 'periodic-sync.yaml'
                if not scheduler_path.exists():
                    logger.info(f"Periodic sync disabled for fabric {self.fabric.name}")
                    break
                
                with open(scheduler_path, 'r') as f:
                    config = yaml.safe_load(f)
                
                if not config.get('enabled', False):
                    logger.info(f"Periodic sync disabled for fabric {self.fabric.name}")
                    break
                
                # Run validation-only sync
                logger.info(f"Running periodic sync validation for fabric {self.fabric.name}")
                sync_result = self.sync_raw_directory(validate_only=True)
                
                # Log validation results
                if sync_result['success']:
                    if sync_result.get('validation_errors'):
                        logger.warning(f"Periodic validation found {len(sync_result['validation_errors'])} issues for fabric {self.fabric.name}")
                    else:
                        logger.info(f"Periodic validation passed for fabric {self.fabric.name}")
                else:
                    logger.error(f"Periodic validation failed for fabric {self.fabric.name}: {sync_result.get('error')}")
                
                # Update next run time
                config['last_run'] = timezone.now().isoformat()
                config['next_run'] = (timezone.now() + timedelta(minutes=interval_minutes)).isoformat()
                
                with open(scheduler_path, 'w') as f:
                    yaml.safe_dump(config, f, default_flow_style=False)
                
            except Exception as e:
                logger.error(f"Periodic sync worker error for fabric {self.fabric.name}: {str(e)}")
                # Continue running despite errors
                continue
    
    def get_onboarding_status(self) -> Dict[str, Any]:
        """Get the current onboarding status for this fabric."""
        status = {
            'fabric_name': self.fabric.name,
            'fabric_id': self.fabric.id,
            'gitops_initialized': getattr(self.fabric, 'gitops_initialized', False),
            'raw_directory_path': getattr(self.fabric, 'raw_directory_path', ''),
            'managed_directory_path': getattr(self.fabric, 'managed_directory_path', ''),
            'archive_strategy': getattr(self.fabric, 'archive_strategy', 'not_set'),
            'structure_validation': self.validate_structure()
        }
        
        # Add sync status if available
        try:
            if self.metadata_path:
                sync_log_path = self.metadata_path / 'sync-log.yaml'
                if sync_log_path.exists():
                    with open(sync_log_path, 'r') as f:
                        sync_log = yaml.safe_load(f)
                    status['last_sync'] = sync_log.get('last_sync')
                
                periodic_sync_path = self.metadata_path / 'periodic-sync.yaml'
                if periodic_sync_path.exists():
                    with open(periodic_sync_path, 'r') as f:
                        periodic_config = yaml.safe_load(f)
                    status['periodic_sync'] = periodic_config
        except Exception as e:
            logger.warning(f"Could not load sync status: {str(e)}")
        
        return status

    def sync_github_repository(self, validate_only: bool = False) -> Dict[str, Any]:
        """
        Synchronize with GitHub repository, processing pre-existing files.
        
        This method handles GitHub integration for GitOps sync:
        1. Fetch files from GitHub repository
        2. Identify pre-existing YAML files in root directory
        3. Validate and move them to appropriate directories
        4. Push changes back to GitHub
        
        Args:
            validate_only: If True, only validate without making changes
            
        Returns:
            Dict with GitHub sync results
        """
        github_result = {
            'success': False,
            'fabric_name': self.fabric.name,
            'started_at': timezone.now(),
            'validate_only': validate_only,
            'files_processed': 0,
            'github_operations': [],
            'errors': []
        }
        
        try:
            # Check if fabric has GitHub repository configured
            if not hasattr(self.fabric, 'git_repository') or not self.fabric.git_repository:
                raise Exception("No Git repository configured for this fabric")
            
            git_repo = self.fabric.git_repository
            if 'github.com' not in git_repo.url:
                raise Exception(f"Repository {git_repo.url} is not a GitHub repository")
            
            # Initialize GitHub client
            github_client = self._get_github_client(git_repo)
            
            # Get fabric path in repository
            fabric_path = self._get_fabric_path_in_repo()
            
            # CRITICAL FIX: Analyze the raw/ subdirectory where YAML files actually exist
            raw_fabric_path = f"{fabric_path}/raw"
            analysis = github_client.analyze_fabric_directory(raw_fabric_path)
            github_result['github_operations'].append(f"Analyzed fabric raw directory: {len(analysis.get('yaml_files_in_root', []))} YAML files found")
            
            # Process each YAML file found in root
            for file_info in analysis.get('yaml_files_in_root', []):
                file_result = self._process_github_file(github_client, fabric_path, file_info, validate_only)
                github_result['files_processed'] += 1
                github_result['github_operations'].extend(file_result.get('operations', []))
                if file_result.get('errors'):
                    github_result['errors'].extend(file_result['errors'])
            
            github_result['success'] = True
            github_result['completed_at'] = timezone.now()
            github_result['message'] = f"GitHub sync completed: {github_result['files_processed']} files processed"
            
            logger.info(f"GitHub sync completed for fabric {self.fabric.name}")
            return github_result
            
        except Exception as e:
            logger.error(f"GitHub sync failed for fabric {self.fabric.name}: {str(e)}")
            github_result['success'] = False
            github_result['error'] = str(e)
            github_result['completed_at'] = timezone.now()
            return github_result
    
    def _get_github_client(self, git_repo) -> 'GitHubClient':
        """
        Create GitHub client for repository operations.
        
        Args:
            git_repo: Git repository configuration
            
        Returns:
            GitHubClient instance
        """
        try:
            # Parse GitHub URL to get owner/repo
            import re
            url_pattern = r'github\.com[:/]([^/]+)/([^/\.]+)'
            match = re.search(url_pattern, git_repo.url)
            
            if not match:
                raise Exception(f"Could not parse GitHub owner/repo from URL: {git_repo.url}")
            
            owner, repo_name = match.groups()
            
            # Get GitHub token from git repository credentials first, then fallback to settings/environment
            github_token = None
            
            # Try to get token from GitRepository credentials
            try:
                if hasattr(git_repo, 'get_credentials'):
                    credentials = git_repo.get_credentials()
                    github_token = credentials.get('token') or credentials.get('access_token')
            except Exception as e:
                logger.warning(f"Could not get token from git repository credentials: {e}")
            
            # Fallback to settings or environment
            if not github_token:
                github_token = getattr(settings, 'GITHUB_TOKEN', None) or os.environ.get('GITHUB_TOKEN')
            
            if not github_token:
                raise Exception("GitHub token not configured. Set token in GitRepository credentials, GITHUB_TOKEN in settings, or environment.")
            
            return GitHubClient(token=github_token, owner=owner, repo=repo_name)
            
        except Exception as e:
            raise Exception(f"Failed to create GitHub client: {str(e)}")
    
    def _get_fabric_path_in_repo(self) -> str:
        """Get the fabric path within the GitHub repository."""
        # Use fabric's gitops_directory if available
        if hasattr(self.fabric, 'gitops_directory') and self.fabric.gitops_directory:
            path = self.fabric.gitops_directory.strip('/')
            return path if path else f"gitops/hedgehog/{self.fabric.name.lower()}"
        
        # Default path structure
        return f"gitops/hedgehog/{self.fabric.name.lower()}"
    
    def _process_github_file(self, github_client, fabric_path: str, file_info: Dict, validate_only: bool) -> Dict[str, Any]:
        """Process a single file from GitHub repository."""
        file_result = {
            'file_name': file_info['name'],
            'operations': [],
            'errors': []
        }
        
        try:
            # Get file content from GitHub
            content = github_client.get_file_content(file_info['path'])
            if not content:
                file_result['errors'].append(f"Could not retrieve content for {file_info['name']}")
                return file_result
            
            # Validate content
            validation = self._validate_yaml_content(content)
            
            if not validation['valid']:
                # Invalid YAML - move to unmanaged in GitHub
                if not validate_only:
                    unmanaged_path = f"{fabric_path}/unmanaged/{file_info['name']}"
                    if github_client.create_or_update_file(
                        unmanaged_path,
                        content,
                        f"Move {file_info['name']} to unmanaged/ (invalid YAML)"
                    ):
                        file_result['operations'].append(f"Moved to unmanaged/{file_info['name']}")
                        
                        # Delete from root
                        if github_client.delete_file(
                            file_info['path'],
                            file_info['sha'],
                            f"Remove {file_info['name']} from root after moving to unmanaged/"
                        ):
                            file_result['operations'].append("Removed from root")
                else:
                    file_result['operations'].append(f"Would move to unmanaged/{file_info['name']} (invalid YAML)")
                
                return file_result
            
            # Check for valid Hedgehog CRs
            cr_validation = self._validate_hedgehog_crs(validation['documents'])
            
            if cr_validation['valid_crs']:
                # Valid CRs - download to local raw directory and process
                if not validate_only:
                    # CRITICAL FIX: Download file to local raw directory for processing
                    try:
                        # Ensure local raw directory exists
                        if not self.raw_path:
                            self.raw_path = self._get_base_directory_path() / 'raw'
                        self.raw_path.mkdir(parents=True, exist_ok=True)
                        
                        # Download file to local raw directory
                        local_file_path = self.raw_path / file_info['name']
                        with open(local_file_path, 'w', encoding='utf-8') as f:
                            f.write(content)
                        
                        file_result['operations'].append(f"Downloaded to local raw/{file_info['name']}")
                        logger.info(f"GitHub sync: Downloaded {file_info['name']} to local raw directory")
                        
                        # CRITICAL FIX: Trigger local raw directory processing
                        local_sync_result = self.sync_raw_directory(validate_only=False)
                        if local_sync_result['success']:
                            file_result['operations'].append(f"Local processing completed: {local_sync_result['files_processed']} files")
                            logger.info(f"GitHub sync: Local processing successful for {file_info['name']}")
                        else:
                            file_result['errors'].append(f"Local processing failed: {local_sync_result.get('error', 'Unknown error')}")
                            logger.error(f"GitHub sync: Local processing failed for {file_info['name']}: {local_sync_result.get('error')}")
                        
                        # Move file to raw/ in GitHub (for organization)
                        raw_path = f"{fabric_path}/raw/{file_info['name']}"
                        if github_client.create_or_update_file(
                            raw_path,
                            content,
                            f"Move {file_info['name']} to raw/ after local processing"
                        ):
                            file_result['operations'].append(f"Moved to raw/{file_info['name']} in GitHub")
                            
                            # Delete from root
                            if github_client.delete_file(
                                file_info['path'],
                                file_info['sha'],
                                f"Remove {file_info['name']} from root after processing"
                            ):
                                file_result['operations'].append("Removed from GitHub root")
                    
                    except Exception as local_error:
                        error_msg = f"Failed to process locally: {str(local_error)}"
                        file_result['errors'].append(error_msg)
                        logger.error(f"GitHub sync local processing error: {error_msg}")
                else:
                    file_result['operations'].append(f"Would download and process locally: {len(cr_validation['valid_crs'])} valid CRs")
            else:
                # No valid CRs - download to local unmanaged and move in GitHub
                if not validate_only:
                    try:
                        # Ensure local unmanaged directory exists
                        if not self.unmanaged_path:
                            self.unmanaged_path = self._get_base_directory_path() / 'unmanaged'
                        self.unmanaged_path.mkdir(parents=True, exist_ok=True)
                        
                        # Download file to local unmanaged directory
                        local_file_path = self.unmanaged_path / file_info['name']
                        with open(local_file_path, 'w', encoding='utf-8') as f:
                            f.write(content)
                        
                        file_result['operations'].append(f"Downloaded to local unmanaged/{file_info['name']}")
                        logger.info(f"GitHub sync: Downloaded invalid file {file_info['name']} to local unmanaged directory")
                        
                        # Move to unmanaged in GitHub
                        unmanaged_path = f"{fabric_path}/unmanaged/{file_info['name']}"
                        if github_client.create_or_update_file(
                            unmanaged_path,
                            content,
                            f"Move {file_info['name']} to unmanaged/ (no valid Hedgehog CRs)"
                        ):
                            file_result['operations'].append(f"Moved to unmanaged/{file_info['name']} in GitHub")
                            
                            # Delete from root
                            if github_client.delete_file(
                                file_info['path'],
                                file_info['sha'],
                                f"Remove {file_info['name']} from root after moving to unmanaged/"
                            ):
                                file_result['operations'].append("Removed from GitHub root")
                    
                    except Exception as local_error:
                        error_msg = f"Failed to download to local unmanaged: {str(local_error)}"
                        file_result['errors'].append(error_msg)
                        logger.error(f"GitHub sync unmanaged download error: {error_msg}")
                else:
                    file_result['operations'].append(f"Would download to local unmanaged: {file_info['name']} (no valid CRs)")
            
            return file_result
            
        except Exception as e:
            file_result['errors'].append(f"Error processing {file_info['name']}: {str(e)}")
            return file_result

    def _ensure_directory_structure(self):
        """Ensure all required GitOps directories exist with proper permissions"""
        try:
            # Get all required directories
            required_dirs = [
                self.raw_path,
                self.managed_path,
                self.unmanaged_path,
                os.path.join(self._get_base_directory_path(), '.hnp')
            ]
            
            # Create managed subdirectories for each CRD type
            managed_subdirs = [
                'vpcs', 'externals', 'servers', 'switches', 'connections', 
                'switchgroups', 'vlannamespaces', 'ipv4namespaces',
                'externalattachments', 'externalpeerings', 'vpcattachments', 'vpcpeerings'
            ]
            
            for subdir in managed_subdirs:
                required_dirs.append(os.path.join(self.managed_path, subdir))
            
            # Create directories with error handling
            for dir_path in required_dirs:
                try:
                    os.makedirs(dir_path, mode=0o755, exist_ok=True)
                    
                    # Validate write permissions by creating and removing a test file
                    test_file = os.path.join(dir_path, '.write_test')
                    with open(test_file, 'w') as f:
                        f.write('test')
                    os.remove(test_file)
                    
                except (OSError, PermissionError) as e:
                    raise Exception(f"Failed to create/access directory {dir_path}: {e}")
            
            logger.info(f"Successfully ensured directory structure for fabric {self.fabric.name}")
            
        except Exception as e:
            logger.error(f"Failed to ensure directory structure: {e}")
            raise

    def _has_files_in_raw(self):
        """Check if there are any YAML files in the raw directory"""
        try:
            if not os.path.exists(self.raw_path):
                return False
            
            from pathlib import Path
            raw_files = list(Path(self.raw_path).glob('*.yaml')) + list(Path(self.raw_path).glob('*.yml'))
            return len(raw_files) > 0
            
        except Exception as e:
            logger.warning(f"Error checking raw directory files: {e}")
            return False

    def _execute_ingestion_with_validation(self):
        """Execute ingestion with comprehensive validation and error handling"""
        try:
            logger.info(f"=== DIAGNOSTIC: Starting _execute_ingestion_with_validation for fabric {self.fabric.name} ===")
            logger.info(f"DIAGNOSTIC: Fabric ID: {self.fabric.id}")
            logger.info(f"DIAGNOSTIC: Raw path: {self.raw_path}")
            logger.info(f"DIAGNOSTIC: Managed path: {self.managed_path}")
            
            # Validate service import  
            try:
                logger.info("DIAGNOSTIC: Attempting to import GitOpsIngestionService...")
                from .gitops_ingestion_service import GitOpsIngestionService
                logger.info("DIAGNOSTIC: GitOpsIngestionService imported successfully")
            except ImportError as e:
                logger.error(f"DIAGNOSTIC: ImportError for GitOpsIngestionService: {e}")
                import traceback
                logger.error(f"DIAGNOSTIC: Import traceback: {traceback.format_exc()}")
                raise Exception(f"GitOpsIngestionService not available: {e}")
            
            # Pre-ingestion validation
            from pathlib import Path
            logger.info("DIAGNOSTIC: Scanning for YAML files in raw directory...")
            raw_files = list(Path(self.raw_path).glob('*.yaml')) + list(Path(self.raw_path).glob('*.yml'))
            logger.info(f"DIAGNOSTIC: Found {len(raw_files)} YAML files: {[str(f) for f in raw_files]}")
            
            if not raw_files:
                logger.info("DIAGNOSTIC: No files to process, returning early success")
                return {
                    'success': True, 
                    'message': 'No files to process', 
                    'processed_count': 0,
                    'documents_extracted': [],
                    'files_created': []
                }
            
            # Check file contents before processing
            for raw_file in raw_files:
                try:
                    file_size = raw_file.stat().st_size
                    logger.info(f"DIAGNOSTIC: File {raw_file.name} size: {file_size} bytes")
                    with open(raw_file, 'r') as f:
                        first_lines = f.read(200)  # First 200 chars
                        logger.info(f"DIAGNOSTIC: File {raw_file.name} starts with: {repr(first_lines)}")
                except Exception as file_e:
                    logger.error(f"DIAGNOSTIC: Error reading file {raw_file}: {file_e}")
            
            logger.info(f"DIAGNOSTIC: Starting ingestion of {len(raw_files)} files from raw directory")
            
            # Execute ingestion
            logger.info("DIAGNOSTIC: Creating GitOpsIngestionService instance...")
            try:
                ingestion_service = GitOpsIngestionService(self.fabric)
                logger.info(f"DIAGNOSTIC: GitOpsIngestionService created successfully for fabric {self.fabric.name}")
                
                # Check service state before processing
                logger.info(f"DIAGNOSTIC: Service raw_path: {ingestion_service.raw_path}")
                logger.info(f"DIAGNOSTIC: Service managed_path: {ingestion_service.managed_path}")
                logger.info(f"DIAGNOSTIC: Service metadata_path: {ingestion_service.metadata_path}")
                
            except Exception as service_e:
                logger.error(f"DIAGNOSTIC: Failed to create GitOpsIngestionService: {service_e}")
                import traceback
                logger.error(f"DIAGNOSTIC: Service creation traceback: {traceback.format_exc()}")
                raise
            
            logger.info("DIAGNOSTIC: Calling process_raw_directory()...")
            try:
                result = ingestion_service.process_raw_directory()
                logger.info(f"DIAGNOSTIC: process_raw_directory() returned: {result}")
            except Exception as proc_e:
                logger.error(f"DIAGNOSTIC: process_raw_directory() failed: {proc_e}")
                import traceback
                logger.error(f"DIAGNOSTIC: Process traceback: {traceback.format_exc()}")
                raise
            
            # Enhanced post-ingestion validation
            logger.info("DIAGNOSTIC: Starting post-ingestion validation...")
            if result.get('success'):
                logger.info("DIAGNOSTIC: Result indicates success, verifying managed files...")
                # Verify files were actually created in managed directories
                try:
                    managed_files = list(Path(self.managed_path).glob('**/*.yaml'))
                    logger.info(f"DIAGNOSTIC: Found {len(managed_files)} managed files: {[str(f) for f in managed_files]}")
                except Exception as glob_e:
                    logger.error(f"DIAGNOSTIC: Error globbing managed files: {glob_e}")
                    managed_files = []
                
                expected_files = result.get('files_created', [])
                logger.info(f"DIAGNOSTIC: Expected {len(expected_files)} files to be created: {expected_files}")
                
                if len(expected_files) > 0 and len(managed_files) == 0:
                    # Files were supposed to be processed but nothing in managed/ - this is a failure
                    error_msg = f"Files processed ({len(expected_files)} expected) but nothing created in managed directories"
                    logger.error(f"DIAGNOSTIC: {error_msg}")
                    return {
                        'success': False, 
                        'error': error_msg,
                        'processed_count': 0,
                        'documents_extracted': result.get('documents_extracted', []),
                        'files_created': []
                    }
                
                logger.info(f"DIAGNOSTIC: Successfully processed {len(expected_files)} files into {len(managed_files)} managed files")
            else:
                logger.error(f"DIAGNOSTIC: Result indicates failure: {result.get('error', 'Unknown error')}")
            
            logger.info(f"DIAGNOSTIC: Final result: {result}")
            return result
            
        except Exception as e:
            error_msg = f"Ingestion execution failed: {str(e)}"
            logger.error(f"DIAGNOSTIC: Exception in _execute_ingestion_with_validation: {error_msg}")
            import traceback
            logger.error(f"DIAGNOSTIC: Full traceback: {traceback.format_exc()}")
            return {
                'success': False, 
                'error': error_msg,
                'processed_count': 0,
                'documents_extracted': [],
                'files_created': []
            }


class GitHubClient:
    """GitHub API client for GitOps operations."""
    
    def __init__(self, token: str, owner: str, repo: str):
        self.token = token
        self.owner = owner
        self.repo = repo
        self.api_base = f"https://api.github.com/repos/{owner}/{repo}"
        self.headers = {
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json'
        }
    
    def analyze_fabric_directory(self, fabric_path: str) -> Dict[str, Any]:
        """Analyze the current state of the fabric directory in GitHub."""
        contents = self.get_directory_contents(fabric_path)
        
        analysis = {
            'yaml_files_in_root': [],
            'directories': [],
            'other_files': []
        }
        
        # Handle case where directory doesn't exist (empty contents)
        if not contents:
            logger.info(f"Directory {fabric_path} not found or empty in GitHub repository")
            return analysis
        
        for item in contents:
            if item['type'] == 'file':
                if item['name'].endswith(('.yaml', '.yml')):
                    analysis['yaml_files_in_root'].append({
                        'name': item['name'],
                        'path': item['path'],
                        'sha': item['sha']
                    })
                else:
                    analysis['other_files'].append(item)
            elif item['type'] == 'dir':
                analysis['directories'].append(item['name'])
        
        return analysis
    
    def get_directory_contents(self, path: str = "") -> List[Dict]:
        """Get contents of a directory in the GitHub repository."""
        url = f"{self.api_base}/contents/{path}" if path else f"{self.api_base}/contents"
        
        try:
            response = requests.get(url, headers=self.headers)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                # Directory doesn't exist - this is expected for new repositories
                logger.info(f"Directory {path} not found in GitHub repository (404)")
                return []
            else:
                logger.error(f"Failed to get contents for {path}: {response.status_code} - {response.text}")
                return []
        except Exception as e:
            logger.error(f"Error getting contents for {path}: {e}")
            return []
    
    def get_file_content(self, file_path: str) -> Optional[str]:
        """Get content of a file from GitHub."""
        url = f"{self.api_base}/contents/{file_path}"
        
        try:
            response = requests.get(url, headers=self.headers)
            if response.status_code == 200:
                file_data = response.json()
                # Decode base64 content
                content = base64.b64decode(file_data['content']).decode('utf-8')
                return content
            else:
                logger.error(f"Failed to get file {file_path}: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            logger.error(f"Error getting file {file_path}: {e}")
            return None
    
    def create_or_update_file(self, file_path: str, content: str, message: str, sha: str = None) -> bool:
        """Create or update a file in GitHub."""
        url = f"{self.api_base}/contents/{file_path}"
        
        # Encode content to base64
        encoded_content = base64.b64encode(content.encode('utf-8')).decode('utf-8')
        
        data = {
            'message': message,
            'content': encoded_content
        }
        
        if sha:
            data['sha'] = sha
        
        try:
            response = requests.put(url, headers=self.headers, json=data)
            if response.status_code in [200, 201]:
                logger.info(f"Successfully created/updated {file_path}")
                return True
            else:
                logger.error(f"Failed to create/update {file_path}: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error creating/updating {file_path}: {e}")
            return False
    
    def delete_file(self, file_path: str, sha: str, message: str) -> bool:
        """Delete a file from GitHub."""
        url = f"{self.api_base}/contents/{file_path}"
        
        data = {
            'message': message,
            'sha': sha
        }
        
        try:
            response = requests.delete(url, headers=self.headers, json=data)
            if response.status_code == 200:
                logger.info(f"Successfully deleted {file_path}")
                return True
            else:
                logger.error(f"Failed to delete {file_path}: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error deleting {file_path}: {e}")
            return False