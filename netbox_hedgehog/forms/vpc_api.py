from django import forms
from netbox.forms import NetBoxModelForm

from ..models import VPC, External, IPv4Namespace

class VPCForm(NetBoxModelForm):
    """Form for creating and editing VPCs"""
    
    spec = forms.JSONField(
        widget=forms.Textarea(attrs={'rows': 10, 'class': 'font-monospace'}),
        help_text='VPC specification as JSON'
    )
    
    labels = forms.JSONField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'font-monospace'}),
        help_text='Kubernetes labels as JSON (optional)'
    )
    
    annotations = forms.JSONField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'font-monospace'}),
        help_text='Kubernetes annotations as JSON (optional)'
    )
    
    class Meta:
        model = VPC
        fields = [
            'fabric', 'name', 'namespace', 'spec', 'labels', 
            'annotations', 'auto_sync', 'tags'
        ]

class ExternalForm(NetBoxModelForm):
    """Form for creating and editing External systems"""
    
    spec = forms.JSONField(
        widget=forms.Textarea(attrs={'rows': 10, 'class': 'font-monospace'}),
        help_text='External system specification as JSON'
    )
    
    labels = forms.JSONField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'font-monospace'}),
        help_text='Kubernetes labels as JSON (optional)'
    )
    
    annotations = forms.JSONField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'font-monospace'}),
        help_text='Kubernetes annotations as JSON (optional)'
    )
    
    class Meta:
        model = External
        fields = [
            'fabric', 'name', 'namespace', 'spec', 'labels',
            'annotations', 'auto_sync', 'tags'
        ]

class IPv4NamespaceForm(NetBoxModelForm):
    """Form for creating and editing IPv4 Namespaces"""
    
    spec = forms.JSONField(
        widget=forms.Textarea(attrs={'rows': 10, 'class': 'font-monospace'}),
        help_text='IPv4 Namespace specification as JSON'
    )
    
    labels = forms.JSONField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'font-monospace'}),
        help_text='Kubernetes labels as JSON (optional)'
    )
    
    annotations = forms.JSONField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'font-monospace'}),
        help_text='Kubernetes annotations as JSON (optional)'
    )
    
    class Meta:
        model = IPv4Namespace
        fields = [
            'fabric', 'name', 'namespace', 'spec', 'labels',
            'annotations', 'auto_sync', 'tags'
        ]