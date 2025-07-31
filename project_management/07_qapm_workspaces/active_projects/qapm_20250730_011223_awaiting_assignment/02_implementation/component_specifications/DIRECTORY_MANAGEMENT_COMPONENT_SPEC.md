# Directory Management Component Specification

**Document Type**: Component Specification  
**Component**: GitOps Directory Management System  
**Project**: HNP GitOps Bidirectional Synchronization  
**Author**: Backend Technical Specialist  
**Date**: July 30, 2025  
**Version**: 1.0

## Component Overview

The Directory Management System provides centralized management of GitOps directory structure, automatic initialization, file ingestion workflows, and structure enforcement across all synchronization operations.

## Core Components

### 1. GitOpsDirectoryManager

**Purpose**: Primary orchestrator for all directory management operations

**File Location**: `netbox_hedgehog/utils/gitops_directory_manager.py`

**Class Definition**:
```python
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
import tempfile
import shutil
import logging
from django.utils import timezone

@dataclass
class DirectoryInitResult:
    success: bool
    message: str
    directories_created: List[str]
    backup_location: Optional[str] = None
    issues: List[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'message': self.message,
            'directories_created': self.directories_created,
            'backup_location': self.backup_location,
            'issues': self.issues or []
        }

@dataclass
class ValidationResult:
    valid: bool
    issues: List[str]
    directories: Dict[str, Dict[str, Any]]
    recommendations: List[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'valid': self.valid,
            'issues': self.issues,
            'directories': self.directories,
            'recommendations': self.recommendations or []
        }

@dataclass
class IngestionResult:
    success: bool
    files_processed: int
    files_created: int
    files_updated: int
    files_archived: int
    errors: List[str]
    processing_time: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'files_processed': self.files_processed,
            'files_created': self.files_created,
            'files_updated': self.files_updated,
            'files_archived': self.files_archived,
            'errors': self.errors,
            'processing_time': self.processing_time
        }

class GitOpsDirectoryManager:
    """
    Centralized management of GitOps directory structure and file operations.
    
    Responsibilities:
    - Initialize and maintain directory structure (raw/, unmanaged/, managed/)
    - Enforce directory structure consistency
    - Handle file ingestion from raw/ to managed/
    - Provide file-to-record mapping services
    """
    
    STANDARD_STRUCTURE = {
        'raw': {
            'pending': {},
            'processed': {},
            'errors': {}
        },
        'unmanaged': {
            'external-configs': {},
            'manual-overrides': {}
        },
        'managed': {
            'vpcs': {},
            'connections': {},
            'switches': {},
            'servers': {},
            'externals': {},
            'metadata': {}
        }
    }
    
    def __init__(self, fabric: 'HedgehogFabric'):
        self.fabric = fabric
        self.logger = logging.getLogger(__name__)
        
        # Validate fabric has required Git configuration
        if not self._validate_fabric_configuration():
            raise ValueError(f"Fabric {fabric.name} is not properly configured for GitOps")
    
    def _validate_fabric_configuration(self) -> bool:
        """Validate fabric has required Git repository configuration"""
        return bool(
            self.fabric.git_repository and 
            self.fabric.gitops_directory and
            self.fabric.git_repository.connection_status == 'connected'
        )
    
    def initialize_directory_structure(
        self, 
        force_recreate: bool = False,
        backup_existing: bool = True,
        structure_template: str = 'standard'
    ) -> DirectoryInitResult:
        """
        Initialize GitOps directory structure for the fabric.
        
        Args:
            force_recreate: Whether to recreate existing directories
            backup_existing: Whether to backup existing content
            structure_template: Directory structure template to use
            
        Returns:
            DirectoryInitResult with operation details
        """
        self.logger.info(f"Initializing directory structure for fabric {self.fabric.name}")
        
        try:
            # Clone repository to temporary location
            with tempfile.TemporaryDirectory() as temp_dir:
                clone_result = self._clone_repository(temp_dir)
                if not clone_result['success']:
                    return DirectoryInitResult(
                        success=False,
                        message=f"Failed to clone repository: {clone_result['error']}",
                        directories_created=[]
                    )
                
                repo_path = Path(temp_dir) / 'repo'
                target_path = repo_path / self.fabric.gitops_directory.strip('/')
                
                # Create backup if requested and content exists
                backup_location = None
                if backup_existing and target_path.exists():
                    backup_location = self._create_backup(target_path)
                
                # Initialize directory structure
                directories_created = []
                issues = []
                
                if structure_template == 'standard':
                    directories_created, init_issues = self._create_standard_structure(
                        target_path, force_recreate
                    )
                    issues.extend(init_issues)
                else:
                    return DirectoryInitResult(
                        success=False,
                        message=f"Unsupported structure template: {structure_template}",
                        directories_created=[]
                    )
                
                # Commit and push changes
                commit_result = self._commit_and_push_changes(
                    repo_path, 
                    f"Initialize GitOps directory structure for fabric {self.fabric.name}"
                )
                
                if not commit_result['success']:
                    issues.append(f"Failed to commit changes: {commit_result['error']}")
                
                # Update fabric metadata
                self._update_fabric_metadata(directories_created)
                
                success = len(issues) == 0
                message = f"Directory structure initialized successfully" if success else f"Initialized with {len(issues)} issues"
                
                self.logger.info(f"Directory initialization for {self.fabric.name}: {message}")
                
                return DirectoryInitResult(
                    success=success,
                    message=message,
                    directories_created=directories_created,
                    backup_location=backup_location,
                    issues=issues
                )
                
        except Exception as e:
            self.logger.error(f"Directory initialization failed: {e}")
            return DirectoryInitResult(
                success=False,
                message=f"Directory initialization failed: {str(e)}",
                directories_created=[]
            )
    
    def validate_directory_structure(self) -> ValidationResult:
        """
        Validate current directory structure against expected layout.
        
        Returns:
            ValidationResult with validation details
        """
        self.logger.info(f"Validating directory structure for fabric {self.fabric.name}")
        
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                clone_result = self._clone_repository(temp_dir)
                if not clone_result['success']:
                    return ValidationResult(
                        valid=False,
                        issues=[f"Failed to access repository: {clone_result['error']}"],
                        directories={}
                    )
                
                repo_path = Path(temp_dir) / 'repo'
                target_path = repo_path / self.fabric.gitops_directory.strip('/')
                
                if not target_path.exists():
                    return ValidationResult(
                        valid=False,
                        issues=[f"GitOps directory {self.fabric.gitops_directory} does not exist"],
                        directories={},
                        recommendations=["Run directory initialization to create required structure"]
                    )
                
                # Validate structure
                issues = []
                directories = {}
                recommendations = []
                
                # Check required directories
                for dir_name, subdirs in self.STANDARD_STRUCTURE.items():
                    dir_path = target_path / dir_name
                    dir_info = {
                        'exists': dir_path.exists(),
                        'is_directory': dir_path.is_dir() if dir_path.exists() else False,
                        'file_count': 0,
                        'subdirectories': {}
                    }
                    
                    if dir_path.exists() and dir_path.is_dir():
                        dir_info['file_count'] = len([f for f in dir_path.rglob('*') if f.is_file()])
                        
                        # Check subdirectories
                        for subdir_name in subdirs.keys():
                            subdir_path = dir_path / subdir_name
                            dir_info['subdirectories'][subdir_name] = {
                                'exists': subdir_path.exists(),
                                'is_directory': subdir_path.is_dir() if subdir_path.exists() else False,
                                'file_count': len([f for f in subdir_path.rglob('*') if f.is_file()]) if subdir_path.exists() and subdir_path.is_dir() else 0
                            }
                            
                            if not subdir_path.exists():
                                issues.append(f"Missing subdirectory: {dir_name}/{subdir_name}")
                                recommendations.append(f"Create missing subdirectory {dir_name}/{subdir_name}")
                    else:
                        issues.append(f"Missing or invalid directory: {dir_name}")
                        recommendations.append(f"Create missing directory {dir_name}")
                    
                    directories[dir_name] = dir_info
                
                # Check for unexpected files in root
                unexpected_files = [
                    f.name for f in target_path.iterdir() 
                    if f.is_file() and not f.name.startswith('.')
                ]
                
                if unexpected_files:
                    issues.append(f"Unexpected files in root directory: {', '.join(unexpected_files)}")
                    recommendations.append("Move unexpected files to appropriate subdirectories")
                
                valid = len(issues) == 0
                
                self.logger.info(f"Directory validation for {self.fabric.name}: {'Valid' if valid else f'{len(issues)} issues found'}")
                
                return ValidationResult(
                    valid=valid,
                    issues=issues,
                    directories=directories,
                    recommendations=recommendations
                )
                
        except Exception as e:
            self.logger.error(f"Directory validation failed: {e}")
            return ValidationResult(
                valid=False,
                issues=[f"Validation failed: {str(e)}"],
                directories={}
            )
    
    def ingest_raw_files(
        self,
        file_patterns: List[str] = None,
        validation_strict: bool = True,
        archive_processed: bool = True
    ) -> IngestionResult:
        """
        Ingest files from raw/ directory into managed/ directory.
        
        Args:
            file_patterns: File patterns to process (default: ['*.yaml', '*.yml'])
            validation_strict: Whether to use strict YAML validation
            archive_processed: Whether to archive successfully processed files
            
        Returns:
            IngestionResult with processing details
        """
        if file_patterns is None:
            file_patterns = ['*.yaml', '*.yml']
        
        start_time = datetime.now()
        self.logger.info(f"Starting file ingestion for fabric {self.fabric.name}")
        
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                clone_result = self._clone_repository(temp_dir)
                if not clone_result['success']:
                    return IngestionResult(
                        success=False,
                        files_processed=0,
                        files_created=0,
                        files_updated=0,
                        files_archived=0,
                        errors=[f"Failed to clone repository: {clone_result['error']}"],
                        processing_time=0.0
                    )
                
                repo_path = Path(temp_dir) / 'repo'
                target_path = repo_path / self.fabric.gitops_directory.strip('/')
                raw_path = target_path / 'raw' / 'pending'
                managed_path = target_path / 'managed'
                processed_path = target_path / 'raw' / 'processed'
                errors_path = target_path / 'raw' / 'errors'
                
                # Ensure directories exist
                for path in [managed_path, processed_path, errors_path]:
                    path.mkdir(parents=True, exist_ok=True)
                
                # Find files to process
                files_to_process = []
                for pattern in file_patterns:
                    files_to_process.extend(raw_path.glob(pattern))
                
                if not files_to_process:
                    processing_time = (datetime.now() - start_time).total_seconds()
                    return IngestionResult(
                        success=True,
                        files_processed=0,
                        files_created=0,
                        files_updated=0,
                        files_archived=0,
                        errors=[],
                        processing_time=processing_time
                    )
                
                # Process each file
                stats = {
                    'processed': 0,
                    'created': 0,
                    'updated': 0,
                    'archived': 0,
                    'errors': []
                }
                
                for file_path in files_to_process:
                    try:
                        result = self._process_raw_file(
                            file_path, 
                            managed_path, 
                            validation_strict
                        )
                        
                        if result['success']:
                            stats['processed'] += 1
                            if result['created']:
                                stats['created'] += 1
                            else:
                                stats['updated'] += 1
                            
                            # Archive processed file
                            if archive_processed:
                                archive_path = processed_path / f"{file_path.stem}_{int(datetime.now().timestamp())}{file_path.suffix}"
                                shutil.move(str(file_path), str(archive_path))
                                stats['archived'] += 1
                            else:
                                file_path.unlink()
                        else:
                            # Move to errors directory
                            error_path = errors_path / f"{file_path.stem}_error_{int(datetime.now().timestamp())}{file_path.suffix}"
                            shutil.move(str(file_path), str(error_path))
                            
                            # Create error log
                            error_log_path = errors_path / f"{file_path.stem}_error_{int(datetime.now().timestamp())}.log"
                            error_log_path.write_text(result['error'])
                            
                            stats['errors'].append(f"{file_path.name}: {result['error']}")
                            
                    except Exception as e:
                        stats['errors'].append(f"{file_path.name}: {str(e)}")
                        self.logger.error(f"Failed to process file {file_path}: {e}")
                
                # Commit changes if any files were processed successfully
                if stats['created'] > 0 or stats['updated'] > 0:
                    commit_result = self._commit_and_push_changes(
                        repo_path,
                        f"Ingest {stats['created']} new and {stats['updated']} updated resources for fabric {self.fabric.name}"
                    )
                    
                    if not commit_result['success']:
                        stats['errors'].append(f"Failed to commit changes: {commit_result['error']}")
                
                processing_time = (datetime.now() - start_time).total_seconds()
                success = len(stats['errors']) == 0
                
                self.logger.info(f"File ingestion for {self.fabric.name} completed: {stats['processed']} files processed, {len(stats['errors'])} errors")
                
                return IngestionResult(
                    success=success,
                    files_processed=stats['processed'],
                    files_created=stats['created'],
                    files_updated=stats['updated'],
                    files_archived=stats['archived'],
                    errors=stats['errors'],
                    processing_time=processing_time
                )
                
        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds()
            self.logger.error(f"File ingestion failed: {e}")
            return IngestionResult(
                success=False,
                files_processed=0,
                files_created=0,
                files_updated=0,
                files_archived=0,
                errors=[f"Ingestion failed: {str(e)}"],
                processing_time=processing_time
            )
    
    def get_directory_status(self) -> Dict[str, Any]:
        """
        Get comprehensive status of directory structure.
        
        Returns:
            Dictionary with directory status information
        """
        validation_result = self.validate_directory_structure()
        
        return {
            'fabric_name': self.fabric.name,
            'initialized': validation_result.valid,
            'structure_valid': validation_result.valid,
            'directories': validation_result.directories,
            'issues': validation_result.issues,
            'recommendations': validation_result.recommendations,
            'last_sync': self.fabric.last_git_sync.isoformat() if self.fabric.last_git_sync else None,
            'gitops_directory': self.fabric.gitops_directory,
            'repository_url': self.fabric.git_repository.url if self.fabric.git_repository else None
        }
    
    # Private helper methods
    def _clone_repository(self, temp_dir: str) -> Dict[str, Any]:
        """Clone repository using GitRepository credentials"""
        try:
            target_path = Path(temp_dir) / 'repo'
            return self.fabric.git_repository.clone_repository(str(target_path))
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _create_backup(self, target_path: Path) -> str:
        """Create backup of existing directory content"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"backup_{self.fabric.name}_{timestamp}"
        backup_path = target_path.parent / backup_name
        
        shutil.copytree(target_path, backup_path)
        return str(backup_path.relative_to(target_path.parent.parent))
    
    def _create_standard_structure(self, target_path: Path, force_recreate: bool) -> Tuple[List[str], List[str]]:
        """Create standard directory structure"""
        created_dirs = []
        issues = []
        
        try:
            if force_recreate and target_path.exists():
                shutil.rmtree(target_path)
            
            target_path.mkdir(parents=True, exist_ok=True)
            
            # Create directory structure
            for dir_name, subdirs in self.STANDARD_STRUCTURE.items():
                dir_path = target_path / dir_name
                dir_path.mkdir(exist_ok=True)
                created_dirs.append(dir_name)
                
                for subdir_name in subdirs.keys():
                    subdir_path = dir_path / subdir_name
                    subdir_path.mkdir(exist_ok=True)
                    created_dirs.append(f"{dir_name}/{subdir_name}")
                
                # Create README files for guidance
                readme_path = dir_path / 'README.md'
                if not readme_path.exists():
                    readme_content = self._generate_readme_content(dir_name)
                    readme_path.write_text(readme_content)
            
            # Create root .gitkeep files to ensure empty directories are tracked
            for dir_name in self.STANDARD_STRUCTURE.keys():
                gitkeep_path = target_path / dir_name / '.gitkeep'
                if not gitkeep_path.exists():
                    gitkeep_path.touch()
                    
        except Exception as e:
            issues.append(f"Failed to create directory structure: {str(e)}")
            
        return created_dirs, issues
    
    def _generate_readme_content(self, dir_name: str) -> str:
        """Generate README content for directory"""
        content_map = {
            'raw': """# Raw Directory

This directory contains files uploaded by users that are awaiting ingestion into HNP.

## Subdirectories:
- `pending/`: Files awaiting validation and processing
- `processed/`: Archives of successfully processed files
- `errors/`: Files that failed processing with error logs

## Usage:
1. Upload YAML files to `pending/` directory
2. Trigger ingestion via HNP GUI or API
3. Check `processed/` for successful ingestion
4. Check `errors/` for any processing failures
""",
            'unmanaged': """# Unmanaged Directory

This directory contains files that are not directly managed by HNP but are part of the GitOps workflow.

## Subdirectories:
- `external-configs/`: Configuration files from external sources
- `manual-overrides/`: Manual configuration overrides

## Note:
Files in this directory are preserved during sync operations but are not automatically processed by HNP.
""",
            'managed': """# Managed Directory

This directory contains files that are directly managed by HNP and synchronized with the NetBox database.

## Subdirectories:
- `vpcs/`: VPC resource definitions
- `connections/`: Connection resource definitions
- `switches/`: Switch resource definitions
- `servers/`: Server resource definitions
- `externals/`: External resource definitions
- `metadata/`: HNP metadata and configuration files

## Warning:
Files in this directory are automatically managed by HNP. Manual modifications may be overwritten during synchronization.
"""
        }
        
        return content_map.get(dir_name, f"# {dir_name.title()} Directory\n\nManaged by HNP GitOps system.")
    
    def _commit_and_push_changes(self, repo_path: Path, commit_message: str) -> Dict[str, Any]:
        """Commit and push changes to repository"""
        try:
            import subprocess
            
            # Configure git for commit
            subprocess.run(['git', '-C', str(repo_path), 'config', 'user.email', 'hnp@githedgehog.com'], check=True)
            subprocess.run(['git', '-C', str(repo_path), 'config', 'user.name', 'HNP GitOps System'], check=True)
            
            # Add all changes
            subprocess.run(['git', '-C', str(repo_path), 'add', '.'], check=True)
            
            # Check if there are changes to commit
            result = subprocess.run(['git', '-C', str(repo_path), 'diff', '--staged', '--quiet'], capture_output=True)
            if result.returncode == 0:
                # No changes to commit
                return {'success': True, 'message': 'No changes to commit'}
            
            # Commit changes
            subprocess.run(['git', '-C', str(repo_path), 'commit', '-m', commit_message], check=True)
            
            # Push changes
            credentials = self.fabric.git_repository.get_credentials()
            if credentials.get('token'):
                # Modify origin URL to include token
                original_url = self.fabric.git_repository.url
                if 'github.com' in original_url:
                    auth_url = original_url.replace('https://', f"https://{credentials['token']}@")
                    subprocess.run(['git', '-C', str(repo_path), 'remote', 'set-url', 'origin', auth_url], check=True)
            
            subprocess.run(['git', '-C', str(repo_path), 'push', 'origin', 'HEAD'], check=True)
            
            return {'success': True, 'message': 'Changes committed and pushed successfully'}
            
        except subprocess.CalledProcessError as e:
            return {'success': False, 'error': f'Git operation failed: {e}'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _update_fabric_metadata(self, directories_created: List[str]):
        """Update fabric metadata after directory initialization"""
        self.fabric.gitops_initialized = True
        self.fabric.save(update_fields=['gitops_initialized'])
        
        self.logger.info(f"Updated fabric {self.fabric.name} metadata: gitops_initialized=True")
    
    def _process_raw_file(self, file_path: Path, managed_path: Path, strict_validation: bool) -> Dict[str, Any]:
        """Process a single raw file into managed directory"""
        try:
            import yaml
            from django.db import transaction
            
            # Parse YAML content
            with open(file_path, 'r') as f:
                documents = list(yaml.safe_load_all(f))
            
            created = False
            updated = False
            processed_resources = []
            
            for doc in documents:
                if not doc or not isinstance(doc, dict):
                    continue
                
                # Extract resource information
                kind = doc.get('kind')
                metadata = doc.get('metadata', {})
                name = metadata.get('name')
                
                if not kind or not name:
                    if strict_validation:
                        return {'success': False, 'error': 'Invalid resource: missing kind or name'}
                    continue
                
                # Determine target file path in managed directory
                resource_type = self._get_resource_type_directory(kind)
                if not resource_type:
                    if strict_validation:
                        return {'success': False, 'error': f'Unsupported resource kind: {kind}'}
                    continue
                
                target_dir = managed_path / resource_type
                target_dir.mkdir(exist_ok=True)
                
                target_file = target_dir / f"{name}.yaml"
                
                # Check if file exists (update vs create)
                file_existed = target_file.exists()
                
                # Write file content
                with open(target_file, 'w') as f:
                    yaml.dump(doc, f, default_flow_style=False)
                
                if file_existed:
                    updated = True
                else:
                    created = True
                
                processed_resources.append({
                    'kind': kind,
                    'name': name,
                    'file_path': str(target_file.relative_to(managed_path.parent)),
                    'action': 'updated' if file_existed else 'created'
                })
            
            if not processed_resources:
                return {'success': False, 'error': 'No valid resources found in file'}
            
            return {
                'success': True,
                'created': created,
                'updated': updated,
                'resources': processed_resources
            }
            
        except yaml.YAMLError as e:
            return {'success': False, 'error': f'YAML parsing error: {str(e)}'}
        except Exception as e:
            return {'success': False, 'error': f'Processing error: {str(e)}'}
    
    def _get_resource_type_directory(self, kind: str) -> Optional[str]:
        """Map Kubernetes resource kind to managed directory"""
        mapping = {
            'VPC': 'vpcs',
            'External': 'externals',
            'ExternalAttachment': 'externals',
            'ExternalPeering': 'externals',
            'IPv4Namespace': 'externals',
            'VPCAttachment': 'vpcs',
            'VPCPeering': 'vpcs',
            'Connection': 'connections',
            'Server': 'servers',
            'Switch': 'switches',
            'SwitchGroup': 'switches',
            'VLANNamespace': 'externals'
        }
        
        return mapping.get(kind)
```

