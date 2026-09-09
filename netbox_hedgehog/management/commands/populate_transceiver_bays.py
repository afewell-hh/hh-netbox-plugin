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


def populate_bays(*, device_types, module_types):
    """Create transceiver ModuleBayTemplates for an **explicit** scope.

    Callers pass exactly the DeviceTypes and NIC ModuleTypes they own, so the
    operation can never reach inventory belonging to someone else.  That matters
    for the ingest path: a case file owns the inventory it declares, and must not
    ready a NIC that belongs to an unrelated plan (#626 review).

    Idempotent throughout (``get_or_create``).  Returns a counts dict.
    """
    counts = {'switch_added': 0, 'switch_removed': 0, 'nic_added': 0, 'nic_removed': 0}

    for dt in device_types:
        if is_virtual_placeholder_switch_device_type(dt):
            # Virtual placeholder switch types intentionally do not get
            # switch-side ModuleBayTemplates. Remove any stale bays that
            # may have been created before this policy existed so future
            # Device.save() calls avoid the per-port module-bay cost.
            counts['switch_removed'] += ModuleBayTemplate.objects.filter(device_type=dt).count()
            ModuleBayTemplate.objects.filter(device_type=dt).delete()
            continue
        for it in InterfaceTemplate.objects.filter(device_type=dt):
            _, created = ModuleBayTemplate.objects.get_or_create(
                device_type=dt,
                name=it.name,
                defaults={'label': f'Transceiver bay for {it.name}'},
            )
            if created:
                counts['switch_added'] += 1

    for mt in module_types:
        if is_virtual_placeholder_module_type(mt):
            counts['nic_removed'] += ModuleBayTemplate.objects.filter(module_type=mt).count()
            ModuleBayTemplate.objects.filter(module_type=mt).delete()
            continue
        # Natural sort (matching _get_module_interface_by_port_index) so cage-N
        # indices align for multi-digit port names (p0…p10, etc.).
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
                counts['nic_added'] += 1

    return counts


def catalog_scope():
    """The global scope used by bootstrap and by manual command runs.

    Switch DeviceTypes are those registered with HNP via DeviceTypeExtension.
    NIC ModuleTypes are those referenced by any PlanServerNIC, plus the NIC
    ModuleTypes the bundled catalog seeds -- the latter because a freshly
    bootstrapped environment has no plans yet, so a PlanServerNIC-only scope
    would leave the seeded catalog without cages and every first generation
    would fail preflight (#626).  Seeded types are matched on
    (manufacturer slug, model) so ModuleTypes this plugin did not create are
    never touched.
    """
    switch_dt_ids = DeviceTypeExtension.objects.values_list('device_type_id', flat=True)

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

    return (
        DeviceType.objects.filter(pk__in=switch_dt_ids),
        ModuleType.objects.filter(pk__in=nic_mt_ids),
    )


def plan_scope(plan):
    """The inventory a single plan owns: its switch DeviceTypes and NIC ModuleTypes.

    Used by case ingest so readying a case cannot touch another plan's NICs.
    """
    switch_dt_ids = (
        plan.switch_classes
        .exclude(device_type_extension__isnull=True)
        .values_list('device_type_extension__device_type_id', flat=True)
    )
    nic_mt_ids = (
        PlanServerNIC.objects
        .filter(server_class__plan=plan)
        .values_list('module_type_id', flat=True)
        .distinct()
    )
    return (
        DeviceType.objects.filter(pk__in=switch_dt_ids),
        ModuleType.objects.filter(pk__in=nic_mt_ids),
    )


class Command(BaseCommand):
    help = (
        'Populate ModuleBayTemplate entries on HNP switch DeviceTypes and '
        'NIC ModuleTypes for Stage 2 transceiver module placement.'
    )

    def handle(self, *args, **options):
        device_types, module_types = catalog_scope()
        counts = populate_bays(device_types=device_types, module_types=module_types)

        self.stdout.write(
            self.style.SUCCESS(
                f'populate_transceiver_bays: '
                f'{counts["switch_added"]} switch bay(s) added, '
                f'{counts["switch_removed"]} switch bay(s) removed, '
                f'{counts["nic_added"]} NIC cage(s) added, '
                f'{counts["nic_removed"]} NIC cage(s) removed.'
            )
        )
