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
        },
    }


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


def _p_topology(doc):
    doc["objects"][1]["topology"]["fabrics"][0]["switchClasses"][0]["quantity"] = 5


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
}


def perturbed(fact_class: str) -> dict:
    """Return a copy of the valid bundle with exactly one fact class changed."""
    document = valid_bundle()
    PERTURBATIONS[fact_class][1](document)
    return document
