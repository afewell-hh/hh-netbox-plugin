# Generated migration for ArgoCD tracking fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_hedgehog', '0012_add_genericforeignkey_to_hedgehogresource'),
    ]

    operations = [
        migrations.AddField(
            model_name='hedgehogfabric',
            name='argocd_installed',
            field=models.BooleanField(
                default=False,
                help_text="Whether ArgoCD is installed and configured for this fabric"
            ),
        ),
        migrations.AddField(
            model_name='hedgehogfabric',
            name='argocd_version',
            field=models.CharField(
                max_length=50,
                blank=True,
                help_text="Version of ArgoCD installed"
            ),
        ),
        migrations.AddField(
            model_name='hedgehogfabric',
            name='argocd_server_url',
            field=models.URLField(
                blank=True,
                help_text="ArgoCD server URL for this fabric"
            ),
        ),
        migrations.AddField(
            model_name='hedgehogfabric',
            name='argocd_health_status',
            field=models.CharField(
                max_length=20,
                choices=[
                    ('unknown', 'Unknown'),
                    ('healthy', 'Healthy'),
                    ('unhealthy', 'Unhealthy'),
                    ('degraded', 'Degraded'),
                    ('installing', 'Installing'),
                    ('failed', 'Failed')
                ],
                default='unknown',
                help_text="Current ArgoCD health status"
            ),
        ),
        migrations.AddField(
            model_name='hedgehogfabric',
            name='argocd_installation_date',
            field=models.DateTimeField(
                null=True,
                blank=True,
                help_text="When ArgoCD was installed for this fabric"
            ),
        ),
        migrations.AddField(
            model_name='hedgehogfabric',
            name='argocd_admin_password',
            field=models.CharField(
                max_length=255,
                blank=True,
                help_text="ArgoCD admin password (encrypted)"
            ),
        ),
        migrations.AddField(
            model_name='hedgehogfabric',
            name='gitops_setup_status',
            field=models.CharField(
                max_length=30,
                choices=[
                    ('not_configured', 'Not Configured'),
                    ('manual', 'Manual'),
                    ('installing', 'Installing'),
                    ('configured', 'Configured'),
                    ('ready', 'Ready'),
                    ('error', 'Error')
                ],
                default='not_configured',
                help_text="Overall GitOps setup status for this fabric"
            ),
        ),
        migrations.AddField(
            model_name='hedgehogfabric',
            name='gitops_setup_error',
            field=models.TextField(
                blank=True,
                help_text="Last GitOps setup error message"
            ),
        ),
        migrations.AddField(
            model_name='hedgehogfabric',
            name='auto_sync_enabled',
            field=models.BooleanField(
                default=True,
                help_text="Enable automatic synchronization for GitOps applications"
            ),
        ),
        migrations.AddField(
            model_name='hedgehogfabric',
            name='prune_enabled',
            field=models.BooleanField(
                default=False,
                help_text="Enable resource pruning in GitOps applications"
            ),
        ),
        migrations.AddField(
            model_name='hedgehogfabric',
            name='self_heal_enabled',
            field=models.BooleanField(
                default=True,
                help_text="Enable self-healing in GitOps applications"
            ),
        ),
        # Update existing choice field to include more GitOps tools
        migrations.AlterField(
            model_name='hedgehogfabric',
            name='gitops_tool',
            field=models.CharField(
                max_length=20,
                choices=[
                    ('manual', 'Manual'),
                    ('argocd', 'ArgoCD'),
                    ('flux', 'Flux'),
                    ('tekton', 'Tekton'),
                    ('jenkins', 'Jenkins'),
                    ('none', 'None')
                ],
                default='manual',
                help_text="GitOps tool used for deployments"
            ),
        ),
    ]