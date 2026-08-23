"""Seed the Generic SFP+ 10GBASE-T copper adapter used by DIET #599."""

from django.db import migrations


def seed_sfp_plus_10gbase_t(apps, schema_editor):
    Manufacturer = apps.get_model('dcim', 'Manufacturer')
    ModuleType = apps.get_model('dcim', 'ModuleType')
    ModuleTypeProfile = apps.get_model('dcim', 'ModuleTypeProfile')
    generic, _ = Manufacturer.objects.get_or_create(name='Generic', defaults={'slug': 'generic'})
    profile = ModuleTypeProfile.objects.filter(name='Network Transceiver').first()
    if profile is None:
        return
    ModuleType.objects.get_or_create(
        manufacturer=generic, model='SFP+-10GBASE-T',
        defaults={
            'profile': profile, 'part_number': 'SFP+-10GBASE-T',
            'description': '10GBASE-T RJ45 copper SFP+ adapter',
            'comments': 'Generic active copper SFP+ adapter for 10GBASE-T endpoints.',
            'attribute_data': {
                'cage_type': 'SFP+', 'medium': 'Copper', 'connector': 'Direct',
                'standard': '10GBASE-T', 'reach_class': 'DAC', 'lane_count': 1,
                'host_serdes_gbps_per_lane': 10, 'gearbox_present': True,
                'cable_assembly_type': 'ACC', 'far_end_medium': 'Copper',
                'far_end_cage_type': 'RJ45', 'breakout_topology': '1x',
            },
        },
    )


def unseed_sfp_plus_10gbase_t(apps, schema_editor):
    ModuleType = apps.get_model('dcim', 'ModuleType')
    ModuleType.objects.filter(manufacturer__name='Generic', model='SFP+-10GBASE-T').delete()


class Migration(migrations.Migration):
    dependencies = [('netbox_hedgehog', '0053_purge_legacy_0009_seed_data'), ('dcim', '__latest__')]
    operations = [migrations.RunPython(seed_sfp_plus_10gbase_t, unseed_sfp_plus_10gbase_t)]
