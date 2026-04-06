"""
Plan-scoped BOM export service.

Aggregates generated Module inventory into procurement-ready BOM line items.
Read-only — does not touch generation, models, or CustomField definitions.

DAC/AOC rule: switch-side cable-assembly modules are suppressed from line_items
and counted in suppressed_switch_cable_assembly_count for auditability.
"""
from __future__ import annotations

from dataclasses import dataclass

from dcim.models import Module

_CABLE_ASSEMBLY_MEDIUMS = frozenset({'DAC', 'ACC'})

_SECTION_ORDER = {'nic': 0, 'server_transceiver': 1, 'switch_transceiver': 2}


@dataclass(frozen=True)
class BOMLineItem:
    section: str
    module_type_id: int
    module_type_model: str
    manufacturer: str
    quantity: int
    cage_type: str | None
    medium: str | None
    connector: str | None
    standard: str | None
    is_cable_assembly: bool


@dataclass(frozen=True)
class PlanBOM:
    plan_id: int
    plan_name: str
    generated_at: str
    line_items: tuple
    suppressed_switch_cable_assembly_count: int


def get_plan_bom(plan) -> PlanBOM:
    """Return an aggregated BOM for a generated plan.

    Modules are scoped via device__custom_field_data__hedgehog_plan_id.
    Switch-side DAC/ACC modules are suppressed; count preserved for audit.
    """
    plan_id = str(plan.pk)
    modules = Module.objects.filter(
        device__custom_field_data__hedgehog_plan_id=plan_id,
    ).select_related(
        'device', 'device__role',
        'module_bay',
        'module_type', 'module_type__manufacturer',
    )

    counts: dict[tuple, int] = {}
    meta: dict[tuple, dict] = {}
    suppressed = 0

    for module in modules:
        section = _classify_module(module)
        attrs = module.module_type.attribute_data or {}
        medium = attrs.get('medium')
        is_cable_assembly = medium in _CABLE_ASSEMBLY_MEDIUMS

        if section == 'switch_transceiver' and is_cable_assembly:
            suppressed += 1
            continue

        key = (section, module.module_type_id)
        counts[key] = counts.get(key, 0) + 1
        if key not in meta:
            mfr_obj = module.module_type.manufacturer
            meta[key] = {
                'module_type_model': module.module_type.model,
                'manufacturer': mfr_obj.name if mfr_obj else '',
                'cage_type': attrs.get('cage_type'),
                'medium': medium,
                'connector': attrs.get('connector'),
                'standard': attrs.get('standard'),
                'is_cable_assembly': is_cable_assembly,
            }

    def _sort_key(item):
        sec, mt_id = item
        m = meta[item]
        return (_SECTION_ORDER.get(sec, 99), m['manufacturer'], m['module_type_model'])

    line_items = tuple(
        BOMLineItem(
            section=section,
            module_type_id=mt_id,
            quantity=counts[(section, mt_id)],
            **meta[(section, mt_id)],
        )
        for (section, mt_id) in sorted(counts.keys(), key=_sort_key)
    )

    gs = getattr(plan, 'generation_state', None)
    generated_at = gs.generated_at.isoformat() if gs else ''

    return PlanBOM(
        plan_id=plan.pk,
        plan_name=plan.name,
        generated_at=generated_at,
        line_items=line_items,
        suppressed_switch_cable_assembly_count=suppressed,
    )


def _classify_module(module) -> str:
    """Single classification authority for BOM section assignment."""
    if module.module_bay.module_id is not None:
        return 'server_transceiver'
    if module.device.role.slug == 'server':
        return 'nic'
    return 'switch_transceiver'
