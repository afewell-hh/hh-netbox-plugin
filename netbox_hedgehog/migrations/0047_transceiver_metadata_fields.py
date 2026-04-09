"""
Migration 0047: Transceiver metadata schema completeness (#415 Phase 4).

Part A: Add 5 new fields to the 'Network Transceiver' ModuleTypeProfile schema.
Part B: Seed new field values on the 3 existing NVIDIA module types.

lane_count and host_serdes_gbps_per_lane candidate values for BF3220/CX-7 are
based on IEEE 802.3cd and QSFP112 conventions. Verify against NVIDIA datasheets
before promoting to production if exact values matter for your catalog.
"""
from django.db import migrations


def _update_profile_schema(apps, schema_editor):
    """Add 5 new optional fields to Network Transceiver profile schema (idempotent)."""
    from dcim.models import ModuleTypeProfile
    profile = ModuleTypeProfile.objects.filter(name='Network Transceiver').first()
    if profile is None:
        return
    schema = profile.schema or {}
    props = schema.setdefault('properties', {})
    changed = False

    new_props = {
        'host_serdes_gbps_per_lane': {'type': 'integer', 'minimum': 1},
        'optical_lane_pattern': {
            'type': 'string',
            'enum': ['SR', 'SR2', 'SR4', 'SR8', 'DR4', 'VR4', 'PSM4'],
        },
        'gearbox_present': {'type': 'boolean'},
        'cable_assembly_type': {
            'type': 'string',
            'enum': ['none', 'DAC', 'ACC', 'AOC'],
        },
        'breakout_topology': {'type': 'string'},
    }
    for key, defn in new_props.items():
        if key not in props:
            props[key] = defn
            changed = True

    if changed:
        profile.schema = schema
        profile.save(update_fields=['schema'])


def _revert_profile_schema(apps, schema_editor):
    """Remove the 5 new fields from profile schema (reverse)."""
    from dcim.models import ModuleTypeProfile
    profile = ModuleTypeProfile.objects.filter(name='Network Transceiver').first()
    if profile is None:
        return
    props = (profile.schema or {}).get('properties', {})
    changed = False
    for key in ('host_serdes_gbps_per_lane', 'optical_lane_pattern',
                'gearbox_present', 'cable_assembly_type', 'breakout_topology'):
        if key in props:
            del props[key]
            changed = True
    if changed:
        profile.save(update_fields=['schema'])


def _seed_module_types(apps, schema_editor):
    """
    Seed new attribute_data fields on the 3 existing NVIDIA module types.

    Uses dict.update() so existing keys are preserved.
    gearbox_present=None is stored as JSON null — valid sentinel for "unknown".
    """
    from dcim.models import Manufacturer, ModuleType
    nvidia = Manufacturer.objects.filter(slug='nvidia').first()
    if nvidia is None:
        return

    seeds = [
        (
            'BlueField-3 BF3220',
            {
                # lane_count / host_serdes_gbps_per_lane: candidates based on QSFP112
                # 200G PAM4 convention (2×100G host-side). Verify vs NVIDIA BF3220 datasheet.
                'lane_count': 2,
                'host_serdes_gbps_per_lane': 100,
                'optical_lane_pattern': 'SR4',   # 200GBASE-SR4 = 4 optical lanes
                'gearbox_present': None,          # unknown — verify datasheet
                'cable_assembly_type': 'none',    # standalone pluggable
                'breakout_topology': '1x',
            },
        ),
        (
            'ConnectX-7 (Single-Port)',
            {
                # 200GBASE-CR4: 4 copper lanes × 53.125 Gbaud NRZ ≈ 50G/lane
                # Verify vs NVIDIA CX-7 datasheet.
                'lane_count': 4,
                'host_serdes_gbps_per_lane': 50,
                'optical_lane_pattern': None,    # copper medium — no optical lane pattern
                'gearbox_present': None,          # not applicable: NIC card, not a cable assembly
                'cable_assembly_type': 'none',    # NIC card; link medium=DAC but card itself is not an integrated assembly
                'breakout_topology': '1x',
            },
        ),
        (
            'ConnectX-7 (Dual-Port)',
            {
                'lane_count': 4,
                'host_serdes_gbps_per_lane': 50,
                'optical_lane_pattern': None,
                'gearbox_present': None,          # not applicable: NIC card, not a cable assembly
                'cable_assembly_type': 'none',    # NIC card; link medium=DAC but card itself is not an integrated assembly
                'breakout_topology': '1x',
            },
        ),
    ]

    for model_name, seed_data in seeds:
        mt = ModuleType.objects.filter(manufacturer=nvidia, model=model_name).first()
        if mt is None:
            continue
        data = mt.attribute_data or {}
        data.update(seed_data)
        mt.attribute_data = data
        mt.save(update_fields=['attribute_data'])


def _unseed_module_types(apps, schema_editor):
    """Remove seeded new fields from NVIDIA module types (reverse)."""
    from dcim.models import Manufacturer, ModuleType
    nvidia = Manufacturer.objects.filter(slug='nvidia').first()
    if nvidia is None:
        return
    fields = ('lane_count', 'host_serdes_gbps_per_lane', 'optical_lane_pattern',
              'gearbox_present', 'cable_assembly_type', 'breakout_topology')
    for model_name in ('BlueField-3 BF3220', 'ConnectX-7 (Single-Port)', 'ConnectX-7 (Dual-Port)'):
        mt = ModuleType.objects.filter(manufacturer=nvidia, model=model_name).first()
        if mt is None:
            continue
        data = mt.attribute_data or {}
        for f in fields:
            data.pop(f, None)
        mt.attribute_data = data
        mt.save(update_fields=['attribute_data'])


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_hedgehog', '0046_remove_transceiver_spec_custom_field'),
    ]

    operations = [
        migrations.RunPython(_update_profile_schema, _revert_profile_schema),
        migrations.RunPython(_seed_module_types, _unseed_module_types),
    ]
