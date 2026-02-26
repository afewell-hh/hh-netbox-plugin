"""Assertion helpers for YAML test-case expectations."""

from __future__ import annotations

from netbox_hedgehog.models.topology_planning import (
    PlanServerClass,
    PlanServerConnection,
    PlanSwitchClass,
    TopologyPlan,
)


def planning_counts(plan: TopologyPlan) -> dict:
    """Return planning-graph counts for assertion checks."""
    return {
        "server_classes": PlanServerClass.objects.filter(plan=plan).count(),
        "switch_classes": PlanSwitchClass.objects.filter(plan=plan).count(),
        "connections": PlanServerConnection.objects.filter(server_class__plan=plan).count(),
    }

