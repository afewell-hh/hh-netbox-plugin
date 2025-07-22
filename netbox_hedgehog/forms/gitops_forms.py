from django import forms
from netbox.forms import NetBoxModelForm

from ..models.vpc_api import VPC, External, ExternalAttachment, ExternalPeering, IPv4Namespace, VPCAttachment, VPCPeering
from ..models.wiring_api import Connection, Server, Switch, SwitchGroup, VLANNamespace


class GitOpsFormMixin:
    """Mixin to add GitOps workflow fields to forms"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Add commit message field
        self.fields['commit_message'] = forms.CharField(
            required=False,
            max_length=500,
            widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Optional: Custom commit message for Git'}),
            help_text='Custom commit message for Git commit. If left blank, a default message will be generated.'
        )
        
        # Add YAML preview button (JavaScript will handle this)
        self.fields['yaml_preview'] = forms.CharField(
            required=False,
            widget=forms.HiddenInput()
        )
    
    def clean_commit_message(self):
        """Validate commit message"""
        commit_message = self.cleaned_data.get('commit_message', '').strip()
        
        if commit_message and len(commit_message) > 500:
            raise forms.ValidationError('Commit message is too long. Maximum 500 characters.')
        
        return commit_message or None


# GitOps-Enhanced VPC API Forms
class GitOpsVPCForm(GitOpsFormMixin, NetBoxModelForm):
    """GitOps-enhanced form for VPCs with commit message support"""
    
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


class GitOpsExternalForm(GitOpsFormMixin, NetBoxModelForm):
    """GitOps-enhanced form for External systems"""
    
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


class GitOpsExternalAttachmentForm(GitOpsFormMixin, NetBoxModelForm):
    """GitOps-enhanced form for External Attachments"""
    
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
    
    class Meta:
        model = ExternalAttachment
        fields = [
            'fabric', 'name', 'namespace', 'spec', 'labels',
            'annotations', 'auto_sync', 'tags'
        ]


class GitOpsExternalPeeringForm(GitOpsFormMixin, NetBoxModelForm):
    """GitOps-enhanced form for External Peerings"""
    
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


class GitOpsIPv4NamespaceForm(GitOpsFormMixin, NetBoxModelForm):
    """GitOps-enhanced form for IPv4 Namespaces"""
    
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


class GitOpsVPCAttachmentForm(GitOpsFormMixin, NetBoxModelForm):
    """GitOps-enhanced form for VPC Attachments"""
    
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


class GitOpsVPCPeeringForm(GitOpsFormMixin, NetBoxModelForm):
    """GitOps-enhanced form for VPC Peerings"""
    
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


# GitOps-Enhanced Wiring API Forms
class GitOpsConnectionForm(GitOpsFormMixin, NetBoxModelForm):
    """GitOps-enhanced form for Connections"""
    
    spec = forms.JSONField(
        widget=forms.Textarea(attrs={'rows': 10, 'class': 'font-monospace'}),
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


class GitOpsServerForm(GitOpsFormMixin, NetBoxModelForm):
    """GitOps-enhanced form for Servers"""
    
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


class GitOpsSwitchForm(GitOpsFormMixin, NetBoxModelForm):
    """GitOps-enhanced form for Switches"""
    
    spec = forms.JSONField(
        widget=forms.Textarea(attrs={'rows': 10, 'class': 'font-monospace'}),
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


class GitOpsSwitchGroupForm(GitOpsFormMixin, NetBoxModelForm):
    """GitOps-enhanced form for Switch Groups"""
    
    spec = forms.JSONField(
        widget=forms.Textarea(attrs={'rows': 10, 'class': 'font-monospace'}),
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
    
    class Meta:
        model = SwitchGroup
        fields = [
            'fabric', 'name', 'namespace', 'spec', 'labels',
            'annotations', 'auto_sync', 'tags'
        ]


class GitOpsVLANNamespaceForm(GitOpsFormMixin, NetBoxModelForm):
    """GitOps-enhanced form for VLAN Namespaces"""
    
    spec = forms.JSONField(
        widget=forms.Textarea(attrs={'rows': 10, 'class': 'font-monospace'}),
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
    
    class Meta:
        model = VLANNamespace
        fields = [
            'fabric', 'name', 'namespace', 'spec', 'labels',
            'annotations', 'auto_sync', 'tags'
        ]