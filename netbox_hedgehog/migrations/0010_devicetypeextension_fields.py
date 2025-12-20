# Generated manually - adds new fields to DeviceTypeExtension and tags to DIET models
# Avoids problematic AlterField operations on operational models

from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_hedgehog', '0009_seed_data_hedgehog_devices'),
    ]

    operations = [
        # Add tags field to BreakoutOption (required for NetBox models)
        migrations.AddField(
            model_name='breakoutoption',
            name='tags',
            field=models.ManyToManyField(blank=True, related_name='+', to='extras.tag'),
        ),

        # Add new fields to DeviceTypeExtension for breakout selection
        migrations.AddField(
            model_name='devicetypeextension',
            name='supported_breakouts',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="List of supported breakout IDs (e.g., ['1x800g', '2x400g', '4x200g']). Used by calc engine to select appropriate BreakoutOption."
            ),
        ),
        migrations.AddField(
            model_name='devicetypeextension',
            name='native_speed',
            field=models.IntegerField(
                blank=True,
                null=True,
                help_text='Native port speed in Gbps (e.g., 800 for 800G). Used for fallback when no breakout matches.'
            ),
        ),
        migrations.AddField(
            model_name='devicetypeextension',
            name='uplink_ports',
            field=models.IntegerField(
                blank=True,
                null=True,
                validators=[django.core.validators.MinValueValidator(0)],
                help_text='Default number of uplink ports to reserve for spine connections'
            ),
        ),

        # Add tags field to DeviceTypeExtension (required for NetBox models)
        migrations.AddField(
            model_name='devicetypeextension',
            name='tags',
            field=models.ManyToManyField(blank=True, related_name='+', to='extras.tag'),
        ),
    ]