## Integration Points

### 1. HedgehogFabric Integration

**Extensions to existing model**:
```python
# Add to HedgehogFabric model
def get_directory_manager(self) -> GitOpsDirectoryManager:
    """Get directory manager instance for this fabric"""
    return GitOpsDirectoryManager(self)

def initialize_gitops_directories(self, **kwargs) -> DirectoryInitResult:
    """Initialize GitOps directory structure"""
    manager = self.get_directory_manager()
    return manager.initialize_directory_structure(**kwargs)

def validate_gitops_directories(self) -> ValidationResult:
    """Validate GitOps directory structure"""
    manager = self.get_directory_manager()
    return manager.validate_directory_structure()

def ingest_raw_files(self, **kwargs) -> IngestionResult:
    """Ingest files from raw directory"""
    manager = self.get_directory_manager()
    return manager.ingest_raw_files(**kwargs)
```

### 2. Django Management Commands

**File Location**: `netbox_hedgehog/management/commands/gitops_directory_init.py`

```python
from django.core.management.base import BaseCommand
from netbox_hedgehog.models import HedgehogFabric

class Command(BaseCommand):
    help = 'Initialize GitOps directory structure for fabrics'
    
    def add_arguments(self, parser):
        parser.add_argument('--fabric', type=str, help='Fabric name to initialize')
        parser.add_argument('--all', action='store_true', help='Initialize all fabrics')
        parser.add_argument('--force', action='store_true', help='Force recreation of existing directories')
        
    def handle(self, *args, **options):
        if options['fabric']:
            try:
                fabric = HedgehogFabric.objects.get(name=options['fabric'])
                result = fabric.initialize_gitops_directories(force_recreate=options['force'])
                self.stdout.write(self.style.SUCCESS(f"Initialized {fabric.name}: {result.message}"))
            except HedgehogFabric.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"Fabric {options['fabric']} not found"))
        elif options['all']:
            for fabric in HedgehogFabric.objects.filter(git_repository__isnull=False):
                result = fabric.initialize_gitops_directories(force_recreate=options['force'])
                status = self.style.SUCCESS if result.success else self.style.ERROR
                self.stdout.write(status(f"{fabric.name}: {result.message}"))
```

