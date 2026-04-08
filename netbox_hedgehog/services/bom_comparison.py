"""
Planned-vs-generated BOM comparison service (#401 / #396).

Compares plan intent (PlanServerNIC, PlanServerConnection.transceiver_module_type)
against generated inventory (Module objects tagged with hedgehog_plan_id) for
server-side devices only.

Read-only — does not touch generation, models, or CustomField definitions.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

from dcim.models import Device, Module


class MatchStatus(str, Enum):
    MATCH = "match"
    TYPE_MISMATCH = "type_mismatch"
    EXPECTED_NOT_GENERATED = "expected_not_generated"
    GENERATED_NOT_IN_PLAN = "generated_not_in_plan"


@dataclass(frozen=True)
class ModuleComparisonItem:
    bay_name: str
    section: str  # "nic" or "server_transceiver"
    plan_module_type: Optional[str]
    generated_module_type: Optional[str]
    status: MatchStatus


@dataclass(frozen=True)
class DeviceBOMComparison:
    device_name: str
    device_pk: int
    hedgehog_class: str
    server_class_id: str
    items: Tuple[ModuleComparisonItem, ...]
    matched: int
    mismatched: int
    expected_not_generated: int
    generated_not_in_plan: int


@dataclass(frozen=True)
class BOMComparisonResult:
    has_generation_state: bool
    needs_regeneration: bool
    devices: Tuple[DeviceBOMComparison, ...]
    total_matched: int
    total_mismatched: int
    total_expected_not_generated: int
    total_generated_not_in_plan: int


def compare_plan_vs_generated(plan) -> BOMComparisonResult:
    """
    Compare plan intent vs generated inventory for server devices.

    Algorithm:
    1. Check GenerationState exists.
    2. Find all server devices tagged to the plan.
    3. For each device, find its PlanServerClass (via hedgehog_class custom field).
    4. Compare PlanServerNIC entries against generated top-level Modules.
    5. Compare PlanServerConnection transceiver_module_type against nested Modules.
    6. Detect orphan generated modules not covered by any plan intent.
    7. Aggregate totals.
    """
    from netbox_hedgehog.models.topology_planning import (
        GenerationState, TopologyPlan,
    )
    from netbox_hedgehog.models.topology_planning.topology_plans import (
        PlanServerClass, PlanServerNIC, PlanServerConnection,
    )

    gs = getattr(plan, 'generation_state', None)
    if gs is None:
        return BOMComparisonResult(
            has_generation_state=False,
            needs_regeneration=False,
            devices=(),
            total_matched=0,
            total_mismatched=0,
            total_expected_not_generated=0,
            total_generated_not_in_plan=0,
        )

    needs_regeneration = plan.needs_regeneration
    plan_id = str(plan.pk)

    devices = Device.objects.filter(
        custom_field_data__hedgehog_plan_id=plan_id,
        role__slug='server',
    ).order_by('name')

    device_comparisons = []

    for device in devices:
        hedgehog_class = device.custom_field_data.get('hedgehog_class', '')

        # Find the PlanServerClass for this device.
        try:
            server_class = PlanServerClass.objects.get(
                plan=plan,
                server_class_id=hedgehog_class,
            )
        except PlanServerClass.DoesNotExist:
            # No current plan class for this device — all generated modules are
            # orphaned (the class was removed from the plan after generation).
            orphan_modules = Module.objects.filter(
                device=device,
                custom_field_data__hedgehog_plan_id=plan_id,
            ).select_related('module_bay', 'module_type')
            orphan_items = tuple(
                ModuleComparisonItem(
                    bay_name=m.module_bay.name,
                    section='server_transceiver' if m.module_bay.module_id is not None else 'nic',
                    plan_module_type=None,
                    generated_module_type=m.module_type.model,
                    status=MatchStatus.GENERATED_NOT_IN_PLAN,
                )
                for m in orphan_modules
            )
            device_comparisons.append(DeviceBOMComparison(
                device_name=device.name,
                device_pk=device.pk,
                hedgehog_class=hedgehog_class,
                server_class_id='',
                items=orphan_items,
                matched=0,
                mismatched=0,
                expected_not_generated=0,
                generated_not_in_plan=len(orphan_items),
            ))
            continue

        # Expected NICs from plan.
        expected_nics = {
            nic.nic_id: nic
            for nic in PlanServerNIC.objects.filter(
                server_class=server_class,
            ).select_related('module_type')
        }

        # Expected transceiver bays from connections.
        # bay_name -> transceiver ModuleType (or None for null FK).
        expected_transceivers: dict = {}
        for conn in PlanServerConnection.objects.filter(
            nic__server_class=server_class,
        ).select_related('nic', 'transceiver_module_type'):
            for i in range(conn.ports_per_connection):
                bay = f"cage-{conn.port_index + i}"
                expected_transceivers[bay] = conn.transceiver_module_type

        # Generated modules on this device, tagged to this plan.
        generated_modules = Module.objects.filter(
            device=device,
            custom_field_data__hedgehog_plan_id=plan_id,
        ).select_related('module_bay', 'module_type')

        # Split into top-level (NIC) and nested (transceiver) by module_bay.module_id.
        generated_top: dict = {}   # bay_name -> module  (NIC bays)
        generated_nested: dict = {}  # bay_name -> module  (cage bays)

        for m in generated_modules:
            # module_bay.module_id is not None when the bay is on a Module (nested).
            if m.module_bay.module_id is not None:
                generated_nested[m.module_bay.name] = m
            else:
                generated_top[m.module_bay.name] = m

        items = []
        matched_bays: set = set()
        matched_cage_bays: set = set()

        # --- NIC comparison ---
        for nic_id, nic in expected_nics.items():
            gen = generated_top.get(nic_id)
            plan_mt_name = nic.module_type.model if nic.module_type else None
            if gen is None:
                status = MatchStatus.EXPECTED_NOT_GENERATED
                gen_mt_name = None
            elif gen.module_type_id != nic.module_type_id:
                status = MatchStatus.TYPE_MISMATCH
                gen_mt_name = gen.module_type.model
            else:
                status = MatchStatus.MATCH
                gen_mt_name = gen.module_type.model
            items.append(ModuleComparisonItem(
                bay_name=nic_id,
                section='nic',
                plan_module_type=plan_mt_name,
                generated_module_type=gen_mt_name,
                status=status,
            ))
            matched_bays.add(nic_id)

        # NIC orphans: generated top-level modules not in expected_nics.
        for bay_name, gen in generated_top.items():
            if bay_name not in matched_bays:
                items.append(ModuleComparisonItem(
                    bay_name=bay_name,
                    section='nic',
                    plan_module_type=None,
                    generated_module_type=gen.module_type.model,
                    status=MatchStatus.GENERATED_NOT_IN_PLAN,
                ))

        # --- Transceiver comparison ---
        for bay_name, plan_mt in expected_transceivers.items():
            gen = generated_nested.get(bay_name)
            if plan_mt is None:
                # Null FK intent: if nothing generated — omit row.
                # If something generated — GENERATED_NOT_IN_PLAN.
                if gen is not None:
                    items.append(ModuleComparisonItem(
                        bay_name=bay_name,
                        section='server_transceiver',
                        plan_module_type=None,
                        generated_module_type=gen.module_type.model,
                        status=MatchStatus.GENERATED_NOT_IN_PLAN,
                    ))
                matched_cage_bays.add(bay_name)
                continue

            if gen is None:
                status = MatchStatus.EXPECTED_NOT_GENERATED
                gen_mt_name = None
            elif gen.module_type_id != plan_mt.pk:
                status = MatchStatus.TYPE_MISMATCH
                gen_mt_name = gen.module_type.model
            else:
                status = MatchStatus.MATCH
                gen_mt_name = gen.module_type.model

            items.append(ModuleComparisonItem(
                bay_name=bay_name,
                section='server_transceiver',
                plan_module_type=plan_mt.model,
                generated_module_type=gen_mt_name,
                status=status,
            ))
            matched_cage_bays.add(bay_name)

        # Transceiver orphans: nested modules not covered by any expected entry.
        for bay_name, gen in generated_nested.items():
            if bay_name not in matched_cage_bays:
                items.append(ModuleComparisonItem(
                    bay_name=bay_name,
                    section='server_transceiver',
                    plan_module_type=None,
                    generated_module_type=gen.module_type.model,
                    status=MatchStatus.GENERATED_NOT_IN_PLAN,
                ))

        items_tuple = tuple(items)
        matched = sum(1 for i in items_tuple if i.status == MatchStatus.MATCH)
        mismatched = sum(1 for i in items_tuple if i.status == MatchStatus.TYPE_MISMATCH)
        exp_not_gen = sum(1 for i in items_tuple if i.status == MatchStatus.EXPECTED_NOT_GENERATED)
        gen_not_plan = sum(1 for i in items_tuple if i.status == MatchStatus.GENERATED_NOT_IN_PLAN)

        device_comparisons.append(DeviceBOMComparison(
            device_name=device.name,
            device_pk=device.pk,
            hedgehog_class=hedgehog_class,
            server_class_id=server_class.server_class_id,
            items=items_tuple,
            matched=matched,
            mismatched=mismatched,
            expected_not_generated=exp_not_gen,
            generated_not_in_plan=gen_not_plan,
        ))

    devices_tuple = tuple(device_comparisons)
    total_matched = sum(d.matched for d in devices_tuple)
    total_mismatched = sum(d.mismatched for d in devices_tuple)
    total_expected_not_generated = sum(d.expected_not_generated for d in devices_tuple)
    total_generated_not_in_plan = sum(d.generated_not_in_plan for d in devices_tuple)

    return BOMComparisonResult(
        has_generation_state=True,
        needs_regeneration=needs_regeneration,
        devices=devices_tuple,
        total_matched=total_matched,
        total_mismatched=total_mismatched,
        total_expected_not_generated=total_expected_not_generated,
        total_generated_not_in_plan=total_generated_not_in_plan,
    )


def render_comparison_csv(result: BOMComparisonResult) -> str:
    """Return a CSV string for the comparison result.

    Field order: device_name, hedgehog_class, server_class_id, section,
                 bay_name, plan_module_type, generated_module_type, status
    """
    buf = io.StringIO()
    fieldnames = [
        'device_name', 'hedgehog_class', 'server_class_id',
        'section', 'bay_name', 'plan_module_type',
        'generated_module_type', 'status',
    ]
    writer = csv.DictWriter(buf, fieldnames=fieldnames, lineterminator='\n')
    writer.writeheader()
    for dev in result.devices:
        for item in dev.items:
            writer.writerow({
                'device_name': dev.device_name,
                'hedgehog_class': dev.hedgehog_class,
                'server_class_id': dev.server_class_id,
                'section': item.section,
                'bay_name': item.bay_name,
                'plan_module_type': item.plan_module_type or '',
                'generated_module_type': item.generated_module_type or '',
                'status': item.status.value,
            })
    return buf.getvalue()
