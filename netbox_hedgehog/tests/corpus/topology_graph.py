"""Test-only, versioned topology comparison representation for #620/#664.

This module intentionally lives below ``tests``.  ``TopologyGraph`` is an
evidence-normalization representation, not a public schema, persisted format,
or runtime dependency.  It does not select a canonical topology format or make
an HNP output authoritative.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping


REPRESENTATION_VERSION = "topology-graph-test/v1"


class ExportMode(str, Enum):
    """Export scope is part of comparison identity, never a normalizable detail."""

    FULL_PLAN = "full-plan"
    FABRIC_SCOPED = "fabric-scoped"


class ComparisonDisposition(str, Enum):
    EQUIVALENCE_ELIGIBLE = "equivalence-eligible"
    DIAGNOSTIC = "diagnostic"


class NodePlacement(str, Enum):
    """A node's topology role; ordinary servers are not fabric members."""

    SERVER = "server"
    MANAGED_FABRIC = "managed-fabric"
    UNMANAGED_FABRIC = "unmanaged-fabric"


@dataclass(frozen=True, order=True)
class Endpoint:
    """A cable endpoint including physical breakout identity where applicable."""

    device: str
    interface: str
    physical_parent: str | None = None
    lane: int | None = None


@dataclass(frozen=True)
class UnmeasuredEndpoint:
    """Records missing breakout identity without collapsing it to a logical port."""

    device: str
    interface: str
    reason: str


def normalize_endpoint(value: Mapping[str, Any]) -> Endpoint | UnmeasuredEndpoint:
    """Normalize an endpoint, refusing to invent parent/lane breakout identity."""

    device = str(value["device"])
    interface = str(value["interface"])
    parent = value.get("physical_parent")
    lane = value.get("lane")
    is_breakout = bool(value.get("is_breakout"))
    if is_breakout and (parent is None or lane is None):
        missing = "physical_parent" if parent is None else "lane"
        return UnmeasuredEndpoint(device, interface, f"breakout endpoint missing {missing}")
    return Endpoint(device, interface, None if parent is None else str(parent), lane)


@dataclass(frozen=True, order=True)
class GraphNode:
    name: str
    kind: str
    placement: NodePlacement = NodePlacement.SERVER
    surrogate: bool = False


@dataclass(frozen=True, order=True)
class GraphEdge:
    left: Endpoint
    right: Endpoint
    kind: str = "Connection"

    def canonical(self) -> tuple[Endpoint, Endpoint, str]:
        return min(self.left, self.right), max(self.left, self.right), self.kind


@dataclass(frozen=True)
class ComparisonIdentity:
    case_id: str
    mode: ExportMode
    source: str
    representation_version: str = REPRESENTATION_VERSION


@dataclass(frozen=True)
class ProvenanceEnvelope:
    """The #620 C4 evidence fields required before an equivalence claim."""

    values: Mapping[str, str]

    REQUIRED_FIELDS = frozenset({
        "source_hash",
        "source_revision",
        "normalizer_version",
        "platform_image_digest",
        "platform_version",
        "plugin_revision",
        "migration_state",
        "configuration_fingerprint",
        "reference_catalog_fingerprint",
        "database_state",
        "runner_flags",
        "export_mode",
        "command",
    })

    def missing(self) -> tuple[str, ...]:
        return tuple(sorted(field for field in self.REQUIRED_FIELDS if not self.values.get(field)))


@dataclass(frozen=True)
class TopologyGraph:
    identity: ComparisonIdentity
    nodes: frozenset[GraphNode] = frozenset()
    edges: frozenset[GraphEdge] = frozenset()
    required_surrogates: frozenset[str] = frozenset()
    forbidden_surrogates: frozenset[str] = frozenset()
    unmeasured: tuple[UnmeasuredEndpoint, ...] = ()
    provenance: ProvenanceEnvelope = field(default_factory=lambda: ProvenanceEnvelope({}))

    @classmethod
    def from_records(
        cls,
        identity: ComparisonIdentity,
        nodes: Iterable[GraphNode],
        edges: Iterable[Mapping[str, Any]],
        provenance: ProvenanceEnvelope,
        required_surrogates: Iterable[str] = (),
        forbidden_surrogates: Iterable[str] = (),
    ) -> "TopologyGraph":
        normalized_edges: set[GraphEdge] = set()
        unmeasured: list[UnmeasuredEndpoint] = []
        for edge in edges:
            left = normalize_endpoint(edge["left"])
            right = normalize_endpoint(edge["right"])
            if isinstance(left, UnmeasuredEndpoint):
                unmeasured.append(left)
            if isinstance(right, UnmeasuredEndpoint):
                unmeasured.append(right)
            if isinstance(left, Endpoint) and isinstance(right, Endpoint):
                normalized_edges.add(GraphEdge(left, right, str(edge.get("kind", "Connection"))))
        return cls(
            identity,
            frozenset(nodes),
            frozenset(normalized_edges),
            frozenset(required_surrogates),
            frozenset(forbidden_surrogates),
            tuple(unmeasured),
            provenance,
        )


