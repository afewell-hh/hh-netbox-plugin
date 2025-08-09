from django import forms
from django.forms import ModelForm
from django.core.exceptions import ValidationError
from django.utils.html import escape
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator

from ..models import HedgehogFabric
# GitRepository import causing issues - will import locally if needed
# from ..models import GitRepository

class FabricForm(ModelForm):
    """Comprehensive form for editing Hedgehog fabrics with enhanced security"""
    
    class Meta:
        model = HedgehogFabric
        fields = [
            # Basic Information
            'name', 'description', 'status',
            # Kubernetes Configuration  
            'kubernetes_server', 'kubernetes_namespace', 'kubernetes_token', 'kubernetes_ca_cert',
            # Git Repository Configuration
            'git_repository', 'gitops_directory', 
            # Sync Configuration (CRITICAL: includes sync_interval)
            'sync_enabled', 'sync_interval',
            # Real-time Monitoring Configuration
            'watch_enabled'
        ]
        widgets = {
            # Basic Information
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            
            # Kubernetes Configuration
            'kubernetes_server': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://kubernetes.example.com:6443'}),
            'kubernetes_namespace': forms.TextInput(attrs={'class': 'form-control'}),
            'kubernetes_token': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Bearer token for authentication'}),
            'kubernetes_ca_cert': forms.Textarea(attrs={'rows': 4, 'class': 'form-control', 'placeholder': '-----BEGIN CERTIFICATE-----\n...\n-----END CERTIFICATE-----'}),
            
            # Git Repository Configuration
            'git_repository': forms.Select(attrs={'class': 'form-control'}),
            'gitops_directory': forms.TextInput(attrs={'class': 'form-control'}),
            
            # Sync Configuration
            'sync_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'sync_interval': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            
            # Real-time Monitoring Configuration
            'watch_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def clean_name(self):
        """Validate and sanitize fabric name"""
        name = self.cleaned_data.get('name')
        if name:
            # Sanitize input to prevent XSS
            name = escape(name.strip())
            # Validate name format
            if not name.replace('-', '').replace('_', '').isalnum():
                raise ValidationError('Fabric name must contain only letters, numbers, hyphens, and underscores.')
            if len(name) > 63:  # Kubernetes name limit
                raise ValidationError('Fabric name must be 63 characters or less.')
        return name
    
    def clean_description(self):
        """Validate and sanitize description"""
        description = self.cleaned_data.get('description')
        if description:
            # Sanitize input to prevent XSS
            description = escape(description.strip())
            if len(description) > 500:
                raise ValidationError('Description must be 500 characters or less.')
        return description
    
    def clean_kubernetes_server(self):
        """Validate Kubernetes server URL"""
        url = self.cleaned_data.get('kubernetes_server')
        if url:
            # Ensure HTTPS for security
            if not url.startswith('https://'):
                raise ValidationError('Kubernetes server URL must use HTTPS for security.')
            # Basic URL validation
            import re
            url_pattern = re.compile(
                r'^https://[\w\.-]+(:[0-9]+)?(/.*)?$'
            )
            if not url_pattern.match(url):
                raise ValidationError('Please enter a valid HTTPS URL for the Kubernetes server.')
        return url
    
    def clean_sync_interval(self):
        """Validate sync interval"""
        interval = self.cleaned_data.get('sync_interval')
        if interval is not None:
            if interval < 0:
                raise ValidationError('Sync interval cannot be negative.')
            if interval > 86400:  # 24 hours
                raise ValidationError('Sync interval cannot exceed 24 hours (86400 seconds).')
        return interval

    def __init__(self, *args, **kwargs):
        # Extract user from kwargs for GitRepository access
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Ensure all critical fields exist and are properly initialized
        required_fields = [
            'name', 'description', 'status', 'kubernetes_server', 'kubernetes_namespace', 
            'kubernetes_token', 'kubernetes_ca_cert', 'git_repository', 'gitops_directory',
            'sync_enabled', 'sync_interval', 'watch_enabled'
        ]
        
        # Validate and fix missing fields
        for field_name in required_fields:
            if field_name not in self.fields or self.fields[field_name] is None:
                # If field is missing or None, recreate it based on model field
                try:
                    model_field = self._meta.model._meta.get_field(field_name)
                    from django import forms
                    
                    # Create appropriate form field based on model field type
                    if hasattr(model_field, 'choices') and model_field.choices:
                        self.fields[field_name] = forms.ChoiceField(choices=model_field.choices, required=not model_field.null)
                    elif model_field.__class__.__name__ == 'BooleanField':
                        self.fields[field_name] = forms.BooleanField(required=False)
                    elif model_field.__class__.__name__ == 'TextField':
                        self.fields[field_name] = forms.CharField(widget=forms.Textarea, required=not model_field.null)
                    elif model_field.__class__.__name__ == 'URLField':
                        self.fields[field_name] = forms.URLField(required=not model_field.null)
                    elif model_field.__class__.__name__ == 'PositiveIntegerField':
                        self.fields[field_name] = forms.IntegerField(min_value=0, required=not model_field.null)
                    elif model_field.__class__.__name__ == 'ForeignKey':
                        self.fields[field_name] = forms.ModelChoiceField(queryset=model_field.related_model.objects.none(), required=not model_field.null)
                    else:
                        self.fields[field_name] = forms.CharField(required=not model_field.null)
                        
                except Exception:
                    # If we can't create the field, create a basic CharField
                    from django import forms
                    self.fields[field_name] = forms.CharField(required=False)
        
        # Critical fix: Ensure sync_interval field has proper widget and validation
        if 'sync_interval' in self.fields:
            self.fields['sync_interval'].widget = forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'step': '1',
                'placeholder': '300 (seconds)'
            })
            self.fields['sync_interval'].help_text = 'Sync interval in seconds (0 to disable automatic sync)'
        
        # Safe git repository setup with user context
        if 'git_repository' in self.fields and self.fields['git_repository'] is not None:
            try:
                # Import GitRepository locally to avoid circular import
                from ..models import GitRepository
                queryset = GitRepository.objects.all()
                
                # Filter by user if provided
                if self.user:
                    queryset = queryset.filter(created_by=self.user)
                    
                self.fields['git_repository'].queryset = queryset.order_by('name')
                self.fields['git_repository'].empty_label = "Select a Git Repository..."
            except Exception:
                # If GitRepository is problematic, make it a simple text field
                from django import forms
                self.fields['git_repository'] = forms.CharField(required=False, help_text="Git Repository URL")