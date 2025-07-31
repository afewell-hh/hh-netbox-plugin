# Bidirectional Sync Engine Component Specification

**Document Type**: Component Specification  
**Component**: Bidirectional Synchronization Engine  
**Project**: HNP GitOps Bidirectional Synchronization  
**Author**: Backend Technical Specialist  
**Date**: July 30, 2025  
**Version**: 1.0

## Component Overview

The Bidirectional Sync Engine is the core orchestrator that manages synchronization workflows between HNP GUI and GitHub repositories. It coordinates GUI → GitHub workflows, GitHub → GUI workflows, conflict detection and resolution, and maintains the three-state synchronization model.

## Core Components

### 1. BidirectionalSyncOrchestrator

**Purpose**: Primary orchestrator for all bidirectional synchronization operations

**File Location**: `netbox_hedgehog/utils/bidirectional_sync_orchestrator.py`

**Class Definition**:
```python
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import logging
import asyncio
from django.db import transaction
from django.utils import timezone

class SyncDirection(Enum):
    GUI_TO_GITHUB = 'gui_to_github'
    GITHUB_TO_GUI = 'github_to_gui'
    BIDIRECTIONAL = 'bidirectional'

class ConflictResolutionStrategy(Enum):
    TIMESTAMP_WINS = 'timestamp_wins'
    GUI_WINS = 'gui_wins'
    GITHUB_WINS = 'github_wins'
    USER_GUIDED = 'user_guided'
    MERGE_STRATEGY = 'merge_strategy'

@dataclass
class SyncRequest:
    fabric: 'HedgehogFabric'
    direction: SyncDirection
    resource_filters: Optional[List[str]] = None
    force_sync: bool = False
    create_pr: bool = False
    conflict_resolution: ConflictResolutionStrategy = ConflictResolutionStrategy.USER_GUIDED
    initiated_by: Optional['User'] = None
    metadata: Dict[str, Any] = None

@dataclass
class SyncResult:
    success: bool
    operation_id: str
    started_at: datetime
    completed_at: Optional[datetime]
    direction: SyncDirection
    
    # Statistics
    resources_processed: int = 0
    resources_created: int = 0
    resources_updated: int = 0
    resources_deleted: int = 0
    conflicts_detected: int = 0
    conflicts_resolved: int = 0
    
    # GitHub integration
    commit_sha: Optional[str] = None
    pull_request_url: Optional[str] = None
    branch_name: Optional[str] = None
    
    # Error handling
    errors: List[str] = None
    warnings: List[str] = None
    
    # Performance metrics
    processing_time_seconds: float = 0.0
    api_calls_made: int = 0
    files_transferred: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'operation_id': self.operation_id,
            'started_at': self.started_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'direction': self.direction.value,
            'statistics': {
                'resources_processed': self.resources_processed,
                'resources_created': self.resources_created,
                'resources_updated': self.resources_updated,
                'resources_deleted': self.resources_deleted,
                'conflicts_detected': self.conflicts_detected,
                'conflicts_resolved': self.conflicts_resolved
            },
            'github_integration': {
                'commit_sha': self.commit_sha,
                'pull_request_url': self.pull_request_url,
                'branch_name': self.branch_name
            },
            'errors': self.errors or [],
            'warnings': self.warnings or [],
            'performance': {
                'processing_time_seconds': self.processing_time_seconds,
                'api_calls_made': self.api_calls_made,
                'files_transferred': self.files_transferred
            }
        }

@dataclass
class ConflictDetectionResult:
    has_conflicts: bool
    conflicts: List['ResourceConflict']
    total_resources_checked: int
    detection_time_seconds: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'has_conflicts': self.has_conflicts,
            'conflicts': [conflict.to_dict() for conflict in self.conflicts],
            'total_resources_checked': self.total_resources_checked,
            'detection_time_seconds': self.detection_time_seconds
        }

@dataclass
class ResourceConflict:
    resource_id: int
    resource_name: str
    resource_kind: str
    conflict_type: str
    detected_at: datetime
    
    # Conflict details
    gui_modification_time: Optional[datetime] = None
    github_modification_time: Optional[datetime] = None
    conflicting_fields: List[str] = None
    gui_values: Dict[str, Any] = None
    github_values: Dict[str, Any] = None
    
    # Resolution options
    resolution_options: List[str] = None
    auto_resolvable: bool = False
    severity: str = 'medium'  # low, medium, high, critical
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'resource_id': self.resource_id,
            'resource_name': self.resource_name,
            'resource_kind': self.resource_kind,
            'conflict_type': self.conflict_type,
            'detected_at': self.detected_at.isoformat(),
            'details': {
                'gui_modification_time': self.gui_modification_time.isoformat() if self.gui_modification_time else None,
                'github_modification_time': self.github_modification_time.isoformat() if self.github_modification_time else None,
                'conflicting_fields': self.conflicting_fields or [],
                'gui_values': self.gui_values or {},
                'github_values': self.github_values or {}
            },
            'resolution': {
                'options': self.resolution_options or [],
                'auto_resolvable': self.auto_resolvable,
                'severity': self.severity
            }
        }

class BidirectionalSyncOrchestrator:
    """
    Main orchestrator for bidirectional synchronization between HNP GUI and GitHub.
    
    Responsibilities:
    - Coordinate GUI → GitHub sync workflows
    - Coordinate GitHub → GUI sync workflows
    - Detect and manage conflicts
    - Maintain sync operation state and history
    - Provide progress tracking and monitoring
    """
    
    def __init__(self, fabric: 'HedgehogFabric'):
        self.fabric = fabric
        self.logger = logging.getLogger(__name__)
        
        # Initialize component dependencies
        self._directory_manager = None
        self._github_client = None
        self._conflict_detector = None
        self._file_mapper = None
        
        # Operation tracking
        self._active_operations = {}
        self._operation_history = []
        
        # Validate fabric configuration
        if not self._validate_fabric_configuration():
            raise ValueError(f"Fabric {fabric.name} is not properly configured for bidirectional sync")
    
    @property
    def directory_manager(self):
        """Lazy-loaded directory manager"""
        if self._directory_manager is None:
            from .gitops_directory_manager import GitOpsDirectoryManager
            self._directory_manager = GitOpsDirectoryManager(self.fabric)
        return self._directory_manager
    
    @property
    def github_client(self):
        """Lazy-loaded GitHub client"""
        if self._github_client is None:
            from .github_sync_client import GitHubSyncClient
            self._github_client = GitHubSyncClient(self.fabric.git_repository)
        return self._github_client
    
    @property
    def conflict_detector(self):
        """Lazy-loaded conflict detector"""
        if self._conflict_detector is None:
            self._conflict_detector = ConflictDetector(self.fabric)
        return self._conflict_detector
    
    @property
    def file_mapper(self):
        """Lazy-loaded file mapper"""
        if self._file_mapper is None:
            self._file_mapper = FileToRecordMapper(self.fabric)
        return self._file_mapper
    
    def _validate_fabric_configuration(self) -> bool:
        """Validate fabric has required configuration for bidirectional sync"""
        return bool(
            self.fabric.git_repository and
            self.fabric.git_repository.connection_status == 'connected' and
            self.fabric.gitops_directory and
            self.fabric.gitops_initialized
        )
    
    async def sync(self, sync_request: SyncRequest) -> SyncResult:
        """
        Main sync method that coordinates the entire synchronization process.
        
        Args:
            sync_request: Detailed sync request with parameters
            
        Returns:
            SyncResult with complete operation details
        """
        operation_id = self._generate_operation_id()
        start_time = datetime.now()
        
        self.logger.info(f"Starting sync operation {operation_id} for fabric {self.fabric.name}")
        
        # Initialize result
        result = SyncResult(
            success=False,
            operation_id=operation_id,
            started_at=start_time,
            direction=sync_request.direction,
            errors=[],
            warnings=[]
        )
        
        # Track active operation
        self._active_operations[operation_id] = {
            'request': sync_request,
            'result': result,
            'status': 'initializing'
        }
        
        try:
            # Create sync operation record
            sync_operation = await self._create_sync_operation_record(sync_request, operation_id)
            
            # Pre-sync validation
            validation_result = await self._pre_sync_validation(sync_request)
            if not validation_result['valid']:
                result.errors.extend(validation_result['errors'])
                result.warnings.extend(validation_result['warnings'])
                return await self._complete_sync_operation(operation_id, result, sync_operation)
            
            # Detect conflicts before sync
            self._active_operations[operation_id]['status'] = 'detecting_conflicts'
            conflict_result = await self._detect_conflicts(sync_request)
            result.conflicts_detected = len(conflict_result.conflicts)
            
            # Handle conflicts if detected
            if conflict_result.has_conflicts:
                conflict_resolution_result = await self._handle_conflicts(
                    conflict_result.conflicts, 
                    sync_request.conflict_resolution,
                    sync_request.initiated_by
                )
                
                if not conflict_resolution_result['success']:
                    result.errors.append(f"Conflict resolution failed: {conflict_resolution_result['error']}")
                    return await self._complete_sync_operation(operation_id, result, sync_operation)
                
                result.conflicts_resolved = conflict_resolution_result['resolved_count']
            
            # Execute sync based on direction
            if sync_request.direction == SyncDirection.GUI_TO_GITHUB:
                sync_result = await self._execute_gui_to_github_sync(sync_request, operation_id)
            elif sync_request.direction == SyncDirection.GITHUB_TO_GUI:
                sync_result = await self._execute_github_to_gui_sync(sync_request, operation_id)
            elif sync_request.direction == SyncDirection.BIDIRECTIONAL:
                sync_result = await self._execute_bidirectional_sync(sync_request, operation_id)
            else:
                result.errors.append(f"Unsupported sync direction: {sync_request.direction}")
                return await self._complete_sync_operation(operation_id, result, sync_operation)
            
            # Merge sync results
            result = self._merge_sync_results(result, sync_result)
            
            # Post-sync validation and cleanup
            post_sync_result = await self._post_sync_validation(sync_request, result)
            if not post_sync_result['valid']:
                result.warnings.extend(post_sync_result['warnings'])
            
            # Mark as successful if no errors
            result.success = len(result.errors) == 0
            
            self.logger.info(f"Sync operation {operation_id} completed: {'success' if result.success else 'failed'}")
            
        except Exception as e:
            self.logger.error(f"Sync operation {operation_id} failed with exception: {e}")
            result.errors.append(f"Sync operation failed: {str(e)}")
            result.success = False
        
        finally:
            # Complete operation
            result = await self._complete_sync_operation(operation_id, result, sync_operation)
        
        return result
    
    async def _execute_gui_to_github_sync(self, sync_request: SyncRequest, operation_id: str) -> Dict[str, Any]:
        """
        Execute GUI → GitHub synchronization workflow.
        
        This workflow:
        1. Identifies resources with draft_spec changes
        2. Generates YAML files from draft specifications
        3. Creates/updates files in GitHub repository
        4. Updates desired_spec to match committed changes
        5. Triggers drift detection against actual_spec
        """
        self.logger.info(f"Executing GUI → GitHub sync for operation {operation_id}")
        self._active_operations[operation_id]['status'] = 'gui_to_github_sync'
        
        result = {
            'success': False,
            'resources_processed': 0,
            'resources_created': 0,
            'resources_updated': 0,
            'resources_deleted': 0,
            'files_created': 0,
            'files_updated': 0,
            'files_deleted': 0,
            'commit_sha': None,
            'pull_request_url': None,
            'errors': [],
            'warnings': []
        }
        
        try:
            # Get resources that need sync (have draft changes)
            resources_to_sync = await self._get_resources_needing_gui_sync(sync_request)
            
            if not resources_to_sync:
                result['success'] = True
                result['warnings'].append("No resources require GUI → GitHub sync")
                return result
            
            result['resources_processed'] = len(resources_to_sync)
            
            # Create branch for changes if PR requested
            branch_name = None
            if sync_request.create_pr:
                branch_name = f"hnp-sync-{operation_id}"
                branch_result = await self.github_client.create_branch(branch_name)
                if not branch_result['success']:
                    result['errors'].append(f"Failed to create branch: {branch_result['error']}")
                    return result
            
            # Process each resource
            file_operations = []
            for resource in resources_to_sync:
                try:
                    operation_result = await self._sync_resource_to_github(
                        resource, 
                        branch_name,
                        sync_request.force_sync
                    )
                    
                    if operation_result['success']:
                        if operation_result['operation'] == 'create':
                            result['resources_created'] += 1
                            result['files_created'] += 1
                        elif operation_result['operation'] == 'update':
                            result['resources_updated'] += 1
                            result['files_updated'] += 1
                        elif operation_result['operation'] == 'delete':
                            result['resources_deleted'] += 1
                            result['files_deleted'] += 1
                        
                        file_operations.append(operation_result)
                    else:
                        result['errors'].append(
                            f"Failed to sync {resource.kind}/{resource.name}: {operation_result['error']}"
                        )
                        
                except Exception as e:
                    result['errors'].append(f"Error syncing {resource.kind}/{resource.name}: {str(e)}")
            
            # Create commit with all changes
            if file_operations:
                commit_message = self._generate_commit_message(
                    result['resources_created'],
                    result['resources_updated'], 
                    result['resources_deleted'],
                    self.fabric.name
                )
                
                commit_result = await self.github_client.commit_changes(
                    message=commit_message,
                    branch=branch_name
                )
                
                if commit_result['success']:
                    result['commit_sha'] = commit_result['commit_sha']
                    
                    # Create PR if requested
                    if sync_request.create_pr and branch_name:
                        pr_result = await self.github_client.create_pull_request(
                            title=f"HNP Sync: {commit_message}",
                            body=self._generate_pr_body(file_operations, sync_request),
                            head_branch=branch_name,
                            base_branch=self.fabric.git_repository.default_branch
                        )
                        
                        if pr_result['success']:
                            result['pull_request_url'] = pr_result['pull_request_url']
                        else:
                            result['warnings'].append(f"Failed to create PR: {pr_result['error']}")
                else:
                    result['errors'].append(f"Failed to commit changes: {commit_result['error']}")
                    return result
            
            # Update resource states after successful sync
            await self._update_resource_states_after_gui_sync(resources_to_sync, result['commit_sha'])
            
            result['success'] = len(result['errors']) == 0
            
        except Exception as e:
            result['errors'].append(f"GUI → GitHub sync failed: {str(e)}")
        
        return result
    
    async def _execute_github_to_gui_sync(self, sync_request: SyncRequest, operation_id: str) -> Dict[str, Any]:
        """
        Execute GitHub → GUI synchronization workflow.
        
        This workflow:
        1. Detects changes in GitHub repository since last sync
        2. Downloads and parses changed YAML files
        3. Updates desired_spec for affected resources
        4. Creates new resources for new files
        5. Marks orphaned resources for cleanup
        6. Triggers drift detection
        """
        self.logger.info(f"Executing GitHub → GUI sync for operation {operation_id}")
        self._active_operations[operation_id]['status'] = 'github_to_gui_sync'
        
        result = {
            'success': False,
            'resources_processed': 0,
            'resources_created': 0,
            'resources_updated': 0,
            'resources_deleted': 0,
            'files_processed': 0,
            'errors': [],
            'warnings': []
        }
        
        try:
            # Detect changes in GitHub since last sync
            last_sync_time = self.fabric.last_git_sync or datetime.min.replace(tzinfo=timezone.utc)
            change_detection_result = await self.github_client.detect_changes(since=last_sync_time)
            
            if not change_detection_result['success']:
                result['errors'].append(f"Failed to detect GitHub changes: {change_detection_result['error']}")
                return result
            
            changed_files = change_detection_result['changed_files']
            if not changed_files:
                result['success'] = True
                result['warnings'].append("No changes detected in GitHub repository")
                return result
            
            result['files_processed'] = len(changed_files)
            
            # Filter for files in our gitops directory
            relevant_files = [
                f for f in changed_files 
                if f['path'].startswith(self.fabric.gitops_directory) and
                   f['path'].endswith(('.yaml', '.yml'))
            ]
            
            # Process each changed file
            for file_change in relevant_files:
                try:
                    process_result = await self._process_github_file_change(
                        file_change,
                        sync_request.force_sync
                    )
                    
                    if process_result['success']:
                        if process_result['operation'] == 'create':
                            result['resources_created'] += 1
                        elif process_result['operation'] == 'update':
                            result['resources_updated'] += 1
                        elif process_result['operation'] == 'delete':
                            result['resources_deleted'] += 1
                        
                        result['resources_processed'] += 1
                    else:
                        result['errors'].append(
                            f"Failed to process file {file_change['path']}: {process_result['error']}"
                        )
                        
                except Exception as e:
                    result['errors'].append(f"Error processing file {file_change['path']}: {str(e)}")
            
            # Update fabric sync timestamp
            self.fabric.last_git_sync = timezone.now()
            self.fabric.save(update_fields=['last_git_sync'])
            
            # Trigger drift detection for updated resources
            await self._trigger_drift_detection_after_github_sync()
            
            result['success'] = len(result['errors']) == 0
            
        except Exception as e:
            result['errors'].append(f"GitHub → GUI sync failed: {str(e)}")
        
        return result
    
    async def _execute_bidirectional_sync(self, sync_request: SyncRequest, operation_id: str) -> Dict[str, Any]:
        """
        Execute bidirectional synchronization workflow.
        
        This workflow:
        1. Executes GitHub → GUI sync first (to get latest remote state)
        2. Detects any new conflicts after GitHub sync
        3. Executes GUI → GitHub sync for local changes
        4. Performs final conflict resolution if needed
        """
        self.logger.info(f"Executing bidirectional sync for operation {operation_id}")
        self._active_operations[operation_id]['status'] = 'bidirectional_sync'
        
        result = {
            'success': False,
            'resources_processed': 0,
            'resources_created': 0,
            'resources_updated': 0,
            'resources_deleted': 0,
            'github_to_gui': {},
            'gui_to_github': {},
            'errors': [],
            'warnings': []
        }
        
        try:
            # Phase 1: GitHub → GUI sync
            github_sync_request = SyncRequest(
                fabric=sync_request.fabric,
                direction=SyncDirection.GITHUB_TO_GUI,
                resource_filters=sync_request.resource_filters,
                force_sync=sync_request.force_sync,
                conflict_resolution=sync_request.conflict_resolution,
                initiated_by=sync_request.initiated_by
            )
            
            github_result = await self._execute_github_to_gui_sync(github_sync_request, operation_id)
            result['github_to_gui'] = github_result
            
            if not github_result['success']:
                result['errors'].extend(github_result['errors'])
                result['warnings'].extend(github_result['warnings'])
                return result
            
            # Detect conflicts after GitHub sync
            post_github_conflicts = await self._detect_conflicts(sync_request)
            if post_github_conflicts.has_conflicts:
                conflict_resolution_result = await self._handle_conflicts(
                    post_github_conflicts.conflicts,
                    sync_request.conflict_resolution,
                    sync_request.initiated_by
                )
                
                if not conflict_resolution_result['success']:
                    result['errors'].append(f"Post-GitHub conflict resolution failed: {conflict_resolution_result['error']}")
                    return result
            
            # Phase 2: GUI → GitHub sync
            gui_sync_request = SyncRequest(
                fabric=sync_request.fabric,
                direction=SyncDirection.GUI_TO_GITHUB,
                resource_filters=sync_request.resource_filters,
                force_sync=sync_request.force_sync,
                create_pr=sync_request.create_pr,
                conflict_resolution=sync_request.conflict_resolution,
                initiated_by=sync_request.initiated_by
            )
            
            gui_result = await self._execute_gui_to_github_sync(gui_sync_request, operation_id)
            result['gui_to_github'] = gui_result
            
            if not gui_result['success']:
                result['errors'].extend(gui_result['errors'])
                result['warnings'].extend(gui_result['warnings'])
                return result
            
            # Aggregate results
            result['resources_processed'] = github_result['resources_processed'] + gui_result['resources_processed']
            result['resources_created'] = github_result['resources_created'] + gui_result['resources_created']
            result['resources_updated'] = github_result['resources_updated'] + gui_result['resources_updated']
            result['resources_deleted'] = github_result['resources_deleted'] + gui_result['resources_deleted']
            
            result['success'] = True
            
        except Exception as e:
            result['errors'].append(f"Bidirectional sync failed: {str(e)}")
        
        return result
    
    async def _detect_conflicts(self, sync_request: SyncRequest) -> ConflictDetectionResult:
        """
        Detect conflicts between GUI state and GitHub state.
        
        Returns:
            ConflictDetectionResult with detected conflicts
        """
        start_time = datetime.now()
        conflicts = []
        
        try:
            # Get all resources that might have conflicts
            resources = await self._get_resources_for_conflict_detection(sync_request)
            
            for resource in resources:
                resource_conflicts = await self.conflict_detector.detect_resource_conflicts(resource)
                conflicts.extend(resource_conflicts)
            
            detection_time = (datetime.now() - start_time).total_seconds()
            
            return ConflictDetectionResult(
                has_conflicts=len(conflicts) > 0,
                conflicts=conflicts,
                total_resources_checked=len(resources),
                detection_time_seconds=detection_time
            )
            
        except Exception as e:
            self.logger.error(f"Conflict detection failed: {e}")
            return ConflictDetectionResult(
                has_conflicts=False,
                conflicts=[],
                total_resources_checked=0,
                detection_time_seconds=(datetime.now() - start_time).total_seconds()
            )
    
    def get_operation_status(self, operation_id: str) -> Optional[Dict[str, Any]]:
        """
        Get status of a specific sync operation.
        
        Args:
            operation_id: ID of the sync operation
            
        Returns:
            Operation status dictionary or None if not found
        """
        if operation_id in self._active_operations:
            operation = self._active_operations[operation_id]
            return {
                'operation_id': operation_id,
                'status': operation['status'],
                'request': {
                    'direction': operation['request'].direction.value,
                    'fabric': operation['request'].fabric.name,
                    'initiated_by': operation['request'].initiated_by.username if operation['request'].initiated_by else None
                },
                'progress': operation.get('progress', {}),
                'started_at': operation['result'].started_at.isoformat(),
                'completed_at': operation['result'].completed_at.isoformat() if operation['result'].completed_at else None
            }
        
        # Check operation history
        for historical_op in self._operation_history:
            if historical_op.operation_id == operation_id:
                return historical_op.to_dict()
        
        return None
    
    def list_active_operations(self) -> List[Dict[str, Any]]:
        """Get list of all active sync operations"""
        return [
            {
                'operation_id': op_id,
                'status': op_data['status'],
                'fabric': op_data['request'].fabric.name,
                'direction': op_data['request'].direction.value,
                'started_at': op_data['result'].started_at.isoformat()
            }
            for op_id, op_data in self._active_operations.items()
        ]
    
    async def cancel_operation(self, operation_id: str) -> Dict[str, Any]:
        """
        Cancel an active sync operation.
        
        Args:
            operation_id: ID of the operation to cancel
            
        Returns:
            Cancellation result
        """
        if operation_id not in self._active_operations:
            return {'success': False, 'error': 'Operation not found or already completed'}
        
        try:
            operation = self._active_operations[operation_id]
            operation['status'] = 'cancelling'
            
            # Perform cleanup based on current status
            cleanup_result = await self._cleanup_cancelled_operation(operation_id, operation)
            
            # Mark as cancelled
            operation['result'].success = False
            operation['result'].completed_at = datetime.now()
            operation['result'].errors.append(f"Operation cancelled by user")
            
            # Move to history
            self._operation_history.append(operation['result'])
            del self._active_operations[operation_id]
            
            return {'success': True, 'message': f'Operation {operation_id} cancelled successfully'}
            
        except Exception as e:
            return {'success': False, 'error': f'Failed to cancel operation: {str(e)}'}
    
    # Private helper methods continue...
    # [Additional helper methods would be implemented here]
```

