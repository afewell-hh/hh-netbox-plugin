from django import forms
from netbox.forms import NetBoxModelForm

from ..models import HedgehogFabric
from ..choices import FabricStatusChoices

class FabricForm(NetBoxModelForm):
    """Form for creating and editing Hedgehog fabrics"""
    
    class Meta:
        model = HedgehogFabric
        fields = [
            'name', 'description', 'status', 'kubernetes_server',
            'kubernetes_token', 'kubernetes_ca_cert', 'kubernetes_namespace',
            'sync_enabled', 'sync_interval', 'tags'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'kubernetes_token': forms.Textarea(attrs={'rows': 4}),
            'kubernetes_ca_cert': forms.Textarea(attrs={'rows': 6}),
        }
        help_texts = {
            'kubernetes_server': 'Kubernetes API server URL (leave empty to use default kubeconfig)',
            'kubernetes_token': 'Service account token (leave empty to use kubeconfig)',
            'kubernetes_ca_cert': 'CA certificate (leave empty to use kubeconfig)',
            'sync_interval': 'Sync interval in seconds (0 to disable automatic sync)',
        }