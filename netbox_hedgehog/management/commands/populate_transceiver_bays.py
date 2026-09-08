"""
Management command: populate_transceiver_bays

Stage 2 (DIET-334): Add ModuleBayTemplate entries to:
  1. HNP switch DeviceTypes — one ModuleBayTemplate per InterfaceTemplate,
     named to match the interface template name.
  2. NIC ModuleTypes used by PlanServerNIC — one nested ModuleBayTemplate
     per InterfaceTemplate (port cage), named 'cage-{index}'.

This command is idempotent; running it multiple times does not create
duplicates (uses get_or_create throughout).

load_diet_reference_data invokes this command, so a bootstrapped
environment is already generation-ready (#626).  Run it directly only to
cover inventory introduced after bootstrap -- for example NIC ModuleTypes
created by a YAML case file.
"""

import re

from django.core.management.base import BaseCommand
from django.db.models import Q

from dcim.models import DeviceType, InterfaceTemplate, ModuleBayTemplate, ModuleType

from netbox_hedgehog.models.topology_planning import DeviceTypeExtension, PlanServerNIC
from netbox_hedgehog.seed_catalog import STATIC_NIC_MODULE_TYPES
from netbox_hedgehog.services.transceiver_bay_policy import (
    is_virtual_placeholder_module_type,
    is_virtual_placeholder_switch_device_type,
)


class Command(BaseCommand):
    help = (
        'Populate ModuleBayTemplate entries on HNP switch DeviceTypes and '
        'NIC ModuleTypes for Stage 2 transceiver module placement.'
    )

    def handle(self, *args, **options):
        switch_bays_added = 0
        nic_bays_added = 0
        switch_bays_removed = 0
        nic_bays_removed = 0

        # --- 1. Switch DeviceTypes ---
        # All DeviceTypes that have a DeviceTypeExtension (HNP-registered switches).
        switch_dt_ids = DeviceTypeExtension.objects.values_list('device_type_id', flat=True)
        for dt in DeviceType.objects.filter(pk__in=switch_dt_ids):
            if is_virtual_placeholder_switch_device_type(dt):
                # Virtual placeholder switch types intentionally do not get
                # switch-side ModuleBayTemplates. Remove any stale bays that
                # may have been created before this policy existed so future
                # Device.save() calls avoid the per-port module-bay cost.
                switch_bays_removed += ModuleBayTemplate.objects.filter(device_type=dt).count()
                ModuleBayTemplate.objects.filter(device_type=dt).delete()
                continue
            for it in InterfaceTemplate.objects.filter(device_type=dt):
                _, created = ModuleBayTemplate.objects.get_or_create(
                    device_type=dt,
                    name=it.name,
                    defaults={'label': f'Transceiver bay for {it.name}'},
                )
                if created:
                    switch_bays_added += 1

        # --- 2. NIC ModuleTypes ---
        # ModuleTypes referenced by at least one PlanServerNIC, plus the NIC
        # ModuleTypes the bundled catalog seeds.  The second set matters at
        # bootstrap time: a fresh environment has no plans yet, so a
        # PlanServerNIC-only scope would leave the seeded catalog without cages
        # and every first generation would fail preflight (#626).
        # Seeded types are matched on (manufacturer slug, model) so ModuleTypes
        # this plugin did not create are never touched.
        nic_mt_ids = set(
            PlanServerNIC.objects.values_list('module_type_id', flat=True).distinct()
        )
        if STATIC_NIC_MODULE_TYPES:
            seeded_q = Q()
            for spec in STATIC_NIC_MODULE_TYPES:
                seeded_q |= Q(
                    manufacturer__slug=spec['manufacturer_slug'],
                    model=spec['model'],
                )
            nic_mt_ids |= set(
                ModuleType.objects.filter(seeded_q).values_list('pk', flat=True)
            )

        for mt in ModuleType.objects.filter(pk__in=nic_mt_ids):
            if is_virtual_placeholder_module_type(mt):
                nic_bays_removed += ModuleBayTemplate.objects.filter(module_type=mt).count()
                ModuleBayTemplate.objects.filter(module_type=mt).delete()
                continue
            # Use natural sort (matching _get_module_interface_by_port_index) so that
            # cage-N indices align correctly for multi-digit port names (p0…p10, etc.).
            def _natural_key(it):
                parts = re.split(r'(\d+)', it.name)
                return [int(p) if p.isdigit() else p.lower() for p in parts]

            port_templates = sorted(
                InterfaceTemplate.objects.filter(module_type=mt),
                key=_natural_key,
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
                f'{switch_bays_removed} switch bay(s) removed, '
                f'{nic_bays_added} NIC cage(s) added, '
                f'{nic_bays_removed} NIC cage(s) removed.'
            )
        )