### 2. ConflictDetector

**Purpose**: Specialized component for detecting conflicts between GUI and GitHub states

**File Location**: `netbox_hedgehog/utils/conflict_detector.py`

**Class Definition**:
```python
from typing import List, Dict, Any, Optional
from datetime import datetime
import json
import logging

class ConflictDetector:
    """
    Detects conflicts between HNP GUI state and GitHub repository state.
    
    Conflict Types:
    - Concurrent modifications (both GUI and GitHub changed)
    - Schema conflicts (invalid YAML structure)
    - Permission conflicts (insufficient GitHub access)
    - Dependency conflicts (resource dependency violations)
    """
    
    CONFLICT_TYPES = {
        'CONCURRENT_MODIFICATION': 'concurrent_modification',
        'SCHEMA_MISMATCH': 'schema_mismatch',
        'PERMISSION_DENIED': 'permission_denied',
        'DEPENDENCY_VIOLATION': 'dependency_violation',
        'FILE_CORRUPTION': 'file_corruption',
        'MISSING_RESOURCE': 'missing_resource'
    }
    
    def __init__(self, fabric: 'HedgehogFabric'):
        self.fabric = fabric
        self.logger = logging.getLogger(__name__)
    
    async def detect_resource_conflicts(self, resource: 'HedgehogResource') -> List[ResourceConflict]:
        """
        Detect conflicts for a specific resource.
        
        Args:
            resource: HedgehogResource to check for conflicts
            
        Returns:
            List of ResourceConflict objects
        """
        conflicts = []
        
        try:
            # Check for concurrent modifications
            concurrent_conflict = await self._check_concurrent_modification(resource)
            if concurrent_conflict:
                conflicts.append(concurrent_conflict)
            
            # Check for schema conflicts
            schema_conflict = await self._check_schema_conflicts(resource)
            if schema_conflict:
                conflicts.append(schema_conflict)
            
            # Check for dependency conflicts
            dependency_conflicts = await self._check_dependency_conflicts(resource)
            conflicts.extend(dependency_conflicts)
            
            # Check for file integrity
            integrity_conflict = await self._check_file_integrity(resource)
            if integrity_conflict:
                conflicts.append(integrity_conflict)
                
        except Exception as e:
            self.logger.error(f"Conflict detection failed for {resource.name}: {e}")
            # Create error conflict
            conflicts.append(ResourceConflict(
                resource_id=resource.id,
                resource_name=resource.name,
                resource_kind=resource.kind,
                conflict_type='detection_error',
                detected_at=datetime.now(),
                severity='high',
                resolution_options=['manual_review'],
                auto_resolvable=False
            ))
        
        return conflicts
    
    async def _check_concurrent_modification(self, resource: 'HedgehogResource') -> Optional[ResourceConflict]:
        """Check for concurrent modifications between GUI and GitHub"""
        
        # Get timestamps
        gui_modified = resource.draft_updated or resource.last_updated
        github_modified = await self._get_github_file_modification_time(resource)
        
        if not gui_modified or not github_modified:
            return None
        
        # Check if both were modified after last sync
        last_sync = resource.last_file_sync or datetime.min.replace(tzinfo=gui_modified.tzinfo)
        
        gui_changed_since_sync = gui_modified > last_sync
        github_changed_since_sync = github_modified > last_sync
        
        if gui_changed_since_sync and github_changed_since_sync:
            # Detect specific conflicting fields
            conflicting_fields = await self._identify_conflicting_fields(resource)
            
            return ResourceConflict(
                resource_id=resource.id,
                resource_name=resource.name,
                resource_kind=resource.kind,
                conflict_type=self.CONFLICT_TYPES['CONCURRENT_MODIFICATION'],
                detected_at=datetime.now(),
                gui_modification_time=gui_modified,
                github_modification_time=github_modified,
                conflicting_fields=conflicting_fields,
                resolution_options=['gui_wins', 'github_wins', 'merge', 'manual'],
                auto_resolvable=len(conflicting_fields) <= 3,  # Auto-resolve simple conflicts
                severity='high' if len(conflicting_fields) > 5 else 'medium'
            )
        
        return None
    
    async def _check_schema_conflicts(self, resource: 'HedgehogResource') -> Optional[ResourceConflict]:
        """Check for YAML schema validation conflicts"""
        
        try:
            # Get current GitHub file content
            github_content = await self._get_github_file_content(resource)
            if not github_content:
                return None
            
            # Validate YAML structure
            import yaml
            parsed_content = yaml.safe_load(github_content)
            
            # Validate against expected schema
            validation_errors = await self._validate_resource_schema(parsed_content, resource.kind)
            
            if validation_errors:
                return ResourceConflict(
                    resource_id=resource.id,
                    resource_name=resource.name,
                    resource_kind=resource.kind,
                    conflict_type=self.CONFLICT_TYPES['SCHEMA_MISMATCH'],
                    detected_at=datetime.now(),
                    github_values={'validation_errors': validation_errors},
                    resolution_options=['fix_schema', 'regenerate_file', 'manual_fix'],
                    auto_resolvable=False,
                    severity='critical'
                )
                
        except yaml.YAMLError:
            return ResourceConflict(
                resource_id=resource.id,
                resource_name=resource.name,
                resource_kind=resource.kind,
                conflict_type=self.CONFLICT_TYPES['FILE_CORRUPTION'],
                detected_at=datetime.now(),
                resolution_options=['regenerate_file', 'manual_fix'],
                auto_resolvable=True,
                severity='high'
            )
        except Exception as e:
            self.logger.error(f"Schema validation failed for {resource.name}: {e}")
        
        return None
    
    async def _identify_conflicting_fields(self, resource: 'HedgehogResource') -> List[str]:
        """Identify specific fields that have conflicts"""
        conflicting_fields = []
        
        try:
            # Get current specs
            draft_spec = resource.draft_spec or {}
            github_content = await self._get_github_file_content(resource)
            
            if github_content:
                import yaml
                github_spec = yaml.safe_load(github_content).get('spec', {})
                
                # Compare field by field
                conflicting_fields = self._compare_specs_for_conflicts(draft_spec, github_spec)
                
        except Exception as e:
            self.logger.error(f"Field comparison failed for {resource.name}: {e}")
        
        return conflicting_fields
    
    def _compare_specs_for_conflicts(self, spec1: Dict[str, Any], spec2: Dict[str, Any], prefix: str = '') -> List[str]:
        """Recursively compare specs to find conflicting fields"""
        conflicts = []
        all_keys = set(spec1.keys()) | set(spec2.keys())
        
        for key in all_keys:
            field_path = f"{prefix}.{key}" if prefix else key
            
            if key not in spec1:
                conflicts.append(f"{field_path} (only in GitHub)")
            elif key not in spec2:
                conflicts.append(f"{field_path} (only in GUI)")
            elif spec1[key] != spec2[key]:
                if isinstance(spec1[key], dict) and isinstance(spec2[key], dict):
                    # Recursively compare nested objects
                    nested_conflicts = self._compare_specs_for_conflicts(
                        spec1[key], spec2[key], field_path
                    )
                    conflicts.extend(nested_conflicts)
                else:
                    conflicts.append(field_path)
        
        return conflicts
```

