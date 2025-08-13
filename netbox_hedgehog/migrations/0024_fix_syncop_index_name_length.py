"""
Fix SyncOperation index name length constraint violation.

The index name 'hnp_syncop_fabric_type_started_idx' (36 chars) exceeds 
Django's 30-character limit. This migration renames it to 
'hnp_syncop_fab_type_start_idx' (29 chars).
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_hedgehog', '0023_add_scheduler_enabled_field'),
    ]

    operations = [
        # Remove the problematic index
        migrations.RunSQL(
            "DROP INDEX IF EXISTS hnp_syncop_fabric_type_started_idx;",
            reverse_sql="-- No reverse action needed"
        ),
        # Add the correctly named index
        migrations.AddIndex(
            model_name='syncoperation',
            index=models.Index(
                fields=['fabric', 'operation_type', 'started_at'], 
                name='hnp_syncop_fab_type_start_idx'
            ),
        ),
    ]