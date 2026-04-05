"""
Management command: populate_transceiver_bays

Stage 2 (DIET-334): Add ModuleBayTemplate entries to:
  1. HNP switch DeviceTypes — one ModuleBayTemplate per InterfaceTemplate,
     named to match the interface template name.
  2. NIC ModuleTypes used by PlanServerNIC — one nested ModuleBayTemplate
     per InterfaceTemplate (port cage), named 'cage-{index}'.

This command is idempotent; running it multiple times does not create
duplicates (uses get_or_create throughout).

Run this command after applying migration 0045, before running Stage 2
generation for the first time.
"""

from django.core.management.base import BaseCommand

from dcim.models import DeviceType, InterfaceTemplate, ModuleBayTemplate, ModuleType

from netbox_hedgehog.models.topology_planning import DeviceTypeExtension, PlanServerNIC


class Command(BaseCommand):
    help = (
        'Populate ModuleBayTemplate entries on HNP switch DeviceTypes and '
        'NIC ModuleTypes for Stage 2 transceiver module placement.'
    )

    def handle(self, *args, **options):
        switch_bays_added = 0
        nic_bays_added = 0

        # --- 1. Switch DeviceTypes ---
        # All DeviceTypes that have a DeviceTypeExtension (HNP-registered switches).
        switch_dt_ids = DeviceTypeExtension.objects.values_list('device_type_id', flat=True)
        for dt in DeviceType.objects.filter(pk__in=switch_dt_ids):
            for it in InterfaceTemplate.objects.filter(device_type=dt):
                _, created = ModuleBayTemplate.objects.get_or_create(
                    device_type=dt,
                    name=it.name,
                    defaults={'label': f'Transceiver bay for {it.name}'},
                )
                if created:
                    switch_bays_added += 1

        # --- 2. NIC ModuleTypes ---
        # All ModuleTypes referenced by at least one PlanServerNIC.
        nic_mt_ids = PlanServerNIC.objects.values_list('module_type_id', flat=True).distinct()
        for mt in ModuleType.objects.filter(pk__in=nic_mt_ids):
            port_templates = list(
                InterfaceTemplate.objects.filter(module_type=mt).order_by('name')
            )
            for index, _it in enumerate(port_templates):
                _, created = ModuleBayTemplate.objects.get_or_create(
                    module_type=mt,
                    name=f'cage-{index}',
                    defaults={'label': f'Transceiver cage {index}'},
                )
                if created:
                    nic_bays_added += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'populate_transceiver_bays: '
                f'{switch_bays_added} switch bay(s) added, '
                f'{nic_bays_added} NIC cage(s) added.'
            )
        )
