"""
Add remaining task-related fields to HedgehogFabric model.

This migration adds the active_sync_tasks, last_task_execution, 
task_execution_count, and failed_task_count fields that are defined 
in the model but missing from the database schema.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_hedgehog', '0026_add_scheduler_additional_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='hedgehogfabric',
            name='active_sync_tasks',
            field=models.JSONField(
                default=list,
                help_text="List of currently executing sync tasks"
            ),
        ),
        migrations.AddField(
            model_name='hedgehogfabric',
            name='last_task_execution',
            field=models.DateTimeField(
                null=True,
                blank=True,
                help_text="Timestamp of last task execution attempt"
            ),
        ),
        migrations.AddField(
            model_name='hedgehogfabric',
            name='task_execution_count',
            field=models.PositiveIntegerField(
                default=0,
                help_text="Total number of sync tasks executed"
            ),
        ),
        migrations.AddField(
            model_name='hedgehogfabric',
            name='failed_task_count',
            field=models.PositiveIntegerField(
                default=0,
                help_text="Number of failed sync task executions"
            ),
        ),
    ]