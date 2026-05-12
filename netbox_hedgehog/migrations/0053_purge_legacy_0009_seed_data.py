# Purge the 3 invalid DeviceTypes created by migration 0009 that must not
# exist in a correct bootstrap. Each slug uses try/except DoesNotExist so
# the migration is idempotent (no-op when rows are already absent).
# Reverse migration is a no-op: rows must not be recreated.
#
# sn5600 is intentionally excluded: it is not required but must not be
# actively purged — it is a neutral slug that may be added later.

from django.db import migrations


def purge_legacy_seed_rows(apps, schema_editor):
    DeviceType = apps.get_model('dcim', 'DeviceType')
    DeviceTypeExtension = apps.get_model('netbox_hedgehog', 'DeviceTypeExtension')
    PlanSwitchClass = apps.get_model('netbox_hedgehog', 'PlanSwitchClass')
    SwitchPortZone = apps.get_model('netbox_hedgehog', 'SwitchPortZone')
    PlanServerConnection = apps.get_model('netbox_hedgehog', 'PlanServerConnection')

    FORBIDDEN_SLUGS = ['ds5000', 'ds3000', 'es1000-48']

    for slug in FORBIDDEN_SLUGS:
        try:
            dt = DeviceType.objects.get(slug=slug)
        except DeviceType.DoesNotExist:
            continue

        # Cascade-aware cleanup: plan data → extension → device type
        ext_qs = DeviceTypeExtension.objects.filter(device_type=dt)
        sc_qs = PlanSwitchClass.objects.filter(device_type_extension__in=ext_qs)
        zone_qs = SwitchPortZone.objects.filter(switch_class__in=sc_qs)
        PlanServerConnection.objects.filter(target_zone__in=zone_qs).delete()
        zone_qs.delete()
        sc_qs.delete()
        ext_qs.delete()
        dt.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_hedgehog', '0052_remove_breakoutoption_optic_type'),
    ]

    operations = [
        migrations.RunPython(
            purge_legacy_seed_rows,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
