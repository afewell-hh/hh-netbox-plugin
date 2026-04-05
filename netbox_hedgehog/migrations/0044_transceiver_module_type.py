"""
Migration 0044: Add transceiver_module_type FK to PlanServerConnection and
SwitchPortZone, and extend the Network Transceiver ModuleTypeProfile schema
with missing enum values (DIET-334 Stage 1).
"""

import django.db.models.deletion
from django.db import migrations, models


def update_network_transceiver_profile(apps, schema_editor):
    """
    Add missing enum values and lane_count to the Network Transceiver profile schema.

    Idempotent: only adds values that are not already present.
    Skips gracefully if the profile does not exist in this environment.
    """
    from dcim.models import ModuleTypeProfile
    profile = ModuleTypeProfile.objects.filter(name='Network Transceiver').first()
    if profile is None:
        return

    schema = profile.schema or {}
    props = schema.setdefault('properties', {})
    changed = False

    # cage_type: add OSFP, SFP+, RJ45
    cage = props.setdefault('cage_type', {'type': 'string', 'enum': []})
    for val in ('OSFP', 'SFP+', 'RJ45'):
        if val not in cage.get('enum', []):
            cage.setdefault('enum', []).append(val)
            changed = True

    # medium: add ACC
    medium = props.setdefault('medium', {'type': 'string', 'enum': []})
    if 'ACC' not in medium.get('enum', []):
        medium.setdefault('enum', []).append('ACC')
        changed = True

    # connector: add MPO-16
    connector = props.setdefault('connector', {'type': 'string', 'enum': []})
    if 'MPO-16' not in connector.get('enum', []):
        connector.setdefault('enum', []).append('MPO-16')
        changed = True

    # lane_count: new integer attribute
    if 'lane_count' not in props:
        props['lane_count'] = {
            'type': 'integer',
            'minimum': 1,
        }
        changed = True

    if changed:
        profile.schema = schema
        profile.save(update_fields=['schema'])


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_hedgehog', '0043_explicit_mesh_mode'),
        ('netbox_hedgehog', 'mesh_migration_helpers'),
        ('dcim', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='planserverconnection',
            name='transceiver_module_type',
            field=models.ForeignKey(
                'dcim.ModuleType',
                on_delete=django.db.models.deletion.SET_NULL,
                null=True,
                blank=True,
                related_name='plan_server_connections',
                help_text=(
                    "Transceiver or DAC/AOC ModuleType to install in this port cage. "
                    "Must have the 'Network Transceiver' ModuleTypeProfile. "
                    "If null, no transceiver Module is generated (Stage 1 backward compat)."
                ),
            ),
        ),
        migrations.AddField(
            model_name='switchportzone',
            name='transceiver_module_type',
            field=models.ForeignKey(
                'dcim.ModuleType',
                on_delete=django.db.models.deletion.SET_NULL,
                null=True,
                blank=True,
                related_name='switch_port_zones',
                help_text=(
                    "Intended transceiver/DAC ModuleType for all ports in this zone (Stage 2). "
                    "Must have the 'Network Transceiver' ModuleTypeProfile. "
                    "Used for plan-save compatibility validation and future switch-side Module generation."
                ),
            ),
        ),
        migrations.RunPython(
            update_network_transceiver_profile,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
