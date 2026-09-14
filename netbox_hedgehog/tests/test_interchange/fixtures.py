"""Controlled interchange fixtures for the #673 RED suite.

Fixtures are built in code rather than read from files so a perturbation can
target exactly one fact class, which is what the comparator's mutation controls
require. Serialized YAML/JSON text is derived from these structures.
"""

from __future__ import annotations

import copy
import json

from netbox_hedgehog.tests.corpus.interchange_model import content_integrity_binding

API_VERSION = "aid.hedgehog.com/v1"
SCHEMA_VERSION = "1.0"

PUBLISHER = "com.hedgehog.aid"
CATALOG_PUBLISHER = "com.celestica.catalog"

#: The catalog content a binding is computed over. Kept inside the restricted
#: profile: integers only, no floats.
CATALOG_CONTENT = {
    "deviceType": "ds5000",
    "portCount": 64,
    "portType": "osfp",
    "breakouts": ["b_1x800", "b_2x400", "b_4x200", "b_8x100"],
}


def catalog_version(slug: str = "ds5000", version: str = "3") -> dict:
    return {
        "apiVersion": API_VERSION,
        "kind": "CatalogVersion",
        "schemaVersion": SCHEMA_VERSION,
        "identity": {"namespace": CATALOG_PUBLISHER, "slug": slug},
        "version": version,
        "catalogContent": copy.deepcopy(CATALOG_CONTENT),
        "maturity": "published",
        "provenance": {"exporter": "hnp-test", "sourceRevision": "r1"},
    }


def catalog_reference(slug: str = "ds5000", version: str = "3",
                      content: dict | None = None) -> dict:
    return {
        "identity": {"namespace": CATALOG_PUBLISHER, "slug": slug},
        "version": version,
        "contentIntegrity": content_integrity_binding(
            CATALOG_CONTENT if content is None else content),
    }


def design_revision(slug: str = "xoc64-mesh") -> dict:
    parent = {"namespace": PUBLISHER, "slug": slug}
    return {
        "apiVersion": API_VERSION,
        "kind": "DesignRevision",
        "schemaVersion": SCHEMA_VERSION,
        "identity": dict(parent),
        "revision": "1",
        "catalogRefs": [catalog_reference()],
        "assumptions": [{"id": "a1", "statement": "air-cooled racks"}],
        "maturity": "draft",
        "provenance": {"exporter": "hnp-test", "sourceRevision": "r1",
                       "schemaVersion": SCHEMA_VERSION},
        "topology": {
            "fabrics": [{
                "name": "frontend",
                "family": "mesh",
                "switchClasses": [{
                    # Child identity is a parent-qualified local slug.
                    "identity": {"parent": dict(parent), "slug": "fe-leaf"},
                    "role": "server-leaf",
                    "quantity": 4,
                    "uplinkPorts": 8,
                    "zones": [{
                        "identity": {"parent": dict(parent), "slug": "fe-leaf-servers"},
                        "breakoutParent": "E1/1",
                        "lane": 0,
                    }],
                }],
            }],
            "connections": [{
                "kind": "Connection",
                "left": {"device": "fe-leaf-01", "interface": "E1/1/1",
                         "physical_parent": "E1/1", "lane": 0, "is_breakout": True},
                "right": {"device": "srv-01", "interface": "fe-p0"},
            }, {
                "kind": "Connection",
                "left": {"device": "fe-leaf-01", "interface": "E1/1/2",
                         "physical_parent": "E1/1", "lane": 1, "is_breakout": True},
                "right": {"device": "srv-02", "interface": "fe-p0"},
            }],
        },
    }


def _switch_class(parent: dict, slug: str, role: str, quantity: int,
                  uplink_ports: int = 0, zones=None) -> dict:
    return {
        "identity": {"parent": dict(parent), "slug": slug},
        "role": role,
        "quantity": quantity,
        "uplinkPorts": uplink_ports,
        "zones": zones if zones is not None else [],
    }


