# Database Schema Enhancements for Bidirectional Sync

**Document Type**: Database Design Specification  
**Component**: Database Schema Enhancements  
**Project**: HNP GitOps Bidirectional Synchronization  
**Author**: Backend Technical Specialist  
**Date**: July 30, 2025  
**Version**: 1.0

## Overview

This document specifies the database schema enhancements required to support GitOps bidirectional synchronization functionality. The enhancements build upon existing HNP models while adding new capabilities for file-to-record mapping, sync operation tracking, and conflict management.

## Enhanced Model Specifications

### 1. HedgehogResource Model Extensions

**Purpose**: Extend existing three-state model with bidirectional sync capabilities

**File Location**: `netbox_hedgehog/models/gitops.py`

**Enhanced Model Definition**:
```python
from django.db import models
from django.utils import timezone
from netbox.models import NetBoxModel
import json

class HedgehogResource(NetBoxModel):
    """
    Enhanced resource model with bidirectional synchronization support.
    
    Extends existing three-state model (desired_spec, draft_spec, actual_spec)
    with file-to-record mapping and conflict management capabilities.
    """
    
    # === EXISTING FIELDS (maintained for backward compatibility) ===
    fabric = models.ForeignKey(
        'netbox_hedgehog.HedgehogFabric',
        on_delete=models.CASCADE,
        related_name='gitops_resources'
    )
    
    name = models.CharField(max_length=253)
    namespace = models.CharField(max_length=253, default='default')
    kind = models.CharField(max_length=50)
    api_version = models.CharField(max_length=100, default='unknown/v1')
    
    # Three-state model (EXISTING)
    desired_spec = models.JSONField(null=True, blank=True)
    desired_commit = models.CharField(max_length=40, blank=True)
    desired_file_path = models.CharField(max_length=500, blank=True)
    desired_updated = models.DateTimeField(null=True, blank=True)
    
    draft_spec = models.JSONField(null=True, blank=True)
    draft_updated = models.DateTimeField(null=True, blank=True)
    draft_updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='draft_resources'
    )
    
    actual_spec = models.JSONField(null=True, blank=True)
    actual_status = models.JSONField(null=True, blank=True)
    actual_resource_version = models.CharField(max_length=50, blank=True)
    actual_updated = models.DateTimeField(null=True, blank=True)
    
    # === NEW BIDIRECTIONAL SYNC FIELDS ===
    
    # File-to-Record Mapping
    managed_file_path = models.CharField(
        max_length=500,
        blank=True,
        help_text="Path to managed file in GitOps repository (relative to gitops_directory)"
    )
    
    file_hash = models.CharField(
        max_length=64,
        blank=True,
        help_text="SHA-256 hash of current managed file content"
    )
    
    last_file_sync = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of last file synchronization"
    )
    
    file_size_bytes = models.PositiveIntegerField(
        default=0,
        help_text="Size of managed file in bytes"
    )
    
    # Synchronization Control
    sync_direction = models.CharField(
        max_length=20,
        choices=[
            ('gui_to_git', 'GUI to Git Only'),
            ('git_to_gui', 'Git to GUI Only'),
            ('bidirectional', 'Bidirectional'),
            ('disabled', 'Sync Disabled'),
            ('manual_only', 'Manual Sync Only')
        ],
        default='bidirectional',
        help_text="Synchronization direction preference for this resource"
    )
    
    auto_sync_enabled = models.BooleanField(
        default=True,
        help_text="Whether automatic synchronization is enabled for this resource"
    )
    
    sync_priority = models.PositiveSmallIntegerField(
        default=100,
        help_text="Sync priority (lower numbers = higher priority)"
    )
    
    # Conflict Management
    conflict_status = models.CharField(
        max_length=20,
        choices=[
            ('none', 'No Conflicts'),
            ('detected', 'Conflict Detected'),
            ('resolving', 'Resolution in Progress'),
            ('resolved', 'Resolved'),
            ('requires_manual', 'Requires Manual Resolution'),
            ('escalated', 'Escalated for Review')
        ],
        default='none',
        help_text="Current conflict status for this resource"
    )
    
    conflict_details = models.JSONField(
        default=dict,
        blank=True,
        help_text="Detailed conflict information and resolution history"
    )
    
    conflict_detected_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When conflict was first detected"
    )
    
    conflict_resolution_attempts = models.PositiveIntegerField(
        default=0,
        help_text="Number of automatic resolution attempts"
    )
    
    # External Modifications Tracking
    external_modifications = models.JSONField(
        default=list,
        blank=True,
        help_text="Log of external modifications detected from GitHub"
    )
    
    last_external_check = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of last external modification check"
    )
    
    external_modification_count = models.PositiveIntegerField(
        default=0,
        help_text="Total number of external modifications detected"
    )
    
    # Sync Metadata and Performance
    sync_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional sync-related metadata and configuration"
    )
    
    last_sync_duration_ms = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Duration of last sync operation in milliseconds"
    )
    
    sync_error_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of consecutive sync errors"
    )
    
    last_sync_error = models.TextField(
        blank=True,
        help_text="Last sync error message"
    )
    
    last_sync_error_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When last sync error occurred"
    )
    
    # GitHub Integration Metadata
    github_branch = models.CharField(
        max_length=255,
        blank=True,
        help_text="GitHub branch where this resource's file is located"
    )
    
    github_commit_sha = models.CharField(
        max_length=40,
        blank=True,
        help_text="GitHub commit SHA of last known file state"
    )
    
    github_pull_request_url = models.URLField(
        blank=True,
        help_text="URL of pull request if changes are pending review"
    )
    
    github_file_url = models.URLField(
        blank=True,
        help_text="Direct URL to file in GitHub repository"
    )
    
    class Meta:
        verbose_name = "Hedgehog Resource"
        verbose_name_plural = "Hedgehog Resources"
        unique_together = [['fabric', 'namespace', 'name', 'kind']]
        ordering = ['fabric', 'namespace', 'kind', 'name']
        indexes = [
            # Existing indexes (maintained)
            models.Index(fields=['fabric', 'resource_state']),
            models.Index(fields=['fabric', 'kind']),
            models.Index(fields=['desired_commit']),
            models.Index(fields=['actual_updated']),
            
            # New bidirectional sync indexes
            models.Index(fields=['fabric', 'conflict_status']),
            models.Index(fields=['fabric', 'sync_direction']),
            models.Index(fields=['last_file_sync', 'auto_sync_enabled']),
            models.Index(fields=['conflict_detected_at', 'conflict_status']),
            models.Index(fields=['managed_file_path'], name='hnp_resource_file_path_idx'),
            models.Index(fields=['file_hash'], name='hnp_resource_file_hash_idx'),
            models.Index(fields=['fabric', 'sync_priority', 'auto_sync_enabled']),
            models.Index(fields=['external_modification_count', 'last_external_check']),
            models.Index(fields=['sync_error_count', 'last_sync_error_at']),
        ]
    
    # === NEW METHODS FOR BIDIRECTIONAL SYNC ===
    
    def update_file_mapping(self, file_path: str, content: str, commit_sha: str = None) -> None:
        """Update file mapping information after successful file operation"""
        import hashlib
        
        self.managed_file_path = file_path
        self.file_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
        self.file_size_bytes = len(content.encode('utf-8'))
        self.last_file_sync = timezone.now()
        
        if commit_sha:
            self.github_commit_sha = commit_sha
        
        # Clear sync errors on successful operation
        self.sync_error_count = 0
        self.last_sync_error = ''
        self.last_sync_error_at = None
        
        self.save(update_fields=[
            'managed_file_path', 'file_hash', 'file_size_bytes', 
            'last_file_sync', 'github_commit_sha', 'sync_error_count',
            'last_sync_error', 'last_sync_error_at'
        ])
    
    def record_sync_error(self, error_message: str) -> None:
        """Record a sync error for this resource"""
        self.sync_error_count += 1
        self.last_sync_error = error_message
        self.last_sync_error_at = timezone.now()
        
        # Disable auto-sync after too many consecutive errors
        if self.sync_error_count >= 5:
            self.auto_sync_enabled = False
        
        self.save(update_fields=[
            'sync_error_count', 'last_sync_error', 'last_sync_error_at', 'auto_sync_enabled'
        ])
    
    def record_external_modification(self, modification_details: dict) -> None:
        """Record an external modification detected from GitHub"""
        self.external_modifications.append({
            'timestamp': timezone.now().isoformat(),
            'details': modification_details
        })
        
        # Keep only last 10 modifications
        self.external_modifications = self.external_modifications[-10:]
        
        self.external_modification_count += 1
        self.last_external_check = timezone.now()
        
        self.save(update_fields=[
            'external_modifications', 'external_modification_count', 'last_external_check'
        ])
    
    def update_conflict_status(self, status: str, details: dict = None) -> None:
        """Update conflict status and details"""
        old_status = self.conflict_status
        self.conflict_status = status
        
        if details:
            self.conflict_details.update(details)
        
        if status == 'detected' and old_status == 'none':
            self.conflict_detected_at = timezone.now()
        elif status == 'resolved':
            self.conflict_detected_at = None
            self.conflict_resolution_attempts = 0
        elif status == 'resolving':
            self.conflict_resolution_attempts += 1
        
        self.save(update_fields=[
            'conflict_status', 'conflict_details', 'conflict_detected_at', 'conflict_resolution_attempts'
        ])
    
    def needs_sync_to_github(self) -> bool:
        """Check if resource needs to be synced to GitHub"""
        if not self.auto_sync_enabled or self.sync_direction in ['git_to_gui', 'disabled']:
            return False
        
        # Check if draft is newer than last file sync
        if self.draft_updated and self.last_file_sync:
            return self.draft_updated > self.last_file_sync
        
        # Check if draft exists but no file sync has occurred
        return bool(self.draft_spec and not self.last_file_sync)
    
    def needs_sync_from_github(self) -> bool:
        """Check if resource needs to be synced from GitHub"""
        if not self.auto_sync_enabled or self.sync_direction in ['gui_to_git', 'disabled']:
            return False
        
        # Check if external modifications are newer than desired state
        if self.external_modification_count > 0 and self.desired_updated:
            return self.last_external_check > self.desired_updated
        
        return False
    
    @property
    def has_pending_conflicts(self) -> bool:
        """Check if resource has unresolved conflicts"""
        return self.conflict_status in ['detected', 'resolving', 'requires_manual']
    
    @property
    def is_sync_healthy(self) -> bool:
        """Check if resource sync is in healthy state"""
        return (
            self.sync_error_count < 3 and
            not self.has_pending_conflicts and
            self.auto_sync_enabled
        )
    
    @property
    def sync_status_summary(self) -> dict:
        """Get comprehensive sync status summary"""
        return {
            'sync_direction': self.sync_direction,
            'auto_sync_enabled': self.auto_sync_enabled,
            'sync_healthy': self.is_sync_healthy,
            'needs_github_sync': self.needs_sync_to_github(),
            'needs_gui_sync': self.needs_sync_from_github(),
            'has_conflicts': self.has_pending_conflicts,
            'last_sync': self.last_file_sync.isoformat() if self.last_file_sync else None,
            'sync_errors': self.sync_error_count,
            'external_modifications': self.external_modification_count,
            'file_info': {
                'path': self.managed_file_path,
                'hash': self.file_hash,
                'size_bytes': self.file_size_bytes
            }
        }
```

