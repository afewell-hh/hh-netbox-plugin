"""
Optional type-owned NIC logical-port -> physical-cage layout (CAGE37 design03).

A NIC ``dcim.ModuleType`` may declare, under a schema-bearing ModuleTypeProfile,
``attribute_data['hnp_nic_cage_map']``::

    {"version": 1,
     "ports": [{"cage": "cage-0", "logical_lane": 0}, ...],   # one per InterfaceTemplate
     "cages": {"cage-0": {"breakout_id": "2x400g"}}}

Key ABSENT -> legacy identity path (cage-{port_index}); unchanged.
Key PRESENT -> must be valid; never a silent fallback.

``logical_lane`` is a zero-based logical channel of the selected BreakoutOption,
NOT an electrical SerDes lane. Declared metadata is intent, not hardware
qualification. This module is pure: it reads only, never writes.

It also builds and validates the optional ``nic_cage_layouts`` snapshot
extension (snapshot_contract_v1). Fingerprints are integrity/consistency
evidence, NOT tamper-proof authority.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

from django.core.exceptions import ValidationError

LAYOUT_KEY = 'hnp_nic_cage_map'
SNAPSHOT_KEY = 'nic_cage_layouts'
EXTENSION_VERSION = 1
MAX_CAGE_NAME = 64
TRANSCEIVER_PROFILE_NAME = 'Network Transceiver'


def natural_key(name: str):
    """Natural sort key identical to populate_bays / generator port ordering."""
    parts = re.split(r'(\d+)', name)
    return [int(p) if p.isdigit() else p.lower() for p in parts]


def has_layout(module_type) -> bool:
    data = getattr(module_type, 'attribute_data', None)
    return isinstance(data, dict) and LAYOUT_KEY in data


def canonical_sha256(payload) -> str:
    """SHA256 of UTF-8 canonical JSON (sort_keys, compact separators, ascii)."""
    text = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


@dataclass(frozen=True)
class CageMode:
    cage: str
    breakout_id: str
    breakout_pk: int
    from_speed: int
    logical_ports: int
    logical_speed: int


@dataclass(frozen=True)
class PortMapping:
    logical_index: int
    template_id: int
    template_name: str
    template_type: str
    cage: str
    logical_lane: int


@dataclass(frozen=True)
class NicCageLayout:
    module_type_id: int
    profile_id: int
    profile_schema_sha256: str
    ports: tuple  # tuple[PortMapping, ...] in logical_index order
    cages: tuple  # tuple[CageMode, ...] sorted by cage name

    def cage_for_index(self, index: int) -> str:
        return self.ports[index].cage

    def mode(self, cage: str) -> CageMode:
        for m in self.cages:
            if m.cage == cage:
                return m
        raise KeyError(cage)


@dataclass(frozen=True)
class PlanLayoutCapture:
    """Immutable preflight capture: layouts used for placement + snapshot evidence."""
    layouts: dict  # PlanServerNIC.pk -> NicCageLayout (opted-in only)
    extension: dict | None  # valid snapshot_contract_v1 record, or None when no opt-in


def _err(module_type, code: str, detail: str) -> ValidationError:
    label = getattr(module_type, 'model', None) or f'pk={getattr(module_type, "pk", None)}'
    return ValidationError(
        f'[{code}] NIC ModuleType {label!r} {LAYOUT_KEY}: {detail}',
        code=code,
    )


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_pos_int(value) -> bool:
    return _is_int(value) and value > 0


def _valid_cage_name(name) -> bool:
    return (
        isinstance(name, str)
        and name != ''
        and name.strip() == name
        and len(name) <= MAX_CAGE_NAME
        and '{' not in name
        and '}' not in name
    )


def _schema_validate(attribute_data, schema):
    """Same native utility ModuleType.clean() uses (jsonschema.validate); no save/clear."""
    import jsonschema
    from jsonschema.exceptions import SchemaError
    from jsonschema.exceptions import ValidationError as JSONValidationError

    try:
        jsonschema.validate(attribute_data, schema=schema)
    except JSONValidationError as exc:
        return str(exc.message)
    except SchemaError as exc:
        # A stored profile schema that is itself malformed is readable bad input:
        # surface it as a typed actionable error, never an implementation exception.
        return f'stored profile schema is itself malformed: {exc.message}'
    return None


_COPPER_MEDIUMS = frozenset({'DAC', 'ACC'})
_OPTICAL_MEDIUMS = frozenset({'MMF', 'SMF'})
_OPTICAL_REACH_CLASSES = frozenset({'SR', 'LR', 'DR'})


_V7_SCALAR_KEYS = ('reach_class', 'medium')


def optic_scalar_type_errors(data) -> list:
    """Keys among reach_class/medium that are present, non-null and not strings.

    A weak profile schema may store containers/other non-string values there; the
    V7 membership check below must never see them (unhashable -> TypeError).
    """
    if not isinstance(data, dict):
        return []
    return [k for k in _V7_SCALAR_KEYS if data.get(k) is not None and not isinstance(data.get(k), str)]


def reach_medium_conflict(data) -> str | None:
    """Existing PlanServerConnection V7 reach_class/medium invariant (unchanged rule).

    Only string values take part in membership tests; callers reject non-string
    values explicitly first (``optic_scalar_type_errors``).
    """
    if not isinstance(data, dict):
        return None
    rc, medium = data.get('reach_class'), data.get('medium')
    if not (isinstance(rc, str) and isinstance(medium, str)):
        return None
    if not (rc and medium):
        return None
    if rc == 'DAC' and medium in _OPTICAL_MEDIUMS:
        return f"reach_class 'DAC' is incompatible with medium {medium!r}"
    if rc in _OPTICAL_REACH_CLASSES and medium in _COPPER_MEDIUMS:
        return f'reach_class {rc!r} is incompatible with medium {medium!r}'
    return None


def _ordered_templates(module_type):
    from dcim.models import InterfaceTemplate

    return sorted(
        InterfaceTemplate.objects.filter(module_type=module_type),
        key=lambda t: natural_key(t.name),
    )


def parse_layout(module_type) -> NicCageLayout | None:
    """Strictly parse/validate the opt-in layout. Returns None when key absent.

    Raises ValidationError (with a specific code) on any present-invalid layout.
    Read-only: never saves, never clears attribute_data.
    """
    from netbox_hedgehog.models.topology_planning import BreakoutOption
    from netbox_hedgehog.services.transceiver_bay_policy import is_virtual_placeholder_module_type

    if not has_layout(module_type):
        return None
    raw = module_type.attribute_data[LAYOUT_KEY]

    if is_virtual_placeholder_module_type(module_type):
        raise _err(module_type, 'nic_layout_virtual', 'opt-in not allowed on a virtual placeholder NIC type')

    profile = getattr(module_type, 'profile', None)
    if profile is None:
        raise _err(module_type, 'nic_layout_profile_missing', 'requires a schema-bearing ModuleTypeProfile')
    schema = getattr(profile, 'schema', None)
    props = schema.get('properties') if isinstance(schema, dict) else None
    if not schema or not isinstance(props, dict) or LAYOUT_KEY not in props:
        raise _err(module_type, 'nic_layout_profile_schema', 'profile schema does not declare this property')
    # Native schema validation (same as pinned ModuleType.clean), without saving/clearing.
    schema_error = _schema_validate(module_type.attribute_data, schema)
    if schema_error is not None:
        raise _err(module_type, 'nic_layout_profile_schema_invalid',
                   f'attribute_data does not satisfy profile schema: {schema_error}')

    if not isinstance(raw, dict):
        raise _err(module_type, 'nic_layout_shape', 'must be an object')
    if set(raw.keys()) != {'version', 'ports', 'cages'}:
        raise _err(module_type, 'nic_layout_shape', 'must contain exactly version/ports/cages')
    version = raw['version']
    if not _is_int(version) or version != 1:
        raise _err(module_type, 'nic_layout_version', f'unsupported version {version!r}')

    ports = raw['ports']
    cages = raw['cages']
    if not isinstance(ports, list) or not ports:
        raise _err(module_type, 'nic_layout_ports', 'ports must be a nonempty array')
    if not isinstance(cages, dict) or not cages:
        raise _err(module_type, 'nic_layout_cages', 'cages must be a nonempty object')

    templates = _ordered_templates(module_type)
    for t in templates:
        if '{module}' in t.name:
            raise _err(module_type, 'nic_layout_template_module_token',
                       f'interface template {t.name!r} containing {{module}} unsupported in version 1')
    if len(ports) != len(templates):
        raise _err(module_type, 'nic_layout_port_count',
                   f'{len(ports)} port rows but {len(templates)} interface templates')

    modes = {}
    for cage_name, body in cages.items():
        if not _valid_cage_name(cage_name):
            raise _err(module_type, 'nic_layout_cage_name', f'invalid cage name {cage_name!r}')
        if not isinstance(body, dict) or set(body.keys()) != {'breakout_id'}:
            raise _err(module_type, 'nic_layout_cage_body', f'cage {cage_name!r} must be exactly {{breakout_id}}')
        bid = body['breakout_id']
        if not isinstance(bid, str) or not bid.strip():
            raise _err(module_type, 'nic_layout_cage_body', f'cage {cage_name!r} breakout_id must be nonempty string')
        bo = BreakoutOption.objects.filter(breakout_id=bid).first()
        if bo is None:
            raise _err(module_type, 'nic_layout_unknown_mode', f'cage {cage_name!r} unknown breakout_id {bid!r}')
        fs, lp, ls = bo.from_speed, bo.logical_ports, bo.logical_speed
        if not all(_is_pos_int(v) for v in (fs, lp, ls)) or lp * ls > fs:
            raise _err(module_type, 'nic_layout_mode_capacity', f'breakout {bid!r} has incoherent capacity')
        modes[cage_name] = CageMode(cage_name, bid, bo.pk, fs, lp, ls)

    seen_channels = set()
    referenced = set()
    mappings = []
    for index, (row, tpl) in enumerate(zip(ports, templates)):
        if not isinstance(row, dict) or set(row.keys()) != {'cage', 'logical_lane'}:
            raise _err(module_type, 'nic_layout_port_shape', f'port {index} must be exactly {{cage, logical_lane}}')
        cage_name, lane = row['cage'], row['logical_lane']
        if not isinstance(cage_name, str) or cage_name not in modes:
            raise _err(module_type, 'nic_layout_port_cage', f'port {index} references undeclared cage {cage_name!r}')
        if not _is_int(lane) or lane < 0:
            raise _err(module_type, 'nic_layout_port_lane', f'port {index} logical_lane must be int >= 0')
        if lane >= modes[cage_name].logical_ports:
            raise _err(module_type, 'nic_layout_port_lane',
                       f'port {index} logical_lane {lane} exceeds mode {modes[cage_name].breakout_id}')
        if (cage_name, lane) in seen_channels:
            raise _err(module_type, 'nic_layout_duplicate_channel', f'duplicate ({cage_name!r}, {lane})')
        seen_channels.add((cage_name, lane))
        referenced.add(cage_name)
        mappings.append(PortMapping(index, tpl.pk, tpl.name, tpl.type, cage_name, lane))

    if referenced != set(modes):
        raise _err(module_type, 'nic_layout_unreferenced_cage',
                   f'declared cages {sorted(set(modes) - referenced)} not referenced by ports')

    return NicCageLayout(
        module_type_id=module_type.pk,
        profile_id=profile.pk,
        profile_schema_sha256=canonical_sha256(schema),
        ports=tuple(mappings),
        cages=tuple(modes[k] for k in sorted(modes)),
    )


def _validate_mapped_optic(nic_mt, optic, mode: CageMode) -> None:
    """Existing Network Transceiver profile invariants + case-only mode match."""
    profile = getattr(optic, 'profile', None)
    if profile is None or profile.name != TRANSCEIVER_PROFILE_NAME or not profile.schema:
        raise _err(nic_mt, 'nic_layout_optic_profile',
                   f'optic {optic.model!r} must use the schema-bearing {TRANSCEIVER_PROFILE_NAME!r} profile')
    data = optic.attribute_data
    if not isinstance(data, dict):
        raise _err(nic_mt, 'nic_layout_optic_profile', f'optic {optic.model!r} has no attribute_data')
    schema_error = _schema_validate(data, profile.schema)
    if schema_error is not None:
        raise _err(nic_mt, 'nic_layout_optic_profile',
                   f'optic {optic.model!r} attribute_data violates its profile schema: {schema_error}')
    bad_types = optic_scalar_type_errors(data)
    if bad_types:
        raise _err(nic_mt, 'nic_layout_optic_attr_type',
                   f'optic {optic.model!r} attribute(s) {bad_types} must be strings '
                   f'(got {[type(data[k]).__name__ for k in bad_types]})')
    conflict = reach_medium_conflict(data)
    if conflict is not None:
        raise _err(nic_mt, 'nic_layout_optic_reach_medium', f'optic {optic.model!r}: {conflict} (V7)')
    topo = data.get('breakout_topology')
    if not isinstance(topo, str) or not topo or topo.strip() != topo:
        raise _err(nic_mt, 'nic_layout_optic_mode',
                   f'optic {optic.model!r} has missing/blank breakout_topology for mode {mode.breakout_id!r}')
    if topo.lower() != mode.breakout_id.lower():
        raise _err(nic_mt, 'nic_layout_optic_mode',
                   f'optic {optic.model!r} breakout_topology {topo!r} does not equal {mode.breakout_id!r}')


def _expand_indices(nic_mt, conn, port_count: int):
    """Strict index expansion exactly as generation does (start + offset)."""
    start, ppc = conn.port_index, conn.ports_per_connection
    if not _is_int(start) or start < 0:
        raise _err(nic_mt, 'nic_layout_index_range',
                   f'connection {conn.connection_id!r} port_index {start!r} must be int >= 0')
    if not _is_pos_int(ppc):
        raise _err(nic_mt, 'nic_layout_index_range',
                   f'connection {conn.connection_id!r} ports_per_connection {ppc!r} must be int >= 1')
    indices = [start + offset for offset in range(ppc)]
    if indices[-1] >= port_count:
        raise _err(nic_mt, 'nic_layout_index_range',
                   f'connection {conn.connection_id!r} ports {indices[0]}..{indices[-1]} '
                   f'outside 0..{port_count - 1}')
    return indices


def _validate_index_usage(nic_mt, conns, port_count: int) -> None:
    """Layout-independent live checks (legacy records of an opted-in plan): range via
    the same strict expansion as mapped, and no logical port consumed twice per NIC."""
    consumed = {}
    for c in conns:
        for idx in _expand_indices(nic_mt, c, port_count):
            if idx in consumed:
                raise _err(nic_mt, 'nic_layout_port_collision',
                           f'logical port {idx} consumed by {consumed[idx]!r} and {c.connection_id!r}')
            consumed[idx] = c.connection_id


def _validate_nic_usage(nic, layout: NicCageLayout, conns, active: bool, bay_names) -> None:
    mt = nic.module_type
    consumed = {}
    per_cage = {}
    for c in conns:
        for idx in _expand_indices(mt, c, len(layout.ports)):
            if idx in consumed:
                raise _err(mt, 'nic_layout_port_collision',
                           f'logical port {idx} consumed by {consumed[idx]!r} and {c.connection_id!r}')
            consumed[idx] = c.connection_id
            per_cage.setdefault(layout.cage_for_index(idx), []).append((c, idx))
    if not active:
        # Inactive/zero-quantity: structure validated above; no placement requirement.
        return
    for cage_name, uses in sorted(per_cage.items()):
        mode = layout.mode(cage_name)
        fk_ids = {c.transceiver_module_type_id for c, _ in uses}
        if None in fk_ids:
            raise _err(mt, 'nic_layout_null_optic', f'used cage {cage_name!r} has connection without optic')
        if len(fk_ids) != 1:
            raise _err(mt, 'nic_layout_conflicting_optic', f'cage {cage_name!r} optic FKs {sorted(fk_ids)}')
        _validate_mapped_optic(mt, uses[0][0].transceiver_module_type, mode)
        channels = set()
        total = 0
        for c, idx in uses:
            if not _is_pos_int(c.speed) or c.speed != mode.logical_speed:
                raise _err(mt, 'nic_layout_speed',
                           f'connection {c.connection_id!r} speed {c.speed!r} != {mode.logical_speed}')
            channels.add(layout.ports[idx].logical_lane)
            total += c.speed
        if len(channels) > mode.logical_ports or total > mode.from_speed:
            raise _err(mt, 'nic_layout_capacity', f'cage {cage_name!r} over capacity')
    missing = sorted(set(per_cage) - set(bay_names))
    if missing:
        raise _err(mt, 'nic_layout_missing_bay_template', f'missing cage bay templates {missing}')


# ------------------------------------------------------------------ capture

def _nic_record(server_class, nic, layout, conns, bay_rows):
    """One snapshot_contract_v1 NIC record (without evidence_sha256)."""
    mt = nic.module_type
    profile = getattr(mt, 'profile', None)
    schema = getattr(profile, 'schema', None) if profile is not None else None
    if layout is not None:
        templates = [
            {'template_id': p.template_id, 'name': p.template_name, 'type': p.template_type,
             'logical_index': p.logical_index}
            for p in layout.ports
        ]
        layout_payload = {
            'version': EXTENSION_VERSION,
            'ports': [{'logical_index': p.logical_index, 'cage': p.cage, 'logical_lane': p.logical_lane}
                      for p in layout.ports],
            'cages': [{'cage': m.cage, 'breakout_id': m.breakout_id} for m in layout.cages],
        }
        modes = [
            {'cage': m.cage, 'breakout_id': m.breakout_id, 'breakout_pk': m.breakout_pk,
             'from_speed': m.from_speed, 'logical_ports': m.logical_ports, 'logical_speed': m.logical_speed}
            for m in layout.cages
        ]
    else:
        templates = [
            {'template_id': t.pk, 'name': t.name, 'type': t.type, 'logical_index': i}
            for i, t in enumerate(_ordered_templates(mt))
        ]
        layout_payload = None
        modes = []
    optics = {}
    for c in conns:
        optic = c.transceiver_module_type
        if optic is None or optic.pk in optics:
            continue
        o_profile = getattr(optic, 'profile', None)
        o_schema = getattr(o_profile, 'schema', None) if o_profile is not None else None
        o_data = optic.attribute_data if isinstance(optic.attribute_data, dict) else None
        topo = o_data.get('breakout_topology') if o_data is not None else None
        optics[optic.pk] = {
            'module_type_id': optic.pk,
            'profile_id': o_profile.pk if o_profile is not None else None,
            'profile_schema_sha256': canonical_sha256(o_schema) if o_schema else None,
            'breakout_topology': topo if isinstance(topo, str) else None,
            'attribute_data_sha256': canonical_sha256(optic.attribute_data),
        }
    return {
        'server_class_id': server_class.server_class_id,
        'nic_id': nic.nic_id,
        'module_type_id': mt.pk,
        'profile_id': profile.pk if profile is not None else None,
        'profile_schema_sha256': canonical_sha256(schema) if schema else None,
        'layout_present': layout is not None,
        'layout': layout_payload,
        'interface_templates': templates,
        'bay_templates': sorted(bay_rows, key=lambda b: (b['name'], b['template_id'])),
        'connections': sorted(
            # Actual connection owner, never manufactured from the NIC (validator checks linkage).
            ({'server_class_id': c.server_class.server_class_id, 'connection_id': c.connection_id,
              'nic_id': nic.nic_id, 'target_zone_id': c.target_zone_id, 'port_index': c.port_index,
              'ports_per_connection': c.ports_per_connection, 'speed': c.speed,
              'transceiver_module_type_id': c.transceiver_module_type_id} for c in conns),
            key=lambda r: r['connection_id'],
        ),
        'modes': modes,
        'optics': [optics[k] for k in sorted(optics)],
    }


def capture_plan_layouts(plan) -> PlanLayoutCapture:
    """Read-only preflight capture over the WHOLE plan. Raises ValidationError.

    Returns the layouts used for placement and, when ANY plan NIC type contains
    the layout key, the complete snapshot extension describing exactly that
    capture. With no opt-in anywhere returns (empty, None): legacy unchanged.
    """
    from dcim.models import ModuleBayTemplate
    from netbox_hedgehog.models.topology_planning import PlanServerConnection, PlanServerNIC

    server_classes = list(plan.server_classes.all().order_by('pk'))
    nics = list(
        PlanServerNIC.objects.filter(server_class__plan=plan)
        .select_related('server_class', 'module_type', 'module_type__profile').order_by('pk')
    )
    conns = list(
        PlanServerConnection.objects.filter(server_class__plan=plan)
        .select_related('server_class', 'transceiver_module_type', 'transceiver_module_type__profile')
        .order_by('pk')
    )
    any_present = any(nic.module_type is not None and has_layout(nic.module_type) for nic in nics)
    if any_present:
        _check_connection_structure(conns, {n.pk: n for n in nics})

    layouts = {}
    records = []
    sc_by_pk = {sc.pk: sc for sc in server_classes}
    for nic in nics:
        mt = nic.module_type
        nic_conns = [c for c in conns if c.nic_id == nic.pk]
        layout = parse_layout(mt) if mt is not None else None
        sc = sc_by_pk.get(nic.server_class_id, nic.server_class)
        bay_rows = []
        if mt is not None:
            bay_rows = [{'template_id': pk, 'name': name, 'position': position}
                        for pk, name, position in ModuleBayTemplate.objects.filter(module_type=mt)
                        .values_list('pk', 'name', 'position')]
        if layout is not None:
            layouts[nic.pk] = layout
            active = _is_pos_int(sc.quantity)
            _validate_nic_usage(nic, layout, nic_conns, active, [b['name'] for b in bay_rows])
        if any_present:
            if mt is None:
                raise ValidationError(f'[nic_layout_snapshot_nic_type_missing] NIC {nic.nic_id!r} has no module type',
                                      code='nic_layout_snapshot_nic_type_missing')
            if layout is None:
                # Legacy record in an opted-in plan: same layout-independent range and
                # per-NIC collision rules (specific codes), active or inactive.
                _validate_index_usage(mt, nic_conns, len(_ordered_templates(mt)))
            records.append(_nic_record(sc, nic, layout, nic_conns, bay_rows))

    if not any_present:
        return PlanLayoutCapture(layouts={}, extension=None)

    orphan = [c.connection_id for c in conns if c.nic_id is None]
    if orphan:
        raise ValidationError(
            f'[nic_layout_snapshot_connection_without_nic] connections {sorted(orphan)} have no NIC; '
            'complete layout evidence cannot be recorded', code='nic_layout_snapshot_connection_without_nic')
    for record in records:
        record['evidence_sha256'] = canonical_sha256(record)
    extension = {
        'version': EXTENSION_VERSION,
        'expected_nic_keys': sorted({(n.server_class.server_class_id, n.nic_id) for n in nics}),
        'expected_connection_keys': sorted({(c.server_class.server_class_id, c.connection_id) for c in conns}),
        'nics': sorted(records, key=lambda r: (r['server_class_id'], r['nic_id'])),
    }
    extension['expected_nic_keys'] = [list(k) for k in extension['expected_nic_keys']]
    extension['expected_connection_keys'] = [list(k) for k in extension['expected_connection_keys']]
    extension['evidence_sha256'] = canonical_sha256(extension)
    # Never admit (or later save) evidence that its own validator rejects.
    active = {sc.server_class_id for sc in server_classes if _is_pos_int(sc.quantity)}
    errors = extension_errors(extension, active_classes=active)
    if errors:
        raise ValidationError(
            f'[nic_layout_snapshot_invalid] captured layout evidence is internally invalid: {errors}',
            code='nic_layout_snapshot_invalid')
    return PlanLayoutCapture(layouts=layouts, extension=extension)


def _check_connection_structure(conns, nics_by_pk) -> None:
    """Pure structural checks over ALL plan connections once any NIC opts in.

    Ownership comes from the connection row and must equal its NIC's owner; speed,
    range and target zone must be structurally valid even for inactive classes
    (inactivity waives optic placement only, never evidence validity).
    """
    for c in conns:
        label = f'connection {c.connection_id!r}'
        nic = nics_by_pk.get(c.nic_id)
        if nic is not None and nic.server_class_id != c.server_class_id:
            raise ValidationError(
                f'[nic_layout_connection_owner] {label} of server class '
                f'{c.server_class.server_class_id!r} references NIC {nic.nic_id!r} owned by '
                f'{nic.server_class.server_class_id!r}', code='nic_layout_connection_owner')
        if not _is_pos_int(c.speed):
            raise ValidationError(f'[nic_layout_connection_speed] {label} speed {c.speed!r} must be int >= 1',
                                  code='nic_layout_connection_speed')
        if not (_is_int(c.port_index) and c.port_index >= 0 and _is_pos_int(c.ports_per_connection)):
            raise ValidationError(f'[nic_layout_index_range] {label} has invalid port range',
                                  code='nic_layout_index_range')
        if c.target_zone_id is None:
            raise ValidationError(f'[nic_layout_connection_zone] {label} has no target zone',
                                  code='nic_layout_connection_zone')


def build_snapshot_extension(plan):
    """Live snapshot extension: None (no opt-in), valid record, or invalid marker.

    Never raises and never writes; any readable-current error becomes the
    typed invalid marker ``{version: 1, status: 'invalid', errors: [...]}``.
    """
    try:
        return capture_plan_layouts(plan).extension
    except ValidationError as exc:
        return {'version': EXTENSION_VERSION, 'status': 'invalid', 'errors': validation_error_codes(exc)}
    except Exception as exc:  # readable-current failure must not become a 500
        return {'version': EXTENSION_VERSION, 'status': 'invalid', 'errors': [f'unreadable:{type(exc).__name__}']}


def validation_error_codes(exc) -> list:
    """Sorted typed codes from a list-form OR dict-form (e.g. native model V7) ValidationError.

    Django's dict-form ValidationError has ``error_dict`` and no ``error_list``;
    accessing ``error_list`` there raises AttributeError inside the handler, which a
    sibling ``except Exception`` would NOT catch (-> HTTP 500). Never raises.
    """
    try:
        if hasattr(exc, 'error_dict'):
            errors = [e for field_errors in exc.error_dict.values() for e in field_errors]
        else:
            errors = list(getattr(exc, 'error_list', None) or [exc])
        codes = {getattr(e, 'code', None) or 'nic_layout_invalid' for e in errors}
        return sorted(str(c) for c in codes) or ['nic_layout_invalid']
    except Exception:  # pragma: no cover - defensive normalization
        return ['nic_layout_invalid']


# --------------------------------------------------------------- validation

_ROOT_KEYS = frozenset({'version', 'expected_nic_keys', 'expected_connection_keys', 'nics', 'evidence_sha256'})
_NIC_KEYS = frozenset({
    'server_class_id', 'nic_id', 'module_type_id', 'profile_id', 'profile_schema_sha256',
    'layout_present', 'layout', 'interface_templates', 'bay_templates', 'connections',
    'modes', 'optics', 'evidence_sha256',
})
_TEMPLATE_KEYS = frozenset({'template_id', 'name', 'type', 'logical_index'})
_BAY_KEYS = frozenset({'template_id', 'name', 'position'})
_CONN_KEYS = frozenset({'server_class_id', 'connection_id', 'nic_id', 'target_zone_id', 'port_index',
                        'ports_per_connection', 'speed', 'transceiver_module_type_id'})
_MODE_KEYS = frozenset({'cage', 'breakout_id', 'breakout_pk', 'from_speed', 'logical_ports', 'logical_speed'})
_OPTIC_KEYS = frozenset({'module_type_id', 'profile_id', 'profile_schema_sha256', 'breakout_topology',
                         'attribute_data_sha256'})
_HEX64 = re.compile(r'^[0-9a-f]{64}$')


class _Invalid(Exception):
    pass


def _need(cond, code):
    if not cond:
        raise _Invalid(code)


def _nonempty_str(v):
    return isinstance(v, str) and v != ''


def _opt_pos_int(v):
    return v is None or _is_pos_int(v)


def _opt_hex(v):
    return v is None or (isinstance(v, str) and bool(_HEX64.match(v)))


def _records(rows, keys, code):
    _need(isinstance(rows, list), code)
    for row in rows:
        _need(isinstance(row, dict) and set(row) == keys, code)
    return rows


def _key_pairs(value, code):
    _need(isinstance(value, list), code)
    pairs = []
    for item in value:
        _need(isinstance(item, list) and len(item) == 2 and all(_nonempty_str(p) for p in item), code)
        pairs.append(tuple(item))
    _need(pairs == sorted(set(pairs)), code)
    return pairs


def _check_layout_record(nic):
    templates = _records(nic['interface_templates'], _TEMPLATE_KEYS, 'template_record')
    for t in templates:
        _need(_is_pos_int(t['template_id']) and _nonempty_str(t['name']) and _nonempty_str(t['type'])
              and _is_int(t['logical_index']), 'template_record')
    _need([t['logical_index'] for t in templates] == list(range(len(templates))), 'template_index')
    _need(len({t['template_id'] for t in templates}) == len(templates), 'template_duplicate')
    # Native InterfaceTemplate uniqueness is (module_type, name): one NIC record can
    # never hold two templates with the same EXACT literal name, even under distinct
    # IDs (mapped AND legacy). Case-sensitive: 'P0'/'p0' are distinct names (equal
    # natural keys stay valid). Per-NIC only: no cross-owner/global name rule.
    _need(len({t['name'] for t in templates}) == len(templates), 'template_duplicate_name')
    # Capture (mapped AND legacy) assigns logical_index by a stable sort on
    # natural_key(name); recorded names must therefore be non-decreasing in that
    # key along their ordinals (equal keys, e.g. case variants, keep either order).
    # Internal semantic consistency only; no case/substitution rule is added here.
    # Enforced for legacy before return and for mapped records AFTER the more
    # specific version-1 {module} token rule ('{' sorts after letters, so a
    # token name would otherwise be masked as a generic ordering error).
    name_keys = [natural_key(t['name']) for t in templates]
    natural_order = all(a <= b for a, b in zip(name_keys, name_keys[1:]))
    bays = _records(nic['bay_templates'], _BAY_KEYS, 'bay_record')
    for b in bays:
        _need(_is_pos_int(b['template_id']) and _nonempty_str(b['name'])
              and (b['position'] is None or isinstance(b['position'], str)), 'bay_record')
    _need(len({b['template_id'] for b in bays}) == len(bays), 'bay_duplicate')
    # Native ModuleBayTemplate uniqueness is (module_type, name): exact literal names
    # are unique per NIC record regardless of ID (case-sensitive; same cage name under
    # a DIFFERENT NIC owner stays valid).
    _need(len({b['name'] for b in bays}) == len(bays), 'bay_duplicate_name')
    modes = _records(nic['modes'], _MODE_KEYS, 'mode_record')
    for m in modes:
        _need(_nonempty_str(m['cage']) and _nonempty_str(m['breakout_id'])
              and all(_is_pos_int(m[k]) for k in ('breakout_pk', 'from_speed', 'logical_ports', 'logical_speed'))
              and m['logical_ports'] * m['logical_speed'] <= m['from_speed'], 'mode_record')
    if not nic['layout_present']:
        _need(nic['layout'] is None and modes == [], 'legacy_layout')
        _need(natural_order, 'template_order')
        return {}, {}
    _need(_is_pos_int(nic['profile_id']) and _opt_hex(nic['profile_schema_sha256'])
          and nic['profile_schema_sha256'] is not None, 'optin_profile')
    layout = nic['layout']
    _need(isinstance(layout, dict) and set(layout) == {'version', 'ports', 'cages'}
          and _is_int(layout['version']) and layout['version'] == 1, 'layout_record')
    ports = _records(layout['ports'], frozenset({'logical_index', 'cage', 'logical_lane'}), 'layout_ports')
    cages = _records(layout['cages'], frozenset({'cage', 'breakout_id'}), 'layout_cages')
    _need(len(ports) > 0 and len(cages) > 0 and len(templates) > 0, 'layout_empty_geometry')
    # Same restriction as live parse_layout: mapped (version 1) geometry never uses
    # templates containing literal {module}; legacy records are unaffected.
    _need(all('{module}' not in t['name'] for t in templates), 'layout_template_module_token')
    _need(natural_order, 'template_order')
    for row in list(cages) + list(modes):
        _need(_valid_cage_name(row['cage']), 'layout_cage_name')
    mode_by_cage = {m['cage']: m for m in modes}
    _need(len(mode_by_cage) == len(modes), 'mode_duplicate')
    _need(len({c['cage'] for c in cages}) == len(cages), 'layout_cage_duplicate')
    _need({c['cage'] for c in cages} == set(mode_by_cage) and len(cages) == len(modes), 'mode_coverage')
    for c in cages:
        _need(mode_by_cage[c['cage']]['breakout_id'] == c['breakout_id'], 'mode_binding')
    _need(all(_is_int(p['logical_index']) for p in ports)
          and sorted(p['logical_index'] for p in ports) == list(range(len(templates)))
          and len(ports) == len(templates), 'layout_index')
    channels = set()
    for p in ports:
        _need(_nonempty_str(p['cage']) and p['cage'] in mode_by_cage and _is_int(p['logical_lane'])
              and 0 <= p['logical_lane'] < mode_by_cage[p['cage']]['logical_ports'], 'layout_port')
        _need((p['cage'], p['logical_lane']) not in channels, 'layout_channel_duplicate')
        channels.add((p['cage'], p['logical_lane']))
    # Declared cages must be exactly the port-referenced target set (parser rule).
    _need({p['cage'] for p in ports} == set(mode_by_cage), 'layout_unreferenced_cage')
    return {p['logical_index']: (p['cage'], p['logical_lane']) for p in ports}, mode_by_cage


def _check_mapped_usage(nic, port_map, mode_by_cage, conns, optics, active):
    """Internal relationships among layout/modes/used ports/bays/optics (parser-equivalent)."""
    # Range/collision already enforced for EVERY record by _check_connection_indices.
    per_cage = {}
    for c in conns:
        for idx in range(c['port_index'], c['port_index'] + c['ports_per_connection']):
            per_cage.setdefault(port_map[idx][0], []).append((c, port_map[idx][1]))
    if not active:
        return  # inactive: structure above validated; no placement-required optic
    optic_by_id = {o['module_type_id']: o for o in optics}
    bay_names = {b['name'] for b in nic['bay_templates']}
    for cage, uses in per_cage.items():
        mode = mode_by_cage[cage]
        fks = {c['transceiver_module_type_id'] for c, _ in uses}
        _need(None not in fks, 'used_cage_null_optic')
        _need(len(fks) == 1, 'used_cage_conflicting_optic')
        topo = optic_by_id[next(iter(fks))]['breakout_topology']
        _need(isinstance(topo, str) and topo != '' and topo.strip() == topo
              and topo.lower() == mode['breakout_id'].lower(), 'used_cage_optic_mode')
        _need(all(c['speed'] == mode['logical_speed'] for c, _ in uses), 'used_cage_speed')
        _need(len({lane for _, lane in uses}) <= mode['logical_ports']
              and sum(c['speed'] for c, _ in uses) <= mode['from_speed'], 'used_cage_capacity')
        _need(cage in bay_names, 'used_cage_missing_bay')


def _check_connection_indices(nic, conns):
    """Layout-independent used-port checks for EVERY NIC record (mapped AND legacy),
    active or inactive: each connection's start+offset indices must lie within the
    recorded interface templates of THAT NIC, and distinct connections of the same NIC
    may not consume the same logical interface (generation could not cable it).
    Per-NIC only: equal indices under different NIC owners are valid."""
    n = len(nic['interface_templates'])
    consumed = set()
    for c in conns:
        _need(c['port_index'] + c['ports_per_connection'] <= n, 'connection_range')
        for idx in range(c['port_index'], c['port_index'] + c['ports_per_connection']):
            _need(idx not in consumed, 'connection_index_collision')
            consumed.add(idx)


def _check_nic(nic, active=True):
    _need(isinstance(nic, dict) and set(nic) == _NIC_KEYS, 'nic_record')
    _need(_nonempty_str(nic['server_class_id']) and _nonempty_str(nic['nic_id'])
          and _is_pos_int(nic['module_type_id']) and _opt_pos_int(nic['profile_id'])
          and _opt_hex(nic['profile_schema_sha256']) and isinstance(nic['layout_present'], bool), 'nic_fields')
    port_map, mode_by_cage = _check_layout_record(nic)
    conns = _records(nic['connections'], _CONN_KEYS, 'connection_record')
    for c in conns:
        _need(c['server_class_id'] == nic['server_class_id'] and c['nic_id'] == nic['nic_id'], 'connection_owner')
        _need(_nonempty_str(c['connection_id']) and _is_pos_int(c['target_zone_id'])
              and _is_int(c['port_index']) and c['port_index'] >= 0
              and _is_pos_int(c['ports_per_connection']) and _is_pos_int(c['speed'])
              and _opt_pos_int(c['transceiver_module_type_id']), 'connection_fields')
    _need(len({c['connection_id'] for c in conns}) == len(conns), 'connection_duplicate')
    optics = _records(nic['optics'], _OPTIC_KEYS, 'optic_record')
    for o in optics:
        _need(_is_pos_int(o['module_type_id']) and _opt_pos_int(o['profile_id'])
              and _opt_hex(o['profile_schema_sha256'])
              and (o['breakout_topology'] is None or isinstance(o['breakout_topology'], str))
              and _opt_hex(o['attribute_data_sha256']) and o['attribute_data_sha256'] is not None,
              'optic_fields')
        if nic['layout_present']:
            _need(o['profile_id'] is not None and o['profile_schema_sha256'] is not None
                  and o['breakout_topology'], 'optin_optic_provenance')
    optic_ids = [o['module_type_id'] for o in optics]
    _need(len(set(optic_ids)) == len(optic_ids), 'optic_duplicate')
    fks = {c['transceiver_module_type_id'] for c in conns} - {None}
    _need(fks == set(optic_ids), 'optic_coverage')
    _check_connection_indices(nic, conns)
    if nic['layout_present']:
        _check_mapped_usage(nic, port_map, mode_by_cage, conns, optics, active)
    digest = nic['evidence_sha256']
    _need(isinstance(digest, str) and bool(_HEX64.match(digest)), 'nic_digest')
    body = {k: v for k, v in nic.items() if k != 'evidence_sha256'}
    _need(canonical_sha256(body) == digest, 'nic_digest_mismatch')
    return conns


def _active_classes_from_base(base_snapshot):
    rows = base_snapshot.get('server_classes') if isinstance(base_snapshot, dict) else None
    _need(isinstance(rows, list) and all(isinstance(r, dict) for r in rows), 'base_server_classes')
    return {r.get('server_class_id') for r in rows if _is_pos_int(r.get('quantity'))}


def extension_errors(extension, base_snapshot=None, active_classes=None) -> list:
    """Return [] for a valid snapshot_contract_v1 record, else typed error codes.

    Invalid markers, unknown versions, omitted/duplicate rows, manifest/base
    mismatches, digest mismatches AND internally incoherent layout/mode/used-port/
    bay/optic relationships are all invalid. Activity (optic placement required) is
    derived from the base snapshot's server_classes quantities, or the explicit
    ``active_classes`` set; with neither every class is treated as active (strict).
    Integrity/consistency only, never authenticated history.
    """
    try:
        _need(isinstance(extension, dict), 'not_object')
        _need('status' not in extension, 'invalid_marker')
        _need(set(extension) == _ROOT_KEYS, 'root_keys')
        _need(_is_int(extension['version']) and extension['version'] == EXTENSION_VERSION, 'version')
        nic_keys = _key_pairs(extension['expected_nic_keys'], 'nic_manifest')
        _need(len(nic_keys) > 0, 'nic_manifest_empty')
        conn_keys = _key_pairs(extension['expected_connection_keys'], 'connection_manifest')
        nics = extension['nics']
        _need(isinstance(nics, list), 'nics')
        if active_classes is None and base_snapshot is not None:
            active_classes = _active_classes_from_base(base_snapshot)
        seen_nics, seen_conns, ext_conn_by_key = [], [], {}
        for nic in nics:
            active = True if active_classes is None else (
                isinstance(nic, dict) and nic.get('server_class_id') in active_classes)
            conns = _check_nic(nic, active=active)
            seen_nics.append((nic['server_class_id'], nic['nic_id']))
            seen_conns.extend((c['server_class_id'], c['connection_id']) for c in conns)
            for c in conns:
                ext_conn_by_key[(c['server_class_id'], c['connection_id'])] = c
        _need(len(set(seen_nics)) == len(seen_nics) and sorted(seen_nics) == nic_keys, 'nic_completeness')
        _need(any(nic['layout_present'] for nic in nics), 'no_opted_in_nic')
        _need(len(set(seen_conns)) == len(seen_conns) and sorted(seen_conns) == conn_keys,
              'connection_completeness')
        if base_snapshot is not None:
            base = base_snapshot.get('connections') if isinstance(base_snapshot, dict) else None
            _need(isinstance(base, list) and all(isinstance(r, dict) for r in base), 'base_connections')
            base_keys = sorted((r.get('server_class_id'), r.get('connection_id')) for r in base)
            _need(base_keys == conn_keys, 'base_connection_linkage')
            # Shared connection VALUES, not only identities: the base record and the
            # extension record of the same (server_class_id, connection_id) describe one
            # PlanServerConnection, so speed and ports_per_connection must both be typed
            # positive ints (bool/float/str never coerced) and agree exactly. The base
            # section is not covered by the extension digests, so this cannot rely on
            # rehash detection. target_zone_id is deliberately NOT compared: the base
            # carries a display label string, the extension the integer PK.
            for r in base:
                c = ext_conn_by_key[(r['server_class_id'], r['connection_id'])]
                for field in ('speed', 'ports_per_connection'):
                    _need(_is_pos_int(r.get(field)) and _is_pos_int(c[field])
                          and r[field] == c[field], 'base_connection_fields')
        digest = extension['evidence_sha256']
        _need(isinstance(digest, str) and bool(_HEX64.match(digest)), 'root_digest')
        body = {k: v for k, v in extension.items() if k != 'evidence_sha256'}
        _need(canonical_sha256(body) == digest, 'root_digest_mismatch')
    except _Invalid as exc:
        return [str(exc)]
    except (TypeError, ValueError, KeyError, AttributeError):
        return ['malformed']
    return []


def snapshot_extension_invalid(snapshot) -> bool:
    """True when a snapshot carries the extension key and it is not a valid record."""
    if not isinstance(snapshot, dict) or SNAPSHOT_KEY not in snapshot:
        return False
    return bool(extension_errors(snapshot[SNAPSHOT_KEY], base_snapshot=snapshot))


def preflight_server_class(server_class) -> dict:
    """Backward-compatible per-class helper; prefer capture_plan_layouts(plan)."""
    capture = capture_plan_layouts(server_class.plan)
    from netbox_hedgehog.models.topology_planning import PlanServerNIC

    nic_pks = set(PlanServerNIC.objects.filter(server_class=server_class).values_list('pk', flat=True))
    return {pk: layout for pk, layout in capture.layouts.items() if pk in nic_pks}
