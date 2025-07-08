# Generated migration for adding GitOps fields to HedgehogFabric

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_hedgehog', '0007_add_count_fields'),
    ]

    operations = [
        # GitOps Configuration Fields
        migrations.AddField(
            model_name='hedgehogfabric',
            name='git_repository_url',
            field=models.URLField(blank=True, null=True, help_text='Git repository containing desired Hedgehog CRD definitions'),
        ),
        migrations.AddField(
            model_name='hedgehogfabric',
            name='git_branch',
            field=models.CharField(default='main', max_length=100, help_text='Git branch to track for desired state'),
        ),
        migrations.AddField(
            model_name='hedgehogfabric',
            name='git_path',
            field=models.CharField(default='hedgehog/', max_length=255, help_text='Path within repo containing Hedgehog CRDs'),
        ),
        migrations.AddField(
            model_name='hedgehogfabric',
            name='git_username',
            field=models.CharField(blank=True, max_length=100, help_text='Git username for authentication'),
        ),
        migrations.AddField(
            model_name='hedgehogfabric',
            name='git_token',
            field=models.CharField(blank=True, max_length=255, help_text='Git access token for authentication'),
        ),
        
        # GitOps State Tracking Fields
        migrations.AddField(
            model_name='hedgehogfabric',
            name='desired_state_commit',
            field=models.CharField(blank=True, max_length=40, help_text='Git commit SHA of current desired state'),
        ),
        migrations.AddField(
            model_name='hedgehogfabric',
            name='drift_status',
            field=models.CharField(
                choices=[
                    ('in_sync', 'In Sync'),
                    ('drift_detected', 'Drift Detected'),
                    ('git_ahead', 'Git Ahead'),
                    ('cluster_ahead', 'Cluster Ahead'),
                    ('conflicts', 'Conflicts')
                ],
                default='in_sync',
                max_length=20,
                help_text='Current drift status between desired and actual state'
            ),
        ),
        migrations.AddField(
            model_name='hedgehogfabric',
            name='drift_count',
            field=models.PositiveIntegerField(default=0, help_text='Number of resources with detected drift'),
        ),
        migrations.AddField(
            model_name='hedgehogfabric',
            name='last_git_sync',
            field=models.DateTimeField(blank=True, null=True, help_text='Timestamp of last Git repository sync'),
        ),
        
        # GitOps Tool Integration Fields
        migrations.AddField(
            model_name='hedgehogfabric',
            name='gitops_tool',
            field=models.CharField(
                choices=[
                    ('manual', 'Manual'),
                    ('argocd', 'ArgoCD'),
                    ('flux', 'Flux'),
                    ('none', 'None')
                ],
                default='manual',
                max_length=20,
                help_text='GitOps tool used for deployments'
            ),
        ),
        migrations.AddField(
            model_name='hedgehogfabric',
            name='gitops_app_name',
            field=models.CharField(blank=True, max_length=255, help_text='GitOps application name (for ArgoCD/Flux integration)'),
        ),
        migrations.AddField(
            model_name='hedgehogfabric',
            name='gitops_namespace',
            field=models.CharField(blank=True, max_length=255, help_text='GitOps application namespace'),
        ),
    ]