### 3. API View Integration

**File Location**: `netbox_hedgehog/api/views/gitops_directory_views.py`

```python
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from netbox.api.viewsets import NetBoxModelViewSet
from ..serializers import HedgehogFabricSerializer
from ...models import HedgehogFabric

class GitOpsDirectoryViewSet(NetBoxModelViewSet):
    """API views for GitOps directory management"""
    
    @action(detail=True, methods=['post'])
    def initialize_directories(self, request, pk=None):
        """Initialize GitOps directory structure"""
        fabric = self.get_object()
        
        # Extract parameters from request
        force_recreate = request.data.get('force_recreate', False)
        backup_existing = request.data.get('backup_existing', True)
        structure_template = request.data.get('structure_template', 'standard')
        
        # Initialize directories
        result = fabric.initialize_gitops_directories(
            force_recreate=force_recreate,
            backup_existing=backup_existing,
            structure_template=structure_template
        )
        
        return Response(
            result.to_dict(),
            status=status.HTTP_200_OK if result.success else status.HTTP_400_BAD_REQUEST
        )
    
    @action(detail=True, methods=['get'])
    def directory_status(self, request, pk=None):
        """Get directory structure status"""
        fabric = self.get_object()
        manager = fabric.get_directory_manager()
        status_info = manager.get_directory_status()
        
        return Response(status_info, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def ingest_files(self, request, pk=None):
        """Ingest files from raw directory"""
        fabric = self.get_object()
        
        # Extract parameters from request
        file_patterns = request.data.get('file_patterns', ['*.yaml', '*.yml'])
        validation_strict = request.data.get('validation_strict', True)
        archive_processed = request.data.get('archive_processed', True)
        
        # Perform ingestion
        result = fabric.ingest_raw_files(
            file_patterns=file_patterns,
            validation_strict=validation_strict,
            archive_processed=archive_processed
        )
        
        return Response(
            result.to_dict(),
            status=status.HTTP_200_OK if result.success else status.HTTP_400_BAD_REQUEST
        )
```