### 3. FileToRecordMapper

**Purpose**: Manages mapping between GitOps files and HNP database records

**File Location**: `netbox_hedgehog/utils/file_to_record_mapper.py`

**Class Definition**:
```python
from typing import Dict, List, Any, Optional, Tuple
import hashlib
import json
from pathlib import Path
from django.db import transaction
from django.utils import timezone

class FileToRecordMapper:
    """
    Manages mapping between GitOps files and HNP database records.
    
    Responsibilities:
    - Track file-to-record relationships
    - Generate file paths from resources
    - Update file hashes and metadata
    - Handle file rename and move operations
    """
    
    def __init__(self, fabric: 'HedgehogFabric'):
        self.fabric = fabric
        self.logger = logging.getLogger(__name__)
    
    def generate_file_path(self, resource: 'HedgehogResource') -> str:
        """
        Generate standardized file path for a resource.
        
        Args:
            resource: Resource to generate path for
            
        Returns:
            Relative file path within managed directory
        """
        # Map resource kind to directory
        kind_to_dir = {
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
        
        resource_dir = kind_to_dir.get(resource.kind, 'unknown')
        
        # Generate filename from resource name (ensure valid filename)
        safe_name = self._sanitize_filename(resource.name)
        filename = f"{safe_name}.yaml"
        
        return f"managed/{resource_dir}/{filename}"
    
    def calculate_file_hash(self, content: str) -> str:
        """Calculate SHA-256 hash of file content"""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    async def update_file_mapping(
        self, 
        resource: 'HedgehogResource', 
        file_path: str, 
        content: str
    ) -> None:
        """
        Update file mapping metadata for a resource.
        
        Args:
            resource: Resource to update mapping for
            file_path: Path to the file
            content: File content for hash calculation
        """
        with transaction.atomic():
            resource.managed_file_path = file_path
            resource.file_hash = self.calculate_file_hash(content)
            resource.last_file_sync = timezone.now()
            resource.save(update_fields=[
                'managed_file_path', 
                'file_hash', 
                'last_file_sync'
            ])
    
    async def detect_file_changes(self) -> List[Dict[str, Any]]:
        """
        Detect changes in file mappings by comparing current hashes.
        
        Returns:
            List of changes detected
        """
        changes = []
        
        # Get all resources with file mappings
        resources = self.fabric.gitops_resources.filter(
            managed_file_path__isnull=False
        )
        
        for resource in resources:
            try:
                # Get current file content from GitHub
                current_content = await self._get_file_content_from_github(
                    resource.managed_file_path
                )
                
                if current_content is None:
                    changes.append({
                        'resource_id': resource.id,
                        'resource_name': resource.name,
                        'change_type': 'file_deleted',
                        'file_path': resource.managed_file_path
                    })
                    continue
                
                # Compare hashes
                current_hash = self.calculate_file_hash(current_content)
                if current_hash != resource.file_hash:
                    changes.append({
                        'resource_id': resource.id,
                        'resource_name': resource.name,
                        'change_type': 'file_modified',
                        'file_path': resource.managed_file_path,
                        'old_hash': resource.file_hash,
                        'new_hash': current_hash
                    })
                    
            except Exception as e:
                self.logger.error(f"Error checking file changes for {resource.name}: {e}")
                changes.append({
                    'resource_id': resource.id,
                    'resource_name': resource.name,
                    'change_type': 'check_failed',
                    'error': str(e)
                })
        
        return changes
    
    def _sanitize_filename(self, name: str) -> str:
        """Sanitize resource name for use as filename"""
        import re
        # Replace invalid characters with hyphens
        sanitized = re.sub(r'[^\w\-_.]', '-', name)
        # Remove multiple consecutive hyphens
        sanitized = re.sub(r'-+', '-', sanitized)
        # Remove leading/trailing hyphens
        sanitized = sanitized.strip('-')
        return sanitized or 'unnamed'
```

