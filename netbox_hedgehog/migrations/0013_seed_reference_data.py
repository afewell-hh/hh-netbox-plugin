# Generated manually - seeds reference data after all fields exist
# Populates supported_breakouts, native_speed, and uplink_ports for DeviceTypeExtension
# records created in migration 0009 after fields were added in migration 0010.
from django.db import migrations


def seed_reference_data(apps, schema_editor):
    """
    Populate DeviceTypeExtension records with breakout/speed/uplink data.

    Migration 0009 created base DeviceTypeExtension records.
    Migration 0010 added supported_breakouts, native_speed, uplink_ports fields.
    This migration (0013) populates those fields after all models exist.
    """
    DeviceType = apps.get_model('dcim', 'DeviceType')
    DeviceTypeExtension = apps.get_model('netbox_hedgehog', 'DeviceTypeExtension')

    # Update DS5000 - 64x 800G switch
    ds5000 = DeviceType.objects.filter(model='DS5000').first()
    if ds5000:
        try:
            ext = DeviceTypeExtension.objects.get(device_type=ds5000)
            ext.supported_breakouts = ['1x800g', '2x400g', '4x200g', '8x100g']
            ext.native_speed = 800
            ext.uplink_ports = 8
            ext.save()
        except DeviceTypeExtension.DoesNotExist:
            # Create if doesn't exist (shouldn't happen but safe)
            DeviceTypeExtension.objects.create(
                device_type=ds5000,
                mclag_capable=False,
                hedgehog_roles=['spine', 'server-leaf'],
                supported_breakouts=['1x800g', '2x400g', '4x200g', '8x100g'],
                native_speed=800,
                uplink_ports=8,
                notes='Primary switch for large Hedgehog deployments. Supports 800G native with breakout to 400G/200G/100G.',
            )

    # Update DS3000 - 32x 100G switch
    ds3000 = DeviceType.objects.filter(model='DS3000').first()
    if ds3000:
        try:
            ext = DeviceTypeExtension.objects.get(device_type=ds3000)
            ext.supported_breakouts = ['1x100g', '4x25g', '4x10g']
            ext.native_speed = 100
            ext.uplink_ports = 4
            ext.save()
        except DeviceTypeExtension.DoesNotExist:
            DeviceTypeExtension.objects.create(
                device_type=ds3000,
                mclag_capable=False,
                hedgehog_roles=['server-leaf', 'border-leaf'],
                supported_breakouts=['1x100g', '4x25g', '4x10g'],
                native_speed=100,
                uplink_ports=4,
                notes='Smaller switch for edge/border deployments. Supports 100G native with breakout to 25G/10G.',
            )

    # Update SN5600 - 64x 800G switch with MCLAG
    sn5600 = DeviceType.objects.filter(model='SN5600').first()
    if sn5600:
        try:
            ext = DeviceTypeExtension.objects.get(device_type=sn5600)
            ext.supported_breakouts = ['1x800g', '2x400g', '4x200g', '8x100g']
            ext.native_speed = 800
            ext.uplink_ports = 8
            ext.save()
        except DeviceTypeExtension.DoesNotExist:
            DeviceTypeExtension.objects.create(
                device_type=sn5600,
                mclag_capable=True,
                hedgehog_roles=['spine', 'server-leaf'],
                supported_breakouts=['1x800g', '2x400g', '4x200g', '8x100g'],
                native_speed=800,
                uplink_ports=8,
                notes='High-end switch with MCLAG support for redundant topologies. 800G native with breakout options.',
            )

    # Update ES1000-48 - Management switch
    es1000 = DeviceType.objects.filter(model='ES1000-48').first()
    if es1000:
        try:
            ext = DeviceTypeExtension.objects.get(device_type=es1000)
            ext.supported_breakouts = ['1x1g']
            ext.native_speed = 1
            ext.uplink_ports = 2
            ext.save()
        except DeviceTypeExtension.DoesNotExist:
            DeviceTypeExtension.objects.create(
                device_type=es1000,
                mclag_capable=False,
                hedgehog_roles=['virtual'],
                supported_breakouts=['1x1g'],
                native_speed=1,
                uplink_ports=2,
                notes='Management and virtual network switch. 1G copper ports.',
            )


def reverse_seed_data(apps, schema_editor):
    """
    Reverse migration - clear the populated fields.
    """
    DeviceTypeExtension = apps.get_model('netbox_hedgehog', 'DeviceTypeExtension')

    for ext in DeviceTypeExtension.objects.all():
        ext.supported_breakouts = []
        ext.native_speed = None
        ext.uplink_ports = None
        ext.save()


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_hedgehog', '0012_topology_plan_models'),
    ]

    operations = [
        migrations.RunPython(seed_reference_data, reverse_seed_data),
    ]
