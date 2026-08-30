"""Deterministic composition of OPG leaf projections into shared XOC spines.

The generator intentionally creates complete, standalone spine-leaf fabrics.
An OPG publication is instead a projection: servers and leaf switches remain,
while its local spine tier is omitted.  This module restores the shared spine
tier at XOC export time without creating a large transient NetBox topology.
"""

from __future__ import annotations

from dataclasses import dataclass
from collections import defaultdict
from copy import deepcopy
import hashlib


class CompositionError(ValueError):
    """Raised when projections cannot form an unambiguous XOC."""


@dataclass(frozen=True)
class LeafProjection:
    """One domain-scoped leaf and its reserved XOC-facing uplink ports."""

    domain: str
    name: str
    fabric: str
    reserved_uplinks: tuple[str, ...]

    @property
    def qualified_name(self) -> str:
        return f"{self.domain}--{self.name}"


@dataclass(frozen=True)
class SpineLink:
    fabric: str
    leaf: str
    leaf_port: str
    spine: str
    spine_port: str


@dataclass(frozen=True)
class ComposedFabric:
    name: str
    spines: tuple[str, ...]
    links: tuple[SpineLink, ...]


XOC3712_SHARED_FABRICS = frozenset({"frontend", "backend-plane-a", "backend-plane-b"})


def compose_shared_spines(
    leaves: list[LeafProjection],
    *,
    spine_count: int = 32,
    spine_downlink_capacity: int = 64,
    spine_name_prefix: str = "xoc3712",
) -> dict[str, ComposedFabric]:
    """Compose full leaf-to-spine meshes for each named fabric.

    Each leaf must supply one uniquely-named reserved uplink per spine.  Port
    number ``i`` on every leaf is paired with spine ``i``; each spine uses a
    sequential downlink port determined by the stable leaf ordering.  The
    result is pure data, so the caller can render inventory/CSV/YAML assets
    without instantiating an intermediate, monolithic topology plan.
    """
    if spine_count <= 0:
        raise CompositionError("spine_count must be positive")

    grouped: dict[str, list[LeafProjection]] = defaultdict(list)
    qualified_names: set[str] = set()
    for leaf in leaves:
        if not leaf.domain or not leaf.name or not leaf.fabric:
            raise CompositionError("leaf domain, name, and fabric are required")
        if leaf.qualified_name in qualified_names:
            raise CompositionError(f"duplicate namespaced leaf: {leaf.qualified_name}")
        qualified_names.add(leaf.qualified_name)
        if len(leaf.reserved_uplinks) != spine_count:
            raise CompositionError(
                f"{leaf.qualified_name}: expected {spine_count} reserved uplinks, "
                f"found {len(leaf.reserved_uplinks)}"
            )
        if len(set(leaf.reserved_uplinks)) != spine_count:
            raise CompositionError(f"{leaf.qualified_name}: reserved uplinks are not unique")
        grouped[leaf.fabric].append(leaf)

    result: dict[str, ComposedFabric] = {}
    for fabric, fabric_leaves in grouped.items():
        ordered_leaves = sorted(fabric_leaves, key=lambda leaf: leaf.qualified_name)
        if len(ordered_leaves) > spine_downlink_capacity:
            raise CompositionError(
                f"{fabric}: {len(ordered_leaves)} leaves exceed spine downlink "
                f"capacity {spine_downlink_capacity}"
            )
        spines = tuple(
            f"{spine_name_prefix}--{fabric}--spine-{index:02d}"
            for index in range(1, spine_count + 1)
        )
        links = []
        for leaf_index, leaf in enumerate(ordered_leaves, start=1):
            for spine_index, spine in enumerate(spines):
                links.append(
                    SpineLink(
                        fabric=fabric,
                        leaf=leaf.qualified_name,
                        leaf_port=leaf.reserved_uplinks[spine_index],
                        spine=spine,
                        spine_port=f"E1/{leaf_index}",
                    )
                )
        result[fabric] = ComposedFabric(fabric, spines, tuple(links))
    return result


def leaf_projections_from_inventory(
    devices: list[dict],
    interfaces: list[dict],
    *,
    domain: str,
    fabrics: set[str],
    reserved_uplink_ports: tuple[str, ...] = tuple(f"E1/{port}" for port in range(33, 65)),
) -> list[LeafProjection]:
    """Extract composable leaf projections from a plan-inventory JSON document.

    Only server-leaf devices in the requested shared fabrics participate.  The
    caller deliberately excludes OPG-local fabrics such as storage and
    converged management.  Reserved uplinks must exist as physical inventory
    interfaces even though a leaf-only OPG projection has no cable on them.
    """
    device_fields = {
        item["name"]: item.get("custom_field_data") or {}
        for item in devices
    }
    interface_names: dict[str, set[str]] = defaultdict(set)
    for interface in interfaces:
        interface_names[interface["device_name"]].add(interface["name"])

    leaves = []
    for device_name, fields in device_fields.items():
        if fields.get("hedgehog_role") != "server-leaf":
            continue
        fabric = fields.get("hedgehog_fabric")
        if fabric not in fabrics:
            continue
        available = interface_names[device_name]
        uplinks = tuple(port for port in reserved_uplink_ports if port in available)
        leaves.append(LeafProjection(domain, device_name, fabric, uplinks))
    return sorted(leaves, key=lambda leaf: leaf.qualified_name)


