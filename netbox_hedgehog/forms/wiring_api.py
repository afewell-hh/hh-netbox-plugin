from django import forms
from netbox.forms import NetBoxModelForm

from ..models import Connection, Switch, Server, SwitchGroup, VLANNamespace

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
    
    def clean(self):
        cleaned_data = super().clean()
        
        # If parent validation failed, return early
        if cleaned_data is None:
            return cleaned_data
        
        # Import here to avoid circular imports
        from ..models import HedgehogFabric
        
        # Check if any fabrics exist
        if not HedgehogFabric.objects.exists():
            raise forms.ValidationError(
                "No fabrics available. Please create a fabric first before creating a connection."
            )
        
        # Ensure fabric is selected
        if not cleaned_data.get('fabric'):
            raise forms.ValidationError(
                "Please select a fabric for this connection. A fabric is required for connection creation."
            )
        
        return cleaned_data
    
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
    
    def clean(self):
        cleaned_data = super().clean()
        
        # If parent validation failed, return early
        if cleaned_data is None:
            return cleaned_data
        
        # Import here to avoid circular imports
        from ..models import HedgehogFabric
        
        # Check if any fabrics exist
        if not HedgehogFabric.objects.exists():
            raise forms.ValidationError(
                "No fabrics available. Please create a fabric first before creating a switch."
            )
        
        # Ensure fabric is selected
        if not cleaned_data.get('fabric'):
            raise forms.ValidationError(
                "Please select a fabric for this switch. A fabric is required for switch creation."
            )
        
        return cleaned_data
    
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
    
    def clean(self):
        cleaned_data = super().clean()
        
        # If parent validation failed, return early
        if cleaned_data is None:
            return cleaned_data
        
        # Import here to avoid circular imports
        from ..models import HedgehogFabric
        
        # Check if any fabrics exist
        if not HedgehogFabric.objects.exists():
            raise forms.ValidationError(
                "No fabrics available. Please create a fabric first before creating a server."
            )
        
        # Ensure fabric is selected
        if not cleaned_data.get('fabric'):
            raise forms.ValidationError(
                "Please select a fabric for this server. A fabric is required for server creation."
            )
        
        return cleaned_data
    
    class Meta:
        model = Server
        fields = [
            'fabric', 'name', 'namespace', 'spec', 'labels',
            'annotations', 'auto_sync', 'tags'
        ]

class SwitchGroupForm(NetBoxModelForm):
    """Form for creating and editing Switch Groups"""
    
    spec = forms.JSONField(
        widget=forms.Textarea(attrs={'rows': 8, 'class': 'font-monospace'}),
        help_text='Switch group specification as JSON'
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
    
    def clean(self):
        cleaned_data = super().clean()
        
        # If parent validation failed, return early
        if cleaned_data is None:
            return cleaned_data
        
        # Import here to avoid circular imports
        from ..models import HedgehogFabric
        
        # Check if any fabrics exist
        if not HedgehogFabric.objects.exists():
            raise forms.ValidationError(
                "No fabrics available. Please create a fabric first before creating a switch group."
            )
        
        # Ensure fabric is selected
        if not cleaned_data.get('fabric'):
            raise forms.ValidationError(
                "Please select a fabric for this switch group. A fabric is required for switch group creation."
            )
        
        return cleaned_data
    
    class Meta:
        model = SwitchGroup
        fields = [
            'fabric', 'name', 'namespace', 'spec', 'labels',
            'annotations', 'auto_sync', 'tags'
        ]

class VLANNamespaceForm(NetBoxModelForm):
    """Form for creating and editing VLAN Namespaces"""
    
    spec = forms.JSONField(
        widget=forms.Textarea(attrs={'rows': 6, 'class': 'font-monospace'}),
        help_text='VLAN namespace specification as JSON'
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
    
    def clean(self):
        cleaned_data = super().clean()
        
        # If parent validation failed, return early
        if cleaned_data is None:
            return cleaned_data
        
        # Import here to avoid circular imports
        from ..models import HedgehogFabric
        
        # Check if any fabrics exist
        if not HedgehogFabric.objects.exists():
            raise forms.ValidationError(
                "No fabrics available. Please create a fabric first before creating a VLAN namespace."
            )
        
        # Ensure fabric is selected
        if not cleaned_data.get('fabric'):
            raise forms.ValidationError(
                "Please select a fabric for this VLAN namespace. A fabric is required for VLAN namespace creation."
            )
        
        return cleaned_data
    
    class Meta:
        model = VLANNamespace
        fields = [
            'fabric', 'name', 'namespace', 'spec', 'labels',
            'annotations', 'auto_sync', 'tags'
        ]