### 2. New SyncOperation Model

**Purpose**: Track individual sync operations for audit, debugging, and monitoring

**Model Definition**:
```python
class SyncOperation(NetBoxModel):
    """
    Track individual synchronization operations for audit and monitoring.
    
    Provides detailed tracking of sync operations including performance metrics,
    error handling, and integration with external systems like GitHub.
    """
    
    # Operation Identification
    operation_id = models.CharField(
        max_length=50,
        unique=True,
        help_text="Unique identifier for this sync operation"
    )
    
    fabric = models.ForeignKey(
        'netbox_hedgehog.HedgehogFabric',
        on_delete=models.CASCADE,
        related_name='sync_operations',
        help_text="Fabric this sync operation belongs to"
    )
    
    # Operation Type and Configuration
    operation_type = models.CharField(
        max_length=30,
        choices=[
            ('gui_to_github', 'GUI to GitHub'),
            ('github_to_gui', 'GitHub to GUI'),
            ('bidirectional', 'Bidirectional'),
            ('directory_init', 'Directory Initialization'),
            ('conflict_resolution', 'Conflict Resolution'),
            ('file_ingestion', 'File Ingestion'),
            ('drift_detection', 'Drift Detection'),
            ('cleanup', 'Cleanup Operation')
        ],
        help_text="Type of synchronization operation"
    )
    
    sync_direction = models.CharField(
        max_length=20,
        choices=[
            ('gui_to_git', 'GUI to Git'),
            ('git_to_gui', 'Git to GUI'),
            ('bidirectional', 'Bidirectional'),
            ('internal', 'Internal Operation')
        ],
        help_text="Direction of data synchronization"
    )
    
    # Operation Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('initializing', 'Initializing'),
            ('in_progress', 'In Progress'),
            ('detecting_conflicts', 'Detecting Conflicts'),
            ('resolving_conflicts', 'Resolving Conflicts'),
            ('syncing_data', 'Syncing Data'),
            ('finalizing', 'Finalizing'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
            ('cancelled', 'Cancelled'),
            ('partially_completed', 'Partially Completed')
        ],
        default='pending',
        help_text="Current status of the operation"
    )
    
    # Timing Information
    started_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the operation was started"
    )
    
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the operation was completed"
    )
    
    estimated_duration_seconds = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Estimated duration in seconds"
    )
    
    actual_duration_seconds = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Actual duration in seconds"
    )
    
    # Resource Tracking
    resources_targeted = models.PositiveIntegerField(
        default=0,
        help_text="Number of resources targeted for sync"
    )
    
    resources_processed = models.PositiveIntegerField(
        default=0,
        help_text="Number of resources successfully processed"
    )
    
    resources_created = models.PositiveIntegerField(
        default=0,
        help_text="Number of resources created"
    )
    
    resources_updated = models.PositiveIntegerField(
        default=0,
        help_text="Number of resources updated"
    )
    
    resources_deleted = models.PositiveIntegerField(
        default=0,
        help_text="Number of resources deleted"
    )
    
    resources_skipped = models.PositiveIntegerField(
        default=0,
        help_text="Number of resources skipped due to errors or conflicts"
    )
    
    # File Operations
    files_processed = models.PositiveIntegerField(
        default=0,
        help_text="Number of files processed"
    )
    
    files_created = models.PositiveIntegerField(
        default=0,
        help_text="Number of files created"
    )
    
    files_updated = models.PositiveIntegerField(
        default=0,
        help_text="Number of files updated"
    )
    
    files_deleted = models.PositiveIntegerField(
        default=0,
        help_text="Number of files deleted"
    )
    
    total_file_size_bytes = models.PositiveBigIntegerField(
        default=0,
        help_text="Total size of files processed in bytes"
    )
    
    # Conflict Handling
    conflicts_detected = models.PositiveIntegerField(
        default=0,
        help_text="Number of conflicts detected"
    )
    
    conflicts_resolved = models.PositiveIntegerField(
        default=0,
        help_text="Number of conflicts resolved"
    )
    
    conflicts_manual = models.PositiveIntegerField(
        default=0,
        help_text="Number of conflicts requiring manual resolution"
    )
    
    conflict_resolution_strategy = models.CharField(
        max_length=20,
        blank=True,
        choices=[
            ('timestamp_wins', 'Timestamp Wins'),
            ('gui_wins', 'GUI Wins'),
            ('github_wins', 'GitHub Wins'),
            ('merge_strategy', 'Merge Strategy'),
            ('user_guided', 'User Guided'),
            ('manual_only', 'Manual Only')
        ],
        help_text="Strategy used for conflict resolution"
    )
    
    # GitHub Integration
    github_operations = models.PositiveIntegerField(
        default=0,
        help_text="Number of GitHub API operations performed"
    )
    
    commit_sha = models.CharField(
        max_length=40,
        blank=True,
        help_text="GitHub commit SHA if changes were committed"
    )
    
    pull_request_url = models.URLField(
        blank=True,
        help_text="URL of pull request if created"
    )
    
    branch_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="GitHub branch name if branch was created"
    )
    
    github_rate_limit_hit = models.BooleanField(
        default=False,
        help_text="Whether GitHub rate limit was encountered"
    )
    
    # Error Handling
    error_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of errors encountered"
    )
    
    warning_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of warnings generated"
    )
    
    error_details = models.JSONField(
        default=list,
        blank=True,
        help_text="Detailed error information"
    )
    
    warning_details = models.JSONField(
        default=list,
        blank=True,
        help_text="Detailed warning information"
    )
    
    last_error_message = models.TextField(
        blank=True,
        help_text="Last error message encountered"
    )
    
    # Performance Metrics
    api_calls_made = models.PositiveIntegerField(
        default=0,
        help_text="Total number of API calls made"
    )
    
    network_transfer_bytes = models.PositiveBigIntegerField(
        default=0,
        help_text="Total network transfer in bytes"
    )
    
    memory_peak_mb = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Peak memory usage in MB"
    )
    
    cpu_time_seconds = models.FloatField(
        null=True,
        blank=True,
        help_text="CPU time consumed in seconds"
    )
    
    # User and Context
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="User who initiated this operation"
    )
    
    trigger_type = models.CharField(
        max_length=20,
        choices=[
            ('manual', 'Manual'),
            ('automatic', 'Automatic'),
            ('scheduled', 'Scheduled'),
            ('webhook', 'Webhook'),
            ('api', 'API'),
            ('cli', 'Command Line')
        ],
        default='manual',
        help_text="What triggered this operation"
    )
    
    client_info = models.JSONField(
        default=dict,
        blank=True,
        help_text="Client information (user agent, IP, etc.)"
    )
    
    # Configuration and Metadata
    operation_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Operation configuration and parameters"
    )
    
    progress_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Progress tracking metadata"
    )
    
    result_summary = models.JSONField(
        default=dict,
        blank=True,
        help_text="Summary of operation results"
    )
    
    class Meta:
        verbose_name = "Sync Operation"
        verbose_name_plural = "Sync Operations"
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['fabric', 'status']),
            models.Index(fields=['operation_type', 'status']),
            models.Index(fields=['started_at', 'status']),
            models.Index(fields=['fabric', 'operation_type', 'started_at']),
            models.Index(fields=['initiated_by', 'started_at']),
            models.Index(fields=['status', 'completed_at']),
            models.Index(fields=['operation_id'], name='hnp_sync_op_id_idx'),
            models.Index(fields=['commit_sha'], name='hnp_sync_commit_idx'),
            models.Index(fields=['error_count', 'status']),
        ]
    
    def __str__(self):
        return f"Sync {self.operation_id} ({self.fabric.name}): {self.operation_type} - {self.status}"
    
    def get_absolute_url(self):
        return f"/plugins/hedgehog/sync-operations/{self.operation_id}/"
    
    # === METHODS ===
    
    def calculate_duration(self) -> int:
        """Calculate actual duration in seconds"""
        if self.completed_at and self.started_at:
            delta = self.completed_at - self.started_at
            return int(delta.total_seconds())
        return 0
    
    def update_progress(self, status: str = None, metadata: dict = None) -> None:
        """Update operation progress"""
        if status:
            self.status = status
        
        if metadata:
            self.progress_metadata.update(metadata)
        
        self.save(update_fields=['status', 'progress_metadata'])
    
    def record_error(self, error_message: str, error_type: str = 'general') -> None:
        """Record an error for this operation"""
        self.error_count += 1
        self.last_error_message = error_message
        
        self.error_details.append({
            'timestamp': timezone.now().isoformat(),
            'type': error_type,
            'message': error_message
        })
        
        # Keep only last 100 errors
        self.error_details = self.error_details[-100:]
        
        self.save(update_fields=['error_count', 'last_error_message', 'error_details'])
    
    def record_warning(self, warning_message: str, warning_type: str = 'general') -> None:
        """Record a warning for this operation"""
        self.warning_count += 1
        
        self.warning_details.append({
            'timestamp': timezone.now().isoformat(),
            'type': warning_type,
            'message': warning_message
        })
        
        # Keep only last 50 warnings
        self.warning_details = self.warning_details[-50:]
        
        self.save(update_fields=['warning_count', 'warning_details'])
    
    def complete_operation(self, success: bool = True) -> None:
        """Mark operation as completed"""
        self.completed_at = timezone.now()
        self.actual_duration_seconds = self.calculate_duration()
        
        if success and self.error_count == 0:
            self.status = 'completed'
        elif self.resources_processed > 0 and self.error_count > 0:
            self.status = 'partially_completed'
        else:
            self.status = 'failed'
        
        # Generate result summary
        self.result_summary = {
            'success': success,
            'duration_seconds': self.actual_duration_seconds,
            'resources': {
                'targeted': self.resources_targeted,
                'processed': self.resources_processed,
                'created': self.resources_created,
                'updated': self.resources_updated,
                'deleted': self.resources_deleted,
                'skipped': self.resources_skipped
            },
            'files': {
                'processed': self.files_processed,
                'created': self.files_created,
                'updated': self.files_updated,
                'deleted': self.files_deleted,
                'total_size_bytes': self.total_file_size_bytes
            },
            'conflicts': {
                'detected': self.conflicts_detected,
                'resolved': self.conflicts_resolved,
                'manual': self.conflicts_manual
            },
            'errors': self.error_count,
            'warnings': self.warning_count
        }
        
        self.save(update_fields=[
            'completed_at', 'actual_duration_seconds', 'status', 'result_summary'
        ])
    
    @property
    def is_active(self) -> bool:
        """Check if operation is currently active"""
        return self.status in ['pending', 'initializing', 'in_progress', 'detecting_conflicts', 
                              'resolving_conflicts', 'syncing_data', 'finalizing']
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate for processed resources"""
        if self.resources_targeted == 0:
            return 1.0
        
        successful = self.resources_processed - self.resources_skipped
        return successful / self.resources_targeted
    
    @property
    def performance_summary(self) -> dict:
        """Get performance metrics summary"""
        duration = self.actual_duration_seconds or self.calculate_duration()
        
        return {
            'duration_seconds': duration,
            'resources_per_second': self.resources_processed / max(duration, 1),
            'files_per_second': self.files_processed / max(duration, 1),
            'bytes_per_second': self.total_file_size_bytes / max(duration, 1),
            'api_calls_per_second': self.api_calls_made / max(duration, 1),
            'memory_peak_mb': self.memory_peak_mb,
            'cpu_time_seconds': self.cpu_time_seconds,
            'efficiency_ratio': self.success_rate
        }
```

