from django import forms
from netbox.forms import NetBoxModelForm

from ..models import Connection, Switch, Server

class ConnectionForm(NetBoxModelForm):
    """Form for creating and editing Connections"""
    
    spec = forms.JSONField(
        widget=forms.Textarea(attrs={'rows': 15, 'class': 'font-monospace'}),
        help_text='Connection specification as JSON'
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
        model = Connection
        fields = [
            'fabric', 'name', 'namespace', 'spec', 'labels',
            'annotations', 'auto_sync', 'tags'
        ]

class SwitchForm(NetBoxModelForm):
    """Form for creating and editing Switches"""
    
    spec = forms.JSONField(
        widget=forms.Textarea(attrs={'rows': 12, 'class': 'font-monospace'}),
        help_text='Switch specification as JSON'
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
        model = Switch
        fields = [
            'fabric', 'name', 'namespace', 'spec', 'labels',
            'annotations', 'auto_sync', 'tags'
        ]

class ServerForm(NetBoxModelForm):
    """Form for creating and editing Servers"""
    
    spec = forms.JSONField(
        widget=forms.Textarea(attrs={'rows': 10, 'class': 'font-monospace'}),
        help_text='Server specification as JSON'
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
        model = Server
        fields = [
            'fabric', 'name', 'namespace', 'spec', 'labels',
            'annotations', 'auto_sync', 'tags'
        ]