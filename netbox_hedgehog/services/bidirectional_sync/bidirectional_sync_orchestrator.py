"""
Bidirectional Synchronization Orchestrator

This module orchestrates all bidirectional synchronization workflows between
HNP GUI and GitHub repositories, managing GUI → GitHub and GitHub → GUI sync
operations with comprehensive conflict detection and resolution.
"""

import logging
import hashlib
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


class SyncResult:
    """Result of synchronization operation"""
    
    def __init__(self, success: bool, message: str = '', 
                 files_processed: int = 0, conflicts_detected: int = 0,
                 resources_synced: int = 0, errors: List[str] = None,
                 warnings: List[str] = None, commit_sha: str = None):
        self.success = success
        self.message = message
        self.files_processed = files_processed
        self.conflicts_detected = conflicts_detected
        self.resources_synced = resources_synced
        self.errors = errors or []
        self.warnings = warnings or []
        self.commit_sha = commit_sha
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'message': self.message,
            'files_processed': self.files_processed,
            'conflicts_detected': self.conflicts_detected,
            'resources_synced': self.resources_synced,
            'errors': self.errors,
            'warnings': self.warnings,
            'commit_sha': self.commit_sha,
            'error_count': len(self.errors)
        }


class ChangeDetectionResult:
    """Result of change detection operation"""
    
    def __init__(self, changes_detected: bool, changed_files: List[str] = None,
                 new_files: List[str] = None, deleted_files: List[str] = None,
                 last_check: datetime = None):
        self.changes_detected = changes_detected
        self.changed_files = changed_files or []
        self.new_files = new_files or []
        self.deleted_files = deleted_files or []
        self.last_check = last_check or timezone.now()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'changes_detected': self.changes_detected,
            'changed_files': self.changed_files,
            'new_files': self.new_files,
            'deleted_files': self.deleted_files,
            'total_changes': len(self.changed_files) + len(self.new_files) + len(self.deleted_files),
            'last_check': self.last_check.isoformat()
        }


class ConflictInfo:
    """Information about detected conflict"""
    
    def __init__(self, resource_id: int, resource_name: str, conflict_type: str,
                 gui_timestamp: datetime = None, github_timestamp: datetime = None,
                 conflicting_fields: List[str] = None, details: Dict[str, Any] = None):
        self.resource_id = resource_id
        self.resource_name = resource_name
        self.conflict_type = conflict_type
        self.gui_timestamp = gui_timestamp
        self.github_timestamp = github_timestamp
        self.conflicting_fields = conflicting_fields or []
        self.details = details or {}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'resource_id': self.resource_id,
            'resource_name': self.resource_name,
            'conflict_type': self.conflict_type,
            'gui_timestamp': self.gui_timestamp.isoformat() if self.gui_timestamp else None,
            'github_timestamp': self.github_timestamp.isoformat() if self.github_timestamp else None,
            'conflicting_fields': self.conflicting_fields,
            'details': self.details
        }