### 3. New ConflictResolution Model

**Purpose**: Track conflict resolution history and strategies

**Model Definition**:
```python
class ConflictResolution(NetBoxModel):
    """
    Track conflict resolution history and outcomes.
    
    Provides detailed tracking of how conflicts are detected, analyzed,
    and resolved, supporting learning and improvement of resolution strategies.
    """
    
    # Conflict Identification
    resource = models.ForeignKey(
        'netbox_hedgehog.HedgehogResource',
        on_delete=models.CASCADE,
        related_name='conflict_resolutions',
        help_text="Resource that had the conflict"
    )
    
    sync_operation = models.ForeignKey(
        'netbox_hedgehog.SyncOperation',
        on_delete=models.CASCADE,
        related_name='conflict_resolutions',
        help_text="Sync operation during which conflict was resolved"
    )
    
    conflict_id = models.CharField(
        max_length=50,
        help_text="Unique identifier for this conflict instance"
    )
    
    # Conflict Details
    conflict_type = models.CharField(
        max_length=30,
        choices=[
            ('concurrent_modification', 'Concurrent Modification'),
            ('schema_mismatch', 'Schema Mismatch'),
            ('dependency_violation', 'Dependency Violation'),
            ('permission_denied', 'Permission Denied'),
            ('file_corruption', 'File Corruption'),
            ('missing_resource', 'Missing Resource'),
            ('validation_error', 'Validation Error'),
            ('merge_conflict', 'Merge Conflict')
        ],
        help_text="Type of conflict encountered"
    )
    
    severity = models.CharField(
        max_length=10,
        choices=[
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('critical', 'Critical')
        ],
        help_text="Severity level of the conflict"
    )
    
    detected_at = models.DateTimeField(
        help_text="When the conflict was first detected"
    )
    
    # Conflict State Information
    gui_state = models.JSONField(
        help_text="State of resource in GUI at time of conflict"
    )
    
    github_state = models.JSONField(
        help_text="State of resource in GitHub at time of conflict"
    )
    
    conflicting_fields = models.JSONField(
        default=list,
        help_text="List of fields that were in conflict"
    )
    
    # Resolution Process
    resolution_strategy = models.CharField(
        max_length=20,
        choices=[
            ('timestamp_wins', 'Timestamp Wins'),
            ('gui_wins', 'GUI Wins'),
            ('github_wins', 'GitHub Wins'),
            ('merge_automatic', 'Automatic Merge'),
            ('merge_manual', 'Manual Merge'),
            ('user_decision', 'User Decision'),
            ('escalated', 'Escalated'),
            ('skipped', 'Skipped')
        ],
        help_text="Strategy used to resolve the conflict"
    )
    
    auto_resolvable = models.BooleanField(
        help_text="Whether conflict was deemed auto-resolvable"
    )
    
    resolution_attempted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When resolution was attempted"
    )
    
    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When conflict was successfully resolved"
    )
    
    resolution_duration_seconds = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Time taken to resolve conflict in seconds"
    )
    
    # Resolution Outcome
    resolution_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending Resolution'),
            ('in_progress', 'Resolution in Progress'),
            ('resolved', 'Resolved Successfully'),
            ('failed', 'Resolution Failed'),
            ('manual_required', 'Manual Resolution Required'),
            ('escalated', 'Escalated to Administrator'),
            ('abandoned', 'Resolution Abandoned')
        ],
        default='pending',
        help_text="Current status of conflict resolution"
    )
    
    resolved_state = models.JSONField(
        null=True,
        blank=True,
        help_text="Final resolved state after conflict resolution"
    )
    
    resolution_details = models.JSONField(
        default=dict,
        help_text="Detailed information about resolution process"
    )
    
    # User Involvement
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="User who resolved the conflict (if manual)"
    )
    
    user_decisions = models.JSONField(
        default=dict,
        blank=True,
        help_text="User decisions made during conflict resolution"
    )
    
    # Quality and Learning
    resolution_quality_score = models.FloatField(
        null=True,
        blank=True,
        help_text="Quality score of resolution (0.0-1.0)"
    )
    
    feedback_provided = models.BooleanField(
        default=False,
        help_text="Whether user provided feedback on resolution"
    )
    
    user_feedback = models.TextField(
        blank=True,
        help_text="User feedback on resolution quality"
    )
    
    lessons_learned = models.JSONField(
        default=dict,
        blank=True,
        help_text="Lessons learned from this conflict resolution"
    )
    
    class Meta:
        verbose_name = "Conflict Resolution"
        verbose_name_plural = "Conflict Resolutions"
        ordering = ['-detected_at']
        indexes = [
            models.Index(fields=['resource', 'detected_at']),
            models.Index(fields=['conflict_type', 'resolution_status']),
            models.Index(fields=['sync_operation', 'resolution_status']),
            models.Index(fields=['severity', 'auto_resolvable']),
            models.Index(fields=['resolved_by', 'resolved_at']),
            models.Index(fields=['resolution_strategy', 'resolution_status']),
        ]
    
    def __str__(self):
        return f"Conflict {self.conflict_id}: {self.resource.name} ({self.conflict_type})"
    
    def calculate_resolution_duration(self) -> int:
        """Calculate resolution duration in seconds"""
        if self.resolved_at and self.resolution_attempted_at:
            delta = self.resolved_at - self.resolution_attempted_at
            return int(delta.total_seconds())
        return 0
    
    def mark_resolved(self, resolved_state: dict, resolved_by: 'User' = None) -> None:
        """Mark conflict as resolved"""
        self.resolution_status = 'resolved'
        self.resolved_at = timezone.now()
        self.resolved_state = resolved_state
        self.resolved_by = resolved_by
        self.resolution_duration_seconds = self.calculate_resolution_duration()
        
        self.save(update_fields=[
            'resolution_status', 'resolved_at', 'resolved_state', 
            'resolved_by', 'resolution_duration_seconds'
        ])
    
    @property
    def is_resolved(self) -> bool:
        """Check if conflict is resolved"""
        return self.resolution_status == 'resolved'
    
    @property
    def requires_attention(self) -> bool:
        """Check if conflict requires human attention"""
        return self.resolution_status in ['manual_required', 'escalated', 'failed']
```

