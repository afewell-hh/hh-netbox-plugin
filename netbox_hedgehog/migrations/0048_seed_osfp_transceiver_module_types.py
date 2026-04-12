"""
Migration 0048: Seed OSFP transceiver ModuleTypes for XOC-64 (DIET-434).

Seeds two Network Transceiver ModuleType records required before training-ra#20
can express truthful transceiver intent for the XOC-64 topology:

- OSFP-400G-DR4  — CX-7 scale-out NIC ports (server-side, 400G SMF DR4)
- OSFP-200G-DR4  — BF3 soc-storage NIC ports (server-side, 200G SMF DR4)

Both use the Generic manufacturer; both carry the Network Transceiver profile.
All lane_count / host_serdes values are based on IEEE 802.3bs (400GBASE-DR4)
and 802.3bs annex (200GBASE-DR4) conventions. Verify against vendor datasheets
before promoting to production if exact values matter for your catalog.
"""

from django.db import migrations


def seed_osfp_transceiver_module_types(apps, schema_editor):
    """Seed OSFP-400G-DR4 and OSFP-200G-DR4 Network Transceiver ModuleTypes."""
    Manufacturer = apps.get_model('dcim', 'Manufacturer')
    ModuleType = apps.get_model('dcim', 'ModuleType')
    InterfaceTemplate = apps.get_model('dcim', 'InterfaceTemplate')
    ModuleTypeProfile = apps.get_model('dcim', 'ModuleTypeProfile')

    # 1. Get or create Generic manufacturer
    generic, _ = Manufacturer.objects.get_or_create(
        name='Generic',
        defaults={'slug': 'generic'}
    )

    # 2. Get the Network Transceiver profile (created by 0029; extended by 0044/0047)
    transceiver_profile = ModuleTypeProfile.objects.filter(
        name='Network Transceiver'
    ).first()
    if transceiver_profile is None:
        # Should never happen after 0029 runs, but guard gracefully
        return

    # 3. Seed OSFP-400G-DR4
    #    IEEE 400GBASE-DR4: 4 × 100G PAM4 lanes over parallel SMF, 1310 nm,
    #    500 m reach, MPO-12 connector.
    osfp_400g, osfp_400g_created = ModuleType.objects.get_or_create(
        manufacturer=generic,
        model='OSFP-400G-DR4',
        defaults={
            'profile': transceiver_profile,
            'attribute_data': {
                'cage_type': 'OSFP',
                'medium': 'SMF',
                'connector': 'MPO-12',
                'wavelength_nm': 1310,
                'standard': '400GBASE-DR4',
                'reach_class': 'DR',
                'lane_count': 4,
                'host_serdes_gbps_per_lane': 100,
                'optical_lane_pattern': 'DR4',
                'gearbox_present': False,
                'cable_assembly_type': 'none',
                'breakout_topology': '1x',
            }
        }
    )

    if osfp_400g_created:
        InterfaceTemplate.objects.create(
            module_type=osfp_400g,
            name='port0',
            type='400gbase-x-osfp',
        )

    # 4. Seed OSFP-200G-DR4
    #    IEEE 200GBASE-DR4: 4 × 50G PAM4 lanes over parallel SMF, 1310 nm,
    #    500 m reach, MPO-12 connector. This is the per-lane profile for a
    #    server-side BF3 OSFP port on a 4x200G breakout from an 800G switch OSFP.
    osfp_200g, osfp_200g_created = ModuleType.objects.get_or_create(
        manufacturer=generic,
        model='OSFP-200G-DR4',
        defaults={
            'profile': transceiver_profile,
            'attribute_data': {
                'cage_type': 'OSFP',
                'medium': 'SMF',
                'connector': 'MPO-12',
                'wavelength_nm': 1310,
                'standard': '200GBASE-DR4',
                'reach_class': 'DR',
                'lane_count': 4,
                'host_serdes_gbps_per_lane': 50,
                'optical_lane_pattern': 'DR4',
                'gearbox_present': False,
                'cable_assembly_type': 'none',
                'breakout_topology': '1x',
            }
        }
    )

    if osfp_200g_created:
        InterfaceTemplate.objects.create(
            module_type=osfp_200g,
            name='port0',
            type='other',
        )


def reverse_seed_osfp_transceiver_module_types(apps, schema_editor):
    """Remove the two OSFP transceiver ModuleType records."""
    Manufacturer = apps.get_model('dcim', 'Manufacturer')
    ModuleType = apps.get_model('dcim', 'ModuleType')

    try:
        generic = Manufacturer.objects.get(name='Generic')
    except Manufacturer.DoesNotExist:
        return

    # Delete both ModuleTypes (cascades to InterfaceTemplates)
    ModuleType.objects.filter(
        manufacturer=generic,
        model__in=['OSFP-400G-DR4', 'OSFP-200G-DR4'],
    ).delete()

    # Do not delete Generic manufacturer — it is shared with other records


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_hedgehog', '0047_transceiver_metadata_fields'),
        ('dcim', '__latest__'),
    ]

    operations = [
        migrations.RunPython(
            seed_osfp_transceiver_module_types,
            reverse_code=reverse_seed_osfp_transceiver_module_types,
        ),
    ]
