# SyncOperation model definition for HNP bidirectional sync

from django.db import models
from django.contrib.auth.models import User

from netbox.models import NetBoxModel
from .fabric import HedgehogFabric


class SyncOperation(NetBoxModel):
    """
    Track bidirectional synchronization operations between HNP GUI and GitHub repository
    """
    
    OPERATION_TYPE_CHOICES = [
        ('gui_to_github', 'GUI to GitHub'),
        ('github_to_gui', 'GitHub to GUI'),
        ('directory_init', 'Directory Initialization'),
        ('conflict_resolution', 'Conflict Resolution'),
        ('ingestion', 'File Ingestion')
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled')
    ]
    
    fabric = models.ForeignKey(
        HedgehogFabric,
        on_delete=models.CASCADE,
        related_name='sync_operations'
    )
    
    operation_type = models.CharField(
        max_length=30,
        choices=OPERATION_TYPE_CHOICES
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    details = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    
    files_processed = models.PositiveIntegerField(default=0)
    files_created = models.PositiveIntegerField(default=0)
    files_updated = models.PositiveIntegerField(default=0)
    files_deleted = models.PositiveIntegerField(default=0)
    
    commit_sha = models.CharField(max_length=40, blank=True)
    pull_request_url = models.URLField(blank=True)
    
    initiated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    class Meta:
        verbose_name = 'Sync Operation'
        verbose_name_plural = 'Sync Operations'
        ordering = ['-started_at']
    
    def __str__(self):
        return f"{self.get_operation_type_display()} - {self.fabric.name} ({self.get_status_display()})"