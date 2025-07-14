# Generated migration for implementing six-state resource management system

from django.db import migrations, models
from django.conf import settings
import django.db.models.deletion
import django.contrib.auth.models


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('netbox_hedgehog', '0009_create_hedgehogresource'),
    ]

    operations = [
        # Add new fields to HedgehogResource for six-state management
        migrations.AddField(
            model_name='hedgehogresource',
            name='api_version',
            field=models.CharField(default='unknown/v1', help_text='Kubernetes API version', max_length=100),
        ),
        
        # Draft State fields
        migrations.AddField(
            model_name='hedgehogresource',
            name='draft_spec',
            field=models.JSONField(blank=True, help_text='Draft resource specification (uncommitted)', null=True),
        ),
        migrations.AddField(
            model_name='hedgehogresource',
            name='draft_updated',
            field=models.DateTimeField(blank=True, help_text='When draft was last updated', null=True),
        ),
        migrations.AddField(
            model_name='hedgehogresource',
            name='draft_updated_by',
            field=models.ForeignKey(blank=True, help_text='User who last updated draft', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='draft_resources', to=settings.AUTH_USER_MODEL),
        ),
        
        # State tracking fields
        migrations.AddField(
            model_name='hedgehogresource',
            name='resource_state',
            field=models.CharField(
                choices=[
                    ('draft', 'Draft'),
                    ('committed', 'Committed'),
                    ('synced', 'Synced'),
                    ('drifted', 'Drifted'),
                    ('orphaned', 'Orphaned'),
                    ('pending', 'Pending'),
                ],
                default='draft',
                help_text='Current resource state',
                max_length=20
            ),
        ),
        migrations.AddField(
            model_name='hedgehogresource',
            name='last_state_change',
            field=models.DateTimeField(auto_now_add=True, help_text='Timestamp of last state change'),
        ),
        migrations.AddField(
            model_name='hedgehogresource',
            name='state_change_reason',
            field=models.TextField(blank=True, help_text='Reason for last state change'),
        ),
        
        # Enhanced drift tracking
        migrations.AddField(
            model_name='hedgehogresource',
            name='drift_severity',
            field=models.CharField(
                blank=True,
                choices=[
                    ('none', 'No Drift'),
                    ('low', 'Low'),
                    ('medium', 'Medium'),
                    ('high', 'High'),
                    ('critical', 'Critical'),
                ],
                help_text='Drift severity level',
                max_length=20
            ),
        ),
        migrations.AddField(
            model_name='hedgehogresource',
            name='last_reconciliation',
            field=models.DateTimeField(blank=True, help_text='Timestamp of last reconciliation attempt', null=True),
        ),
        migrations.AddField(
            model_name='hedgehogresource',
            name='reconciliation_attempts',
            field=models.PositiveIntegerField(default=0, help_text='Number of reconciliation attempts'),
        ),
        
        # Relationship tracking
        migrations.AddField(
            model_name='hedgehogresource',
            name='dependent_resources',
            field=models.ManyToManyField(
                blank=True,
                help_text='Resources this resource depends on',
                related_name='dependency_of',
                to='netbox_hedgehog.hedgehogresource'
            ),
        ),
        migrations.AddField(
            model_name='hedgehogresource',
            name='dependency_score',
            field=models.FloatField(default=0.0, help_text='Calculated dependency complexity score'),
        ),
        migrations.AddField(
            model_name='hedgehogresource',
            name='relationship_metadata',
            field=models.JSONField(blank=True, default=dict, help_text='Relationship metadata and caching'),
        ),
        
        # Sync tracking
        migrations.AddField(
            model_name='hedgehogresource',
            name='last_synced_commit',
            field=models.CharField(blank=True, help_text='Git commit SHA of last successful sync', max_length=40),
        ),
        migrations.AddField(
            model_name='hedgehogresource',
            name='sync_attempts',
            field=models.PositiveIntegerField(default=0, help_text='Number of sync attempts'),
        ),
        migrations.AddField(
            model_name='hedgehogresource',
            name='last_sync_error',
            field=models.TextField(blank=True, help_text='Last sync error message'),
        ),
        
        # User tracking
        migrations.AddField(
            model_name='hedgehogresource',
            name='created_by',
            field=models.ForeignKey(blank=True, help_text='User who created this resource', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_resources', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='hedgehogresource',
            name='last_modified_by',
            field=models.ForeignKey(blank=True, help_text='User who last modified this resource', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='modified_resources', to=settings.AUTH_USER_MODEL),
        ),
        
        # Create StateTransitionHistory model
        migrations.CreateModel(
            name='StateTransitionHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict, encoder=None)),
                ('tags', models.ManyToManyField(blank=True, related_name='%(app_label)s_%(class)s_related', to='extras.tag')),
                
                # Transition details
                ('from_state', models.CharField(
                    choices=[
                        ('draft', 'Draft'),
                        ('committed', 'Committed'),
                        ('synced', 'Synced'),
                        ('drifted', 'Drifted'),
                        ('orphaned', 'Orphaned'),
                        ('pending', 'Pending'),
                    ],
                    help_text='Previous state',
                    max_length=20
                )),
                ('to_state', models.CharField(
                    choices=[
                        ('draft', 'Draft'),
                        ('committed', 'Committed'),
                        ('synced', 'Synced'),
                        ('drifted', 'Drifted'),
                        ('orphaned', 'Orphaned'),
                        ('pending', 'Pending'),
                    ],
                    help_text='New state',
                    max_length=20
                )),
                ('trigger', models.CharField(help_text='What triggered the transition', max_length=50)),
                ('reason', models.TextField(blank=True, help_text='Reason for transition')),
                ('context', models.JSONField(blank=True, default=dict, help_text='Transition context')),
                ('timestamp', models.DateTimeField(auto_now_add=True, help_text='When transition occurred')),
                
                # Foreign Keys
                ('resource', models.ForeignKey(
                    help_text='Resource this transition belongs to',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='state_history',
                    to='netbox_hedgehog.hedgehogresource'
                )),
                ('user', models.ForeignKey(
                    blank=True,
                    help_text='User who triggered transition',
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to=settings.AUTH_USER_MODEL
                )),
            ],
            options={
                'verbose_name': 'State Transition History',
                'verbose_name_plural': 'State Transition Histories',
                'ordering': ['-timestamp'],
            },
        ),
        
        # Update HedgehogResource model metadata
        migrations.AlterModelOptions(
            name='hedgehogresource',
            options={
                'verbose_name': 'Hedgehog Resource',
                'verbose_name_plural': 'Hedgehog Resources',
                'ordering': ['fabric', 'namespace', 'kind', 'name'],
            },
        ),
        
        # Add new indexes for enhanced performance
        migrations.AddIndex(
            model_name='hedgehogresource',
            index=models.Index(fields=['fabric', 'resource_state'], name='hedgehogresource_fabric_state_idx'),
        ),
        migrations.AddIndex(
            model_name='hedgehogresource',
            index=models.Index(fields=['resource_state', 'last_state_change'], name='hedgehogresource_state_change_idx'),
        ),
        migrations.AddIndex(
            model_name='hedgehogresource',
            index=models.Index(fields=['last_reconciliation'], name='hedgehogresource_reconciliation_idx'),
        ),
        migrations.AddIndex(
            model_name='hedgehogresource',
            index=models.Index(fields=['fabric', 'kind', 'resource_state'], name='hedgehogresource_fabric_kind_state_idx'),
        ),
        
        # Add indexes for StateTransitionHistory
        migrations.AddIndex(
            model_name='statetransitionhistory',
            index=models.Index(fields=['resource', 'timestamp'], name='statetransitionhistory_resource_timestamp_idx'),
        ),
        migrations.AddIndex(
            model_name='statetransitionhistory',
            index=models.Index(fields=['resource', 'to_state'], name='statetransitionhistory_resource_to_state_idx'),
        ),
        migrations.AddIndex(
            model_name='statetransitionhistory',
            index=models.Index(fields=['timestamp'], name='statetransitionhistory_timestamp_idx'),
        ),
        migrations.AddIndex(
            model_name='statetransitionhistory',
            index=models.Index(fields=['from_state', 'to_state'], name='statetransitionhistory_from_to_state_idx'),
        ),
    ]