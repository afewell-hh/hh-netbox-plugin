"""
File Management Service
Provides comprehensive file system operations with safety guarantees,
directory structure management, metadata tracking, and backup/restore capabilities.
"""

import os
import shutil
import json
import yaml
import hashlib
import logging
import fcntl
import tempfile
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Tuple, Generator
from datetime import datetime, timedelta
from contextlib import contextmanager, suppress
from dataclasses import dataclass, asdict
from threading import Lock
import time

from django.utils import timezone
from django.conf import settings

logger = logging.getLogger(__name__)


@dataclass
class FileMetadata:
    """Metadata for tracked files."""
    file_path: str
    file_hash: str
    size: int
    created_at: datetime
    modified_at: datetime
    accessed_at: datetime
    permissions: str
    owner: str
    group: str
    version: int
    backup_paths: List[str]
    tags: List[str]
    checksum_algorithm: str = 'sha256'


@dataclass
class DirectoryStructure:
    """Represents a managed directory structure."""
    base_path: str
    subdirectories: List[str]
    required_files: List[str]
    permissions: Dict[str, str]
    created_at: datetime
    last_validated: datetime


class FileOperationLock:
    """Thread-safe file operation locking mechanism."""
    
    def __init__(self):
        self._locks = {}
        self._global_lock = Lock()
    
    @contextmanager
    def acquire(self, file_path: str):
        """Acquire a lock for a specific file path."""
        normalized_path = str(Path(file_path).resolve())
        
        with self._global_lock:
            if normalized_path not in self._locks:
                self._locks[normalized_path] = Lock()
            file_lock = self._locks[normalized_path]
        
        with file_lock:
            yield


