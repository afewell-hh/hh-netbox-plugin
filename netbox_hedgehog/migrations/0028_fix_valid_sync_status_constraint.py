# Generated migration to fix sync_status constraint

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_hedgehog', '0027_add_remaining_task_fields'),
    ]

    operations = [
        migrations.RunSQL(
            sql=[
                # Drop the old constraint with incorrect values
                "ALTER TABLE netbox_hedgehog_hedgehogfabric DROP CONSTRAINT IF EXISTS valid_sync_status;",
                
                # Add the new constraint with correct SyncStatusChoices values
                "ALTER TABLE netbox_hedgehog_hedgehogfabric ADD CONSTRAINT valid_sync_status CHECK (sync_status IN ('never_synced', 'in_sync', 'out_of_sync', 'syncing', 'error'));",
            ],
            reverse_sql=[
                # Reverse back to the old constraint if needed
                "ALTER TABLE netbox_hedgehog_hedgehogfabric DROP CONSTRAINT IF EXISTS valid_sync_status;",
                "ALTER TABLE netbox_hedgehog_hedgehogfabric ADD CONSTRAINT valid_sync_status CHECK (sync_status IN ('synced', 'syncing', 'error', 'never_synced'));",
            ]
        ),
    ]