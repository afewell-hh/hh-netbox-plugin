# Generated migration for real-time monitoring fields

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_hedgehog', '0015_add_git_sync_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='hedgehogfabric',
            name='watch_enabled',
            field=models.BooleanField(default=True, help_text='Enable real-time Kubernetes CRD watching for this fabric'),
        ),
        migrations.AddField(
            model_name='hedgehogfabric',
            name='watch_crd_types',
            field=models.JSONField(default=list, help_text='List of CRD types to watch (empty for all supported types)'),
        ),
        migrations.AddField(
            model_name='hedgehogfabric',
            name='watch_status',
            field=models.CharField(
                choices=[
                    ('inactive', 'Inactive'),
                    ('starting', 'Starting'),
                    ('active', 'Active'),
                    ('error', 'Error'),
                    ('stopped', 'Stopped')
                ],
                default='inactive',
                help_text='Current watch status for real-time monitoring',
                max_length=20
            ),
        ),
        migrations.AddField(
            model_name='hedgehogfabric',
            name='watch_started_at',
            field=models.DateTimeField(blank=True, help_text='When real-time watching was started', null=True),
        ),
        migrations.AddField(
            model_name='hedgehogfabric',
            name='watch_last_event',
            field=models.DateTimeField(blank=True, help_text='Timestamp of last watch event received', null=True),
        ),
        migrations.AddField(
            model_name='hedgehogfabric',
            name='watch_event_count',
            field=models.PositiveIntegerField(default=0, help_text='Total number of watch events processed'),
        ),
        migrations.AddField(
            model_name='hedgehogfabric',
            name='watch_error_message',
            field=models.TextField(blank=True, help_text='Last watch error message'),
        ),
    ]