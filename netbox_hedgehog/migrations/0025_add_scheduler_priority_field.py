"""
Add scheduler_priority field to HedgehogFabric model.

This migration adds the missing scheduler_priority field that is defined
in the model but missing from the database schema, causing ProgrammingError
when accessing fabric list pages.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_hedgehog', '0024_fix_syncop_index_name_length'),
    ]

    operations = [
        migrations.AddField(
            model_name='hedgehogfabric',
            name='scheduler_priority',
            field=models.CharField(
                max_length=20,
                choices=[
                    ('critical', 'Critical'),
                    ('high', 'High'), 
                    ('medium', 'Medium'),
                    ('low', 'Low'),
                    ('maintenance', 'Maintenance')
                ],
                default='medium',
                help_text="Scheduler priority level for sync operations"
            ),
        ),
    ]