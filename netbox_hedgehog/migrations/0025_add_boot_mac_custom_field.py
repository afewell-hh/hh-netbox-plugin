# Generated manually for issue #143
from django.db import migrations


CUSTOM_FIELD_DEFINITIONS = [
    {
        'name': 'boot_mac',
        'label': 'Boot MAC Address',
        'type': 'text',
        'description': 'Switch boot MAC address for Hedgehog fabric identification (spec.boot.mac)',
        'weight': 107,
        'content_types': [('dcim', 'device')],
    }
]


def create_custom_fields(apps, schema_editor):
    ContentType = apps.get_model('contenttypes', 'ContentType')
    CustomField = apps.get_model('extras', 'CustomField')

    for field_def in CUSTOM_FIELD_DEFINITIONS:
        content_types = [
            ContentType.objects.get(app_label=app, model=model)
            for app, model in field_def.pop('content_types')
        ]

        custom_field, created = CustomField.objects.get_or_create(
            name=field_def['name'],
            defaults=field_def
        )

        if created:
            custom_field.object_types.set(content_types)


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_hedgehog', '0024_add_hedgehog_profile_name'),
    ]

    operations = [
        migrations.RunPython(create_custom_fields, migrations.RunPython.noop),
    ]
