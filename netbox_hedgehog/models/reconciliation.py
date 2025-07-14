from django.db import models
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from netbox.models import NetBoxModel
from utilities.choices import ChoiceSet
import json
from datetime import datetime, timedelta


class AlertSeverityChoices(ChoiceSet):
    """Alert severity levels for reconciliation alerts"""
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    CRITICAL = 'critical'
    
    CHOICES = [
        (LOW, 'Low'),
        (MEDIUM, 'Medium'),
        (HIGH, 'High'),
        (CRITICAL, 'Critical'),
    ]


class AlertStatusChoices(ChoiceSet):
    """Alert status choices for reconciliation alerts"""
    ACTIVE = 'active'
    ACKNOWLEDGED = 'acknowledged'
    RESOLVED = 'resolved'
    SUPPRESSED = 'suppressed'
    
    CHOICES = [
        (ACTIVE, 'Active'),
        (ACKNOWLEDGED, 'Acknowledged'),
        (RESOLVED, 'Resolved'),
        (SUPPRESSED, 'Suppressed'),
    ]


class ResolutionActionChoices(ChoiceSet):
    """Resolution action choices for reconciliation alerts"""
    IMPORT_TO_GIT = 'import_to_git'
    DELETE_FROM_CLUSTER = 'delete_from_cluster'
    UPDATE_GIT = 'update_git'
    IGNORE = 'ignore'
    MANUAL_REVIEW = 'manual_review'
    
    CHOICES = [
        (IMPORT_TO_GIT, 'Import to Git'),
        (DELETE_FROM_CLUSTER, 'Delete from Cluster'),
        (UPDATE_GIT, 'Update Git'),
        (IGNORE, 'Ignore'),
        (MANUAL_REVIEW, 'Manual Review'),
    ]


