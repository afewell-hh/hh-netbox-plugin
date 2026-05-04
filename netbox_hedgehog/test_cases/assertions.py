"""Assertion helpers for YAML test-case expectations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from netbox_hedgehog.models.topology_planning import (
    GenerationState,
    PlanServerClass,
    PlanServerConnection,
    PlanSwitchClass,
    SwitchPortZone,
    TopologyPlan,
)


@dataclass
class ContractResult:
    name: str
    result: str  # "pass", "fail", "skipped"
    expected: Any = None
    actual: Any = None
    message: str = ""

    def __repr__(self):
        return f"ContractResult({self.name!r}, {self.result!r}, expected={self.expected!r}, actual={self.actual!r})"


def planning_counts(plan: TopologyPlan) -> dict:
    """Return planning-graph counts for assertion checks."""
    return {
        "server_classes": PlanServerClass.objects.filter(plan=plan).count(),
        "switch_classes": PlanSwitchClass.objects.filter(plan=plan).count(),
        "connections": PlanServerConnection.objects.filter(server_class__plan=plan).count(),
    }


def validate_contract(plan: TopologyPlan, contract: dict) -> list[ContractResult]:
    """
    Validate a contract dict against live DB state for the given plan.

    Supported contract keys: counts, zones, generation, topology.
    Returns a list of ContractResult objects.
    """
    results: list[ContractResult] = []

    # counts assertions
    counts_spec = contract.get("counts")
    if isinstance(counts_spec, dict):
        actual = planning_counts(plan)
        for key, expected_val in counts_spec.items():
            actual_val = actual.get(key)
            if actual_val == expected_val:
                results.append(ContractResult(
                    name=f"counts.{key}", result="pass",
                    expected=expected_val, actual=actual_val,
                ))
            else:
                results.append(ContractResult(
                    name=f"counts.{key}", result="fail",
                    expected=expected_val, actual=actual_val,
                    message=f"Expected {expected_val}, got {actual_val}",
                ))

    # zones assertions
    zones_spec = contract.get("zones")
    if isinstance(zones_spec, dict):
        required = zones_spec.get("required", []) or []
        for entry in required:
            sc_id = entry.get("switch_class")
            zone_name = entry.get("zone_name")
            exists = SwitchPortZone.objects.filter(
                switch_class__plan=plan,
                switch_class__switch_class_id=sc_id,
                zone_name=zone_name,
            ).exists()
            name = f"zones.required[{sc_id}/{zone_name}]"
            if exists:
                results.append(ContractResult(name=name, result="pass"))
            else:
                results.append(ContractResult(
                    name=name, result="fail",
                    message=f"Zone '{zone_name}' not found for switch_class '{sc_id}'",
                ))

    # generation assertions
    generation_spec = contract.get("generation")
    if isinstance(generation_spec, dict):
        try:
            gs = GenerationState.objects.get(plan=plan)
        except GenerationState.DoesNotExist:
            for key in generation_spec:
                results.append(ContractResult(
                    name=f"generation.{key}", result="skipped",
                    message="No GenerationState exists for this plan",
                ))
        else:
            field_map = {
                "device_count": gs.device_count,
                "interface_count": gs.interface_count,
                "cable_count": gs.cable_count,
            }
            for key, expected_val in generation_spec.items():
                actual_val = field_map.get(key)
                if actual_val == expected_val:
                    results.append(ContractResult(
                        name=f"generation.{key}", result="pass",
                        expected=expected_val, actual=actual_val,
                    ))
                else:
                    results.append(ContractResult(
                        name=f"generation.{key}", result="fail",
                        expected=expected_val, actual=actual_val,
                        message=f"Expected {expected_val}, got {actual_val}",
                    ))

    # topology assertions
    topology_spec = contract.get("topology")
    if isinstance(topology_spec, dict):
        storage_spec = topology_spec.get("storage")
        if isinstance(storage_spec, dict):
            results.extend(_validate_topology_storage(plan, storage_spec))

    return results


def _validate_topology_storage(plan: TopologyPlan, storage: dict) -> list[ContractResult]:
    results: list[ContractResult] = []
    sc_id = storage.get("switch_class_id")
    srv_id = storage.get("server_class_id")
    expected_qty = storage.get("server_quantity")

    if srv_id is not None and expected_qty is not None:
        try:
            sc = PlanServerClass.objects.get(plan=plan, server_class_id=srv_id)
            actual_qty = sc.quantity
        except PlanServerClass.DoesNotExist:
            actual_qty = None
        name = f"topology.storage.server_quantity[{srv_id}]"
        if actual_qty == expected_qty:
            results.append(ContractResult(name=name, result="pass",
                                          expected=expected_qty, actual=actual_qty))
        else:
            results.append(ContractResult(name=name, result="fail",
                                          expected=expected_qty, actual=actual_qty,
                                          message=f"Expected quantity {expected_qty}, got {actual_qty}"))

    if sc_id is not None:
        exists = PlanSwitchClass.objects.filter(plan=plan, switch_class_id=sc_id).exists()
        name = f"topology.storage.switch_class_id[{sc_id}]"
        if exists:
            results.append(ContractResult(name=name, result="pass"))
        else:
            results.append(ContractResult(name=name, result="fail",
                                          message=f"Switch class '{sc_id}' not found"))

    return results
