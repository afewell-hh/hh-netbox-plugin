"""
Migration 0045: Add mismatch_report JSONField to GenerationState.

Stage 2 (DIET-334): Stores structured list of transceiver incompatibilities
found during the post-generation pairwise compatibility sweep. Null when
generation succeeded or has not yet been run; populated before status is
set to FAILED when the sweep finds mismatches.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_hedgehog', '0044_transceiver_module_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='generationstate',
            name='mismatch_report',
            field=models.JSONField(
                null=True,
                blank=True,
                default=None,
                help_text=(
                    'Structured list of transceiver incompatibilities found during '
                    'post-generation pairwise sweep. Null when generation succeeded '
                    'or has not run. Set before status=FAILED when mismatches found.'
                ),
            ),
        ),
    ]
