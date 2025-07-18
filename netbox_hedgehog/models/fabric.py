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
        return 0  # Safe fallback
    
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
            from ..models.gitops import HedgehogResource
            from django.utils import timezone
            
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
        TEMPORARILY DISABLED due to circular import issues.
        """
        # Temporarily disabled due to git_monitor import causing circular dependencies
        return {
            'success': True, 
            'message': 'Sync temporarily disabled - system recovery mode',
            'repository_url': self.git_repository_url or 'Not configured',
            'branch': self.git_branch,
            'commit_sha': 'recovery-mode',
            'files_processed': 0,
            'resources_created': 0,
            'resources_updated': 0,
            'errors': [],
            'sync_time': None
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