## Error Handling and Logging

### 1. Exception Hierarchy

```python
class GitOpsDirectoryError(Exception):
    """Base exception for GitOps directory operations"""
    pass

class DirectoryInitializationError(GitOpsDirectoryError):
    """Raised when directory initialization fails"""
    pass

class DirectoryValidationError(GitOpsDirectoryError):
    """Raised when directory validation fails"""
    pass

class FileIngestionError(GitOpsDirectoryError):
    """Raised when file ingestion fails"""
    pass

class RepositoryAccessError(GitOpsDirectoryError):
    """Raised when repository access fails"""
    pass
```

### 2. Logging Configuration

```python
LOGGING = {
    'loggers': {
        'netbox_hedgehog.utils.gitops_directory_manager': {
            'level': 'INFO',
            'handlers': ['console', 'file'],
            'propagate': False,
        },
    },
    'handlers': {
        'file': {
            'level': 'DEBUG',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/var/log/netbox/hnp_gitops_directory.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
}
```

## Testing Specifications

### 1. Unit Tests

**File Location**: `netbox_hedgehog/tests/test_gitops_directory_manager.py`

```python
import unittest
from unittest.mock import Mock, patch, MagicMock
from netbox_hedgehog.utils.gitops_directory_manager import GitOpsDirectoryManager

class TestGitOpsDirectoryManager(unittest.TestCase):
    
    def setUp(self):
        self.fabric = Mock()
        self.fabric.name = 'test-fabric'
        self.fabric.gitops_directory = 'gitops/test-fabric'
        self.fabric.git_repository = Mock()
        self.fabric.git_repository.connection_status = 'connected'
        
    def test_initialization_success(self):
        """Test successful directory initialization"""
        manager = GitOpsDirectoryManager(self.fabric)
        
        with patch.object(manager, '_clone_repository') as mock_clone, \
             patch.object(manager, '_create_standard_structure') as mock_create, \
             patch.object(manager, '_commit_and_push_changes') as mock_commit:
            
            mock_clone.return_value = {'success': True, 'commit_sha': 'abc123'}
            mock_create.return_value = (['raw', 'managed', 'unmanaged'], [])
            mock_commit.return_value = {'success': True}
            
            result = manager.initialize_directory_structure()
            
            self.assertTrue(result.success)
            self.assertEqual(len(result.directories_created), 3)
            self.assertEqual(len(result.issues), 0)
    
    def test_validation_missing_directories(self):
        """Test validation with missing directories"""
        manager = GitOpsDirectoryManager(self.fabric)
        
        with patch.object(manager, '_clone_repository') as mock_clone:
            mock_clone.return_value = {'success': True}
            
            # Mock missing directories
            with patch('pathlib.Path.exists', return_value=False):
                result = manager.validate_directory_structure()
                
                self.assertFalse(result.valid)
                self.assertGreater(len(result.issues), 0)
                self.assertGreater(len(result.recommendations), 0)
    
    def test_file_ingestion_success(self):
        """Test successful file ingestion"""
        manager = GitOpsDirectoryManager(self.fabric)
        
        with patch.object(manager, '_clone_repository') as mock_clone, \
             patch.object(manager, '_process_raw_file') as mock_process, \
             patch.object(manager, '_commit_and_push_changes') as mock_commit:
            
            mock_clone.return_value = {'success': True}
            mock_process.return_value = {'success': True, 'created': True}
            mock_commit.return_value = {'success': True}
            
            # Mock file discovery
            with patch('pathlib.Path.glob', return_value=[Mock(name='test.yaml')]):
                result = manager.ingest_raw_files()
                
                self.assertTrue(result.success)
                self.assertEqual(result.files_processed, 1)
                self.assertEqual(result.files_created, 1)
```