## Integration Points

### 1. HedgehogFabric Model Extensions

```python
# Add to HedgehogFabric model
async def sync_bidirectional(
    self, 
    direction: str = 'bidirectional',
    create_pr: bool = False,
    conflict_resolution: str = 'user_guided',
    initiated_by: 'User' = None
) -> SyncResult:
    """Trigger bidirectional synchronization"""
    from .utils.bidirectional_sync_orchestrator import (
        BidirectionalSyncOrchestrator, 
        SyncRequest, 
        SyncDirection,
        ConflictResolutionStrategy
    )
    
    orchestrator = BidirectionalSyncOrchestrator(self)
    
    sync_request = SyncRequest(
        fabric=self,
        direction=SyncDirection(direction),
        create_pr=create_pr,
        conflict_resolution=ConflictResolutionStrategy(conflict_resolution),
        initiated_by=initiated_by
    )
    
    return await orchestrator.sync(sync_request)
```

### 2. API Views Integration

**File Location**: `netbox_hedgehog/api/views/sync_views.py`

```python
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from netbox.api.viewsets import NetBoxModelViewSet

class BidirectionalSyncViewSet(NetBoxModelViewSet):
    """API views for bidirectional synchronization"""
    
    @action(detail=True, methods=['post'])
    async def sync(self, request, pk=None):
        """Trigger bidirectional synchronization"""
        fabric = self.get_object()
        
        # Extract sync parameters
        direction = request.data.get('direction', 'bidirectional')
        force = request.data.get('force', False)
        create_pr = request.data.get('create_pr', False)
        conflict_resolution = request.data.get('conflict_resolution', 'user_guided')
        
        # Perform sync
        result = await fabric.sync_bidirectional(
            direction=direction,
            create_pr=create_pr,
            conflict_resolution=conflict_resolution,
            initiated_by=request.user
        )
        
        return Response(
            result.to_dict(),
            status=status.HTTP_200_OK if result.success else status.HTTP_400_BAD_REQUEST
        )
    
    @action(detail=True, methods=['get'])
    def sync_status(self, request, pk=None):
        """Get sync operation status"""
        fabric = self.get_object()
        operation_id = request.query_params.get('operation_id')
        
        orchestrator = BidirectionalSyncOrchestrator(fabric)
        
        if operation_id:
            status_info = orchestrator.get_operation_status(operation_id)
            if not status_info:
                return Response(
                    {'error': 'Operation not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            status_info = orchestrator.list_active_operations()
        
        return Response(status_info, status=status.HTTP_200_OK)
```

