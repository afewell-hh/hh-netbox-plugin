# Generated migration for GitOps architecture separation
# Implements Week 1 GitOps Backend Architecture Enhancement

import json
import base64
from cryptography.fernet import Fernet
from django.db import migrations, models
from django.conf import settings
import django.db.models.deletion


def migrate_git_configurations_forward(apps, schema_editor):
    """
    Migrate existing fabric git configurations to GitRepository model.
    
    This function preserves all existing data by:
    1. Creating GitRepository records from existing fabric git configs
    2. Updating fabrics to reference the new GitRepository records
    3. Encrypting credentials during migration
    """
    HedgehogFabric = apps.get_model('netbox_hedgehog', 'HedgehogFabric')
    GitRepository = apps.get_model('netbox_hedgehog', 'GitRepository')
    User = apps.get_model('auth', 'User')
    
    # Get encryption key for credential migration
    def get_encryption_key():
        """Get encryption key derived from Django SECRET_KEY"""
        secret = settings.SECRET_KEY.encode('utf-8')
        key = base64.urlsafe_b64encode(secret[:32].ljust(32, b'\0'))
        return key
    
    def encrypt_credentials(credentials_dict):
        """Encrypt credentials for storage"""
        if not credentials_dict:
            return ''
        try:
            credentials_json = json.dumps(credentials_dict)
            fernet = Fernet(get_encryption_key())
            encrypted_data = fernet.encrypt(credentials_json.encode('utf-8'))
            return base64.b64encode(encrypted_data).decode('utf-8')
        except Exception:
            return ''
    
    # Create a default system user if needed for orphaned configurations
    system_user, created = User.objects.get_or_create(
        username='system_migration',
        defaults={
            'email': 'system@hedgehog.migration',
            'first_name': 'System',
            'last_name': 'Migration',
            'is_active': False,
            'is_staff': False
        }
    )
    
    # Track repository URL to GitRepository mapping to avoid duplicates
    repository_mapping = {}
    
    # Process all fabrics with git configurations
    fabrics_with_git = HedgehogFabric.objects.exclude(git_repository_url='').exclude(git_repository_url__isnull=True)
    
    migration_summary = {
        'fabrics_processed': 0,
        'repositories_created': 0,
        'credentials_migrated': 0,
        'errors': []
    }
    
    for fabric in fabrics_with_git:
        try:
            migration_summary['fabrics_processed'] += 1
            
            # Determine repository URL
            repo_url = fabric.git_repository_url
            if not repo_url:
                continue
            
            # Create unique key for repository (URL + user)
            # Use system user if no user is associated with fabric
            fabric_user = getattr(fabric, 'created_by', None) or system_user
            repo_key = f"{repo_url}_{fabric_user.id}"
            
            # Check if we already created a GitRepository for this URL + user combination
            if repo_key not in repository_mapping:
                # Determine provider from URL
                provider = 'generic'
                if 'github.com' in repo_url:
                    provider = 'github'
                elif 'gitlab.com' in repo_url or 'gitlab' in repo_url:
                    provider = 'gitlab'
                elif 'bitbucket.org' in repo_url:
                    provider = 'bitbucket'
                elif 'dev.azure.com' in repo_url or 'visualstudio.com' in repo_url:
                    provider = 'azure'
                
                # Prepare credentials for encryption
                credentials = {}
                auth_type = 'token'  # Default to token
                
                # Migrate existing credentials
                if hasattr(fabric, 'git_token') and fabric.git_token:
                    credentials['token'] = fabric.git_token
                    auth_type = 'token'
                elif hasattr(fabric, 'git_username') and fabric.git_username:
                    credentials['username'] = fabric.git_username
                    if hasattr(fabric, 'git_password') and getattr(fabric, 'git_password', None):
                        credentials['password'] = getattr(fabric, 'git_password', '')
                    auth_type = 'basic'
                
                # Encrypt credentials
                encrypted_credentials = encrypt_credentials(credentials)
                if credentials:
                    migration_summary['credentials_migrated'] += 1
                
                # Create GitRepository record
                git_repository = GitRepository.objects.create(
                    name=f"{fabric.name} Git Repository",
                    url=repo_url,
                    provider=provider,
                    authentication_type=auth_type,
                    encrypted_credentials=encrypted_credentials,
                    connection_status='pending',
                    default_branch=getattr(fabric, 'git_branch', 'main'),
                    is_private=True,  # Assume private by default
                    fabric_count=0,  # Will be updated below
                    created_by=fabric_user,
                    description=f"Migrated from fabric '{fabric.name}' during GitOps architecture separation"
                )
                
                repository_mapping[repo_key] = git_repository
                migration_summary['repositories_created'] += 1
            else:
                git_repository = repository_mapping[repo_key]
            
            # Update fabric to reference GitRepository
            fabric.git_repository = git_repository
            
            # Migrate git_path to gitops_directory
            gitops_directory = getattr(fabric, 'git_path', '/') or '/'
            if not gitops_directory.startswith('/'):
                gitops_directory = '/' + gitops_directory
            if not gitops_directory.endswith('/') and gitops_directory != '/':
                gitops_directory = gitops_directory + '/'
            fabric.gitops_directory = gitops_directory
            
            fabric.save(update_fields=['git_repository', 'gitops_directory'])
            
        except Exception as e:
            error_msg = f"Error migrating fabric '{fabric.name}': {str(e)}"
            migration_summary['errors'].append(error_msg)
            print(f"Migration warning: {error_msg}")
    
    # Update fabric counts for all created repositories
    for git_repository in repository_mapping.values():
        git_repository.update_fabric_count()
    
    # Print migration summary
    print(f"Git Repository Migration Summary:")
    print(f"  Fabrics processed: {migration_summary['fabrics_processed']}")
    print(f"  Repositories created: {migration_summary['repositories_created']}")
    print(f"  Credentials migrated: {migration_summary['credentials_migrated']}")
    if migration_summary['errors']:
        print(f"  Errors encountered: {len(migration_summary['errors'])}")
        for error in migration_summary['errors']:
            print(f"    - {error}")


