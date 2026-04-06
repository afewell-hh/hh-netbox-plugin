"""
Migration 0046: Remove hedgehog_transceiver_spec CustomField from dcim.Interface (DIET-347 Stage 3).

Step 1: Wipe the 'hedgehog_transceiver_spec' key from Interface.custom_field_data
        for all rows where the key is present. NetBox CustomField.delete() does not
        clean up custom_field_data JSON blobs on existing rows.
Step 2: Delete the CustomField object itself.

Django-reversible (reverse recreates the field). Data-lossy in practice (wipe cannot
be undone). This is explicitly accepted per #347.
"""

from django.db import migrations


def wipe_transceiver_spec_from_interface_data(apps, schema_editor):
    """Remove hedgehog_transceiver_spec key from Interface.custom_field_data where present."""
    Interface = apps.get_model('dcim', 'Interface')
    for iface in Interface.objects.filter(
        custom_field_data__has_key='hedgehog_transceiver_spec'
    ).iterator():
        iface.custom_field_data.pop('hedgehog_transceiver_spec', None)
        iface.save(update_fields=['custom_field_data'])


def _noop(apps, schema_editor):
    pass


def remove_transceiver_spec_custom_field(apps, schema_editor):
    CustomField = apps.get_model('extras', 'CustomField')
    CustomField.objects.filter(name='hedgehog_transceiver_spec').delete()


def add_transceiver_spec_custom_field(apps, schema_editor):
    """Reverse: recreate hedgehog_transceiver_spec CustomField on dcim.Interface."""
    CustomField = apps.get_model('extras', 'CustomField')
    ContentType = apps.get_model('contenttypes', 'ContentType')
    Interface = apps.get_model('dcim', 'Interface')

    interface_ct = ContentType.objects.get_for_model(Interface)
    cf, _ = CustomField.objects.get_or_create(
        name='hedgehog_transceiver_spec',
        defaults={
            'label': 'Hedgehog Transceiver Spec',
            'type': 'text',
            'description': 'Transceiver review spec (CAGE|MEDIUM|CONNECTOR|STD) on server interfaces.',
            'required': False,
            'weight': 110,
        },
    )
    cf.object_types.add(interface_ct)


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_hedgehog', '0045_generationstate_mismatch_report'),
    ]

    operations = [
        # Step 1: Wipe orphaned key from existing Interface rows.
        migrations.RunPython(
            wipe_transceiver_spec_from_interface_data,
            _noop,
        ),
        # Step 2: Delete the CustomField object.
        migrations.RunPython(
            remove_transceiver_spec_custom_field,
            add_transceiver_spec_custom_field,
        ),
    ]
