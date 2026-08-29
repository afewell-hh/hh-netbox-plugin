"""
DIET-607: extend the ``hedgehog_plan_id`` custom field to ``dcim.rack`` so
generated racks carry the plan tag/CF and can be cleaned up plan-scoped.

Mirrors the idempotent pattern in 0015_add_custom_fields. Reverse removes only
the rack content type (leaving device/interface/cable intact).
"""

from django.db import migrations


def add_rack_content_type(apps, schema_editor):
    CustomField = apps.get_model('extras', 'CustomField')
    ContentType = apps.get_model('contenttypes', 'ContentType')
    Rack = apps.get_model('dcim', 'Rack')

    cf = CustomField.objects.filter(name='hedgehog_plan_id').first()
    if cf is None:
        return
    rack_ct = ContentType.objects.get_for_model(Rack)
    cf.object_types.add(rack_ct)


def remove_rack_content_type(apps, schema_editor):
    CustomField = apps.get_model('extras', 'CustomField')
    ContentType = apps.get_model('contenttypes', 'ContentType')
    Rack = apps.get_model('dcim', 'Rack')

    cf = CustomField.objects.filter(name='hedgehog_plan_id').first()
    if cf is None:
        return
    rack_ct = ContentType.objects.get_for_model(Rack)
    cf.object_types.remove(rack_ct)


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_hedgehog', '0055_rack_placement'),
    ]

    operations = [
        migrations.RunPython(add_rack_content_type, remove_rack_content_type),
    ]