## Database Migration Strategy

### 1. Migration Planning

**Migration Phases**:
1. **Phase 1**: Add new fields to HedgehogResource model
2. **Phase 2**: Create new SyncOperation model  
3. **Phase 3**: Create new ConflictResolution model
4. **Phase 4**: Add database indexes for performance
5. **Phase 5**: Data migration for existing resources

### 2. Migration Scripts

**Phase 1 Migration**:
```python
# migrations/0001_add_bidirectional_sync_fields.py
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [
        ('netbox_hedgehog', '0001_initial'),
    ]
    
    operations = [
        # Add bidirectional sync fields to HedgehogResource
        migrations.AddField(
            model_name='hedgehogresource',
            name='managed_file_path',
            field=models.CharField(blank=True, max_length=500, 
                help_text='Path to managed file in GitOps repository'),
        ),
        migrations.AddField(
            model_name='hedgehogresource',
            name='file_hash',
            field=models.CharField(blank=True, max_length=64, 
                help_text='SHA-256 hash of current managed file content'),
        ),
        migrations.AddField(
            model_name='hedgehogresource',
            name='last_file_sync',
            field=models.DateTimeField(blank=True, null=True, 
                help_text='Timestamp of last file synchronization'),
        ),
        # ... (additional fields)
        
        # Add indexes
        migrations.AddIndex(
            model_name='hedgehogresource',
            index=models.Index(fields=['managed_file_path'], name='hnp_resource_file_path_idx'),
        ),
        migrations.AddIndex(
            model_name='hedgehogresource',
            index=models.Index(fields=['file_hash'], name='hnp_resource_file_hash_idx'),
        ),
        # ... (additional indexes)
    ]
```

