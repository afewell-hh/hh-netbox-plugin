"""
Fabric Management Forms
Enhanced forms for fabric onboarding, configuration, and management.
"""

from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
import json
import yaml

# NetBox imports
from netbox.forms import NetBoxModelForm
# from utilities.forms.fields import DynamicModelChoiceField
# from utilities.forms.widgets import StaticSelect2

# Plugin imports  
from ..models.fabric import HedgehogFabric
from ..choices import KubernetesStatusChoices
from ..utils.fabric_onboarding import FabricOnboardingManager


class HedgehogFabricForm(NetBoxModelForm):
    """Enhanced form for creating and editing Hedgehog fabrics"""
    
    kubeconfig_content = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 15,
            'class': 'form-control',
            'placeholder': 'Paste your kubeconfig content here...'
        }),
        required=False,
        help_text="Paste the complete kubeconfig content for connecting to the Hedgehog cluster"
    )
    
    cluster_endpoint = forms.URLField(
        widget=forms.URLInput(attrs={
            'class': 'form-control',
            'placeholder': 'https://kubernetes.example.com:6443'
        }),
        required=False,
        help_text="Kubernetes API server endpoint (will be extracted from kubeconfig if provided)"
    )
    
    test_connection = forms.BooleanField(
        required=False,
        initial=True,
        help_text="Test the connection to the Kubernetes cluster after saving"
    )
    
    class Meta:
        model = HedgehogFabric
        fields = [
            'name', 'description', 'cluster_endpoint', 'kubeconfig_content', 
            'test_connection', 'tags'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., production-datacenter-1'
            }),
            'description': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control',
                'placeholder': 'Description of this Hedgehog fabric deployment'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # If editing existing fabric, populate kubeconfig
        if self.instance and self.instance.pk:
            if self.instance.kubeconfig_data:
                try:
                    # Convert stored kubeconfig back to YAML for editing
                    kubeconfig_dict = self.instance.kubeconfig_data
                    self.fields['kubeconfig_content'].initial = yaml.dump(
                        kubeconfig_dict, default_flow_style=False
                    )
                except Exception:
                    pass
    
    def clean_kubeconfig_content(self):
        """Validate kubeconfig content"""
        content = self.cleaned_data.get('kubeconfig_content')
        
        if not content:
            return None
        
        try:
            # Try to parse as YAML
            kubeconfig_dict = yaml.safe_load(content)
            
            # Validate required kubeconfig fields
            required_fields = ['apiVersion', 'kind', 'clusters', 'users', 'contexts']
            for field in required_fields:
                if field not in kubeconfig_dict:
                    raise ValidationError(f"Invalid kubeconfig: missing '{field}' field")
            
            if kubeconfig_dict.get('kind') != 'Config':
                raise ValidationError("Invalid kubeconfig: kind must be 'Config'")
            
            # Validate clusters have required fields
            clusters = kubeconfig_dict.get('clusters', [])
            if not clusters:
                raise ValidationError("Invalid kubeconfig: no clusters defined")
            
            for cluster in clusters:
                if 'cluster' not in cluster or 'server' not in cluster['cluster']:
                    raise ValidationError("Invalid kubeconfig: cluster missing server URL")
            
            return kubeconfig_dict
            
        except yaml.YAMLError as e:
            raise ValidationError(f"Invalid YAML format: {e}")
        except Exception as e:
            raise ValidationError(f"Invalid kubeconfig content: {e}")
    
    def clean(self):
        """Cross-field validation"""
        cleaned_data = super().clean()
        
        kubeconfig_content = cleaned_data.get('kubeconfig_content')
        cluster_endpoint = cleaned_data.get('cluster_endpoint')
        
        # Extract cluster endpoint from kubeconfig if provided
        if kubeconfig_content and isinstance(kubeconfig_content, dict):
            try:
                clusters = kubeconfig_content.get('clusters', [])
                if clusters:
                    server_url = clusters[0]['cluster']['server']
                    cleaned_data['cluster_endpoint'] = server_url
            except (KeyError, IndexError):
                pass
        
        # Ensure we have either kubeconfig or cluster endpoint
        if not kubeconfig_content and not cluster_endpoint:
            raise ValidationError(
                "Either kubeconfig content or cluster endpoint must be provided"
            )
        
        return cleaned_data
    
    def save(self, commit=True):
        """Save fabric with kubeconfig data"""
        instance = super().save(commit=False)
        
        # Store kubeconfig data
        kubeconfig_content = self.cleaned_data.get('kubeconfig_content')
        if kubeconfig_content:
            instance.kubeconfig_data = kubeconfig_content
        
        if commit:
            instance.save()
            
            # Test connection if requested
            if self.cleaned_data.get('test_connection') and instance.pk:
                try:
                    onboarding_manager = FabricOnboardingManager(instance)
                    success, message, cluster_info = onboarding_manager.validate_kubernetes_connection()
                    
                    if success:
                        instance.sync_status = 'synced'
                        instance.cluster_info = cluster_info
                    else:
                        instance.sync_status = 'error'
                    
                    instance.save()
                except Exception:
                    instance.sync_status = 'error'
                    instance.save()
        
        return instance


