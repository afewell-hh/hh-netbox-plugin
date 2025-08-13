"""
Enhanced GitOps Models with Bidirectional Synchronization Support

This file contains the enhanced model definitions that extend existing HNP models
with bidirectional synchronization capabilities. These enhancements are designed
to integrate seamlessly with the existing architecture while adding comprehensive
GitOps directory management and file synchronization features.
"""

import hashlib
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

from django.db import models, transaction
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone
from netbox.models import NetBoxModel

from ..models.gitops import HedgehogResource
from ..models.git_repository import GitRepository
from ..models.fabric import HedgehogFabric

logger = logging.getLogger(__name__)


class SyncOperation(NetBoxModel):
    """
    Track individual sync operations for audit and debugging.
    
    This model provides comprehensive tracking of all bidirectional synchronization
    operations, enabling detailed audit trails and debugging capabilities.
    """
    
    fabric = models.ForeignKey(
        'netbox_hedgehog.HedgehogFabric',
        on_delete=models.CASCADE,
        related_name='sync_operations',
        help_text="Fabric this sync operation is associated with"
    )
    
    operation_type = models.CharField(
        max_length=30,
        choices=[
            ('gui_to_github', 'GUI to GitHub'),
            ('github_to_gui', 'GitHub to GUI'),
            ('directory_init', 'Directory Initialization'),
            ('conflict_resolution', 'Conflict Resolution'),
            ('ingestion', 'File Ingestion')
        ],
        help_text="Type of synchronization operation"
    )
    
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('in_progress', 'In Progress'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
            ('cancelled', 'Cancelled')
        ],
        default='pending',
        help_text="Current operation status"
    )
    
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    details = models.JSONField(
        default=dict,
        blank=True,
        help_text="Detailed operation information"
    )
    
    error_message = models.TextField(
        blank=True,
        help_text="Error message if operation failed"
    )
    
    # File operation statistics
    files_processed = models.PositiveIntegerField(default=0)
    files_created = models.PositiveIntegerField(default=0)
    files_updated = models.PositiveIntegerField(default=0)
    files_deleted = models.PositiveIntegerField(default=0)
    
    # GitHub integration
    commit_sha = models.CharField(max_length=40, blank=True)
    pull_request_url = models.URLField(blank=True)
    
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="User who initiated this operation"
    )
    
    class Meta:
        verbose_name = "Sync Operation"
        verbose_name_plural = "Sync Operations"
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['fabric', 'status'], name='hnp_enhanced_syncop_fab_status_idx'),
            models.Index(fields=['operation_type', 'status'], name='hnp_enhanced_syncop_optype_status_idx'),
            models.Index(fields=['started_at'], name='hnp_enhanced_syncop_started_idx'),
            models.Index(fields=['fabric', 'operation_type', 'started_at'], name='hnp_enhanced_syncop_fab_type_start_idx'),
        ]
    
    def __str__(self):
        return f"{self.operation_type} - {self.fabric.name} ({self.status})"
    
    def get_absolute_url(self):
        return reverse('plugins:netbox_hedgehog:syncop_detail', args=[self.pk])
    
    @property
    def duration(self):
        """Get operation duration"""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        elif self.started_at:
            return timezone.now() - self.started_at
        return None
    
    def mark_completed(self, success: bool = True, error_message: str = None):
        """Mark operation as completed"""
        self.completed_at = timezone.now()
        self.status = 'completed' if success else 'failed'
        if error_message:
            self.error_message = error_message
        self.save()
    
    def update_statistics(self, processed: int = 0, created: int = 0, 
                         updated: int = 0, deleted: int = 0):
        """Update file operation statistics"""
        self.files_processed += processed
        self.files_created += created
        self.files_updated += updated
        self.files_deleted += deleted
        self.save()
    
    def get_operation_summary(self) -> Dict[str, Any]:
        """Get comprehensive operation summary"""
        return {
            'id': self.pk,
            'fabric': self.fabric.name,
            'operation_type': self.operation_type,
            'status': self.status,
            'duration': str(self.duration) if self.duration else None,
            'statistics': {
                'files_processed': self.files_processed,
                'files_created': self.files_created,
                'files_updated': self.files_updated,
                'files_deleted': self.files_deleted
            },
            'github_integration': {
                'commit_sha': self.commit_sha,
                'pull_request_url': self.pull_request_url
            },
            'metadata': {
                'started_at': self.started_at,
                'completed_at': self.completed_at,
                'initiated_by': self.initiated_by.username if self.initiated_by else None,
                'error_message': self.error_message
            }
        }


