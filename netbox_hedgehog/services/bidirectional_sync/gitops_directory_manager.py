"""
GitOps Directory Manager

This module provides comprehensive directory management for GitOps repositories,
implementing the three-directory structure (raw/, unmanaged/, managed/) and
handling directory initialization, validation, and maintenance.
"""

import os
import json
import logging
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

from django.utils import timezone
from django.db import transaction

logger = logging.getLogger(__name__)


class DirectoryInitResult:
    """Result of directory initialization operation"""
    
    def __init__(self, success: bool, message: str = '', directories_created: List[str] = None,
                 errors: List[str] = None, warnings: List[str] = None):
        self.success = success
        self.message = message
        self.directories_created = directories_created or []
        self.errors = errors or []
        self.warnings = warnings or []
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'message': self.message,
            'directories_created': self.directories_created,
            'errors': self.errors,
            'warnings': self.warnings,
            'directories_count': len(self.directories_created)
        }


class ValidationResult:
    """Result of directory structure validation"""
    
    def __init__(self, valid: bool, issues: List[str] = None, 
                 missing_directories: List[str] = None, 
                 extra_files: List[str] = None):
        self.valid = valid
        self.issues = issues or []
        self.missing_directories = missing_directories or []
        self.extra_files = extra_files or []
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'valid': self.valid,
            'issues': self.issues,
            'missing_directories': self.missing_directories,
            'extra_files': self.extra_files,
            'issue_count': len(self.issues)
        }


class IngestionResult:
    """Result of file ingestion operation"""
    
    def __init__(self, success: bool, files_processed: int = 0, 
                 files_ingested: int = 0, files_archived: int = 0,
                 errors: List[str] = None, warnings: List[str] = None):
        self.success = success
        self.files_processed = files_processed
        self.files_ingested = files_ingested
        self.files_archived = files_archived
        self.errors = errors or []
        self.warnings = warnings or []
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'files_processed': self.files_processed,
            'files_ingested': self.files_ingested,
            'files_archived': self.files_archived,
            'errors': self.errors,
            'warnings': self.warnings,
            'error_count': len(self.errors)
        }


