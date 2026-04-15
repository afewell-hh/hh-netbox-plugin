"""
Migration 0050: Seed QSFP112-200GBASE-SR2 generic placeholder ModuleType (#443).

Seeds the server-side placeholder optic for the XOC-64 soc_storage_server_4x200
zone. This optic is used on the server side of the approved asymmetric pair:

  Switch side: Celestica R4113-A9220-VR (800G OSFP112 2xVR4, Dual MPO-12, MMF)
  Server side: Generic QSFP112-200GBASE-SR2 (200G QSFP112 SR2, MPO-12, MMF)

The Y-splitter splitting the 800G OSFP link into two 400G QSFP112 sub-links is
external to NetBox and is not modeled here. Each server port connects to one of
the two sub-links at 200G (using 2 of the 4 100G PAM4 lanes per sub-link).

Manufacturer is 'Generic' and description explicitly says "placeholder" to signal
that this must be replaced with a vendor-qualified SKU before production use.

No InterfaceTemplates are added: transceiver ModuleTypes are optics, not NICs.
The logical interface comes from the NIC module type (e.g., QSFP112 SoC NIC).

Seed path: this ModuleType is also in seed_catalog.py:STATIC_TRANSCEIVER_MODULE_TYPES
so that load_diet_reference_data can recreate it after a purge/reset without
requiring migrations to be re-run.

## Standards basis
200GBASE-SR2: 2 × 100G PAM4 lanes over parallel MMF, 850 nm, 70 m reach,
MPO-12 connector. IEEE 802.3cd compliant.
"""

from django.db import migrations


def seed_qsfp112_200gbase_sr2(apps, schema_editor):
    """Seed Generic/QSFP112-200GBASE-SR2 Network Transceiver ModuleType."""
    Manufacturer = apps.get_model('dcim', 'Manufacturer')
    ModuleType = apps.get_model('dcim', 'ModuleType')
    ModuleTypeProfile = apps.get_model('dcim', 'ModuleTypeProfile')

    generic, _ = Manufacturer.objects.get_or_create(
        name='Generic',
        defaults={'slug': 'generic'},
    )

    transceiver_profile = ModuleTypeProfile.objects.filter(
        name='Network Transceiver'
    ).first()
    if transceiver_profile is None:
        # Should never happen after 0029 runs; guard gracefully
        return

    ModuleType.objects.get_or_create(
        manufacturer=generic,
        model='QSFP112-200GBASE-SR2',
        defaults={
            'profile': transceiver_profile,
            'part_number': 'QSFP112-200GBASE-SR2',
            'description': (
                '200G QSFP112 SR2 (MPO-12) — generic placeholder; '
                'replace with vendor SKU when qualified'
            ),
            'comments': (
                'Generic placeholder for the server-side QSFP112 host optic used in XOC-64 '
                'soc_storage_server_4x200 connections. The switch side uses Celestica R4113-A9220-VR '
                '(800G OSFP112 2xVR4) with an external Y-splitter. Replace this entry with a '
                'vendor-qualified SKU when the deployment optic is selected.'
            ),
            'attribute_data': {
                'cage_type': 'QSFP112',
                'medium': 'MMF',
                'connector': 'MPO-12',
                'wavelength_nm': 850,
                'standard': '200GBASE-SR2',
                'reach_class': 'SR',
                'lane_count': 2,
                'host_serdes_gbps_per_lane': 100,
                'optical_lane_pattern': 'SR2',
                'gearbox_present': False,
                'cable_assembly_type': 'none',
                'breakout_topology': '1x',
            },
        },
    )
    # No InterfaceTemplates: transceivers are optics, not NICs.


def reverse_seed_qsfp112_200gbase_sr2(apps, schema_editor):
    """Remove QSFP112-200GBASE-SR2 ModuleType."""
    Manufacturer = apps.get_model('dcim', 'Manufacturer')
    ModuleType = apps.get_model('dcim', 'ModuleType')

    try:
        generic = Manufacturer.objects.get(name='Generic')
    except Manufacturer.DoesNotExist:
        return

    ModuleType.objects.filter(
        manufacturer=generic,
        model='QSFP112-200GBASE-SR2',
    ).delete()
    # Do not delete Generic manufacturer — shared with other records


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_hedgehog', '0049_remove_osfp_interface_templates'),
        ('dcim', '__latest__'),
    ]

    operations = [
        migrations.RunPython(
            seed_qsfp112_200gbase_sr2,
            reverse_code=reverse_seed_qsfp112_200gbase_sr2,
        ),
    ]
