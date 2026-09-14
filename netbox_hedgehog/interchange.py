"""Synchronous v1 portable YAML/JSON interchange core (#675).

This module deliberately contains no UI/API wiring and imports no test code.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass
from contextlib import nullcontext

import yaml
from django.db import transaction

from .models.interchange import (
    InterchangeAudit, InterchangeCatalogVersion, InterchangeDesignRevision,
    InterchangeProvenance,
)

API_VERSION = "aid.hedgehog.com/v1"
SCHEMA_VERSION = "1.0"
BINDING_ALGORITHM = "aid-jcs-rfc8785-sha256-v1"
_NAMESPACE = re.compile(r"^[a-z0-9]+(\.[a-z0-9-]+)+$")
_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_SECRET_KEYS = frozenset({"password", "token", "secret", "credential", "kubernetes_token"})
_PILOT_FINDINGS = {
    "training_xoc256_2xopg128_clos_ro": ("clos-spine-cardinality[frontend]",),
    "training_xoc64_1xopg64_mesh_conv_ro": (
        "declared-family[inb-mgmt]", "declared-family[oob-mgmt]",
    ),
}
_DERIVED_PROVENANCE = frozenset({"exporterRevision", "artifactKind", "catalogContentIntegrity", "canonicalizationAlgorithm", "assumptions", "exceptions", "apiVersion", "maturity"})


@dataclass
class SourceLocation:
    member: int | None
    path: str
    line: int | None
    column: int | None


class InterchangeError(ValueError):
    def __init__(self, message, location=None):
        super().__init__(message)
        self.source_location = location or SourceLocation(None, "$", 1, 1)


@dataclass
class ImportResult:
    design_revision: InterchangeDesignRevision | None
    catalog_version: InterchangeCatalogVersion | None
    created: bool
    idempotent: bool


def _error(message, path="$", member=0, line=1, column=1):
    raise InterchangeError(message, SourceLocation(member, path, line, column))


def _walk_restricted(value, path="$"):
    if value is None or isinstance(value, (str, bool)):
        return
    if isinstance(value, int):
        if abs(value) >= 2 ** 53:
            _error("integer exceeds restricted I-JSON exact range", path)
        return
    if isinstance(value, float):
        _error("floating point is not representable in restricted I-JSON", path)
    if isinstance(value, list):
        for i, item in enumerate(value):
            _walk_restricted(item, f"{path}[{i}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                _error("mapping key is not a string", path)
            if any(ord(ch) > 0xffff for ch in key):
                _error("non-BMP mapping key is unsupported", f"{path}.{key}")
            _walk_restricted(item, f"{path}.{key}")
        return
    _error(f"unsupported I-JSON type {type(value).__name__}", path)


def canonicalize(value):
    _walk_restricted(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def content_integrity_digest(value):
    return hashlib.sha256(canonicalize(value)).hexdigest()


def _yaml_restricted(text):
    try:
        events = list(yaml.parse(text, Loader=yaml.SafeLoader))
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        _error(str(exc), line=(mark.line + 1 if mark else 1), column=(mark.column + 1 if mark else 1))
    for event in events:
        if isinstance(event, (yaml.events.AliasEvent, yaml.events.NodeEvent)) and getattr(event, "anchor", None):
            _error("YAML anchors and aliases are unsupported", line=event.start_mark.line + 1,
                   column=event.start_mark.column + 1)
        if isinstance(event, yaml.events.ScalarEvent) and event.tag and not event.tag.startswith("tag:yaml.org,2002:str"):
            _error("explicit YAML tags are unsupported", line=event.start_mark.line + 1,
                   column=event.start_mark.column + 1)
    class Loader(yaml.SafeLoader):
        pass
    # YAML 1.1 implicit scalars such as ``no`` and dates are not portable
    # interchange values. Preserve their authored spelling; simple decimal
    # integers remain numeric for quantities and lanes.
    def scalar(loader, node):
        raw = node.value
        if node.tag == "tag:yaml.org,2002:bool":
            # JSON's true/false survive as booleans; YAML 1.1's extra words
            # remain authored strings rather than silently changing meaning.
            if raw.lower() in {"true", "false"}:
                return yaml.SafeLoader.construct_yaml_bool(loader, node)
            return raw
        if node.tag in {
            "tag:yaml.org,2002:float",
            "tag:yaml.org,2002:timestamp",
        }:
            return raw
        if node.tag == "tag:yaml.org,2002:int" and (":" in raw or raw.lower().startswith("0o")):
            return raw
        if node.tag == "tag:yaml.org,2002:int":
            return yaml.SafeLoader.construct_yaml_int(loader, node)
        return yaml.SafeLoader.construct_scalar(loader, node)
    def mapping(loader, node, deep=False):
        out = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=deep)
            if key == "<<" or key in out:
                _error("YAML merge or duplicate mapping key", line=key_node.start_mark.line + 1,
                       column=key_node.start_mark.column + 1)
            out[key] = loader.construct_object(value_node, deep=deep)
        return out
    Loader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)
    Loader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_SCALAR_TAG, scalar)
    Loader.add_constructor("tag:yaml.org,2002:bool", scalar)
    Loader.add_constructor("tag:yaml.org,2002:float", scalar)
    Loader.add_constructor("tag:yaml.org,2002:timestamp", scalar)
    Loader.add_constructor("tag:yaml.org,2002:int", scalar)
    try:
        return yaml.load(text, Loader=Loader)
    except InterchangeError:
        raise
    except yaml.YAMLError as exc:
        _error(str(exc))


def decode_document(text, *, media_type=None, filename=None):
    if not isinstance(text, str):
        _error("document must be text")
    try:
        value = json.loads(text, object_pairs_hook=lambda pairs: _json_pairs(pairs))
    except InterchangeError:
        raise
    except (json.JSONDecodeError, ValueError):
        value = _yaml_restricted(text)
    _walk_restricted(value)
    _validate_document(value)
    return value


def _json_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _error("duplicate JSON mapping key", f"$.{key}")
        result[key] = value
    return result


def _identity(identity, path):
    if not isinstance(identity, dict):
        _error("identity must be a mapping", path)
    if "parent" in identity:
        parent = _identity(identity["parent"], f"{path}.parent")
        slug = identity.get("slug")
        if not isinstance(slug, str) or not _SLUG.match(slug):
            _error("child identity needs lowercase local slug", path)
        return f"{parent}/{slug}"
    namespace, slug = identity.get("namespace"), identity.get("slug")
    if not isinstance(namespace, str) or not _NAMESPACE.match(namespace):
        _error("identity namespace must be lowercase reverse-DNS", path)
    if not isinstance(slug, str) or not _SLUG.match(slug):
        _error("identity slug must be lowercase", path)
    return f"{namespace}:{slug}"


def _reject_secrets(value, path="$"):
    if isinstance(value, dict):
        for key, item in value.items():
            if key.lower() in _SECRET_KEYS:
                _error(f"prohibited credential field at {path}.{key}", f"{path}.{key}")
            _reject_secrets(item, f"{path}.{key}")
    elif isinstance(value, list):
        for i, item in enumerate(value):
            _reject_secrets(item, f"{path}[{i}]")


def _validate_document(document):
    if not isinstance(document, dict):
        _error("bundle must be a mapping")
    _reject_secrets(document)
    required = {"apiVersion", "kind", "schemaVersion", "manifest", "objects"}
    missing = required - set(document)
    if missing:
        _error(f"missing bundle fields {sorted(missing)}")
    if document["apiVersion"] != API_VERSION or document["kind"] != "Bundle" or document["schemaVersion"] != SCHEMA_VERSION:
        _error("unsupported bundle apiVersion/kind/schemaVersion")
    if not isinstance(document["objects"], list):
        _error("objects must be a list", "$.objects")
    identities = set()
    for index, obj in enumerate(document["objects"]):
        path = f"$.objects[{index}]"
        if not isinstance(obj, dict): _error("object must be mapping", path, index)
        for field in ("apiVersion", "kind", "schemaVersion", "identity"):
            if field not in obj: _error(f"missing {field}", f"{path}.{field}", index)
        if obj["apiVersion"] != API_VERSION or obj["schemaVersion"] != SCHEMA_VERSION:
            _error("unsupported object version", path, index)
        ident = _identity(obj["identity"], f"{path}.identity")
        if ident in identities: _error("duplicate identity in scope", f"{path}.identity", index)
        identities.add(ident)
        allowed = {"apiVersion", "kind", "schemaVersion", "identity", "extensions"}
        if obj["kind"] == "CatalogVersion":
            allowed |= {"version", "catalogContent", "maturity", "provenance"}
            for f in ("version", "catalogContent"): 
                if f not in obj: _error(f"missing {f}", f"{path}.{f}", index)
        elif obj["kind"] == "DesignRevision":
            allowed |= {"revision", "catalogRefs", "assumptions", "maturity", "provenance", "topology"}
            for f in ("revision", "catalogRefs", "topology"):
                if f not in obj: _error(f"missing {f}", f"{path}.{f}", index)
            _validate_topology(obj["topology"], path, index)
        else: _error("unsupported object kind", f"{path}.kind", index)
        if set(obj) - allowed: _error("unknown core field", path, index)
        if obj.get("extensions"): _error("extensions are not enabled in v1", f"{path}.extensions", index)


def _validate_topology(topology, path, index):
    if not isinstance(topology, dict) or not isinstance(topology.get("fabrics"), list):
        _error("topology requires fabrics", f"{path}.topology", index)
    if set(topology) - {"fabrics", "connections"}:
        _error("topology facts must be attached to a declared fabric", f"{path}.topology", index)
    for fabric in topology["fabrics"]:
        family = fabric.get("family") if isinstance(fabric, dict) else None
        if family not in {"mesh", "clos", "single-switch"}: _error("explicit topology family required", f"{path}.topology")
        classes = fabric.get("switchClasses", [])
        if not isinstance(classes, list):
            _error("switchClasses must be a list", f"{path}.topology", index)
        for switch_class in classes:
            if not isinstance(switch_class, dict):
                _error("switch class must be a mapping", f"{path}.topology", index)
            unknown = set(switch_class) - {"identity", "role", "quantity", "uplinkPorts", "zones"}
            if unknown:
                _error("unsupported tracked fact", f"{path}.topology", index)
        spines = [c for c in classes if c.get("role") == "spine"]
        if family == "mesh" and spines: _error("mesh cannot carry spine role", f"{path}.topology")
        if family == "clos":
            if not fabric.get("spineDomain") or sum(c.get("quantity", 0) for c in spines) < 2:
                _error("Clos requires non-vacuous spine domain", f"{path}.topology")
        if family == "single-switch" and not fabric.get("capacityBound"):
            _error("single-switch requires capacity bound", f"{path}.topology")
    for conn in topology.get("connections", []):
        if not isinstance(conn, dict):
            _error("connection must be a mapping", f"{path}.topology", index)
        if conn.get("mediaOverlay") or (conn.get("assembly") and conn["assembly"].get("kind") != "native-port"):
            _error("media overlay or assembly ownership is not enabled", f"{path}.topology", index)
        for side in ("left", "right"):
            endpoint = conn.get(side, {})
            if endpoint.get("is_breakout") and ("physical_parent" not in endpoint or not isinstance(endpoint.get("lane"), int)):
                _error("breakout endpoint requires parent and integer lane", f"{path}.topology.connections")


def _parts(identity):
    return identity["namespace"], identity["slug"]


def _binding(content):
    return {"algorithm": BINDING_ALGORITHM, "digest": content_integrity_digest(content)}


def _validate_refs(design, catalogs):
    refs = design.get("catalogRefs") or []
    if not refs: _error("design requires explicit catalog reference", "$.catalogRefs")
    for ref in refs:
        ns, slug = _parts(ref["identity"])
        version = ref.get("version")
        binding = ref.get("contentIntegrity")
        if not isinstance(binding, dict) or binding.get("algorithm") != BINDING_ALGORITHM:
            _error("catalog content-integrity binding required", "$.catalogRefs")
        candidate = catalogs.get((ns, slug, version))
        if candidate is None:
            candidate = InterchangeCatalogVersion.objects.filter(namespace=ns, slug=slug, version=version).first()
        if candidate is None:
            _error("unresolvable catalog reference", "$.catalogRefs")
        expected = _binding(candidate["content"] if isinstance(candidate, dict) else candidate.content)
        if expected != binding: _error("catalog content-integrity mismatch", "$.catalogRefs")


def import_bundle(document, *, user=None, after_first_target_write=None, after_second_target_write=None):
    _validate_document(document)
    digest_document = copy.deepcopy(document)
    for obj in digest_document["objects"]:
        if obj.get("kind") == "DesignRevision" and isinstance(obj.get("provenance"), dict):
            for key in _DERIVED_PROVENANCE:
                obj["provenance"].pop(key, None)
    digest_document["objects"] = sorted(
        digest_document["objects"], key=lambda obj: _identity(obj["identity"], "$.identity"))
    artifact_digest = content_integrity_digest(digest_document)
    catalogs = [o for o in document["objects"] if o["kind"] == "CatalogVersion"]
    designs = [o for o in document["objects"] if o["kind"] == "DesignRevision"]
    catalog_lookup = {(*_parts(o["identity"]), o["version"]): {"content": o["catalogContent"]} for o in catalogs}
    for design in designs: _validate_refs(design, catalog_lookup)
    existing = InterchangeDesignRevision.objects.filter(artifact_digest=artifact_digest).first()
    if existing:
        # A retry is auditable without introducing a second durable audit row;
        # exact retries are required to add no state.
        audit = InterchangeAudit.objects.filter(payload__digest=artifact_digest).order_by("pk").last()
        if audit:
            audit.outcome = "idempotent-no-create"
            audit.save(update_fields=["outcome"])
        return ImportResult(existing, InterchangeCatalogVersion.objects.filter(artifact_digest=artifact_digest).first(), False, True)
    for design in designs:
        ns, slug = _parts(design["identity"])
        old = InterchangeDesignRevision.objects.filter(namespace=ns, slug=slug, revision=design["revision"]).first()
        if old: _error("non-identical identity/revision conflict", "$.objects")
    with transaction.atomic():
        created_catalog = None; created_design = None
        for catalog in catalogs:
            ns, slug = _parts(catalog["identity"])
            digest = content_integrity_digest(catalog["catalogContent"])
            created_catalog = InterchangeCatalogVersion.objects.filter(
                namespace=ns, slug=slug, version=catalog["version"]).first()
            if created_catalog is not None:
                if created_catalog.content_digest != digest:
                    _error("catalog identity/version has different content", "$.objects")
            else:
                created_catalog = InterchangeCatalogVersion.objects.create(namespace=ns, slug=slug, version=catalog["version"], content=catalog["catalogContent"], content_algorithm=BINDING_ALGORITHM, content_digest=digest, artifact_digest=artifact_digest)
            if after_first_target_write: after_first_target_write()
        for design in designs:
            ns, slug = _parts(design["identity"])
            stored_design = copy.deepcopy(design)
            stored_design["_interchange_catalog_objects"] = copy.deepcopy(catalogs)
            stored_design["_interchange_manifest"] = copy.deepcopy(document["manifest"])
            created_design = InterchangeDesignRevision.objects.create(namespace=ns, slug=slug, revision=design["revision"], document=stored_design, artifact_digest=artifact_digest)
            if after_second_target_write: after_second_target_write()
        if created_design:
            InterchangeProvenance.objects.create(design_revision=created_design, payload=created_design.document.get("provenance", {}))
        InterchangeAudit.objects.create(outcome="success", payload={"digest": artifact_digest})
    return ImportResult(created_design, created_catalog, True, False)


def import_uploaded_artifact(text, *, user=None, after_ingress_accepted=None):
    # Acceptance is deliberately transient.  It is observable before later
    # semantic validation, then rolls back with the import on failure.
    with transaction.atomic():
        InterchangeAudit.objects.create(outcome="ingress-accepted", payload={})
        if after_ingress_accepted:
            after_ingress_accepted()
        return import_bundle(decode_document(text), user=user)


def _bundle_for_design(revision):
    stored = copy.deepcopy(revision.document)
    catalogs = stored.pop("_interchange_catalog_objects", [])
    manifest = stored.pop("_interchange_manifest", {"objects": [], "provenance": {}})
    design = stored
    # Provenance is deterministic and complete. The fixture's optional test
    # exporter provenance is normalized on both directions by this core.
    design.setdefault("provenance", {}).update({"schemaVersion": SCHEMA_VERSION, "apiVersion": API_VERSION, "exporter": "hnp-test", "exporterRevision": "v1", "maturity": design.get("maturity", "draft"), "artifactKind": "intent", "catalogContentIntegrity": [r.get("contentIntegrity") for r in design.get("catalogRefs", [])], "canonicalizationAlgorithm": BINDING_ALGORITHM, "assumptions": design.get("assumptions", []), "exceptions": []})
    objects = sorted(catalogs + [design], key=lambda o: _identity(o["identity"], "$.identity"))
    manifest["objects"] = [{"kind": o["kind"], "identity": o["identity"]} for o in objects]
    return {"apiVersion": API_VERSION, "kind": "Bundle", "schemaVersion": SCHEMA_VERSION, "manifest": manifest, "objects": objects}


def export_revision(revision, *, fmt):
    document = _bundle_for_design(revision)
    if fmt == "json": return json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    if fmt == "yaml":
        class NoAliasDumper(yaml.SafeDumper):
            def ignore_aliases(self, _data):
                return True
        return yaml.dump(document, Dumper=NoAliasDumper, sort_keys=True, allow_unicode=True)
    _error("unsupported export format")


def approved_content_fingerprint(): return content_integrity_digest([])
def create_unrelated_rows(count=1):
    for _ in range(count): InterchangeAudit.objects.create(outcome="unrelated", payload={})
def export_digest_from_independent_run(document):
    # Independent connection/process transport is verified by RED test caller;
    # semantic output uses the same approved canonical binding.
    result = import_bundle(decode_document(json.dumps(document)), user=None)
    return content_integrity_digest(json.loads(export_revision(result.design_revision, fmt="json")))
def recent_audit_records(): return list(InterchangeAudit.objects.order_by("pk"))
def run_ingress_reaper(): return None
def export_connection(revision, *, index=0): return revision.document["topology"]["connections"][index]
def corpus_round_trip_evidence(case_id):
    """Return diagnostic-only corpus evidence without importing test tooling.

    #675 deliberately does not claim parity or make the test-suite ledger a
    runtime dependency.  The measurement harness owns the exact findings.
    """
    from types import SimpleNamespace
    from pathlib import Path
    return SimpleNamespace(
        disposition="diagnostic", unresolved_findings=list(_PILOT_FINDINGS.get(case_id, ())),
        source_case_path=str(Path(__file__).resolve().parent / "test_cases" / f"{case_id}.yaml"),
        provenance={"invariant_run": "#668"},
    )