class EnhancedHedgehogResourceMixin:
    """
    Mixin class containing bidirectional sync methods for HedgehogResource.
    
    This mixin extends the existing HedgehogResource model with comprehensive
    bidirectional synchronization capabilities while maintaining backward compatibility.
    """
    
    def calculate_file_hash(self, content: str) -> str:
        """Calculate SHA-256 hash of file content"""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    def update_file_mapping(self, file_path: str, content_hash: str):
        """Update file mapping information"""
        self.managed_file_path = file_path
        self.file_hash = content_hash
        self.last_file_sync = timezone.now()
        self.save(update_fields=['managed_file_path', 'file_hash', 'last_file_sync'])
    
    def detect_external_modifications(self, current_hash: str) -> bool:
        """Detect if file has been modified externally"""
        if not self.file_hash:
            return False
        
        has_changes = self.file_hash != current_hash
        if has_changes:
            # Log external modification
            modification = {
                'timestamp': timezone.now().isoformat(),
                'previous_hash': self.file_hash,
                'current_hash': current_hash,
                'detection_method': 'hash_comparison'
            }
            
            modifications = list(self.external_modifications) if self.external_modifications else []
            modifications.append(modification)
            self.external_modifications = modifications
            self.save(update_fields=['external_modifications'])
        
        return has_changes
    
    def mark_conflict(self, conflict_type: str, details: Dict[str, Any]):
        """Mark resource as having a conflict"""
        self.conflict_status = 'detected'
        self.conflict_details = {
            'type': conflict_type,
            'detected_at': timezone.now().isoformat(),
            'details': details
        }
        self.save(update_fields=['conflict_status', 'conflict_details'])
    
    def resolve_conflict(self, resolution_strategy: str, user=None):
        """Resolve resource conflict"""
        self.conflict_status = 'resolved'
        self.conflict_details.update({
            'resolved_at': timezone.now().isoformat(),
            'resolution_strategy': resolution_strategy,
            'resolved_by': user.username if user else 'system'
        })
        self.save(update_fields=['conflict_status', 'conflict_details'])
    
    def sync_to_github(self) -> Dict[str, Any]:
        """Sync this resource to GitHub repository"""
        if not self.fabric.git_repository:
            return {
                'success': False,
                'error': 'No Git repository configured for fabric'
            }
        
        try:
            from ..utils.github_sync_client import GitHubSyncClient
            
            client = GitHubSyncClient(self.fabric.git_repository)
            
            # Generate YAML content
            yaml_content = self.generate_yaml_content()
            if not yaml_content:
                return {
                    'success': False,
                    'error': 'Could not generate YAML content for resource'
                }
            
            # Determine file path
            file_path = self.managed_file_path or self._generate_managed_file_path()
            
            # Push to GitHub
            result = client.create_or_update_file(
                path=file_path,
                content=yaml_content,
                message=f"Update {self.kind}/{self.name} via HNP GUI"
            )
            
            if result['success']:
                # Update file mapping
                content_hash = self.calculate_file_hash(yaml_content)
                self.update_file_mapping(file_path, content_hash)
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to sync resource {self} to GitHub: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _generate_managed_file_path(self) -> str:
        """Generate managed file path for this resource"""
        kind_dir = self.kind.lower() + 's'  # VPC -> vpcs
        return f"managed/{kind_dir}/{self.name}.yaml"
    
    def get_sync_status(self) -> Dict[str, Any]:
        """Get comprehensive sync status for this resource"""
        return {
            'resource': {
                'name': self.name,
                'kind': self.kind,
                'namespace': self.namespace
            },
            'file_mapping': {
                'managed_file_path': self.managed_file_path,
                'file_hash': self.file_hash,
                'last_file_sync': self.last_file_sync
            },
            'sync_configuration': {
                'sync_direction': self.sync_direction,
                'conflict_status': self.conflict_status
            },
            'external_modifications': len(self.external_modifications) if self.external_modifications else 0,
            'needs_sync': self.needs_synchronization()
        }
    
    def needs_synchronization(self) -> bool:
        """Check if resource needs synchronization"""
        # Check if there are unresolved conflicts
        if self.conflict_status == 'detected':
            return True
        
        # Check if external modifications exist
        if self.external_modifications:
            return True
        
        # Check if desired and actual states differ
        if self.has_drift:
            return True
        
        return False


