"""
Add remaining scheduler fields to HedgehogFabric model.

This migration adds the sync_plan_version, last_scheduler_run, sync_health_score,
and scheduler_metadata fields that are defined in the model but missing from 
the database schema.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_hedgehog', '0025_add_scheduler_priority_field'),
    ]

    operations = [
        migrations.AddField(
            model_name='hedgehogfabric',
            name='sync_plan_version',
            field=models.PositiveIntegerField(
                default=1,
                help_text="Version of current sync plan (incremented on plan changes)"
            ),
        ),
        migrations.AddField(
            model_name='hedgehogfabric',
            name='last_scheduler_run',
            field=models.DateTimeField(
                null=True,
                blank=True,
                help_text="Timestamp of last master scheduler run for this fabric"
            ),
        ),
        migrations.AddField(
            model_name='hedgehogfabric',
            name='sync_health_score',
            field=models.FloatField(
                default=1.0,
                help_text="Health score calculated by scheduler (0.0=critical, 1.0=healthy)"
            ),
        ),
        migrations.AddField(
            model_name='hedgehogfabric',
            name='scheduler_metadata',
            field=models.JSONField(
                default=dict,
                help_text="Scheduler-specific metadata and planning information"
            ),
        ),
    ]