class FabricOnboardingForm(forms.Form):
    """Form for fabric onboarding workflow"""
    
    fabric = forms.ModelChoiceField(
        queryset=HedgehogFabric.objects.all(),
        widget=forms.Select(),
        help_text="Select the fabric to onboard"
    )
    
    onboarding_steps = forms.MultipleChoiceField(
        choices=[
            ('validate_connection', 'Validate Kubernetes Connection'),
            ('discover_installation', 'Discover Hedgehog Installation'),
            ('import_resources', 'Import Existing Resources'),
            ('setup_reconciliation', 'Setup Reconciliation'),
        ],
        widget=forms.CheckboxSelectMultiple(),
        initial=['validate_connection', 'discover_installation', 'import_resources'],
        help_text="Select which onboarding steps to perform"
    )
    
    import_namespace = forms.CharField(
        max_length=100,
        initial='default',
        help_text="Kubernetes namespace to import resources from (leave blank for all namespaces)"
    )
    
    generate_service_account = forms.BooleanField(
        initial=True,
        required=False,
        help_text="Generate service account YAML for manual application"
    )
    
    def __init__(self, *args, **kwargs):
        fabric_id = kwargs.pop('fabric_id', None)
        super().__init__(*args, **kwargs)
        
        if fabric_id:
            try:
                fabric = HedgehogFabric.objects.get(pk=fabric_id)
                self.fields['fabric'].initial = fabric
                self.fields['fabric'].widget.attrs['readonly'] = True
            except HedgehogFabric.DoesNotExist:
                pass


class ConnectionTestForm(forms.Form):
    """Form for testing Kubernetes connection"""
    
    fabric = forms.ModelChoiceField(
        queryset=HedgehogFabric.objects.all(),
        widget=forms.Select(),
        help_text="Select fabric to test"
    )
    
    test_type = forms.ChoiceField(
        choices=[
            ('basic', 'Basic Connection Test'),
            ('discovery', 'CRD Discovery Test'),
            ('permissions', 'Permissions Test'),
            ('full', 'Full Integration Test'),
        ],
        initial='basic',
        widget=forms.Select(),
        help_text="Type of connection test to perform"
    )
    
    timeout_seconds = forms.IntegerField(
        initial=30,
        min_value=5,
        max_value=300,
        help_text="Connection timeout in seconds"
    )


