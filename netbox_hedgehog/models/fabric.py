import logging
from django.db import models
from django.urls import reverse
from netbox.models import NetBoxModel

from ..choices import FabricStatusChoices, ConnectionStatusChoices, SyncStatusChoices

logger = logging.getLogger(__name__)

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
    
    # GitOps configuration (NEW ARCHITECTURE - Separated Concerns)
    git_repository = models.ForeignKey(
        'GitRepository',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Reference to authenticated git repository (separated architecture)"
    )
    
    gitops_directory = models.CharField(
        max_length=500,
        default='/',
        help_text="Directory path within repository for this fabric's CRDs"
    )
    
    # Legacy GitOps configuration (DEPRECATED - will be migrated)
    # These fields are kept temporarily for migration compatibility
    git_repository_url = models.URLField(
        blank=True,
        null=True,
        help_text="[DEPRECATED] Git repository URL - use git_repository field instead"
    )
    
    git_branch = models.CharField(
        max_length=100,
        default='main',
        help_text="[DEPRECATED] Git branch - managed by GitRepository"
    )
    
    git_path = models.CharField(
        max_length=255,
        default='hedgehog/',
        help_text="[DEPRECATED] Git path - use gitops_directory field instead"
    )
    
    git_username = models.CharField(
        max_length=100,
        blank=True,
        help_text="[DEPRECATED] Git username - managed by GitRepository"
    )
    
    git_token = models.CharField(
        max_length=255,
        blank=True,
        help_text="[DEPRECATED] Git token - managed by GitRepository"
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
            ('tekton', 'Tekton'),
            ('jenkins', 'Jenkins'),
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
    
    # ArgoCD tracking fields (Week 2 MVP2)
    argocd_installed = models.BooleanField(
        default=False,
        help_text="Whether ArgoCD is installed and configured for this fabric"
    )
    
    argocd_version = models.CharField(
        max_length=50,
        blank=True,
        help_text="Version of ArgoCD installed"
    )
    
    argocd_server_url = models.URLField(
        blank=True,
        help_text="ArgoCD server URL for this fabric"
    )
    
    argocd_health_status = models.CharField(
        max_length=20,
        choices=[
            ('unknown', 'Unknown'),
            ('healthy', 'Healthy'),
            ('unhealthy', 'Unhealthy'),
            ('degraded', 'Degraded'),
            ('installing', 'Installing'),
            ('failed', 'Failed')
        ],
        default='unknown',
        help_text="Current ArgoCD health status"
    )
    
    argocd_installation_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When ArgoCD was installed for this fabric"
    )
    
    argocd_admin_password = models.CharField(
        max_length=255,
        blank=True,
        help_text="ArgoCD admin password (encrypted)"
    )
    
    gitops_setup_status = models.CharField(
        max_length=30,
        choices=[
            ('not_configured', 'Not Configured'),
            ('manual', 'Manual'),
            ('installing', 'Installing'),
            ('configured', 'Configured'),
            ('ready', 'Ready'),
            ('error', 'Error')
        ],
        default='not_configured',
        help_text="Overall GitOps setup status for this fabric"
    )
    
    gitops_setup_error = models.TextField(
        blank=True,
        help_text="Last GitOps setup error message"
    )
    
    auto_sync_enabled = models.BooleanField(
        default=True,
        help_text="Enable automatic synchronization for GitOps applications"
    )
    
    prune_enabled = models.BooleanField(
        default=False,
        help_text="Enable resource pruning in GitOps applications"
    )
    
    self_heal_enabled = models.BooleanField(
        default=True,
        help_text="Enable self-healing in GitOps applications"
    )
    
    # Phase 2 Enhanced Periodic Sync Scheduler Fields
    scheduler_enabled = models.BooleanField(
        default=True,
        help_text="Enable fabric for enhanced periodic sync scheduling"
    )
    
    scheduler_priority = models.CharField(
        max_length=20,
        choices=[
            ('critical', 'Critical'),
            ('high', 'High'), 
            ('medium', 'Medium'),
            ('low', 'Low'),
            ('maintenance', 'Maintenance')
        ],
        default='medium',
        help_text="Scheduler priority level for sync operations"
    )
    
    sync_plan_version = models.PositiveIntegerField(
        default=1,
        help_text="Version of current sync plan (incremented on plan changes)"
    )
    
    last_scheduler_run = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of last master scheduler run for this fabric"
    )
    
    sync_health_score = models.FloatField(
        default=1.0,
        help_text="Health score calculated by scheduler (0.0=critical, 1.0=healthy)"
    )
    
    scheduler_metadata = models.JSONField(
        default=dict,
        help_text="Scheduler-specific metadata and planning information"
    )
    
    # Micro-task execution tracking
    active_sync_tasks = models.JSONField(
        default=list,
        help_text="List of currently active sync tasks for this fabric"
    )
    
    last_task_execution = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of last task execution (any type)"
    )
    
    task_execution_count = models.PositiveIntegerField(
        default=0,
        help_text="Total number of tasks executed for this fabric"
    )
    
    failed_task_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of failed task executions"
    )
    
    # Real-time monitoring configuration
    watch_enabled = models.BooleanField(
        default=True,
        help_text="Enable real-time Kubernetes CRD watching for this fabric"
    )
    
    watch_crd_types = models.JSONField(
        default=list,
        help_text="List of CRD types to watch (empty for all supported types)"
    )
    
    watch_status = models.CharField(
        max_length=20,
        choices=[
            ('inactive', 'Inactive'),
            ('starting', 'Starting'),
            ('active', 'Active'),
            ('error', 'Error'),
            ('stopped', 'Stopped')
        ],
        default='inactive',
        help_text="Current watch status for real-time monitoring"
    )
    
    watch_started_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When real-time watching was started"
    )
    
    watch_last_event = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of last watch event received"
    )
    
    watch_event_count = models.PositiveIntegerField(
        default=0,
        help_text="Total number of watch events processed"
    )
    
    watch_error_message = models.TextField(
        blank=True,
        help_text="Last watch error message"
    )
    
    # GitOps File Management System fields (MVP2 Enhancement)
    gitops_initialized = models.BooleanField(
        default=False,
        help_text="Whether GitOps file management structure has been initialized"
    )
    
    archive_strategy = models.CharField(
        max_length=30,
        choices=[
            ('rename_with_extension', 'Rename with .archived extension'),
            ('move_to_archive_dir', 'Move to archive directory'),
            ('backup_with_timestamp', 'Backup with timestamp'),
            ('none', 'No archiving')
        ],
        default='rename_with_extension',
        help_text="Strategy for archiving original files during ingestion"
    )
    
    raw_directory_path = models.CharField(
        max_length=500,
        blank=True,
        help_text="Full path to the raw/ directory where users drop files"
    )
    
    managed_directory_path = models.CharField(
        max_length=500,
        blank=True,
        help_text="Full path to the managed/ directory where HNP maintains normalized files"
    )
    
    class Meta:
        verbose_name = "Hedgehog Fabric"
        verbose_name_plural = "Hedgehog Fabrics"
        ordering = ['name']
        unique_together = [['git_repository', 'gitops_directory']]
    
    def __str__(self):
        return self.name
    
    def get_absolute_url(self):
        return reverse('plugins:netbox_hedgehog:fabric_detail', kwargs={'pk': self.pk})
    
    @property
    def crd_count(self):
        """Return total count of CRDs in this fabric"""
        return getattr(self, 'cached_crd_count', 0)
    
    @property
    def calculated_sync_status(self):
        """
        Calculate actual sync status based on configuration and timing.
        Returns proper status that reflects the real state.
        FIXES: Prevents contradictory status like "synced" without kubernetes_server.
        """
        from django.utils import timezone
        
        # CRITICAL FIX: If no Kubernetes server configured, cannot be synced
        if not self.kubernetes_server or not self.kubernetes_server.strip():
            return 'not_configured'
        
        # CRITICAL FIX: If sync is disabled, cannot be synced
        if not self.sync_enabled:
            return 'disabled'
        
        # If never synced, return never_synced
        if not self.last_sync:
            return 'never_synced'
        
        # Calculate time since last sync
        time_since_sync = timezone.now() - self.last_sync
        sync_age_seconds = time_since_sync.total_seconds()
        
        # CRITICAL FIX: If there's a sync error, return error status
        if self.sync_error and self.sync_error.strip():
            return 'error'
            
        # CRITICAL FIX: If there's a connection error, return error status  
        if self.connection_error and self.connection_error.strip():
            return 'error'
        
        # If last sync is more than 2x sync interval, consider out of sync
        if self.sync_interval > 0 and sync_age_seconds > (self.sync_interval * 2):
            return 'out_of_sync'
        
        # If within sync interval, consider in sync
        if self.sync_interval > 0 and sync_age_seconds <= self.sync_interval:
            return 'in_sync'
        
        # For edge cases (sync interval = 0 or other scenarios)
        if sync_age_seconds <= 3600:  # Within last hour
            return 'in_sync'
        else:
            return 'out_of_sync'

    @property
    def calculated_sync_status_display(self):
        """
        Get display-friendly version of calculated sync status.
        FIXES: Adds missing status displays for data consistency.
        """
        status_map = {
            'not_configured': 'Not Configured',
            'disabled': 'Sync Disabled',
            'never_synced': 'Never Synced',
            'in_sync': 'In Sync',
            'out_of_sync': 'Out of Sync',
            'error': 'Sync Error',
        }
        return status_map.get(self.calculated_sync_status, 'Unknown')

    @property
    def calculated_sync_status_badge_class(self):
        """
        Get Bootstrap badge class for sync status display.
        FIXES: Adds missing badge class for disabled status.
        """
        status_classes = {
            'not_configured': 'bg-secondary text-white',
            'disabled': 'bg-secondary text-white',
            'never_synced': 'bg-warning text-dark',
            'in_sync': 'bg-success text-white',
            'out_of_sync': 'bg-danger text-white',
            'error': 'bg-danger text-white',
        }
        return status_classes.get(self.calculated_sync_status, 'bg-secondary text-white')
    
    @property
    def active_crd_count(self):
        """Return count of active/live CRDs in this fabric"""
        total = 0
        try:
            from django.apps import apps
            from ..choices import KubernetesStatusChoices
            
            # Use apps.get_model to avoid circular imports
            VPC = apps.get_model('netbox_hedgehog', 'VPC')
            External = apps.get_model('netbox_hedgehog', 'External')
            ExternalAttachment = apps.get_model('netbox_hedgehog', 'ExternalAttachment')
            ExternalPeering = apps.get_model('netbox_hedgehog', 'ExternalPeering')
            IPv4Namespace = apps.get_model('netbox_hedgehog', 'IPv4Namespace')
            VPCAttachment = apps.get_model('netbox_hedgehog', 'VPCAttachment')
            VPCPeering = apps.get_model('netbox_hedgehog', 'VPCPeering')
            Connection = apps.get_model('netbox_hedgehog', 'Connection')
            Server = apps.get_model('netbox_hedgehog', 'Server')
            Switch = apps.get_model('netbox_hedgehog', 'Switch')
            SwitchGroup = apps.get_model('netbox_hedgehog', 'SwitchGroup')
            VLANNamespace = apps.get_model('netbox_hedgehog', 'VLANNamespace')
            
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
            from django.apps import apps
            from ..choices import KubernetesStatusChoices
            
            # Use apps.get_model to avoid circular imports (same pattern as active_crd_count)
            VPC = apps.get_model('netbox_hedgehog', 'VPC')
            External = apps.get_model('netbox_hedgehog', 'External')
            ExternalAttachment = apps.get_model('netbox_hedgehog', 'ExternalAttachment')
            ExternalPeering = apps.get_model('netbox_hedgehog', 'ExternalPeering')
            IPv4Namespace = apps.get_model('netbox_hedgehog', 'IPv4Namespace')
            VPCAttachment = apps.get_model('netbox_hedgehog', 'VPCAttachment')
            VPCPeering = apps.get_model('netbox_hedgehog', 'VPCPeering')
            Connection = apps.get_model('netbox_hedgehog', 'Connection')
            Server = apps.get_model('netbox_hedgehog', 'Server')
            Switch = apps.get_model('netbox_hedgehog', 'Switch')
            SwitchGroup = apps.get_model('netbox_hedgehog', 'SwitchGroup')
            VLANNamespace = apps.get_model('netbox_hedgehog', 'VLANNamespace')
            
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
            from ..utils.git_monitor import GitRepositoryMonitor
            
            # Create monitor to get repository status
            monitor = GitRepositoryMonitor(self)
            status = monitor.get_repository_status()
            
            return {
                'configured': status.configured,
                'repository_url': self.git_repository_url,
                'branch': self.git_branch,
                'path': self.git_path,
                'last_commit': self.desired_state_commit or 'Unknown',
                'last_sync': self.last_git_sync,
                'status': status.status,
                'repository_exists': status.repository_exists,
                'current_commit': status.current_commit,
                'current_branch': status.current_branch,
                'error': status.error
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
            from django.apps import apps
            from django.utils import timezone
            
            # Use apps.get_model to avoid circular imports
            HedgehogResource = apps.get_model('netbox_hedgehog', 'HedgehogResource')
            
            # Get all resources for this fabric
            resources = HedgehogResource.objects.filter(fabric=self)
            
            # Count resources with drift
            drift_count = 0
            resource_details = {}
            
            for resource in resources:
                # Trigger drift calculation for each resource
                resource.calculate_drift()
                
                if resource.drift_status != 'in_sync':
                    drift_count += 1
                    resource_details[f"{resource.kind}/{resource.name}"] = {
                        'status': resource.drift_status,
                        'score': resource.drift_score,
                        'summary': resource.get_drift_summary()
                    }
            
            # Determine overall drift status
            if drift_count == 0:
                overall_status = 'in_sync'
            else:
                overall_status = 'drift_detected'
            
            # Update fabric drift information
            self.drift_status = overall_status
            self.drift_count = drift_count
            self.save(update_fields=['drift_status', 'drift_count'])
            
            return {
                'drift_status': overall_status,
                'drift_count': drift_count,
                'total_resources': resources.count(),
                'last_calculated': timezone.now(),
                'resource_details': resource_details,
                'details': f'Calculated drift for {resources.count()} resources'
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
            # Implement actual GitOps tool client creation
            if self.gitops_tool == 'argocd':
                from ..utils.argocd_git_integration import ArgoCDClient
                
                client = ArgoCDClient(
                    server=self.kubernetes_server,
                    namespace=self.gitops_namespace or self.kubernetes_namespace,
                    app_name=self.gitops_app_name
                )
                
                # Test client connectivity
                status = client.get_application_status()
                
                return {
                    'tool': self.gitops_tool,
                    'app_name': self.gitops_app_name,
                    'namespace': self.gitops_namespace,
                    'configured': bool(self.gitops_app_name),
                    'status': 'connected' if status.get('success') else 'error',
                    'client': client,
                    'app_status': status.get('app_status', 'unknown')
                }
                
            elif self.gitops_tool == 'flux':
                from ..utils.flux_client import FluxClient
                
                client = FluxClient(
                    namespace=self.gitops_namespace or self.kubernetes_namespace,
                    source_name=self.gitops_app_name
                )
                
                # Test client connectivity
                status = client.get_source_status()
                
                return {
                    'tool': self.gitops_tool,
                    'app_name': self.gitops_app_name,
                    'namespace': self.gitops_namespace,
                    'configured': bool(self.gitops_app_name),
                    'status': 'connected' if status.get('success') else 'error',
                    'client': client,
                    'source_status': status.get('source_status', 'unknown')
                }
                
            else:
                return {
                    'tool': self.gitops_tool,
                    'app_name': self.gitops_app_name,
                    'namespace': self.gitops_namespace,
                    'configured': bool(self.gitops_app_name),
                    'status': 'unsupported_tool',
                    'error': f'GitOps tool {self.gitops_tool} not implemented'
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
        Creates HedgehogResource records for all CRs found in GitOps directory.
        """
        if not self.git_repository_url:
            return {
                'success': False,
                'error': 'No Git repository configured'
            }
        
        try:
            # Import here to avoid circular dependencies
            import tempfile
            import shutil
            import yaml
            import git
            from pathlib import Path
            from django.utils import timezone
            from django.db import transaction
            
            # Clone repository
            temp_dir = tempfile.mkdtemp()
            try:
                repo = git.Repo.clone_from(self.git_repository_url, temp_dir, branch=self.git_branch)
                commit_sha = repo.head.commit.hexsha
                
                # Look for YAML files in the specified git path
                git_path = Path(temp_dir) / (self.git_path.strip('/') if self.git_path else '')
                
                if not git_path.exists():
                    return {
                        'success': False,
                        'error': f'GitOps path {self.git_path} not found in repository'
                    }
                
                yaml_files = list(git_path.glob('*.yaml')) + list(git_path.glob('*.yml'))
                
                resources_created = 0
                resources_updated = 0
                errors = []
                
                with transaction.atomic():
                    # Clear existing desired_spec for this fabric (to detect removed files)
                    from ..models.gitops import HedgehogResource
                    
                    # Clear desired_spec for existing resources
                    HedgehogResource.objects.filter(fabric=self).update(desired_spec=None)
                    
                    for yaml_file in yaml_files:
                        try:
                            with open(yaml_file, 'r') as f:
                                docs = list(yaml.safe_load_all(f))
                            
                            for doc in docs:
                                if not doc or 'kind' not in doc or 'metadata' not in doc:
                                    continue
                                
                                # Check if this is a Hedgehog CRD
                                kind = doc.get('kind')
                                api_version = doc.get('apiVersion', '')
                                
                                if 'hedgehog.githedgehog.com' in api_version or kind in [
                                    'VPC', 'External', 'ExternalAttachment', 'ExternalPeering', 
                                    'IPv4Namespace', 'VPCAttachment', 'VPCPeering',
                                    'Connection', 'Server', 'Switch', 'SwitchGroup', 'VLANNamespace'
                                ]:
                                    name = doc['metadata'].get('name', 'unknown')
                                    namespace = doc['metadata'].get('namespace', 'default')
                                    
                                    # Create or update HedgehogResource
                                    resource, created = HedgehogResource.objects.get_or_create(
                                        fabric=self,
                                        kind=kind,
                                        name=name,
                                        namespace=namespace,
                                        defaults={
                                            'desired_spec': doc,
                                            'api_version': api_version,
                                            'desired_commit': commit_sha
                                        }
                                    )
                                    
                                    if created:
                                        resources_created += 1
                                    else:
                                        resource.desired_spec = doc
                                        resource.desired_commit = commit_sha
                                        resource.save()
                                        resources_updated += 1
                                        
                        except Exception as e:
                            errors.append(f"Error processing {yaml_file.name}: {str(e)}")
                
                # Update fabric sync info
                self.desired_state_commit = commit_sha
                self.last_git_sync = timezone.now()
                self.save(update_fields=['desired_state_commit', 'last_git_sync'])
                
                return {
                    'success': True,
                    'message': f'Sync completed successfully',
                    'repository_url': self.git_repository_url,
                    'branch': self.git_branch,
                    'commit_sha': commit_sha,
                    'files_processed': len(yaml_files),
                    'resources_created': resources_created,
                    'resources_updated': resources_updated,
                    'errors': errors,
                    'sync_time': self.last_git_sync
                }
                
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)
                
        except Exception as e:
            return {
                'success': False,
                'error': f'Sync failed: {str(e)}'
            }
        
        # Original implementation commented out to prevent circular imports
        # if not self.git_repository_url:
        #     return {
        #         'success': False,
        #         'error': 'No Git repository configured'
        #     }
        # 
        # try:
        #     import asyncio
        #     from ..utils.git_monitor import GitRepositoryMonitor
        #     
        #     # Run the async sync operation
        #     async def run_sync():
        #         async with GitRepositoryMonitor(self) as monitor:
        #             return await monitor.sync_to_database()
        #     
        #     # Execute async operation
        #     sync_result = asyncio.run(run_sync())
        #     
        #     return {
        #         'success': sync_result.success,
        #         'message': sync_result.message,
        #         'repository_url': self.git_repository_url,
        #         'branch': self.git_branch,
        #         'commit_sha': sync_result.commit_sha,
        #         'files_processed': sync_result.files_processed,
        #         'resources_created': sync_result.resources_created,
        #         'resources_updated': sync_result.resources_updated,
        #         'errors': sync_result.errors,
        #         'sync_time': self.last_git_sync
        #     }
        #     
        # except Exception as e:
        #     return {
        #         'success': False,
        #         'error': str(e)
        #     }
    
    def trigger_gitops_sync(self):
        """
        Sync CRs from Git repository directory into HNP database.
        This does NOT trigger external GitOps tools - it syncs Git -> HNP.
        """
        from ..utils.git_directory_sync import sync_fabric_from_git
        
        try:
            # Perform Git directory sync
            result = sync_fabric_from_git(self)
            
            if result['success']:
                logger.info(f"Git sync completed for fabric {self.name}: {result['message']}")
            else:
                logger.error(f"Git sync failed for fabric {self.name}: {result.get('error', 'Unknown error')}")
                
            return result
            
        except Exception as e:
            logger.error(f"Git sync failed: {e}")
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
    
    # ArgoCD-specific methods for MVP2 GitOps Setup Automation
    
    async def setup_argocd_gitops(self, repository_config=None):
        """
        Set up complete ArgoCD GitOps stack for this fabric.
        
        This is the main entry point for Phase 1 ArgoCD automation.
        
        Args:
            repository_config: Optional repository configuration overrides
            
        Returns:
            Setup result dict
        """
        try:
            from ..utils.argocd_installer import ArgoCDIntegrationManager
            
            # Update setup status to installing
            self.gitops_setup_status = 'installing'
            self.save(update_fields=['gitops_setup_status'])
            
            # Create integration manager and set up complete stack
            integration_manager = ArgoCDIntegrationManager(self)
            result = await integration_manager.setup_complete_gitops_stack(repository_config)
            
            # Update fabric based on results
            if result['overall_success']:
                self.gitops_setup_status = 'ready'
                self.gitops_setup_error = ''
                
                # Extract ArgoCD status if available
                if result.get('argocd_status'):
                    argocd_status = result['argocd_status']
                    self.argocd_installed = argocd_status.installed
                    self.argocd_version = argocd_status.version
                    self.argocd_server_url = argocd_status.server_url
                    self.argocd_health_status = argocd_status.health_status
                    if argocd_status.installed and not self.argocd_installation_date:
                        from django.utils import timezone
                        self.argocd_installation_date = timezone.now()
            else:
                self.gitops_setup_status = 'error'
                failed_steps = [step['step'] for step in result.get('steps_failed', [])]
                self.gitops_setup_error = f"Setup failed at: {', '.join(failed_steps)}"
            
            self.save()
            
            return result
            
        except Exception as e:
            self.gitops_setup_status = 'error'
            self.gitops_setup_error = str(e)
            self.save(update_fields=['gitops_setup_status', 'gitops_setup_error'])
            
            return {
                'overall_success': False,
                'fabric_name': self.name,
                'steps_failed': [{'step': 'setup_process', 'error': str(e)}],
                'error': str(e)
            }
    
    async def get_argocd_status(self):
        """
        Get current ArgoCD installation and health status for this fabric.
        
        Returns:
            ArgoCD status dict
        """
        try:
            from ..utils.argocd_installer import ArgoCDIntegrationManager
            
            integration_manager = ArgoCDIntegrationManager(self)
            return await integration_manager.get_gitops_status()
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'fabric_name': self.name,
                'argocd_installed': False
            }
    
    async def install_argocd_only(self):
        """
        Install only ArgoCD without application setup.
        Useful for testing or manual configuration scenarios.
        
        Returns:
            Installation result dict
        """
        try:
            from ..utils.argocd_installer import ArgoCDInstaller
            
            # Update setup status
            self.gitops_setup_status = 'installing'
            self.save(update_fields=['gitops_setup_status'])
            
            installer = ArgoCDInstaller(self)
            result = await installer.install_argocd()
            
            if result['success']:
                self.gitops_setup_status = 'configured'
                self.gitops_tool = 'argocd'
                self.argocd_installed = True
                
                # Update ArgoCD-specific fields
                if result.get('installation_status'):
                    status = result['installation_status']
                    self.argocd_version = status.version
                    self.argocd_server_url = status.server_url
                    self.argocd_health_status = status.health_status
                    if not self.argocd_installation_date:
                        from django.utils import timezone
                        self.argocd_installation_date = timezone.now()
                
                self.gitops_setup_error = ''
            else:
                self.gitops_setup_status = 'error'
                self.gitops_setup_error = result.get('error', 'Unknown installation error')
            
            self.save()
            return result
            
        except Exception as e:
            self.gitops_setup_status = 'error'
            self.gitops_setup_error = str(e)
            self.save(update_fields=['gitops_setup_status', 'gitops_setup_error'])
            
            return {
                'success': False,
                'error': str(e),
                'message': 'ArgoCD installation failed'
            }
    
    async def create_argocd_application(self, app_config=None):
        """
        Create ArgoCD application for this fabric's Hedgehog resources.
        
        Args:
            app_config: Optional application configuration overrides
            
        Returns:
            Application creation result dict
        """
        try:
            from ..utils.argocd_installer import ArgoCDIntegrationManager, ArgoCDApplicationConfig
            
            # Validate prerequisites
            if not self.argocd_installed:
                return {
                    'success': False,
                    'error': 'ArgoCD is not installed for this fabric'
                }
            
            if not self.git_repository_url:
                return {
                    'success': False,
                    'error': 'Git repository not configured for this fabric'
                }
            
            # Create application configuration
            if not app_config:
                app_config = ArgoCDApplicationConfig(
                    name=f'hedgehog-{self.name}',
                    namespace='argocd',  # ArgoCD namespace
                    repository_url=self.git_repository_url,
                    repository_branch=self.git_branch,
                    repository_path=self.git_path,
                    destination_namespace=self.kubernetes_namespace,
                    auto_sync=self.auto_sync_enabled,
                    prune=self.prune_enabled,
                    self_heal=self.self_heal_enabled
                )
            
            integration_manager = ArgoCDIntegrationManager(self)
            result = await integration_manager.app_manager.create_hedgehog_application(app_config)
            
            if result['success']:
                self.gitops_app_name = app_config.name
                self.gitops_namespace = app_config.namespace
                self.save(update_fields=['gitops_app_name', 'gitops_namespace'])
            
            return result
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': 'Failed to create ArgoCD application'
            }
    
    async def sync_argocd_application(self):
        """
        Trigger synchronization of ArgoCD application for this fabric.
        
        Returns:
            Sync result dict
        """
        try:
            from ..utils.argocd_installer import ArgoCDIntegrationManager
            
            if not self.gitops_app_name:
                return {
                    'success': False,
                    'error': 'No ArgoCD application configured for this fabric'
                }
            
            integration_manager = ArgoCDIntegrationManager(self)
            return await integration_manager.app_manager.sync_application(self.gitops_app_name)
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': 'Failed to sync ArgoCD application'
            }
    
    async def get_argocd_application_status(self):
        """
        Get status of ArgoCD application for this fabric.
        
        Returns:
            Application status dict
        """
        try:
            from ..utils.argocd_installer import ArgoCDIntegrationManager
            
            if not self.gitops_app_name:
                return {
                    'success': False,
                    'error': 'No ArgoCD application configured for this fabric'
                }
            
            integration_manager = ArgoCDIntegrationManager(self)
            return await integration_manager.app_manager.get_application_status(self.gitops_app_name)
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': 'Failed to get ArgoCD application status'
            }
    
    async def uninstall_argocd(self):
        """
        Uninstall ArgoCD from this fabric's cluster.
        
        Returns:
            Uninstallation result dict
        """
        try:
            from ..utils.argocd_installer import ArgoCDInstaller
            
            installer = ArgoCDInstaller(self)
            result = await installer.uninstall_argocd()
            
            if result['success']:
                # Reset ArgoCD-related fields
                self.argocd_installed = False
                self.argocd_version = ''
                self.argocd_server_url = ''
                self.argocd_health_status = 'unknown'
                self.argocd_installation_date = None
                self.argocd_admin_password = ''
                self.gitops_setup_status = 'not_configured'
                self.gitops_tool = 'manual'
                self.gitops_app_name = ''
                self.gitops_namespace = ''
                self.gitops_setup_error = ''
                self.save()
            
            return result
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': 'ArgoCD uninstallation failed'
            }
    
    def is_argocd_ready_for_uat(self):
        """
        Check if ArgoCD setup is ready for User Acceptance Testing.
        
        Returns:
            bool: True if ready for UAT
        """
        return (
            self.argocd_installed and
            self.argocd_health_status == 'healthy' and
            self.gitops_setup_status == 'ready' and
            bool(self.git_repository_url) and
            bool(self.gitops_app_name)
        )
    
    def get_gitops_setup_summary(self):
        """
        Get comprehensive GitOps setup summary including ArgoCD status.
        
        Returns:
            Complete setup status dict
        """
        base_summary = self.get_gitops_summary()
        
        # Add ArgoCD-specific information
        argocd_info = {
            'argocd': {
                'installed': getattr(self, 'argocd_installed', False),
                'version': getattr(self, 'argocd_version', ''),
                'server_url': getattr(self, 'argocd_server_url', ''),
                'health_status': getattr(self, 'argocd_health_status', 'unknown'),
                'installation_date': getattr(self, 'argocd_installation_date', None),
                'admin_password_set': bool(getattr(self, 'argocd_admin_password', '')),
            },
            'setup_status': {
                'status': getattr(self, 'gitops_setup_status', 'not_configured'),
                'error': getattr(self, 'gitops_setup_error', ''),
                'ready_for_uat': self.is_argocd_ready_for_uat(),
            },
            'sync_policies': {
                'auto_sync': getattr(self, 'auto_sync_enabled', True),
                'prune': getattr(self, 'prune_enabled', False),
                'self_heal': getattr(self, 'self_heal_enabled', True),
            }
        }
        
        # Merge with base summary
        base_summary.update(argocd_info)
        return base_summary
    
    # Real-time monitoring methods
    
    def get_watch_configuration(self):
        """
        Get watch configuration for real-time monitoring.
        
        Returns:
            FabricConnectionInfo for Kubernetes watch service
        """
        from ..domain.interfaces.kubernetes_watch_interface import FabricConnectionInfo
        
        # Default CRD types if none specified
        enabled_crds = self.watch_crd_types if self.watch_crd_types else [
            'VPC', 'External', 'ExternalAttachment', 'ExternalPeering', 
            'IPv4Namespace', 'VPCAttachment', 'VPCPeering',
            'Connection', 'Server', 'Switch', 'SwitchGroup', 'VLANNamespace'
        ]
        
        return FabricConnectionInfo(
            fabric_id=self.pk,
            cluster_endpoint=self.kubernetes_server or '',
            token=self.kubernetes_token,
            ca_cert=self.kubernetes_ca_cert,
            namespace=self.kubernetes_namespace or 'default',
            enabled_crds=enabled_crds
        )
    
    def can_enable_watch(self):
        """
        Check if real-time watching can be enabled for this fabric.
        
        Returns:
            bool: True if watch can be enabled
        """
        connection_info = self.get_watch_configuration()
        return connection_info.is_valid and self.watch_enabled
    
    def update_watch_status(self, status, error_message=None):
        """
        Update watch status and related fields.
        
        Args:
            status: New watch status
            error_message: Optional error message
        """
        from django.utils import timezone
        
        old_status = self.watch_status
        self.watch_status = status
        
        if error_message:
            self.watch_error_message = error_message
        elif status != 'error':
            self.watch_error_message = ''
        
        if status == 'active' and old_status != 'active':
            self.watch_started_at = timezone.now()
        elif status in ['inactive', 'stopped', 'error']:
            # Don't clear watch_started_at to preserve history
            pass
        
        self.save(update_fields=[
            'watch_status', 'watch_error_message', 'watch_started_at'
        ])
        
        logger.info(f"Fabric {self.name} watch status updated: {old_status} -> {status}")
    
    def record_watch_event(self):
        """
        Record that a watch event was received.
        Updates event count and last event timestamp.
        """
        from django.utils import timezone
        
        self.watch_event_count += 1
        self.watch_last_event = timezone.now()
        self.save(update_fields=['watch_event_count', 'watch_last_event'])
    
    def get_watch_statistics(self):
        """
        Get watch statistics for this fabric.
        
        Returns:
            Dict with watch statistics
        """
        return {
            'enabled': self.watch_enabled,
            'status': self.watch_status,
            'started_at': self.watch_started_at,
            'last_event': self.watch_last_event,
            'event_count': self.watch_event_count,
            'enabled_crd_types': self.watch_crd_types or 'all',
            'error_message': self.watch_error_message,
            'can_enable': self.can_enable_watch()
        }
    
    # Phase 2 Enhanced Scheduler Integration Methods
    
    def calculate_scheduler_health_score(self) -> float:
        """
        Calculate comprehensive health score for scheduler planning.
        
        Returns:
            Float between 0.0 (critical) and 1.0 (healthy)
        """
        health_factors = []
        
        # Sync status factor (25% weight)
        sync_score = 1.0
        if self.sync_status == 'error':
            sync_score = 0.1
        elif self.sync_status == 'never_synced':
            sync_score = 0.2
        elif self.sync_status == 'syncing':
            sync_score = 0.7
        elif self.sync_status == 'stale':
            sync_score = 0.6
        health_factors.append(sync_score * 0.25)
        
        # Connection status factor (20% weight)
        conn_score = 1.0 if self.connection_status == 'connected' else 0.3
        health_factors.append(conn_score * 0.20)
        
        # Time since last sync factor (20% weight)
        time_score = 1.0
        if self.last_sync:
            hours_since = (timezone.now() - self.last_sync).total_seconds() / 3600
            if hours_since > 24:
                time_score = 0.2
            elif hours_since > 6:
                time_score = 0.5
            elif hours_since > 1:
                time_score = 0.8
        else:
            time_score = 0.1
        health_factors.append(time_score * 0.20)
        
        # Error rate factor (15% weight)
        if self.task_execution_count > 0:
            error_rate = self.failed_task_count / self.task_execution_count
            error_score = max(0.0, 1.0 - (error_rate * 2))  # Scale error impact
        else:
            error_score = 1.0
        health_factors.append(error_score * 0.15)
        
        # CRD error count factor (10% weight)
        error_count = self.error_crd_count
        crd_score = 1.0
        if error_count > 20:
            crd_score = 0.2
        elif error_count > 10:
            crd_score = 0.4  
        elif error_count > 5:
            crd_score = 0.7
        elif error_count > 0:
            crd_score = 0.9
        health_factors.append(crd_score * 0.10)
        
        # GitOps status factor (10% weight)
        gitops_score = 1.0
        if hasattr(self, 'drift_status'):
            if self.drift_status == 'conflicts':
                gitops_score = 0.3
            elif self.drift_status == 'drift_detected':
                gitops_score = 0.6
            elif self.drift_status == 'git_ahead':
                gitops_score = 0.8
        health_factors.append(gitops_score * 0.10)
        
        final_score = sum(health_factors)
        
        # Update the stored health score
        if abs(final_score - self.sync_health_score) > 0.05:  # Only update if significant change
            self.sync_health_score = final_score
            self.save(update_fields=['sync_health_score'])
        
        return final_score
    
    def should_be_scheduled(self) -> bool:
        """
        Determine if this fabric should be included in scheduler runs.
        
        Returns:
            True if fabric needs scheduler attention
        """
        if not self.scheduler_enabled:
            return False
        
        # Always schedule critical and high priority fabrics
        if self.scheduler_priority in ['critical', 'high']:
            return True
        
        # Schedule based on health score
        health_score = self.calculate_scheduler_health_score()
        if health_score < 0.8:
            return True
        
        # Schedule if overdue for sync
        if self.sync_enabled and self.sync_interval:
            if not self.last_sync:
                return True
            
            time_since_sync = timezone.now() - self.last_sync
            if time_since_sync.total_seconds() >= self.sync_interval:
                return True
        
        return False
    
    def get_scheduler_priority_level(self) -> int:
        """
        Get numeric priority level for scheduler ordering.
        
        Returns:
            Integer priority (1=highest, 5=lowest)
        """
        priority_map = {
            'critical': 1,
            'high': 2,
            'medium': 3,
            'low': 4,
            'maintenance': 5
        }
        return priority_map.get(self.scheduler_priority, 3)
    
    def update_scheduler_execution_metrics(self, task_type: str, success: bool):
        """
        Update scheduler execution metrics for this fabric.
        
        Args:
            task_type: Type of task executed
            success: Whether the task succeeded
        """
        from django.utils import timezone
        
        self.task_execution_count += 1
        if not success:
            self.failed_task_count += 1
        
        self.last_task_execution = timezone.now()
        
        # Update scheduler metadata with task tracking
        if not isinstance(self.scheduler_metadata, dict):
            self.scheduler_metadata = {}
        
        task_history = self.scheduler_metadata.get('task_history', [])
        task_history.append({
            'task_type': task_type,
            'success': success,
            'timestamp': timezone.now().isoformat(),
            'execution_count': self.task_execution_count
        })
        
        # Keep only last 10 task records
        self.scheduler_metadata['task_history'] = task_history[-10:]
        self.scheduler_metadata['last_update'] = timezone.now().isoformat()
        
        self.save(update_fields=[
            'task_execution_count', 'failed_task_count',
            'last_task_execution', 'scheduler_metadata'
        ])
    
    def add_active_sync_task(self, task_id: str, task_type: str, estimated_duration: int):
        """
        Add a sync task to the active tasks list.
        
        Args:
            task_id: Unique identifier for the task
            task_type: Type of sync task
            estimated_duration: Estimated duration in seconds
        """
        if not isinstance(self.active_sync_tasks, list):
            self.active_sync_tasks = []
        
        task_info = {
            'task_id': task_id,
            'task_type': task_type,
            'estimated_duration': estimated_duration,
            'started_at': timezone.now().isoformat()
        }
        
        # Remove any existing task with same ID
        self.active_sync_tasks = [
            task for task in self.active_sync_tasks 
            if task.get('task_id') != task_id
        ]
        
        self.active_sync_tasks.append(task_info)
        self.save(update_fields=['active_sync_tasks'])
    
    def remove_active_sync_task(self, task_id: str, success: bool = True):
        """
        Remove a sync task from the active tasks list.
        
        Args:
            task_id: Task identifier to remove
            success: Whether the task completed successfully
        """
        if not isinstance(self.active_sync_tasks, list):
            return
        
        # Find and remove the task
        task_found = False
        for task in self.active_sync_tasks[:]:
            if task.get('task_id') == task_id:
                self.active_sync_tasks.remove(task)
                task_found = True
                
                # Update execution metrics
                task_type = task.get('task_type', 'unknown')
                self.update_scheduler_execution_metrics(task_type, success)
                break
        
        if task_found:
            self.save(update_fields=['active_sync_tasks'])
    
    def get_active_task_count(self) -> int:
        """Get count of currently active sync tasks."""
        if not isinstance(self.active_sync_tasks, list):
            return 0
        return len(self.active_sync_tasks)
    
    def get_scheduler_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive scheduler statistics for this fabric.
        
        Returns:
            Dict with scheduler metrics and status
        """
        health_score = self.calculate_scheduler_health_score()
        
        return {
            'fabric_id': self.id,
            'fabric_name': self.name,
            'scheduler_enabled': self.scheduler_enabled,
            'priority': self.scheduler_priority,
            'health_score': health_score,
            'should_be_scheduled': self.should_be_scheduled(),
            'last_scheduler_run': self.last_scheduler_run,
            'execution_metrics': {
                'total_executions': self.task_execution_count,
                'failed_executions': self.failed_task_count,
                'success_rate': (
                    (self.task_execution_count - self.failed_task_count) / self.task_execution_count
                    if self.task_execution_count > 0 else 1.0
                ),
                'last_execution': self.last_task_execution
            },
            'active_tasks': {
                'count': self.get_active_task_count(),
                'tasks': self.active_sync_tasks or []
            },
            'sync_status': {
                'status': self.sync_status,
                'last_sync': self.last_sync,
                'sync_enabled': self.sync_enabled,
                'sync_interval': self.sync_interval
            },
            'metadata': self.scheduler_metadata or {}
        }
    
    def sync_actual_state(self):
        """
        Sync actual state from Kubernetes cluster to HedgehogResource records.
        Updates actual_spec and actual_status fields for drift detection.
        """
        if not self.kubernetes_server:
            return {
                'success': False,
                'error': 'No Kubernetes cluster configured'
            }
        
        try:
            from ..utils.kubernetes import KubernetesSync
            from ..models.gitops import HedgehogResource
            from django.utils import timezone
            from django.db import transaction
            
            # Create Kubernetes sync client
            k8s_sync = KubernetesSync(self)
            
            # Fetch CRDs from cluster
            fetch_result = k8s_sync.fetch_crds_from_kubernetes()
            
            if not fetch_result['success']:
                return {
                    'success': False,
                    'error': f"Failed to fetch CRDs from cluster: {'; '.join(fetch_result['errors'])}"
                }
            
            resources_updated = 0
            resources_cleared = 0
            errors = []
            
            with transaction.atomic():
                # Clear actual_spec for all resources (to detect removed resources)
                HedgehogResource.objects.filter(fabric=self).update(
                    actual_spec=None,
                    actual_status=None,
                    actual_updated=None
                )
                
                # Update actual_spec for resources found in cluster
                for kind, cluster_resources in fetch_result['resources'].items():
                    for resource in cluster_resources:
                        try:
                            metadata = resource.get('metadata', {})
                            name = metadata.get('name', '')
                            namespace = metadata.get('namespace', 'default')
                            
                            if not name:
                                continue
                            
                            # Find corresponding HedgehogResource
                            try:
                                hedgehog_resource = HedgehogResource.objects.get(
                                    fabric=self,
                                    kind=kind,
                                    name=name,
                                    namespace=namespace
                                )
                                
                                # Update actual state
                                hedgehog_resource.actual_spec = resource.get('spec', {})
                                hedgehog_resource.actual_status = resource.get('status', {})
                                hedgehog_resource.actual_resource_version = metadata.get('resourceVersion', '')
                                hedgehog_resource.actual_updated = timezone.now()
                                hedgehog_resource.save(update_fields=[
                                    'actual_spec', 'actual_status', 'actual_resource_version', 'actual_updated'
                                ])
                                
                                resources_updated += 1
                                
                            except HedgehogResource.DoesNotExist:
                                # Resource exists in cluster but not in GitOps - create orphaned resource
                                HedgehogResource.objects.create(
                                    fabric=self,
                                    kind=kind,
                                    name=name,
                                    namespace=namespace,
                                    api_version=resource.get('apiVersion', ''),
                                    actual_spec=resource.get('spec', {}),
                                    actual_status=resource.get('status', {}),
                                    actual_resource_version=metadata.get('resourceVersion', ''),
                                    actual_updated=timezone.now(),
                                    labels=metadata.get('labels', {}),
                                    annotations=metadata.get('annotations', {})
                                )
                                
                                resources_updated += 1
                                
                        except Exception as e:
                            error_msg = f"Error processing {kind}/{name}: {str(e)}"
                            errors.append(error_msg)
                            logger.error(error_msg)
                
                # Calculate drift for all resources
                for resource in HedgehogResource.objects.filter(fabric=self):
                    resource.calculate_drift()
            
            # Update fabric state
            self.calculate_drift_status()
            
            return {
                'success': True,
                'message': f'Cluster sync completed successfully',
                'resources_updated': resources_updated,
                'errors': errors,
                'sync_time': timezone.now()
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Cluster sync failed: {str(e)}'
            }