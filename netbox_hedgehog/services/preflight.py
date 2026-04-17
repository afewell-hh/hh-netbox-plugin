"""
Pre-flight validation service for topology plan generation (DIET-348).

Provides check_transceiver_bay_readiness(plan) — the single source of truth
for determining whether transceiver ModuleBayTemplates are present before
generation is attempted. Called from views, the management command, and the
plan detail page context builder.

This module does NOT call DeviceGenerator and makes NO writes to the database.
The generation-time backstop in DeviceGenerator.generate_all() is retained as
defense-in-depth and is independent of this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from django.db.models import Count

from dcim.models import DeviceType, ModuleType

from netbox_hedgehog.models.topology_planning.topology_plans import PlanServerConnection
from netbox_hedgehog.models.topology_planning.port_zones import SwitchPortZone

if TYPE_CHECKING:
    from netbox_hedgehog.models.topology_planning.topology_plans import TopologyPlan


@dataclass
class TransceiverBayReadinessResult:
    """
    Result of check_transceiver_bay_readiness(plan).

    Fields
    ------
    is_ready : bool
        True if generation may proceed; False if any hard blocker was found.
        True when either (a) no transceiver_module_type FK is set anywhere in
        this plan (early-exit path), or (b) all required ModuleBayTemplate rows
        are present for all switch DeviceType and NIC ModuleType records.

    has_transceiver_fks : bool
        True if any transceiver_module_type FK is non-null in this plan.
        False means the early-exit path was taken; no bay checks were run.
        Controls whether the advisory banner renders on the detail page.

    missing : list[dict]
        One entry per missing-bay entity (not per individual bay). Empty when
        is_ready is True. Each entry has keys:
            entity_type  : 'switch_device_type' | 'nic_module_type'
            entity_id    : int   — PK of the DeviceType or ModuleType
            entity_name  : str   — DeviceType.model or ModuleType.model
            missing_count: int   — it_count - mbt_count (switch) or 0 (NIC at-least-one check)
            hint         : str   — actionable operator text
    """
    is_ready: bool
    has_transceiver_fks: bool
    missing: list = field(default_factory=list)


def check_transceiver_bay_readiness(plan: "TopologyPlan") -> TransceiverBayReadinessResult:
    """
    Run the two-phase transceiver bay pre-flight check for *plan*.

    Phase 1 (fast-path gates — checks 1 & 2):
        If no transceiver_module_type FK is set on any PlanServerConnection or
        SwitchPortZone belonging to this plan, return immediately with
        is_ready=True and has_transceiver_fks=False. Zero additional queries
        beyond the two existence checks.

    Phase 2 (bay presence checks — checks 3 & 4):
        Only reached when at least one FK is set.
        Check 3: NIC ModuleType — each ModuleType referenced by a
            PlanServerConnection with a non-null transceiver_module_type in this
            plan must have at least one ModuleBayTemplate child.
        Check 4: Switch DeviceType bay count parity — each DeviceType referenced
            by a SwitchPortZone with a non-null transceiver_module_type in this
            plan must have at least as many ModuleBayTemplate rows as
            InterfaceTemplate rows.
        Unrelated NICs and switch classes in the same plan that carry no
        transceiver intent are deliberately excluded from both checks.

    Returns a TransceiverBayReadinessResult. Never raises.
    """
    # Phase 0 — DIET-466: required transceiver intent check (always runs).
    # Counts null-transceiver connections and zones; if any are missing, blocks
    # generation immediately.  An empty plan (0 connections + 0 zones) has counts
    # of zero and passes this check (PF7).
    missing = []
    null_conn_count = PlanServerConnection.objects.filter(
        server_class__plan=plan,
        transceiver_module_type__isnull=True,
    ).count()
    null_zone_count = SwitchPortZone.objects.filter(
        switch_class__plan=plan,
        transceiver_module_type__isnull=True,
    ).count()
    if null_conn_count > 0:
        missing.append({
            'entity_type': 'missing_transceiver_connections',
            'entity_id': None,
            'entity_name': 'Server Connections',
            'missing_count': null_conn_count,
            'hint': 'Set transceiver_module_type on all server connections.',
        })
    if null_zone_count > 0:
        missing.append({
            'entity_type': 'missing_transceiver_zones',
            'entity_id': None,
            'entity_name': 'Switch Port Zones',
            'missing_count': null_zone_count,
            'hint': 'Set transceiver_module_type on all switch port zones.',
        })

    # Check 1 — PlanServerConnection transceiver FK presence (Phase 2 scope gate)
    connection_fk_set = PlanServerConnection.objects.filter(
        server_class__plan=plan,
        transceiver_module_type__isnull=False,
    ).exists()

    # Check 2 — SwitchPortZone transceiver FK presence (Phase 2 scope gate)
    zone_fk_set = SwitchPortZone.objects.filter(
        switch_class__plan=plan,
        transceiver_module_type__isnull=False,
    ).exists()

    has_transceiver_fks = connection_fk_set or zone_fk_set

    if not has_transceiver_fks:
        # No non-null FKs: Phase 2 bay checks have no scope; return current missing[].
        return TransceiverBayReadinessResult(
            is_ready=len(missing) == 0,
            has_transceiver_fks=False,
            missing=missing,
        )

    # Phase 2 — bay presence checks (only when at least one FK is set).

    # Check 3 — NIC ModuleType bay presence (at-least-one-bay check)
    # Scope: only NIC module types actually referenced by PlanServerConnection rows
    # in this plan that have a non-null transceiver_module_type FK.  Unrelated NICs
    # in the same plan (no transceiver intent) are deliberately excluded so that
    # mixed plans are not over-blocked.
    # FK chain: PlanServerConnection.nic__module_type_id (nic → PlanServerNIC)
    nic_mt_ids = (
        PlanServerConnection.objects.filter(
            server_class__plan=plan,
            transceiver_module_type__isnull=False,
        )
        .values_list('nic__module_type_id', flat=True)
        .distinct()
    )
    missing_nic_types = ModuleType.objects.filter(
        pk__in=nic_mt_ids,
        modulebaytemplates__isnull=True,
    ).values('pk', 'model')

    for nic_mt in missing_nic_types:
        missing.append({
            'entity_type': 'nic_module_type',
            'entity_id': nic_mt['pk'],
            'entity_name': nic_mt['model'],
            'missing_count': 0,  # at-least-one check; exact parity deferred (open question 7)
            'hint': (
                'Run populate_transceiver_bays to add cage ModuleBayTemplates '
                'to this NIC ModuleType.'
            ),
        })

    # Check 4 — Switch DeviceType bay count parity
    # Scope: only device types actually referenced by SwitchPortZone rows in this
    # plan that have a non-null transceiver_module_type FK.  Unrelated switch classes
    # in the same plan (no transceiver intent on any of their zones) are deliberately
    # excluded so that mixed plans are not over-blocked.
    # FK chain: SwitchPortZone.switch_class__device_type_extension__device_type_id
    dt_ids = (
        SwitchPortZone.objects.filter(
            switch_class__plan=plan,
            transceiver_module_type__isnull=False,
        )
        .values_list('switch_class__device_type_extension__device_type_id', flat=True)
        .distinct()
    )
    for dt in DeviceType.objects.filter(pk__in=dt_ids).annotate(
        it_count=Count('interfacetemplates', distinct=True),
        mbt_count=Count('modulebaytemplates', distinct=True),
    ):
        if dt.mbt_count < dt.it_count:
            missing.append({
                'entity_type': 'switch_device_type',
                'entity_id': dt.pk,
                'entity_name': dt.model,
                'missing_count': dt.it_count - dt.mbt_count,
                'hint': (
                    'Run populate_transceiver_bays to add ModuleBayTemplates '
                    'to this switch DeviceType.'
                ),
            })

    return TransceiverBayReadinessResult(
        is_ready=len(missing) == 0,
        has_transceiver_fks=has_transceiver_fks,
        missing=missing,
    )


def _entry_kind_label(entry: dict) -> str:
    """Human-readable label for a missing[] entry."""
    etype = entry.get('entity_type', '')
    if etype == 'missing_transceiver_connections':
        return 'Server Connections (missing transceiver intent)'
    if etype == 'missing_transceiver_zones':
        return 'Switch Port Zones (missing transceiver intent)'
    if etype == 'switch_device_type':
        return 'Switch DeviceType'
    return 'NIC ModuleType'


def user_message(result: TransceiverBayReadinessResult) -> str:
    """Short operator-facing string for django.contrib.messages.error()."""
    if not result.missing:
        return (
            "Transceiver pre-flight check failed. "
            "Set transceiver_module_type on all zones and connections, then retry."
        )
    # Check if the blockers are missing-intent (Phase 0) vs missing-bay (Phase 2)
    intent_entries = [
        e for e in result.missing
        if e['entity_type'] in ('missing_transceiver_connections', 'missing_transceiver_zones')
    ]
    bay_entries = [
        e for e in result.missing
        if e['entity_type'] not in ('missing_transceiver_connections', 'missing_transceiver_zones')
    ]
    parts = []
    if intent_entries:
        total_missing = sum(e['missing_count'] for e in intent_entries)
        parts.append(
            f"{total_missing} zone(s)/connection(s) are missing transceiver_module_type"
        )
    if bay_entries:
        names = ', '.join(e['entity_name'] for e in bay_entries)
        parts.append(
            f"transceiver bays are missing for {names} "
            f"(run populate_transceiver_bays to fix)"
        )
    return f"Cannot generate devices: {'; '.join(parts)}. Fix the issues and retry."


def cli_message(result: TransceiverBayReadinessResult) -> str:
    """Multi-line operator-facing string for CommandError or stdout in the CLI."""
    if not result.missing:
        return (
            "Transceiver pre-flight check failed. "
            "Set transceiver_module_type on all zones and connections, then retry."
        )
    lines = ["Generation blocked: transceiver pre-flight check failed.", ""]
    for entry in result.missing:
        etype = entry.get('entity_type', '')
        if etype == 'missing_transceiver_connections':
            lines.append(
                f"  - {entry['missing_count']} server connection(s) are missing "
                f"transceiver_module_type. {entry['hint']}"
            )
        elif etype == 'missing_transceiver_zones':
            lines.append(
                f"  - {entry['missing_count']} switch port zone(s) are missing "
                f"transceiver_module_type. {entry['hint']}"
            )
        else:
            kind = _entry_kind_label(entry)
            if entry['missing_count']:
                lines.append(
                    f"  - [{kind}] {entry['entity_name']} "
                    f"(missing {entry['missing_count']} ModuleBayTemplate(s))"
                )
            else:
                lines.append(
                    f"  - [{kind}] {entry['entity_name']} (no ModuleBayTemplates found)"
                )
    lines.append("")
    lines.append("Run populate_transceiver_bays after setting all transceiver intents.")
    return '\n'.join(lines)