## Testing Specifications

### 1. Unit Tests

**File Location**: `netbox_hedgehog/tests/test_bidirectional_sync_orchestrator.py`

```python
import asyncio
import unittest
from unittest.mock import Mock, patch, AsyncMock
from netbox_hedgehog.utils.bidirectional_sync_orchestrator import (
    BidirectionalSyncOrchestrator,
    SyncRequest,
    SyncDirection,
    ConflictResolutionStrategy
)

class TestBidirectionalSyncOrchestrator(unittest.TestCase):
    
    def setUp(self):
        self.fabric = Mock()
        self.fabric.name = 'test-fabric'
        self.fabric.git_repository = Mock()
        self.fabric.git_repository.connection_status = 'connected'
        self.fabric.gitops_directory = 'gitops/test-fabric'
        self.fabric.gitops_initialized = True
        
    def test_orchestrator_initialization(self):
        """Test orchestrator initializes correctly"""
        orchestrator = BidirectionalSyncOrchestrator(self.fabric)
        self.assertEqual(orchestrator.fabric, self.fabric)
        self.assertEqual(len(orchestrator._active_operations), 0)
    
    @patch('netbox_hedgehog.utils.bidirectional_sync_orchestrator.asyncio')
    async def test_gui_to_github_sync(self):
        """Test GUI → GitHub sync workflow"""
        orchestrator = BidirectionalSyncOrchestrator(self.fabric)
        
        sync_request = SyncRequest(
            fabric=self.fabric,
            direction=SyncDirection.GUI_TO_GITHUB,
            force_sync=False
        )
        
        with patch.object(orchestrator, '_get_resources_needing_gui_sync') as mock_resources, \
             patch.object(orchestrator, '_sync_resource_to_github') as mock_sync, \
             patch.object(orchestrator, 'github_client') as mock_client:
            
            mock_resources.return_value = [Mock(kind='VPC', name='test-vpc')]
            mock_sync.return_value = {'success': True, 'operation': 'create'}
            mock_client.commit_changes.return_value = {'success': True, 'commit_sha': 'abc123'}
            
            result = await orchestrator._execute_gui_to_github_sync(sync_request, 'test-op')
            
            self.assertTrue(result['success'])
            self.assertEqual(result['resources_created'], 1)
```

