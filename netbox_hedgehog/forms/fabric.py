from django import forms
from django.forms import ModelForm

from ..models import HedgehogFabric
# GitRepository import causing issues - will import locally if needed
# from ..models import GitRepository

class FabricForm(ModelForm):
    """Comprehensive form for editing Hedgehog fabrics"""
    
    class Meta:
        model = HedgehogFabric
        fields = [
            # Basic Information
            'name', 'description', 'status',
            # Kubernetes Configuration
            'kubernetes_server', 'kubernetes_namespace', 'kubernetes_token', 'kubernetes_ca_cert',
            # Git Repository Configuration
            'git_repository', 'gitops_directory',
            # Sync Configuration
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
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Ensure all fields exist and are properly initialized
        required_fields = [
            'name', 'description', 'status', 'kubernetes_server', 'kubernetes_namespace', 
            'kubernetes_token', 'kubernetes_ca_cert', 'git_repository', 'gitops_directory',
            'sync_enabled', 'sync_interval', 'watch_enabled'
        ]
        
        # Check each field exists and fix if None
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
        
        # Safe git repository setup
        if 'git_repository' in self.fields and self.fields['git_repository'] is not None:
            try:
                # Import GitRepository locally to avoid circular import
                from ..models import GitRepository
                self.fields['git_repository'].queryset = GitRepository.objects.all()
                self.fields['git_repository'].empty_label = "Select a Git Repository..."
            except Exception:
                # If GitRepository is problematic, make it a simple text field
                from django import forms
                self.fields['git_repository'] = forms.CharField(required=False, help_text="Git Repository URL")