class FileManagementService:
    """
    Comprehensive file management service with safety guarantees, versioning,
    and backup capabilities for GitOps workflows.
    
    Key Features:
    - Atomic file operations with rollback support
    - Comprehensive metadata tracking and versioning
    - Directory structure management with validation
    - Advanced backup and restore capabilities
    - File locking and concurrent access protection
    - Integrity verification with checksums
    """
    
    def __init__(self, base_directory: Union[str, Path]):
        self.base_directory = Path(base_directory).resolve()
        self.metadata_directory = self.base_directory / '.hnp-metadata'
        self.backup_directory = self.base_directory / '.hnp-backups'
        self.temp_directory = self.base_directory / '.hnp-temp'
        
        # Initialize locks and state
        self.file_locks = FileOperationLock()
        self.operation_history = []
        
        # Configuration
        self.max_backup_versions = getattr(settings, 'FILE_MGMT_MAX_BACKUP_VERSIONS', 10)
        self.backup_retention_days = getattr(settings, 'FILE_MGMT_BACKUP_RETENTION_DAYS', 30)
        self.max_file_size = getattr(settings, 'FILE_MGMT_MAX_FILE_SIZE', 50 * 1024 * 1024)  # 50MB
        self.verify_checksums = getattr(settings, 'FILE_MGMT_VERIFY_CHECKSUMS', True)
        
        # Initialize service
        self._initialize_service()
    
    def _initialize_service(self):
        """Initialize the file management service directories and metadata."""
        try:
            # Create required directories
            for directory in [self.metadata_directory, self.backup_directory, self.temp_directory]:
                directory.mkdir(parents=True, exist_ok=True, mode=0o755)
                logger.debug(f"Initialized directory: {directory}")
            
            # Initialize metadata index if it doesn't exist
            metadata_index_path = self.metadata_directory / 'file_index.json'
            if not metadata_index_path.exists():
                self._create_empty_metadata_index()
            
            logger.info(f"File management service initialized for {self.base_directory}")
            
        except Exception as e:
            logger.error(f"Failed to initialize file management service: {str(e)}")
            raise
    
    def create_file(self, file_path: Union[str, Path], content: Union[str, bytes], 
                   metadata: Optional[Dict[str, Any]] = None, 
                   create_backup: bool = True) -> Dict[str, Any]:
        """
        Create a new file with comprehensive safety checks and metadata tracking.
        
        Args:
            file_path: Path where the file should be created
            content: Content to write to the file
            metadata: Optional metadata to associate with the file
            create_backup: Whether to create a backup if file already exists
            
        Returns:
            Dict with operation results and file metadata
        """
        file_path = self._resolve_path(file_path)
        operation_id = f"create_{int(time.time())}"
        
        logger.info(f"Creating file: {file_path}")
        
        result = {
            'success': False,
            'operation': 'create',
            'file_path': str(file_path),
            'operation_id': operation_id,
            'started_at': timezone.now()
        }
        
        try:
            with self.file_locks.acquire(str(file_path)):
                # Pre-creation validation
                validation = self._validate_file_creation(file_path, content)
                if not validation['valid']:
                    result['error'] = f"Validation failed: {validation['error']}"
                    return result
                
                # Create backup of existing file if requested
                if file_path.exists() and create_backup:
                    backup_result = self.create_backup(file_path)
                    result['backup_created'] = backup_result['success']
                    result['backup_path'] = backup_result.get('backup_path')
                
                # Prepare file content and metadata
                file_content = content.encode('utf-8') if isinstance(content, str) else content
                
                # Create file atomically using temporary file
                with self._atomic_write(file_path) as temp_file:
                    temp_file.write(file_content)
                    temp_file.flush()
                    os.fsync(temp_file.fileno())  # Ensure data is written to disk
                
                # Create and store file metadata
                file_metadata = self._create_file_metadata(file_path, metadata)
                self._store_file_metadata(file_metadata)
                
                # Verify file integrity
                if self.verify_checksums:
                    integrity_check = self._verify_file_integrity(file_path, file_metadata.file_hash)
                    if not integrity_check['valid']:
                        result['error'] = f"Integrity verification failed: {integrity_check['error']}"
                        # Clean up on verification failure
                        with suppress(Exception):
                            file_path.unlink()
                        return result
                
                result.update({
                    'success': True,
                    'file_size': file_path.stat().st_size,
                    'file_hash': file_metadata.file_hash,
                    'metadata': asdict(file_metadata),
                    'completed_at': timezone.now()
                })
                
                logger.info(f"Successfully created file: {file_path} ({result['file_size']} bytes)")
                
        except Exception as e:
            logger.error(f"File creation failed for {file_path}: {str(e)}")
            result['error'] = str(e)
            result['completed_at'] = timezone.now()
        
        self._record_operation(result)
        return result
    
    def update_file(self, file_path: Union[str, Path], content: Union[str, bytes],
                   create_backup: bool = True, verify_before_update: bool = True) -> Dict[str, Any]:
        """
        Update an existing file with comprehensive safety checks.
        
        Args:
            file_path: Path to the file to update
            content: New content for the file
            create_backup: Whether to create a backup before updating
            verify_before_update: Whether to verify current file integrity
            
        Returns:
            Dict with operation results
        """
        file_path = self._resolve_path(file_path)
        operation_id = f"update_{int(time.time())}"
        
        logger.info(f"Updating file: {file_path}")
        
        result = {
            'success': False,
            'operation': 'update',
            'file_path': str(file_path),
            'operation_id': operation_id,
            'started_at': timezone.now()
        }
        
        try:
            with self.file_locks.acquire(str(file_path)):
                # Validate file exists and is updatable
                if not file_path.exists():
                    result['error'] = "File does not exist"
                    return result
                
                # Get current file metadata
                current_metadata = self._get_file_metadata(file_path)
                if current_metadata and verify_before_update:
                    integrity_check = self._verify_file_integrity(file_path, current_metadata.file_hash)
                    if not integrity_check['valid']:
                        result['error'] = f"Current file integrity check failed: {integrity_check['error']}"
                        return result
                
                # Create backup if requested
                if create_backup:
                    backup_result = self.create_backup(file_path)
                    result['backup_created'] = backup_result['success']
                    result['backup_path'] = backup_result.get('backup_path')
                
                # Store original file info
                original_size = file_path.stat().st_size
                original_mtime = file_path.stat().st_mtime
                
                # Prepare new content
                file_content = content.encode('utf-8') if isinstance(content, str) else content
                
                # Validate new content
                validation = self._validate_file_content(file_content)
                if not validation['valid']:
                    result['error'] = f"Content validation failed: {validation['error']}"
                    return result
                
                # Update file atomically
                with self._atomic_write(file_path) as temp_file:
                    temp_file.write(file_content)
                    temp_file.flush()
                    os.fsync(temp_file.fileno())
                
                # Update file metadata
                updated_metadata = self._create_file_metadata(file_path)
                if current_metadata:
                    updated_metadata.version = current_metadata.version + 1
                    updated_metadata.backup_paths = current_metadata.backup_paths
                    if result.get('backup_path'):
                        updated_metadata.backup_paths.append(result['backup_path'])
                
                self._store_file_metadata(updated_metadata)
                
                # Verify updated file integrity
                if self.verify_checksums:
                    integrity_check = self._verify_file_integrity(file_path, updated_metadata.file_hash)
                    if not integrity_check['valid']:
                        result['error'] = f"Updated file integrity verification failed: {integrity_check['error']}"
                        return result
                
                result.update({
                    'success': True,
                    'original_size': original_size,
                    'new_size': file_path.stat().st_size,
                    'original_mtime': original_mtime,
                    'new_mtime': file_path.stat().st_mtime,
                    'version': updated_metadata.version,
                    'file_hash': updated_metadata.file_hash,
                    'completed_at': timezone.now()
                })
                
                logger.info(f"Successfully updated file: {file_path} (v{updated_metadata.version})")
                
        except Exception as e:
            logger.error(f"File update failed for {file_path}: {str(e)}")
            result['error'] = str(e)
            result['completed_at'] = timezone.now()
        
        self._record_operation(result)
        return result
    
    def delete_file(self, file_path: Union[str, Path], create_backup: bool = True,
                   secure_delete: bool = False) -> Dict[str, Any]:
        """
        Delete a file with safety checks and optional backup.
        
        Args:
            file_path: Path to the file to delete
            create_backup: Whether to create a backup before deletion
            secure_delete: Whether to perform secure deletion (overwrite with random data)
            
        Returns:
            Dict with operation results
        """
        file_path = self._resolve_path(file_path)
        operation_id = f"delete_{int(time.time())}"
        
        logger.info(f"Deleting file: {file_path}")
        
        result = {
            'success': False,
            'operation': 'delete',
            'file_path': str(file_path),
            'operation_id': operation_id,
            'started_at': timezone.now()
        }
        
        try:
            with self.file_locks.acquire(str(file_path)):
                if not file_path.exists():
                    result['error'] = "File does not exist"
                    return result
                
                # Get file info before deletion
                file_size = file_path.stat().st_size
                file_metadata = self._get_file_metadata(file_path)
                
                # Create backup if requested
                if create_backup:
                    backup_result = self.create_backup(file_path)
                    result['backup_created'] = backup_result['success']
                    result['backup_path'] = backup_result.get('backup_path')
                
                # Perform secure deletion if requested
                if secure_delete:
                    self._secure_delete_file(file_path)
                else:
                    file_path.unlink()
                
                # Remove from metadata index but keep metadata record for auditing
                if file_metadata:
                    file_metadata.tags.append('deleted')
                    self._store_file_metadata(file_metadata, mark_deleted=True)
                
                result.update({
                    'success': True,
                    'file_size': file_size,
                    'secure_delete': secure_delete,
                    'metadata_preserved': file_metadata is not None,
                    'completed_at': timezone.now()
                })
                
                logger.info(f"Successfully deleted file: {file_path} ({file_size} bytes)")
                
        except Exception as e:
            logger.error(f"File deletion failed for {file_path}: {str(e)}")
            result['error'] = str(e)
            result['completed_at'] = timezone.now()
        
        self._record_operation(result)
        return result
    
    def move_file(self, source_path: Union[str, Path], target_path: Union[str, Path],
                 create_backup: bool = True, overwrite: bool = False) -> Dict[str, Any]:
        """
        Move a file from source to target location with safety checks.
        
        Args:
            source_path: Current file location
            target_path: Destination file location
            create_backup: Whether to create backup of source file
            overwrite: Whether to overwrite existing target file
            
        Returns:
            Dict with operation results
        """
        source_path = self._resolve_path(source_path)
        target_path = self._resolve_path(target_path)
        operation_id = f"move_{int(time.time())}"
        
        logger.info(f"Moving file: {source_path} -> {target_path}")
        
        result = {
            'success': False,
            'operation': 'move',
            'source_path': str(source_path),
            'target_path': str(target_path),
            'operation_id': operation_id,
            'started_at': timezone.now()
        }
        
        try:
            # Acquire locks for both files in consistent order to prevent deadlocks
            paths_to_lock = sorted([str(source_path), str(target_path)])
            with self.file_locks.acquire(paths_to_lock[0]), \
                 self.file_locks.acquire(paths_to_lock[1]):
                
                # Validate source file exists
                if not source_path.exists():
                    result['error'] = "Source file does not exist"
                    return result
                
                # Check target file handling
                if target_path.exists() and not overwrite:
                    result['error'] = "Target file exists and overwrite is False"
                    return result
                
                # Create target directory if it doesn't exist
                target_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Create backup of source file if requested
                if create_backup:
                    backup_result = self.create_backup(source_path)
                    result['backup_created'] = backup_result['success']
                    result['backup_path'] = backup_result.get('backup_path')
                
                # Create backup of target file if it exists and will be overwritten
                target_backup_path = None
                if target_path.exists() and overwrite:
                    target_backup_result = self.create_backup(target_path)
                    result['target_backup_created'] = target_backup_result['success']
                    target_backup_path = target_backup_result.get('backup_path')
                
                # Get source file metadata
                source_metadata = self._get_file_metadata(source_path)
                source_size = source_path.stat().st_size
                
                # Perform the move operation
                shutil.move(str(source_path), str(target_path))
                
                # Update metadata
                if source_metadata:
                    source_metadata.file_path = str(target_path)
                    source_metadata.modified_at = timezone.now()
                    if result.get('backup_path'):
                        source_metadata.backup_paths.append(result['backup_path'])
                    self._store_file_metadata(source_metadata)
                    # Remove old metadata entry
                    self._remove_file_metadata(str(source_path))
                
                # Verify move was successful
                if not target_path.exists():
                    result['error'] = "Move operation failed - target file does not exist"
                    return result
                
                result.update({
                    'success': True,
                    'file_size': source_size,
                    'target_file_size': target_path.stat().st_size,
                    'target_backup_path': target_backup_path,
                    'completed_at': timezone.now()
                })
                
                logger.info(f"Successfully moved file: {source_path} -> {target_path}")
                
        except Exception as e:
            logger.error(f"File move failed from {source_path} to {target_path}: {str(e)}")
            result['error'] = str(e)
            result['completed_at'] = timezone.now()
        
        self._record_operation(result)
        return result
    
    def copy_file(self, source_path: Union[str, Path], target_path: Union[str, Path],
                 preserve_metadata: bool = True, overwrite: bool = False) -> Dict[str, Any]:
        """
        Copy a file with metadata preservation and safety checks.
        
        Args:
            source_path: Source file path
            target_path: Target file path
            preserve_metadata: Whether to preserve file metadata
            overwrite: Whether to overwrite existing target file
            
        Returns:
            Dict with operation results
        """
        source_path = self._resolve_path(source_path)
        target_path = self._resolve_path(target_path)
        operation_id = f"copy_{int(time.time())}"
        
        logger.info(f"Copying file: {source_path} -> {target_path}")
        
        result = {
            'success': False,
            'operation': 'copy',
            'source_path': str(source_path),
            'target_path': str(target_path),
            'operation_id': operation_id,
            'started_at': timezone.now()
        }
        
        try:
            with self.file_locks.acquire(str(source_path)), \
                 self.file_locks.acquire(str(target_path)):
                
                # Validate source file
                if not source_path.exists():
                    result['error'] = "Source file does not exist"
                    return result
                
                # Check target handling
                if target_path.exists() and not overwrite:
                    result['error'] = "Target file exists and overwrite is False"
                    return result
                
                # Create target directory
                target_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Get source metadata
                source_metadata = self._get_file_metadata(source_path)
                source_size = source_path.stat().st_size
                
                # Perform copy operation
                if preserve_metadata:
                    shutil.copy2(source_path, target_path)
                else:
                    shutil.copy(source_path, target_path)
                
                # Create metadata for target file
                if source_metadata and preserve_metadata:
                    target_metadata = FileMetadata(
                        file_path=str(target_path),
                        file_hash=self._calculate_file_hash(target_path),
                        size=target_path.stat().st_size,
                        created_at=timezone.now(),
                        modified_at=timezone.now(),
                        accessed_at=timezone.now(),
                        permissions=oct(target_path.stat().st_mode),
                        owner=source_metadata.owner,
                        group=source_metadata.group,
                        version=1,  # New file gets version 1
                        backup_paths=[],
                        tags=source_metadata.tags.copy()
                    )
                    self._store_file_metadata(target_metadata)
                
                # Verify copy was successful
                if not target_path.exists():
                    result['error'] = "Copy operation failed - target file does not exist"
                    return result
                
                # Verify file integrity if checksums are enabled
                if self.verify_checksums and source_metadata:
                    target_hash = self._calculate_file_hash(target_path)
                    if target_hash != source_metadata.file_hash:
                        result['error'] = "Copy integrity verification failed - file hashes don't match"
                        return result
                
                result.update({
                    'success': True,
                    'source_size': source_size,
                    'target_size': target_path.stat().st_size,
                    'metadata_preserved': preserve_metadata,
                    'completed_at': timezone.now()
                })
                
                logger.info(f"Successfully copied file: {source_path} -> {target_path}")
                
        except Exception as e:
            logger.error(f"File copy failed from {source_path} to {target_path}: {str(e)}")
            result['error'] = str(e)
            result['completed_at'] = timezone.now()
        
        self._record_operation(result)
        return result
    
    def create_backup(self, file_path: Union[str, Path], backup_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a backup of a file with versioning.
        
        Args:
            file_path: Path to the file to backup
            backup_name: Optional custom backup name
            
        Returns:
            Dict with backup results
        """
        file_path = self._resolve_path(file_path)
        
        if not file_path.exists():
            return {'success': False, 'error': 'File does not exist'}
        
        try:
            timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
            if backup_name:
                backup_filename = f"{backup_name}_{timestamp}"
            else:
                backup_filename = f"{file_path.name}_{timestamp}.backup"
            
            backup_path = self.backup_directory / backup_filename
            
            # Create backup using copy2 to preserve metadata
            shutil.copy2(file_path, backup_path)
            
            # Update file metadata with backup path
            file_metadata = self._get_file_metadata(file_path)
            if file_metadata:
                file_metadata.backup_paths.append(str(backup_path))
                self._store_file_metadata(file_metadata)
            
            # Clean up old backups if needed
            self._cleanup_old_backups(file_path)
            
            return {
                'success': True,
                'backup_path': str(backup_path),
                'backup_size': backup_path.stat().st_size,
                'created_at': timezone.now()
            }
            
        except Exception as e:
            logger.error(f"Backup creation failed for {file_path}: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def restore_from_backup(self, file_path: Union[str, Path], backup_path: Union[str, Path],
                           create_current_backup: bool = True) -> Dict[str, Any]:
        """
        Restore a file from a backup.
        
        Args:
            file_path: Path where the file should be restored
            backup_path: Path to the backup file
            create_current_backup: Whether to backup current file before restoring
            
        Returns:
            Dict with restoration results
        """
        file_path = self._resolve_path(file_path)
        backup_path = self._resolve_path(backup_path)
        
        logger.info(f"Restoring file from backup: {backup_path} -> {file_path}")
        
        result = {
            'success': False,
            'operation': 'restore',
            'file_path': str(file_path),
            'backup_path': str(backup_path),
            'started_at': timezone.now()
        }
        
        try:
            if not backup_path.exists():
                result['error'] = "Backup file does not exist"
                return result
            
            # Create backup of current file if it exists
            if file_path.exists() and create_current_backup:
                current_backup_result = self.create_backup(file_path)
                result['current_backup_created'] = current_backup_result['success']
                result['current_backup_path'] = current_backup_result.get('backup_path')
            
            # Restore from backup
            file_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup_path, file_path)
            
            # Update metadata
            restored_metadata = self._create_file_metadata(file_path)
            restored_metadata.tags.append('restored')
            self._store_file_metadata(restored_metadata)
            
            result.update({
                'success': True,
                'restored_size': file_path.stat().st_size,
                'completed_at': timezone.now()
            })
            
            logger.info(f"Successfully restored file from backup: {file_path}")
            
        except Exception as e:
            logger.error(f"File restoration failed: {str(e)}")
            result['error'] = str(e)
            result['completed_at'] = timezone.now()
        
        self._record_operation(result)
        return result
    
    def create_directory_structure(self, structure_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a complete directory structure with files and permissions.
        
        Args:
            structure_config: Configuration defining the directory structure
            
        Returns:
            Dict with creation results
        """
        logger.info(f"Creating directory structure from config")
        
        result = {
            'success': False,
            'operation': 'create_directory_structure',
            'started_at': timezone.now(),
            'directories_created': [],
            'files_created': [],
            'errors': []
        }
        
        try:
            base_path = self._resolve_path(structure_config.get('base_path', '.'))
            
            # Create directories
            for dir_config in structure_config.get('directories', []):
                dir_path = base_path / dir_config['path']
                try:
                    dir_path.mkdir(parents=True, exist_ok=True)
                    
                    # Set permissions if specified
                    if 'permissions' in dir_config:
                        dir_path.chmod(int(dir_config['permissions'], 8))
                    
                    result['directories_created'].append(str(dir_path))
                    
                except Exception as e:
                    result['errors'].append(f"Failed to create directory {dir_path}: {str(e)}")
            
            # Create files
            for file_config in structure_config.get('files', []):
                file_path = base_path / file_config['path']
                try:
                    content = file_config.get('content', '')
                    template_vars = file_config.get('template_vars', {})
                    
                    # Process template if variables are provided
                    if template_vars:
                        content = self._process_template(content, template_vars)
                    
                    file_result = self.create_file(file_path, content, create_backup=False)
                    if file_result['success']:
                        result['files_created'].append(str(file_path))
                    else:
                        result['errors'].append(f"Failed to create file {file_path}: {file_result.get('error')}")
                        
                except Exception as e:
                    result['errors'].append(f"Failed to create file {file_path}: {str(e)}")
            
            result['success'] = len(result['errors']) == 0
            result['completed_at'] = timezone.now()
            
            logger.info(f"Directory structure creation completed: "
                       f"{len(result['directories_created'])} dirs, "
                       f"{len(result['files_created'])} files, "
                       f"{len(result['errors'])} errors")
            
        except Exception as e:
            logger.error(f"Directory structure creation failed: {str(e)}")
            result['error'] = str(e)
            result['completed_at'] = timezone.now()
        
        return result
    
    def validate_directory_structure(self, expected_structure: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate that a directory structure matches expectations.
        
        Args:
            expected_structure: Expected directory and file structure
            
        Returns:
            Dict with validation results
        """
        result = {
            'valid': False,
            'missing_directories': [],
            'missing_files': [],
            'unexpected_items': [],
            'permission_issues': [],
            'validation_errors': []
        }
        
        try:
            base_path = self._resolve_path(expected_structure.get('base_path', '.'))
            
            # Check directories
            for dir_config in expected_structure.get('directories', []):
                dir_path = base_path / dir_config['path']
                if not dir_path.exists():
                    result['missing_directories'].append(str(dir_path))
                elif not dir_path.is_dir():
                    result['validation_errors'].append(f"{dir_path} exists but is not a directory")
                else:
                    # Check permissions if specified
                    if 'permissions' in dir_config:
                        expected_perms = int(dir_config['permissions'], 8)
                        actual_perms = dir_path.stat().st_mode & 0o777
                        if actual_perms != expected_perms:
                            result['permission_issues'].append(
                                f"{dir_path}: expected {oct(expected_perms)}, got {oct(actual_perms)}"
                            )
            
            # Check files
            for file_config in expected_structure.get('files', []):
                file_path = base_path / file_config['path']
                if not file_path.exists():
                    result['missing_files'].append(str(file_path))
                elif not file_path.is_file():
                    result['validation_errors'].append(f"{file_path} exists but is not a file")
            
            # Check for unexpected items if strict mode is enabled
            if expected_structure.get('strict_validation', False):
                expected_items = set()
                for dir_config in expected_structure.get('directories', []):
                    expected_items.add(str(base_path / dir_config['path']))
                for file_config in expected_structure.get('files', []):
                    expected_items.add(str(base_path / file_config['path']))
                
                for item in base_path.rglob('*'):
                    if str(item) not in expected_items:
                        result['unexpected_items'].append(str(item))
            
            # Overall validation result
            result['valid'] = (
                len(result['missing_directories']) == 0 and
                len(result['missing_files']) == 0 and
                len(result['validation_errors']) == 0
            )
            
        except Exception as e:
            result['validation_errors'].append(f"Validation failed: {str(e)}")
        
        return result
    
    def get_file_metadata(self, file_path: Union[str, Path]) -> Optional[FileMetadata]:
        """Get metadata for a specific file."""
        return self._get_file_metadata(self._resolve_path(file_path))
    
    def list_files_with_metadata(self, directory_path: Union[str, Path] = None,
                                recursive: bool = True) -> List[FileMetadata]:
        """List all files with their metadata."""
        if directory_path:
            search_path = self._resolve_path(directory_path)
        else:
            search_path = self.base_directory
        
        files_with_metadata = []
        pattern = '**/*' if recursive else '*'
        
        for file_path in search_path.glob(pattern):
            if file_path.is_file():
                metadata = self._get_file_metadata(file_path)
                if metadata:
                    files_with_metadata.append(metadata)
        
        return files_with_metadata
    
    def cleanup_old_backups(self, max_age_days: Optional[int] = None) -> Dict[str, Any]:
        """Clean up old backup files based on retention policy."""
        max_age_days = max_age_days or self.backup_retention_days
        cutoff_date = timezone.now() - timedelta(days=max_age_days)
        
        result = {
            'backups_removed': 0,
            'space_freed': 0,
            'errors': []
        }
        
        try:
            for backup_file in self.backup_directory.glob('*.backup'):
                try:
                    backup_time = datetime.fromtimestamp(backup_file.stat().st_mtime)
                    if backup_time < cutoff_date.replace(tzinfo=None):
                        file_size = backup_file.stat().st_size
                        backup_file.unlink()
                        result['backups_removed'] += 1
                        result['space_freed'] += file_size
                        
                except Exception as e:
                    result['errors'].append(f"Failed to remove backup {backup_file}: {str(e)}")
            
            logger.info(f"Backup cleanup completed: {result['backups_removed']} files removed, "
                       f"{result['space_freed']} bytes freed")
            
        except Exception as e:
            result['errors'].append(f"Backup cleanup failed: {str(e)}")
        
        return result
    
    # Private helper methods
    
    def _resolve_path(self, path: Union[str, Path]) -> Path:
        """Resolve and validate a file path within the managed directory."""
        resolved_path = Path(path).resolve()
        
        # Ensure path is within the managed base directory
        try:
            resolved_path.relative_to(self.base_directory)
        except ValueError:
            # Path is outside base directory, make it relative
            if not Path(path).is_absolute():
                resolved_path = (self.base_directory / path).resolve()
            else:
                raise ValueError(f"Path {path} is outside managed directory {self.base_directory}")
        
        return resolved_path
    
    @contextmanager
    def _atomic_write(self, file_path: Path) -> Generator:
        """Context manager for atomic file writing using temporary file."""
        temp_file = None
        try:
            # Create temporary file in the same directory as target
            temp_fd, temp_path = tempfile.mkstemp(
                prefix=f'.tmp_{file_path.name}_',
                suffix='.tmp',
                dir=file_path.parent
            )
            temp_file = os.fdopen(temp_fd, 'wb')
            
            yield temp_file
            
            # Close and sync the temporary file
            temp_file.close()
            temp_file = None
            
            # Atomically replace the target file
            os.replace(temp_path, file_path)
            
        except Exception:
            # Clean up on error
            if temp_file:
                temp_file.close()
            with suppress(OSError):
                os.unlink(temp_path)
            raise
    
    def _create_file_metadata(self, file_path: Path, additional_metadata: Optional[Dict[str, Any]] = None) -> FileMetadata:
        """Create metadata record for a file."""
        stat_info = file_path.stat()
        
        metadata = FileMetadata(
            file_path=str(file_path),
            file_hash=self._calculate_file_hash(file_path),
            size=stat_info.st_size,
            created_at=timezone.now(),
            modified_at=datetime.fromtimestamp(stat_info.st_mtime, tz=timezone.utc),
            accessed_at=datetime.fromtimestamp(stat_info.st_atime, tz=timezone.utc),
            permissions=oct(stat_info.st_mode),
            owner=str(stat_info.st_uid),
            group=str(stat_info.st_gid),
            version=1,
            backup_paths=[],
            tags=[]
        )
        
        if additional_metadata:
            for key, value in additional_metadata.items():
                if hasattr(metadata, key):
                    setattr(metadata, key, value)
        
        return metadata
    
    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate hash for a file."""
        hash_algo = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hash_algo.update(chunk)
        return hash_algo.hexdigest()
    
    def _store_file_metadata(self, metadata: FileMetadata, mark_deleted: bool = False):
        """Store file metadata in the metadata index."""
        try:
            metadata_file = self.metadata_directory / 'file_index.json'
            
            # Load existing metadata
            if metadata_file.exists():
                with open(metadata_file, 'r') as f:
                    metadata_index = json.load(f)
            else:
                metadata_index = {}
            
            # Update metadata entry
            file_key = str(Path(metadata.file_path).relative_to(self.base_directory))
            metadata_dict = asdict(metadata)
            
            if mark_deleted:
                metadata_dict['deleted_at'] = timezone.now().isoformat()
            
            metadata_index[file_key] = metadata_dict
            
            # Write updated metadata
            with open(metadata_file, 'w') as f:
                json.dump(metadata_index, f, indent=2, default=str)
                
        except Exception as e:
            logger.error(f"Failed to store metadata for {metadata.file_path}: {str(e)}")
    
    def _get_file_metadata(self, file_path: Path) -> Optional[FileMetadata]:
        """Retrieve file metadata from the index."""
        try:
            metadata_file = self.metadata_directory / 'file_index.json'
            if not metadata_file.exists():
                return None
            
            with open(metadata_file, 'r') as f:
                metadata_index = json.load(f)
            
            file_key = str(file_path.relative_to(self.base_directory))
            metadata_dict = metadata_index.get(file_key)
            
            if metadata_dict and 'deleted_at' not in metadata_dict:
                # Convert datetime strings back to datetime objects
                for field in ['created_at', 'modified_at', 'accessed_at']:
                    if field in metadata_dict:
                        metadata_dict[field] = datetime.fromisoformat(metadata_dict[field])
                
                return FileMetadata(**metadata_dict)
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get metadata for {file_path}: {str(e)}")
            return None
    
    def _remove_file_metadata(self, file_path: str):
        """Remove file metadata from the index."""
        try:
            metadata_file = self.metadata_directory / 'file_index.json'
            if not metadata_file.exists():
                return
            
            with open(metadata_file, 'r') as f:
                metadata_index = json.load(f)
            
            file_key = str(Path(file_path).relative_to(self.base_directory))
            metadata_index.pop(file_key, None)
            
            with open(metadata_file, 'w') as f:
                json.dump(metadata_index, f, indent=2, default=str)
                
        except Exception as e:
            logger.error(f"Failed to remove metadata for {file_path}: {str(e)}")
    
    def _create_empty_metadata_index(self):
        """Create an empty metadata index file."""
        metadata_file = self.metadata_directory / 'file_index.json'
        with open(metadata_file, 'w') as f:
            json.dump({}, f)
    
    def _validate_file_creation(self, file_path: Path, content: Union[str, bytes]) -> Dict[str, Any]:
        """Validate file creation parameters."""
        if isinstance(content, str):
            content_size = len(content.encode('utf-8'))
        else:
            content_size = len(content)
        
        if content_size > self.max_file_size:
            return {
                'valid': False,
                'error': f'File size {content_size} exceeds maximum {self.max_file_size}'
            }
        
        return {'valid': True}
    
    def _validate_file_content(self, content: bytes) -> Dict[str, Any]:
        """Validate file content."""
        if len(content) > self.max_file_size:
            return {
                'valid': False,
                'error': f'Content size {len(content)} exceeds maximum {self.max_file_size}'
            }
        
        return {'valid': True}
    
    def _verify_file_integrity(self, file_path: Path, expected_hash: str) -> Dict[str, Any]:
        """Verify file integrity using checksum."""
        try:
            actual_hash = self._calculate_file_hash(file_path)
            if actual_hash == expected_hash:
                return {'valid': True}
            else:
                return {
                    'valid': False,
                    'error': f'Hash mismatch: expected {expected_hash}, got {actual_hash}'
                }
        except Exception as e:
            return {
                'valid': False,
                'error': f'Integrity check failed: {str(e)}'
            }
    
    def _secure_delete_file(self, file_path: Path, passes: int = 3):
        """Securely delete a file by overwriting with random data."""
        file_size = file_path.stat().st_size
        
        with open(file_path, 'r+b') as f:
            for _ in range(passes):
                f.seek(0)
                f.write(os.urandom(file_size))
                f.flush()
                os.fsync(f.fileno())
        
        file_path.unlink()
    
    def _cleanup_old_backups(self, file_path: Path):
        """Clean up old backups for a specific file."""
        file_backups = []
        base_name = file_path.name
        
        # Find all backups for this file
        for backup_file in self.backup_directory.glob(f"{base_name}_*.backup"):
            file_backups.append((backup_file.stat().st_mtime, backup_file))
        
        # Sort by modification time (newest first)
        file_backups.sort(reverse=True)
        
        # Remove excess backups
        if len(file_backups) > self.max_backup_versions:
            for _, backup_file in file_backups[self.max_backup_versions:]:
                try:
                    backup_file.unlink()
                    logger.debug(f"Removed old backup: {backup_file}")
                except Exception as e:
                    logger.warning(f"Failed to remove old backup {backup_file}: {str(e)}")
    
    def _process_template(self, content: str, variables: Dict[str, Any]) -> str:
        """Process template content with variables."""
        # Simple variable substitution - could be enhanced with Jinja2
        for key, value in variables.items():
            content = content.replace(f"{{{{{key}}}}}", str(value))
        return content
    
    def _record_operation(self, operation_result: Dict[str, Any]):
        """Record operation in the history log."""
        self.operation_history.append(operation_result)
        
        # Keep only recent operations to prevent memory buildup
        if len(self.operation_history) > 1000:
            self.operation_history = self.operation_history[-500:]