class KubeconfigUploadForm(forms.Form):
    """Form for uploading kubeconfig files"""
    
    kubeconfig_file = forms.FileField(
        help_text="Upload a kubeconfig file (.yaml or .yml)"
    )
    
    fabric_name = forms.CharField(
        max_length=100,
        help_text="Name for the new fabric (will be extracted from kubeconfig if not provided)"
    )
    
    description = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        required=False,
        help_text="Optional description for the fabric"
    )
    
    test_connection = forms.BooleanField(
        initial=True,
        required=False,
        help_text="Test connection after creating fabric"
    )
    
    def clean_kubeconfig_file(self):
        """Validate uploaded kubeconfig file"""
        file = self.cleaned_data.get('kubeconfig_file')
        
        if not file:
            return file
        
        # Check file extension
        if not file.name.lower().endswith(('.yaml', '.yml', '.config')):
            raise ValidationError("File must be a YAML file (.yaml, .yml, or .config)")
        
        # Check file size (max 1MB)
        if file.size > 1024 * 1024:
            raise ValidationError("File size must be less than 1MB")
        
        try:
            # Read and validate content
            file.seek(0)
            content = file.read().decode('utf-8')
            file.seek(0)  # Reset file pointer
            
            kubeconfig_dict = yaml.safe_load(content)
            
            # Basic validation
            if not isinstance(kubeconfig_dict, dict):
                raise ValidationError("Invalid kubeconfig: must be a YAML object")
            
            if kubeconfig_dict.get('kind') != 'Config':
                raise ValidationError("Invalid kubeconfig: kind must be 'Config'")
            
            # Store parsed content for later use
            file.kubeconfig_dict = kubeconfig_dict
            
        except UnicodeDecodeError:
            raise ValidationError("File must be valid UTF-8 text")
        except yaml.YAMLError as e:
            raise ValidationError(f"Invalid YAML format: {e}")
        except Exception as e:
            raise ValidationError(f"Error reading file: {e}")
        
        return file
    
    def clean_fabric_name(self):
        """Validate fabric name"""
        name = self.cleaned_data.get('fabric_name')
        
        if not name:
            return name
        
        # Check if fabric already exists
        if HedgehogFabric.objects.filter(name=name).exists():
            raise ValidationError(f"A fabric with the name '{name}' already exists")
        
        return name


class ReconciliationSettingsForm(forms.Form):
    """Form for configuring reconciliation settings"""
    
    fabric = forms.ModelChoiceField(
        queryset=HedgehogFabric.objects.all(),
        widget=forms.Select()
    )
    
    sync_interval = forms.IntegerField(
        initial=300,
        min_value=60,
        max_value=3600,
        help_text="Sync interval in seconds (60-3600)"
    )
    
    enable_auto_import = forms.BooleanField(
        initial=True,
        required=False,
        help_text="Automatically import resources created outside NetBox"
    )
    
    enable_notifications = forms.BooleanField(
        initial=True,
        required=False,
        help_text="Send notifications when external changes are detected"
    )
    
    notification_email = forms.EmailField(
        required=False,
        help_text="Email address for notifications (optional)"
    )
    
    dry_run_mode = forms.BooleanField(
        initial=False,
        required=False,
        help_text="Run reconciliation in dry-run mode (detect changes but don't apply)"
    )


class BulkFabricOperationsForm(forms.Form):
    """Form for bulk operations on multiple fabrics"""
    
    fabrics = forms.ModelMultipleChoiceField(
        queryset=HedgehogFabric.objects.all(),
        widget=forms.CheckboxSelectMultiple(),
        help_text="Select fabrics to operate on"
    )
    
    operation = forms.ChoiceField(
        choices=[
            ('test_connection', 'Test Connection'),
            ('sync', 'Trigger Sync'),
            ('update_status', 'Update Status'),
            ('export_config', 'Export Configuration'),
        ],
        widget=forms.Select(),
        help_text="Operation to perform on selected fabrics"
    )
    
    confirm = forms.BooleanField(
        required=True,
        help_text="Confirm that you want to perform this operation"
    )