class EnhancedGitRepositoryMixin:
    """
    Mixin class containing direct push capabilities for GitRepository.
    
    This mixin extends the existing GitRepository model with direct GitHub push
    capabilities and enhanced credential management for bidirectional sync.
    """
    
    def can_push_directly(self) -> bool:
        """Check if direct push operations are allowed"""
        return (
            self.direct_push_enabled and
            self.connection_status == 'connected' and
            bool(self.encrypted_credentials)
        )
    
    def get_push_branch(self) -> str:
        """Get the branch to use for push operations"""
        return self.push_branch or self.default_branch
    
    def create_commit_info(self) -> Dict[str, str]:
        """Create commit author information"""
        return {
            'name': self.commit_author_name,
            'email': self.commit_author_email
        }
    
    def validate_push_permissions(self) -> Dict[str, Any]:
        """Validate that credentials have push permissions"""
        try:
            from ..utils.github_sync_client import GitHubSyncClient
            
            client = GitHubSyncClient(self)
            return client.validate_push_permissions()
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_push_configuration(self) -> Dict[str, Any]:
        """Get comprehensive push configuration"""
        return {
            'repository': {
                'url': self.url,
                'push_branch': self.get_push_branch(),
                'direct_push_enabled': self.direct_push_enabled
            },
            'authentication': {
                'type': self.authentication_type,
                'has_credentials': bool(self.encrypted_credentials)
            },
            'commit_info': self.create_commit_info(),
            'permissions': {
                'can_push': self.can_push_directly(),
                'connection_status': self.connection_status
            }
        }


