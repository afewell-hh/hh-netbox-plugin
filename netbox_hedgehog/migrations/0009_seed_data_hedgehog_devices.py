# Generated manually - seed data for common Hedgehog devices
# Creates DeviceTypes and BreakoutOptions for typical Hedgehog deployments

from django.db import migrations


def load_seed_data(apps, schema_editor):
    """
    Load seed data for common Hedgehog network devices.

    Creates:
    - Manufacturers (Celestica, NVIDIA, Edge-Core)
    - DeviceTypes for common switches
    - InterfaceTemplates for ports
    - DeviceTypeExtensions for Hedgehog-specific metadata
    - BreakoutOptions for common breakout configurations
    """
    # Get models
    Manufacturer = apps.get_model('dcim', 'Manufacturer')
    DeviceType = apps.get_model('dcim', 'DeviceType')
    InterfaceTemplate = apps.get_model('dcim', 'InterfaceTemplate')
    DeviceTypeExtension = apps.get_model('netbox_hedgehog', 'DeviceTypeExtension')
    BreakoutOption = apps.get_model('netbox_hedgehog', 'BreakoutOption')

    # Create manufacturers
    celestica, _ = Manufacturer.objects.get_or_create(
        name='Celestica',
        defaults={'slug': 'celestica'}
    )

    nvidia, _ = Manufacturer.objects.get_or_create(
        name='NVIDIA',
        defaults={'slug': 'nvidia'}
    )

    edgecore, _ = Manufacturer.objects.get_or_create(
        name='Edge-Core',
        defaults={'slug': 'edge-core'}
    )

    # ========================================================================
    # Celestica DS5000 - 64x 800G QSFP-DD Switch
    # ========================================================================
    ds5000, created = DeviceType.objects.get_or_create(
        manufacturer=celestica,
        model='DS5000',
        defaults={
            'slug': 'ds5000',
            'u_height': 1,
            'is_full_depth': True,
            'comments': '64-port 800G QSFP-DD switch for Hedgehog spine/leaf',
        }
    )

    if created:
        # Create interface templates for DS5000
        for i in range(1, 65):
            InterfaceTemplate.objects.create(
                device_type=ds5000,
                name=f'Ethernet1/{i}',
                type='800gbase-x-qsfpdd',
            )

        # Add Hedgehog metadata
        DeviceTypeExtension.objects.create(
            device_type=ds5000,
            mclag_capable=False,
            hedgehog_roles=['spine', 'server-leaf'],
            supported_breakouts=['1x800g', '2x400g', '4x200g', '8x100g'],
            native_speed=800,
            uplink_ports=8,
            notes='Primary switch for large Hedgehog deployments. Supports 800G native with breakout to 400G/200G/100G.',
        )

    # ========================================================================
    # Celestica DS3000 - 32x 100G QSFP28 Switch
    # ========================================================================
    ds3000, created = DeviceType.objects.get_or_create(
        manufacturer=celestica,
        model='DS3000',
        defaults={
            'slug': 'ds3000',
            'u_height': 1,
            'is_full_depth': True,
            'comments': '32-port 100G QSFP28 switch for Hedgehog leaf/border',
        }
    )

    if created:
        # Create interface templates for DS3000
        for i in range(1, 33):
            InterfaceTemplate.objects.create(
                device_type=ds3000,
                name=f'Ethernet1/{i}',
                type='100gbase-x-qsfp28',
            )

        # Add Hedgehog metadata
        DeviceTypeExtension.objects.create(
            device_type=ds3000,
            mclag_capable=False,
            hedgehog_roles=['server-leaf', 'border-leaf'],
            supported_breakouts=['1x100g', '4x25g', '4x10g'],
            native_speed=100,
            uplink_ports=4,
            notes='Smaller switch for edge/border deployments. Supports 100G native with breakout to 25G/10G.',
        )

    # ========================================================================
    # NVIDIA SN5600 - 64x 800G QSFP-DD Switch with MCLAG
    # ========================================================================
    sn5600, created = DeviceType.objects.get_or_create(
        manufacturer=nvidia,
        model='SN5600',
        defaults={
            'slug': 'sn5600',
            'u_height': 1,
            'is_full_depth': True,
            'comments': '64-port 800G QSFP-DD switch with MCLAG support',
        }
    )

    if created:
        # Create interface templates for SN5600
        for i in range(1, 65):
            InterfaceTemplate.objects.create(
                device_type=sn5600,
                name=f'Ethernet1/{i}',
                type='800gbase-x-qsfpdd',
            )

        # Add Hedgehog metadata
        DeviceTypeExtension.objects.create(
            device_type=sn5600,
            mclag_capable=True,
            hedgehog_roles=['spine', 'server-leaf'],
            supported_breakouts=['1x800g', '2x400g', '4x200g', '8x100g'],
            native_speed=800,
            uplink_ports=8,
            notes='High-end switch with MCLAG support for redundant topologies. 800G native with breakout options.',
        )

    # ========================================================================
    # Edge-Core ES1000-48 - Virtual/Management Switch
    # ========================================================================
    es1000, created = DeviceType.objects.get_or_create(
        manufacturer=edgecore,
        model='ES1000-48',
        defaults={
            'slug': 'es1000-48',
            'u_height': 1,
            'is_full_depth': False,
            'comments': '48-port 1G switch for management/virtual networks',
        }
    )

    if created:
        # Create interface templates for ES1000-48
        for i in range(1, 49):
            InterfaceTemplate.objects.create(
                device_type=es1000,
                name=f'Ethernet1/{i}',
                type='1000base-t',
            )

        # Add Hedgehog metadata
        DeviceTypeExtension.objects.create(
            device_type=es1000,
            mclag_capable=False,
            hedgehog_roles=['virtual'],
            supported_breakouts=['1x1g'],
            native_speed=1,
            uplink_ports=2,
            notes='Management and virtual network switch. 1G copper ports.',
        )

    # ========================================================================
    # BreakoutOptions - Common breakout configurations
    # ========================================================================

    # 800G breakout options
    BreakoutOption.objects.get_or_create(
        breakout_id='1x800g',
        defaults={
            'from_speed': 800,
            'logical_ports': 1,
            'logical_speed': 800,
            'optic_type': 'QSFP-DD',
        }
    )

    BreakoutOption.objects.get_or_create(
        breakout_id='2x400g',
        defaults={
            'from_speed': 800,
            'logical_ports': 2,
            'logical_speed': 400,
            'optic_type': 'QSFP-DD',
        }
    )

    BreakoutOption.objects.get_or_create(
        breakout_id='4x200g',
        defaults={
            'from_speed': 800,
            'logical_ports': 4,
            'logical_speed': 200,
            'optic_type': 'QSFP-DD',
        }
    )

    BreakoutOption.objects.get_or_create(
        breakout_id='8x100g',
        defaults={
            'from_speed': 800,
            'logical_ports': 8,
            'logical_speed': 100,
            'optic_type': 'QSFP-DD',
        }
    )

    # 100G breakout options
    BreakoutOption.objects.get_or_create(
        breakout_id='1x100g',
        defaults={
            'from_speed': 100,
            'logical_ports': 1,
            'logical_speed': 100,
            'optic_type': 'QSFP28',
        }
    )

    BreakoutOption.objects.get_or_create(
        breakout_id='4x25g',
        defaults={
            'from_speed': 100,
            'logical_ports': 4,
            'logical_speed': 25,
            'optic_type': 'QSFP28',
        }
    )

    BreakoutOption.objects.get_or_create(
        breakout_id='4x10g',
        defaults={
            'from_speed': 100,
            'logical_ports': 4,
            'logical_speed': 10,
            'optic_type': 'QSFP28',
        }
    )

    # 1G (no breakout)
    BreakoutOption.objects.get_or_create(
        breakout_id='1x1g',
        defaults={
            'from_speed': 1,
            'logical_ports': 1,
            'logical_speed': 1,
            'optic_type': 'RJ45',
        }
    )


def remove_seed_data(apps, schema_editor):
    """
    Remove seed data (reverse migration).

    WARNING: This will delete DeviceTypes and their extensions.
    Only safe to run if no real data depends on these DeviceTypes.
    """
    DeviceType = apps.get_model('dcim', 'DeviceType')
    BreakoutOption = apps.get_model('netbox_hedgehog', 'BreakoutOption')

    # Delete DeviceTypes (will cascade to DeviceTypeExtension and InterfaceTemplates)
    DeviceType.objects.filter(model__in=['DS5000', 'DS3000', 'SN5600', 'ES1000-48']).delete()

    # Delete BreakoutOptions
    BreakoutOption.objects.filter(
        breakout_id__in=[
            '1x800g', '2x400g', '4x200g', '8x100g',
            '1x100g', '4x25g', '4x10g', '1x1g'
        ]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('dcim', '0216_latitude_longitude_validators'),
        ('netbox_hedgehog', '0008_topology_planning_models'),
    ]

    operations = [
        migrations.RunPython(load_seed_data, remove_seed_data),
    ]
