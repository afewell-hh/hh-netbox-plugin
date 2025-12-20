# Generated manually - updates existing DeviceTypeExtension records with breakout data
from django.db import migrations


def update_extension_data(apps, schema_editor):
    """
    Update existing DeviceTypeExtension records with supported_breakouts,
    native_speed, and uplink_ports fields.
    """
    DeviceType = apps.get_model('dcim', 'DeviceType')
    DeviceTypeExtension = apps.get_model('netbox_hedgehog', 'DeviceTypeExtension')

    # Update DS5000
    ds5000 = DeviceType.objects.filter(model='DS5000').first()
    if ds5000 and hasattr(ds5000, 'hedgehog_metadata'):
        ext = ds5000.hedgehog_metadata
        ext.supported_breakouts = ['1x800g', '2x400g', '4x200g', '8x100g']
        ext.native_speed = 800
        ext.uplink_ports = 8
        ext.save()

    # Update DS3000
    ds3000 = DeviceType.objects.filter(model='DS3000').first()
    if ds3000 and hasattr(ds3000, 'hedgehog_metadata'):
        ext = ds3000.hedgehog_metadata
        ext.supported_breakouts = ['1x100g', '4x25g', '4x10g']
        ext.native_speed = 100
        ext.uplink_ports = 4
        ext.save()

    # Update SN5600
    sn5600 = DeviceType.objects.filter(model='SN5600').first()
    if sn5600 and hasattr(sn5600, 'hedgehog_metadata'):
        ext = sn5600.hedgehog_metadata
        ext.supported_breakouts = ['1x800g', '2x400g', '4x200g', '8x100g']
        ext.native_speed = 800
        ext.uplink_ports = 8
        ext.save()

    # Update ES1000-48
    es1000 = DeviceType.objects.filter(model='ES1000-48').first()
    if es1000 and hasattr(es1000, 'hedgehog_metadata'):
        ext = es1000.hedgehog_metadata
        ext.supported_breakouts = ['1x1g']
        ext.native_speed = 1
        ext.uplink_ports = 2
        ext.save()


def reverse_update(apps, schema_editor):
    """
    Reverse migration - clear the fields.
    """
    DeviceTypeExtension = apps.get_model('netbox_hedgehog', 'DeviceTypeExtension')

    for ext in DeviceTypeExtension.objects.all():
        ext.supported_breakouts = []
        ext.native_speed = None
        ext.uplink_ports = None
        ext.save()


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_hedgehog', '0010_devicetypeextension_fields'),
    ]

    operations = [
        migrations.RunPython(update_extension_data, reverse_update),
    ]
