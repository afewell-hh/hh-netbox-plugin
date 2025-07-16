"""
Git Repository Management Forms
"""

from django import forms
from netbox.forms import NetBoxModelForm, NetBoxModelFilterSetForm
from utilities.forms.fields import DynamicModelChoiceField, DynamicModelMultipleChoiceField
from ..models import GitRepository
from ..choices import GitRepositoryProviderChoices, GitAuthenticationTypeChoices, GitConnectionStatusChoices


class GitRepositoryForm(NetBoxModelForm):
    """Form for creating and editing Git repositories"""
    
    # Override credential fields to use appropriate widgets
    username = forms.CharField(
        required=False,
        help_text="Username for basic authentication (required for basic auth)",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    
    password = forms.CharField(
        required=False,
        help_text="Password for basic authentication",
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    
    token = forms.CharField(
        required=False,
        help_text="Personal access token or API token (required for token auth)",
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    
    ssh_private_key = forms.CharField(
        required=False,
        help_text="SSH private key content (required for SSH auth)",
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 10})
    )
    
    ssh_passphrase = forms.CharField(
        required=False,
        help_text="SSH key passphrase (if key is encrypted)",
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    
    class Meta:
        model = GitRepository
        fields = [
            'name', 'url', 'provider', 'authentication_type', 'default_branch',
            'username', 'password', 'token', 'ssh_private_key', 'ssh_passphrase',
            'tags'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Production GitOps Repository'
            }),
            'url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://github.com/organization/repo.git'
            }),
            'provider': forms.Select(attrs={'class': 'form-select'}),
            'authentication_type': forms.Select(attrs={'class': 'form-select'}),
            'default_branch': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'main'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # If editing existing repository, populate credential fields
        if self.instance.pk:
            credentials = self.instance.get_decrypted_credentials()
            if credentials:
                self.fields['username'].initial = credentials.get('username', '')
                self.fields['token'].initial = credentials.get('token', '')
                self.fields['ssh_private_key'].initial = credentials.get('ssh_private_key', '')
                # Don't populate password/passphrase for security
        
        # Update field requirements based on authentication type
        self.update_field_requirements()
    
    def update_field_requirements(self):
        """Update field requirements based on authentication type"""
        auth_type = self.data.get('authentication_type') or (
            self.instance.authentication_type if self.instance.pk else GitAuthenticationTypeChoices.TOKEN
        )
        
        # Reset all credential fields to not required
        self.fields['username'].required = False
        self.fields['password'].required = False
        self.fields['token'].required = False
        self.fields['ssh_private_key'].required = False
        self.fields['ssh_passphrase'].required = False
        
        # Set requirements based on auth type
        if auth_type == GitAuthenticationTypeChoices.BASIC:
            self.fields['username'].required = True
            self.fields['password'].required = True if not self.instance.pk else False
        elif auth_type == GitAuthenticationTypeChoices.TOKEN:
            self.fields['token'].required = True if not self.instance.pk else False
        elif auth_type == GitAuthenticationTypeChoices.SSH:
            self.fields['ssh_private_key'].required = True if not self.instance.pk else False
    
    def clean(self):
        cleaned_data = super().clean()
        auth_type = cleaned_data.get('authentication_type')
        
        # Validate required fields based on authentication type
        if auth_type == GitAuthenticationTypeChoices.BASIC:
            if not cleaned_data.get('username'):
                self.add_error('username', 'Username is required for basic authentication')
            if not self.instance.pk and not cleaned_data.get('password'):
                self.add_error('password', 'Password is required for basic authentication')
        
        elif auth_type == GitAuthenticationTypeChoices.TOKEN:
            if not self.instance.pk and not cleaned_data.get('token'):
                self.add_error('token', 'Token is required for token authentication')
        
        elif auth_type == GitAuthenticationTypeChoices.SSH:
            if not self.instance.pk and not cleaned_data.get('ssh_private_key'):
                self.add_error('ssh_private_key', 'SSH private key is required for SSH authentication')
        
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Prepare credentials for encryption
        credentials = {}
        
        if instance.authentication_type == GitAuthenticationTypeChoices.BASIC:
            if self.cleaned_data.get('username'):
                credentials['username'] = self.cleaned_data['username']
            if self.cleaned_data.get('password'):
                credentials['password'] = self.cleaned_data['password']
        
        elif instance.authentication_type == GitAuthenticationTypeChoices.TOKEN:
            if self.cleaned_data.get('token'):
                credentials['token'] = self.cleaned_data['token']
        
        elif instance.authentication_type == GitAuthenticationTypeChoices.SSH:
            if self.cleaned_data.get('ssh_private_key'):
                credentials['ssh_private_key'] = self.cleaned_data['ssh_private_key']
            if self.cleaned_data.get('ssh_passphrase'):
                credentials['ssh_passphrase'] = self.cleaned_data['ssh_passphrase']
        
        # Update credentials if provided
        if credentials:
            instance.set_encrypted_credentials(credentials)
        
        if commit:
            instance.save()
        
        return instance


class GitRepositoryFilterForm(NetBoxModelFilterSetForm):
    """Filter form for Git repository list view"""
    
    model = GitRepository
    
    provider = forms.MultipleChoiceField(
        choices=GitRepositoryProviderChoices,
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'form-select'})
    )
    
    authentication_type = forms.MultipleChoiceField(
        choices=GitAuthenticationTypeChoices,
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'form-select'})
    )
    
    connection_status = forms.MultipleChoiceField(
        choices=GitConnectionStatusChoices,
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'form-select'})
    )
    
    is_private = forms.NullBooleanField(
        required=False,
        widget=forms.Select(
            choices=[
                ('', '---------'),
                (True, 'Private'),
                (False, 'Public')
            ],
            attrs={'class': 'form-select'}
        )
    )