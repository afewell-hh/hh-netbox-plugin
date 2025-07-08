# Generated migration for creating HedgehogResource dual-state model

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_hedgehog', '0008_add_gitops_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='HedgehogResource',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict, encoder=None)),
                ('tags', models.ManyToManyField(blank=True, related_name='%(app_label)s_%(class)s_related', to='extras.tag')),
                
                # Resource Identification
                ('name', models.CharField(help_text='Kubernetes resource name (DNS-1123 compliant)', max_length=253)),
                ('namespace', models.CharField(default='default', help_text='Kubernetes namespace for this resource', max_length=253)),
                ('kind', models.CharField(help_text='Kubernetes resource kind (VPC, Connection, Server, etc.)', max_length=50)),
                
                # Desired State (from Git repository)
                ('desired_spec', models.JSONField(blank=True, help_text='Desired resource specification from Git repository', null=True)),
                ('desired_commit', models.CharField(blank=True, help_text='Git commit SHA containing this desired state', max_length=40)),
                ('desired_file_path', models.CharField(blank=True, help_text='Path to YAML file in Git repository', max_length=500)),
                ('desired_updated', models.DateTimeField(blank=True, help_text='When desired state was last updated from Git', null=True)),
                
                # Actual State (from Kubernetes cluster)
                ('actual_spec', models.JSONField(blank=True, help_text='Actual resource specification from Kubernetes', null=True)),
                ('actual_status', models.JSONField(blank=True, help_text='Actual resource status from Kubernetes', null=True)),
                ('actual_resource_version', models.CharField(blank=True, help_text='Kubernetes resource version', max_length=50)),
                ('actual_updated', models.DateTimeField(blank=True, help_text='When actual state was last updated from Kubernetes', null=True)),
                
                # Drift Analysis
                ('drift_status', models.CharField(
                    choices=[
                        ('in_sync', 'In Sync'),
                        ('spec_drift', 'Spec Drift'),
                        ('desired_only', 'Desired Only'),
                        ('actual_only', 'Actual Only'),
                        ('creation_pending', 'Creation Pending'),
                        ('deletion_pending', 'Deletion Pending')
                    ],
                    default='in_sync',
                    help_text='Current drift status between desired and actual state',
                    max_length=20
                )),
                ('drift_details', models.JSONField(blank=True, default=dict, help_text='Detailed drift analysis including specific differences')),
                ('drift_score', models.FloatField(default=0.0, help_text='Numerical drift score (0.0 = no drift, 1.0 = complete drift)')),
                
                # Metadata
                ('labels', models.JSONField(blank=True, default=dict, help_text='Kubernetes labels as JSON')),
                ('annotations', models.JSONField(blank=True, default=dict, help_text='Kubernetes annotations as JSON')),
                
                # Tracking fields
                ('first_seen', models.DateTimeField(auto_now_add=True, help_text='When this resource was first discovered')),
                ('last_drift_check', models.DateTimeField(blank=True, help_text='When drift was last calculated for this resource', null=True)),
                
                # Foreign Key to HedgehogFabric
                ('fabric', models.ForeignKey(
                    help_text='Hedgehog fabric this resource belongs to',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='gitops_resources',
                    to='netbox_hedgehog.hedgehogfabric'
                )),
            ],
            options={
                'verbose_name': 'GitOps Resource',
                'verbose_name_plural': 'GitOps Resources',
                'ordering': ['fabric', 'namespace', 'kind', 'name'],
            },
        ),
        
        # Add unique constraint
        migrations.AddConstraint(
            model_name='hedgehogresource',
            constraint=models.UniqueConstraint(
                fields=['fabric', 'namespace', 'name', 'kind'],
                name='unique_hedgehogresource_per_fabric'
            ),
        ),
        
        # Add database indexes for performance
        migrations.AddIndex(
            model_name='hedgehogresource',
            index=models.Index(fields=['fabric', 'drift_status'], name='hedgehogresource_fabric_drift_idx'),
        ),
        migrations.AddIndex(
            model_name='hedgehogresource',
            index=models.Index(fields=['fabric', 'kind'], name='hedgehogresource_fabric_kind_idx'),
        ),
        migrations.AddIndex(
            model_name='hedgehogresource',
            index=models.Index(fields=['desired_commit'], name='hedgehogresource_desired_commit_idx'),
        ),
        migrations.AddIndex(
            model_name='hedgehogresource',
            index=models.Index(fields=['actual_updated'], name='hedgehogresource_actual_updated_idx'),
        ),
        migrations.AddIndex(
            model_name='hedgehogresource',
            index=models.Index(fields=['drift_status', 'drift_score'], name='hedgehogresource_drift_score_idx'),
        ),
        migrations.AddIndex(
            model_name='hedgehogresource',
            index=models.Index(fields=['fabric', 'kind', 'drift_status'], name='hedgehogresource_fabric_kind_drift_idx'),
        ),
    ]