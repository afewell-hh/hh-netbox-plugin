"""
Migration 0043: Explicit manual mesh topology mode (DIET-317).

Changes:
1. Remove TopologyPlan.mesh_ip_pool field (no longer needed).
2. Data-migrate PlanSwitchClass.topology_mode: 'prefer-mesh' → 'mesh'.
3. Delete the hedgehog_topology_mode CustomField on dcim.Device
   (classification now derives from plan state, not device custom fields).
"""

from django.db import migrations, models


def seed_missing_breakout_options(apps, schema_editor):
    """Seed the 1x400g BreakoutOption that was missing from initial seeding."""
    BreakoutOption = apps.get_model('netbox_hedgehog', 'BreakoutOption')
    BreakoutOption.objects.get_or_create(
        breakout_id='1x400g',
        defaults={'from_speed': 400, 'logical_ports': 1, 'logical_speed': 400},
    )


def rename_prefer_mesh(apps, schema_editor):
    """Rename prefer-mesh → mesh for all existing PlanSwitchClass rows."""
    PlanSwitchClass = apps.get_model('netbox_hedgehog', 'PlanSwitchClass')
    PlanSwitchClass.objects.filter(topology_mode='prefer-mesh').update(topology_mode='mesh')


def remove_topology_mode_custom_field(apps, schema_editor):
    """Delete the hedgehog_topology_mode CustomField (replaced by plan-state lookup)."""
    CustomField = apps.get_model('extras', 'CustomField')
    CustomField.objects.filter(name='hedgehog_topology_mode').delete()


def restore_topology_mode_custom_field(apps, schema_editor):
    """Reverse: re-create hedgehog_topology_mode CustomField for rollback."""
    CustomField = apps.get_model('extras', 'CustomField')
    ContentType = apps.get_model('contenttypes', 'ContentType')
    Device = apps.get_model('dcim', 'Device')

    device_ct = ContentType.objects.get_for_model(Device)
    cf, _ = CustomField.objects.get_or_create(
        name='hedgehog_topology_mode',
        defaults={
            'label': 'Hedgehog Topology Mode',
            'type': 'text',
            'description': 'Restored by migration rollback.',
            'required': False,
            'weight': 120,
        },
    )
    cf.object_types.add(device_ct)


def restore_prefer_mesh(apps, schema_editor):
    """Reverse: rename mesh → prefer-mesh (rollback only)."""
    PlanSwitchClass = apps.get_model('netbox_hedgehog', 'PlanSwitchClass')
    PlanSwitchClass.objects.filter(topology_mode='mesh').update(topology_mode='prefer-mesh')


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_hedgehog', '0042_hedgehog_topology_mode_custom_field'),
    ]

    operations = [
        # 1. Remove mesh_ip_pool from TopologyPlan
        migrations.RemoveField(
            model_name='topologyplan',
            name='mesh_ip_pool',
        ),
        # 2. Data migration: prefer-mesh → mesh
        migrations.RunPython(rename_prefer_mesh, restore_prefer_mesh),
        # 3. Delete hedgehog_topology_mode CustomField
        migrations.RunPython(
            remove_topology_mode_custom_field,
            restore_topology_mode_custom_field,
        ),
        # 4. Seed missing BreakoutOption (1x400g was absent from initial seeding)
        migrations.RunPython(
            seed_missing_breakout_options,
            migrations.RunPython.noop,
        ),
    ]
