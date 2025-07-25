from django.db import models
from django.core.exceptions import ValidationError
from netbox.models import NetBoxModel
import json
import yaml

from ..choices import KubernetesStatusChoices

class BaseCRD(NetBoxModel):
    """
    Abstract base model for all Hedgehog CRDs.
    Contains common fields and functionality shared by all CRD types.
    """
    
    fabric = models.ForeignKey(
        'netbox_hedgehog.HedgehogFabric',
        on_delete=models.CASCADE,
        related_name='%(class)s_set',
        help_text="Hedgehog fabric this CRD belongs to"
    )
    
    name = models.CharField(
        max_length=253,  # Kubernetes resource name limit
        help_text="Kubernetes resource name (must be DNS-1123 compliant)"
    )
    
    namespace = models.CharField(
        max_length=253,
        default='default',
        help_text="Kubernetes namespace for this resource"
    )
    
    # CRD specification (the actual resource definition)
    spec = models.JSONField(
        help_text="CRD specification as JSON"
    )
    
    # Store raw spec for preserving YAML structure  
    raw_spec = models.JSONField(
        default=dict,
        blank=True,
        help_text="Raw spec from YAML file (preserves structure)"
    )
    
    # Labels and annotations
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
    
    # Kubernetes status tracking
    kubernetes_status = models.CharField(
        max_length=20,
        choices=KubernetesStatusChoices,
        default=KubernetesStatusChoices.UNKNOWN,
        help_text="Current status in Kubernetes"
    )
    
    kubernetes_uid = models.CharField(
        max_length=36,
        blank=True,
        help_text="Kubernetes resource UID"
    )
    
    kubernetes_resource_version = models.CharField(
        max_length=50,
        blank=True,
        help_text="Kubernetes resource version"
    )
    
    # Sync tracking
    last_applied = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this CRD was last applied to Kubernetes"
    )
    
    last_synced = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this CRD was last synced from Kubernetes"
    )
    
    sync_error = models.TextField(
        blank=True,
        help_text="Last sync error message (if any)"
    )
    
    # Git sync tracking
    git_file_path = models.CharField(
        max_length=500,
        blank=True,
        help_text="Path to this resource in Git repository"
    )
    
    # Management fields
    auto_sync = models.BooleanField(
        default=True,
        help_text="Enable automatic sync for this resource"
    )
    
    class Meta:
        abstract = True
        unique_together = [['fabric', 'namespace', 'name']]
        ordering = ['fabric', 'namespace', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.fabric.name})"
    
    def clean(self):
        """Validate the CRD before saving"""
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
        
        # Validate spec is valid JSON
        if isinstance(self.spec, str):
            try:
                self.spec = json.loads(self.spec)
            except json.JSONDecodeError as e:
                raise ValidationError({
                    'spec': f'Invalid JSON in spec: {e}'
                })
        
        # Validate labels and annotations are valid JSON
        for field_name in ['labels', 'annotations']:
            field_value = getattr(self, field_name)
            if isinstance(field_value, str):
                try:
                    setattr(self, field_name, json.loads(field_value))
                except json.JSONDecodeError as e:
                    raise ValidationError({
                        field_name: f'Invalid JSON in {field_name}: {e}'
                    })
    
    @staticmethod
    def is_valid_k8s_name(name):
        """
        Validate Kubernetes resource name (DNS-1123 compliant).
        Must be lowercase alphanumeric plus hyphens, start/end with alphanumeric.
        """
        import re
        pattern = r'^[a-z0-9]([-a-z0-9]*[a-z0-9])?$'
        return bool(re.match(pattern, name)) and len(name) <= 253
    
    def to_kubernetes_manifest(self):
        """
        Convert this CRD to a Kubernetes manifest dictionary.
        Subclasses should override this to provide proper apiVersion and kind.
        """
        return {
            'apiVersion': self.get_api_version(),
            'kind': self.get_kind(),
            'metadata': {
                'name': self.name,
                'namespace': self.namespace,
                'labels': self.labels or {},
                'annotations': self.annotations or {},
            },
            'spec': self.spec
        }
    
    def to_yaml(self):
        """Convert this CRD to YAML format"""
        return yaml.dump(self.to_kubernetes_manifest(), default_flow_style=False)
    
    def get_api_version(self):
        """Return the Kubernetes API version for this CRD type"""
        # Subclasses must implement this
        raise NotImplementedError("Subclasses must implement get_api_version()")
    
    def get_kind(self):
        """Return the Kubernetes kind for this CRD type"""
        # Default implementation uses the class name
        return self.__class__.__name__
    
    def get_crd_type(self):
        """Return the CRD type identifier"""
        return self.__class__.__name__.lower()
    
    @property
    def status_display(self):
        """Return human-readable status with icon"""
        status_icons = {
            KubernetesStatusChoices.LIVE: '🟢',
            KubernetesStatusChoices.APPLIED: '🟡',
            KubernetesStatusChoices.PENDING: '🟡',
            KubernetesStatusChoices.SYNCING: '🟡',
            KubernetesStatusChoices.ERROR: '🔴',
            KubernetesStatusChoices.DELETING: '🟠',
            KubernetesStatusChoices.UNKNOWN: '⚪',
        }
        icon = status_icons.get(self.kubernetes_status, '⚪')
        return f"{icon} {self.get_kubernetes_status_display()}"
    
    @property
    def has_sync_error(self):
        """Return True if this CRD has a sync error"""
        return bool(self.sync_error)
    
    def get_full_name(self):
        """Return the full Kubernetes resource name (namespace/name)"""
        return f"{self.namespace}/{self.name}"
    
    def get_git_file_status(self):
        """
        Return the Git file status for this CRD.
        Used to determine if the CRD came from Git or was created via UI.
        
        Returns:
            str: "From Git" if CRD has git_file_path, "Not from Git" otherwise
        """
        if self.git_file_path and self.git_file_path.strip():
            return "From Git"
        else:
            return "Not from Git"
    
    # GitOps integration methods (added for MVP2)
    def get_gitops_resource(self):
        """
        Get the corresponding HedgehogResource for GitOps tracking.
        Returns None if no GitOps tracking exists.
        """
        try:
            from .gitops import HedgehogResource
            return HedgehogResource.objects.filter(
                fabric=self.fabric,
                name=self.name,
                namespace=self.namespace,
                kind=self.get_kind()
            ).first()
        except Exception:
            return None
    
    def sync_to_gitops(self, commit_sha: str = None, file_path: str = None):
        """
        Sync this CRD to GitOps dual-state tracking.
        Creates or updates corresponding HedgehogResource.
        
        Args:
            commit_sha: Git commit SHA if this came from Git
            file_path: Git file path if this came from Git
            
        Returns:
            HedgehogResource instance or None if sync fails
        """
        try:
            # GitOps integration temporarily disabled to prevent circular imports
            return None
        except Exception as e:
            # Log error but don't break existing functionality
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to sync {self} to GitOps: {e}")
            return None
    
    def get_gitops_status(self):
        """
        Get GitOps status for this CRD.
        Returns dict with GitOps tracking information.
        """
        gitops_resource = self.get_gitops_resource()
        if not gitops_resource:
            return {
                'tracked': False,
                'message': 'Not tracked in GitOps system'
            }
        
        return {
            'tracked': True,
            'drift_status': gitops_resource.drift_status,
            'drift_score': gitops_resource.drift_score,
            'has_drift': gitops_resource.has_drift,
            'desired_commit': gitops_resource.desired_commit,
            'git_file_url': gitops_resource.git_file_url,
            'last_drift_check': gitops_resource.last_drift_check,
            'summary': gitops_resource.get_drift_summary()
        }
    
    def trigger_gitops_sync(self):
        """
        Trigger GitOps sync for this resource through the fabric's GitOps tool.
        Returns sync operation result.
        """
        try:
            # Get fabric's GitOps configuration
            gitops_status = self.fabric.get_gitops_summary()
            
            if not gitops_status['capabilities']['gitops_sync']:
                return {
                    'success': False,
                    'message': 'GitOps sync not configured for this fabric'
                }
            
            # Trigger fabric-level sync (includes this resource)
            return self.fabric.trigger_gitops_sync()
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def generate_gitops_yaml(self):
        """
        Generate GitOps-compatible YAML for this CRD.
        Returns YAML string suitable for Git repository storage.
        """
        try:
            gitops_resource = self.get_gitops_resource()
            if gitops_resource:
                return gitops_resource.generate_yaml_content()
            
            # If no GitOps tracking, generate from current CRD
            import yaml
            manifest = {
                'apiVersion': self.get_api_version(),
                'kind': self.get_kind(),
                'metadata': {
                    'name': self.name,
                    'namespace': self.namespace,
                    'labels': self.labels or {},
                    'annotations': self.annotations or {}
                },
                'spec': self.spec
            }
            
            # Add GitOps annotations
            if 'annotations' not in manifest['metadata']:
                manifest['metadata']['annotations'] = {}
            manifest['metadata']['annotations']['managed-by'] = 'hedgehog-netbox-plugin'
            
            return yaml.dump(manifest, default_flow_style=False)
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to generate GitOps YAML for {self}: {e}")
            return None