def design_revision_for_family(family: str, slug: str | None = None) -> dict:
    """A FAMILY-COMPLETE design revision.

    Flipping the `family` string on the mesh fixture would have asked a future
    implementation to accept under-specified intent -- a Clos with no spine
    domain, or an unbounded single switch. #661 requires a non-vacuous spine
    domain for Clos and an explicit capacity bound for a single switch, so each
    family gets intent that is actually valid for it.
    """
    slug = slug or f"xoc64-{family}"
    revision = design_revision(slug)
    parent = {"namespace": PUBLISHER, "slug": slug}
    fabric = revision["topology"]["fabrics"][0]
    fabric["family"] = family

    if family == "mesh":
        pass  # leaf-only is valid for mesh
    elif family == "clos":
        # Non-vacuous spine domain: S >= 2 (#661 F2).
        fabric["switchClasses"][0]["uplinkPorts"] = 8
        fabric["switchClasses"].append(
            _switch_class(parent, "fe-spine", "spine", quantity=2))
        fabric["spineDomain"] = {"spineClass": "fe-spine", "spineCount": 2}
    elif family == "single-switch":
        # Explicitly capacity-bounded, not merely "one switch".
        fabric["switchClasses"] = [
            _switch_class(parent, "fe-only", "server-leaf", quantity=1,
                          zones=[{
                              "identity": {"parent": dict(parent),
                                           "slug": "fe-only-servers"},
                              "breakoutParent": "E1/1",
                              "lane": 0,
                          }])
        ]
        fabric["capacityBound"] = {"maxServerPorts": 48, "declared": True}
    else:
        raise ValueError(f"no complete fixture for family {family!r}")
    return revision


def bundle_for_family(family: str) -> dict:
    return bundle(catalog_version(), design_revision_for_family(family))


#: Family-complete positives, and the intent shapes that must NOT be accepted.
VALID_FAMILIES = ("mesh", "clos", "single-switch")

INVALID_FAMILY_INTENT = {
    "clos with no spine class": lambda d: (
        d["topology"]["fabrics"][0].__setitem__("family", "clos")),
    "clos with one spine": lambda d: _set_spine_count(d, 1),
    "clos with zero spines": lambda d: _set_spine_count(d, 0),
    "single-switch without a capacity bound": lambda d: (
        d["topology"]["fabrics"][0].pop("capacityBound", None)
        or d["topology"]["fabrics"][0].__setitem__("family", "single-switch")),
}


def _set_spine_count(revision: dict, count: int) -> None:
    fabric = revision["topology"]["fabrics"][0]
    fabric["family"] = "clos"
    parent = revision["identity"]
    fabric["switchClasses"] = [
        c for c in fabric["switchClasses"] if c.get("role") != "spine"]
    if count:
        fabric["switchClasses"].append(
            _switch_class(parent, "fe-spine", "spine", quantity=count))
    fabric["spineDomain"] = {"spineClass": "fe-spine", "spineCount": count}


def bundle(*objects) -> dict:
    members = list(objects) or [catalog_version(), design_revision()]
    return {
        "apiVersion": API_VERSION,
        "kind": "Bundle",
        "schemaVersion": SCHEMA_VERSION,
        "manifest": {
            "objects": [
                {"kind": obj["kind"], "identity": copy.deepcopy(obj["identity"])}
                for obj in members
            ],
            "provenance": {"exporter": "hnp-test"},
        },
        "objects": members,
    }


def valid_bundle() -> dict:
    return bundle()


def to_json(document: dict) -> str:
    return json.dumps(document, indent=2)


def to_yaml(document: dict) -> str:
    """Serialize with PyYAML if present, else a JSON subset (valid YAML)."""
    try:
        import yaml
    except ImportError:  # pragma: no cover - PyYAML ships with NetBox
        return to_json(document)
    return yaml.safe_dump(document, sort_keys=False, default_flow_style=False)


#: Perturbations: fact class -> (label, callable mutating a bundle in place).
#: Exactly one fact class per entry, which is what makes the control specific.
def _p_envelope(doc):
    doc["objects"][1]["schemaVersion"] = "9.9"


def _p_identity(doc):
    doc["objects"][1]["identity"]["slug"] = "xoc64-mesh-renamed"


