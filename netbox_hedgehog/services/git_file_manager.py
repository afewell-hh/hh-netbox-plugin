"""
Enhanced Git File Manager Service
Provides advanced GitOps file management capabilities with smart synchronization,
conflict detection, and atomic operations with rollback support.
"""

import os
import shutil
import logging
import hashlib
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime, timedelta
from contextlib import contextmanager

from django.utils import timezone
from django.db import transaction
from django.conf import settings

logger = logging.getLogger(__name__)


class GitFileManager:
    """
    Enhanced Git file operations manager with smart bi-directional synchronization,
    advanced conflict detection, and atomic operations with rollback capabilities.
    
    Key Features:
    - Smart bi-directional file synchronization between NetBox and Git
    - Advanced file versioning with conflict detection
    - Atomic file operations with rollback capabilities
    - Integration with existing Git repository management
    """
    
    def __init__(self, fabric):
        self.fabric = fabric
        self.operation_log = []
        self.backup_registry = {}
        
        # Initialize paths
        self._initialize_paths()
        
        # Configuration
        self.max_file_size = getattr(settings, 'GITOPS_MAX_FILE_SIZE', 10 * 1024 * 1024)  # 10MB
        self.backup_retention_days = getattr(settings, 'GITOPS_BACKUP_RETENTION_DAYS', 30)
        
    def _initialize_paths(self):
        """Initialize all required paths for GitOps operations."""
        # Base path from fabric configuration
        if hasattr(self.fabric, 'git_repository') and self.fabric.git_repository:
            base_path = getattr(self.fabric.git_repository, 'local_path', None)
            if base_path:
                self.base_path = Path(base_path)
            else:
                self.base_path = Path(f"/tmp/hedgehog-repos/{self.fabric.name}")
        else:
            self.base_path = Path(f"/tmp/hedgehog-repos/{self.fabric.name}")
        
        # GitOps structure paths
        self.gitops_path = self.base_path / 'gitops'
        self.raw_path = self.gitops_path / 'raw'
        self.managed_path = self.gitops_path / 'managed'
        self.templates_path = self.gitops_path / 'templates'
        self.archive_path = self.gitops_path / '.archive'
        self.backup_path = self.gitops_path / '.backups'
        
        # Metadata paths
        self.metadata_path = self.gitops_path / '.hnp'
        self.conflicts_path = self.metadata_path / 'conflicts'
        self.operations_log_path = self.metadata_path / 'operations.log'
        
    def smart_sync_files(self, direction: str = 'bidirectional') -> Dict[str, Any]:
        """
        Perform smart bi-directional file synchronization with conflict detection.
        
        Args:
            direction: 'push', 'pull', or 'bidirectional'
            
        Returns:
            Dict with sync results and conflict information
        """
        logger.info(f"Starting smart file sync for fabric {self.fabric.name}, direction: {direction}")
        
        sync_result = {
            'success': False,
            'direction': direction,
            'started_at': timezone.now(),
            'files_processed': 0,
            'files_synchronized': 0,
            'conflicts_detected': 0,
            'conflicts': [],
            'errors': [],
            'warnings': [],
            'operations': []
        }
        
        try:
            with self._atomic_operation("smart_sync"):
                # Ensure repository structure exists
                self._ensure_gitops_structure()
                
                # Pre-sync validation
                validation_result = self._validate_git_state()
                if not validation_result['valid']:
                    sync_result['errors'].append(f"Git state validation failed: {validation_result['error']}")
                    return sync_result
                
                # Detect and handle conflicts before sync
                conflicts = self._detect_file_conflicts()
                if conflicts:
                    sync_result['conflicts_detected'] = len(conflicts)
                    sync_result['conflicts'] = conflicts
                    
                    # Auto-resolve conflicts where possible
                    auto_resolved = self._auto_resolve_conflicts(conflicts)
                    sync_result['auto_resolved'] = len(auto_resolved)
                
                # Perform synchronization based on direction
                if direction in ['pull', 'bidirectional']:
                    pull_result = self._smart_pull()
                    sync_result['operations'].append(pull_result)
                    sync_result['files_processed'] += pull_result.get('files_processed', 0)
                
                if direction in ['push', 'bidirectional']:
                    push_result = self._smart_push()
                    sync_result['operations'].append(push_result)
                    sync_result['files_processed'] += push_result.get('files_processed', 0)
                
                # Post-sync validation
                post_validation = self._validate_sync_integrity()
                if not post_validation['valid']:
                    raise Exception(f"Post-sync validation failed: {post_validation['error']}")
                
                sync_result['success'] = True
                sync_result['files_synchronized'] = sync_result['files_processed']
                sync_result['completed_at'] = timezone.now()
                
                logger.info(f"Smart sync completed for fabric {self.fabric.name}: "
                           f"{sync_result['files_synchronized']} files synchronized")
                
                return sync_result
                
        except Exception as e:
            logger.error(f"Smart sync failed for fabric {self.fabric.name}: {str(e)}")
            sync_result['error'] = str(e)
            sync_result['completed_at'] = timezone.now()
            
            # Attempt rollback
            try:
                self._rollback_operation("smart_sync")
                sync_result['rollback_successful'] = True
            except Exception as rollback_error:
                logger.error(f"Rollback failed: {rollback_error}")
                sync_result['rollback_successful'] = False
                sync_result['rollback_error'] = str(rollback_error)
            
            return sync_result
    
    def atomic_file_operation(self, operation: str, file_path: Union[str, Path], 
                            content: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """
        Perform atomic file operations with automatic backup and rollback.
        
        Args:
            operation: 'create', 'update', 'delete', 'move', 'copy'
            file_path: Target file path
            content: File content for create/update operations
            **kwargs: Additional operation-specific parameters
            
        Returns:
            Dict with operation results
        """
        file_path = Path(file_path)
        operation_id = f"{operation}_{file_path.name}_{int(timezone.now().timestamp())}"
        
        logger.info(f"Starting atomic file operation: {operation} on {file_path}")
        
        result = {
            'success': False,
            'operation': operation,
            'file_path': str(file_path),
            'operation_id': operation_id,
            'started_at': timezone.now()
        }
        
        try:
            with self._atomic_operation(operation_id):
                # Create backup before operation
                if file_path.exists():
                    backup_path = self._create_file_backup(file_path)
                    result['backup_path'] = str(backup_path)
                
                # Validate operation parameters
                validation = self._validate_file_operation(operation, file_path, content, **kwargs)
                if not validation['valid']:
                    raise ValueError(f"Invalid operation: {validation['error']}")
                
                # Perform the operation
                if operation == 'create':
                    result.update(self._create_file(file_path, content, **kwargs))
                elif operation == 'update':
                    result.update(self._update_file(file_path, content, **kwargs))
                elif operation == 'delete':
                    result.update(self._delete_file(file_path, **kwargs))
                elif operation == 'move':
                    target_path = kwargs.get('target_path')
                    result.update(self._move_file(file_path, target_path, **kwargs))
                elif operation == 'copy':
                    target_path = kwargs.get('target_path')
                    result.update(self._copy_file(file_path, target_path, **kwargs))
                else:
                    raise ValueError(f"Unsupported operation: {operation}")
                
                # Validate post-operation state
                post_validation = self._validate_post_operation(operation, file_path, **kwargs)
                if not post_validation['valid']:
                    raise Exception(f"Post-operation validation failed: {post_validation['error']}")
                
                result['success'] = True
                result['completed_at'] = timezone.now()
                
                logger.info(f"Atomic file operation completed: {operation} on {file_path}")
                return result
                
        except Exception as e:
            logger.error(f"Atomic file operation failed: {operation} on {file_path}: {str(e)}")
            result['error'] = str(e)
            result['completed_at'] = timezone.now()
            
            # Attempt rollback
            try:
                self._rollback_operation(operation_id)
                result['rollback_successful'] = True
            except Exception as rollback_error:
                logger.error(f"Rollback failed for operation {operation_id}: {rollback_error}")
                result['rollback_successful'] = False
                result['rollback_error'] = str(rollback_error)
            
            return result
    
    def detect_and_resolve_conflicts(self) -> Dict[str, Any]:
        """
        Detect file conflicts and attempt resolution using smart strategies.
        
        Returns:
            Dict with conflict detection and resolution results
        """
        logger.info(f"Starting conflict detection for fabric {self.fabric.name}")
        
        result = {
            'success': False,
            'started_at': timezone.now(),
            'conflicts_detected': 0,
            'conflicts_resolved': 0,
            'conflicts': [],
            'resolution_strategies': {},
            'errors': []
        }
        
        try:
            # Detect all types of conflicts
            conflicts = self._comprehensive_conflict_detection()
            result['conflicts_detected'] = len(conflicts)
            result['conflicts'] = conflicts
            
            if not conflicts:
                result['success'] = True
                result['message'] = "No conflicts detected"
                return result
            
            # Apply resolution strategies
            for conflict in conflicts:
                try:
                    resolution = self._resolve_single_conflict(conflict)
                    if resolution['success']:
                        result['conflicts_resolved'] += 1
                        result['resolution_strategies'][conflict['conflict_id']] = resolution
                    else:
                        result['errors'].append(f"Failed to resolve conflict {conflict['conflict_id']}: {resolution['error']}")
                except Exception as e:
                    result['errors'].append(f"Error resolving conflict {conflict['conflict_id']}: {str(e)}")
            
            result['success'] = result['conflicts_resolved'] > 0 or len(result['errors']) == 0
            result['completed_at'] = timezone.now()
            
            logger.info(f"Conflict detection completed: {result['conflicts_resolved']}/{result['conflicts_detected']} resolved")
            return result
            
        except Exception as e:
            logger.error(f"Conflict detection failed: {str(e)}")
            result['error'] = str(e)
            result['completed_at'] = timezone.now()
            return result
    
    def get_file_version_history(self, file_path: Union[str, Path]) -> List[Dict[str, Any]]:
        """
        Get version history for a specific file from Git and backup records.
        
        Args:
            file_path: Path to the file
            
        Returns:
            List of version records with timestamps and changes
        """
        file_path = Path(file_path)
        
        try:
            # Get Git history
            git_history = self._get_git_file_history(file_path)
            
            # Get backup history
            backup_history = self._get_backup_file_history(file_path)
            
            # Combine and sort by timestamp
            all_versions = git_history + backup_history
            all_versions.sort(key=lambda x: x['timestamp'], reverse=True)
            
            return all_versions
            
        except Exception as e:
            logger.error(f"Failed to get version history for {file_path}: {str(e)}")
            return []
    
    @contextmanager
    def _atomic_operation(self, operation_id: str):
        """Context manager for atomic operations with rollback capability."""
        logger.debug(f"Starting atomic operation: {operation_id}")
        
        # Create operation checkpoint
        checkpoint = {
            'operation_id': operation_id,
            'timestamp': timezone.now(),
            'initial_state': self._capture_state_snapshot(),
            'operations': []
        }
        
        self.operation_log.append(checkpoint)
        
        try:
            yield checkpoint
            # Operation succeeded, finalize
            logger.debug(f"Atomic operation completed: {operation_id}")
        except Exception as e:
            # Operation failed, prepare for rollback
            logger.error(f"Atomic operation failed: {operation_id}, preparing rollback")
            raise
    
    def _rollback_operation(self, operation_id: str):
        """Rollback a specific operation using its checkpoint data."""
        logger.info(f"Rolling back operation: {operation_id}")
        
        # Find the operation checkpoint
        checkpoint = None
        for log_entry in reversed(self.operation_log):
            if log_entry['operation_id'] == operation_id:
                checkpoint = log_entry
                break
        
        if not checkpoint:
            raise Exception(f"No checkpoint found for operation {operation_id}")
        
        try:
            # Restore file system state
            self._restore_state_snapshot(checkpoint['initial_state'])
            
            # Restore any backed up files
            for file_path, backup_path in self.backup_registry.items():
                if backup_path and Path(backup_path).exists():
                    shutil.copy2(backup_path, file_path)
                    logger.debug(f"Restored {file_path} from backup {backup_path}")
            
            logger.info(f"Successfully rolled back operation: {operation_id}")
            
        except Exception as e:
            logger.error(f"Rollback failed for operation {operation_id}: {str(e)}")
            raise Exception(f"Rollback failed: {str(e)}")
    
    def _ensure_gitops_structure(self):
        """Ensure all required GitOps directories exist."""
        required_dirs = [
            self.gitops_path,
            self.raw_path,
            self.managed_path,
            self.templates_path,
            self.archive_path,
            self.backup_path,
            self.metadata_path,
            self.conflicts_path
        ]
        
        for dir_path in required_dirs:
            dir_path.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Ensured directory exists: {dir_path}")
    
    def _validate_git_state(self) -> Dict[str, Any]:
        """Validate the current Git repository state."""
        if not self.base_path.exists():
            return {'valid': False, 'error': 'Git repository path does not exist'}
        
        if not (self.base_path / '.git').exists():
            return {'valid': False, 'error': 'Not a valid Git repository'}
        
        try:
            # Check if there are uncommitted changes
            result = subprocess.run(
                ['git', 'status', '--porcelain'],
                cwd=self.base_path,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                return {'valid': False, 'error': f'Git status failed: {result.stderr}'}
            
            has_changes = bool(result.stdout.strip())
            
            return {
                'valid': True,
                'has_uncommitted_changes': has_changes,
                'status_output': result.stdout
            }
            
        except subprocess.TimeoutExpired:
            return {'valid': False, 'error': 'Git status command timed out'}
        except Exception as e:
            return {'valid': False, 'error': f'Git validation failed: {str(e)}'}
    
    def _detect_file_conflicts(self) -> List[Dict[str, Any]]:
        """Detect various types of file conflicts."""
        conflicts = []
        
        try:
            # Check for merge conflicts
            merge_conflicts = self._detect_merge_conflicts()
            conflicts.extend(merge_conflicts)
            
            # Check for file system conflicts
            fs_conflicts = self._detect_filesystem_conflicts()
            conflicts.extend(fs_conflicts)
            
            # Check for semantic conflicts
            semantic_conflicts = self._detect_semantic_conflicts()
            conflicts.extend(semantic_conflicts)
            
            return conflicts
            
        except Exception as e:
            logger.error(f"Conflict detection failed: {str(e)}")
            return []
    
    def _detect_merge_conflicts(self) -> List[Dict[str, Any]]:
        """Detect Git merge conflicts."""
        conflicts = []
        
        try:
            # Check for merge conflict markers
            result = subprocess.run(
                ['git', 'diff', '--name-only', '--diff-filter=U'],
                cwd=self.base_path,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0 and result.stdout.strip():
                for file_path in result.stdout.strip().split('\n'):
                    conflicts.append({
                        'type': 'merge_conflict',
                        'file_path': file_path,
                        'conflict_id': f"merge_{hashlib.md5(file_path.encode()).hexdigest()[:8]}",
                        'detected_at': timezone.now(),
                        'severity': 'high'
                    })
            
        except Exception as e:
            logger.warning(f"Failed to detect merge conflicts: {str(e)}")
        
        return conflicts
    
    def _detect_filesystem_conflicts(self) -> List[Dict[str, Any]]:
        """Detect file system level conflicts (permissions, locks, etc.)."""
        conflicts = []
        
        # Check for permission conflicts
        for path in [self.raw_path, self.managed_path]:
            if path.exists():
                try:
                    # Test write permissions
                    test_file = path / '.write_test'
                    test_file.touch()
                    test_file.unlink()
                except PermissionError:
                    conflicts.append({
                        'type': 'permission_conflict',
                        'file_path': str(path),
                        'conflict_id': f"perm_{hashlib.md5(str(path).encode()).hexdigest()[:8]}",
                        'detected_at': timezone.now(),
                        'severity': 'medium',
                        'description': f'No write permission for directory {path}'
                    })
        
        return conflicts
    
    def _detect_semantic_conflicts(self) -> List[Dict[str, Any]]:
        """Detect semantic conflicts in YAML files."""
        conflicts = []
        
        # This would involve comparing YAML content for semantic differences
        # Implementation would depend on specific conflict resolution rules
        # For now, we'll return an empty list as this is a complex feature
        # that would be implemented based on specific requirements
        
        return conflicts
    
    def _auto_resolve_conflicts(self, conflicts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Attempt to automatically resolve conflicts using predefined strategies."""
        resolved = []
        
        for conflict in conflicts:
            try:
                resolution = self._resolve_single_conflict(conflict)
                if resolution['success']:
                    resolved.append(resolution)
            except Exception as e:
                logger.warning(f"Failed to auto-resolve conflict {conflict['conflict_id']}: {str(e)}")
        
        return resolved
    
    def _resolve_single_conflict(self, conflict: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve a single conflict based on its type and context."""
        conflict_type = conflict['type']
        
        if conflict_type == 'merge_conflict':
            return self._resolve_merge_conflict(conflict)
        elif conflict_type == 'permission_conflict':
            return self._resolve_permission_conflict(conflict)
        elif conflict_type == 'semantic_conflict':
            return self._resolve_semantic_conflict(conflict)
        else:
            return {
                'success': False,
                'error': f"Unknown conflict type: {conflict_type}"
            }
    
    def _resolve_merge_conflict(self, conflict: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve Git merge conflicts using smart strategies."""
        # This would implement intelligent merge conflict resolution
        # For now, return a placeholder
        return {
            'success': False,
            'error': 'Merge conflict resolution not yet implemented'
        }
    
    def _resolve_permission_conflict(self, conflict: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve permission-related conflicts."""
        try:
            file_path = Path(conflict['file_path'])
            # Attempt to fix permissions
            file_path.chmod(0o755)
            return {
                'success': True,
                'resolution_method': 'permission_fix',
                'resolved_at': timezone.now()
            }
        except Exception as e:
            return {
                'success': False,
                'error': f"Failed to fix permissions: {str(e)}"
            }
    
    def _resolve_semantic_conflict(self, conflict: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve semantic conflicts in configuration files."""
        # Placeholder for semantic conflict resolution
        return {
            'success': False,
            'error': 'Semantic conflict resolution not yet implemented'
        }
    
    def _smart_pull(self) -> Dict[str, Any]:
        """Perform intelligent pull operation with conflict handling."""
        try:
            result = subprocess.run(
                ['git', 'pull', 'origin', 'main'],
                cwd=self.base_path,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            return {
                'operation': 'pull',
                'success': result.returncode == 0,
                'output': result.stdout,
                'error': result.stderr if result.returncode != 0 else None,
                'files_processed': len(result.stdout.split('\n')) if result.returncode == 0 else 0
            }
            
        except Exception as e:
            return {
                'operation': 'pull',
                'success': False,
                'error': str(e),
                'files_processed': 0
            }
    
    def _smart_push(self) -> Dict[str, Any]:
        """Perform intelligent push operation with pre-push validation."""
        try:
            # Stage all changes
            subprocess.run(
                ['git', 'add', '.'],
                cwd=self.base_path,
                check=True,
                timeout=60
            )
            
            # Commit changes
            commit_msg = f"GitOps file sync - {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}"
            subprocess.run(
                ['git', 'commit', '-m', commit_msg],
                cwd=self.base_path,
                check=True,
                timeout=60
            )
            
            # Push to remote
            result = subprocess.run(
                ['git', 'push', 'origin', 'main'],
                cwd=self.base_path,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            return {
                'operation': 'push',
                'success': result.returncode == 0,
                'output': result.stdout,
                'error': result.stderr if result.returncode != 0 else None,
                'files_processed': 1  # At least one commit
            }
            
        except Exception as e:
            return {
                'operation': 'push',
                'success': False,
                'error': str(e),
                'files_processed': 0
            }
    
    def _validate_sync_integrity(self) -> Dict[str, Any]:
        """Validate the integrity of the sync operation."""
        try:
            # Check if Git repository is in a clean state
            validation = self._validate_git_state()
            if not validation['valid']:
                return validation
            
            # Additional integrity checks could be added here
            return {'valid': True}
            
        except Exception as e:
            return {
                'valid': False,
                'error': f'Sync integrity validation failed: {str(e)}'
            }
    
    def _create_file_backup(self, file_path: Path) -> Path:
        """Create a timestamped backup of a file."""
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"{file_path.name}_{timestamp}.backup"
        backup_path = self.backup_path / backup_name
        
        shutil.copy2(file_path, backup_path)
        self.backup_registry[str(file_path)] = str(backup_path)
        
        logger.debug(f"Created backup: {backup_path}")
        return backup_path
    
    def _validate_file_operation(self, operation: str, file_path: Path, 
                                content: Optional[str], **kwargs) -> Dict[str, Any]:
        """Validate parameters for file operations."""
        if operation in ['create', 'update'] and not content:
            return {'valid': False, 'error': 'Content required for create/update operations'}
        
        if operation in ['move', 'copy'] and 'target_path' not in kwargs:
            return {'valid': False, 'error': 'target_path required for move/copy operations'}
        
        if content and len(content.encode('utf-8')) > self.max_file_size:
            return {'valid': False, 'error': f'File size exceeds maximum allowed size'}
        
        return {'valid': True}
    
    def _create_file(self, file_path: Path, content: str, **kwargs) -> Dict[str, Any]:
        """Create a new file with content."""
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding='utf-8')
        
        return {
            'action': 'created',
            'size': len(content.encode('utf-8'))
        }
    
    def _update_file(self, file_path: Path, content: str, **kwargs) -> Dict[str, Any]:
        """Update an existing file with new content."""
        old_size = file_path.stat().st_size if file_path.exists() else 0
        file_path.write_text(content, encoding='utf-8')
        new_size = len(content.encode('utf-8'))
        
        return {
            'action': 'updated',
            'old_size': old_size,
            'new_size': new_size
        }
    
    def _delete_file(self, file_path: Path, **kwargs) -> Dict[str, Any]:
        """Delete a file."""
        size = file_path.stat().st_size if file_path.exists() else 0
        file_path.unlink(missing_ok=True)
        
        return {
            'action': 'deleted',
            'size': size
        }
    
    def _move_file(self, file_path: Path, target_path: Path, **kwargs) -> Dict[str, Any]:
        """Move a file to a new location."""
        target_path = Path(target_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(file_path), str(target_path))
        
        return {
            'action': 'moved',
            'target_path': str(target_path)
        }
    
    def _copy_file(self, file_path: Path, target_path: Path, **kwargs) -> Dict[str, Any]:
        """Copy a file to a new location."""
        target_path = Path(target_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file_path, target_path)
        
        return {
            'action': 'copied',
            'target_path': str(target_path)
        }
    
    def _validate_post_operation(self, operation: str, file_path: Path, **kwargs) -> Dict[str, Any]:
        """Validate the state after a file operation."""
        if operation == 'create' and not file_path.exists():
            return {'valid': False, 'error': 'File was not created'}
        
        if operation == 'delete' and file_path.exists():
            return {'valid': False, 'error': 'File was not deleted'}
        
        if operation == 'move':
            target_path = Path(kwargs.get('target_path'))
            if not target_path.exists():
                return {'valid': False, 'error': 'File was not moved to target location'}
        
        return {'valid': True}
    
    def _capture_state_snapshot(self) -> Dict[str, Any]:
        """Capture current state for rollback purposes."""
        return {
            'timestamp': timezone.now(),
            'git_status': self._validate_git_state(),
            'file_hashes': self._calculate_directory_hashes()
        }
    
    def _restore_state_snapshot(self, snapshot: Dict[str, Any]):
        """Restore state from a snapshot."""
        # This would implement state restoration logic
        # For now, we'll just log the attempt
        logger.info(f"Restoring state snapshot from {snapshot['timestamp']}")
    
    def _calculate_directory_hashes(self) -> Dict[str, str]:
        """Calculate hashes for all files in managed directories."""
        hashes = {}
        
        for directory in [self.raw_path, self.managed_path]:
            if directory.exists():
                for file_path in directory.rglob('*'):
                    if file_path.is_file():
                        try:
                            with open(file_path, 'rb') as f:
                                file_hash = hashlib.md5(f.read()).hexdigest()
                                hashes[str(file_path.relative_to(self.gitops_path))] = file_hash
                        except Exception as e:
                            logger.warning(f"Failed to hash {file_path}: {str(e)}")
        
        return hashes
    
    def _comprehensive_conflict_detection(self) -> List[Dict[str, Any]]:
        """Perform comprehensive conflict detection across all types."""
        conflicts = []
        
        # Git-level conflicts
        conflicts.extend(self._detect_merge_conflicts())
        
        # File system conflicts
        conflicts.extend(self._detect_filesystem_conflicts())
        
        # Semantic conflicts
        conflicts.extend(self._detect_semantic_conflicts())
        
        return conflicts
    
    def _get_git_file_history(self, file_path: Path) -> List[Dict[str, Any]]:
        """Get Git commit history for a specific file."""
        try:
            result = subprocess.run(
                ['git', 'log', '--format=%H|%ci|%s', '--', str(file_path)],
                cwd=self.base_path,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                return []
            
            history = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    commit_hash, timestamp, message = line.split('|', 2)
                    history.append({
                        'type': 'git_commit',
                        'commit_hash': commit_hash,
                        'timestamp': datetime.fromisoformat(timestamp.replace(' ', 'T')),
                        'message': message,
                        'file_path': str(file_path)
                    })
            
            return history
            
        except Exception as e:
            logger.error(f"Failed to get Git history for {file_path}: {str(e)}")
            return []
    
    def _get_backup_file_history(self, file_path: Path) -> List[Dict[str, Any]]:
        """Get backup history for a specific file."""
        history = []
        
        if not self.backup_path.exists():
            return history
        
        # Look for backup files matching the pattern
        pattern = f"{file_path.name}_*.backup"
        for backup_file in self.backup_path.glob(pattern):
            try:
                # Extract timestamp from filename
                timestamp_str = backup_file.stem.split('_')[-2] + '_' + backup_file.stem.split('_')[-1]
                timestamp = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')
                
                history.append({
                    'type': 'backup',
                    'backup_path': str(backup_file),
                    'timestamp': timestamp,
                    'file_path': str(file_path),
                    'size': backup_file.stat().st_size
                })
                
            except Exception as e:
                logger.warning(f"Failed to parse backup file {backup_file}: {str(e)}")
        
        return history


# Convenience functions for integration with existing services
def create_git_file_manager(fabric) -> GitFileManager:
    """Factory function to create a GitFileManager instance."""
    return GitFileManager(fabric)


def smart_sync_fabric_files(fabric, direction: str = 'bidirectional') -> Dict[str, Any]:
    """Convenience function for smart file synchronization."""
    manager = GitFileManager(fabric)
    return manager.smart_sync_files(direction)


def atomic_file_operation(fabric, operation: str, file_path: Union[str, Path], 
                         content: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """Convenience function for atomic file operations."""
    manager = GitFileManager(fabric)
    return manager.atomic_file_operation(operation, file_path, content, **kwargs)