def compose_xoc3712(
    opg512_devices: list[dict],
    opg512_interfaces: list[dict],
    opg640_devices: list[dict],
    opg640_interfaces: list[dict],
) -> dict[str, ComposedFabric]:
    """Compose the approved six-OPG-512 plus one-OPG-640 XOC-3712 topology."""
    leaves = []
    for index in range(1, 7):
        leaves.extend(leaf_projections_from_inventory(
            opg512_devices, opg512_interfaces,
            domain=f"opg512-{index}", fabrics=XOC3712_SHARED_FABRICS,
        ))
    leaves.extend(leaf_projections_from_inventory(
        opg640_devices, opg640_interfaces,
        domain="opg640", fabrics=XOC3712_SHARED_FABRICS,
    ))
    fabrics = compose_shared_spines(leaves)
    expected_leaf_counts = {"frontend": 14, "backend-plane-a": 51, "backend-plane-b": 51}
    actual_leaf_counts = {name: len(fabric.links) // 32 for name, fabric in fabrics.items()}
    if actual_leaf_counts != expected_leaf_counts:
        raise CompositionError(
            f"XOC-3712 leaf counts must be {expected_leaf_counts}, found {actual_leaf_counts}"
        )
    return fabrics


def compose_wiring_documents(domains, *, fabric, spine_count=32):
    """Replace projection-local spines with a namespaced shared spine tier.

    ``domains`` is an ordered iterable of ``(domain, YAML-documents)`` for one
    fabric.  The documents are the existing per-fabric HNP exports.
    """
    namespace_docs, body, leaves = [], [], []
    for domain, documents in domains:
        device_names = set()
        for doc in documents:
            if doc.get("kind") in {"VLANNamespace", "IPv4Namespace"}:
                if not any(existing.get("kind") == doc.get("kind") for existing in namespace_docs):
                    namespace_docs.append(deepcopy(doc))
                continue
            item = deepcopy(doc)
            metadata = item.get("metadata", {})
            original = metadata.get("name", "")
            kind = item.get("kind")
            if kind == "Switch" and item.get("spec", {}).get("role") == "spine":
                continue
            if kind == "Connection" and "fabric" in item.get("spec", {}):
                continue
            if kind in {"Switch", "Server"}:
                device_names.add(original)
                metadata["name"] = f"{domain}--{original}"
                if kind == "Switch":
                    item["spec"]["boot"]["mac"] = _composition_mac(metadata["name"])
                    leaves.append((metadata["name"], item))
            elif kind == "Connection":
                metadata["name"] = f"{domain}--{original}"
                _namespace_connection_ports(item, device_names, domain)
            body.append(item)

    spines = []
    fabric_links = []
    ordered_leaves = sorted(name for name, _ in leaves)
    for spine_index in range(1, spine_count + 1):
        spine = f"xoc3712--{fabric}--spine-{spine_index:02d}"
        spines.append({"apiVersion": "wiring.githedgehog.com/v1beta1", "kind": "Switch",
            "metadata": {"name": spine, "namespace": "default"},
            "spec": {"role": "spine", "profile": "celestica-ds5000", "boot": {"mac": _composition_mac(spine)},
                     "portBreakouts": {f"E1/{port}": "1x800G" for port in range(1, 65)}}})
        for leaf_index, leaf in enumerate(ordered_leaves, start=1):
            fabric_links.append({"apiVersion": "wiring.githedgehog.com/v1beta1", "kind": "Connection",
                "metadata": {"name": f"{spine}-fabric-{leaf}", "namespace": "default"},
                "spec": {"fabric": {"links": [{
                    "leaf": {"port": f"{leaf}/E1/{32 + spine_index}"},
                    "spine": {"port": f"{spine}/E1/{leaf_index}"},
                }]}}})
    return namespace_docs + body + spines + fabric_links


def _composition_mac(name):
    digest = hashlib.sha256(name.encode()).digest()
    return ":".join(f"{byte:02x}" for byte in bytes([0x02]) + digest[:5])


def _namespace_connection_ports(document, device_names, domain):
    def update(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "port" and isinstance(child, str) and "/" in child:
                    device, port = child.split("/", 1)
                    if device in device_names:
                        value[key] = f"{domain}--{device}/{port}"
                else:
                    update(child)
        elif isinstance(value, list):
            for child in value:
                update(child)
    update(document.get("spec", {}))
