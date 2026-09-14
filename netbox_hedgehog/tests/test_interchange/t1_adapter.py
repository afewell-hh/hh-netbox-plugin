"""Test-only adapter: decoded interchange -> T1 TopologyGraph (#673 I11a).

Used ONLY to compare the topology subset. It is deliberately separate from the
full-model comparator, which must never import T1 -- the whole reason the
full-model comparator exists is that T1 cannot see envelope, catalog, manifest,
provenance, or extension facts (#672 B3).

Production must never import this module either; `test_containment` asserts it.
"""

from __future__ import annotations

from typing import Any, Mapping

from netbox_hedgehog.tests.corpus.topology_graph import (
    ComparisonIdentity,
    ExportMode,
    GraphNode,
    NodePlacement,
    ProvenanceEnvelope,
    TopologyGraph,
)

#: A complete C4 envelope for fixture-derived graphs. Real corpus evidence must
#: carry measured values; these exist so a FIXTURE comparison is not reported as
#: provenance-incomplete and thereby mask a genuine topology difference.
FIXTURE_PROVENANCE = {field: f"fixture-{field}" for field in ProvenanceEnvelope.REQUIRED_FIELDS}


def _design_revisions(decoded: Mapping[str, Any]):
    for obj in decoded.get("objects") or []:
        if isinstance(obj, Mapping) and obj.get("kind") == "DesignRevision":
            yield obj


def to_topology_graph(decoded: Mapping[str, Any], *, case_id: str,
                      mode: ExportMode = ExportMode.FULL_PLAN,
                      source: str = "interchange") -> TopologyGraph:
    """Project the topology subset of a decoded bundle into T1's representation."""
    nodes, edges = [], []
    for revision in _design_revisions(decoded):
        topology = revision.get("topology") or {}
        for fabric in topology.get("fabrics") or []:
            for switch_class in fabric.get("switchClasses") or []:
                identity = switch_class.get("identity") or {}
                nodes.append(GraphNode(
                    name=str(identity.get("slug")),
                    kind=str(switch_class.get("role")),
                    placement=NodePlacement.MANAGED_FABRIC,
                ))
        for connection in topology.get("connections") or []:
            edges.append(connection)
    return TopologyGraph.from_records(
        ComparisonIdentity(case_id=case_id, mode=mode, source=source),
        nodes, edges, ProvenanceEnvelope(dict(FIXTURE_PROVENANCE)),
    )