class ReconciliationAlert(NetBoxModel):
    """
    Reconciliation alert for tracking drift detection and resolution workflows.
    Manages the alert queue system for GitOps reconciliation operations.
    """
    
    # Resource identification
    fabric = models.ForeignKey(
        'netbox_hedgehog.HedgehogFabric',
        on_delete=models.CASCADE,
        related_name='reconciliation_alerts',
        help_text="Hedgehog fabric this alert belongs to"
    )
    
    resource = models.ForeignKey(
        'netbox_hedgehog.HedgehogResource',
        on_delete=models.CASCADE,
        related_name='reconciliation_alerts',
        help_text="Resource this alert is for"
    )
    
    # Alert details
    alert_type = models.CharField(
        max_length=50,
        choices=[
            ('drift_detected', 'Drift Detected'),
            ('orphaned_resource', 'Orphaned Resource'),
            ('creation_pending', 'Creation Pending'),
            ('deletion_pending', 'Deletion Pending'),
            ('sync_failure', 'Sync Failure'),
            ('validation_error', 'Validation Error'),
            ('conflict_detected', 'Conflict Detected'),
        ],
        help_text="Type of reconciliation alert"
    )
    
    severity = models.CharField(
        max_length=20,
        choices=AlertSeverityChoices,
        default=AlertSeverityChoices.MEDIUM,
        help_text="Alert severity level"
    )
    
    status = models.CharField(
        max_length=20,
        choices=AlertStatusChoices,
        default=AlertStatusChoices.ACTIVE,
        help_text="Current alert status"
    )
    
    title = models.CharField(
        max_length=200,
        help_text="Alert title"
    )
    
    message = models.TextField(
        help_text="Detailed alert message"
    )
    
    # Alert context
    alert_context = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional context for the alert"
    )
    
    drift_details = models.JSONField(
        default=dict,
        blank=True,
        help_text="Drift analysis details"
    )
    
    # Resolution workflow
    suggested_action = models.CharField(
        max_length=30,
        choices=ResolutionActionChoices,
        default=ResolutionActionChoices.MANUAL_REVIEW,
        help_text="Suggested resolution action"
    )
    
    resolved_action = models.CharField(
        max_length=30,
        choices=ResolutionActionChoices,
        blank=True,
        help_text="Action taken to resolve the alert"
    )
    
    resolution_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Metadata about the resolution"
    )
    
    # Timestamps
    created = models.DateTimeField(
        auto_now_add=True,
        help_text="When alert was created"
    )
    
    acknowledged_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When alert was acknowledged"
    )
    
    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When alert was resolved"
    )
    
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When alert expires if not resolved"
    )
    
    # User tracking
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_alerts',
        help_text="User who created this alert"
    )
    
    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='acknowledged_alerts',
        help_text="User who acknowledged this alert"
    )
    
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_alerts',
        help_text="User who resolved this alert"
    )
    
    # Queue management
    queue_priority = models.PositiveIntegerField(
        default=100,
        help_text="Queue priority (lower numbers = higher priority)"
    )
    
    processing_attempts = models.PositiveIntegerField(
        default=0,
        help_text="Number of processing attempts"
    )
    
    last_processing_attempt = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last processing attempt timestamp"
    )
    
    processing_error = models.TextField(
        blank=True,
        help_text="Last processing error message"
    )
    
    # Batch processing
    batch_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="Batch ID for grouped processing"
    )
    
    related_alerts = models.ManyToManyField(
        'self',
        symmetrical=False,
        blank=True,
        help_text="Related alerts for batch processing"
    )
    
    class Meta:
        verbose_name = "Reconciliation Alert"
        verbose_name_plural = "Reconciliation Alerts"
        ordering = ['-created', 'queue_priority']
        indexes = [
            models.Index(fields=['fabric', 'status']),
            models.Index(fields=['resource', 'status']),
            models.Index(fields=['status', 'queue_priority']),
            models.Index(fields=['alert_type', 'severity']),
            models.Index(fields=['created', 'status']),
            models.Index(fields=['expires_at']),
            models.Index(fields=['batch_id']),
            models.Index(fields=['fabric', 'alert_type', 'status']),
        ]
    
    def __str__(self):
        return f"{self.alert_type}: {self.resource.name} ({self.severity})"
    
    def get_absolute_url(self):
        return reverse('plugins:netbox_hedgehog:reconciliation_alert_detail', kwargs={'pk': self.pk})
    
    def clean(self):
        """Validate reconciliation alert before saving"""
        super().clean()
        
        # Validate severity calculation
        if self.severity not in [choice[0] for choice in AlertSeverityChoices.CHOICES]:
            raise ValidationError({
                'severity': 'Invalid severity level'
            })
        
        # Validate queue priority
        if self.queue_priority < 1 or self.queue_priority > 1000:
            raise ValidationError({
                'queue_priority': 'Queue priority must be between 1 and 1000'
            })
        
        # Validate expiry date
        if self.expires_at and self.expires_at <= timezone.now():
            raise ValidationError({
                'expires_at': 'Expiry date must be in the future'
            })
    
    def save(self, *args, **kwargs):
        """Override save to set calculated fields"""
        # Set expiry date if not provided
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=30)
        
        # Calculate queue priority based on severity and age
        self.queue_priority = self.calculate_queue_priority()
        
        super().save(*args, **kwargs)
    
    def calculate_queue_priority(self):
        """Calculate queue priority based on severity and age"""
        # Base priority by severity
        severity_priority = {
            AlertSeverityChoices.CRITICAL: 10,
            AlertSeverityChoices.HIGH: 30,
            AlertSeverityChoices.MEDIUM: 50,
            AlertSeverityChoices.LOW: 70
        }
        
        base_priority = severity_priority.get(self.severity, 50)
        
        # Age factor (older alerts get higher priority)
        if self.created:
            age_hours = (timezone.now() - self.created).total_seconds() / 3600
            age_factor = min(int(age_hours), 20)  # Cap at 20 hours
            return max(base_priority - age_factor, 1)
        
        return base_priority
    
    def calculate_severity(self):
        """Calculate alert severity based on drift details and context"""
        # Critical conditions
        if self.alert_type == 'orphaned_resource':
            return AlertSeverityChoices.CRITICAL
        
        if self.alert_type == 'conflict_detected':
            return AlertSeverityChoices.CRITICAL
        
        # High severity conditions
        if self.alert_type == 'sync_failure':
            return AlertSeverityChoices.HIGH
        
        if self.alert_type == 'validation_error':
            return AlertSeverityChoices.HIGH
        
        # Medium severity for drift
        if self.alert_type == 'drift_detected':
            drift_score = self.drift_details.get('drift_score', 0.0)
            if drift_score >= 0.8:
                return AlertSeverityChoices.HIGH
            elif drift_score >= 0.5:
                return AlertSeverityChoices.MEDIUM
            else:
                return AlertSeverityChoices.LOW
        
        # Default to medium
        return AlertSeverityChoices.MEDIUM
    
    def auto_calculate_severity(self):
        """Auto-calculate and update severity"""
        calculated_severity = self.calculate_severity()
        if calculated_severity != self.severity:
            self.severity = calculated_severity
            self.save(update_fields=['severity'])
        return calculated_severity
    
    def acknowledge(self, user=None):
        """Acknowledge this alert"""
        if self.status != AlertStatusChoices.ACTIVE:
            return {
                'success': False,
                'error': f'Alert is not active (current status: {self.status})'
            }
        
        self.status = AlertStatusChoices.ACKNOWLEDGED
        self.acknowledged_at = timezone.now()
        self.acknowledged_by = user
        self.save(update_fields=['status', 'acknowledged_at', 'acknowledged_by'])
        
        return {
            'success': True,
            'message': 'Alert acknowledged successfully'
        }
    
    def resolve(self, action, user=None, metadata=None):
        """Resolve this alert with specified action"""
        if self.status == AlertStatusChoices.RESOLVED:
            return {
                'success': False,
                'error': 'Alert is already resolved'
            }
        
        if action not in [choice[0] for choice in ResolutionActionChoices.CHOICES]:
            return {
                'success': False,
                'error': f'Invalid resolution action: {action}'
            }
        
        self.status = AlertStatusChoices.RESOLVED
        self.resolved_action = action
        self.resolved_at = timezone.now()
        self.resolved_by = user
        
        if metadata:
            self.resolution_metadata = metadata
        
        self.save(update_fields=[
            'status', 'resolved_action', 'resolved_at', 'resolved_by', 'resolution_metadata'
        ])
        
        return {
            'success': True,
            'message': f'Alert resolved with action: {action}'
        }
    
    def suppress(self, user=None, reason=None):
        """Suppress this alert"""
        if self.status == AlertStatusChoices.RESOLVED:
            return {
                'success': False,
                'error': 'Cannot suppress resolved alert'
            }
        
        self.status = AlertStatusChoices.SUPPRESSED
        self.resolved_at = timezone.now()
        self.resolved_by = user
        
        if reason:
            self.resolution_metadata = {'suppression_reason': reason}
        
        self.save(update_fields=['status', 'resolved_at', 'resolved_by', 'resolution_metadata'])
        
        return {
            'success': True,
            'message': 'Alert suppressed successfully'
        }
    
    def get_suggested_actions(self):
        """Get suggested resolution actions based on alert type and context"""
        actions = []
        
        if self.alert_type == 'orphaned_resource':
            actions = [
                {
                    'action': ResolutionActionChoices.IMPORT_TO_GIT,
                    'description': 'Import orphaned resource to Git repository',
                    'priority': 1
                },
                {
                    'action': ResolutionActionChoices.DELETE_FROM_CLUSTER,
                    'description': 'Delete orphaned resource from cluster',
                    'priority': 2
                },
                {
                    'action': ResolutionActionChoices.IGNORE,
                    'description': 'Ignore this orphaned resource',
                    'priority': 3
                }
            ]
        
        elif self.alert_type == 'drift_detected':
            actions = [
                {
                    'action': ResolutionActionChoices.UPDATE_GIT,
                    'description': 'Update Git to match cluster state',
                    'priority': 1
                },
                {
                    'action': ResolutionActionChoices.IMPORT_TO_GIT,
                    'description': 'Import changes to Git repository',
                    'priority': 2
                },
                {
                    'action': ResolutionActionChoices.IGNORE,
                    'description': 'Ignore this drift',
                    'priority': 3
                }
            ]
        
        elif self.alert_type == 'creation_pending':
            actions = [
                {
                    'action': ResolutionActionChoices.MANUAL_REVIEW,
                    'description': 'Review and approve resource creation',
                    'priority': 1
                },
                {
                    'action': ResolutionActionChoices.IGNORE,
                    'description': 'Ignore pending creation',
                    'priority': 2
                }
            ]
        
        elif self.alert_type == 'deletion_pending':
            actions = [
                {
                    'action': ResolutionActionChoices.MANUAL_REVIEW,
                    'description': 'Review and approve resource deletion',
                    'priority': 1
                },
                {
                    'action': ResolutionActionChoices.IGNORE,
                    'description': 'Ignore pending deletion',
                    'priority': 2
                }
            ]
        
        else:
            actions = [
                {
                    'action': ResolutionActionChoices.MANUAL_REVIEW,
                    'description': 'Manual review required',
                    'priority': 1
                }
            ]
        
        return sorted(actions, key=lambda x: x['priority'])
    
    def execute_resolution_action(self, action, user=None, dry_run=False):
        """Execute the specified resolution action"""
        if action not in [choice[0] for choice in ResolutionActionChoices.CHOICES]:
            return {
                'success': False,
                'error': f'Invalid action: {action}'
            }
        
        execution_result = {
            'action': action,
            'dry_run': dry_run,
            'success': False,
            'message': '',
            'details': {}
        }
        
        try:
            if action == ResolutionActionChoices.IMPORT_TO_GIT:
                result = self._execute_import_to_git(dry_run)
            elif action == ResolutionActionChoices.DELETE_FROM_CLUSTER:
                result = self._execute_delete_from_cluster(dry_run)
            elif action == ResolutionActionChoices.UPDATE_GIT:
                result = self._execute_update_git(dry_run)
            elif action == ResolutionActionChoices.IGNORE:
                result = self._execute_ignore(dry_run)
            elif action == ResolutionActionChoices.MANUAL_REVIEW:
                result = self._execute_manual_review(dry_run)
            else:
                result = {
                    'success': False,
                    'error': f'Action {action} not implemented'
                }
            
            execution_result.update(result)
            
            # If successful and not dry run, resolve the alert
            if result.get('success') and not dry_run:
                resolve_result = self.resolve(action, user, result.get('details', {}))
                execution_result['resolved'] = resolve_result
            
        except Exception as e:
            execution_result['success'] = False
            execution_result['error'] = str(e)
        
        return execution_result
    
    def _execute_import_to_git(self, dry_run=False):
        """Execute import to Git action"""
        if not self.resource.has_actual_state:
            return {
                'success': False,
                'error': 'No actual state to import'
            }
        
        if dry_run:
            return {
                'success': True,
                'message': 'Would import resource to Git repository',
                'details': {
                    'resource_name': self.resource.name,
                    'resource_kind': self.resource.kind,
                    'yaml_content': self.resource.generate_yaml_content()
                }
            }
        
        # TODO: Implement actual Git import
        return {
            'success': True,
            'message': 'Resource imported to Git repository (placeholder)',
            'details': {
                'resource_name': self.resource.name,
                'resource_kind': self.resource.kind,
                'implementation': 'pending'
            }
        }
    
    def _execute_delete_from_cluster(self, dry_run=False):
        """Execute delete from cluster action"""
        if not self.resource.has_actual_state:
            return {
                'success': False,
                'error': 'No actual state to delete'
            }
        
        if dry_run:
            return {
                'success': True,
                'message': 'Would delete resource from cluster',
                'details': {
                    'resource_name': self.resource.name,
                    'resource_kind': self.resource.kind,
                    'namespace': self.resource.namespace
                }
            }
        
        # TODO: Implement actual cluster deletion
        return {
            'success': True,
            'message': 'Resource deleted from cluster (placeholder)',
            'details': {
                'resource_name': self.resource.name,
                'resource_kind': self.resource.kind,
                'implementation': 'pending'
            }
        }
    
    def _execute_update_git(self, dry_run=False):
        """Execute update Git action"""
        if not self.resource.has_actual_state:
            return {
                'success': False,
                'error': 'No actual state to update Git with'
            }
        
        if dry_run:
            return {
                'success': True,
                'message': 'Would update Git with cluster state',
                'details': {
                    'resource_name': self.resource.name,
                    'resource_kind': self.resource.kind,
                    'changes': self.drift_details.get('differences', [])
                }
            }
        
        # TODO: Implement actual Git update
        return {
            'success': True,
            'message': 'Git updated with cluster state (placeholder)',
            'details': {
                'resource_name': self.resource.name,
                'resource_kind': self.resource.kind,
                'implementation': 'pending'
            }
        }
    
    def _execute_ignore(self, dry_run=False):
        """Execute ignore action"""
        return {
            'success': True,
            'message': 'Alert ignored as requested',
            'details': {
                'resource_name': self.resource.name,
                'alert_type': self.alert_type,
                'ignored_at': timezone.now().isoformat()
            }
        }
    
    def _execute_manual_review(self, dry_run=False):
        """Execute manual review action"""
        return {
            'success': True,
            'message': 'Alert marked for manual review',
            'details': {
                'resource_name': self.resource.name,
                'alert_type': self.alert_type,
                'review_required': True
            }
        }
    
    def get_alert_summary(self):
        """Get comprehensive alert summary"""
        return {
            'alert': {
                'id': self.id,
                'type': self.alert_type,
                'severity': self.severity,
                'status': self.status,
                'title': self.title,
                'message': self.message
            },
            'resource': {
                'name': self.resource.name,
                'kind': self.resource.kind,
                'namespace': self.resource.namespace,
                'fabric': self.fabric.name
            },
            'timing': {
                'created': self.created,
                'acknowledged_at': self.acknowledged_at,
                'resolved_at': self.resolved_at,
                'expires_at': self.expires_at
            },
            'resolution': {
                'suggested_action': self.suggested_action,
                'resolved_action': self.resolved_action,
                'suggested_actions': self.get_suggested_actions()
            },
            'queue': {
                'priority': self.queue_priority,
                'processing_attempts': self.processing_attempts,
                'last_processing_attempt': self.last_processing_attempt
            }
        }
    
    @property
    def is_active(self):
        """Check if alert is active"""
        return self.status == AlertStatusChoices.ACTIVE
    
    @property
    def is_expired(self):
        """Check if alert has expired"""
        return self.expires_at and self.expires_at <= timezone.now()
    
    @property
    def age_hours(self):
        """Get alert age in hours"""
        if self.created:
            return (timezone.now() - self.created).total_seconds() / 3600
        return 0
    
    @property
    def time_to_resolution(self):
        """Get time to resolution in hours"""
        if self.created and self.resolved_at:
            return (self.resolved_at - self.created).total_seconds() / 3600
        return None
    
    @classmethod
    def get_queue_stats(cls, fabric=None):
        """Get queue statistics"""
        queryset = cls.objects.all()
        if fabric:
            queryset = queryset.filter(fabric=fabric)
        
        stats = {
            'total_alerts': queryset.count(),
            'active_alerts': queryset.filter(status=AlertStatusChoices.ACTIVE).count(),
            'acknowledged_alerts': queryset.filter(status=AlertStatusChoices.ACKNOWLEDGED).count(),
            'resolved_alerts': queryset.filter(status=AlertStatusChoices.RESOLVED).count(),
            'suppressed_alerts': queryset.filter(status=AlertStatusChoices.SUPPRESSED).count(),
            'by_severity': {}
        }
        
        for severity in AlertSeverityChoices.CHOICES:
            stats['by_severity'][severity[0]] = queryset.filter(severity=severity[0]).count()
        
        return stats