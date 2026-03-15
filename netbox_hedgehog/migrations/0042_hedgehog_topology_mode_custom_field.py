"""
Migration 0042: provision hedgehog_topology_mode CustomField on dcim.Device.

Follows the same pattern as 0038 (hedgehog_transceiver_spec on dcim.Interface).
Previously this field was created lazily during DeviceGenerator.generate_all(),
which caused shared-schema side-effects and concurrent-generation races.

Per DIET-309 review finding (Dev C): custom fields shared across all plans must
be provisioned through migrations, not at runtime.
"""

from django.db import migrations


def add_topology_mode_custom_field(apps, schema_editor):
    """Add hedgehog_topology_mode custom field on dcim.Device."""
    CustomField = apps.get_model('extras', 'CustomField')
    ContentType = apps.get_model('contenttypes', 'ContentType')
    Device = apps.get_model('dcim', 'Device')

    device_ct = ContentType.objects.get_for_model(Device)

    cf, created = CustomField.objects.get_or_create(
        name='hedgehog_topology_mode',
        defaults={
            'label': 'Hedgehog Topology Mode',
            'type': 'text',
            'description': (
                'Topology mode for this switch device in a DIET-generated fabric. '
                'Set to "prefer-mesh" for switches in a mesh fabric.'
            ),
            'required': False,
            'weight': 120,
        },
    )
    cf.object_types.add(device_ct)


def remove_topology_mode_custom_field(apps, schema_editor):
    CustomField = apps.get_model('extras', 'CustomField')
    CustomField.objects.filter(name='hedgehog_topology_mode').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_hedgehog', '0041_mesh_link_leaf_names_nonnullable_plan'),
    ]

    operations = [
        migrations.RunPython(
            add_topology_mode_custom_field,
            remove_topology_mode_custom_field,
        ),
    ]
