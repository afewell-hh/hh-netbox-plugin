# Generated migration for adding connection and sync status fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_hedgehog', '0002_remaining_models'),
    ]

    operations = [
        migrations.AddField(
            model_name='hedgehogfabric',
            name='connection_status',
            field=models.CharField(
                choices=[
                    ('unknown', 'Unknown'),
                    ('connected', 'Connected'),
                    ('disconnected', 'Disconnected'),
                    ('error', 'Error'),
                ],
                default='unknown',
                help_text='Connection status - whether NetBox can connect to this fabric',
                max_length=20
            ),
        ),
        migrations.AddField(
            model_name='hedgehogfabric',
            name='sync_status',
            field=models.CharField(
                choices=[
                    ('never_synced', 'Never Synced'),
                    ('in_sync', 'In Sync'),
                    ('out_of_sync', 'Out of Sync'),
                    ('syncing', 'Syncing'),
                    ('error', 'Sync Error'),
                ],
                default='never_synced',
                help_text='Sync status - whether data is synchronized with Kubernetes',
                max_length=20
            ),
        ),
    ]