@dataclass(frozen=True)
class ComparisonReport:
    disposition: ComparisonDisposition
    matches: Mapping[str, tuple[Any, ...]]
    differences: Mapping[str, tuple[Any, ...]]
    exclusions: tuple[str, ...]
    unmeasured: tuple[UnmeasuredEndpoint, ...]
    missing_provenance: tuple[str, ...]


def compare_graphs(left: TopologyGraph, right: TopologyGraph) -> ComparisonReport:
    """Compare graphs while preserving scope, provenance, and unmeasured facts."""

    differences: dict[str, tuple[Any, ...]] = {}
    exclusions: list[str] = []
    if left.identity.representation_version != right.identity.representation_version:
        differences["representation_version"] = (
            left.identity.representation_version,
            right.identity.representation_version,
        )
    if left.identity.case_id != right.identity.case_id:
        differences["case_id"] = (left.identity.case_id, right.identity.case_id)
    if left.identity.mode != right.identity.mode:
        differences["export_mode"] = (left.identity.mode.value, right.identity.mode.value)

    left_edges = frozenset(edge.canonical() for edge in left.edges)
    right_edges = frozenset(edge.canonical() for edge in right.edges)
    for axis, first, second in (("nodes", left.nodes, right.nodes), ("edges", left_edges, right_edges)):
        only_left = tuple(sorted(first - second))
        only_right = tuple(sorted(second - first))
        if only_left or only_right:
            differences[axis] = (only_left, only_right)

    for graph in (left, right):
        exclusions.extend(validate_surrogate_contract(graph))

    missing = tuple(sorted(set(left.provenance.missing()) | set(right.provenance.missing())))
    unmeasured = tuple(dict.fromkeys(left.unmeasured + right.unmeasured))
    if missing:
        differences["provenance"] = missing
    if unmeasured:
        differences["unmeasured"] = tuple(unmeasured)

    matches = {
        axis: value
        for axis, value in {
            "nodes": tuple(sorted(left.nodes)),
            "edges": tuple(sorted(left_edges)),
        }.items()
        if axis not in differences or differences[axis] == ()
    }
    disposition = (
        ComparisonDisposition.EQUIVALENCE_ELIGIBLE
        if not missing and not unmeasured and not differences and not exclusions
        else ComparisonDisposition.DIAGNOSTIC
    )
    return ComparisonReport(disposition, matches, differences, tuple(exclusions), unmeasured, missing)


def validate_surrogate_contract(graph: TopologyGraph) -> list[str]:
    """Apply #620 positive and negative unmanaged-fabric export obligations."""

    nodes_by_name = {node.name: node for node in graph.nodes}
    findings: list[str] = []
    actual_surrogates = {node.name for node in graph.nodes if node.surrogate}
    for name in sorted(graph.required_surrogates - actual_surrogates):
        findings.append(f"missing required surrogate node: {name}")
    for name in sorted(graph.forbidden_surrogates & actual_surrogates):
        findings.append(f"forbidden scoped surrogate node: {name}")
    for node in graph.nodes:
        if node.placement is NodePlacement.UNMANAGED_FABRIC and not node.surrogate:
            findings.append(f"forbidden non-surrogate unmanaged node: {node.name}")
    for edge in graph.edges:
        left = nodes_by_name.get(edge.left.device)
        right = nodes_by_name.get(edge.right.device)
        if not left or not right:
            continue
        surrogate_endpoints = [node for node in (left, right) if node.surrogate]
        if not surrogate_endpoints:
            continue
        if left.surrogate and right.surrogate:
            findings.append(f"forbidden surrogate-to-surrogate connection: {left.name}<->{right.name}")
        elif left.placement is NodePlacement.SERVER or right.placement is NodePlacement.SERVER:
            findings.append(f"forbidden server-to-surrogate connection: {left.name}<->{right.name}")
    return findings
