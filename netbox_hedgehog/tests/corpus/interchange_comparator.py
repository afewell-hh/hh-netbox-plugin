"""Test-only fail-closed full-model interchange comparator (#672 I11b / #673).

Owner: Dev A. Independent reviewer: Dev B. Neither may self-certify coverage.

This comparator exists because T1 ``TopologyGraph`` represents only the
topology subset. Judging a YAML/JSON round trip through T1 alone would let a
trip that drops every catalog reference pass green, because the oracle cannot
see the dropped facts (#672 B3). This module compares the COMPLETE model.

Three rules keep it from becoming the same kind of unvalidated oracle it
replaces:

1. **It never imports T1.** T1 remains the topology-subset helper for I11a.
2. **It fails closed.** An unknown kind, field, extension namespace, or schema
   version is reported UNMEASURED and blocks ``full_model_equal``. Facts the
   comparator cannot see are never silently treated as equal -- which is the
   failure mode a mutation control is structurally blind to, since you can only
   perturb a fact class you already modelled.
3. **Every claimed fact class carries a mutation control AND an unperturbed
   control** (see ``test_comparator_controls.py``). The perturbed pair proves it
   detects a change; the matching pair proves it does not simply report
   everything as different. A fact class without both controls may not appear
   in ``CLAIMED_FACT_CLASSES``.

It is test-only and must never be imported by production code.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping

#: Fact classes this comparator claims to compare. Adding one REQUIRES adding
#: its mutation control and matching control first (#672 Amendment 2).
CLAIMED_FACT_CLASSES = (
    "envelope",
    "identity",
    "bundle_manifest",
    "catalog_content",
    "catalog_reference",
    "content_integrity",
    "assumption",
    "maturity",
    "provenance",
    "extension",
    "topology",
)

SUPPORTED_API_VERSIONS = frozenset({"aid.hedgehog.com/v1"})
SUPPORTED_SCHEMA_VERSIONS = frozenset({"1.0"})

#: Registered extension namespaces. Per the accepted extension-governance
#: decision no third-party namespace is enabled by default, so this is empty
#: and every extension namespace encountered is unregistered -> unmeasured.
REGISTERED_EXTENSION_NAMESPACES: frozenset = frozenset()

_COMMON_FIELDS = frozenset({"apiVersion", "kind", "schemaVersion", "identity", "extensions"})
_KIND_FIELDS = {
    "Bundle": frozenset({"manifest", "objects"}),
    "CatalogVersion": frozenset({"version", "catalogContent", "maturity", "provenance"}),
    "DesignRevision": frozenset({
        "revision", "catalogRefs", "assumptions", "maturity", "provenance", "topology"}),
}

#: Fields whose ABSENCE must be unmeasured rather than equal. Checking only for
#: unknown fields let a dropped required field compare equal, because both sides
#: simply extracted None -- the oracle gap #672 N1 warns about, in the one place
#: it is easiest to miss.
_REQUIRED_FIELDS = {
    "Bundle": frozenset({"apiVersion", "kind", "schemaVersion", "manifest", "objects"}),
    "CatalogVersion": frozenset({
        "apiVersion", "kind", "schemaVersion", "identity", "version", "catalogContent"}),
    "DesignRevision": frozenset({
        "apiVersion", "kind", "schemaVersion", "identity", "revision", "catalogRefs",
        "topology"}),
}

#: Accepted identity syntax: publisher reverse-DNS namespace plus lowercase slug.
_NAMESPACE_RE = re.compile(r"^[a-z0-9]+(\.[a-z0-9-]+)+$")
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


@dataclass(frozen=True)
class FactDifference:
    fact_class: str
    path: str
    left: Any
    right: Any

    def describe(self) -> str:
        return f"{self.fact_class} @ {self.path}: {self.left!r} != {self.right!r}"


@dataclass(frozen=True)
class Unmeasured:
    """A dimension the comparator could not evaluate. Blocks equality."""
    fact_class: str
    path: str
    reason: str

    def describe(self) -> str:
        return f"{self.fact_class} @ {self.path}: {self.reason}"


@dataclass(frozen=True)
class ComparisonOutcome:
    differences: tuple
    unmeasured: tuple
    compared_classes: frozenset

    @property
    def full_model_equal(self) -> bool:
        """True only when nothing differs AND nothing was left unmeasured."""
        return not self.differences and not self.unmeasured

    def describe(self) -> str:
        parts = [d.describe() for d in self.differences]
        parts += [f"UNMEASURED {u.describe()}" for u in self.unmeasured]
        return "; ".join(parts) or "no differences"


def qualified_identity(identity: Any, path: str) -> tuple:
    """Return (qualified-string, unmeasured-or-None) for an identity block.

    Top-level identity is a publisher reverse-DNS namespace plus lowercase
    slug; child identity is a parent-qualified local slug. Display names and
    NetBox primary keys are never identity.
    """
    if not isinstance(identity, Mapping):
        return None, Unmeasured("identity", path, "identity block is not a mapping")
    if "parent" in identity:
        parent, problem = qualified_identity(identity.get("parent"), f"{path}.parent")
        if problem is not None:
            return None, problem
        slug = identity.get("slug")
        if not isinstance(slug, str):
            return None, Unmeasured("identity", path, "child identity has no local slug")
        if not _SLUG_RE.match(slug):
            return None, Unmeasured(
                "identity", path, f"local slug {slug!r} is not a lowercase slug")
        return f"{parent}/{slug}", None
    namespace, slug = identity.get("namespace"), identity.get("slug")
    if not isinstance(namespace, str) or not isinstance(slug, str):
        return None, Unmeasured(
            "identity", path, "top-level identity needs namespace and slug")
    if not _NAMESPACE_RE.match(namespace):
        return None, Unmeasured(
            "identity", path,
            f"namespace {namespace!r} is not a lowercase reverse-DNS namespace")
    if not _SLUG_RE.match(slug):
        return None, Unmeasured(
            "identity", path, f"slug {slug!r} is not a lowercase slug")
    return f"{namespace}:{slug}", None


def _extension_findings(obj: Mapping, path: str) -> list:
    findings = []
    extensions = obj.get("extensions")
    if extensions is None:
        return findings
    if not isinstance(extensions, Mapping):
        return [Unmeasured("extension", f"{path}.extensions", "extensions is not a mapping")]
    for namespace in sorted(extensions):
        if namespace not in REGISTERED_EXTENSION_NAMESPACES:
            findings.append(Unmeasured(
                "extension", f"{path}.extensions.{namespace}",
                "unregistered extension namespace; comparison treatment is undeclared"))
    return findings


def _structural_findings(obj: Any, path: str) -> list:
    """Fail-closed structural scan of one object."""
    if not isinstance(obj, Mapping):
        return [Unmeasured("envelope", path, "object is not a mapping")]
    findings = []
    kind = obj.get("kind")
    if kind not in _KIND_FIELDS:
        return [Unmeasured("envelope", path, f"unknown kind {kind!r}")]
    if obj.get("apiVersion") not in SUPPORTED_API_VERSIONS:
        findings.append(Unmeasured(
            "envelope", path, f"unsupported apiVersion {obj.get('apiVersion')!r}"))
    if obj.get("schemaVersion") not in SUPPORTED_SCHEMA_VERSIONS:
        findings.append(Unmeasured(
            "envelope", path, f"unsupported schemaVersion {obj.get('schemaVersion')!r}"))
    allowed = _COMMON_FIELDS | _KIND_FIELDS[kind]
    for field in sorted(set(obj) - allowed):
        findings.append(Unmeasured(
            "envelope", f"{path}.{field}", f"unknown field for kind {kind!r}"))
    for field in sorted(_REQUIRED_FIELDS[kind] - set(obj)):
        findings.append(Unmeasured(
            "envelope", f"{path}.{field}",
            f"required field missing for kind {kind!r}; absence is unmeasured, "
            f"never equal"))
    findings += _extension_findings(obj, path)
    return findings


def _catalog_refs(obj: Mapping) -> tuple:
    refs = obj.get("catalogRefs") or []
    identities, bindings = [], []
    for index, ref in enumerate(refs):
        if not isinstance(ref, Mapping):
            continue
        qualified, _ = qualified_identity(ref.get("identity"), f"catalogRefs[{index}]")
        identities.append((qualified, ref.get("version")))
        binding = ref.get("contentIntegrity") or {}
        bindings.append((
            qualified, ref.get("version"),
            binding.get("algorithm") if isinstance(binding, Mapping) else None,
            binding.get("digest") if isinstance(binding, Mapping) else None,
        ))
    return tuple(sorted(identities, key=repr)), tuple(sorted(bindings, key=repr))


#: fact class -> callable(obj) -> comparable value
_EXTRACTORS = {
    "envelope": lambda o: (o.get("apiVersion"), o.get("kind"), o.get("schemaVersion")),
    "catalog_reference": lambda o: _catalog_refs(o)[0],
    "content_integrity": lambda o: _catalog_refs(o)[1],
    "assumption": lambda o: o.get("assumptions"),
    "maturity": lambda o: o.get("maturity"),
    "provenance": lambda o: o.get("provenance"),
    "extension": lambda o: o.get("extensions"),
    "topology": lambda o: o.get("topology"),
    # Catalog CONTENT, distinct from the reference binding held by a design.
    # Altering published content while leaving a design's binding untouched was
    # invisible before this class existed.
    "catalog_content": lambda o: o.get("catalogContent"),
}


def compare_interchange(left: Any, right: Any) -> ComparisonOutcome:
    """Compare two decoded interchange bundles across every claimed fact class."""
    differences: list = []
    unmeasured: list = []

    indexes = []
    for side, document in (("left", left), ("right", right)):
        findings = _structural_findings(document, side)
        if findings:
            unmeasured.extend(findings)
        index = {}
        objects = document.get("objects") if isinstance(document, Mapping) else None
        if objects is None:
            unmeasured.append(Unmeasured("envelope", side, "bundle carries no objects list"))
            objects = []
        for position, obj in enumerate(objects):
            path = f"{side}.objects[{position}]"
            obj_findings = _structural_findings(obj, path)
            unmeasured.extend(obj_findings)
            if not isinstance(obj, Mapping):
                continue
            qualified, problem = qualified_identity(obj.get("identity"), f"{path}.identity")
            if problem is not None:
                unmeasured.append(problem)
                continue
            index[qualified] = obj
        indexes.append(index)

    # The bundle document itself carries facts -- envelope and manifest -- that
    # are not attached to any indexed member, so comparing only members left
    # them unchecked.
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        for fact_class, key in (("envelope", None), ("bundle_manifest", "manifest")):
            if key is None:
                lvalue = (left.get("apiVersion"), left.get("kind"), left.get("schemaVersion"))
                rvalue = (right.get("apiVersion"), right.get("kind"), right.get("schemaVersion"))
            else:
                lvalue, rvalue = left.get(key), right.get(key)
            if lvalue != rvalue:
                differences.append(FactDifference(
                    fact_class, f"bundle.{key or 'envelope'}", lvalue, rvalue))

    left_index, right_index = indexes
    for missing in sorted(set(left_index) - set(right_index)):
        differences.append(FactDifference("identity", f"objects[{missing}]", missing, None))
    for added in sorted(set(right_index) - set(left_index)):
        differences.append(FactDifference("identity", f"objects[{added}]", None, added))

    for qualified in sorted(set(left_index) & set(right_index)):
        lobj, robj = left_index[qualified], right_index[qualified]
        for fact_class, extract in _EXTRACTORS.items():
            lvalue, rvalue = extract(lobj), extract(robj)
            if lvalue != rvalue:
                differences.append(FactDifference(
                    fact_class, f"objects[{qualified}].{fact_class}", lvalue, rvalue))

    return ComparisonOutcome(
        differences=tuple(differences),
        unmeasured=tuple(unmeasured),
        compared_classes=frozenset(CLAIMED_FACT_CLASSES),
    )
