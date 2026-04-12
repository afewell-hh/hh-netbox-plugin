"""
Migration 0049: Remove InterfaceTemplates from OSFP transceiver ModuleTypes.

OSFP-400G-DR4 and OSFP-200G-DR4 are pluggable optical transceivers, not NICs.
They do not add logical interfaces to a device — the device's interfaces come
from the NIC module type. The InterfaceTemplates seeded by 0048 caused
duplicate-interface errors during device generation whenever multiple
transceiver modules were installed on the same server (e.g., one OSFP per
scale-out rail in XOC-64 → 8 × "port0" on the same device → UNIQUE violation).

Removing the InterfaceTemplates is correct: a Module record in a cage-N bay
is sufficient to record which transceiver is present; no separate interface
is needed on the parent device.
"""

from django.db import migrations


def remove_osfp_interface_templates(apps, schema_editor):
    """Delete InterfaceTemplates from OSFP-400G-DR4 and OSFP-200G-DR4."""
    Manufacturer = apps.get_model('dcim', 'Manufacturer')
    ModuleType = apps.get_model('dcim', 'ModuleType')
    InterfaceTemplate = apps.get_model('dcim', 'InterfaceTemplate')

    try:
        generic = Manufacturer.objects.get(name='Generic')
    except Manufacturer.DoesNotExist:
        return

    osfp_models = ModuleType.objects.filter(
        manufacturer=generic,
        model__in=['OSFP-400G-DR4', 'OSFP-200G-DR4'],
    )
    InterfaceTemplate.objects.filter(module_type__in=osfp_models).delete()


def restore_osfp_interface_templates(apps, schema_editor):
    """Restore InterfaceTemplates removed by forward migration (for reverse)."""
    Manufacturer = apps.get_model('dcim', 'Manufacturer')
    ModuleType = apps.get_model('dcim', 'ModuleType')
    InterfaceTemplate = apps.get_model('dcim', 'InterfaceTemplate')

    try:
        generic = Manufacturer.objects.get(name='Generic')
    except Manufacturer.DoesNotExist:
        return

    for model_name, iface_type in [
        ('OSFP-400G-DR4', '400gbase-x-osfp'),
        ('OSFP-200G-DR4', 'other'),
    ]:
        mt = ModuleType.objects.filter(manufacturer=generic, model=model_name).first()
        if mt is None:
            continue
        InterfaceTemplate.objects.get_or_create(
            module_type=mt,
            name='port0',
            defaults={'type': iface_type},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_hedgehog', '0048_seed_osfp_transceiver_module_types'),
        ('dcim', '__latest__'),
    ]

    operations = [
        migrations.RunPython(
            remove_osfp_interface_templates,
            reverse_code=restore_osfp_interface_templates,
        ),
    ]
