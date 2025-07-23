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


# GitOps File Management Forms
class GitOpsOnboardingForm(forms.Form):
    """
    Form for GitOps onboarding wizard configuration step.
    """
    
    ARCHIVE_STRATEGY_CHOICES = [
        ('organize', 'Organize & Migrate (Recommended) - Parse files and organize into managed structure'),
        ('archive', 'Archive & Start Fresh - Archive all files and start with clean structure'),
        ('backup', 'Backup Only - Create backups but leave files in place'),
    ]
    
    # Basic Configuration
    fabric = forms.ModelChoiceField(
        queryset=None,  # Will be set in __init__
        required=True,
        help_text="Select the fabric to configure for GitOps file management",
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'fabric-selector'
        })
    )
    
    gitops_directory = forms.CharField(
        max_length=500,
        required=True,
        help_text="Path within repository where GitOps files will be managed (e.g., /fabrics/production/gitops)",
        widget=forms.TextInput(attrs={
            'placeholder': '/fabrics/production/gitops',
            'class': 'form-control',
            'id': 'gitops-directory'
        })
    )
    
    raw_directory = forms.CharField(
        max_length=200,
        initial='raw/',
        help_text="Directory name for unprocessed YAML files",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'id': 'raw-directory'
        })
    )
    
    managed_directory = forms.CharField(
        max_length=200,
        initial='managed/',
        help_text="Directory name for processed and organized files",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'id': 'managed-directory'
        })
    )
    
    # Migration Strategy
    archive_strategy = forms.ChoiceField(
        choices=ARCHIVE_STRATEGY_CHOICES,
        initial='organize',
        required=True,
        help_text="Choose how to handle existing files during setup",
        widget=forms.RadioSelect(attrs={
            'class': 'form-check-input'
        })
    )
    
    # Confirmation
    confirm_migration = forms.BooleanField(
        required=True,
        label="I understand existing files will be reorganized according to the selected strategy",
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'confirm-strategy'
        })
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Import here to avoid circular imports
        from ..models.fabric import HedgehogFabric
        self.fields['fabric'].queryset = HedgehogFabric.objects.all()


class FileUploadForm(forms.Form):
    """
    Form for uploading files to the raw directory.
    """
    
    fabric = forms.ModelChoiceField(
        queryset=None,  # Will be set in __init__
        required=True,
        help_text="Select the target fabric for file upload",
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'fabric-select'
        })
    )
    
    files = forms.FileField(
        required=True,
        help_text="Select YAML files to upload",
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'id': 'file-input',
            'accept': '.yaml,.yml'
        })
    )
    
    auto_process = forms.BooleanField(
        initial=False,
        required=False,
        label="Automatically process after upload",
        help_text="Start processing immediately after upload completes",
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'auto-process'
        })
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Import here to avoid circular imports
        from ..models.fabric import HedgehogFabric
        self.fields['fabric'].queryset = HedgehogFabric.objects.filter(gitops_initialized=True)


class ArchiveRestoreForm(forms.Form):
    """
    Form for restoring archived files.
    """
    
    archive_ids = forms.MultipleChoiceField(
        required=True,
        help_text="Select archives to restore",
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-check-input'
        })
    )
    
    target_directory = forms.ChoiceField(
        choices=[
            ('raw', 'Raw Directory - Files will be queued for processing'),
            ('managed', 'Managed Directory - Files will be organized directly'),
            ('custom', 'Custom Location - Specify custom path'),
        ],
        initial='raw',
        required=True,
        help_text="Choose where to restore the archived files",
        widget=forms.RadioSelect(attrs={
            'class': 'form-check-input'
        })
    )
    
    overwrite_existing = forms.BooleanField(
        initial=False,
        required=False,
        label="Overwrite existing files with the same name",
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'overwrite-existing'
        })
    )
    
    def __init__(self, *args, available_archives=None, **kwargs):
        super().__init__(*args, **kwargs)
        
        if available_archives:
            choices = [(archive.id, f"{archive.original_name} ({archive.archived_date})") 
                      for archive in available_archives]
            self.fields['archive_ids'].choices = choices