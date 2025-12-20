# No-op migration - previously updated DeviceTypeExtension records with breakout data
# This is now handled by migration 0009_seed_data_hedgehog_devices which runs after
# 0010_devicetypeextension_fields, so the data is seeded with all fields from the start.
from django.db import migrations


def noop(apps, schema_editor):
    """
    No-op function - seed data now creates records with all fields.
    Migration order was fixed so 0009 runs after 0010.
    """
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_hedgehog', '0009_seed_data_hedgehog_devices'),
    ]

    operations = [
        migrations.RunPython(noop, noop),
    ]