**Phase 2 Migration**:
```python
# migrations/0002_create_sync_operation_model.py
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [
        ('netbox_hedgehog', '0001_add_bidirectional_sync_fields'),
    ]
    
    operations = [
        migrations.CreateModel(
            name='SyncOperation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('operation_id', models.CharField(max_length=50, unique=True, 
                    help_text='Unique identifier for this sync operation')),
                ('fabric', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, 
                    related_name='sync_operations', to='netbox_hedgehog.hedgehogfabric')),
                # ... (all other fields)
            ],
            options={
                'verbose_name': 'Sync Operation',
                'verbose_name_plural': 'Sync Operations',
                'ordering': ['-started_at'],
            },
        ),
        # Add indexes
        migrations.AddIndex(
            model_name='syncoperation',
            index=models.Index(fields=['operation_id'], name='hnp_sync_op_id_idx'),
        ),
        # ... (additional indexes)
    ]
```

### 3. Data Migration for Existing Resources

**Migration Script**:
```python
# migrations/0005_migrate_existing_resource_data.py
from django.db import migrations
from django.utils import timezone

def migrate_existing_resources(apps, schema_editor):
    """Migrate existing HedgehogResource records to support bidirectional sync"""
    HedgehogResource = apps.get_model('netbox_hedgehog', 'HedgehogResource')
    
    for resource in HedgehogResource.objects.all():
        # Set default sync direction
        resource.sync_direction = 'bidirectional'
        resource.auto_sync_enabled = True
        resource.sync_priority = 100
        resource.conflict_status = 'none'
        
        # Initialize empty collections
        resource.external_modifications = []
        resource.sync_metadata = {}
        resource.conflict_details = {}
        
        # Set GitHub branch to default if fabric has git repository
        if resource.fabric.git_repository:
            resource.github_branch = resource.fabric.git_repository.default_branch or 'main'
        
        resource.save()

def reverse_migration(apps, schema_editor):
    """Reverse migration - no action needed as fields will be removed"""
    pass

class Migration(migrations.Migration):
    dependencies = [
        ('netbox_hedgehog', '0004_create_conflict_resolution_model'),
    ]
    
    operations = [
        migrations.RunPython(migrate_existing_resources, reverse_migration),
    ]
```