### 2. Integration Tests

**File Location**: `netbox_hedgehog/tests/integration/test_directory_management_integration.py`

```python
import tempfile
from django.test import TestCase
from netbox_hedgehog.models import HedgehogFabric, GitRepository
from netbox_hedgehog.utils.gitops_directory_manager import GitOpsDirectoryManager

class DirectoryManagementIntegrationTest(TestCase):
    
    def setUp(self):
        # Create test repository
        self.git_repo = GitRepository.objects.create(
            name='Test Repository',
            url='https://github.com/test/repo.git',
            provider='github'
        )
        
        # Create test fabric
        self.fabric = HedgehogFabric.objects.create(
            name='test-fabric',
            git_repository=self.git_repo,
            gitops_directory='gitops/test-fabric'
        )
    
    def test_end_to_end_directory_workflow(self):
        """Test complete directory management workflow"""
        manager = GitOpsDirectoryManager(self.fabric)
        
        # Test initialization
        with patch.object(manager, '_clone_repository') as mock_clone:
            mock_clone.return_value = {'success': True}
            
            result = manager.initialize_directory_structure()
            self.assertTrue(result.success)
        
        # Test validation
        result = manager.validate_directory_structure()
        self.assertIsNotNone(result)
        
        # Test ingestion
        result = manager.ingest_raw_files()
        self.assertIsNotNone(result)
```

## Performance Considerations

### 1. Optimization Strategies

- **Repository Caching**: Cache cloned repositories for short periods to avoid repeated clones
- **Parallel Processing**: Process multiple files concurrently during ingestion
- **Lazy Loading**: Load directory structure information only when needed
- **Batch Operations**: Group file operations for efficient Git commits

### 2. Monitoring Metrics

- Directory initialization time
- File ingestion throughput
- Repository access latency
- Error rates by operation type
- Memory usage during large file processing

## Security Considerations

### 1. Access Control

- Validate user permissions before directory operations
- Use existing GitRepository credential encryption
- Audit all directory modification operations
- Implement rate limiting for API endpoints

### 2. Input Validation

- Validate all file paths to prevent directory traversal
- Sanitize YAML content during ingestion
- Verify file size limits to prevent resource exhaustion
- Validate directory names against allowed patterns

This component specification provides a comprehensive foundation for implementing the GitOps Directory Management System as part of the bidirectional synchronization architecture.