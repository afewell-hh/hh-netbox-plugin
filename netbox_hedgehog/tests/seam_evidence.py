"""Reusable seam evidence helpers (DIET-665 / #662 T3).

Test-only. Makes the #660 B3 / #661 F5 obligations mechanically checkable:

  1. secret **absence** across a seam's enumerated actual emission paths; and
  2. audit **presence and content** for a realization/lifecycle mutation.

Both directions are required. #625 redacted one serializer and missed a second,
structurally distinct path; #653 then found mutations landing with no audit
record at all. A check for only one direction would have passed in both cases.

This module prevents *future* exposure. It does not inspect, mutate, or purge
historical records -- that remains #658's separately authorized responsibility.
"""

from dataclasses import dataclass, field
from typing import Iterable, Sequence

#: Emission-path categories required by #661 F5. "including but not limited to" --
#: a seam adds its own categories rather than being limited to this list.
CATEGORIES = (
    'api_serializer',
    'model_serialization',
    'exporter',
    'event',
    'log',
    'cache',
    'snapshot',
    'changelog',
    'error_handling',
    'import_template',
    'retention_backup',
)

#: An enumerated path is in exactly one of these states. `unverified` and
#: `latent` exist so a path cannot be quietly omitted by being hard to classify.
#:
#: `known_false` is deliberately distinct from `unverified` (#687). `unverified`
#: means nobody has looked; `known_false` means somebody looked and the boundary
#: does not hold. Filing a measured disclosure under `unverified` would let it
#: hide among honest unknowns, and the whole point of this inventory is that a
#: known gap stays visible. It therefore carries a named remediation issue, the
#: way `out_of_scope` carries a named owner.
STATUSES = (
    'asserted',      # a test in this repository proves the boundary holds here
    'unverified',    # enumerated, boundary plausible but not proven -- must be stated
    'known_false',   # a test in this repository proves the boundary does NOT hold
    'latent',        # code exists but is unreachable; becomes live if wired up
    'out_of_scope',  # explicitly owned elsewhere, with the owner named
)


@dataclass(frozen=True)
class EmissionPath:
    """One place a seam's data can leave the system."""

    name: str
    category: str
    status: str
    detail: str
    owner_issue: str = ''

    def __post_init__(self):
        if self.category not in CATEGORIES:
            raise ValueError(f'unknown emission category: {self.category}')
        if self.status not in STATUSES:
            raise ValueError(f'unknown path status: {self.status}')
        if self.status == 'out_of_scope' and not self.owner_issue:
            raise ValueError(f'{self.name}: out_of_scope requires a named owner')
        if self.status == 'known_false' and not self.owner_issue:
            raise ValueError(f'{self.name}: known_false requires a named remediation issue')


@dataclass(frozen=True)
class SeamInventory:
    """The enumerated emission paths for one seam, plus its secret field names."""

    seam: str
    secret_fields: Sequence[str]
    paths: Sequence[EmissionPath]
    touches_credentials: bool
    touches_audit: bool
    notes: str = ''

    def by_status(self, status: str) -> list:
        return [p for p in self.paths if p.status == status]

    def proven_paths(self) -> list:
        """Only the paths a test actually proves. Never `known_false` (#687).

        Exists so a caller asks for proof explicitly rather than counting rows
        and treating enumeration as coverage.
        """
        return self.by_status('asserted')

    def known_false_paths(self) -> list:
        """Paths measured to be leaking, each with its remediation issue."""
        return self.by_status('known_false')

    def categories_covered(self) -> set:
        return {p.category for p in self.paths}


# --- direction 1: secret absence -------------------------------------------

#: How to interpret a payload when checking for secret key names.
#:
#: 'structured' -- dict/JSON/serialized data, where a secret key's presence
#:                 means the field is being emitted as data. Keys AND values.
#: 'markup'     -- rendered HTML, where a form field's name/id attribute is
#:                 structurally required for the field to function and
#:                 discloses nothing beyond the form's existence. Values only.
#:
#: 'structured' is the default deliberately: it is the stricter check, so a
#: caller who forgets to classify gets more scrutiny rather than less.
PAYLOAD_KINDS = ('structured', 'markup')


def find_secret_leaks(
    payload,
    secret_values: Iterable[str],
    secret_keys: Iterable[str],
    payload_kind: str = 'structured',
) -> list:
    """Return human-readable descriptions of every secret occurrence in `payload`.

    Secret *values* are always a leak, in either payload kind -- that is the
    #625 shape, where a Textarea rendered the stored credential as its content.
    Secret *key names* are a leak only in structured payloads; in markup a
    ``name="kubernetes_token"`` attribute is how the form submits at all.
    """
    if payload_kind not in PAYLOAD_KINDS:
        raise ValueError(f'unknown payload_kind: {payload_kind}')

    text = payload if isinstance(payload, str) else str(payload)
    leaks = []

    # Values leak in every payload kind.
    for value in secret_values:
        if value and value in text:
            leaks.append(f'secret VALUE present: {value[:12]}…')

    if payload_kind == 'markup':
        return leaks

    if isinstance(payload, (dict, list, tuple)):
        # Walk the whole structure. A top-level-only check misses
        # {'spec': {'kubernetes_token': ''}} -- and REST/event payloads nest
        # routinely (custom_fields, related objects), so a surviving secret key
        # is more likely to appear nested than at the root.
        wanted = set(secret_keys)
        for path, key in _walk_mapping_keys(payload):
            if key in wanted:
                leaks.append(f'secret KEY present at {path}')
    else:
        for key in secret_keys:
            if key in text:
                leaks.append(f'secret KEY present in serialized form: {key}')
    return leaks


def _walk_mapping_keys(payload, prefix: str = ''):
    """Yield (dotted_path, key) for every mapping key at any depth.

    Recurses through dicts and sequences. Only mapping *keys* are yielded;
    values are covered separately by the value scan, which is string-based and
    therefore already depth-independent.
    """
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_text = str(key)
            path = f'{prefix}.{key_text}' if prefix else key_text
            yield path, key_text
            yield from _walk_mapping_keys(value, path)
    elif isinstance(payload, (list, tuple)):
        for index, item in enumerate(payload):
            yield from _walk_mapping_keys(item, f'{prefix}[{index}]' if prefix else f'[{index}]')


# --- direction 2: audit presence -------------------------------------------

#: Minimum audit content for a realization/lifecycle mutation (#660 B3).
REQUIRED_AUDIT_FACTS = ('actor', 'time', 'scope', 'provenance', 'changed_facts')


def find_audit_gaps(record) -> list:
    """Return descriptions of missing required audit content.

    `record` is None for the #653 shape -- a mutation that landed with no audit
    record at all. That is a failure, not a neutral outcome.
    """
    if record is None:
        return ['no audit record was produced for the mutation']

    gaps = []
    if not getattr(record, 'user', None) and not getattr(record, 'user_name', ''):
        gaps.append('actor absent (user/user_name)')
    if not getattr(record, 'time', None):
        gaps.append('time absent')
    if not getattr(record, 'changed_object_type', None):
        gaps.append('scope absent (changed_object_type)')
    if getattr(record, 'changed_object_id', None) is None:
        gaps.append('scope absent (changed_object_id)')
    if not getattr(record, 'object_repr', ''):
        gaps.append('provenance absent (object_repr)')

    pre = getattr(record, 'prechange_data', None)
    post = getattr(record, 'postchange_data', None)
    if pre in (None, {}) and post in (None, {}):
        gaps.append('changed facts absent (both prechange_data and postchange_data empty)')
    return gaps