def _p_catalog_reference(doc):
    doc["objects"][1]["catalogRefs"][0]["version"] = "4"


def _p_content_integrity(doc):
    doc["objects"][1]["catalogRefs"][0]["contentIntegrity"]["digest"] = "0" * 64


def _p_assumption(doc):
    doc["objects"][1]["assumptions"][0]["statement"] = "liquid-cooled racks"


def _p_maturity(doc):
    doc["objects"][1]["maturity"] = "approved"


def _p_provenance(doc):
    doc["objects"][1]["provenance"]["exporter"] = "other-exporter"


def _p_extension(doc):
    doc["objects"][1]["extensions"] = {"com.example.ext/v1": {"note": "hello"}}


def _p_bundle_manifest(doc):
    doc["manifest"]["provenance"]["exporter"] = "other-exporter"


def _p_catalog_content(doc):
    # Alters PUBLISHED catalog content while leaving the design's reference
    # binding untouched -- invisible until catalog_content became a fact class.
    doc["objects"][0]["catalogContent"]["portCount"] = 32


def _p_topology(doc):
    doc["objects"][1]["topology"]["fabrics"][0]["switchClasses"][0]["quantity"] = 5


def _p_topology_edge(doc):
    """A connection-level change, which the T1 subset must also see."""
    doc["objects"][1]["topology"]["connections"][0]["right"]["device"] = "srv-99"


PERTURBATIONS = {
    "envelope": ("schemaVersion changed", _p_envelope),
    "identity": ("design revision slug renamed", _p_identity),
    "catalog_reference": ("catalog version pin changed", _p_catalog_reference),
    "content_integrity": ("content-integrity digest changed", _p_content_integrity),
    "assumption": ("assumption statement changed", _p_assumption),
    "maturity": ("maturity raised draft->approved", _p_maturity),
    "provenance": ("exporter changed", _p_provenance),
    "extension": ("unregistered extension namespace added", _p_extension),
    "topology": ("switch-class quantity changed", _p_topology),
    "bundle_manifest": ("bundle manifest provenance changed", _p_bundle_manifest),
    "catalog_content": ("published catalog content changed, binding untouched",
                        _p_catalog_content),
}

#: (label, callable) pairs that REMOVE a required field. Absence must be
#: unmeasured, never equal -- both sides extracting None is not agreement.
REQUIRED_FIELD_REMOVALS = {
    "bundle.manifest": lambda d: d.pop("manifest"),
    "bundle.objects": lambda d: d.pop("objects"),
    "CatalogVersion.catalogContent": lambda d: d["objects"][0].pop("catalogContent"),
    "CatalogVersion.version": lambda d: d["objects"][0].pop("version"),
    "CatalogVersion.identity": lambda d: d["objects"][0].pop("identity"),
    "DesignRevision.revision": lambda d: d["objects"][1].pop("revision"),
    "DesignRevision.catalogRefs": lambda d: d["objects"][1].pop("catalogRefs"),
    "DesignRevision.topology": lambda d: d["objects"][1].pop("topology"),
}


def without_required_field(name: str) -> dict:
    document = valid_bundle()
    REQUIRED_FIELD_REMOVALS[name](document)
    return document


#: Identity values that violate the accepted reverse-DNS + lowercase-slug rule.
MALFORMED_IDENTITIES = {
    "namespace not reverse-DNS": {"namespace": "hedgehog", "slug": "plan-a"},
    "uppercase namespace": {"namespace": "Com.Hedgehog.Aid", "slug": "plan-a"},
    "uppercase slug": {"namespace": PUBLISHER, "slug": "Plan-A"},
    "slug with underscore": {"namespace": PUBLISHER, "slug": "plan_a"},
    "display-name identity": {"name": "Plan A"},
    "child without parent qualification": {"slug": "fe-leaf"},
}


def with_identity(identity: dict) -> dict:
    document = valid_bundle()
    document["objects"][1]["identity"] = identity
    return document


def perturbed(fact_class: str) -> dict:
    """Return a copy of the valid bundle with exactly one fact class changed."""
    document = valid_bundle()
    PERTURBATIONS[fact_class][1](document)
    return document
