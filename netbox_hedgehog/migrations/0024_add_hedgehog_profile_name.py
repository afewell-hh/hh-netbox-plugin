# Generated manually for issue #143
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_hedgehog', '0023_backfill_nic_slot_legacy'),
    ]

    operations = [
        migrations.AddField(
            model_name='devicetypeextension',
            name='hedgehog_profile_name',
            field=models.CharField(
                blank=True,
                max_length=100,
                null=True,
                help_text="Hedgehog fabric switch profile name (e.g., 'celestica-ds5000', 'dell-s5248f-on'). "
                          "Imported from fabric profile metadata. Allows tracking the original profile source."
            ),
        ),
    ]