## Performance Considerations

### 1. Database Indexes

**Optimized Index Strategy**:
```sql
-- Primary lookup indexes
CREATE INDEX CONCURRENTLY hnp_resource_file_path_idx ON netbox_hedgehog_hedgehogresource (managed_file_path);
CREATE INDEX CONCURRENTLY hnp_resource_file_hash_idx ON netbox_hedgehog_hedgehogresource (file_hash);
CREATE INDEX CONCURRENTLY hnp_sync_op_id_idx ON netbox_hedgehog_syncoperation (operation_id);

-- Composite indexes for common queries
CREATE INDEX CONCURRENTLY hnp_resource_sync_status_idx ON netbox_hedgehog_hedgehogresource (fabric_id, conflict_status, auto_sync_enabled);
CREATE INDEX CONCURRENTLY hnp_resource_sync_priority_idx ON netbox_hedgehog_hedgehogresource (fabric_id, sync_priority, auto_sync_enabled);
CREATE INDEX CONCURRENTLY hnp_sync_op_fabric_status_idx ON netbox_hedgehog_syncoperation (fabric_id, status, started_at);

-- Performance monitoring indexes
CREATE INDEX CONCURRENTLY hnp_resource_error_tracking_idx ON netbox_hedgehog_hedgehogresource (sync_error_count, last_sync_error_at);
CREATE INDEX CONCURRENTLY hnp_conflict_severity_idx ON netbox_hedgehog_conflictresolution (severity, auto_resolvable, resolution_status);
```

