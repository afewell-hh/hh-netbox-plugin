from django.db import models
from django.urls import reverse
from netbox.models import NetBoxModel

from ..choices import FabricStatusChoices

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
        default=FabricStatusChoices.ACTIVE,
        help_text="Current status of this fabric"
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
    
    class Meta:
        verbose_name = "Hedgehog Fabric"
        verbose_name_plural = "Hedgehog Fabrics"
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def get_absolute_url(self):
        return reverse('plugins:netbox_hedgehog:fabric', kwargs={'pk': self.pk})
    
    @property
    def crd_count(self):
        """Return total count of CRDs in this fabric"""
        from .base import BaseCRD
        return BaseCRD.objects.filter(fabric=self).count()
    
    @property
    def active_crd_count(self):
        """Return count of active/live CRDs in this fabric"""
        from .base import BaseCRD
        from ..choices import KubernetesStatusChoices
        return BaseCRD.objects.filter(
            fabric=self,
            kubernetes_status=KubernetesStatusChoices.LIVE
        ).count()
    
    @property
    def error_crd_count(self):
        """Return count of CRDs with errors in this fabric"""
        from .base import BaseCRD
        from ..choices import KubernetesStatusChoices
        return BaseCRD.objects.filter(
            fabric=self,
            kubernetes_status=KubernetesStatusChoices.ERROR
        ).count()
    
    def get_kubernetes_config(self):
        """
        Return Kubernetes configuration for this fabric.
        Returns dict with connection parameters or None to use default kubeconfig.
        """
        if self.kubernetes_server:
            config = {
                'host': self.kubernetes_server,
                'verify_ssl': bool(self.kubernetes_ca_cert),
            }
            
            if self.kubernetes_token:
                config['api_key'] = {'authorization': f'Bearer {self.kubernetes_token}'}
            
            if self.kubernetes_ca_cert:
                config['ssl_ca_cert'] = self.kubernetes_ca_cert
            
            return config
        
        return None  # Use default kubeconfig