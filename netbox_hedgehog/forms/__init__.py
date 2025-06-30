# Forms for Hedgehog NetBox Plugin
from django import forms
from django.forms import ModelForm
from ..models.fabric import HedgehogFabric
from ..models.vpc_api import VPC

class HedgehogFabricForm(ModelForm):
    """Form for creating and editing Hedgehog Fabrics"""
    
    class Meta:
        model = HedgehogFabric
        fields = [
            'name', 'description', 'status', 
            'kubernetes_server', 'kubernetes_token', 'kubernetes_ca_cert',
            'kubernetes_namespace', 'sync_enabled', 'sync_interval'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
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
            'kubernetes_server': 'Kubernetes API server URL for this fabric',
            'kubernetes_token': 'Service account token with appropriate permissions',
            'kubernetes_ca_cert': 'CA certificate for TLS verification (leave empty for insecure connections)',
            'kubernetes_namespace': 'Default namespace for this fabric\'s resources',
            'sync_interval': 'Sync interval in seconds (0 to disable)',
        }

class VPCForm(ModelForm):
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