class FabricCreationWorkflowForm(NetBoxModelForm):
    """
    Unified fabric creation form that integrates with UnifiedFabricCreationWorkflow.
    Supports both existing and new git repository workflows.
    """
    
    # Workflow step field
    workflow_step = forms.CharField(
        widget=forms.HiddenInput(),
        initial='basic_info',
        required=False
    )
    
    # Git repository selection
    git_repository = forms.ModelChoiceField(
        queryset=None,  # Set in __init__ based on user
        required=False,
        empty_label="Select existing repository...",
        help_text="Choose an existing Git repository or create a new one"
    )
    
    gitops_directory = forms.CharField(
        max_length=500,
        initial='/',
        help_text="Directory path within the Git repository for this fabric"
    )
    
    # New repository creation fields (hidden by default)
    create_new_repository = forms.BooleanField(
        required=False,
        initial=False,
        help_text="Create a new Git repository for this fabric"
    )
    
    new_repo_name = forms.CharField(
        max_length=200,
        required=False,
        help_text="Name for the new Git repository"
    )
    
    new_repo_url = forms.URLField(
        required=False,
        help_text="URL for the new Git repository"
    )
    
    new_repo_provider = forms.ChoiceField(
        choices=[
            ('github', 'GitHub'),
            ('gitlab', 'GitLab'),
            ('bitbucket', 'Bitbucket'),
            ('generic', 'Generic Git'),
        ],
        required=False,
        initial='github'
    )
    
    new_repo_auth_type = forms.ChoiceField(
        choices=[
            ('token', 'Personal Access Token'),
            ('basic', 'Username/Password'),
            ('ssh_key', 'SSH Key'),
        ],
        required=False,
        initial='token'
    )
    
    new_repo_token = forms.CharField(
        widget=forms.PasswordInput(),
        required=False,
        help_text="Personal access token for repository authentication"
    )
    
    new_repo_username = forms.CharField(
        max_length=100,
        required=False,
        help_text="Username for repository authentication"
    )
    
    new_repo_password = forms.CharField(
        widget=forms.PasswordInput(),
        required=False,
        help_text="Password for repository authentication"
    )
    
    new_repo_ssh_key = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 8}),
        required=False,
        help_text="SSH private key for repository authentication"
    )
    
    # GitOps configuration
    gitops_tool = forms.ChoiceField(
        choices=[
            ('manual', 'Manual Deployment'),
            ('argocd', 'ArgoCD'),
            ('flux', 'Flux v2'),
        ],
        initial='manual',
        help_text="GitOps tool for automated deployment"
    )
    
    auto_sync_enabled = forms.BooleanField(
        initial=True,
        required=False,
        help_text="Enable automatic synchronization from Git"
    )
    
    class Meta:
        model = HedgehogFabric
        fields = [
            'name', 'description', 'status',
            'kubernetes_server', 'kubernetes_namespace', 'kubernetes_token', 'kubernetes_ca_cert',
            'sync_enabled', 'sync_interval'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., production-datacenter-1'
            }),
            'description': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control',
                'placeholder': 'Description of this Hedgehog fabric deployment'
            }),
            'kubernetes_server': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://kubernetes.example.com:6443'
            }),
            'kubernetes_namespace': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'hedgehog-system'
            }),
            'kubernetes_token': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control font-monospace',
                'placeholder': 'Kubernetes service account token'
            }),
            'kubernetes_ca_cert': forms.Textarea(attrs={
                'rows': 8,
                'class': 'form-control font-monospace',
                'placeholder': 'Kubernetes cluster CA certificate'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Set git repository queryset based on user
        if self.user:
            from ..models.git_repository import GitRepository
            self.fields['git_repository'].queryset = GitRepository.objects.filter(
                created_by=self.user
            ).order_by('name')
        
        # Set default namespace
        if not self.instance.pk:
            self.fields['kubernetes_namespace'].initial = 'hedgehog-system'
    
    def clean(self):
        """Cross-field validation for fabric creation workflow"""
        cleaned_data = super().clean()
        
        # Validate git repository configuration
        git_repository = cleaned_data.get('git_repository')
        create_new_repository = cleaned_data.get('create_new_repository')
        
        if not git_repository and not create_new_repository:
            raise ValidationError(
                "Either select an existing Git repository or choose to create a new one."
            )
        
        # Validate new repository fields if creating new
        if create_new_repository:
            new_repo_name = cleaned_data.get('new_repo_name')
            new_repo_url = cleaned_data.get('new_repo_url')
            auth_type = cleaned_data.get('new_repo_auth_type')
            
            if not new_repo_name:
                raise ValidationError("Repository name is required when creating a new repository.")
            
            if not new_repo_url:
                raise ValidationError("Repository URL is required when creating a new repository.")
            
            # Validate authentication fields based on type
            if auth_type == 'token':
                if not cleaned_data.get('new_repo_token'):
                    raise ValidationError("Token is required for token authentication.")
            elif auth_type == 'basic':
                if not cleaned_data.get('new_repo_username') or not cleaned_data.get('new_repo_password'):
                    raise ValidationError("Username and password are required for basic authentication.")
            elif auth_type == 'ssh_key':
                if not cleaned_data.get('new_repo_ssh_key'):
                    raise ValidationError("SSH private key is required for SSH key authentication.")
        
        # Validate GitOps directory
        gitops_directory = cleaned_data.get('gitops_directory', '/')
        if not gitops_directory.startswith('/'):
            cleaned_data['gitops_directory'] = '/' + gitops_directory
        
        return cleaned_data
    
    def save(self, commit=True):
        """Save fabric using UnifiedFabricCreationWorkflow"""
        if not commit:
            return super().save(commit=False)
        
        from ..utils.fabric_creation_workflow import UnifiedFabricCreationWorkflow
        
        # Prepare fabric data
        fabric_data = {
            'name': self.cleaned_data['name'],
            'description': self.cleaned_data.get('description', ''),
            'status': self.cleaned_data.get('status', 'planned'),
            'kubernetes_server': self.cleaned_data.get('kubernetes_server', ''),
            'kubernetes_token': self.cleaned_data.get('kubernetes_token', ''),
            'kubernetes_ca_cert': self.cleaned_data.get('kubernetes_ca_cert', ''),
            'kubernetes_namespace': self.cleaned_data.get('kubernetes_namespace', 'hedgehog-system'),
            'sync_enabled': self.cleaned_data.get('sync_enabled', True),
            'sync_interval': self.cleaned_data.get('sync_interval', 300),
            'gitops_tool': self.cleaned_data.get('gitops_tool', 'manual'),
            'auto_sync_enabled': self.cleaned_data.get('auto_sync_enabled', True),
            'prune_enabled': False,
            'self_heal_enabled': True,
        }
        
        # Initialize workflow
        workflow = UnifiedFabricCreationWorkflow(self.user)
        
        # Determine creation path
        if self.cleaned_data.get('create_new_repository'):
            # Create fabric with new repository
            git_config = {
                'name': self.cleaned_data['new_repo_name'],
                'url': self.cleaned_data['new_repo_url'],
                'provider': self.cleaned_data.get('new_repo_provider', 'github'),
                'authentication_type': self.cleaned_data.get('new_repo_auth_type', 'token'),
                'gitops_directory': self.cleaned_data.get('gitops_directory', '/'),
                'test_connection': True,  # Always test new repositories
            }
            
            # Add credentials based on auth type
            auth_type = self.cleaned_data.get('new_repo_auth_type', 'token')
            credentials = {}
            
            if auth_type == 'token':
                credentials['token'] = self.cleaned_data.get('new_repo_token')
            elif auth_type == 'basic':
                credentials['username'] = self.cleaned_data.get('new_repo_username')
                credentials['password'] = self.cleaned_data.get('new_repo_password')
            elif auth_type == 'ssh_key':
                credentials['private_key'] = self.cleaned_data.get('new_repo_ssh_key')
            
            if credentials:
                git_config['credentials'] = credentials
            
            result = workflow.create_fabric_with_new_repository(fabric_data, git_config)
        else:
            # Create fabric with existing repository
            git_repository = self.cleaned_data['git_repository']
            directory = self.cleaned_data.get('gitops_directory', '/')
            
            result = workflow.create_fabric_with_git_repository(
                fabric_data, git_repository.id, directory
            )
        
        if result.success:
            self.instance = result.fabric
            return self.instance
        else:
            raise ValidationError(f"Fabric creation failed: {result.error}")
    
    def get_workflow_data(self):
        """Get data for workflow dialog steps"""
        return {
            'basic_info': {
                'name': self.cleaned_data.get('name', ''),
                'description': self.cleaned_data.get('description', ''),
                'status': self.cleaned_data.get('status', 'planned'),
            },
            'git_config': {
                'repository': self.cleaned_data.get('git_repository'),
                'directory': self.cleaned_data.get('gitops_directory', '/'),
                'create_new': self.cleaned_data.get('create_new_repository', False),
            },
            'kubernetes_config': {
                'server': self.cleaned_data.get('kubernetes_server', ''),
                'namespace': self.cleaned_data.get('kubernetes_namespace', 'hedgehog-system'),
                'token': self.cleaned_data.get('kubernetes_token', ''),
                'ca_cert': self.cleaned_data.get('kubernetes_ca_cert', ''),
            },
            'gitops_config': {
                'tool': self.cleaned_data.get('gitops_tool', 'manual'),
                'auto_sync': self.cleaned_data.get('auto_sync_enabled', True),
            }
        }