### 2. Query Optimization

**Optimized Queries**:
```python
# Get resources needing sync (optimized)
resources_needing_sync = HedgehogResource.objects.select_related('fabric', 'fabric__git_repository').filter(
    fabric=fabric,
    auto_sync_enabled=True,
    conflict_status='none'
).exclude(
    sync_direction__in=['disabled', 'git_to_gui']
).order_by('sync_priority', 'last_file_sync')

# Get sync operations with statistics (optimized)  
sync_operations = SyncOperation.objects.filter(
    fabric=fabric,
    started_at__gte=timezone.now() - timedelta(days=30)
).values(
    'operation_type', 'status'
).annotate(
    count=Count('id'),
    avg_duration=Avg('actual_duration_seconds'),
    success_rate=Avg('resources_processed') / Avg('resources_targeted')
)
```

### 3. Monitoring and Alerting

**Performance Metrics**:
- Sync operation duration trends
- Conflict resolution success rates
- GitHub API usage and rate limiting
- Database query performance
- File synchronization throughput

## Testing Strategy

### 1. Database Schema Tests

**Migration Tests**:
```python
class TestBidirectionalSyncMigrations(TestCase):
    
    def test_migration_adds_required_fields(self):
        """Test that migration adds all required fields"""
        resource = HedgehogResource.objects.create(
            fabric=self.fabric,
            name='test-resource',
            kind='VPC'
        )
        
        # Test new fields exist and have correct defaults
        self.assertEqual(resource.sync_direction, 'bidirectional')
        self.assertTrue(resource.auto_sync_enabled)
        self.assertEqual(resource.conflict_status, 'none')
        self.assertEqual(resource.external_modifications, [])
    
    def test_sync_operation_model_creation(self):
        """Test SyncOperation model functionality"""
        operation = SyncOperation.objects.create(
            operation_id='test-op-123',
            fabric=self.fabric,
            operation_type='gui_to_github'
        )
        
        self.assertTrue(operation.is_active)
        self.assertEqual(operation.success_rate, 1.0)
        
        operation.complete_operation(success=True)
        self.assertFalse(operation.is_active)
        self.assertEqual(operation.status, 'completed')
```

### 2. Performance Tests

**Database Performance Tests**:
```python
class TestDatabasePerformance(TestCase):
    
    def test_sync_query_performance(self):
        """Test that sync queries perform within acceptable limits"""
        # Create test data
        for i in range(1000):
            HedgehogResource.objects.create(
                fabric=self.fabric,
                name=f'resource-{i}',
                kind='VPC'
            )
        
        # Test query performance
        start_time = time.time()
        resources = list(HedgehogResource.objects.filter(
            fabric=self.fabric,
            auto_sync_enabled=True
        ).order_by('sync_priority')[:100])
        query_time = time.time() - start_time
        
        self.assertLess(query_time, 0.1)  # Query should complete in < 100ms
        self.assertEqual(len(resources), 100)
```

This database schema enhancement provides a robust foundation for bidirectional synchronization while maintaining compatibility with existing HNP architecture and ensuring scalable performance for enterprise deployments.