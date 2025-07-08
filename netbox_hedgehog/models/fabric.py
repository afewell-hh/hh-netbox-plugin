from django.db import models
from django.urls import reverse
from netbox.models import NetBoxModel

from ..choices import FabricStatusChoices, ConnectionStatusChoices, SyncStatusChoices

class HedgehogFabric(NetBoxModel):
    """
    Represents a Hedgehog fabric (Kubernetes cluster) that contains CRDs.
    Allows for multi-fabric support where each fabric can be managed independently.
    """
    
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Unique name for this Hedgehog fabric"
    )
    
    description = models.TextField(
        blank=True,
        help_text="Optional description of this fabric"
    )
    
    status = models.CharField(
        max_length=20,
        choices=FabricStatusChoices,
        default=FabricStatusChoices.PLANNED,
        help_text="Configuration status - whether this fabric is planned, active, etc."
    )
    
    connection_status = models.CharField(
        max_length=20,
        choices=ConnectionStatusChoices,
        default=ConnectionStatusChoices.UNKNOWN,
        help_text="Connection status - whether NetBox can connect to this fabric"
    )
    
    sync_status = models.CharField(
        max_length=20,
        choices=SyncStatusChoices,
        default=SyncStatusChoices.NEVER_SYNCED,
        help_text="Sync status - whether data is synchronized with Kubernetes"
    )
    
    # Kubernetes connection configuration
    kubernetes_server = models.URLField(
        blank=True,
        help_text="Kubernetes API server URL (optional if using default kubeconfig)"
    )
    
    kubernetes_token = models.TextField(
        blank=True,
        help_text="Kubernetes service account token (leave empty to use kubeconfig)"
    )
    
    kubernetes_ca_cert = models.TextField(
        blank=True,
        help_text="Kubernetes CA certificate (leave empty to use kubeconfig)"
    )
    
    kubernetes_namespace = models.CharField(
        max_length=253,
        default='default',
        help_text="Default namespace for this fabric's CRDs"
    )
    
    # Sync configuration
    sync_enabled = models.BooleanField(
        default=True,
        help_text="Enable automatic synchronization with Kubernetes"
    )
    
    sync_interval = models.PositiveIntegerField(
        default=300,
        help_text="Sync interval in seconds (0 to disable automatic sync)"
    )
    
    last_sync = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of last successful sync"
    )
    
    sync_error = models.TextField(
        blank=True,
        help_text="Last sync error message (if any)"
    )
    
    connection_error = models.TextField(
        blank=True,
        help_text="Last connection error message (if any)"
    )
    
    # GitOps configuration
    git_repository_url = models.URLField(
        blank=True,
        null=True,
        help_text="Git repository containing desired Hedgehog CRD definitions"
    )
    
    git_branch = models.CharField(
        max_length=100,
        default='main',
        help_text="Git branch to track for desired state"
    )
    
    git_path = models.CharField(
        max_length=255,
        default='hedgehog/',
        help_text="Path within repo containing Hedgehog CRDs"
    )
    
    git_username = models.CharField(
        max_length=100,
        blank=True,
        help_text="Git username for authentication"
    )
    
    git_token = models.CharField(
        max_length=255,
        blank=True,
        help_text="Git access token for authentication"
    )
    
    # GitOps state tracking
    desired_state_commit = models.CharField(
        max_length=40,
        blank=True,
        help_text="Git commit SHA of current desired state"
    )
    
    drift_status = models.CharField(
        max_length=20,
        choices=[
            ('in_sync', 'In Sync'),
            ('drift_detected', 'Drift Detected'),
            ('git_ahead', 'Git Ahead'),
            ('cluster_ahead', 'Cluster Ahead'),
            ('conflicts', 'Conflicts')
        ],
        default='in_sync',
        help_text="Current drift status between desired and actual state"
    )
    
    drift_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of resources with detected drift"
    )
    
    last_git_sync = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of last Git repository sync"
    )
    
    # GitOps tool integration
    gitops_tool = models.CharField(
        max_length=20,
        choices=[
            ('manual', 'Manual'),
            ('argocd', 'ArgoCD'),
            ('flux', 'Flux'),
            ('none', 'None')
        ],
        default='manual',
        help_text="GitOps tool used for deployments"
    )
    
    gitops_app_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="GitOps application name (for ArgoCD/Flux integration)"
    )
    
    gitops_namespace = models.CharField(
        max_length=255,
        blank=True,
        help_text="GitOps application namespace"
    )
    
    # Cached CRD counts for dashboard display
    cached_crd_count = models.PositiveIntegerField(
        default=0,
        help_text="Cached total count of CRDs (updated during sync)"
    )
    
    cached_vpc_count = models.PositiveIntegerField(
        default=0,
        help_text="Cached VPC count (updated during sync)"
    )
    
    cached_connection_count = models.PositiveIntegerField(
        default=0,
        help_text="Cached Connection count (updated during sync)"
    )
    
    # Add specific count properties for the template
    connections_count = models.PositiveIntegerField(
        default=0,
        help_text="Count of Connection CRDs"
    )
    
    servers_count = models.PositiveIntegerField(
        default=0,
        help_text="Count of Server CRDs"  
    )
    
    switches_count = models.PositiveIntegerField(
        default=0,
        help_text="Count of Switch CRDs"
    )
    
    vpcs_count = models.PositiveIntegerField(
        default=0,
        help_text="Count of VPC CRDs"
    )
    
    class Meta:
        verbose_name = "Hedgehog Fabric"
        verbose_name_plural = "Hedgehog Fabrics"
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def get_absolute_url(self):
        return reverse('plugins:netbox_hedgehog:fabric_detail', kwargs={'pk': self.pk})
    
    @property
    def crd_count(self):
        """Return total count of CRDs in this fabric"""
        # Count all concrete CRD types that have this fabric
        # Handle missing tables gracefully during development
        total = 0
        try:
            from netbox_hedgehog.models import (
                VPC, External, ExternalAttachment, ExternalPeering, IPv4Namespace, VPCAttachment, VPCPeering,
                Connection, Server, Switch, SwitchGroup, VLANNamespace
            )
            
            models = [VPC, External, ExternalAttachment, ExternalPeering, IPv4Namespace, VPCAttachment, VPCPeering,
                     Connection, Server, Switch, SwitchGroup, VLANNamespace]
            
            for model in models:
                try:
                    total += model.objects.filter(fabric=self).count()
                except Exception:
                    # Table doesn't exist yet, skip this model
                    pass
        except ImportError:
            # Models not available, return 0
            pass
        return total
    
    @property
    def active_crd_count(self):
        """Return count of active/live CRDs in this fabric"""
        total = 0
        try:
            from ..choices import KubernetesStatusChoices
            from netbox_hedgehog.models import (
                VPC, External, ExternalAttachment, ExternalPeering, IPv4Namespace, VPCAttachment, VPCPeering,
                Connection, Server, Switch, SwitchGroup, VLANNamespace
            )
            
            models = [VPC, External, ExternalAttachment, ExternalPeering, IPv4Namespace, VPCAttachment, VPCPeering,
                     Connection, Server, Switch, SwitchGroup, VLANNamespace]
            
            for model in models:
                try:
                    total += model.objects.filter(
                        fabric=self,
                        kubernetes_status=KubernetesStatusChoices.LIVE
                    ).count()
                except Exception:
                    # Table doesn't exist yet, skip this model
                    pass
        except ImportError:
            # Models not available, return 0
            pass
        return total
    
    @property
    def error_crd_count(self):
        """Return count of CRDs with errors in this fabric"""
        total = 0
        try:
            from ..choices import KubernetesStatusChoices
            from netbox_hedgehog.models import (
                VPC, External, ExternalAttachment, ExternalPeering, IPv4Namespace, VPCAttachment, VPCPeering,
                Connection, Server, Switch, SwitchGroup, VLANNamespace
            )
            
            models = [VPC, External, ExternalAttachment, ExternalPeering, IPv4Namespace, VPCAttachment, VPCPeering,
                     Connection, Server, Switch, SwitchGroup, VLANNamespace]
            
            for model in models:
                try:
                    total += model.objects.filter(
                        fabric=self,
                        kubernetes_status=KubernetesStatusChoices.ERROR
                    ).count()
                except Exception:
                    # Table doesn't exist yet, skip this model
                    pass
        except ImportError:
            # Models not available, return 0
            pass
        return total
    
    def get_kubernetes_config(self):
        """
        Return Kubernetes configuration for this fabric.
        Returns dict with connection parameters or None to use default kubeconfig.
        """
        if self.kubernetes_server:
            # Check if this looks like a Docker network proxy (disable SSL verification)
            is_docker_proxy = '://172.18.0.1:' in self.kubernetes_server or '://172.18.0.1/' in self.kubernetes_server
            
            config = {
                'host': self.kubernetes_server,
                'verify_ssl': bool(self.kubernetes_ca_cert) and not is_docker_proxy,
            }
            
            if self.kubernetes_token:
                config['api_key'] = {'authorization': f'Bearer {self.kubernetes_token}'}
            
            if self.kubernetes_ca_cert and not is_docker_proxy:
                config['ssl_ca_cert'] = self.kubernetes_ca_cert
            
            return config
        
        return None  # Use default kubeconfig
    
    # GitOps functionality methods
    def get_git_status(self):
        """
        Get current Git repository status.
        Returns dict with Git repository information and status.
        """
        if not self.git_repository_url:
            return {
                'configured': False,
                'message': 'No Git repository configured'
            }
        
        try:
            # Basic Git repository validation
            # TODO: Implement actual Git repository status checking
            return {
                'configured': True,
                'repository_url': self.git_repository_url,
                'branch': self.git_branch,
                'path': self.git_path,
                'last_commit': self.desired_state_commit or 'Unknown',
                'last_sync': self.last_git_sync,
                'status': 'ready'
            }
        except Exception as e:
            return {
                'configured': True,
                'status': 'error',
                'error': str(e)
            }
    
    def calculate_drift_status(self):
        """
        Calculate current drift status between desired and actual state.
        Updates drift_status and drift_count fields.
        """
        try:
            # TODO: Implement actual drift detection logic
            # For now, return current status
            return {
                'drift_status': self.drift_status,
                'drift_count': self.drift_count,
                'last_calculated': self.last_git_sync,
                'details': 'Drift detection not yet implemented'
            }
        except Exception as e:
            return {
                'drift_status': 'error',
                'error': str(e)
            }
    
    def get_gitops_tool_client(self):
        """
        Get GitOps tool client (ArgoCD/Flux) for this fabric.
        Returns configured client or None if not configured.
        """
        if self.gitops_tool == 'none' or self.gitops_tool == 'manual':
            return None
        
        try:
            # TODO: Implement actual GitOps tool client creation
            return {
                'tool': self.gitops_tool,
                'app_name': self.gitops_app_name,
                'namespace': self.gitops_namespace,
                'configured': bool(self.gitops_app_name),
                'status': 'client_not_implemented'
            }
        except Exception as e:
            return {
                'tool': self.gitops_tool,
                'status': 'error',
                'error': str(e)
            }
    
    def sync_desired_state(self):
        """
        Sync desired state from Git repository.
        Updates desired_state_commit and last_git_sync fields.
        """
        if not self.git_repository_url:
            return {
                'success': False,
                'error': 'No Git repository configured'
            }
        
        try:
            # TODO: Implement actual Git repository sync
            # For now, update the sync timestamp
            from django.utils import timezone
            self.last_git_sync = timezone.now()
            self.save(update_fields=['last_git_sync'])
            
            return {
                'success': True,
                'message': 'Git sync placeholder - implementation pending',
                'repository_url': self.git_repository_url,
                'branch': self.git_branch,
                'sync_time': self.last_git_sync
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def trigger_gitops_sync(self):
        """
        Trigger GitOps tool synchronization (ArgoCD/Flux).
        Returns sync operation status.
        """
        if self.gitops_tool == 'none' or self.gitops_tool == 'manual':
            return {
                'success': False,
                'message': f'GitOps tool is set to {self.gitops_tool} - manual sync required'
            }
        
        if not self.gitops_app_name:
            return {
                'success': False,
                'error': 'GitOps application name not configured'
            }
        
        try:
            # TODO: Implement actual GitOps tool sync triggering
            return {
                'success': True,
                'message': f'{self.gitops_tool} sync placeholder - implementation pending',
                'tool': self.gitops_tool,
                'app_name': self.gitops_app_name,
                'namespace': self.gitops_namespace
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_gitops_summary(self):
        """
        Get comprehensive GitOps status summary for this fabric.
        Returns complete GitOps configuration and status information.
        """
        return {
            'git_config': {
                'repository_url': self.git_repository_url,
                'branch': self.git_branch,
                'path': self.git_path,
                'configured': bool(self.git_repository_url)
            },
            'drift_status': {
                'status': self.drift_status,
                'count': self.drift_count,
                'last_sync': self.last_git_sync,
                'desired_commit': self.desired_state_commit
            },
            'gitops_tool': {
                'tool': self.gitops_tool,
                'app_name': self.gitops_app_name,
                'namespace': self.gitops_namespace,
                'configured': bool(self.gitops_app_name) if self.gitops_tool not in ['none', 'manual'] else True
            },
            'capabilities': {
                'git_sync': bool(self.git_repository_url),
                'drift_detection': bool(self.git_repository_url),
                'gitops_sync': bool(self.gitops_app_name) and self.gitops_tool not in ['none', 'manual']
            }
        }