### 2. Integration Tests

**File Location**: `netbox_hedgehog/tests/integration/test_bidirectional_sync_integration.py`

```python
import asyncio
from django.test import TestCase
from netbox_hedgehog.models import HedgehogFabric, GitRepository, HedgehogResource
from netbox_hedgehog.utils.bidirectional_sync_orchestrator import BidirectionalSyncOrchestrator

class BidirectionalSyncIntegrationTest(TestCase):
    
    def setUp(self):
        # Create test setup
        self.git_repo = GitRepository.objects.create(
            name='Test Repository',
            url='https://github.com/test/repo.git'
        )
        
        self.fabric = HedgehogFabric.objects.create(
            name='test-fabric',
            git_repository=self.git_repo,
            gitops_directory='gitops/test-fabric',
            gitops_initialized=True
        )
    
    async def test_end_to_end_sync_workflow(self):
        """Test complete bidirectional sync workflow"""
        orchestrator = BidirectionalSyncOrchestrator(self.fabric)
        
        # Create test resource
        resource = HedgehogResource.objects.create(
            fabric=self.fabric,
            name='test-vpc',
            kind='VPC',
            draft_spec={'name': 'test-vpc', 'subnets': ['10.0.0.0/24']}
        )
        
        # Mock external dependencies
        with patch.object(orchestrator, 'github_client') as mock_client, \
             patch.object(orchestrator, 'directory_manager') as mock_dir:
            
            mock_client.detect_changes.return_value = {'success': True, 'changed_files': []}
            mock_client.commit_changes.return_value = {'success': True, 'commit_sha': 'test123'}
            
            sync_request = SyncRequest(fabric=self.fabric, direction=SyncDirection.BIDIRECTIONAL)
            result = await orchestrator.sync(sync_request)
            
            self.assertTrue(result.success)
            self.assertGreater(result.resources_processed, 0)
```

This component specification provides a comprehensive foundation for implementing the Bidirectional Sync Engine as the core orchestrator of the GitOps synchronization system.