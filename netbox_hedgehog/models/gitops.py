from django.db import models
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.conf import settings
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from netbox.models import NetBoxModel
from utilities.choices import ChoiceSet
import json
import yaml
from datetime import datetime


class ResourceStateChoices(ChoiceSet):
    """Resource state choices for six-state model"""
    DRAFT = 'draft'
    COMMITTED = 'committed'
    SYNCED = 'synced'
    DRIFTED = 'drifted'
    ORPHANED = 'orphaned'
    PENDING = 'pending'
    
    CHOICES = [
        (DRAFT, 'Draft'),
        (COMMITTED, 'Committed'),
        (SYNCED, 'Synced'),
        (DRIFTED, 'Drifted'),
        (ORPHANED, 'Orphaned'),
        (PENDING, 'Pending'),
    ]


class HedgehogResource(NetBoxModel):
    """
    Enhanced resource model with six-state management system.
    Tracks desired state (from Git), actual state (from Kubernetes),
    and draft state (uncommitted changes) for comprehensive GitOps workflows.
    """
    
    # Resource Identification
    fabric = models.ForeignKey(
        'netbox_hedgehog.HedgehogFabric',
        on_delete=models.CASCADE,
        related_name='gitops_resources',
        help_text="Hedgehog fabric this resource belongs to"
    )
    
    name = models.CharField(
        max_length=253,
        help_text="Kubernetes resource name (DNS-1123 compliant)"
    )
    
    namespace = models.CharField(
        max_length=253,
        default='default',
        help_text="Kubernetes namespace for this resource"
    )
    
    kind = models.CharField(
        max_length=50,
        help_text="Kubernetes resource kind (VPC, Connection, Server, etc.)"
    )
    
    api_version = models.CharField(
        max_length=100,
        default='unknown/v1',
        help_text="Kubernetes API version"
    )
    
    # Link to actual CRD object
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Content type of the linked CRD object"
    )
    
    object_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="ID of the linked CRD object"
    )
    
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # Desired State (from Git repository)
    desired_spec = models.JSONField(
        null=True,
        blank=True,
        help_text="Desired resource specification from Git repository"
    )
    
    desired_commit = models.CharField(
        max_length=40,
        blank=True,
        help_text="Git commit SHA containing this desired state"
    )
    
    desired_file_path = models.CharField(
        max_length=500,
        blank=True,
        help_text="Path to YAML file in Git repository"
    )
    
    desired_updated = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When desired state was last updated from Git"
    )
    
    # Draft State (uncommitted changes)
    draft_spec = models.JSONField(
        null=True,
        blank=True,
        help_text="Draft resource specification (uncommitted)"
    )
    
    draft_updated = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When draft was last updated"
    )
    
    draft_updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='draft_resources',
        help_text="User who last updated draft"
    )
    
    # Actual State (from Kubernetes cluster)
    actual_spec = models.JSONField(
        null=True,
        blank=True,
        help_text="Actual resource specification from Kubernetes"
    )
    
    actual_status = models.JSONField(
        null=True,
        blank=True,
        help_text="Actual resource status from Kubernetes"
    )
    
    actual_resource_version = models.CharField(
        max_length=50,
        blank=True,
        help_text="Kubernetes resource version"
    )
    
    actual_updated = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When actual state was last updated from Kubernetes"
    )
    
    # State tracking
    resource_state = models.CharField(
        max_length=20,
        choices=ResourceStateChoices,
        default=ResourceStateChoices.DRAFT,
        help_text="Current resource state"
    )
    
    last_state_change = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp of last state change"
    )
    
    state_change_reason = models.TextField(
        blank=True,
        help_text="Reason for last state change"
    )
    
    # Drift Analysis
    drift_status = models.CharField(
        max_length=20,
        choices=[
            ('in_sync', 'In Sync'),
            ('spec_drift', 'Spec Drift'),
            ('desired_only', 'Desired Only'),
            ('actual_only', 'Actual Only'),
            ('creation_pending', 'Creation Pending'),
            ('deletion_pending', 'Deletion Pending')
        ],
        default='in_sync',
        help_text="Current drift status between desired and actual state"
    )
    
    drift_details = models.JSONField(
        default=dict,
        blank=True,
        help_text="Detailed drift analysis including specific differences"
    )
    
    drift_score = models.FloatField(
        default=0.0,
        help_text="Numerical drift score (0.0 = no drift, 1.0 = complete drift)"
    )
    
    drift_severity = models.CharField(
        max_length=20,
        blank=True,
        choices=[
            ('none', 'No Drift'),
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('critical', 'Critical'),
        ],
        help_text="Drift severity level"
    )
    
    last_reconciliation = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of last reconciliation attempt"
    )
    
    reconciliation_attempts = models.PositiveIntegerField(
        default=0,
        help_text="Number of reconciliation attempts"
    )
    
    # Relationship tracking
    dependent_resources = models.ManyToManyField(
        'self',
        symmetrical=False,
        related_name='dependency_of',
        blank=True,
        help_text="Resources this resource depends on"
    )
    
    dependency_score = models.FloatField(
        default=0.0,
        help_text="Calculated dependency complexity score"
    )
    
    relationship_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Relationship metadata and caching"
    )
    
    # Sync tracking
    last_synced_commit = models.CharField(
        max_length=40,
        blank=True,
        help_text="Git commit SHA of last successful sync"
    )
    
    sync_attempts = models.PositiveIntegerField(
        default=0,
        help_text="Number of sync attempts"
    )
    
    last_sync_error = models.TextField(
        blank=True,
        help_text="Last sync error message"
    )
    
    # Metadata
    labels = models.JSONField(
        default=dict,
        blank=True,
        help_text="Kubernetes labels as JSON"
    )
    
    annotations = models.JSONField(
        default=dict,
        blank=True,
        help_text="Kubernetes annotations as JSON"
    )
    
    # Tracking fields
    first_seen = models.DateTimeField(
        auto_now_add=True,
        help_text="When this resource was first discovered"
    )
    
    last_drift_check = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When drift was last calculated for this resource"
    )
    
    # User tracking
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_resources',
        help_text="User who created this resource"
    )
    
    last_modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='modified_resources',
        help_text="User who last modified this resource"
    )
    
    class Meta:
        verbose_name = "Hedgehog Resource"
        verbose_name_plural = "Hedgehog Resources"
        unique_together = [['fabric', 'namespace', 'name', 'kind']]
        ordering = ['fabric', 'namespace', 'kind', 'name']
        indexes = [
            models.Index(fields=['fabric', 'resource_state']),
            models.Index(fields=['fabric', 'kind']),
            models.Index(fields=['resource_state', 'last_state_change']),
            models.Index(fields=['desired_commit']),
            models.Index(fields=['actual_updated']),
            models.Index(fields=['drift_status', 'drift_score']),
            models.Index(fields=['fabric', 'kind', 'drift_status']),
            models.Index(fields=['last_reconciliation']),
            models.Index(fields=['fabric', 'kind', 'resource_state']),
        ]
    
    def __str__(self):
        return f"{self.kind}/{self.name} ({self.fabric.name})"
    
    def get_absolute_url(self):
        # TODO: Add proper URL when gitops resource detail view is implemented
        return f"/plugins/hedgehog/gitops/resources/{self.pk}/"
    
    def clean(self):
        """Validate the GitOps resource before saving"""
        super().clean()
        
        # Validate Kubernetes name format
        if not self.is_valid_k8s_name(self.name):
            raise ValidationError({
                'name': 'Name must be a valid Kubernetes resource name (DNS-1123 compliant)'
            })
        
        # Validate namespace format
        if not self.is_valid_k8s_name(self.namespace):
            raise ValidationError({
                'namespace': 'Namespace must be a valid Kubernetes namespace name'
            })
        
        # Validate kind is not empty
        if not self.kind.strip():
            raise ValidationError({
                'kind': 'Kind must be specified'
            })
        
        # Validate drift score range
        if self.drift_score < 0.0 or self.drift_score > 1.0:
            raise ValidationError({
                'drift_score': 'Drift score must be between 0.0 and 1.0'
            })
    
    @staticmethod
    def is_valid_k8s_name(name):
        """
        Validate Kubernetes resource name (DNS-1123 compliant).
        Must be lowercase alphanumeric plus hyphens, start/end with alphanumeric.
        """
        import re
        if not name:
            return False
        pattern = r'^[a-z0-9]([-a-z0-9]*[a-z0-9])?$'
        return bool(re.match(pattern, name)) and len(name) <= 253
    
    # Properties for state checking
    @property
    def has_drift(self):
        """Return True if this resource has detected drift"""
        return self.drift_status != 'in_sync'
    
    @property
    def has_desired_state(self):
        """Return True if desired state is available"""
        return self.desired_spec is not None
    
    @property
    def has_actual_state(self):
        """Return True if actual state is available"""
        return self.actual_spec is not None
    
    @property
    def is_orphaned(self):
        """Return True if resource exists in cluster but not in Git"""
        return self.drift_status == 'actual_only'
    
    @property
    def is_pending_creation(self):
        """Return True if resource exists in Git but not in cluster"""
        return self.drift_status == 'desired_only'
    
    @property
    def git_file_url(self):
        """Generate GitHub/GitLab URL for this resource's YAML file"""
        if self.desired_file_path and self.fabric.git_repository_url:
            base_url = self.fabric.git_repository_url.rstrip('.git')
            return f"{base_url}/blob/{self.fabric.git_branch}/{self.desired_file_path}"
        return None
    
    @property
    def resource_identifier(self):
        """Return unique resource identifier"""
        return f"{self.namespace}/{self.kind}/{self.name}"
    
    # Drift detection and analysis methods
    def calculate_drift(self):
        """
        Calculate drift between desired and actual state.
        Updates drift_status, drift_details, and drift_score fields.
        """
        from django.utils import timezone
        
        try:
            # Handle missing states
            if not self.has_desired_state and not self.has_actual_state:
                self.drift_status = 'in_sync'  # Both missing = in sync
                self.drift_score = 0.0
                self.drift_details = {}
            elif not self.has_desired_state:
                self.drift_status = 'actual_only'
                self.drift_score = 1.0
                self.drift_details = {'type': 'orphaned', 'message': 'Resource exists in cluster but not in Git'}
            elif not self.has_actual_state:
                self.drift_status = 'desired_only'
                self.drift_score = 1.0
                self.drift_details = {'type': 'pending', 'message': 'Resource exists in Git but not in cluster'}
            else:
                # Both states exist - compare them
                drift_result = self._compare_specs(self.desired_spec, self.actual_spec)
                self.drift_status = 'spec_drift' if drift_result['has_drift'] else 'in_sync'
                self.drift_score = drift_result['drift_score']
                self.drift_details = drift_result['details']
            
            self.last_drift_check = timezone.now()
            self.save(update_fields=['drift_status', 'drift_score', 'drift_details', 'last_drift_check'])
            
            return {
                'success': True,
                'drift_status': self.drift_status,
                'drift_score': self.drift_score,
                'details': self.drift_details
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _compare_specs(self, desired, actual):
        """
        Compare desired and actual specs to detect drift.
        Returns dict with drift analysis results.
        """
        if desired == actual:
            return {
                'has_drift': False,
                'drift_score': 0.0,
                'details': {}
            }
        
        # TODO: Implement sophisticated spec comparison
        # For now, simple comparison
        differences = []
        drift_score = 0.0
        
        # Basic field comparison
        if isinstance(desired, dict) and isinstance(actual, dict):
            all_keys = set(desired.keys()) | set(actual.keys())
            differing_keys = []
            
            for key in all_keys:
                if key not in desired:
                    differences.append(f"Field '{key}' only in actual state")
                    differing_keys.append(key)
                elif key not in actual:
                    differences.append(f"Field '{key}' only in desired state")
                    differing_keys.append(key)
                elif desired[key] != actual[key]:
                    differences.append(f"Field '{key}' differs: desired={desired[key]}, actual={actual[key]}")
                    differing_keys.append(key)
            
            # Calculate drift score based on percentage of differing fields
            if all_keys:
                drift_score = len(differing_keys) / len(all_keys)
        else:
            # Non-dict comparison
            differences.append(f"Spec type differs: desired={type(desired)}, actual={type(actual)}")
            drift_score = 1.0
        
        return {
            'has_drift': len(differences) > 0,
            'drift_score': min(drift_score, 1.0),
            'details': {
                'differences': differences,
                'total_differences': len(differences),
                'comparison_type': 'basic'
            }
        }
    
    def get_drift_summary(self):
        """Get human-readable drift summary"""
        if not self.has_drift:
            return "Resource is in sync"
        
        status_messages = {
            'spec_drift': f"Configuration differs ({len(self.drift_details.get('differences', []))} differences)",
            'desired_only': "Resource defined in Git but not deployed to cluster",
            'actual_only': "Resource exists in cluster but not defined in Git",
            'creation_pending': "Resource creation is pending",
            'deletion_pending': "Resource deletion is pending"
        }
        
        return status_messages.get(self.drift_status, f"Unknown drift status: {self.drift_status}")
    
    # YAML generation and manipulation
    def generate_yaml_content(self):
        """Generate YAML content for this resource"""
        if not self.desired_spec:
            return None
        
        # Build Kubernetes manifest
        manifest = {
            'apiVersion': self.get_api_version(),
            'kind': self.kind,
            'metadata': {
                'name': self.name,
                'namespace': self.namespace,
            },
            'spec': self.desired_spec
        }
        
        # Add labels if present
        if self.labels:
            manifest['metadata']['labels'] = self.labels
        
        # Add annotations if present
        if self.annotations:
            manifest['metadata']['annotations'] = self.annotations
        
        # Add managed-by annotation
        if 'annotations' not in manifest['metadata']:
            manifest['metadata']['annotations'] = {}
        manifest['metadata']['annotations']['managed-by'] = 'hedgehog-netbox-plugin'
        
        return yaml.dump(manifest, default_flow_style=False)
    
    def get_api_version(self):
        """Return the Kubernetes API version for this resource type"""
        # Map common Hedgehog kinds to their API versions
        api_versions = {
            'VPC': 'vpc.githedgehog.com/v1beta1',
            'External': 'vpc.githedgehog.com/v1beta1',
            'ExternalAttachment': 'vpc.githedgehog.com/v1beta1',
            'ExternalPeering': 'vpc.githedgehog.com/v1beta1',
            'IPv4Namespace': 'vpc.githedgehog.com/v1beta1',
            'VPCAttachment': 'vpc.githedgehog.com/v1beta1',
            'VPCPeering': 'vpc.githedgehog.com/v1beta1',
            'Connection': 'wiring.githedgehog.com/v1beta1',
            'Server': 'wiring.githedgehog.com/v1beta1',
            'Switch': 'wiring.githedgehog.com/v1beta1',
            'SwitchGroup': 'wiring.githedgehog.com/v1beta1',
            'VLANNamespace': 'wiring.githedgehog.com/v1beta1',
        }
        
        return api_versions.get(self.kind, 'unknown/v1')
    
    # State management methods
    def update_desired_state(self, spec, commit_sha, file_path):
        """Update desired state from Git repository"""
        from django.utils import timezone
        
        self.desired_spec = spec
        self.desired_commit = commit_sha
        self.desired_file_path = file_path
        self.desired_updated = timezone.now()
        self.save(update_fields=['desired_spec', 'desired_commit', 'desired_file_path', 'desired_updated'])
        
        # Recalculate drift after state update
        drift_result = self.calculate_drift()
        
        # Update state based on drift
        if self.resource_state == ResourceStateChoices.SYNCED and drift_result.get('success'):
            if self.drift_status != 'in_sync':
                self.mark_as_drifted()
        
        return drift_result
    
    def update_actual_state(self, spec, status, resource_version):
        """Update actual state from Kubernetes cluster"""
        from django.utils import timezone
        
        self.actual_spec = spec
        self.actual_status = status
        self.actual_resource_version = resource_version
        self.actual_updated = timezone.now()
        self.save(update_fields=['actual_spec', 'actual_status', 'actual_resource_version', 'actual_updated'])
        
        # Recalculate drift after state update
        drift_result = self.calculate_drift()
        
        # Update state based on drift
        if self.resource_state == ResourceStateChoices.SYNCED and drift_result.get('success'):
            if self.drift_status != 'in_sync':
                self.mark_as_drifted()
        
        return drift_result
    
    def get_full_name(self):
        """Return the full Kubernetes resource name (namespace/kind/name)"""
        return f"{self.namespace}/{self.kind}/{self.name}"
    
    def get_status_summary(self):
        """Get comprehensive status summary for this resource"""
        return {
            'resource': {
                'name': self.name,
                'namespace': self.namespace,
                'kind': self.kind,
                'fabric': self.fabric.name
            },
            'desired_state': {
                'available': self.has_desired_state,
                'commit': self.desired_commit,
                'file_path': self.desired_file_path,
                'updated': self.desired_updated
            },
            'actual_state': {
                'available': self.has_actual_state,
                'resource_version': self.actual_resource_version,
                'updated': self.actual_updated
            },
            'drift': {
                'status': self.drift_status,
                'score': self.drift_score,
                'summary': self.get_drift_summary(),
                'last_check': self.last_drift_check
            },
            'flags': {
                'has_drift': self.has_drift,
                'is_orphaned': self.is_orphaned,
                'is_pending_creation': self.is_pending_creation
            }
        }


class StateTransitionHistory(NetBoxModel):
    """History of resource state transitions"""
    
    resource = models.ForeignKey(
        HedgehogResource,
        on_delete=models.CASCADE,
        related_name='state_history',
        help_text='Resource this transition belongs to'
    )
    
    # Transition details
    from_state = models.CharField(
        max_length=20,
        choices=ResourceStateChoices,
        help_text='Previous state'
    )
    
    to_state = models.CharField(
        max_length=20,
        choices=ResourceStateChoices,
        help_text='New state'
    )
    
    trigger = models.CharField(
        max_length=50,
        help_text='What triggered the transition'
    )
    
    reason = models.TextField(
        blank=True,
        help_text='Reason for transition'
    )
    
    # Context
    context = models.JSONField(
        default=dict,
        blank=True,
        help_text='Transition context'
    )
    
    # Timestamps
    timestamp = models.DateTimeField(
        auto_now_add=True,
        help_text='When transition occurred'
    )
    
    # User
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text='User who triggered transition'
    )
    
    class Meta:
        verbose_name = 'State Transition History'
        verbose_name_plural = 'State Transition Histories'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['resource', 'timestamp']),
            models.Index(fields=['resource', 'to_state']),
            models.Index(fields=['timestamp']),
            models.Index(fields=['from_state', 'to_state']),
        ]
    
    def __str__(self):
        return f"{self.resource.name}: {self.from_state} → {self.to_state}"
    
    def get_absolute_url(self):
        # TODO: Add proper URL when state history detail view is implemented  
        return f"/plugins/hedgehog/gitops/history/{self.pk}/"
    
    @property
    def duration_display(self):
        """Get human-readable duration since transition"""
        if not self.timestamp:
            return "Unknown"
        
        delta = timezone.now() - self.timestamp
        
        if delta.days > 0:
            return f"{delta.days} day{'s' if delta.days != 1 else ''} ago"
        elif delta.seconds > 3600:
            hours = delta.seconds // 3600
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif delta.seconds > 60:
            minutes = delta.seconds // 60
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        else:
            return "Just now"
    
    @property
    def is_successful_transition(self):
        """Check if this was a successful transition"""
        return self.from_state != self.to_state
    
    @property
    def transition_direction(self):
        """Get the direction of the transition"""
        state_order = {
            'draft': 1,
            'committed': 2,
            'pending': 3,
            'synced': 4,
            'drifted': 3,  # Drifted is a deviation from synced
            'orphaned': 0  # Orphaned is outside the normal flow
        }
        
        from_order = state_order.get(self.from_state, 0)
        to_order = state_order.get(self.to_state, 0)
        
        if from_order < to_order:
            return 'forward'
        elif from_order > to_order:
            return 'backward'
        else:
            return 'lateral'
    
    def get_transition_summary(self):
        """Get comprehensive transition summary"""
        return {
            'resource': {
                'name': self.resource.name,
                'kind': self.resource.kind,
                'namespace': self.resource.namespace,
                'fabric': self.resource.fabric.name
            },
            'transition': {
                'from_state': self.from_state,
                'to_state': self.to_state,
                'trigger': self.trigger,
                'reason': self.reason,
                'direction': self.transition_direction,
                'successful': self.is_successful_transition
            },
            'metadata': {
                'timestamp': self.timestamp,
                'duration_display': self.duration_display,
                'user': self.user.username if self.user else 'System',
                'context': self.context
            }
        }