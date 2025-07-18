# Forms for Hedgehog NetBox Plugin
from django import forms
from django.forms import ModelForm
from ..models.fabric import HedgehogFabric
from ..models.vpc_api import VPC, External
from ..models.git_repository import GitRepository

class HedgehogFabricForm(ModelForm):
    """Form for creating and editing Hedgehog Fabrics"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Configure git repository field
        if 'git_repository' in self.fields:
            self.fields['git_repository'].queryset = GitRepository.objects.all().order_by('name')
            # Make it optional with empty choice
            self.fields['git_repository'].empty_label = "-- No Git Repository (Manual Configuration) --"
    
    class Meta:
        model = HedgehogFabric
        fields = [
            'name', 'description', 'status', 
            'git_repository', 'gitops_directory',
            'kubernetes_server', 'kubernetes_token', 'kubernetes_ca_cert',
            'kubernetes_namespace', 'sync_enabled', 'sync_interval'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'git_repository': forms.Select(attrs={
                'class': 'form-select',
                'onchange': 'updateGitRepositoryInfo(this.value)'
            }),
            'gitops_directory': forms.TextInput(attrs={
                'placeholder': '/',
                'class': 'form-control'
            }),
            'kubernetes_server': forms.URLInput(attrs={
                'placeholder': 'https://k8s-api.example.com:6443',
                'class': 'form-control'
            }),
            'kubernetes_token': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'Service account token for authentication',
                'class': 'form-control'
            }),
            'kubernetes_ca_cert': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'CA certificate for TLS verification (optional)',
                'class': 'form-control'
            }),
            'kubernetes_namespace': forms.TextInput(attrs={
                'placeholder': 'default',
                'class': 'form-control'
            }),
            'sync_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'sync_interval': forms.NumberInput(attrs={'class': 'form-control'}),
        }
        help_texts = {
            'git_repository': 'Select a Git repository for GitOps (optional - leave empty for manual configuration)',
            'gitops_directory': 'Directory path within the repository for this fabric\'s CRDs (e.g., /fabrics/fabric1)',
            'kubernetes_server': 'Kubernetes API server URL for this fabric',
            'kubernetes_token': 'Service account token with appropriate permissions',
            'kubernetes_ca_cert': 'CA certificate for TLS verification (leave empty for insecure connections)',
            'kubernetes_namespace': 'Default namespace for this fabric\'s resources',
            'sync_interval': 'Sync interval in seconds (0 to disable)',
        }

# Import forms from other modules - temporarily disabled for system recovery
# from .vpc_api import VPCForm, ExternalForm, IPv4NamespaceForm, ExternalAttachmentForm, ExternalPeeringForm, VPCAttachmentForm, VPCPeeringForm
# from .wiring_api import ConnectionForm, SwitchForm, ServerForm, SwitchGroupForm, VLANNamespaceForm
# from .git_repository import GitRepositoryForm, GitRepositoryFilterForm

__all__ = [
    'HedgehogFabricForm',
    # Other forms temporarily disabled for system recovery
    # 'VPCForm',
    # 'ExternalForm',
    # 'IPv4NamespaceForm',
    # 'ExternalAttachmentForm',
    # 'ExternalPeeringForm',
    # 'VPCAttachmentForm',
    # 'VPCPeeringForm',
    # 'ConnectionForm',
    # 'SwitchForm',
    # 'ServerForm',
    # 'SwitchGroupForm',
    # 'VLANNamespaceForm',
    # 'GitRepositoryForm',
    # 'GitRepositoryFilterForm',
]