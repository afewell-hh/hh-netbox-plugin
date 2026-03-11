from django.db import migrations, models


def _legacy_fabric_name_to_class(fabric_name):
    if fabric_name in {"frontend", "backend"}:
        return "managed"
    return "unmanaged"


def backfill_fabric_class_and_custom_field(apps, schema_editor):
    PlanSwitchClass = apps.get_model('netbox_hedgehog', 'PlanSwitchClass')
    Device = apps.get_model('dcim', 'Device')
    CustomField = apps.get_model('extras', 'CustomField')
    ContentType = apps.get_model('contenttypes', 'ContentType')

    for switch_class in PlanSwitchClass.objects.all():
        switch_class.fabric_class = _legacy_fabric_name_to_class(switch_class.fabric_name)
        switch_class.save(update_fields=['fabric_class'])

    for device in Device.objects.exclude(custom_field_data=None):
        custom_field_data = dict(device.custom_field_data or {})
        fabric_name = custom_field_data.get('hedgehog_fabric')
        if fabric_name and not custom_field_data.get('hedgehog_fabric_class'):
            custom_field_data['hedgehog_fabric_class'] = _legacy_fabric_name_to_class(fabric_name)
            device.custom_field_data = custom_field_data
            device.save(update_fields=['custom_field_data'])

    device_ct = ContentType.objects.get(app_label='dcim', model='device')
    custom_field, _ = CustomField.objects.get_or_create(
        name='hedgehog_fabric_class',
        defaults={
            'label': 'Hedgehog Fabric Class',
            'type': 'text',
            'description': 'Behavioral fabric class for generated devices',
            'required': False,
            'weight': 102,
        },
    )
    custom_field.object_types.add(device_ct)


def remove_fabric_class_custom_field(apps, schema_editor):
    CustomField = apps.get_model('extras', 'CustomField')
    CustomField.objects.filter(name='hedgehog_fabric_class').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_hedgehog', '0035_switchportzone_peer_zone'),
        ('extras', '0133_make_cf_minmax_decimal'),
    ]

    operations = [
        migrations.RenameField(
            model_name='planswitchclass',
            old_name='fabric',
            new_name='fabric_name',
        ),
        migrations.AddField(
            model_name='planswitchclass',
            name='fabric_class',
            field=models.CharField(
                choices=[('managed', 'Managed'), ('unmanaged', 'Unmanaged')],
                default='managed',
                help_text='Behavioral class for this fabric. Managed fabrics export as Switch CRDs; unmanaged fabrics export as Server surrogates.',
                max_length=16,
            ),
        ),
        migrations.AlterModelOptions(
            name='planswitchclass',
            options={
                'ordering': ['plan', 'fabric_name', 'switch_class_id'],
                'verbose_name': 'Switch Class',
                'verbose_name_plural': 'Switch Classes',
            },
        ),
        migrations.RunPython(
            backfill_fabric_class_and_custom_field,
            remove_fabric_class_custom_field,
        ),
    ]
