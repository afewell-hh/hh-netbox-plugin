"""
Migration 0029: Seed NIC ModuleTypes for DIET-173 Phase 5.

Creates NetBox-native ModuleTypes for NVIDIA NICs:
- BlueField-3 BF3220 (dual-port QSFP112)
- ConnectX-7 (Single-Port) (single QSFP112)
- ConnectX-7 (Dual-Port) (dual QSFP112)

Each ModuleType includes InterfaceTemplates and transceiver attributes
following the Phase 3 technical specification.
"""

from django.db import migrations


def seed_nic_module_types(apps, schema_editor):
    """Seed NIC ModuleTypes with transceiver attributes."""
    Manufacturer = apps.get_model('dcim', 'Manufacturer')
    ModuleType = apps.get_model('dcim', 'ModuleType')
    InterfaceTemplate = apps.get_model('dcim', 'InterfaceTemplate')
    ModuleTypeProfile = apps.get_model('dcim', 'ModuleTypeProfile')

    # 1. Create or get NVIDIA manufacturer
    nvidia, _ = Manufacturer.objects.get_or_create(
        name='NVIDIA',
        defaults={'slug': 'nvidia'}
    )

    # 2. Create ModuleTypeProfile for Network Transceivers
    transceiver_profile, _ = ModuleTypeProfile.objects.get_or_create(
        name='Network Transceiver',
        defaults={
            'schema': {
                'type': 'object',
                'properties': {
                    'cage_type': {
                        'type': 'string',
                        'enum': ['QSFP112', 'QSFP-DD', 'QSFP28', 'SFP28']
                    },
                    'medium': {
                        'type': 'string',
                        'enum': ['MMF', 'SMF', 'DAC']
                    },
                    'connector': {
                        'type': 'string',
                        'enum': ['LC', 'MPO-12', 'Direct']
                    },
                    'wavelength_nm': {
                        'type': 'integer'
                    },
                    'standard': {
                        'type': 'string'
                    },
                    'reach_class': {
                        'type': 'string',
                        'enum': ['SR', 'LR', 'DR', 'DAC']
                    }
                }
            }
        }
    )

    # 3. Create BlueField-3 BF3220 (dual-port QSFP112)
    bf3_type, bf3_created = ModuleType.objects.get_or_create(
        manufacturer=nvidia,
        model='BlueField-3 BF3220',
        defaults={
            'profile': transceiver_profile,
            'attribute_data': {
                'cage_type': 'QSFP112',
                'medium': 'MMF',
                'connector': 'MPO-12',
                'wavelength_nm': 850,
                'standard': '200GBASE-SR4',
                'reach_class': 'SR',
            }
        }
    )

    # Create InterfaceTemplates for BlueField-3 (if just created)
    if bf3_created:
        InterfaceTemplate.objects.create(
            module_type=bf3_type,
            name='p0',
            type='200gbase-x-qsfp112'
        )
        InterfaceTemplate.objects.create(
            module_type=bf3_type,
            name='p1',
            type='200gbase-x-qsfp112'
        )

    # 4. Create ConnectX-7 (Single-Port) (single QSFP112)
    cx7_single, cx7_single_created = ModuleType.objects.get_or_create(
        manufacturer=nvidia,
        model='ConnectX-7 (Single-Port)',
        defaults={
            'profile': transceiver_profile,
            'attribute_data': {
                'cage_type': 'QSFP112',
                'medium': 'DAC',
                'connector': 'Direct',
                'standard': '200GBASE-CR4',
                'reach_class': 'DAC',
            }
        }
    )

    if cx7_single_created:
        InterfaceTemplate.objects.create(
            module_type=cx7_single,
            name='port0',
            type='200gbase-x-qsfp112'
        )

    # 5. Create ConnectX-7 (Dual-Port) (dual QSFP112)
    cx7_dual, cx7_dual_created = ModuleType.objects.get_or_create(
        manufacturer=nvidia,
        model='ConnectX-7 (Dual-Port)',
        defaults={
            'profile': transceiver_profile,
            'attribute_data': {
                'cage_type': 'QSFP112',
                'medium': 'DAC',
                'connector': 'Direct',
                'standard': '200GBASE-CR4',
                'reach_class': 'DAC',
            }
        }
    )

    if cx7_dual_created:
        InterfaceTemplate.objects.create(
            module_type=cx7_dual,
            name='port0',
            type='200gbase-x-qsfp112'
        )
        InterfaceTemplate.objects.create(
            module_type=cx7_dual,
            name='port1',
            type='200gbase-x-qsfp112'
        )


def reverse_seed_nic_module_types(apps, schema_editor):
    """Remove seeded NIC ModuleTypes."""
    Manufacturer = apps.get_model('dcim', 'Manufacturer')
    ModuleType = apps.get_model('dcim', 'ModuleType')
    ModuleTypeProfile = apps.get_model('dcim', 'ModuleTypeProfile')

    # Get NVIDIA manufacturer
    try:
        nvidia = Manufacturer.objects.get(name='NVIDIA')
    except Manufacturer.DoesNotExist:
        return

    # Delete ModuleTypes (cascades to InterfaceTemplates)
    ModuleType.objects.filter(
        manufacturer=nvidia,
        model__in=[
            'BlueField-3 BF3220',
            'ConnectX-7 (Single-Port)',
            'ConnectX-7 (Dual-Port)',
        ]
    ).delete()

    # Delete ModuleTypeProfile (only if not referenced by other ModuleTypes)
    try:
        profile = ModuleTypeProfile.objects.get(name='Network Transceiver')
        if not ModuleType.objects.filter(profile=profile).exists():
            profile.delete()
    except ModuleTypeProfile.DoesNotExist:
        pass

    # Note: We don't delete NVIDIA manufacturer in case it's used elsewhere


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_hedgehog', '0028_make_switch_group_name_required'),
        ('dcim', '__latest__'),  # Ensure dcim models are available
    ]

    operations = [
        migrations.RunPython(
            seed_nic_module_types,
            reverse_code=reverse_seed_nic_module_types
        ),
    ]