def migrate_git_configurations_reverse(apps, schema_editor):
    """
    Reverse migration: restore git configurations back to fabric fields.
    
    This allows rollback by copying GitRepository data back to fabric fields.
    """
    HedgehogFabric = apps.get_model('netbox_hedgehog', 'HedgehogFabric')
    GitRepository = apps.get_model('netbox_hedgehog', 'GitRepository')
    
    # Get decryption key for credential migration
    def get_encryption_key():
        """Get encryption key derived from Django SECRET_KEY"""
        secret = settings.SECRET_KEY.encode('utf-8')
        key = base64.urlsafe_b64encode(secret[:32].ljust(32, b'\0'))
        return key
    
    def decrypt_credentials(encrypted_credentials):
        """Decrypt credentials from storage"""
        if not encrypted_credentials:
            return {}
        try:
            encrypted_data = base64.b64decode(encrypted_credentials.encode('utf-8'))
            fernet = Fernet(get_encryption_key())
            decrypted_data = fernet.decrypt(encrypted_data)
            return json.loads(decrypted_data.decode('utf-8'))
        except Exception:
            return {}
    
    rollback_summary = {
        'fabrics_processed': 0,
        'credentials_restored': 0,
        'errors': []
    }
    
    # Process all fabrics that have git_repository set
    fabrics_with_repo = HedgehogFabric.objects.exclude(git_repository__isnull=True)
    
    for fabric in fabrics_with_repo:
        try:
            rollback_summary['fabrics_processed'] += 1
            git_repo = fabric.git_repository
            
            # Restore git configuration fields
            fabric.git_repository_url = git_repo.url
            fabric.git_branch = git_repo.default_branch
            
            # Restore gitops_directory to git_path
            gitops_dir = getattr(fabric, 'gitops_directory', '/')
            if gitops_dir.startswith('/'):
                gitops_dir = gitops_dir[1:]
            if gitops_dir.endswith('/') and gitops_dir != '/':
                gitops_dir = gitops_dir[:-1]
            fabric.git_path = gitops_dir or 'hedgehog/'
            
            # Restore credentials
            credentials = decrypt_credentials(git_repo.encrypted_credentials)
            if credentials:
                rollback_summary['credentials_restored'] += 1
                
                if 'token' in credentials:
                    fabric.git_token = credentials['token']
                    fabric.git_username = ''
                elif 'username' in credentials:
                    fabric.git_username = credentials['username']
                    fabric.git_token = ''
                    # Note: password cannot be restored as it's not stored in legacy model
            
            # Clear new architecture fields
            fabric.git_repository = None
            fabric.gitops_directory = '/'
            
            fabric.save(update_fields=[
                'git_repository_url', 'git_branch', 'git_path',
                'git_token', 'git_username', 'git_repository', 'gitops_directory'
            ])
            
        except Exception as e:
            error_msg = f"Error rolling back fabric '{fabric.name}': {str(e)}"
            rollback_summary['errors'].append(error_msg)
            print(f"Rollback warning: {error_msg}")
    
    # Print rollback summary
    print(f"Git Repository Rollback Summary:")
    print(f"  Fabrics processed: {rollback_summary['fabrics_processed']}")
    print(f"  Credentials restored: {rollback_summary['credentials_restored']}")
    if rollback_summary['errors']:
        print(f"  Errors encountered: {len(rollback_summary['errors'])}")
        for error in rollback_summary['errors']:
            print(f"    - {error}")


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_hedgehog', '0013_add_argocd_tracking_fields'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        # Step 1: Create GitRepository model
        migrations.CreateModel(
            name='GitRepository',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict, encoder=None)),
                ('tags', models.ManyToManyField(blank=True, related_name='%(app_label)s_%(class)s_related', to='extras.tag')),
                
                # Core identification fields
                ('name', models.CharField(max_length=100, help_text='User-friendly name for this git repository')),
                ('url', models.URLField(max_length=500, help_text='Git repository URL (HTTPS or SSH)')),
                ('provider', models.CharField(
                    max_length=20,
                    choices=[
                        ('github', 'GitHub'),
                        ('gitlab', 'GitLab'),
                        ('bitbucket', 'Bitbucket'),
                        ('azure', 'Azure DevOps'),
                        ('generic', 'Generic Git'),
                    ],
                    default='generic',
                    help_text='Git provider type'
                )),
                ('authentication_type', models.CharField(
                    max_length=20,
                    choices=[
                        ('token', 'Personal Access Token'),
                        ('ssh_key', 'SSH Key'),
                        ('oauth', 'OAuth Token'),
                        ('basic', 'Username/Password'),
                    ],
                    default='token',
                    help_text='Authentication method for repository access'
                )),
                
                # Encrypted credential storage
                ('encrypted_credentials', models.TextField(
                    blank=True,
                    help_text='Encrypted JSON containing authentication credentials'
                )),
                
                # Connection status tracking
                ('connection_status', models.CharField(
                    max_length=20,
                    choices=[
                        ('pending', 'Pending Validation'),
                        ('testing', 'Testing Connection'),
                        ('connected', 'Connected'),
                        ('failed', 'Connection Failed'),
                    ],
                    default='pending',
                    help_text='Current connection status to repository'
                )),
                ('last_validated', models.DateTimeField(
                    null=True,
                    blank=True,
                    help_text='Timestamp of last successful connection test'
                )),
                ('validation_error', models.TextField(
                    blank=True,
                    help_text='Last connection error message (if any)'
                )),
                
                # Repository metadata
                ('default_branch', models.CharField(
                    max_length=100,
                    default='main',
                    help_text='Default branch name (main, master, etc.)'
                )),
                ('is_private', models.BooleanField(
                    default=True,
                    help_text='Whether this is a private repository requiring authentication'
                )),
                ('fabric_count', models.PositiveIntegerField(
                    default=0,
                    help_text='Number of fabrics using this repository'
                )),
                
                # Additional metadata
                ('description', models.TextField(
                    blank=True,
                    help_text='Optional description of this repository'
                )),
                
                # Validation settings
                ('validate_ssl', models.BooleanField(
                    default=True,
                    help_text='Validate SSL certificates when connecting'
                )),
                ('timeout_seconds', models.PositiveIntegerField(
                    default=30,
                    help_text='Connection timeout in seconds'
                )),
                
                # User association
                ('created_by', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='auth.user',
                    help_text='User who created this repository configuration'
                )),
            ],
            options={
                'verbose_name': 'Git Repository',
                'verbose_name_plural': 'Git Repositories',
                'ordering': ['name'],
            },
        ),
        
        # Step 2: Add unique constraint to GitRepository
        migrations.AddConstraint(
            model_name='gitrepository',
            constraint=models.UniqueConstraint(
                fields=['url', 'created_by'],
                name='unique_git_repository_per_user'
            ),
        ),
        
        # Step 3: Add new fields to HedgehogFabric
        migrations.AddField(
            model_name='hedgehogfabric',
            name='git_repository',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.SET_NULL,
                null=True,
                blank=True,
                to='netbox_hedgehog.gitrepository',
                help_text='Reference to authenticated git repository (separated architecture)'
            ),
        ),
        migrations.AddField(
            model_name='hedgehogfabric',
            name='gitops_directory',
            field=models.CharField(
                max_length=500,
                default='/',
                help_text='Directory path within repository for this fabric\'s CRDs'
            ),
        ),
        
        # Step 4: Add unique constraint to HedgehogFabric to prevent conflicts
        migrations.AddConstraint(
            model_name='hedgehogfabric',
            constraint=models.UniqueConstraint(
                fields=['git_repository', 'gitops_directory'],
                name='unique_fabric_git_directory',
                condition=models.Q(git_repository__isnull=False)
            ),
        ),
        
        # Step 5: Run data migration to preserve existing configurations
        migrations.RunPython(
            migrate_git_configurations_forward,
            migrate_git_configurations_reverse,
            hints={'preserve_data': True}
        ),
        
        # Step 6: Mark legacy fields as deprecated (but don't remove them yet)
        migrations.AlterField(
            model_name='hedgehogfabric',
            name='git_repository_url',
            field=models.URLField(
                blank=True,
                null=True,
                help_text='[DEPRECATED] Git repository URL - use git_repository field instead'
            ),
        ),
        migrations.AlterField(
            model_name='hedgehogfabric',
            name='git_branch',
            field=models.CharField(
                max_length=100,
                default='main',
                help_text='[DEPRECATED] Git branch - managed by GitRepository'
            ),
        ),
        migrations.AlterField(
            model_name='hedgehogfabric',
            name='git_path',
            field=models.CharField(
                max_length=255,
                default='hedgehog/',
                help_text='[DEPRECATED] Git path - use gitops_directory field instead'
            ),
        ),
        migrations.AlterField(
            model_name='hedgehogfabric',
            name='git_username',
            field=models.CharField(
                max_length=100,
                blank=True,
                help_text='[DEPRECATED] Git username - managed by GitRepository'
            ),
        ),
        migrations.AlterField(
            model_name='hedgehogfabric',
            name='git_token',
            field=models.CharField(
                max_length=255,
                blank=True,
                help_text='[DEPRECATED] Git token - managed by GitRepository'
            ),
        ),
    ]