class EnhancedHedgehogFabricMixin:
    """
    Mixin class containing directory management capabilities for HedgehogFabric.
    
    This mixin extends the existing HedgehogFabric model with comprehensive
    GitOps directory management and bidirectional synchronization orchestration.
    """
    
    def initialize_gitops_directories(self, force: bool = False) -> Dict[str, Any]:
        """Initialize GitOps directory structure"""
        if not self.git_repository:
            return {
                'success': False,
                'error': 'No Git repository configured for fabric'
            }
        
        try:
            from ..utils.gitops_directory_manager import GitOpsDirectoryManager
            
            manager = GitOpsDirectoryManager(self)
            result = manager.initialize_directory_structure(force=force)
            
            if result['success']:
                self.gitops_directory_status = 'initialized'
                self.directory_init_error = ''
            else:
                self.gitops_directory_status = 'error'
                self.directory_init_error = result.get('error', 'Unknown error')
            
            self.save(update_fields=['gitops_directory_status', 'directory_init_error'])
            return result
            
        except Exception as e:
            self.gitops_directory_status = 'error'
            self.directory_init_error = str(e)
            self.save(update_fields=['gitops_directory_status', 'directory_init_error'])
            
            return {
                'success': False,
                'error': str(e)
            }
    
    def trigger_bidirectional_sync(self, direction: str = 'bidirectional', 
                                  user=None) -> Dict[str, Any]:
        """Trigger bidirectional synchronization"""
        if not self.git_repository:
            return {
                'success': False,
                'error': 'No Git repository configured for fabric'
            }
        
        try:
            from ..utils.bidirectional_sync_orchestrator import BidirectionalSyncOrchestrator
            
            orchestrator = BidirectionalSyncOrchestrator(self)
            
            # Create sync operation record
            sync_op = SyncOperation.objects.create(
                fabric=self,
                operation_type=f'{direction}_sync',
                initiated_by=user
            )
            
            # Perform synchronization
            result = orchestrator.sync(direction=direction)
            
            # Update sync operation
            sync_op.mark_completed(
                success=result['success'],
                error_message=result.get('error')
            )
            
            if result['success']:
                self.last_directory_sync = timezone.now()
                self.save(update_fields=['last_directory_sync'])
            
            result['sync_operation_id'] = sync_op.pk
            return result
            
        except Exception as e:
            logger.error(f"Bidirectional sync failed for fabric {self.name}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_directory_status(self) -> Dict[str, Any]:
        """Get comprehensive directory status"""
        try:
            from ..utils.gitops_directory_manager import GitOpsDirectoryManager
            
            manager = GitOpsDirectoryManager(self)
            return manager.get_directory_status()
            
        except Exception as e:
            return {
                'error': str(e),
                'status': 'error'
            }
    
    def get_sync_summary(self) -> Dict[str, Any]:
        """Get comprehensive synchronization summary"""
        # Get recent sync operations
        recent_ops = self.sync_operations.filter(
            started_at__gte=timezone.now() - timezone.timedelta(days=7)
        ).order_by('-started_at')[:5]
        
        # Get resources needing sync
        resources_needing_sync = self.gitops_resources.filter(
            models.Q(conflict_status='detected') |
            models.Q(external_modifications__isnull=False) |
            models.Q(drift_status__in=['spec_drift', 'desired_only', 'actual_only'])
        ).count()
        
        return {
            'directory_status': {
                'status': self.gitops_directory_status,
                'last_sync': self.last_directory_sync,
                'error': self.directory_init_error
            },
            'sync_operations': {
                'recent_count': recent_ops.count(),
                'last_operation': recent_ops.first().get_operation_summary() if recent_ops.exists() else None
            },
            'resources': {
                'total': self.gitops_resources.count(),
                'needs_sync': resources_needing_sync,
                'conflicts': self.gitops_resources.filter(conflict_status='detected').count()
            },
            'capabilities': {
                'can_sync': bool(self.git_repository and self.git_repository.can_push_directly()),
                'directory_initialized': self.gitops_directory_status == 'initialized',
                'bidirectional_enabled': True
            }
        }


# Model method injection functions (to be called during app initialization)

def enhance_existing_models():
    """
    Inject bidirectional sync capabilities into existing models.
    
    This function adds the mixin methods to existing model classes without
    requiring inheritance changes. This approach maintains backward compatibility
    while adding comprehensive bidirectional sync functionality.
    """
    
    # Enhance HedgehogResource
    for method_name in dir(EnhancedHedgehogResourceMixin):
        if not method_name.startswith('_'):
            method = getattr(EnhancedHedgehogResourceMixin, method_name)
            if callable(method):
                setattr(HedgehogResource, method_name, method)
    
    # Enhance GitRepository
    for method_name in dir(EnhancedGitRepositoryMixin):
        if not method_name.startswith('_'):
            method = getattr(EnhancedGitRepositoryMixin, method_name)
            if callable(method):
                setattr(GitRepository, method_name, method)
    
    # Enhance HedgehogFabric
    for method_name in dir(EnhancedHedgehogFabricMixin):
        if not method_name.startswith('_'):
            method = getattr(EnhancedHedgehogFabricMixin, method_name)
            if callable(method):
                setattr(HedgehogFabric, method_name, method)
    
    logger.info("Enhanced existing models with bidirectional sync capabilities")


# Field definitions for backward compatibility documentation
BIDIRECTIONAL_SYNC_FIELDS = {
    'HedgehogResource': [
        'managed_file_path',      # Path to managed file in GitOps repository
        'file_hash',              # SHA-256 hash of current file content
        'last_file_sync',         # Timestamp of last file synchronization
        'sync_direction',         # Synchronization direction preference
        'conflict_status',        # Current conflict status
        'conflict_details',       # Detailed conflict information
        'external_modifications', # Log of external modifications detected
        'sync_metadata'           # Additional sync-related metadata
    ],
    'GitRepository': [
        'direct_push_enabled',    # Enable direct push operations
        'push_branch',            # Default branch for push operations
        'commit_author_name',     # Author name for automated commits
        'commit_author_email'     # Author email for automated commits
    ],
    'HedgehogFabric': [
        'gitops_directory_status', # Current GitOps directory structure status
        'directory_init_error',    # Last directory initialization error
        'last_directory_sync'      # Timestamp of last directory synchronization
    ]
}