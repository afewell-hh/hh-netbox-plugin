"""Migration 0034: Expand FabricTypeChoices with management fabric types.

This is a state-only migration (AlterField). No schema change because the
fabric column is a VARCHAR and the new values are simply additional valid
choices. Existing 'oob' data is unaffected.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_hedgehog', '0033_finalize_zone_targeted'),
    ]

    operations = [
        migrations.AlterField(
            model_name='planswitchclass',
            name='fabric',
            field=models.CharField(
                blank=True,
                choices=[
                    ('frontend', 'Frontend'),
                    ('backend', 'Backend'),
                    ('oob', 'Out-of-Band (DEPRECATED)'),
                    ('oob-mgmt', 'OOB Management'),
                    ('in-band-mgmt', 'In-Band Management'),
                    ('network-mgmt', 'Network Management'),
                ],
                help_text='Fabric type. Frontend and Backend are Hedgehog-managed (appear in wiring YAML). '
                          'Management types are tracked for inventory but excluded from wiring export. '
                          'Out-of-Band (oob) is deprecated; use oob-mgmt instead.',
                max_length=50,
            ),
        ),
    ]