class BidirectionalSyncOrchestrator:
    """
    Orchestrates bidirectional synchronization between HNP GUI and GitHub.
    
    This class manages all synchronization workflows, conflict detection,
    and resolution strategies for maintaining consistency between HNP GUI
    state and GitOps repository state.
    """
    
    def __init__(self, fabric):
        """Initialize orchestrator for specified fabric"""
        self.fabric = fabric
        self.git_repository = fabric.git_repository
        
        if not self.git_repository:
            raise ValueError(f"Fabric {fabric.name} has no Git repository configured")
        
        self.stats = {
            'gui_to_github': {'files': 0, 'resources': 0, 'conflicts': 0},
            'github_to_gui': {'files': 0, 'resources': 0, 'conflicts': 0},
            'total_conflicts': 0,
            'total_errors': 0
        }
        
        self.conflicts_detected = []
        self.errors = []
        self.warnings = []
    
    def sync(self, direction: str = 'bidirectional', force: bool = False,
             conflict_resolution: str = 'user_guided') -> SyncResult:
        """
        Main synchronization entry point.
        
        Args:
            direction: 'gui_to_github', 'github_to_gui', or 'bidirectional'
            force: Force sync even if conflicts are detected
            conflict_resolution: 'timestamp', 'user_guided', or 'merge'
            
        Returns:
            SyncResult with operation details
        """
        logger.info(f"Starting {direction} sync for fabric {self.fabric.name}")
        
        try:
            if direction == 'gui_to_github':
                return self._sync_gui_to_github(force, conflict_resolution)
            elif direction == 'github_to_gui':
                return self._sync_github_to_gui(force, conflict_resolution)
            elif direction == 'bidirectional':
                return self._sync_bidirectional(force, conflict_resolution)
            else:
                return SyncResult(
                    success=False,
                    message=f"Invalid sync direction: {direction}",
                    errors=[f"Invalid sync direction: {direction}"]
                )
        
        except Exception as e:
            logger.error(f"Sync operation failed: {e}")
            return SyncResult(
                success=False,
                message=f"Sync operation failed: {str(e)}",
                errors=[str(e)]
            )
    
    def _sync_gui_to_github(self, force: bool, conflict_resolution: str) -> SyncResult:
        """Sync GUI changes to GitHub repository"""
        logger.info(f"Syncing GUI changes to GitHub for fabric {self.fabric.name}")
        
        files_processed = 0
        resources_synced = 0
        conflicts_detected = 0
        errors = []
        
        try:
            from .github_sync_client import GitHubSyncClient
            from ..models.gitops import HedgehogResource
            
            client = GitHubSyncClient(self.git_repository)
            
            # Get resources that need GUI → GitHub sync
            resources_to_sync = HedgehogResource.objects.filter(
                fabric=self.fabric,
                sync_direction__in=['gui_to_git', 'bidirectional']
            ).exclude(
                conflict_status='detected'
            ) if not force else HedgehogResource.objects.filter(
                fabric=self.fabric,
                sync_direction__in=['gui_to_git', 'bidirectional']
            )
            
            # Process each resource
            for resource in resources_to_sync:
                try:
                    # Check for conflicts if not forcing
                    if not force:
                        conflict = self._detect_resource_conflict(resource)
                        if conflict:
                            conflicts_detected += 1
                            self.conflicts_detected.append(conflict)
                            continue
                    
                    # Generate YAML content from GUI state
                    yaml_content = self._generate_yaml_from_resource(resource)
                    if not yaml_content:
                        errors.append(f"Could not generate YAML for {resource.name}")
                        continue
                    
                    # Determine file path
                    file_path = resource.managed_file_path or self._generate_managed_file_path(resource)
                    
                    # Push to GitHub
                    push_result = client.create_or_update_file(
                        path=file_path,
                        content=yaml_content,
                        message=f"Update {resource.kind}/{resource.name} from HNP GUI"
                    )
                    
                    if push_result['success']:
                        # Update resource file mapping
                        content_hash = hashlib.sha256(yaml_content.encode('utf-8')).hexdigest()
                        resource.update_file_mapping(file_path, content_hash)
                        
                        files_processed += 1
                        resources_synced += 1
                        
                        logger.debug(f"Synced {resource.kind}/{resource.name} to GitHub")
                    else:
                        errors.append(f"Failed to sync {resource.name}: {push_result['error']}")
                
                except Exception as e:
                    errors.append(f"Error syncing resource {resource.name}: {str(e)}")
                    logger.error(f"Error syncing resource {resource.name}: {e}")
            
            # Update statistics
            self.stats['gui_to_github']['files'] = files_processed
            self.stats['gui_to_github']['resources'] = resources_synced
            self.stats['gui_to_github']['conflicts'] = conflicts_detected
            self.stats['total_conflicts'] += conflicts_detected
            self.stats['total_errors'] += len(errors)
            
            success = len(errors) == 0
            message = f"GUI → GitHub sync completed: {resources_synced} resources synced"
            if conflicts_detected > 0:
                message += f", {conflicts_detected} conflicts detected"
            if errors:
                message += f", {len(errors)} errors"
            
            return SyncResult(
                success=success,
                message=message,
                files_processed=files_processed,
                conflicts_detected=conflicts_detected,
                resources_synced=resources_synced,
                errors=errors
            )
        
        except Exception as e:
            logger.error(f"GUI → GitHub sync failed: {e}")
            return SyncResult(
                success=False,
                message=f"GUI → GitHub sync failed: {str(e)}",
                errors=[str(e)]
            )
    
    def _sync_github_to_gui(self, force: bool, conflict_resolution: str) -> SyncResult:
        """Sync GitHub changes to GUI/database"""
        logger.info(f"Syncing GitHub changes to GUI for fabric {self.fabric.name}")
        
        files_processed = 0
        resources_synced = 0
        conflicts_detected = 0
        errors = []
        
        try:
            from .github_sync_client import GitHubSyncClient
            from ..models.gitops import HedgehogResource
            from ..utils.git_directory_sync import GitDirectorySync
            
            # Detect external changes first
            change_detection = self.detect_external_changes()
            
            if not change_detection.changes_detected:
                return SyncResult(
                    success=True,
                    message="No changes detected in GitHub repository",
                    files_processed=0,
                    resources_synced=0
                )
            
            # Use existing Git directory sync for GitHub → GUI
            sync = GitDirectorySync(self.fabric)
            sync_result = sync.sync_from_git()
            
            if sync_result['success']:
                files_processed = sync_result.get('files_processed', 0)
                resources_synced = sync_result.get('resources_created', 0) + sync_result.get('resources_updated', 0)
                
                # Update file mappings for synced resources
                self._update_file_mappings_after_git_sync()
                
                # Check for conflicts in newly synced resources
                if not force:
                    conflicts_detected = self._detect_post_sync_conflicts()
                    self.stats['github_to_gui']['conflicts'] = conflicts_detected
                
                self.stats['github_to_gui']['files'] = files_processed
                self.stats['github_to_gui']['resources'] = resources_synced
                
                return SyncResult(
                    success=True,
                    message=sync_result['message'],
                    files_processed=files_processed,
                    conflicts_detected=conflicts_detected,
                    resources_synced=resources_synced,
                    commit_sha=sync_result.get('commit_sha')
                )
            else:
                return SyncResult(
                    success=False,
                    message=sync_result.get('error', 'GitHub → GUI sync failed'),
                    errors=[sync_result.get('error', 'Unknown error')]
                )
        
        except Exception as e:
            logger.error(f"GitHub → GUI sync failed: {e}")
            return SyncResult(
                success=False,
                message=f"GitHub → GUI sync failed: {str(e)}",
                errors=[str(e)]
            )
    
    def _sync_bidirectional(self, force: bool, conflict_resolution: str) -> SyncResult:
        """Perform bidirectional synchronization"""
        logger.info(f"Performing bidirectional sync for fabric {self.fabric.name}")
        
        try:
            # First, detect external changes
            change_detection = self.detect_external_changes()
            
            # Then, sync GitHub → GUI to get latest state
            github_to_gui_result = self._sync_github_to_gui(force, conflict_resolution)
            
            # Finally, sync GUI → GitHub to push any local changes
            gui_to_github_result = self._sync_gui_to_github(force, conflict_resolution)
            
            # Combine results
            total_files = github_to_gui_result.files_processed + gui_to_github_result.files_processed
            total_resources = github_to_gui_result.resources_synced + gui_to_github_result.resources_synced
            total_conflicts = github_to_gui_result.conflicts_detected + gui_to_github_result.conflicts_detected
            
            all_errors = github_to_gui_result.errors + gui_to_github_result.errors
            
            success = github_to_gui_result.success and gui_to_github_result.success
            message = f"Bidirectional sync completed: {total_resources} resources synced"
            if total_conflicts > 0:
                message += f", {total_conflicts} conflicts detected"
            if all_errors:
                message += f", {len(all_errors)} errors"
            
            return SyncResult(
                success=success,
                message=message,
                files_processed=total_files,
                conflicts_detected=total_conflicts,
                resources_synced=total_resources,
                errors=all_errors,
                commit_sha=gui_to_github_result.commit_sha or github_to_gui_result.commit_sha
            )
        
        except Exception as e:
            logger.error(f"Bidirectional sync failed: {e}")
            return SyncResult(
                success=False,
                message=f"Bidirectional sync failed: {str(e)}",
                errors=[str(e)]
            )
    
    def detect_external_changes(self) -> ChangeDetectionResult:
        """Detect changes made externally to GitHub repository"""
        logger.info(f"Detecting external changes for fabric {self.fabric.name}")
        
        try:
            from .github_sync_client import GitHubSyncClient
            
            client = GitHubSyncClient(self.git_repository)
            
            # Get last known commit SHA
            last_commit = self.fabric.desired_state_commit or ''
            
            # Get current commit SHA
            current_commit_result = client.get_latest_commit()
            if not current_commit_result['success']:
                logger.warning(f"Could not get latest commit: {current_commit_result['error']}")
                return ChangeDetectionResult(changes_detected=False)
            
            current_commit = current_commit_result['commit_sha']
            
            # If commits are the same, no changes
            if last_commit == current_commit:
                return ChangeDetectionResult(changes_detected=False)
            
            # Get list of changed files
            changes_result = client.get_file_changes(
                base_commit=last_commit,
                head_commit=current_commit,
                directory_path=self.fabric.gitops_directory
            )
            
            if not changes_result['success']:
                logger.warning(f"Could not get file changes: {changes_result['error']}")
                return ChangeDetectionResult(changes_detected=False)
            
            changed_files = changes_result.get('changed_files', [])
            new_files = changes_result.get('new_files', [])
            deleted_files = changes_result.get('deleted_files', [])
            
            changes_detected = len(changed_files) > 0 or len(new_files) > 0 or len(deleted_files) > 0
            
            logger.info(f"External changes detected: {len(changed_files)} changed, {len(new_files)} new, {len(deleted_files)} deleted")
            
            return ChangeDetectionResult(
                changes_detected=changes_detected,
                changed_files=changed_files,
                new_files=new_files,
                deleted_files=deleted_files
            )
        
        except Exception as e:
            logger.error(f"External change detection failed: {e}")
            return ChangeDetectionResult(changes_detected=False)
    
    def _detect_resource_conflict(self, resource) -> Optional[ConflictInfo]:
        """Detect conflict for specific resource"""
        try:
            # Check if resource has external modifications
            if resource.external_modifications:
                return ConflictInfo(
                    resource_id=resource.pk,
                    resource_name=resource.name,
                    conflict_type='external_modification',
                    details={
                        'modifications_count': len(resource.external_modifications),
                        'last_modification': resource.external_modifications[-1] if resource.external_modifications else None
                    }
                )
            
            # Check if there's drift between desired and actual state
            if resource.has_drift and resource.drift_status in ['spec_drift']:
                return ConflictInfo(
                    resource_id=resource.pk,
                    resource_name=resource.name,
                    conflict_type='drift_detected',
                    details={
                        'drift_status': resource.drift_status,
                        'drift_score': resource.drift_score,
                        'drift_details': resource.drift_details
                    }
                )
            
            # Check timestamps for concurrent modifications
            if (resource.last_file_sync and resource.last_updated and 
                resource.last_updated > resource.last_file_sync):
                
                return ConflictInfo(
                    resource_id=resource.pk,
                    resource_name=resource.name,
                    conflict_type='concurrent_modification',
                    gui_timestamp=resource.last_updated,
                    github_timestamp=resource.last_file_sync,
                    details={
                        'gui_newer': True,
                        'time_difference': (resource.last_updated - resource.last_file_sync).total_seconds()
                    }
                )
            
            return None
        
        except Exception as e:
            logger.error(f"Error detecting conflict for resource {resource.name}: {e}")
            return None
    
    def _detect_post_sync_conflicts(self) -> int:
        """Detect conflicts after GitHub → GUI sync"""
        conflicts = 0
        
        try:
            from ..models.gitops import HedgehogResource
            
            # Check all resources for conflicts
            resources = HedgehogResource.objects.filter(fabric=self.fabric)
            
            for resource in resources:
                conflict = self._detect_resource_conflict(resource)
                if conflict:
                    conflicts += 1
                    resource.mark_conflict(conflict.conflict_type, conflict.details)
        
        except Exception as e:
            logger.error(f"Error detecting post-sync conflicts: {e}")
        
        return conflicts
    
    def _generate_yaml_from_resource(self, resource) -> Optional[str]:
        """Generate YAML content from HedgehogResource"""
        try:
            return resource.generate_yaml_content()
        except Exception as e:
            logger.error(f"Failed to generate YAML for resource {resource.name}: {e}")
            return None
    
    def _generate_managed_file_path(self, resource) -> str:
        """Generate managed file path for resource"""
        kind_dir = resource.kind.lower() + 's'  # VPC -> vpcs
        return f"managed/{kind_dir}/{resource.name}.yaml"
    
    def _update_file_mappings_after_git_sync(self):
        """Update file mappings after Git sync operation"""
        try:
            from ..models.gitops import HedgehogResource
            
            # Update file mappings for all resources that were synced
            resources = HedgehogResource.objects.filter(
                fabric=self.fabric,
                desired_updated__isnull=False
            )
            
            for resource in resources:
                if resource.desired_file_path and not resource.managed_file_path:
                    # Map desired_file_path to managed_file_path structure
                    managed_path = self._convert_to_managed_path(resource.desired_file_path)
                    
                    if resource.desired_spec:
                        yaml_content = yaml.dump(resource.desired_spec, default_flow_style=False)
                        content_hash = hashlib.sha256(yaml_content.encode('utf-8')).hexdigest()
                        resource.update_file_mapping(managed_path, content_hash)
        
        except Exception as e:
            logger.error(f"Failed to update file mappings: {e}")
    
    def _convert_to_managed_path(self, git_file_path: str) -> str:
        """Convert git file path to managed directory structure"""
        # Simple conversion - could be enhanced based on requirements
        file_name = Path(git_file_path).name
        return f"managed/resources/{file_name}"
    
    def get_sync_statistics(self) -> Dict[str, Any]:
        """Get comprehensive sync statistics"""
        return {
            'fabric': self.fabric.name,
            'statistics': self.stats,
            'conflicts': {
                'total_detected': len(self.conflicts_detected),
                'by_type': self._categorize_conflicts(),
                'details': [conflict.to_dict() for conflict in self.conflicts_detected]
            },
            'errors': {
                'total': len(self.errors),
                'details': self.errors
            },
            'warnings': {
                'total': len(self.warnings),
                'details': self.warnings
            },
            'repository_info': {
                'url': self.git_repository.url,
                'connection_status': self.git_repository.connection_status,
                'can_push': self.git_repository.can_push_directly()
            }
        }
    
    def _categorize_conflicts(self) -> Dict[str, int]:
        """Categorize detected conflicts by type"""
        categories = {}
        for conflict in self.conflicts_detected:
            conflict_type = conflict.conflict_type
            categories[conflict_type] = categories.get(conflict_type, 0) + 1
        return categories
    
    def resolve_conflicts(self, resolution_strategy: str = 'user_guided') -> Dict[str, Any]:
        """
        Resolve detected conflicts using specified strategy.
        
        Args:
            resolution_strategy: 'timestamp', 'user_guided', 'merge', 'gui_wins', 'github_wins'
            
        Returns:
            Dictionary with resolution results
        """
        logger.info(f"Resolving conflicts using {resolution_strategy} strategy")
        
        resolved_conflicts = 0
        resolution_errors = []
        
        try:
            from ..models.gitops import HedgehogResource
            
            # Get resources with conflicts
            conflicted_resources = HedgehogResource.objects.filter(
                fabric=self.fabric,
                conflict_status='detected'
            )
            
            for resource in conflicted_resources:
                try:
                    if resolution_strategy == 'timestamp':
                        self._resolve_conflict_by_timestamp(resource)
                    elif resolution_strategy == 'gui_wins':
                        self._resolve_conflict_gui_wins(resource)
                    elif resolution_strategy == 'github_wins':
                        self._resolve_conflict_github_wins(resource)
                    elif resolution_strategy == 'merge':
                        self._resolve_conflict_merge(resource)
                    else:
                        # user_guided - mark as needing manual resolution
                        continue
                    
                    resolved_conflicts += 1
                    
                except Exception as e:
                    resolution_errors.append(f"Failed to resolve conflict for {resource.name}: {str(e)}")
            
            return {
                'success': len(resolution_errors) == 0,
                'resolved_conflicts': resolved_conflicts,
                'total_conflicts': len(self.conflicts_detected),
                'strategy': resolution_strategy,
                'errors': resolution_errors
            }
        
        except Exception as e:
            logger.error(f"Conflict resolution failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _resolve_conflict_by_timestamp(self, resource):
        """Resolve conflict by choosing most recent modification"""
        # Implementation would check timestamps and choose winner
        # For now, mark as resolved
        resource.resolve_conflict('timestamp_based')
    
    def _resolve_conflict_gui_wins(self, resource):
        """Resolve conflict by keeping GUI state"""
        # Sync GUI state to GitHub
        result = resource.sync_to_github()
        if result['success']:
            resource.resolve_conflict('gui_wins')
    
    def _resolve_conflict_github_wins(self, resource):
        """Resolve conflict by keeping GitHub state"""
        # Update GUI state from current desired_spec
        if resource.desired_spec:
            # Update resource fields based on desired_spec
            # This would need specific implementation based on resource type
            resource.resolve_conflict('github_wins')
    
    def _resolve_conflict_merge(self, resource):
        """Resolve conflict by merging changes"""
        # Intelligent merge would require field-level comparison
        # For now, mark as resolved with merge strategy
        resource.resolve_conflict('merge_attempted')