class GitOpsDirectoryManager:
    """
    Manages GitOps directory structure and file operations.
    
    This class implements the comprehensive directory management system for
    GitOps repositories, providing initialization, validation, and maintenance
    of the three-directory structure (raw/, unmanaged/, managed/).
    """
    
    # Standard directory structure
    STANDARD_DIRECTORIES = [
        'raw',
        'raw/pending',
        'raw/processed',
        'raw/errors',
        'unmanaged',
        'unmanaged/external-configs',
        'unmanaged/manual-overrides',
        'managed',
        'managed/vpcs',
        'managed/connections',
        'managed/switches',
        'managed/servers',
        'managed/switch-groups',
        'managed/metadata'
    ]
    
    # Standard metadata files
    METADATA_FILES = {
        'managed/metadata/directory-info.json': {
            'created_by': 'hedgehog-netbox-plugin',
            'structure_version': '1.0',
            'created_at': None,  # Will be set during creation
            'description': 'HNP managed GitOps directory structure'
        },
        'raw/README.md': """# Raw Directory

This directory contains files awaiting ingestion into the managed GitOps structure.

## Subdirectories:
- `pending/`: Files awaiting validation and processing
- `processed/`: Successfully processed files (archived)
- `errors/`: Files that failed validation or processing

## Usage:
Place YAML files here for automatic ingestion into the managed structure.
Files will be validated, processed, and moved to appropriate subdirectories.
""",
        'unmanaged/README.md': """# Unmanaged Directory

This directory contains files not managed by HNP but part of the GitOps workflow.

## Subdirectories:
- `external-configs/`: Configuration files from external sources
- `manual-overrides/`: Manual configuration overrides

## Note:
Files in this directory are not automatically processed by HNP but are preserved
during sync operations to maintain GitOps workflow integrity.
""",
        'managed/README.md': """# Managed Directory

This directory contains HNP-managed Kubernetes resource files.

## Structure:
- `vpcs/`: VPC resource definitions
- `connections/`: Connection resource definitions  
- `switches/`: Switch resource definitions
- `servers/`: Server resource definitions
- `switch-groups/`: SwitchGroup resource definitions
- `metadata/`: HNP metadata and configuration files

## Important:
Files in this directory are automatically managed by HNP. Manual modifications
may be overwritten during synchronization operations.
"""
    }
    
    def __init__(self, fabric):
        """Initialize GitOps Directory Manager for specified fabric"""
        self.fabric = fabric
        self.git_repository = fabric.git_repository
        
        if not self.git_repository:
            raise ValueError(f"Fabric {fabric.name} has no Git repository configured")
    
    def initialize_directory_structure(self, force: bool = False) -> DirectoryInitResult:
        """
        Initialize GitOps directory structure in the repository.
        
        Args:
            force: Force initialization even if directories already exist
            
        Returns:
            DirectoryInitResult with operation details
        """
        logger.info(f"Initializing GitOps directory structure for fabric {self.fabric.name}")
        
        directories_created = []
        errors = []
        warnings = []
        
        try:
            # Clone repository to temporary location
            with tempfile.TemporaryDirectory() as temp_dir:
                clone_result = self.git_repository.clone_repository(temp_dir)
                
                if not clone_result['success']:
                    return DirectoryInitResult(
                        success=False,
                        message="Failed to clone repository",
                        errors=[clone_result['error']]
                    )
                
                repo_path = Path(temp_dir)
                gitops_path = repo_path / self.fabric.gitops_directory.strip('/')
                
                # Ensure gitops base directory exists
                gitops_path.mkdir(parents=True, exist_ok=True)
                
                # Create directory structure
                for directory in self.STANDARD_DIRECTORIES:
                    dir_path = gitops_path / directory
                    
                    if dir_path.exists() and not force:
                        warnings.append(f"Directory {directory} already exists")
                        continue
                    
                    try:
                        dir_path.mkdir(parents=True, exist_ok=True)
                        directories_created.append(directory)
                        logger.debug(f"Created directory: {directory}")
                    except Exception as e:
                        errors.append(f"Failed to create directory {directory}: {str(e)}")
                
                # Create metadata files
                for file_path, content in self.METADATA_FILES.items():
                    full_path = gitops_path / file_path
                    
                    if full_path.exists() and not force:
                        warnings.append(f"File {file_path} already exists")
                        continue
                    
                    try:
                        full_path.parent.mkdir(parents=True, exist_ok=True)
                        
                        if isinstance(content, dict):
                            # JSON metadata file
                            content['created_at'] = timezone.now().isoformat()
                            content['fabric_name'] = self.fabric.name
                            content['gitops_directory'] = self.fabric.gitops_directory
                            
                            with open(full_path, 'w') as f:
                                json.dump(content, f, indent=2)
                        else:
                            # Text file
                            with open(full_path, 'w') as f:
                                f.write(content)
                        
                        logger.debug(f"Created metadata file: {file_path}")
                    except Exception as e:
                        errors.append(f"Failed to create file {file_path}: {str(e)}")
                
                # Push changes to repository if any directories were created
                if directories_created and not errors:
                    try:
                        from .github_sync_client import GitHubSyncClient
                        
                        client = GitHubSyncClient(self.git_repository)
                        
                        # Create commit for directory initialization
                        commit_result = client.commit_directory_changes(
                            directory_path=str(gitops_path),
                            message=f"Initialize GitOps directory structure for {self.fabric.name}",
                            branch=self.git_repository.get_push_branch()
                        )
                        
                        if not commit_result['success']:
                            errors.append(f"Failed to commit changes: {commit_result['error']}")
                    
                    except Exception as e:
                        errors.append(f"Failed to push directory structure: {str(e)}")
                
                success = len(errors) == 0
                message = f"Directory initialization {'completed' if success else 'failed'}"
                if directories_created:
                    message += f" - {len(directories_created)} directories created"
                if errors:
                    message += f" - {len(errors)} errors occurred"
                
                return DirectoryInitResult(
                    success=success,
                    message=message,
                    directories_created=directories_created,
                    errors=errors,
                    warnings=warnings
                )
        
        except Exception as e:
            logger.error(f"Directory initialization failed: {e}")
            return DirectoryInitResult(
                success=False,
                message=f"Directory initialization failed: {str(e)}",
                errors=[str(e)]
            )
    
    def validate_directory_structure(self) -> ValidationResult:
        """
        Validate existing directory structure.
        
        Returns:
            ValidationResult with validation details
        """
        logger.info(f"Validating GitOps directory structure for fabric {self.fabric.name}")
        
        issues = []
        missing_directories = []
        extra_files = []
        
        try:
            # Clone repository to temporary location
            with tempfile.TemporaryDirectory() as temp_dir:
                clone_result = self.git_repository.clone_repository(temp_dir)
                
                if not clone_result['success']:
                    issues.append(f"Cannot access repository: {clone_result['error']}")
                    return ValidationResult(valid=False, issues=issues)
                
                repo_path = Path(temp_dir)
                gitops_path = repo_path / self.fabric.gitops_directory.strip('/')
                
                if not gitops_path.exists():
                    issues.append(f"GitOps directory {self.fabric.gitops_directory} does not exist")
                    return ValidationResult(valid=False, issues=issues)
                
                # Check for required directories
                for directory in self.STANDARD_DIRECTORIES:
                    dir_path = gitops_path / directory
                    if not dir_path.exists():
                        missing_directories.append(directory)
                        issues.append(f"Missing required directory: {directory}")
                
                # Check for metadata files
                for file_path in self.METADATA_FILES.keys():
                    full_path = gitops_path / file_path
                    if not full_path.exists():
                        issues.append(f"Missing metadata file: {file_path}")
                
                # Check for unexpected files in root
                for item in gitops_path.iterdir():
                    if item.is_file() and item.name not in [f.split('/')[-1] for f in self.METADATA_FILES.keys()]:
                        extra_files.append(item.name)
                
                valid = len(issues) == 0
                
                return ValidationResult(
                    valid=valid,
                    issues=issues,
                    missing_directories=missing_directories,
                    extra_files=extra_files
                )
        
        except Exception as e:
            logger.error(f"Directory validation failed: {e}")
            return ValidationResult(
                valid=False,
                issues=[f"Validation failed: {str(e)}"]
            )
    
    def ingest_raw_files(self) -> IngestionResult:
        """
        Ingest files from raw/ directory into managed/ structure.
        
        Returns:
            IngestionResult with ingestion details
        """
        logger.info(f"Starting file ingestion for fabric {self.fabric.name}")
        
        files_processed = 0
        files_ingested = 0
        files_archived = 0
        errors = []
        warnings = []
        
        try:
            from .file_ingestion_pipeline import FileIngestionPipeline
            
            pipeline = FileIngestionPipeline(self.fabric)
            result = pipeline.process_raw_directory()
            
            return IngestionResult(
                success=result['success'],
                files_processed=result.get('files_processed', 0),
                files_ingested=result.get('files_ingested', 0),
                files_archived=result.get('files_archived', 0),
                errors=result.get('errors', []),
                warnings=result.get('warnings', [])
            )
        
        except Exception as e:
            logger.error(f"File ingestion failed: {e}")
            return IngestionResult(
                success=False,
                errors=[str(e)]
            )
    
    def get_directory_status(self) -> Dict[str, Any]:
        """
        Get comprehensive directory status information.
        
        Returns:
            Dictionary with directory status details
        """
        try:
            # Validate directory structure
            validation = self.validate_directory_structure()
            
            # Get directory contents information
            directory_info = self._get_directory_contents_info()
            
            return {
                'initialized': validation.valid,
                'structure_valid': validation.valid,
                'validation_issues': validation.issues,
                'missing_directories': validation.missing_directories,
                'directories': directory_info,
                'fabric': {
                    'name': self.fabric.name,
                    'gitops_directory': self.fabric.gitops_directory,
                    'status': self.fabric.gitops_directory_status
                },
                'repository': {
                    'url': self.git_repository.url,
                    'connection_status': self.git_repository.connection_status
                }
            }
        
        except Exception as e:
            logger.error(f"Failed to get directory status: {e}")
            return {
                'initialized': False,
                'structure_valid': False,
                'error': str(e)
            }
    
    def _get_directory_contents_info(self) -> Dict[str, Any]:
        """Get information about directory contents"""
        directory_info = {}
        
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                clone_result = self.git_repository.clone_repository(temp_dir)
                
                if not clone_result['success']:
                    return {'error': 'Cannot access repository'}
                
                repo_path = Path(temp_dir)
                gitops_path = repo_path / self.fabric.gitops_directory.strip('/')
                
                # Get info for each standard directory
                for directory in ['raw', 'unmanaged', 'managed']:
                    dir_path = gitops_path / directory
                    
                    if dir_path.exists():
                        # Count files recursively
                        yaml_files = list(dir_path.rglob('*.yaml')) + list(dir_path.rglob('*.yml'))
                        all_files = [f for f in dir_path.rglob('*') if f.is_file()]
                        
                        directory_info[directory] = {
                            'exists': True,
                            'file_count': len(all_files),
                            'yaml_file_count': len(yaml_files),
                            'last_modified': max(
                                (f.stat().st_mtime for f in all_files),
                                default=0
                            ) if all_files else 0
                        }
                        
                        # Additional info for specific directories
                        if directory == 'raw':
                            pending_files = list((dir_path / 'pending').glob('*.yaml')) if (dir_path / 'pending').exists() else []
                            directory_info[directory]['pending_ingestion'] = len(pending_files)
                        
                        elif directory == 'managed':
                            directory_info[directory]['last_sync'] = self.fabric.last_directory_sync
                    else:
                        directory_info[directory] = {
                            'exists': False,
                            'file_count': 0
                        }
                
                return directory_info
        
        except Exception as e:
            logger.error(f"Failed to get directory contents info: {e}")
            return {'error': str(e)}
    
    def enforce_directory_structure(self) -> Dict[str, Any]:
        """
        Enforce directory structure consistency during sync operations.
        
        Returns:
            Dictionary with enforcement results
        """
        logger.info(f"Enforcing directory structure for fabric {self.fabric.name}")
        
        try:
            # First validate current structure
            validation = self.validate_directory_structure()
            
            if validation.valid:
                return {
                    'success': True,
                    'message': 'Directory structure is valid',
                    'actions_taken': []
                }
            
            # Attempt to fix issues
            if validation.missing_directories:
                init_result = self.initialize_directory_structure(force=False)
                
                return {
                    'success': init_result.success,
                    'message': init_result.message,
                    'actions_taken': ['directory_initialization'],
                    'directories_created': init_result.directories_created,
                    'errors': init_result.errors
                }
            
            return {
                'success': False,
                'message': 'Unable to enforce directory structure',
                'issues': validation.issues
            }
        
        except Exception as e:
            logger.error(f"Directory structure enforcement failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def handle_unmanaged_files(self, action: str = 'preserve') -> Dict[str, Any]:
        """
        Handle files that don't fit the managed structure.
        
        Args:
            action: Action to take ('preserve', 'archive', 'warn')
            
        Returns:
            Dictionary with handling results
        """
        logger.info(f"Handling unmanaged files for fabric {self.fabric.name}")
        
        handled_files = []
        errors = []
        
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                clone_result = self.git_repository.clone_repository(temp_dir)
                
                if not clone_result['success']:
                    return {
                        'success': False,
                        'error': 'Cannot access repository'
                    }
                
                repo_path = Path(temp_dir)
                gitops_path = repo_path / self.fabric.gitops_directory.strip('/')
                
                # Find unmanaged files
                unmanaged_files = []
                for file_path in gitops_path.rglob('*'):
                    if file_path.is_file():
                        relative_path = file_path.relative_to(gitops_path)
                        
                        # Check if file is in an expected location
                        is_managed = any(
                            str(relative_path).startswith(expected_dir) 
                            for expected_dir in ['raw/', 'unmanaged/', 'managed/']
                        )
                        
                        if not is_managed:
                            unmanaged_files.append(relative_path)
                
                # Handle unmanaged files based on action
                for file_path in unmanaged_files:
                    full_path = gitops_path / file_path
                    
                    if action == 'preserve':
                        # Move to unmanaged/external-configs/
                        target_path = gitops_path / 'unmanaged' / 'external-configs' / file_path.name
                        target_path.parent.mkdir(parents=True, exist_ok=True)
                        
                        shutil.move(str(full_path), str(target_path))
                        handled_files.append(f"Moved {file_path} to unmanaged/external-configs/")
                    
                    elif action == 'archive':
                        # Move to archive directory with timestamp
                        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                        archive_dir = gitops_path / 'archive' / timestamp
                        archive_dir.mkdir(parents=True, exist_ok=True)
                        
                        target_path = archive_dir / file_path.name
                        shutil.move(str(full_path), str(target_path))
                        handled_files.append(f"Archived {file_path} to archive/{timestamp}/")
                    
                    elif action == 'warn':
                        handled_files.append(f"Warning: Unmanaged file {file_path}")
                
                return {
                    'success': True,
                    'message': f"Handled {len(handled_files)} unmanaged files",
                    'handled_files': handled_files,
                    'action': action
                }
        
        except Exception as e:
            logger.error(f"Failed to handle unmanaged files: {e}")
            return {
                'success': False,
                'error': str(e)
            }