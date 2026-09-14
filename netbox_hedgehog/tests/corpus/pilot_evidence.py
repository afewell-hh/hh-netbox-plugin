"""Test-only corpus-gate evidence for #677.

Replaces the deferred #673 I30 placeholder with REAL measurement: actual HNP
ingest and calculation, actual T2 invariant findings, an actual round trip
through the versioned interchange path, and a measured #620 C4 envelope.

Three rules keep this from becoming the stub it replaces:

1. **The candidate is produced, not copied.** The comparison candidate comes
   from exporting through `netbox_hedgehog.interchange` and reading the result
   back. Comparing a projection against itself is tautological and was the
   defect in the draft this supersedes.
2. **An unmeasured axis is recorded, never silently empty.** Absent edges are
   reported as unmeasured rather than compared as an empty set that trivially
   matches.
3. **The verdict is DIAGNOSTIC unless every requirement is met.** A failure of
   the interchange path is evidence about the corpus, not a harness error, and
   is recorded as such.

Nothing here claims AID/HNP parity, canonical-format selection, or seam
selection, and it never will while any recorded T2 finding is unresolved.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from django.db import connection

from netbox_hedgehog.tests.corpus.topology_graph import (
    ComparisonDisposition,
    ComparisonIdentity,
    ExportMode,
    GraphNode,
    NodePlacement,
    ProvenanceEnvelope,
    TopologyGraph,
    compare_graphs,
    validate_surrogate_contract,
)

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
CASE_DIR = PLUGIN_ROOT / "test_cases"

#: Recorded source digests. A drift makes a pilot STALE: its measurement no
#: longer describes the input it is recorded against.
PILOT_SOURCE_DIGESTS = {
    "training_xoc64_1xopg64_mesh_conv_ro":
        "b67b1e0455055569cccfd7e5462a3f34e83c8fa1d64887fbf246f60c1e3bd745",
    "training_xoc256_2xopg128_clos_ro":
        "f272e0d413ab5c66a307425c92e379cbfce0280bb14d0797e5e0df8511899c1b",
}

#: Axes this harness claims to compare. Each needs a deliberate mismatch
#: control; an axis that cannot be measured is reported, not dropped.
CLAIMED_AXES = ("nodes", "edges", "export_mode", "provenance",
                "interchange_round_trip", "surrogate_contract")

_SLUG_SAFE = re.compile(r"[^a-z0-9-]+")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _git_revision() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=PLUGIN_ROOT.parent, text=True,
            stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "unrecorded-revision"


def _migration_state() -> str:
    with connection.cursor() as cursor:
        cursor.execute("SELECT app, name FROM django_migrations ORDER BY app, name")
        return _sha256(json.dumps(cursor.fetchall(), separators=(",", ":")).encode())


def _catalog_fingerprint() -> str:
    from dcim.models import DeviceType
    rows = list(DeviceType.objects.order_by("manufacturer__slug", "model")
                .values_list("manufacturer__slug", "model", "slug"))
    return _sha256(json.dumps(rows, separators=(",", ":")).encode())


def measure_c4(case_path: Path, mode: ExportMode = ExportMode.FULL_PLAN) -> ProvenanceEnvelope:
    """Measure the #620 C4 envelope. Unknown values are left EMPTY so the
    envelope reports itself incomplete, rather than filled with a placeholder
    that would make an incomplete measurement look complete."""
    revision = _git_revision()
    return ProvenanceEnvelope({
        "source_hash": _sha256(case_path.read_bytes()),
        "source_revision": revision,
        "normalizer_version": "topology-graph-test/v1",
        "platform_image_digest": os.environ.get("HH_PLATFORM_IMAGE_DIGEST", ""),
        "platform_version": os.environ.get("HH_PLATFORM_VERSION", ""),
        "plugin_revision": revision,
        "migration_state": _migration_state(),
        "configuration_fingerprint": _sha256(
            Path(os.environ["HH_CORPUS_CONFIG_PATH"]).read_bytes())
        if os.environ.get("HH_CORPUS_CONFIG_PATH") else "",
        "reference_catalog_fingerprint": _catalog_fingerprint(),
        "database_state": "test-db:" + (connection.settings_dict.get("NAME") or ""),
        "runner_flags": os.environ.get("HH_CORPUS_RUNNER_FLAGS", ""),
        "export_mode": mode.value,
        "command": "manage.py test netbox_hedgehog.tests.test_topology_planning."
                   "test_real_corpus_gate",
    })


def _slug(value: str) -> str:
    return _SLUG_SAFE.sub("-", value.lower().replace("_", "-")).strip("-")


def classify_fabric(fabric_name: str):
    """Return (placement, surrogate) for a fabric, from the product's own rules.

    Modelling every node as MANAGED erased #620's surrogate/exclusion dimension:
    `validate_surrogate_contract` had nothing to check and reported clean, which
    reads as evidence of compliance when it was really evidence of nothing.
    """
    from netbox_hedgehog.choices import FabricTypeChoices

    if FabricTypeChoices.is_hedgehog_managed(fabric_name):
        return NodePlacement.MANAGED_FABRIC, False
    if FabricTypeChoices.is_surrogate_endpoint(fabric_name):
        return NodePlacement.UNMANAGED_FABRIC, True
    # in-band-mgmt / network-mgmt / legacy-oob: excluded from all CRDs, and
    # therefore expected to raise a #620 exclusion rather than pass silently.
    return NodePlacement.UNMANAGED_FABRIC, False


def plan_nodes(classes) -> list:
    nodes = []
    for item in classes:
        placement, surrogate = classify_fabric(item.fabric_name)
        # Normalised on BOTH sides. The interchange path returns slugified
        # identifiers, so projecting the reference with raw ids made every node
        # read as different -- a harness artifact reported as a real divergence.
        nodes.append(GraphNode(
            name=f"{item.fabric_name}:{_slug(item.switch_class_id)}",
            kind=str(item.hedgehog_role), placement=placement, surrogate=surrogate))
    return nodes


def build_bundle(case_id: str, classes) -> dict:
    """Project persisted HNP plan state into a versioned interchange bundle."""
    from netbox_hedgehog.interchange import API_VERSION, SCHEMA_VERSION, _binding

    namespace = "com.hedgehog.aid"
    slug = _slug(case_id)
    parent = {"namespace": namespace, "slug": slug}
    catalog_content = {"pilot": case_id, "classCount": len(classes)}
    catalog_identity = {"namespace": "com.hedgehog.catalog", "slug": f"{slug}-catalog"}

    fabrics: dict = {}
    for item in classes:
        fabric = fabrics.setdefault(item.fabric_name, {"name": item.fabric_name,
                                                       "switchClasses": []})
        quantity = (item.override_quantity if item.override_quantity is not None
                    else item.calculated_quantity)
        fabric["switchClasses"].append({
            "identity": {"parent": dict(parent), "slug": _slug(item.switch_class_id)},
            "role": str(item.hedgehog_role),
            "quantity": int(quantity or 0),
            "uplinkPorts": int(item.uplink_ports_per_switch or 0),
            "zones": [],
        })

    for item in classes:
        fabric = fabrics[item.fabric_name]
        spines = [c for c in fabric["switchClasses"] if c["role"] == "spine"]
        modes = {getattr(item, "topology_mode", None) for item in classes
                 if item.fabric_name == fabric["name"]}
        if spines:
            fabric["family"] = "clos"
            fabric["spineDomain"] = {
                "spineClass": spines[0]["identity"]["slug"],
                "spineCount": sum(c["quantity"] for c in spines),
            }
        elif "mesh" in modes:
            fabric["family"] = "mesh"
        else:
            fabric["family"] = "single-switch"
            fabric["capacityBound"] = {"declared": True}

    design = {
        "apiVersion": API_VERSION, "kind": "DesignRevision",
        "schemaVersion": SCHEMA_VERSION, "identity": dict(parent), "revision": "1",
        "catalogRefs": [{"identity": dict(catalog_identity), "version": "1",
                         "contentIntegrity": _binding(catalog_content)}],
        "assumptions": [], "maturity": "draft",
        "provenance": {"sourceRevision": "1", "schemaVersion": SCHEMA_VERSION},
        "topology": {"fabrics": sorted(fabrics.values(), key=lambda f: f["name"])},
    }
    catalog = {
        "apiVersion": API_VERSION, "kind": "CatalogVersion",
        "schemaVersion": SCHEMA_VERSION, "identity": dict(catalog_identity),
        "version": "1", "catalogContent": catalog_content, "maturity": "published",
        "provenance": {"sourceRevision": "1", "schemaVersion": SCHEMA_VERSION},
    }
    return {
        "apiVersion": API_VERSION, "kind": "Bundle", "schemaVersion": SCHEMA_VERSION,
        "manifest": {"objects": [{"kind": o["kind"], "identity": o["identity"]}
                                 for o in (catalog, design)],
                     "provenance": {"sourceRevision": "1",
                                    "schemaVersion": SCHEMA_VERSION}},
        "objects": [catalog, design],
    }


def interchange_round_trip(bundle: dict):
    """Export the bundle through the real interchange path and read it back.

    Returns (decoded_or_None, error_or_None). A failure is EVIDENCE about the
    corpus, not a harness error: a pilot whose persisted state cannot survive
    the versioned path is precisely what this gate exists to surface.
    """
    from netbox_hedgehog import interchange
    try:
        result = interchange.import_bundle(
            interchange.decode_document(json.dumps(bundle)), user=None)
        exported = interchange.export_revision(result.design_revision, fmt="json")
        return interchange.decode_document(exported), None
    except Exception as exc:  # noqa: BLE001 - the error IS the measurement
        return None, f"{type(exc).__name__}: {exc}"


def graph_from_bundle(decoded: dict, case_id: str, source: str,
                      provenance: ProvenanceEnvelope) -> TopologyGraph:
    nodes = []
    for obj in decoded.get("objects", []):
        if obj.get("kind") != "DesignRevision":
            continue
        for fabric in (obj.get("topology") or {}).get("fabrics", []):
            for switch_class in fabric.get("switchClasses", []):
                placement, surrogate = classify_fabric(str(fabric.get("name")))
                nodes.append(GraphNode(
                    name=f"{fabric.get('name')}:{switch_class['identity']['slug']}",
                    kind=str(switch_class.get("role")),
                    placement=placement, surrogate=surrogate))
    return TopologyGraph.from_records(
        ComparisonIdentity(case_id, ExportMode.FULL_PLAN, source), nodes, (), provenance)


@dataclass
class PilotEvidence:
    case_id: str
    disposition: ComparisonDisposition
    reasons: tuple = ()
    unmeasured_axes: tuple = ()
    t2_failures: tuple = ()
    stale: bool = False
    provenance_missing: tuple = ()
    t1_differences: dict = field(default_factory=dict)
    round_trip_error: str | None = None
    #: #620 surrogate/exclusion findings actually produced by the contract.
    exclusions: tuple = ()
    #: Which surrogate sub-dimensions were measured, and which were not.
    surrogate_dimensions: dict = field(default_factory=dict)

    @property
    def claims_parity(self) -> bool:
        """This harness never claims parity. Kept explicit so the answer is
        asserted rather than assumed."""
        return False


def evaluate(case_id: str, classes, t2_failures, provenance: ProvenanceEnvelope) -> PilotEvidence:
    """Derive the pilot's state from ACTUAL results."""
    case_path = CASE_DIR / f"{case_id}.yaml"
    reasons: list = []
    unmeasured: list = []

    stale = _sha256(case_path.read_bytes()) != PILOT_SOURCE_DIGESTS.get(case_id)
    if stale:
        reasons.append(
            f"{case_id}: source digest differs from the recorded baseline, so this "
            f"measurement no longer describes the input it is recorded against")

    reference = TopologyGraph.from_records(
        ComparisonIdentity(case_id, ExportMode.FULL_PLAN, "hnp-persisted-plan"),
        plan_nodes(classes), (), provenance)

    decoded, error = interchange_round_trip(build_bundle(case_id, classes))
    differences: dict = {}
    exclusions: tuple = ()
    if error is not None:
        reasons.append(f"{case_id}: interchange round trip failed -- {error}")
        # The surrogate contract is still evaluable on the reference alone; a
        # failed round trip must not silently drop that dimension too.
        exclusions = tuple(dict.fromkeys(validate_surrogate_contract(reference)))
    else:
        candidate = graph_from_bundle(decoded, case_id, "interchange-round-trip", provenance)
        report = compare_graphs(reference, candidate)
        differences = {k: v for k, v in report.differences.items()}
        # compare_graphs evaluates the contract on BOTH graphs, so an exclusion
        # present in each appears twice. Deduplicated, order preserved: two
        # sightings of one defect are one finding, and counting them twice
        # overstates the evidence.
        exclusions = tuple(dict.fromkeys(report.exclusions))
        if report.disposition is not ComparisonDisposition.EQUIVALENCE_ELIGIBLE:
            reasons.append(f"{case_id}: T1 comparison is {report.disposition.value}")

    # #620 surrogate/exclusion dimensions, reported as measured or unmeasured.
    # Node placement and surrogate status ARE derivable from persisted fabric
    # classification; the cabling-derived obligations are not, without
    # generation, and are recorded rather than treated as satisfied.
    surrogate_dimensions = {
        "node_placement_and_surrogate_status": "measured",
        "required_surrogate_set": "unmeasured: derived from cabling, which "
                                  "requires device generation",
        "forbidden_scoped_surrogate_set": "unmeasured: scoped-export obligation "
                                          "requires cabling",
        "surrogate_edge_rules": "unmeasured: no edges without generation",
    }
    for name, state in sorted(surrogate_dimensions.items()):
        if state.startswith("unmeasured"):
            unmeasured.append(f"surrogate/{name}: {state.split(': ', 1)[1]}")
            reasons.append(f"{case_id}: {unmeasured[-1]}")
    if exclusions:
        reasons.append(
            f"{case_id}: {len(exclusions)} #620 exclusion finding(s): "
            f"{list(exclusions)}")

    # Edges are not measured without device generation. Recorded rather than
    # compared as an empty set, which would trivially match.
    unmeasured.append(
        "edges: cable-level topology requires device generation, which this "
        "diagnostic tranche does not perform")
    reasons.append(f"{case_id}: {unmeasured[-1]}")

    missing = provenance.missing()
    if missing:
        reasons.append(f"{case_id}: C4 envelope incomplete -- missing {list(missing)}")
    if t2_failures:
        reasons.append(
            f"{case_id}: {len(t2_failures)} unresolved T2 finding(s) recorded against "
            f"this pilot; equivalence is not claimable until #671 resolves them")

    eligible = (not reasons and not stale and not unmeasured and not t2_failures
                and not missing and error is None and not differences
                and not exclusions)
    return PilotEvidence(
        case_id=case_id,
        disposition=(ComparisonDisposition.EQUIVALENCE_ELIGIBLE if eligible
                     else ComparisonDisposition.DIAGNOSTIC),
        reasons=tuple(reasons), unmeasured_axes=tuple(unmeasured),
        t2_failures=tuple(t2_failures), stale=stale,
        provenance_missing=tuple(missing), t1_differences=differences,
        round_trip_error=error, exclusions=exclusions,
        surrogate_dimensions=surrogate_dimensions,
    )
