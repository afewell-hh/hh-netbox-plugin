"""Synchronous v1 portable YAML/JSON interchange core (#675).

This module deliberately contains no UI/API wiring and imports no test code.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import time
from dataclasses import dataclass
from contextlib import nullcontext
from pathlib import Path

import yaml
from django.db import OperationalError, connection, transaction

from .models.interchange import (
    InterchangeAudit, InterchangeCatalogVersion, InterchangeDesignRevision,
    InterchangeProvenance,
)

API_VERSION = "aid.hedgehog.com/v1"
SCHEMA_VERSION = "1.0"
BINDING_ALGORITHM = "aid-jcs-rfc8785-sha256-v1"
EXPORTER_ID = "netbox-hedgehog"
_NAMESPACE = re.compile(r"^[a-z0-9]+(\.[a-z0-9-]+)+$")
_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_SECRET_KEYS = frozenset({"password", "token", "secret", "credential", "kubernetes_token"})
_DERIVED_PROVENANCE = frozenset({"exporter", "exporterRevision", "artifactKind", "catalogContentIntegrity", "canonicalizationAlgorithm", "assumptions", "exceptions", "apiVersion", "maturity"})


@dataclass
class SourceLocation:
    member: int | None
    # A decoded document key is untrusted input.  A location omits its path
    # rather than echoing a path built from such a key.
    path: str | None
    line: int | None
    column: int | None


class InterchangeError(ValueError):
    def __init__(self, message, location=None, *, code="invalid-document"):
        super().__init__(message)
        self.code = code
        self.source_location = location or SourceLocation(None, "$", 1, 1)


class OperationDeadlineExceeded(InterchangeError):
    """A synchronous UI operation exceeded its caller-provided deadline."""

    def __init__(self):
        ValueError.__init__(self, 'operation deadline exceeded')
        self.source_location = None


@dataclass
class ImportResult:
    design_revision: InterchangeDesignRevision | None
    catalog_version: InterchangeCatalogVersion | None
    created: bool
    idempotent: bool


def _error(message, path="$", member=0, line=1, column=1, *, code="invalid-document"):
    raise InterchangeError(message, SourceLocation(member, path, line, column), code=code)


def _yaml_error(mark=None):
    """Convert PyYAML failures at the decoder boundary without its raw text."""
    _error(
        "invalid YAML document",
        path=None,
        line=(mark.line + 1 if mark else 1),
        column=(mark.column + 1 if mark else 1),
        code="invalid-yaml",
    )


def _index_path(path, index):
    """Append a trusted sequence index without reviving an unsafe parent path."""
    return f"{path}[{index}]" if path is not None else None


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
            _walk_restricted(item, _index_path(path, i))
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                _error("mapping key is not a string", path)
            if any(ord(ch) > 0xffff for ch in key):
                _error("non-BMP mapping key is unsupported", path,
                       code="unsupported-mapping-key")
            # Mapping keys are authored input, even when the current key looks
            # harmless. Do not build a diagnostic path from them.
            _walk_restricted(item, None)
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
        _yaml_error(mark)
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
        _yaml_error(getattr(exc, "problem_mark", None))


def _depth(value):
    if isinstance(value, dict): return 1 + max((_depth(v) for v in value.values()), default=0)
    if isinstance(value, list): return 1 + max((_depth(v) for v in value), default=0)
    return 0


def decode_document(text, *, media_type=None, filename=None, limits=None):
    if not isinstance(text, str):
        _error("document must be text")
    try:
        return _decode_bounded(text, limits)
    except RecursionError:
        # Every pass below recurses over the decoded structure, and the
        # configured depth limit can only be reported once _depth() has
        # finished walking. A document nested past the interpreter's stack
        # therefore exhausts it before the limit check speaks, and
        # RecursionError is a RuntimeError, so it escapes the ValueError
        # handling around the parser (#693: this surfaced as an unhandled 500
        # with no failure audit at all).
        #
        # Report it as the depth failure it is. The limit is the already
        # approved max_nesting_depth, so this invents no new user-visible
        # bound; it makes an existing one reachable for inputs that used to
        # crash first, and keeps 33-deep and 5000-deep indistinguishable to
        # the caller rather than disclosing where this deployment's stack
        # gives out. The location stays the fixed "$"/1/1 the ordinary depth
        # failure uses -- nothing here is derived from the submitted text.
        _error('depth limit exceeded', '$')


def _decode_bounded(text, limits):
    """Decode and validate. Recursion is mapped by the caller, not here."""
    try:
        value = json.loads(text, object_pairs_hook=lambda pairs: _json_pairs(pairs))
    except InterchangeError:
        raise
    except (json.JSONDecodeError, ValueError):
        value = _yaml_restricted(text)
    _walk_restricted(value)
    if limits:
        if isinstance(value, dict) and isinstance(value.get('objects'), list) and len(value['objects']) > limits['max_objects']:
            _error('object limit exceeded', '$.objects')
        if _depth(value) > limits['max_nesting_depth']:
            _error('depth limit exceeded', '$')
    _validate_document(value)
    return value


def _json_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _error("duplicate JSON mapping key", None, code="duplicate-mapping-key")
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
                _error("prohibited credential field", None,
                       code="prohibited-credential-field")
            # Never incorporate an authored key into a location. This also
            # ensures descendants cannot inherit an unsafe path.
            _reject_secrets(item, None)
    elif isinstance(value, list):
        for item in value:
            _reject_secrets(item, path)


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


def _exporter_revision():
    """A deterministic fingerprint of the shipped exporter implementation."""
    return "source-sha256:" + hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


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


def _check_deadline(deadline):
    if deadline is not None and time.monotonic() >= deadline:
        raise OperationDeadlineExceeded()


def import_bundle(document, *, user=None, after_first_target_write=None,
                  after_second_target_write=None, deadline=None):
    _check_deadline(deadline)
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
        # Append-only audit history records the retry without falsifying the
        # original successful import.
        InterchangeAudit.objects.create(
            outcome="idempotent-no-create", payload={"digest": artifact_digest, "design": existing.pk})
        return ImportResult(existing, InterchangeCatalogVersion.objects.filter(artifact_digest=artifact_digest).first(), False, True)
    for design in designs:
        ns, slug = _parts(design["identity"])
        old = InterchangeDesignRevision.objects.filter(namespace=ns, slug=slug, revision=design["revision"]).first()
        if old: _error("non-identical identity/revision conflict", "$.objects")
    try:
        with transaction.atomic():
            if deadline is not None:
                remaining_ms = max(1, int((deadline - time.monotonic()) * 1000))
                with connection.cursor() as cursor:
                    cursor.execute('SET LOCAL statement_timeout = %s', [remaining_ms])
            _check_deadline(deadline)
            created_catalog = None; created_design = None
            for catalog in catalogs:
                _check_deadline(deadline)
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
                _check_deadline(deadline)
            for design in designs:
                _check_deadline(deadline)
                ns, slug = _parts(design["identity"])
                stored_design = copy.deepcopy(design)
                stored_design["_interchange_catalog_objects"] = copy.deepcopy(catalogs)
                stored_design["_interchange_manifest"] = copy.deepcopy(document["manifest"])
                created_design = InterchangeDesignRevision.objects.create(namespace=ns, slug=slug, revision=design["revision"], document=stored_design, artifact_digest=artifact_digest)
                if after_second_target_write: after_second_target_write()
                _check_deadline(deadline)
            if created_design:
                InterchangeProvenance.objects.create(design_revision=created_design, payload=created_design.document.get("provenance", {}))
            _check_deadline(deadline)
            InterchangeAudit.objects.create(outcome="success", payload={"digest": artifact_digest})
    except OperationalError:
        if deadline is not None and time.monotonic() >= deadline:
            raise OperationDeadlineExceeded() from None
        raise
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
    design.setdefault("provenance", {}).update({"schemaVersion": SCHEMA_VERSION, "apiVersion": API_VERSION, "exporter": EXPORTER_ID, "exporterRevision": _exporter_revision(), "maturity": design.get("maturity", "draft"), "artifactKind": "intent", "catalogContentIntegrity": [r.get("contentIntegrity") for r in design.get("catalogRefs", [])], "canonicalizationAlgorithm": BINDING_ALGORITHM, "assumptions": design.get("assumptions", []), "exceptions": []})
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


def approved_content_fingerprint():
    """Fingerprint immutable published catalog content, never a test stub."""
    published = [
        {"identity": {"namespace": item.namespace, "slug": item.slug},
         "version": item.version, "contentIntegrity": _binding(item.content)}
        for item in InterchangeCatalogVersion.objects.filter(published=True)
    ]
    return content_integrity_digest(sorted(published, key=lambda item: (
        item["identity"]["namespace"], item["identity"]["slug"], item["version"])))
def recent_audit_records(): return list(InterchangeAudit.objects.order_by("pk"))
def run_ingress_reaper(): return None
def export_connection(revision, *, index=0): return revision.document["topology"]["connections"][index]
