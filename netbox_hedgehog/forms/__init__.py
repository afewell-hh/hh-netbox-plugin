# Forms for Hedgehog NetBox Plugin
from django import forms
from netbox.forms import NetBoxModelForm
from ..models.fabric import HedgehogFabric
from ..models.vpc_api import VPC

class HedgehogFabricForm(NetBoxModelForm):
    """Form for creating and editing Hedgehog Fabrics"""
    
    class Meta:
        model = HedgehogFabric
        fields = [
            'name', 'description', 'status', 
            'kubernetes_server', 'kubernetes_namespace',
            'sync_enabled', 'sync_interval'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'kubernetes_server': forms.URLInput(attrs={
                'placeholder': 'https://k8s-api.example.com:6443 (optional)'
            }),
            'kubernetes_namespace': forms.TextInput(attrs={
                'placeholder': 'default'
            }),
        }
        help_texts = {
            'kubernetes_server': 'Leave empty to use default kubeconfig',
            'sync_interval': 'Sync interval in seconds (0 to disable)',
        }

class VPCForm(NetBoxModelForm):
    """Form for creating and editing VPCs"""
    
    # Add helper fields for better UX
    subnets_text = forms.CharField(
        label='Subnets',
        widget=forms.Textarea(attrs={
            'rows': 4,
            'placeholder': '10.1.0.0/24\n10.1.1.0/24'
        }),
        help_text='One subnet per line in CIDR notation',
        required=False
    )
    
    permit_list_support = forms.BooleanField(
        label='Permit List Support',
        required=False,
        help_text='Enable permit list support for this VPC'
    )
    
    class Meta:
        model = VPC
        fields = [
            'name', 'fabric', 'namespace', 'spec', 'labels', 'annotations'
        ]
        widgets = {
            'spec': forms.Textarea(attrs={'rows': 8}),
            'labels': forms.Textarea(attrs={'rows': 3}),
            'annotations': forms.Textarea(attrs={'rows': 3}),
        }
        help_texts = {
            'spec': 'VPC specification as JSON (e.g., {"subnets": ["10.1.0.0/24"]})',
            'labels': 'Kubernetes labels as JSON',
            'annotations': 'Kubernetes annotations as JSON',
        }

__all__ = [
    'HedgehogFabricForm',
    'VPCForm',
]