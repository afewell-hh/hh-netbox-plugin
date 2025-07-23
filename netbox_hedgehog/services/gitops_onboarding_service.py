"""
GitOps Onboarding Service

Handles initialization of GitOps directory structure and migration of existing files.
Creates the proper directory layout for the new bidirectional file management system.
"""

import os
import logging
import yaml
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from django.utils import timezone
from django.db import transaction

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
            self.metadata_path = self.base_path / '.hnp'
            
            with transaction.atomic():
                # Step 1: Create directory structure
                self._create_directory_structure()
                
                # Step 2: Scan for existing files and migrate them
                existing_files = self._scan_existing_files()
                if existing_files:
                    self._migrate_existing_files(existing_files)
                
                # Step 3: Create initial manifests
                self._create_initial_manifests()
                
                # Step 4: Update fabric model
                self._update_fabric_model()
                
                self.onboarding_result['success'] = True
                self.onboarding_result['completed_at'] = timezone.now()
                self.onboarding_result['message'] = f"Successfully initialized GitOps structure for fabric {self.fabric.name}"
                
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
    
    def get_onboarding_status(self) -> Dict[str, Any]:
        """Get the current onboarding status for this fabric."""
        return {
            'fabric_name': self.fabric.name,
            'fabric_id': self.fabric.id,
            'gitops_initialized': getattr(self.fabric, 'gitops_initialized', False),
            'raw_directory_path': getattr(self.fabric, 'raw_directory_path', ''),
            'managed_directory_path': getattr(self.fabric, 'managed_directory_path', ''),
            'archive_strategy': getattr(self.fabric, 'archive_strategy', 'not_set'),
            'structure_validation': self.validate_structure()
        }