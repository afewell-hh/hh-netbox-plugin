from django import forms
from netbox.forms import NetBoxModelForm

from ..models import VPC, External, IPv4Namespace, ExternalAttachment, ExternalPeering, VPCAttachment, VPCPeering

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
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Import here to avoid circular imports
        from ..models import HedgehogFabric
        
        # If no fabrics exist, show helpful message
        if not HedgehogFabric.objects.exists():
            self.fields['fabric'].empty_label = 'No fabrics available - create a fabric first'
            # Keep field required so validation fails with helpful message
    
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
                "No fabrics available. Please create a fabric first before creating a VPC."
            )
        
        # If fabrics exist but none selected, show different message
        if not cleaned_data.get('fabric'):
            raise forms.ValidationError(
                "Please select a fabric for this VPC. A fabric is required for VPC creation."
            )
        
        return cleaned_data
    
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
                "No fabrics available. Please create a fabric first before creating an external system."
            )
        
        # Ensure fabric is selected
        if not cleaned_data.get('fabric'):
            raise forms.ValidationError(
                "Please select a fabric for this external system. A fabric is required for external system creation."
            )
        
        return cleaned_data
    
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

class ExternalAttachmentForm(NetBoxModelForm):
    """Form for creating and editing External Attachments"""
    
    spec = forms.JSONField(
        widget=forms.Textarea(attrs={'rows': 10, 'class': 'font-monospace'}),
        help_text='External attachment specification as JSON'
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
                "No fabrics available. Please create a fabric first before creating an external attachment."
            )
        
        # Ensure fabric is selected
        if not cleaned_data.get('fabric'):
            raise forms.ValidationError(
                "Please select a fabric for this external attachment. A fabric is required for external attachment creation."
            )
        
        return cleaned_data
    
    class Meta:
        model = ExternalAttachment
        fields = [
            'fabric', 'name', 'namespace', 'spec', 'labels',
            'annotations', 'auto_sync', 'tags'
        ]

class ExternalPeeringForm(NetBoxModelForm):
    """Form for creating and editing External Peerings"""
    
    spec = forms.JSONField(
        widget=forms.Textarea(attrs={'rows': 10, 'class': 'font-monospace'}),
        help_text='External peering specification as JSON'
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
        model = ExternalPeering
        fields = [
            'fabric', 'name', 'namespace', 'spec', 'labels',
            'annotations', 'auto_sync', 'tags'
        ]

class VPCAttachmentForm(NetBoxModelForm):
    """Form for creating and editing VPC Attachments"""
    
    spec = forms.JSONField(
        widget=forms.Textarea(attrs={'rows': 10, 'class': 'font-monospace'}),
        help_text='VPC attachment specification as JSON'
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
        model = VPCAttachment
        fields = [
            'fabric', 'name', 'namespace', 'spec', 'labels',
            'annotations', 'auto_sync', 'tags'
        ]

class VPCPeeringForm(NetBoxModelForm):
    """Form for creating and editing VPC Peerings"""
    
    spec = forms.JSONField(
        widget=forms.Textarea(attrs={'rows': 10, 'class': 'font-monospace'}),
        help_text='VPC peering specification as JSON'
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
        model = VPCPeering
        fields = [
            'fabric', 'name', 'namespace', 'spec', 'labels',
            'annotations', 'auto_sync', 'tags'
        ]