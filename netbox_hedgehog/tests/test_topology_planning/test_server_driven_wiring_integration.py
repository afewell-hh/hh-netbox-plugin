"""
SERVER29: server demand -> leaf/spine sizing -> physical wiring integration tests.

Scope (cases A-H): synthetic server classes (quantity is the only sizing input; every
leaf and spine ``override_quantity`` stays NULL and ``calculated_quantity`` starts at 0) are
run through the real public ``update_plan_calculations(plan)`` and then the real
``DeviceGenerator(plan).generate_all()``. The tests assert the persisted calculated
quantities/summary, GENERATED state, the complete generated device/interface/cable/
Module/ModuleBay inventory and the exact server->leaf and leaf->spine endpoint graph.

Discovery is by baseline PK difference (every Device/Interface/Cable/Module/ModuleBay
created by generation), never by tag/plan metadata filters; ownership metadata is then
asserted on the discovered rows. Expected endpoints come from declared fixture slot
tables and the declared sequential allocation / SAME_SWITCH grouping below; expected
leaf/spine counts are stated literals, not formulas mirroring the implementation.

Case E (9 servers) encodes the #661 accepted equal-spine / exact-distributability rule
(S>=2, each leaf's 4 uplinks split equally over spines): with 20 leaf uplinks and 8
fabric ports per spine, S=2 overloads (10>8), S=3 does not divide 4, so S=4 is the only
feasible count. Historical: initial CI on source 6a51ac4 observed E RED (calculated
spine=3) before generation; repaired calculation is not claimed passing here.

Case F (9 servers, 6 logical uplinks/leaf): 30 uplinks / 8 -> capacity minimum 4,
but 4 and 5 do not divide 6, so S=6 (distinguishes next-feasible from capacity
minimum, power-of-two rounding or a hard-coded 4). Case G (17 servers, 9 leaves x 4
uplinks): minimum ceil(36/8)=5 exceeds the 4 possible equal spines -> structured
spine-class error, no generation. Case H (two active leaf classes, 3x4 + 2x6 uplinks,
8 fabric ports): minimum 3, common equal divisors of 4 and 6 are only 1/2 -> error.

Cases I-N (ADMISSION30) cover generator-side equal-spine admission with an
intentional spine ``override_quantity`` applied after the real calculation: I/J/K
reject at real ``generate_all`` before any INSERT/UPDATE/DELETE/DDL (enforced by a
``connection.execute_wrapper`` around ``generate_all`` only; constructor
get_or_create runs before it), J/K/I preserve inventory row values, cable
terminations, tag memberships and GenerationState; L/M are valid overrides that
still generate exact graphs; N exercises the real authorized Generate POST and
error render (behaviour only, no pixel claim). O uses two disjoint, explicitly ordered
spine FABRIC zones (E1/1-4 then E1/5-8) with an explicit spine override 2 and asserts
the full graph crosses the zone boundary (the calculated spine quantity is captured as
a preservation baseline only, never as an oracle or optimality claim). P removes the
leaf UPLINK declaration after a valid calculation and expects a pre-write
missing-configuration rejection with the same no-mutation proof.

Not covered: real hardware, optics/transceivers/BOM, UI/jobs (except N's specific
synchronous Generate POST journey), whole workbook flows,
YAML export or all fabric families. All device/module models are synthetic
``srv29-*``. Nothing is mocked; no private generator helper is called.
"""

from collections import Counter

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TestCase
from django.urls import reverse

from dcim.models import CableTermination
from extras.models import TaggedItem

from dcim.choices import InterfaceTypeChoices
from dcim.models import (
    Cable,
    Device,
    DeviceType,
    Interface,
    InterfaceTemplate,
    Manufacturer,
    Module,
    ModuleBay,
    ModuleType,
)

from netbox_hedgehog.choices import (
    ConnectionDistributionChoices,
    ConnectionTypeChoices,
    DeviceCategoryChoices,
    FabricClassChoices,
    GenerationStatusChoices,
    HedgehogRoleChoices,
    PortZoneTypeChoices,
    TopologyModeChoices,
)
from netbox_hedgehog.models.topology_planning import (
    BreakoutOption,
    DeviceTypeExtension,
    GenerationState,
    NamingTemplate,
    PlanServerClass,
    PlanServerConnection,
    PlanServerNIC,
    PlanSwitchClass,
    SwitchPortZone,
    TopologyPlan,
)
from netbox_hedgehog.services.device_generator import DeviceGenerator
from netbox_hedgehog.utils.topology_calculations import update_plan_calculations

FABRIC = 'srv29-fabric'
TAG = 'hedgehog-generated'
T100 = InterfaceTypeChoices.TYPE_100GE_QSFP28
T400 = InterfaceTypeChoices.TYPE_400GE_QSFP_DD
T800 = InterfaceTypeChoices.TYPE_800GE_QSFP_DD
NAME_PATTERN = '{class}-{index:02d}'
NIC_ID = 'nic0'
NIC_PORT = f'{NIC_ID}-p0'  # generator prefixes module interface names with nic_id

BREAKOUTS = {
    # breakout_id: (from_speed, logical_ports, logical_speed)
    '1x100g': (100, 1, 100),
    '1x800g': (800, 1, 800),
    '2x400g': (800, 2, 400),
}

# Declared logical-slot tables in sequential allocation order: (name, parent, lane).
NATIVE = {
    'leaf_parents': [1, 2, 3, 4, 5, 6],
    'leaf_server': [(f'E1/{p}', p, None) for p in (1, 2)],
    'leaf_uplink': [(f'E1/{p}', p, None) for p in (3, 4, 5, 6)],
    'spine_parents': [1, 2, 3, 4, 5, 6, 7, 8],
    'spine_fabric': [(f'E1/{p}', p, None) for p in (1, 2, 3, 4, 5, 6, 7, 8)],
    'leaf_native': 100, 'leaf_type': T100, 'spine_native': 100, 'spine_type': T100,
    'leaf_server_spec': '1-2', 'leaf_uplink_spec': '3-6', 'spine_spec': '1-8',
    'breakout': '1x100g', 'supported': ['1x100g'], 'link_type': T100, 'speed': 100,
}
SIX_UPLINK = dict(
    NATIVE,
    leaf_parents=[1, 2, 3, 4, 5, 6, 7, 8],
    leaf_uplink=[(f'E1/{p}', p, None) for p in (3, 4, 5, 6, 7, 8)],
    leaf_uplink_spec='3-8',
)
BREAKOUT = {
    'leaf_parents': [1, 2, 3],
    'leaf_server': [('E1/1/1', 1, 1), ('E1/1/2', 1, 2)],
    'leaf_uplink': [('E1/2/1', 2, 1), ('E1/2/2', 2, 2), ('E1/3/1', 3, 1), ('E1/3/2', 3, 2)],
    'spine_parents': [1, 2, 3, 4],
    'spine_fabric': [(f'E1/{p}/{lane}', p, lane) for p in (1, 2, 3, 4) for lane in (1, 2)],
    'leaf_native': 800, 'leaf_type': T800, 'spine_native': 800, 'spine_type': T800,
    'leaf_server_spec': '1', 'leaf_uplink_spec': '2-3', 'spine_spec': '1-4',
    'breakout': '2x400g', 'supported': ['1x800g', '2x400g'], 'link_type': T400, 'speed': 400,
}


def _breakout(breakout_id):
    from_speed, logical_ports, logical_speed = BREAKOUTS[breakout_id]
    option, _ = BreakoutOption.objects.get_or_create(
        breakout_id=breakout_id,
        defaults={'from_speed': from_speed, 'logical_ports': logical_ports,
                  'logical_speed': logical_speed},
    )
    assert (option.from_speed, option.logical_ports, option.logical_speed) == (
        from_speed, logical_ports, logical_speed,
    ), f'BreakoutOption {breakout_id} has inconsistent pre-existing semantics'
    return option


def _manufacturer():
    manufacturer, _ = Manufacturer.objects.get_or_create(
        name='srv29-synthetic', defaults={'slug': 'srv29-synthetic'},
    )
    return manufacturer


def _switch_ext(model, parents, native_speed, native_type, supported, roles):
    device_type = DeviceType.objects.create(
        manufacturer=_manufacturer(), model=model, slug=model, u_height=1,
    )
    for port in parents:
        InterfaceTemplate.objects.create(device_type=device_type, name=f'E1/{port}', type=native_type)
    return DeviceTypeExtension.objects.create(
        device_type=device_type, mclag_capable=False, hedgehog_roles=roles,
        supported_breakouts=supported, native_speed=native_speed,
    )


def _pks(model):
    return set(model.objects.values_list('pk', flat=True))


INVENTORY_MODELS = (Device, Interface, Cable, Module, ModuleBay)


class ServerDrivenWiringIntegrationTestCase(TestCase):
    """Real update_plan_calculations -> real DeviceGenerator.generate_all."""

    # ---------------------------------------------------------------- fixture

    def _build(self, case, servers, profile):
        self.case = case
        self.p = profile
        self.plan = TopologyPlan.objects.create(name=f'srv29-plan-{case}', customer_name='srv29')
        for category in (DeviceCategoryChoices.SERVER, DeviceCategoryChoices.LEAF,
                         DeviceCategoryChoices.SPINE):
            NamingTemplate.objects.create(plan=self.plan, device_category=category, pattern=NAME_PATTERN)

        leaf_ext = _switch_ext(f'srv29-leaf-{case}', profile['leaf_parents'], profile['leaf_native'],
                               profile['leaf_type'], profile['supported'], ['server-leaf'])
        spine_ext = _switch_ext(f'srv29-spine-{case}', profile['spine_parents'], profile['spine_native'],
                                profile['spine_type'], profile['supported'], ['spine'])
        self.leaf_device_type, self.spine_device_type = leaf_ext.device_type, spine_ext.device_type
        breakout = _breakout(profile['breakout'])

        self.leaf_class = self._switch_class(f'srv29-{case}-leaf', HedgehogRoleChoices.SERVER_LEAF, leaf_ext)
        self.spine_class = self._switch_class(f'srv29-{case}-spine', HedgehogRoleChoices.SPINE, spine_ext)
        self.server_zone_name = f'srv29-{case}-server'
        self.uplink_zone_name = f'srv29-{case}-uplink'
        self.fabric_zone_name = f'srv29-{case}-fabric'
        server_zone = self._zone(self.leaf_class, self.server_zone_name, PortZoneTypeChoices.SERVER,
                                 profile['leaf_server_spec'], breakout)
        self._zone(self.leaf_class, self.uplink_zone_name, PortZoneTypeChoices.UPLINK,
                   profile['leaf_uplink_spec'], breakout)
        self._zone(self.spine_class, self.fabric_zone_name, PortZoneTypeChoices.FABRIC,
                   profile['spine_spec'], breakout)

        # One synthetic server type, one synthetic one-port NIC of the link speed.
        self.server_device_type = DeviceType.objects.create(
            manufacturer=_manufacturer(), model=f'srv29-server-{case}', slug=f'srv29-server-{case}', u_height=1,
        )
        self.nic_module_type = ModuleType.objects.create(
            manufacturer=_manufacturer(), model=f'srv29-nic-{case}-1x{profile["speed"]}g',
        )
        InterfaceTemplate.objects.create(module_type=self.nic_module_type, name='p0', type=profile['link_type'])
        self.server_class = PlanServerClass.objects.create(
            plan=self.plan, server_class_id=f'srv29-{case}-server',
            server_device_type=self.server_device_type, quantity=servers,
        )
        nic = PlanServerNIC.objects.create(
            server_class=self.server_class, nic_id=NIC_ID, module_type=self.nic_module_type,
        )
        PlanServerConnection.objects.create(
            server_class=self.server_class, connection_id=f'srv29-{case}-conn', nic=nic, port_index=0,
            ports_per_connection=1, hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.SAME_SWITCH, target_zone=server_zone,
            speed=profile['speed'],
        )

    def _switch_class(self, class_id, role, ext):
        return PlanSwitchClass.objects.create(
            plan=self.plan, switch_class_id=class_id, fabric_name=FABRIC,
            fabric_class=FabricClassChoices.MANAGED, hedgehog_role=role,
            topology_mode=TopologyModeChoices.SPINE_LEAF, device_type_extension=ext,
            override_quantity=None, calculated_quantity=0,
        )

    @staticmethod
    def _zone(switch_class, name, zone_type, port_spec, breakout):
        return SwitchPortZone.objects.create(
            switch_class=switch_class, zone_name=name, zone_type=zone_type, port_spec=port_spec,
            breakout_option=breakout, allocation_strategy='sequential', priority=100,
        )

    # ------------------------------------------------------------ expectations

    def _names(self, servers, leaves, spines):
        return (
            [f'srv29-{self.case}-server-{i:02d}' for i in range(1, servers + 1)],
            [f'srv29-{self.case}-leaf-{i:02d}' for i in range(1, leaves + 1)],
            [f'srv29-{self.case}-spine-{j:02d}' for j in range(1, spines + 1)],
        )

    def _expected_edges(self, servers, leaves, spines, links_per_pair):
        """Declared fixture expectation.

        SAME_SWITCH: server ordinal i -> leaf floor(i/2), leaf server slot i%2.
        Fabric: sorted leaf i / spine j, k links: leaf_slots[j*k+n] <-> spine_slots[i*k+n].
        """
        server_names, leaf_names, spine_names = self._names(servers, leaves, spines)
        server_edges, fabric_edges = Counter(), Counter()
        for i, server in enumerate(server_names):
            leaf_slot = self.p['leaf_server'][i % 2][0]
            server_edges[(server, NIC_PORT, leaf_names[i // 2], leaf_slot)] += 1
        k = links_per_pair
        for i, leaf in enumerate(leaf_names):
            for j, spine in enumerate(spine_names):
                for n in range(k):
                    fabric_edges[(leaf, self.p['leaf_uplink'][j * k + n][0],
                                  spine, self.p['spine_fabric'][i * k + n][0])] += 1
        return server_edges, fabric_edges

    # --------------------------------------------------------------- execution

    def _calculate(self, leaves, spines):
        for switch_class in (self.leaf_class, self.spine_class):
            switch_class.refresh_from_db()
            self.assertIsNone(switch_class.override_quantity)
        result = update_plan_calculations(self.plan)
        self.assertEqual(result['errors'], [])
        self.assertEqual(result['summary'], {
            self.leaf_class.switch_class_id: {'calculated': leaves, 'override': None, 'effective': leaves},
            self.spine_class.switch_class_id: {'calculated': spines, 'override': None, 'effective': spines},
        })
        for switch_class, expected in ((self.leaf_class, leaves), (self.spine_class, spines)):
            switch_class.refresh_from_db()
            self.assertIsNone(switch_class.override_quantity)
            self.assertEqual(switch_class.calculated_quantity, expected)
            self.assertEqual(switch_class.effective_quantity, expected)

    def _generate(self, devices_total, generated_interfaces, cables_total):
        """Run real generation and check the persisted GenerationState summary.

        ``generated_interfaces`` is the stated literal count of switch-side generated
        endpoints only (device_generator excludes server NIC interfaces and unused
        parent inventory from ``interface_count``); it is never derived from output.
        """
        DeviceGenerator(self.plan).generate_all()
        state = GenerationState.objects.get(plan=self.plan)
        self.assertEqual(state.status, GenerationStatusChoices.GENERATED)
        self.assertFalse(state.mismatch_report)
        self.assertEqual(
            (state.device_count, state.interface_count, state.cable_count),
            (devices_total, generated_interfaces, cables_total),
            'persisted GenerationState (device, switch-endpoint interface, cable) counts',
        )
        for switch_class in (self.leaf_class, self.spine_class):
            switch_class.refresh_from_db()
            self.assertIsNone(switch_class.override_quantity)

    def _capture_baseline(self):
        self.baseline = {model: _pks(model) for model in INVENTORY_MODELS}

    # -------------------------------------------------------------- discovery

    def _new_inventory(self):
        for model, base in self.baseline.items():
            self.assertTrue(base <= _pks(model), f'baseline {model.__name__} removed')
        new = {model: list(model.objects.exclude(pk__in=self.baseline[model])) for model in INVENTORY_MODELS}
        devices = {d.pk: d for d in new[Device]}
        for model in (Interface, Module, ModuleBay):
            for row in new[model]:
                self.assertIn(row.device_id, devices, f'new {model.__name__} {row.pk} on foreign device')
            on_devices = set(model.objects.filter(device_id__in=devices.keys()).values_list('pk', flat=True))
            self.assertEqual(on_devices, {r.pk for r in new[model]}, f'{model.__name__} inventory')
        cable_ids = {c.pk for c in new[Cable]}
        incident = {i.cable_id for i in new[Interface] if i.cable_id is not None}
        self.assertEqual(incident - cable_ids, set(), 'baseline cable attached to generated device')
        cables = list(Cable.objects.filter(pk__in=cable_ids | incident))
        return devices, new[Interface], cables, new[Module], new[ModuleBay]

    # ------------------------------------------------------------- assertions

    def _assert_devices(self, devices, names):
        server_names, leaf_names, spine_names = names
        by_name = {d.name: d for d in devices.values()}
        self.assertEqual(len(by_name), len(devices), 'duplicate device names')
        self.assertEqual(set(by_name), set(server_names) | set(leaf_names) | set(spine_names))
        plan_id = str(self.plan.pk)
        for name, device in by_name.items():
            cf = device.custom_field_data
            self.assertIn(TAG, set(device.tags.values_list('slug', flat=True)), name)
            self.assertEqual(cf.get('hedgehog_plan_id'), plan_id, name)
            if name in server_names:
                self.assertEqual(cf.get('hedgehog_class'), self.server_class.server_class_id, name)
                self.assertEqual(device.role.slug, DeviceCategoryChoices.SERVER, name)
                self.assertEqual(device.device_type, self.server_device_type, name)
                continue
            is_spine = name in spine_names
            switch_class = self.spine_class if is_spine else self.leaf_class
            self.assertEqual(cf.get('hedgehog_class'), switch_class.switch_class_id, name)
            self.assertEqual(cf.get('hedgehog_fabric'), FABRIC, name)
            self.assertEqual(cf.get('hedgehog_fabric_class'), FabricClassChoices.MANAGED, name)
            self.assertEqual(cf.get('hedgehog_role'),
                             HedgehogRoleChoices.SPINE if is_spine else HedgehogRoleChoices.SERVER_LEAF, name)
            self.assertEqual(device.role.slug,
                             DeviceCategoryChoices.SPINE if is_spine else DeviceCategoryChoices.LEAF, name)
            self.assertEqual(device.device_type,
                             self.spine_device_type if is_spine else self.leaf_device_type, name)
        return by_name

    def _assert_nics(self, by_name, server_names, interfaces, modules, bays):
        """Exactly one synthetic NIC module in bay nic0 with exactly one interface p0."""
        plan_id = str(self.plan.pk)
        server_pks = {by_name[n].pk: n for n in server_names}
        self.assertEqual(len(modules), len(server_names), 'unexpected Module count (optics/duplicates)')
        self.assertEqual(len(bays), len(server_names), 'unexpected ModuleBay count')
        for module in modules:
            self.assertIn(module.device_id, server_pks, 'module on non-server device')
            self.assertEqual(module.module_type_id, self.nic_module_type.pk)
            self.assertEqual(module.custom_field_data.get('hedgehog_plan_id'), plan_id)
        for bay in bays:
            self.assertIn(bay.device_id, server_pks, 'module bay on non-server device')
            self.assertEqual(bay.name, NIC_ID)
            self.assertIsNone(bay.module_id, 'NIC bay unexpectedly nested in a module')
        self.assertEqual(Counter(m.device_id for m in modules), Counter({pk: 1 for pk in server_pks}))
        bay_by_device = {b.device_id: b for b in bays}
        module_by_device = {m.device_id: m for m in modules}
        for device_pk, name in server_pks.items():
            self.assertEqual(module_by_device[device_pk].module_bay_id, bay_by_device[device_pk].pk, name)
            ifaces = [i for i in interfaces if i.device_id == device_pk]
            self.assertEqual([i.name for i in ifaces], [NIC_PORT], name)
            self.assertEqual(ifaces[0].module_id, module_by_device[device_pk].pk, name)
            self.assertEqual(ifaces[0].type, self.p['link_type'], name)
            self.assertIsNotNone(ifaces[0].cable_id, f'{name} NIC uncabled')

    def _assert_switch_interfaces(self, by_name, names, interfaces, server_edges, fabric_edges):
        """Complete switch inventory: declared parents + used logical children only."""
        _, leaf_names, spine_names = names
        plan_id = str(self.plan.pk)
        used = {}
        for _, _, leaf, slot in server_edges:
            used.setdefault(leaf, {})[slot] = self.server_zone_name
        for leaf, leaf_slot, spine, spine_slot in fabric_edges:
            used.setdefault(leaf, {})[leaf_slot] = self.uplink_zone_name
            used.setdefault(spine, {})[spine_slot] = self.fabric_zone_name
        per_device = {}
        for iface in interfaces:
            per_device.setdefault(iface.device_id, {})[iface.name] = iface
        for name in leaf_names + spine_names:
            is_spine = name in spine_names
            parents = self.p['spine_parents'] if is_spine else self.p['leaf_parents']
            slots = self.p['spine_fabric'] if is_spine else self.p['leaf_server'] + self.p['leaf_uplink']
            native_type = self.p['spine_type'] if is_spine else self.p['leaf_type']
            slot_meta = {s: (parent, lane) for s, parent, lane in slots}
            device_used = used.get(name, {})
            ifaces = per_device.get(by_name[name].pk, {})
            self.assertEqual(set(ifaces), {f'E1/{p}' for p in parents} | set(device_used), name)
            for slot_name, zone_name in device_used.items():
                parent, lane = slot_meta[slot_name]
                iface = ifaces[slot_name]
                cf = iface.custom_field_data
                self.assertEqual(iface.type, self.p['link_type'], f'{name} {slot_name}')
                self.assertEqual(cf.get('hedgehog_plan_id'), plan_id)
                self.assertEqual(cf.get('hedgehog_zone'), zone_name, f'{name} {slot_name}')
                self.assertEqual(cf.get('hedgehog_physical_port'), parent, f'{name} {slot_name}')
                self.assertEqual(cf.get('hedgehog_breakout_index'), lane, f'{name} {slot_name}')
                self.assertIsNotNone(iface.cable_id, f'{name} {slot_name} uncabled')
                self.assertIn(TAG, set(iface.tags.values_list('slug', flat=True)), f'{name} {slot_name}')
            for iface_name, iface in ifaces.items():
                if iface_name in device_used:
                    continue
                # Breakout parent cage or explicitly-expected unused native slot.
                self.assertEqual(iface.type, native_type, f'{name} {iface_name}')
                self.assertIsNone(iface.cable_id, f'{name} {iface_name} unexpectedly cabled')
                self.assertFalse((iface.custom_field_data or {}).get('hedgehog_zone'), f'{name} {iface_name}')

    def _assert_cables(self, by_name, names, cables, server_edges, fabric_edges):
        server_names, leaf_names, spine_names = names
        plan_id = str(self.plan.pk)
        names_by_pk = {d.pk: n for n, d in by_name.items()}
        actual_server, actual_fabric, used = Counter(), Counter(), Counter()
        for cable in cables:
            self.assertEqual(cable.custom_field_data.get('hedgehog_plan_id'), plan_id, f'cable {cable.pk}')
            self.assertIn(TAG, set(cable.tags.values_list('slug', flat=True)), f'cable {cable.pk}')
            # Generator sets no Cable.type; pinned NetBox 4.4.8 Cable.type is nullable with no
            # explicit default. This synthetic logical graph claims no media qualification.
            self.assertIsNone(cable.type, f'cable {cable.pk} has unexpected type {cable.type!r}')
            a_terms, b_terms = list(cable.a_terminations), list(cable.b_terminations)
            self.assertEqual((len(a_terms), len(b_terms)), (1, 1), f'cable {cable.pk}')
            ends = a_terms + b_terms
            for end in ends:
                self.assertIsInstance(end, Interface)
                self.assertIn(end.device_id, names_by_pk, 'foreign endpoint')
                used[end.pk] += 1
            ends.sort(key=lambda e: (names_by_pk[e.device_id] not in server_names,
                                     names_by_pk[e.device_id] in spine_names))
            first, second = (names_by_pk[e.device_id] for e in ends)
            key = (first, ends[0].name, second, ends[1].name)
            if first in server_names:
                self.assertIn(second, leaf_names, f'server not cabled to leaf: {key}')
                actual_server[key] += 1
            else:
                self.assertEqual((first in leaf_names, second in spine_names), (True, True), f'bad pair {key}')
                actual_fabric[key] += 1
        self.assertEqual({k: v for k, v in used.items() if v > 1}, {}, 'interface reused')
        self.assertEqual(actual_server, server_edges)
        self.assertEqual(actual_fabric, fabric_edges)
        return actual_server + actual_fabric

    def _verify(self, servers, leaves, spines, links_per_pair, cables_total, devices_total):
        names = self._names(servers, leaves, spines)
        server_edges, fabric_edges = self._expected_edges(servers, leaves, spines, links_per_pair)
        self.assertEqual(sum(server_edges.values()) + sum(fabric_edges.values()), cables_total)
        devices, interfaces, cables, modules, bays = self._new_inventory()
        self.assertEqual(len(devices), devices_total)
        by_name = self._assert_devices(devices, names)
        self._assert_nics(by_name, names[0], interfaces, modules, bays)
        self._assert_switch_interfaces(by_name, names, interfaces, server_edges, fabric_edges)
        self.assertEqual(len(cables), cables_total)
        edges = self._assert_cables(by_name, names, cables, server_edges, fabric_edges)
        ids = {Device: set(devices), Interface: {i.pk for i in interfaces}, Cable: {c.pk for c in cables},
               Module: {m.pk for m in modules}, ModuleBay: {b.pk for b in bays}}
        return edges, ids

    def _run(self, servers, leaves, spines, links_per_pair, cables_total, devices_total,
             generated_interfaces):
        self._calculate(leaves, spines)
        self._capture_baseline()
        self._generate(devices_total, generated_interfaces, cables_total)
        return self._verify(servers, leaves, spines, links_per_pair, cables_total, devices_total)

    # ------------------------------------------------------------------ cases
    # GenerationState literals (device, switch-endpoint interface, cable):
    # A/C (14, 40, 24), B (28, 80, 48), E (18, 49, 29); D first A-state then B-state.

    def test_a_native_100g_8_servers(self):
        self._build('a', 8, NATIVE)
        self._run(servers=8, leaves=4, spines=2, links_per_pair=2, cables_total=24, devices_total=14,
                  generated_interfaces=40)

    def test_b_native_100g_16_servers(self):
        self._build('b', 16, NATIVE)
        self._run(servers=16, leaves=8, spines=4, links_per_pair=1, cables_total=48, devices_total=28,
                  generated_interfaces=80)

    def test_c_400g_servers_on_800g_cages_in_2x400(self):
        self._build('c', 8, BREAKOUT)
        self._run(servers=8, leaves=4, spines=2, links_per_pair=2, cables_total=24, devices_total=14,
                  generated_interfaces=40)

    def test_d_quantity_edit_same_plan_regenerates_larger_graph(self):
        self._build('d', 8, NATIVE)
        first_edges, first_ids = self._run(servers=8, leaves=4, spines=2, links_per_pair=2,
                                           cables_total=24, devices_total=14, generated_interfaces=40)
        self.server_class.refresh_from_db()
        self.server_class.quantity = 16
        self.server_class.save()
        self._calculate(leaves=8, spines=4)
        # baseline stays the ORIGINAL pre-first-generation baseline
        self._generate(devices_total=28, generated_interfaces=80, cables_total=48)
        second_edges, second_ids = self._verify(servers=16, leaves=8, spines=4, links_per_pair=1,
                                                cables_total=48, devices_total=28)
        self.assertNotEqual(second_edges, first_edges)
        for model in INVENTORY_MODELS:
            self.assertEqual(first_ids[model] & second_ids[model], set(), f'stale {model.__name__} reused')
            self.assertFalse(model.objects.filter(pk__in=first_ids[model]).exists(),
                             f'first-generation {model.__name__} remains')

    def test_e_native_100g_9_servers_equal_spine_distribution(self):
        # #661: 5 leaves x 4 uplinks; S=2 overloads (10>8), S=3 does not divide 4 -> S=4.
        # Historical: initially observed RED on 6a51ac4 (calculated ceil(20/8)=3).
        self._build('e', 9, NATIVE)
        self._run(servers=9, leaves=5, spines=4, links_per_pair=1, cables_total=29, devices_total=18,
                  generated_interfaces=49)

    def test_f_native_100g_9_servers_six_uplinks_next_feasible_spines(self):
        # 5 leaves x 6 uplinks = 30; ceil(30/8)=4; 4,5 do not divide 6 -> S=6 (k=1).
        self._build('f', 9, SIX_UPLINK)
        self._run(servers=9, leaves=5, spines=6, links_per_pair=1, cables_total=39, devices_total=20,
                  generated_interfaces=69)

    # ------------------------------------------------- infeasible (no generation)

    def _assert_spine_infeasible(self, result, leaf_summary):
        self.assertEqual(result['summary'], leaf_summary)
        self.assertEqual(len(result['errors']), 1, result['errors'])
        error = result['errors'][0]
        self.assertEqual(error['switch_class'], self.spine_class.switch_class_id)
        self.assertIn('equal-spine distribution infeasible', error['error'])
        self.assertIn(self.spine_class.switch_class_id, error['error'])
        self.spine_class.refresh_from_db()
        self.assertIsNone(self.spine_class.override_quantity)
        self.assertEqual(self.spine_class.calculated_quantity, 0)
        for model in INVENTORY_MODELS:
            self.assertEqual(_pks(model), self.baseline[model], f'{model.__name__} inventory changed')
        self.assertFalse(GenerationState.objects.filter(plan=self.plan).exists())

    def test_g_native_100g_17_servers_spine_infeasible(self):
        # 9 leaves x 4 uplinks = 36; minimum ceil(36/8)=5 > 4 equal spines possible.
        self._build('g', 17, NATIVE)
        self.assertIsNone(self.leaf_class.override_quantity)
        self.assertIsNone(self.spine_class.override_quantity)
        self._capture_baseline()
        result = update_plan_calculations(self.plan)
        self._assert_spine_infeasible(result, {
            self.leaf_class.switch_class_id: {'calculated': 9, 'override': None, 'effective': 9},
        })
        self.leaf_class.refresh_from_db()
        self.assertIsNone(self.leaf_class.override_quantity)
        self.assertEqual(self.leaf_class.calculated_quantity, 9)

    def _leaf_class_with_servers(self, case, label, uplink_parents, servers):
        """Separate leaf class (server zone E1/1-2, uplinks on uplink_parents) fed by
        its own one-port server class / NIC type / connection."""
        parents = [1, 2] + list(uplink_parents)
        ext = _switch_ext(f'srv29-leaf-{case}{label}', parents, 100, T100, ['1x100g'], ['server-leaf'])
        breakout = _breakout('1x100g')
        leaf = self._switch_class(f'srv29-{case}{label}-leaf', HedgehogRoleChoices.SERVER_LEAF, ext)
        server_zone = self._zone(leaf, f'srv29-{case}{label}-server', PortZoneTypeChoices.SERVER, '1-2',
                                 breakout)
        self._zone(leaf, f'srv29-{case}{label}-uplink', PortZoneTypeChoices.UPLINK,
                   f'{uplink_parents[0]}-{uplink_parents[-1]}', breakout)
        server_type = DeviceType.objects.create(
            manufacturer=_manufacturer(), model=f'srv29-server-{case}{label}',
            slug=f'srv29-server-{case}{label}', u_height=1,
        )
        nic_type = ModuleType.objects.create(manufacturer=_manufacturer(), model=f'srv29-nic-{case}{label}-1x100g')
        InterfaceTemplate.objects.create(module_type=nic_type, name='p0', type=T100)
        server_class = PlanServerClass.objects.create(
            plan=self.plan, server_class_id=f'srv29-{case}{label}-server',
            server_device_type=server_type, quantity=servers,
        )
        nic = PlanServerNIC.objects.create(server_class=server_class, nic_id=NIC_ID, module_type=nic_type)
        PlanServerConnection.objects.create(
            server_class=server_class, connection_id=f'srv29-{case}{label}-conn', nic=nic, port_index=0,
            ports_per_connection=1, hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.SAME_SWITCH, target_zone=server_zone, speed=100,
        )
        return leaf

    def test_h_two_leaf_classes_no_common_equal_spine_count(self):
        # leaf A: 6 servers -> 3 leaves x 4 uplinks; leaf B: 4 servers -> 2 leaves x 6
        # uplinks; demand 24 / 8 -> minimum 3; equal divisors common to 4 and 6: 1, 2.
        case = 'h'
        self.case = case
        self.plan = TopologyPlan.objects.create(name=f'srv29-plan-{case}', customer_name='srv29')
        for category in (DeviceCategoryChoices.SERVER, DeviceCategoryChoices.LEAF,
                         DeviceCategoryChoices.SPINE):
            NamingTemplate.objects.create(plan=self.plan, device_category=category, pattern=NAME_PATTERN)
        leaf_a = self._leaf_class_with_servers(case, 'a', [3, 4, 5, 6], 6)
        leaf_b = self._leaf_class_with_servers(case, 'b', [3, 4, 5, 6, 7, 8], 4)
        spine_ext = _switch_ext(f'srv29-spine-{case}', list(range(1, 9)), 100, T100, ['1x100g'], ['spine'])
        self.spine_class = self._switch_class(f'srv29-{case}-spine', HedgehogRoleChoices.SPINE, spine_ext)
        self._zone(self.spine_class, f'srv29-{case}-fabric', PortZoneTypeChoices.FABRIC, '1-8',
                   _breakout('1x100g'))
        for switch_class in (leaf_a, leaf_b, self.spine_class):
            self.assertIsNone(switch_class.override_quantity)
            self.assertEqual(switch_class.calculated_quantity, 0)
        self._capture_baseline()
        result = update_plan_calculations(self.plan)
        self._assert_spine_infeasible(result, {
            leaf_a.switch_class_id: {'calculated': 3, 'override': None, 'effective': 3},
            leaf_b.switch_class_id: {'calculated': 2, 'override': None, 'effective': 2},
        })
        for leaf, expected in ((leaf_a, 3), (leaf_b, 2)):
            leaf.refresh_from_db()
            self.assertIsNone(leaf.override_quantity)
            self.assertEqual(leaf.calculated_quantity, expected)

    # ------------------------------------- ADMISSION30: generator equal-spine admission

    def _set_spine_override(self, override, calculated):
        """Intentional caller edit after the real calculation; never via the generator."""
        self.spine_class.refresh_from_db()
        self.assertEqual(self.spine_class.calculated_quantity, calculated)
        self.spine_class.override_quantity = override
        self.spine_class.save()
        self._assert_intent(override, calculated)

    def _assert_intent(self, override, calculated):
        self.spine_class.refresh_from_db()
        self.assertEqual(self.spine_class.override_quantity, override)
        self.assertEqual(self.spine_class.calculated_quantity, calculated)
        self.assertEqual(self.spine_class.effective_quantity, override)
        self.leaf_class.refresh_from_db()
        self.assertIsNone(self.leaf_class.override_quantity)

    def _db_snapshot(self):
        """Full row values (not metadata-filtered) of inventory, terminations, tags, state, intent."""
        snap = {}
        for model in INVENTORY_MODELS + (CableTermination, TaggedItem):
            snap[model.__name__] = list(model.objects.order_by('pk').values())
        snap['GenerationState'] = list(
            GenerationState.objects.filter(plan=self.plan).order_by('pk').values()
        )
        snap['PlanSwitchClass'] = list(
            PlanSwitchClass.objects.filter(plan=self.plan).order_by('pk').values()
        )
        return snap

    def _reject_without_mutation(self, generator):
        """Run real generate_all under a mutation-denying execute_wrapper (generate_all ONLY)."""
        denied = []
        allowed_heads = ('SELECT', 'SAVEPOINT', 'RELEASE', 'ROLLBACK')
        denied_heads = ('INSERT', 'UPDATE', 'DELETE', 'CREATE', 'ALTER', 'DROP', 'TRUNCATE',
                        'RENAME', 'COMMENT', 'GRANT', 'REVOKE', 'COPY', 'MERGE')

        def deny(execute, sql, params, many, context):
            head = sql.lstrip().split(None, 1)[0].upper() if sql.strip() else ''
            if head in denied_heads or head not in allowed_heads:
                denied.append(sql)
                raise AssertionError(f'mutation/unexpected SQL during admission: {sql[:200]}')
            return execute(sql, params, many, context)

        with connection.execute_wrapper(deny):
            with self.assertRaises(ValidationError) as ctx:
                generator.generate_all()
        self.assertEqual(denied, [], 'SQL mutation attempted before admission rejection')
        return ' '.join(ctx.exception.messages)

    def _assert_equal_spine_message(self, message, *fragments):
        self.assertIn('equal-spine distribution infeasible', message)
        self.assertIn(f"fabric '{FABRIC}'", message)
        self.assertIn(self.spine_class.switch_class_id, message)
        for fragment in fragments:
            self.assertIn(fragment, message)

    def _generate_with_override(self, override, calculated, devices_total, generated_interfaces,
                                cables_total):
        """Public generator with intentional override; the NULL-override _generate is unchanged."""
        self._assert_intent(override, calculated)
        DeviceGenerator(self.plan).generate_all()
        state = GenerationState.objects.get(plan=self.plan)
        self.assertEqual(state.status, GenerationStatusChoices.GENERATED)
        self.assertFalse(state.mismatch_report)
        self.assertEqual(
            (state.device_count, state.interface_count, state.cable_count),
            (devices_total, generated_interfaces, cables_total),
            'persisted GenerationState (device, switch-endpoint interface, cable) counts',
        )
        self._assert_intent(override, calculated)

    def test_i_native_override_three_spines_rejected_indivisible(self):
        # 4 leaves x 4 uplinks over S=3: capacity 4*2=8 would fit, but 4 -> 2/1/1 is unequal.
        self._build('i', 8, NATIVE)
        self._calculate(leaves=4, spines=2)
        self._set_spine_override(3, calculated=2)
        self._capture_baseline()
        generator = DeviceGenerator(self.plan)  # default Site/Tag get_or_create before denial
        before = self._db_snapshot()
        message = self._reject_without_mutation(generator)
        self._assert_equal_spine_message(
            message, self.leaf_class.switch_class_id, '4 logical uplinks',
            'not divisible by spine count 3',
        )
        self.assertEqual(self._db_snapshot(), before)
        for model in INVENTORY_MODELS:
            self.assertEqual(_pks(model), self.baseline[model], f'{model.__name__} inventory changed')
        self.assertFalse(GenerationState.objects.filter(plan=self.plan).exists())
        self._assert_intent(3, calculated=2)

    def test_j_regenerate_after_invalid_override_preserves_prior_generation(self):
        self._build('j', 8, NATIVE)
        _, first_ids = self._run(servers=8, leaves=4, spines=2, links_per_pair=2, cables_total=24,
                                 devices_total=14, generated_interfaces=40)
        self._set_spine_override(3, calculated=2)
        generator = DeviceGenerator(self.plan)
        before = self._db_snapshot()  # after intent edit and constructor setup
        self.assertEqual(len(before['GenerationState']), 1)
        message = self._reject_without_mutation(generator)
        self._assert_equal_spine_message(message, '4 logical uplinks', 'not divisible by spine count 3')
        after = self._db_snapshot()
        self.assertEqual(after, before, 'prior generated rows/terminations/tags/state changed')
        for model in INVENTORY_MODELS:
            self.assertTrue(first_ids[model] <= _pks(model), f'first-generation {model.__name__} lost')
        state = GenerationState.objects.get(plan=self.plan)
        self.assertEqual(state.status, GenerationStatusChoices.GENERATED)
        self.assertEqual((state.device_count, state.interface_count, state.cable_count), (14, 40, 24))
        self._assert_intent(3, calculated=2)

    def test_k_six_uplink_override_three_spines_rejected_capacity(self):
        # 5 leaves x 6 uplinks, S=3: 6%3==0 but 5*2=10 > 8 fabric ports per spine.
        self._build('k', 9, SIX_UPLINK)
        self._calculate(leaves=5, spines=6)
        self._set_spine_override(3, calculated=6)
        self._capture_baseline()
        generator = DeviceGenerator(self.plan)
        before = self._db_snapshot()
        message = self._reject_without_mutation(generator)
        self._assert_equal_spine_message(message, 'needs 10 fabric ports', 'capacity 8')
        self.assertNotIn('not divisible', message)
        self.assertEqual(self._db_snapshot(), before)
        for model in INVENTORY_MODELS:
            self.assertEqual(_pks(model), self.baseline[model], f'{model.__name__} inventory changed')
        self.assertFalse(GenerationState.objects.filter(plan=self.plan).exists())
        self._assert_intent(3, calculated=6)

    def test_l_six_uplink_valid_override_three_generates_exact_graph(self):
        self._build('l', 8, SIX_UPLINK)
        self._calculate(leaves=4, spines=3)
        self._set_spine_override(3, calculated=3)
        self._capture_baseline()
        self._generate_with_override(3, 3, devices_total=15, generated_interfaces=56, cables_total=32)
        self._verify(servers=8, leaves=4, spines=3, links_per_pair=2, cables_total=32, devices_total=15)

    def test_m_native_valid_override_four_above_minimum_generates_exact_graph(self):
        self._build('m', 8, NATIVE)
        self._calculate(leaves=4, spines=2)
        self._set_spine_override(4, calculated=2)
        self._capture_baseline()
        self._generate_with_override(4, 2, devices_total=16, generated_interfaces=40, cables_total=24)
        self._verify(servers=8, leaves=4, spines=4, links_per_pair=1, cables_total=24, devices_total=16)

    def test_n_generate_post_renders_equal_spine_error(self):
        # Synthetic NULL transceiver FKs: preflight readiness is legitimately ready.
        self._build('n', 8, NATIVE)
        self._calculate(leaves=4, spines=2)
        self._set_spine_override(3, calculated=2)
        self._capture_baseline()
        user = get_user_model().objects.create_superuser(
            username='srv29-admission-admin', email='srv29-admin@example.invalid', password='unused-pw',
        )
        self.client.force_login(user)
        url = reverse('plugins:netbox_hedgehog:topologyplan_generate', kwargs={'pk': self.plan.pk})
        response = self.client.post(url, follow=True)
        self.assertEqual(response.redirect_chain, [(url, 302)])
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Generation failed')
        self.assertContains(response, 'equal-spine distribution infeasible')
        self.assertContains(response, 'not divisible by spine count 3')
        self.assertContains(response, self.spine_class.switch_class_id)
        for model in INVENTORY_MODELS:
            self.assertEqual(_pks(model), self.baseline[model], f'{model.__name__} inventory changed')
        self.assertFalse(GenerationState.objects.filter(plan=self.plan).exists())
        self._assert_intent(3, calculated=2)

    # ----------------------------------- O: two disjoint spine FABRIC zones (cursor-aware)

    # Declared fixture tables: zone A then zone B, explicit priority order.
    O_SPINE_ZONES = (
        # (zone suffix, port_spec, priority)
        ('fabric-a', '1-4', 100),
        ('fabric-b', '5-8', 200),
    )
    # Declared spine slot -> (zone suffix, physical parent); every spine uses all 8.
    O_SPINE_SLOT_ZONE = {
        'E1/1': ('fabric-a', 1), 'E1/2': ('fabric-a', 2),
        'E1/3': ('fabric-a', 3), 'E1/4': ('fabric-a', 4),
        'E1/5': ('fabric-b', 5), 'E1/6': ('fabric-b', 6),
        'E1/7': ('fabric-b', 7), 'E1/8': ('fabric-b', 8),
    }

    def _o_split_spine_fabric_zones(self):
        SwitchPortZone.objects.filter(
            switch_class=self.spine_class, zone_type=PortZoneTypeChoices.FABRIC,
        ).delete()
        breakout = _breakout(self.p['breakout'])
        for suffix, spec, priority in self.O_SPINE_ZONES:
            SwitchPortZone.objects.create(
                switch_class=self.spine_class, zone_name=f'srv29-{self.case}-{suffix}',
                zone_type=PortZoneTypeChoices.FABRIC, port_spec=spec, breakout_option=breakout,
                allocation_strategy='sequential', priority=priority,
            )
        self.assertEqual(
            list(SwitchPortZone.objects.filter(
                switch_class=self.spine_class, zone_type=PortZoneTypeChoices.FABRIC,
            ).order_by('priority', 'zone_name').values_list('zone_name', 'port_spec', 'priority')),
            [(f'srv29-{self.case}-{s}', spec, pr) for s, spec, pr in self.O_SPINE_ZONES],
        )

    def _o_assert_spine_interfaces(self, by_name, spine_names, interfaces):
        """All 8 spine interfaces per device: exact zone/plan/parent/lane/type/tag/cable, no extras."""
        plan_id = str(self.plan.pk)
        per_device = {}
        for iface in interfaces:
            per_device.setdefault(iface.device_id, {})[iface.name] = iface
        for name in spine_names:
            ifaces = per_device.get(by_name[name].pk, {})
            self.assertEqual(set(ifaces), set(self.O_SPINE_SLOT_ZONE), f'{name} interface set')
            for slot_name, (suffix, parent) in self.O_SPINE_SLOT_ZONE.items():
                iface = ifaces[slot_name]
                cf = iface.custom_field_data
                self.assertEqual(iface.type, self.p['link_type'], f'{name} {slot_name}')
                self.assertEqual(cf.get('hedgehog_plan_id'), plan_id, f'{name} {slot_name}')
                self.assertEqual(cf.get('hedgehog_zone'), f'srv29-{self.case}-{suffix}', f'{name} {slot_name}')
                self.assertEqual(cf.get('hedgehog_physical_port'), parent, f'{name} {slot_name}')
                self.assertIsNone(cf.get('hedgehog_breakout_index'), f'{name} {slot_name}')
                self.assertIsNotNone(iface.cable_id, f'{name} {slot_name} uncabled')
                self.assertIn(TAG, set(iface.tags.values_list('slug', flat=True)), f'{name} {slot_name}')

    def test_o_two_spine_fabric_zones_cross_zone_boundary(self):
        self._build('o', 8, NATIVE)
        self._o_split_spine_fabric_zones()
        for switch_class in (self.leaf_class, self.spine_class):
            switch_class.refresh_from_db()
            self.assertIsNone(switch_class.override_quantity)
        result = update_plan_calculations(self.plan)
        self.assertEqual(result['summary'].get(self.leaf_class.switch_class_id),
                         {'calculated': 4, 'override': None, 'effective': 4})
        self.leaf_class.refresh_from_db()
        self.assertIsNone(self.leaf_class.override_quantity)
        self.assertEqual(self.leaf_class.calculated_quantity, 4)
        self.spine_class.refresh_from_db()
        calculated_spines = self.spine_class.calculated_quantity  # preservation baseline only
        self._set_spine_override(2, calculated=calculated_spines)
        self._capture_baseline()
        self._generate_with_override(2, calculated_spines, devices_total=14, generated_interfaces=40,
                                     cables_total=24)

        servers, leaves, spines, k, cables_total, devices_total = 8, 4, 2, 2, 24, 14
        names = self._names(servers, leaves, spines)
        server_edges, fabric_edges = self._expected_edges(servers, leaves, spines, k)
        self.assertEqual(sum(server_edges.values()) + sum(fabric_edges.values()), cables_total)
        devices, interfaces, cables, modules, bays = self._new_inventory()
        self.assertEqual(len(devices), devices_total)
        by_name = self._assert_devices(devices, names)
        self._assert_nics(by_name, names[0], interfaces, modules, bays)
        # Old one-zone helper on leaves only; spines verified separately per declared zone table.
        self._assert_switch_interfaces(by_name, (names[0], names[1], []), interfaces,
                                       server_edges, fabric_edges)
        self._o_assert_spine_interfaces(by_name, names[2], interfaces)
        switch_pks = {by_name[n].pk for n in names[1] + names[2]}
        self.assertEqual(sum(1 for i in interfaces if i.device_id in switch_pks), 4 * 6 + 2 * 8,
                         'switch interface inventory has extras')
        self.assertEqual(len(cables), cables_total)
        self._assert_cables(by_name, names, cables, server_edges, fabric_edges)
        # Explicit cross-boundary edges: leaf-03/04 land on spine zone B ports 5..8.
        for spine in names[2]:
            for leaf, ports in ((names[1][0], ('E1/1', 'E1/2')), (names[1][1], ('E1/3', 'E1/4')),
                                (names[1][2], ('E1/5', 'E1/6')), (names[1][3], ('E1/7', 'E1/8'))):
                self.assertEqual(
                    sorted(e[3] for e in fabric_edges if e[0] == leaf and e[2] == spine), list(ports),
                )
        self._assert_intent(2, calculated_spines)

    # --------------------------------------------- P: missing leaf UPLINK declaration

    def test_p_missing_leaf_uplink_zone_rejected_before_writes(self):
        self._build('p', 8, NATIVE)
        self._calculate(leaves=4, spines=2)
        SwitchPortZone.objects.filter(
            switch_class=self.leaf_class, zone_type=PortZoneTypeChoices.UPLINK,
        ).delete()
        self.assertFalse(self.leaf_class.port_zones.filter(zone_type=PortZoneTypeChoices.UPLINK).exists())
        self._set_spine_override(2, calculated=2)
        self.leaf_class.refresh_from_db()
        self.assertEqual(self.leaf_class.effective_quantity, 4)
        self._capture_baseline()
        generator = DeviceGenerator(self.plan)
        before = self._db_snapshot()
        zones_before = list(SwitchPortZone.objects.filter(
            switch_class__plan=self.plan).order_by('pk').values())
        message = self._reject_without_mutation(generator)
        self.assertIn('missing configuration', message)
        self.assertIn(f"fabric '{FABRIC}'", message)
        self.assertIn(self.leaf_class.switch_class_id, message)
        self.assertIn('no UPLINK port zones', message)
        self.assertNotIn('equal-spine distribution infeasible', message)
        self.assertEqual(self._db_snapshot(), before)
        self.assertEqual(list(SwitchPortZone.objects.filter(
            switch_class__plan=self.plan).order_by('pk').values()), zones_before)
        for model in INVENTORY_MODELS:
            self.assertEqual(_pks(model), self.baseline[model], f'{model.__name__} inventory changed')
        self.assertFalse(GenerationState.objects.filter(plan=self.plan).exists())
        self._assert_intent(2, calculated=2)
        self.assertEqual(self.leaf_class.calculated_quantity, 4)

    # ------------------------------- SCALE34 Q-AH: frozen server-scale boundary matrix

    def _scale_profile(self, name):
        """Return an independent new copy of a declared SCALE34 slot table.

        native8/breakout8 are unchanged copies of NATIVE/BREAKOUT. native16/six12 extend
        only the native spine (parents/slots 1..16 or 1..12, spec 1-16/1-12); ten20 also
        extends the native leaf (parents 1..12, uplinks E1/3..E1/12, spec 3-12) and the
        spine (1..20). Every slot is a native parent with lane None; one zone per role, the
        two leaf server slots E1/1-2 are kept. Existing module profiles are never mutated.
        """
        def native(ports):
            return [(f'E1/{p}', p, None) for p in ports]

        if name == 'native8':
            profile = dict(NATIVE)
        elif name == 'breakout8':
            profile = dict(BREAKOUT)
        elif name == 'native16':
            profile = dict(NATIVE, spine_parents=list(range(1, 17)),
                           spine_fabric=native(range(1, 17)), spine_spec='1-16')
        elif name == 'six12':
            profile = dict(SIX_UPLINK, spine_parents=list(range(1, 13)),
                           spine_fabric=native(range(1, 13)), spine_spec='1-12')
        elif name == 'ten20':
            profile = dict(NATIVE, leaf_parents=list(range(1, 13)),
                           leaf_uplink=native(range(3, 13)), leaf_uplink_spec='3-12',
                           spine_parents=list(range(1, 21)),
                           spine_fabric=native(range(1, 21)), spine_spec='1-20')
        else:
            self.fail(f'undeclared SCALE34 profile {name!r}')
        for key in ('leaf_parents', 'leaf_server', 'leaf_uplink', 'spine_parents', 'spine_fabric'):
            profile[key] = list(profile[key])  # no list shared with a module profile
        source = BREAKOUT if name == 'breakout8' else NATIVE
        self.assertEqual(profile['leaf_server'], source['leaf_server'], 'two leaf server slots preserved')
        self.assertEqual(len(profile['leaf_server']), 2)
        return profile

    def _scale_positive(self, case, profile_name, servers, leaves, spines, links_per_pair,
                        cables_total, devices_total, generated_interfaces):
        """Frozen matrix positive row through existing _build/_run.

        Real update_plan_calculations and DeviceGenerator.generate_all; expected graph is the
        existing declared sequential slot oracle (_expected_edges); all counts are literals
        from matrix.json, never derived from output or a production sizing helper.
        """
        self._build(case, servers, self._scale_profile(profile_name))
        self._run(servers=servers, leaves=leaves, spines=spines, links_per_pair=links_per_pair,
                  cables_total=cables_total, devices_total=devices_total,
                  generated_interfaces=generated_interfaces)

    def _scale_negative(self, case, profile_name, servers, leaves):
        """Frozen matrix negative row: spine demand crosses maximum feasible equal capacity.

        Asserts only the real calculation rejection (structured spine-class error, literal
        leaf summary, spine calculated 0, no overrides, unchanged inventory, no
        GenerationState). generate_all is deliberately NOT called; no generator-rejection or
        no-SQL claim is made for these rows.
        """
        self._build(case, servers, self._scale_profile(profile_name))
        self.assertIsNone(self.leaf_class.override_quantity)
        self.assertIsNone(self.spine_class.override_quantity)
        self._capture_baseline()
        result = update_plan_calculations(self.plan)
        self._assert_spine_infeasible(result, {
            self.leaf_class.switch_class_id: {'calculated': leaves, 'override': None, 'effective': leaves},
        })
        self.leaf_class.refresh_from_db()
        self.assertIsNone(self.leaf_class.override_quantity)
        self.assertEqual(self.leaf_class.calculated_quantity, leaves)
        self.assertEqual(self.leaf_class.effective_quantity, leaves)

    def test_q_native8_6_servers_3_leaves_2_spines(self):
        self._scale_positive('q', 'native8', 6, 3, 2, 2, 18, 11, 30)

    def test_r_native8_7_servers_odd_last_leaf(self):
        self._scale_positive('r', 'native8', 7, 4, 2, 2, 23, 13, 39)

    def test_s_native8_10_servers_4_spines(self):
        # 5 leaves x 4 = 20 uplinks; S=2 overloads (10>8), 3 does not divide 4 -> 4.
        self._scale_positive('s', 'native8', 10, 5, 4, 1, 30, 19, 50)

    def test_t_native8_15_servers_full_spine_capacity(self):
        self._scale_positive('t', 'native8', 15, 8, 4, 1, 47, 27, 79)

    def test_u_breakout8_7_servers(self):
        self._scale_positive('u', 'breakout8', 7, 4, 2, 2, 23, 13, 39)

    def test_v_breakout8_15_servers_full_logical_capacity(self):
        self._scale_positive('v', 'breakout8', 15, 8, 4, 1, 47, 27, 79)

    def test_w_native16_17_servers(self):
        self._scale_positive('w', 'native16', 17, 9, 4, 1, 53, 30, 89)

    def test_x_native16_31_servers(self):
        self._scale_positive('x', 'native16', 31, 16, 4, 1, 95, 51, 159)

    def test_y_native16_32_servers_max_capacity(self):
        self._scale_positive('y', 'native16', 32, 16, 4, 1, 96, 52, 160)

    def test_z_six12_9_servers_3_spines_not_power_of_two(self):
        # 5 leaves x 6 = 30 uplinks / 12 -> minimum 3; 3 divides 6 -> S=3 (not 4).
        self._scale_positive('z', 'six12', 9, 5, 3, 2, 39, 17, 69)

    def test_aa_six12_17_servers_6_spines(self):
        self._scale_positive('aa', 'six12', 17, 9, 6, 1, 71, 32, 125)

    def test_ab_six12_23_servers_max_capacity(self):
        self._scale_positive('ab', 'six12', 23, 12, 6, 1, 95, 41, 167)

    def test_ac_ten20_17_servers_5_spines_not_power_of_two(self):
        # 9 leaves x 10 = 90 uplinks / 20 -> minimum 5; 5 divides 10 -> S=5 (not 8).
        self._scale_positive('ac', 'ten20', 17, 9, 5, 2, 107, 31, 197)

    def test_ad_ten20_31_servers_10_spines(self):
        self._scale_positive('ad', 'ten20', 31, 16, 10, 1, 191, 57, 351)

    def test_ae_ten20_39_servers_20_leaves_10_spines(self):
        self._scale_positive('ae', 'ten20', 39, 20, 10, 1, 239, 69, 439)

    def test_af_native16_33_servers_spine_infeasible(self):
        # 17 leaves; at S=4 each spine needs 17 > 16 fabric ports.
        self._scale_negative('af', 'native16', 33, 17)

    def test_ag_six12_25_servers_spine_infeasible(self):
        # 13 leaves; at S=6 each spine needs 13 > 12 fabric ports.
        self._scale_negative('ag', 'six12', 25, 13)

    def test_ah_ten20_41_servers_spine_infeasible(self):
        # 21 leaves; at S=10 each spine needs 21 > 20 fabric ports.
        self._scale_negative('ah', 'ten20', 41, 21)

    # --------------------- ARTIFACT35 AI-AO: generated graph -> public YAML + export GET
    # Real update_plan_calculations -> DeviceGenerator.generate_all -> public
    # generate_yaml_for_plan and the existing authenticated export route. Profile labels
    # are synthetic, non-bundled fixture declarations (no real-hardware/profile claim).
    # The graph oracle is the declared slot table (_names/_expected_edges), never the
    # YAML generator. No hhfab/schema, optics/BOM, workbook or pixel qualification.

    def _a35_assign_profiles(self, profile_name):
        """Explicit fixture intent BEFORE generation: fictional leaf/spine profile labels."""
        labels = {}
        for switch_class, role in ((self.leaf_class, 'leaf'), (self.spine_class, 'spine')):
            label = f'artifact35-{profile_name}-{role}'
            ext = switch_class.device_type_extension
            ext.refresh_from_db()
            self.assertFalse(ext.hedgehog_profile_name, 'fixture extension unexpectedly pre-profiled')
            ext.hedgehog_profile_name = label
            ext.save()
            ext.refresh_from_db()
            self.assertEqual(ext.hedgehog_profile_name, label)
            labels[role] = label
        return labels

    def _a35_login(self, superuser=True):
        """User/session setup happens before any snapshot or read-only boundary."""
        model = get_user_model()
        username = f'artifact35-{self.case}-{"admin" if superuser else "noperm"}'
        if superuser:
            user = model.objects.create_superuser(
                username=username, email=f'{username}@example.invalid', password=None,
            )
        else:
            user = model.objects.create_user(
                username=username, email=f'{username}@example.invalid', password=None,
            )
        self.client.force_login(user)
        return user

    def _a35_export_url(self):
        return reverse('plugins:netbox_hedgehog:topologyplan_export', args=[self.plan.pk])

    def _a35_snapshot(self):
        """Full row values: existing _db_snapshot plus plan intent and profile/type rows."""
        snap = self._db_snapshot()
        snap['TopologyPlan'] = list(TopologyPlan.objects.filter(pk=self.plan.pk).values())
        snap['NamingTemplate'] = list(NamingTemplate.objects.filter(plan=self.plan).order_by('pk').values())
        snap['PlanServerClass'] = list(PlanServerClass.objects.filter(plan=self.plan).order_by('pk').values())
        snap['PlanServerNIC'] = list(
            PlanServerNIC.objects.filter(server_class__plan=self.plan).order_by('pk').values()
        )
        snap['PlanServerConnection'] = list(
            PlanServerConnection.objects.filter(server_class__plan=self.plan).order_by('pk').values()
        )
        snap['SwitchPortZone'] = list(
            SwitchPortZone.objects.filter(switch_class__plan=self.plan).order_by('pk').values()
        )
        for model in (DeviceTypeExtension, BreakoutOption, DeviceType, ModuleType, InterfaceTemplate):
            snap[model.__name__] = list(model.objects.order_by('pk').values())
        return snap

    def _a35_guarded(self, operation):
        """Run ONE export operation under a wrapper rejecting any non-read SQL."""
        attempts = []
        allowed_heads = ('SELECT', 'SAVEPOINT', 'RELEASE', 'ROLLBACK', 'BEGIN', 'COMMIT')

        def guard(execute, sql, params, many, context):
            text = sql.strip() if isinstance(sql, str) else str(sql).strip()
            head = text.split(None, 1)[0].upper() if text else ''
            if head not in allowed_heads:
                attempts.append(text[:200])
                raise AssertionError(f'mutation/unexpected SQL during export: {text[:200]}')
            return execute(sql, params, many, context)

        with connection.execute_wrapper(guard):
            result = operation()
        self.assertEqual(attempts, [], 'SQL mutation/unexpected statement attempted during export')
        return result

    def _a35_port(self, endpoint):
        """Split '<device>/<interface>' at the FIRST slash only (keeps E1/x/y breakouts)."""
        self.assertIsInstance(endpoint, dict)
        self.assertEqual(set(endpoint), {'port'}, endpoint)
        port = endpoint['port']
        self.assertIsInstance(port, str)
        device, sep, iface = port.partition('/')
        self.assertEqual(sep, '/', port)
        self.assertTrue(device and iface, port)
        return device, iface

    def _a35_assert_artifact(self, text, servers, leaves, spines, links_per_pair, cables_total, labels):
        """Parse and validate a complete wiring artifact against the declared fixture graph."""
        import re
        import yaml

        wiring = 'wiring.githedgehog.com/v1beta1'
        dns = re.compile(r'^[a-z0-9]([-a-z0-9]*[a-z0-9])?$')
        api_re = re.compile(r'^[a-z0-9]([-a-z0-9.]*[a-z0-9])?/v[0-9a-z]+$')
        self.assertIsInstance(text, str)
        docs = list(yaml.safe_load_all(text))
        self.assertTrue(docs, 'empty artifact')
        identities, by_kind = Counter(), {}
        for doc in docs:
            self.assertIsInstance(doc, dict, f'unstructured document {doc!r}')
            self.assertEqual(set(doc), {'apiVersion', 'kind', 'metadata', 'spec'}, doc)
            api, kind, meta = doc['apiVersion'], doc['kind'], doc['metadata']
            self.assertIsInstance(api, str)
            self.assertRegex(api, api_re)
            self.assertIsInstance(kind, str)
            self.assertTrue(kind)
            self.assertIsInstance(meta, dict)
            self.assertEqual(set(meta), {'name', 'namespace'}, meta)
            for value in (meta['name'], meta['namespace']):
                self.assertIsInstance(value, str)
                self.assertLessEqual(len(value), 63, value)
                self.assertRegex(value, dns)
            identities[(api, kind, meta['namespace'], meta['name'])] += 1
            by_kind.setdefault(kind, []).append(doc)
        self.assertEqual({i: n for i, n in identities.items() if n > 1}, {}, 'duplicate identity')

        server_names, leaf_names, spine_names = self._names(servers, leaves, spines)
        connection_docs = servers + leaves * spines
        self.assertEqual(
            Counter({kind: len(items) for kind, items in by_kind.items()}),
            Counter({'VLANNamespace': 1, 'IPv4Namespace': 1, 'Switch': leaves + spines,
                     'Server': servers, 'Connection': connection_docs}),
            'artifact document kinds/counts (foundational namespaces counted separately)',
        )

        switches = {}
        for doc in by_kind['Switch']:
            self.assertEqual(doc['apiVersion'], wiring)
            spec = doc['spec']
            self.assertIsInstance(spec, dict)
            self.assertIsInstance(spec.get('boot'), dict)
            self.assertTrue(spec['boot'].get('mac'))
            switches[doc['metadata']['name']] = (spec.get('role'), spec.get('profile'))
        expected_switches = {n: (HedgehogRoleChoices.SERVER_LEAF, labels['leaf']) for n in leaf_names}
        expected_switches.update({n: (HedgehogRoleChoices.SPINE, labels['spine']) for n in spine_names})
        self.assertEqual(switches, expected_switches, 'Switch identities/roles/profile labels')
        for doc in by_kind['Server']:
            self.assertEqual(doc['apiVersion'], wiring)
            self.assertIsInstance(doc['spec'], dict)
        self.assertEqual({d['metadata']['name'] for d in by_kind['Server']}, set(server_names))

        allowed_ifaces = {n: {NIC_PORT} for n in server_names}
        allowed_ifaces.update({n: {s[0] for s in self.p['leaf_server'] + self.p['leaf_uplink']}
                               for n in leaf_names})
        allowed_ifaces.update({n: {s[0] for s in self.p['spine_fabric']} for n in spine_names})
        server_links, fabric_links, endpoints, pairs = Counter(), Counter(), Counter(), Counter()
        modes = Counter()
        for doc in by_kind['Connection']:
            self.assertEqual(doc['apiVersion'], wiring)
            spec = doc['spec']
            self.assertIsInstance(spec, dict)
            self.assertEqual(len(spec), 1, f'connection has multiple/no modes: {spec}')
            (mode, body), = spec.items()
            self.assertIn(mode, ('unbundled', 'fabric'), f'unexpected connection mode {mode!r}')
            modes[mode] += 1
            self.assertIsInstance(body, dict)
            if mode == 'unbundled':
                self.assertEqual(set(body), {'link'}, body)
                link = body['link']
                self.assertIsInstance(link, dict)
                self.assertEqual(set(link), {'server', 'switch'}, link)
                server, switch = self._a35_port(link['server']), self._a35_port(link['switch'])
                self.assertIn(server[0], server_names, server)
                self.assertIn(switch[0], leaf_names, switch)
                server_links[server + switch] += 1
                endpoints[server] += 1
                endpoints[switch] += 1
                continue
            self.assertEqual(set(body), {'links'}, body)
            self.assertIsInstance(body['links'], list)
            self.assertTrue(body['links'], 'fabric connection without links')
            doc_pairs = set()
            for link in body['links']:
                self.assertIsInstance(link, dict)
                self.assertEqual(set(link), {'leaf', 'spine'}, link)
                leaf, spine = self._a35_port(link['leaf']), self._a35_port(link['spine'])
                self.assertIn(leaf[0], leaf_names, leaf)
                self.assertIn(spine[0], spine_names, spine)
                fabric_links[leaf + spine] += 1
                endpoints[leaf] += 1
                endpoints[spine] += 1
                doc_pairs.add((leaf[0], spine[0]))
            self.assertEqual(len(doc_pairs), 1, f'fabric connection mixes pairs {doc_pairs}')
            pairs[doc_pairs.pop()] += 1

        server_edges, fabric_edges = self._expected_edges(servers, leaves, spines, links_per_pair)
        self.assertEqual(modes, Counter({'unbundled': servers, 'fabric': leaves * spines}))
        self.assertEqual(pairs, Counter({(l, s): 1 for l in leaf_names for s in spine_names}))
        self.assertEqual(server_links, server_edges, 'exported server links')
        self.assertEqual(fabric_links, fabric_edges, 'exported fabric links')
        self.assertEqual(sum(server_links.values()) + sum(fabric_links.values()), cables_total)
        self.assertEqual({e: n for e, n in endpoints.items() if n > 1}, {}, 'endpoint exported twice')
        expected_endpoints = set()
        for edge in list(server_edges) + list(fabric_edges):
            expected_endpoints.update({edge[:2], edge[2:]})
        self.assertEqual(set(endpoints), expected_endpoints)
        for device, iface in endpoints:
            self.assertIn(iface, allowed_ifaces[device], f'{device}/{iface} not a declared slot')
        return docs, (server_links, fabric_links)

    def _a35_export(self, servers, leaves, spines, links_per_pair, cables_total, labels):
        """Public service + authenticated GET + repeat GET, all read-only; returns bytes, graph."""
        import json
        from netbox_hedgehog.services.yaml_generator import generate_yaml_for_plan

        url = self._a35_export_url()
        before = self._a35_snapshot()
        service_text = self._a35_guarded(lambda: generate_yaml_for_plan(self.plan))
        first = self._a35_guarded(lambda: self.client.get(url))
        repeat = self._a35_guarded(lambda: self.client.get(url))
        self.assertEqual(self._a35_snapshot(), before, 'export changed persisted rows')
        disposition = f'attachment; filename="{self.plan.name}-{FABRIC}.yaml"'
        for response in (first, repeat):
            self.assertEqual(response.status_code, 200, response.content[:500])
            self.assertEqual(response['Content-Type'], 'text/yaml; charset=utf-8')
            self.assertEqual(response['Content-Disposition'], disposition)
        self.assertEqual(first.content, repeat.content, 'repeat download not byte-identical')
        args = (servers, leaves, spines, links_per_pair, cables_total, labels)
        service_docs, _ = self._a35_assert_artifact(service_text, *args)
        download_docs, graph = self._a35_assert_artifact(first.content.decode('utf-8'), *args)

        def canonical(docs):
            return sorted(json.dumps(doc, sort_keys=True) for doc in docs)

        self.assertEqual(canonical(service_docs), canonical(download_docs),
                         'service output and download differ semantically')
        return first.content, graph

    def _a35_positive(self, case, profile_name, servers, leaves, spines, links_per_pair,
                      cables_total, devices_total, generated_interfaces):
        self._build(case, servers, self._scale_profile(profile_name))
        labels = self._a35_assign_profiles(profile_name)
        self._run(servers=servers, leaves=leaves, spines=spines, links_per_pair=links_per_pair,
                  cables_total=cables_total, devices_total=devices_total,
                  generated_interfaces=generated_interfaces)
        self._a35_login()
        return self._a35_export(servers, leaves, spines, links_per_pair, cables_total, labels)

    def test_ai_native8_export_service_and_download_match_graph(self):
        self._a35_positive('ai', 'native8', 8, 4, 2, 2, 24, 14, 40)

    def test_aj_breakout8_export_preserves_breakout_interface_names(self):
        self._a35_positive('aj', 'breakout8', 8, 4, 2, 2, 24, 14, 40)

    def test_ak_six12_export_service_and_download_match_graph(self):
        self._a35_positive('ak', 'six12', 9, 5, 3, 2, 39, 17, 69)

    def test_al_ten20_export_service_and_download_match_graph(self):
        self._a35_positive('al', 'ten20', 31, 16, 10, 1, 191, 57, 351)

    def test_am_breakout8_regenerate_16_servers_export_reflects_new_graph(self):
        self._build('am', 8, self._scale_profile('breakout8'))
        labels = self._a35_assign_profiles('breakout8')
        first_edges, first_ids = self._run(servers=8, leaves=4, spines=2, links_per_pair=2,
                                           cables_total=24, devices_total=14, generated_interfaces=40)
        self._a35_login()
        first_content, _ = self._a35_export(8, 4, 2, 2, 24, labels)

        self.server_class.refresh_from_db()
        self.server_class.quantity = 16
        self.server_class.save()
        self._calculate(leaves=8, spines=4)
        # baseline stays the ORIGINAL pre-first-generation baseline
        self._generate(devices_total=28, generated_interfaces=80, cables_total=48)
        second_edges, second_ids = self._verify(servers=16, leaves=8, spines=4, links_per_pair=1,
                                                cables_total=48, devices_total=28)
        self.assertNotEqual(second_edges, first_edges)
        for model in INVENTORY_MODELS:
            self.assertEqual(first_ids[model] & second_ids[model], set(), f'stale {model.__name__} reused')
            self.assertFalse(model.objects.filter(pk__in=first_ids[model]).exists(),
                             f'first-generation {model.__name__} remains')

        second_content, (_, exported_fabric) = self._a35_export(16, 8, 4, 1, 48, labels)
        self.assertNotEqual(second_content, first_content, 'artifact unchanged after regeneration')
        _, old_fabric = self._expected_edges(8, 4, 2, 2)
        _, new_fabric = self._expected_edges(16, 8, 4, 1)
        old_exclusive = set(old_fabric) - set(new_fabric)
        self.assertTrue(old_exclusive)
        self.assertEqual(old_exclusive & set(exported_fabric), set(), 'old-exclusive fabric edge exported')

    def test_an_native8_export_missing_profile_returns_400_without_mutation(self):
        from netbox_hedgehog.services.yaml_generator import generate_yaml_for_plan

        self._build('an', 8, self._scale_profile('native8'))
        for switch_class in (self.leaf_class, self.spine_class):
            ext = switch_class.device_type_extension
            ext.refresh_from_db()
            self.assertFalse(ext.hedgehog_profile_name, 'fixture intent: no export profile assigned')
        self._run(servers=8, leaves=4, spines=2, links_per_pair=2, cables_total=24, devices_total=14,
                  generated_interfaces=40)
        self._a35_login()
        url = self._a35_export_url()
        before = self._a35_snapshot()

        def service():
            with self.assertRaises(ValidationError) as ctx:
                generate_yaml_for_plan(self.plan)
            return ' '.join(ctx.exception.messages)

        message = self._a35_guarded(service)
        response = self._a35_guarded(lambda: self.client.get(url))
        self.assertEqual(self._a35_snapshot(), before, 'failed export changed persisted rows')
        self.assertIn('missing hedgehog_profile_name', message)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.has_header('Content-Disposition'), 'attachment on failed export')
        self.assertFalse(response['Content-Type'].startswith('text/yaml'))
        body = response.content.decode('utf-8')
        self.assertIn('YAML generation failed', body)
        self.assertIn('missing hedgehog_profile_name', body)
        _, leaf_names, spine_names = self._names(8, 4, 2)
        self.assertTrue(any(f'Switch {n} device type' in body for n in leaf_names + spine_names), body)
        self.assertNotIn('apiVersion', body)

    def test_ao_native8_export_without_permission_returns_403_without_mutation(self):
        self._build('ao', 8, self._scale_profile('native8'))
        self._a35_assign_profiles('native8')
        self._run(servers=8, leaves=4, spines=2, links_per_pair=2, cables_total=24, devices_total=14,
                  generated_interfaces=40)
        user = self._a35_login(superuser=False)
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.has_perm('netbox_hedgehog.change_topologyplan'))
        url = self._a35_export_url()
        before = self._a35_snapshot()
        responses = [self._a35_guarded(lambda: self.client.get(url)) for _ in range(2)]
        self.assertEqual(self._a35_snapshot(), before, 'denied export changed persisted rows')
        for response in responses:
            self.assertEqual(response.status_code, 403)
            self.assertFalse(response.has_header('Content-Disposition'), 'attachment on denied export')
            self.assertFalse(response.get('Content-Type', '').startswith('text/yaml'))
            self.assertNotIn(b'apiVersion', response.content)

    # ------------------- CAGE38 AP: synthetic shared physical NIC cage (first baseline)

    def test_ap_shared_nic_cage_physical_inventory(self):
        """Synthetic shared-physical-cage regression (CAGE38 first baseline, not full spec).

        One test-owned two-port NIC type (p0/p1, 400G) declares, via a test-owned
        schema-bearing ModuleTypeProfile and native full_clean, ``hnp_nic_cage_map``
        version 1 mapping both logical ports to channels 0/1 of ONE physical cage
        ``cage-0`` in mode 2x400g. One fictional test-owned optic type (existing Network
        Transceiver profile, synthetic declared capacity, no vendor qualification) is the
        same non-null FK on the server connection and the leaf SERVER zone. Real
        update_plan_calculations -> populate_bays (explicit test-owned scope) ->
        DeviceGenerator.generate_all, then the full logical graph, then the intended
        physical state: per server exactly one root NIC Module, one nested cage-0 and one
        optic; one switch optic per used leaf physical cage; exact public BOM quantities.
        Expected counts are stated literals, never derived from output. Not covered:
        regeneration, negative/malformed layouts, workbook, hardware, YAML, UI, snapshot.
        """
        import copy

        from dcim.models import ModuleTypeProfile
        from netbox_hedgehog.management.commands.populate_transceiver_bays import populate_bays
        from netbox_hedgehog.services.bom_export import get_plan_bom

        self._build('ap', 4, BREAKOUT)
        nic_type = self.nic_module_type
        InterfaceTemplate.objects.create(module_type=nic_type, name='p1', type=T400)
        self.assertEqual(
            sorted(InterfaceTemplate.objects.filter(module_type=nic_type).values_list('name', 'type')),
            [('p0', T400), ('p1', T400)],
        )

        # --- test-owned schema-bearing NIC profile + declared cage map (native validation)
        cage_map = {
            'version': 1,
            'ports': [{'cage': 'cage-0', 'logical_lane': 0}, {'cage': 'cage-0', 'logical_lane': 1}],
            'cages': {'cage-0': {'breakout_id': '2x400g'}},
        }
        map_schema = {
            'type': 'object',
            'required': ['version', 'ports', 'cages'],
            'additionalProperties': False,
            'properties': {
                'version': {'type': 'integer', 'enum': [1]},
                'ports': {
                    'type': 'array', 'minItems': 1,
                    'items': {
                        'type': 'object', 'required': ['cage', 'logical_lane'],
                        'additionalProperties': False,
                        'properties': {
                            'cage': {'type': 'string', 'minLength': 1, 'maxLength': 64},
                            'logical_lane': {'type': 'integer', 'minimum': 0},
                        },
                    },
                },
                'cages': {
                    'type': 'object', 'minProperties': 1,
                    'additionalProperties': {
                        'type': 'object', 'required': ['breakout_id'], 'additionalProperties': False,
                        'properties': {'breakout_id': {'type': 'string', 'minLength': 1}},
                    },
                },
            },
        }
        nic_schema = {
            'type': 'object',
            'required': ['hnp_nic_cage_map'],
            'properties': {'hnp_nic_cage_map': map_schema},
        }
        nic_profile = ModuleTypeProfile(name='srv29-ap-nic-cage-profile', schema=copy.deepcopy(nic_schema))
        nic_profile.full_clean()
        nic_profile.save()
        nic_profile.refresh_from_db()
        self.assertEqual(nic_profile.schema, nic_schema)

        nic_type.profile = nic_profile
        nic_type.attribute_data = {'hnp_nic_cage_map': copy.deepcopy(cage_map)}
        nic_type.full_clean()
        nic_type.save()
        nic_type.refresh_from_db()
        self.assertEqual(nic_type.profile_id, nic_profile.pk)
        self.assertEqual(nic_type.attribute_data, {'hnp_nic_cage_map': cage_map}, 'persisted map not exact')

        # --- fictional test-owned optic on the EXISTING (unaltered) Network Transceiver profile
        xcvr_profile = ModuleTypeProfile.objects.filter(name='Network Transceiver').first()
        self.assertIsNotNone(xcvr_profile, 'shared Network Transceiver profile missing')
        self.assertTrue(xcvr_profile.schema, 'shared Network Transceiver profile has no schema')
        xcvr_schema_before = copy.deepcopy(xcvr_profile.schema)
        optic_attrs = {
            'cage_type': 'OSFP', 'medium': 'SMF', 'connector': 'MPO-12', 'standard': '400GBASE-DR4',
            'reach_class': 'DR', 'lane_count': 8, 'host_serdes_gbps_per_lane': 100,
            'breakout_topology': '2x400g',
        }
        optic_type = ModuleType(
            manufacturer=_manufacturer(), model='srv29-ap-fictional-osfp-2x400g',
            profile=xcvr_profile, attribute_data=dict(optic_attrs),
        )
        optic_type.full_clean()
        optic_type.save()
        optic_type.refresh_from_db()
        self.assertEqual(optic_type.profile_id, xcvr_profile.pk)
        self.assertEqual(optic_type.attribute_data, optic_attrs)

        # --- intent: same optic FK on server connection and leaf SERVER zone; 2 ports/conn
        conn = PlanServerConnection.objects.get(server_class=self.server_class)
        conn.ports_per_connection = 2
        conn.port_index = 0
        conn.transceiver_module_type = optic_type
        conn.full_clean()
        conn.save()
        server_zone = SwitchPortZone.objects.get(switch_class=self.leaf_class,
                                                 zone_type=PortZoneTypeChoices.SERVER)
        server_zone.transceiver_module_type = optic_type
        server_zone.full_clean()
        server_zone.save()
        conn.refresh_from_db()
        server_zone.refresh_from_db()
        self.assertEqual(
            (conn.ports_per_connection, conn.port_index, conn.speed, conn.distribution,
             conn.hedgehog_conn_type, conn.transceiver_module_type_id, conn.target_zone_id),
            (2, 0, 400, ConnectionDistributionChoices.SAME_SWITCH, ConnectionTypeChoices.UNBUNDLED,
             optic_type.pk, server_zone.pk),
        )
        self.assertEqual(server_zone.transceiver_module_type_id, optic_type.pk)
        for zone in SwitchPortZone.objects.filter(switch_class__plan=self.plan).exclude(pk=server_zone.pk):
            self.assertIsNone(zone.transceiver_module_type_id, f'{zone.zone_name} unexpectedly has optic FK')

        # --- real populate_bays, ONLY test-owned switch device types and NIC type
        populate_bays(device_types=[self.leaf_device_type, self.spine_device_type], module_types=[nic_type])

        # --- real calculation + generation; literals: 4 leaves, 2 spines, (10, 40, 24)
        self._calculate(leaves=4, spines=2)
        self._capture_baseline()
        self._generate(devices_total=10, generated_interfaces=40, cables_total=24)

        # --- full logical graph BEFORE physical assertions
        servers, leaves, spines, cables_total, devices_total = 4, 4, 2, 24, 10
        names = self._names(servers, leaves, spines)
        server_names, leaf_names, spine_names = names
        server_edges = Counter()
        for i, server in enumerate(server_names):  # one server per leaf; p0->E1/1/1, p1->E1/1/2
            for port, (slot, _, _) in enumerate(BREAKOUT['leaf_server']):
                server_edges[(server, f'{NIC_ID}-p{port}', leaf_names[i], slot)] += 1
        _, fabric_edges = self._expected_edges(servers, leaves, spines, 2)  # fabric part only
        self.assertEqual(sum(server_edges.values()), 8)
        self.assertEqual(sum(fabric_edges.values()), 16)
        devices, interfaces, cables, modules, bays = self._new_inventory()
        self.assertEqual(len(devices), devices_total)
        by_name = self._assert_devices(devices, names)
        self._assert_switch_interfaces(by_name, names, interfaces, server_edges, fabric_edges)
        self.assertEqual(len(cables), cables_total)
        self._assert_cables(by_name, names, cables, server_edges, fabric_edges)
        for name in server_names:
            ifaces = sorted((i for i in interfaces if i.device_id == by_name[name].pk), key=lambda i: i.name)
            self.assertEqual([i.name for i in ifaces], [f'{NIC_ID}-p0', f'{NIC_ID}-p1'], name)
            for iface in ifaces:
                self.assertEqual(iface.type, T400, f'{name} {iface.name}')
                self.assertIsNotNone(iface.cable_id, f'{name} {iface.name} uncabled')

        # --- intended physical state: one NIC, one nested cage-0, one optic per server
        plan_id = str(self.plan.pk)
        modules_by_device, bays_by_device = {}, {}
        for module in modules:
            modules_by_device.setdefault(module.device_id, []).append(module)
        for bay in bays:
            bays_by_device.setdefault(bay.device_id, []).append(bay)
        for name in server_names:
            device = by_name[name]
            dev_bays = bays_by_device.get(device.pk, [])
            roots = [b for b in dev_bays if b.module_id is None]
            self.assertEqual([b.name for b in roots], [NIC_ID], f'{name} top-level bays')
            root = roots[0]
            self.assertIsNone(root.parent_id, f'{name} root NIC bay has a parent')
            dev_modules = modules_by_device.get(device.pk, [])
            nics = [m for m in dev_modules if m.module_bay_id == root.pk]
            self.assertEqual(len(nics), 1, f'{name} NIC module count')
            nic = nics[0]
            self.assertEqual((nic.device_id, nic.module_type_id), (device.pk, nic_type.pk), name)
            self.assertEqual(nic.custom_field_data.get('hedgehog_plan_id'), plan_id, name)
            nested = [b for b in dev_bays if b.module_id is not None]
            self.assertEqual(sorted(b.name for b in nested), ['cage-0'],
                             f'{name} physical nested cages (shared cage expected, no cage-1)')
            cage = nested[0]
            self.assertEqual((cage.module_id, cage.device_id), (nic.pk, device.pk), f'{name} cage owner')
            self.assertEqual(cage.parent_id, root.pk, f'{name} cage parent bay')
            optics = [m for m in dev_modules if m.pk != nic.pk]
            self.assertEqual(len(optics), 1, f'{name} server optic count (one per physical cage)')
            optic = optics[0]
            self.assertEqual((optic.device_id, optic.module_bay_id, optic.module_type_id),
                             (device.pk, cage.pk, optic_type.pk), f'{name} optic placement')
            self.assertEqual(optic.custom_field_data.get('hedgehog_plan_id'), plan_id, name)

        # --- switch optics: one per used leaf physical cage (E1/1); none on fabric zones
        for name in leaf_names + spine_names:
            device = by_name[name]
            is_spine = name in spine_names
            parents = BREAKOUT['spine_parents'] if is_spine else BREAKOUT['leaf_parents']
            dev_bays = bays_by_device.get(device.pk, [])
            self.assertEqual(sorted(b.name for b in dev_bays), sorted(f'E1/{p}' for p in parents), name)
            for bay in dev_bays:
                self.assertIsNone(bay.module_id, f'{name} {bay.name} nested')
            dev_modules = modules_by_device.get(device.pk, [])
            if is_spine:
                self.assertEqual(dev_modules, [], f'{name} unexpected spine optic')
                continue
            self.assertEqual(len(dev_modules), 1, f'{name} leaf optic count')
            bay_by_pk = {b.pk: b for b in dev_bays}
            optic = dev_modules[0]
            self.assertEqual(bay_by_pk[optic.module_bay_id].name, 'E1/1', name)
            self.assertEqual((optic.device_id, optic.module_type_id), (device.pk, optic_type.pk), name)

        self.assertEqual(Counter(m.module_type_id for m in modules),
                         Counter({nic_type.pk: 4, optic_type.pk: 8}), 'total module inventory')
        self.assertEqual(len(modules), 12, 'surprise modules')
        self.assertEqual(len(bays), 4 * 2 + 4 * 3 + 2 * 4, 'module bay inventory')

        # --- actual public BOM: exact sections/types/quantities, no suppression
        bom = get_plan_bom(self.plan)
        self.assertEqual(bom.suppressed_switch_cable_assembly_count, 0)
        self.assertEqual(len(bom.line_items), 3, [(i.section, i.module_type_model) for i in bom.line_items])
        self.assertEqual(
            {(i.section, i.module_type_id): i.quantity for i in bom.line_items},
            {('nic', nic_type.pk): 4, ('server_transceiver', optic_type.pk): 4,
             ('switch_transceiver', optic_type.pk): 4},
        )
        self.assertEqual(bom.module_total_qty, 12)
        self.assertEqual(
            Counter({(i.section, i.role, i.hedgehog_class, i.device_type_model): i.quantity
                     for i in bom.base_device_items}),
            Counter({
                ('server', DeviceCategoryChoices.SERVER, self.server_class.server_class_id,
                 self.server_device_type.model): 4,
                ('switch', DeviceCategoryChoices.LEAF, self.leaf_class.switch_class_id,
                 self.leaf_device_type.model): 4,
                ('switch', DeviceCategoryChoices.SPINE, self.spine_class.switch_class_id,
                 self.spine_device_type.model): 2,
            }),
        )
        self.assertEqual(bom.base_device_total_qty, 10)

        # --- shared schema untouched; declared map still exact
        xcvr_profile.refresh_from_db()
        self.assertEqual(xcvr_profile.schema, xcvr_schema_before, 'shared transceiver schema altered')
        nic_type.refresh_from_db()
        self.assertEqual(nic_type.attribute_data, {'hnp_nic_cage_map': cage_map})

    # ------------------- CAGE39: shared NIC cage feature coverage (T01-T12, appended)
    # Fictional test-owned profiles/types only; no real-hardware/catalog qualification.

    C39_MAP = {
        'version': 1,
        'ports': [{'cage': 'cage-0', 'logical_lane': 0}, {'cage': 'cage-0', 'logical_lane': 1}],
        'cages': {'cage-0': {'breakout_id': '2x400g'}},
    }
    C39_OPTIC_ATTRS = {
        'cage_type': 'OSFP', 'medium': 'SMF', 'connector': 'MPO-12', 'standard': '400GBASE-DR4',
        'reach_class': 'DR', 'lane_count': 8, 'host_serdes_gbps_per_lane': 100,
        'breakout_topology': '2x400g',
    }

    def _c39_fixture(self, case, weak_schema=False):
        """AP-equivalent declared fixture (BREAKOUT, 4 servers, one 2-port mapped NIC/cage),
        through scoped populate_bays and real calculation; NOT generated."""
        import copy

        from dcim.models import ModuleTypeProfile
        from netbox_hedgehog.management.commands.populate_transceiver_bays import populate_bays

        self._build(case, 4, BREAKOUT)
        nic_type = self.nic_module_type
        InterfaceTemplate.objects.create(module_type=nic_type, name='p1', type=T400)
        if weak_schema:
            schema = {'type': 'object', 'properties': {'hnp_nic_cage_map': {}}}
        else:
            schema = {'type': 'object', 'required': ['hnp_nic_cage_map'],
                      'properties': {'hnp_nic_cage_map': {
                          'type': 'object', 'required': ['version', 'ports', 'cages'],
                          'additionalProperties': False,
                          'properties': {'version': {'type': 'integer', 'enum': [1]},
                                         'ports': {'type': 'array', 'minItems': 1},
                                         'cages': {'type': 'object', 'minProperties': 1}}}}}
        profile = ModuleTypeProfile(name=f'srv29-{case}-nic-profile', schema=schema)
        profile.full_clean()
        profile.save()
        nic_type.profile = profile
        nic_type.attribute_data = {'hnp_nic_cage_map': copy.deepcopy(self.C39_MAP)}
        nic_type.full_clean()
        nic_type.save()
        xcvr_profile = ModuleTypeProfile.objects.get(name='Network Transceiver')
        optic = ModuleType(manufacturer=_manufacturer(), model=f'srv29-{case}-fictional-osfp-2x400g',
                           profile=xcvr_profile, attribute_data=dict(self.C39_OPTIC_ATTRS))
        optic.full_clean()
        optic.save()
        conn = PlanServerConnection.objects.get(server_class=self.server_class)
        conn.ports_per_connection = 2
        conn.transceiver_module_type = optic
        conn.full_clean()
        conn.save()
        zone = SwitchPortZone.objects.get(switch_class=self.leaf_class, zone_type=PortZoneTypeChoices.SERVER)
        zone.transceiver_module_type = optic
        zone.full_clean()
        zone.save()
        populate_bays(device_types=[self.leaf_device_type, self.spine_device_type], module_types=[nic_type])
        self._calculate(leaves=4, spines=2)
        self.c39 = {'nic_type': nic_type, 'optic': optic, 'profile': profile, 'conn': conn, 'zone': zone}
        return self.c39

    def _c39_generate(self):
        self._capture_baseline()
        self._generate(devices_total=10, generated_interfaces=40, cables_total=24)

    def _c39_set_map(self, value, key_present=True):
        data = {} if not key_present else {'hnp_nic_cage_map': value}
        ModuleType.objects.filter(pk=self.c39['nic_type'].pk).update(attribute_data=data)

    def _c39_parse_code(self, expected_code):
        from netbox_hedgehog.services.nic_cage_layout import parse_layout

        mt = ModuleType.objects.select_related('profile').get(pk=self.c39['nic_type'].pk)
        with self.assertRaises(ValidationError) as ctx:
            parse_layout(mt)
        self.assertIn(f'[{expected_code}]', ' '.join(ctx.exception.messages))

    def _c39_prewrite_reject(self, *fragments):
        """Public generate_all must reject with ZERO attempted mutations; full rows preserved."""
        self._capture_baseline()
        generator = DeviceGenerator(self.plan)  # constructor Site/Tag setup outside guarantee
        before = self._db_snapshot()
        message = self._reject_without_mutation(generator)
        for fragment in fragments:
            self.assertIn(fragment, message)
        self.assertEqual(self._db_snapshot(), before)
        for model in INVENTORY_MODELS:
            self.assertEqual(_pks(model), self.baseline[model], f'{model.__name__} inventory changed')
        return message

    def _c39_physical(self):
        """Per-server {name: (nic count, nested cage names TUPLE, optic count)} from actual ORM graph.

        Values are fully immutable (review03 P2-1: a list inside made set()/literal sets raise
        TypeError). Only servers actually generated appear, so complete dict equality against
        ``_c39_assert_physical``'s declared names detects a missing server."""
        _, _, _, modules, bays = self._new_inventory()
        out = {}
        server_names = self._names(4, 4, 2)[0]
        devices = {d.pk: d.name for d in Device.objects.filter(name__in=server_names)}
        for pk, name in devices.items():
            dev_bays = [b for b in bays if b.device_id == pk]
            dev_mods = [m for m in modules if m.device_id == pk]
            nested = tuple(sorted(b.name for b in dev_bays if b.module_id is not None))
            nics = [m for m in dev_mods if m.module_type_id == self.c39['nic_type'].pk]
            optics = [m for m in dev_mods if m.module_type_id == self.c39['optic'].pk]
            out[name] = (len(nics), nested, len(optics))
        return out

    def _c39_assert_physical(self, nested, optics):
        """Complete per-device equality: EVERY declared server (explicit literal ordinals 1..4)
        has exactly one NIC, exactly the literal nested cage names and the literal optic count.
        No set-collapse: a missing/extra server or a single wrong device fails."""
        expected = {f'srv29-{self.case}-server-{i:02d}': (1, tuple(nested), optics) for i in (1, 2, 3, 4)}
        physical = self._c39_physical()
        self.assertEqual(physical, expected, physical)
        return physical

    @staticmethod
    def _c39_rehash(ext):
        from netbox_hedgehog.services.nic_cage_layout import canonical_sha256

        for nic in ext['nics']:
            nic['evidence_sha256'] = canonical_sha256({k: v for k, v in nic.items() if k != 'evidence_sha256'})
        ext['evidence_sha256'] = canonical_sha256({k: v for k, v in ext.items() if k != 'evidence_sha256'})
        return ext

    def test_c39_t01_shared_cage_generation_one_optic_and_valid_snapshot(self):
        """T01/C05/C06/C08/C09: one NIC, two logical links, one physical cage + one optic."""
        from netbox_hedgehog.models.topology_planning.generation import SYNC_IN_SYNC
        from netbox_hedgehog.services.nic_cage_layout import SNAPSHOT_KEY, extension_errors
        from netbox_hedgehog.services.bom_export import get_plan_bom
        from netbox_hedgehog.utils.snapshot_builder import build_plan_snapshot

        self._c39_fixture('c39a')
        self._c39_generate()
        self._c39_assert_physical(('cage-0',), 1)
        bom = get_plan_bom(self.plan)
        self.assertEqual(
            {(i.section, i.module_type_id): i.quantity for i in bom.line_items},
            {('nic', self.c39['nic_type'].pk): 4, ('server_transceiver', self.c39['optic'].pk): 4,
             ('switch_transceiver', self.c39['optic'].pk): 4},
        )
        state = GenerationState.objects.get(plan=self.plan)
        self.assertIn(SNAPSHOT_KEY, state.snapshot)
        self.assertEqual(extension_errors(state.snapshot[SNAPSHOT_KEY], base_snapshot=state.snapshot), [])
        self.assertEqual(state.snapshot[SNAPSHOT_KEY], build_plan_snapshot(self.plan)[SNAPSHOT_KEY])
        self.assertFalse(state.is_dirty())
        self.assertEqual(state.sync_display_state(), SYNC_IN_SYNC)

    def test_c39_t05_typed_malformed_layouts_never_fall_back(self):
        """T05: weak schema stores malformed maps (direct ORM); strong parser rejects each."""
        import copy

        self._c39_fixture('c39b', weak_schema=True)
        good = copy.deepcopy(self.C39_MAP)

        def variant(**changes):
            value = copy.deepcopy(good)
            value.update(changes)
            return value

        cases = [
            ('null', None, 'nic_layout_shape'),
            ('empty', {}, 'nic_layout_shape'),
            ('extra_root', variant(extra=1), 'nic_layout_shape'),
            ('version_bool', variant(version=True), 'nic_layout_version'),
            ('version_2', variant(version=2), 'nic_layout_version'),
            ('ports_dict', variant(ports={}), 'nic_layout_ports'),
            ('cages_list', variant(cages=[]), 'nic_layout_cages'),
            ('port_count', variant(ports=good['ports'][:1]), 'nic_layout_port_count'),
            ('lane_negative', variant(ports=[{'cage': 'cage-0', 'logical_lane': -1}, good['ports'][1]]),
             'nic_layout_port_lane'),
            ('lane_bool', variant(ports=[{'cage': 'cage-0', 'logical_lane': False}, good['ports'][1]]),
             'nic_layout_port_lane'),
            ('lane_over_mode', variant(ports=[good['ports'][0], {'cage': 'cage-0', 'logical_lane': 2}]),
             'nic_layout_port_lane'),
            ('port_extra_field', variant(ports=[dict(good['ports'][0], x=1), good['ports'][1]]),
             'nic_layout_port_shape'),
            ('duplicate_channel', variant(ports=[good['ports'][0], good['ports'][0]]),
             'nic_layout_duplicate_channel'),
            ('unknown_mode', variant(cages={'cage-0': {'breakout_id': 'srv29-no-such-mode'}}),
             'nic_layout_unknown_mode'),
            ('cage_body_extra', variant(cages={'cage-0': {'breakout_id': '2x400g', 'x': 1}}),
             'nic_layout_cage_body'),
            ('substitution_name', {'version': 1,
                                   'ports': [{'cage': '{module}', 'logical_lane': 0},
                                             {'cage': '{module}', 'logical_lane': 1}],
                                   'cages': {'{module}': {'breakout_id': '2x400g'}}}, 'nic_layout_cage_name'),
            ('trim_unstable_name', {'version': 1,
                                    'ports': [{'cage': 'cage-0 ', 'logical_lane': 0},
                                              {'cage': 'cage-0 ', 'logical_lane': 1}],
                                    'cages': {'cage-0 ': {'breakout_id': '2x400g'}}}, 'nic_layout_cage_name'),
            ('unreferenced_cage', variant(cages={'cage-0': {'breakout_id': '2x400g'},
                                                 'cage-9': {'breakout_id': '2x400g'}}),
             'nic_layout_unreferenced_cage'),
            ('undeclared_cage', variant(ports=[good['ports'][0], {'cage': 'cage-x', 'logical_lane': 1}]),
             'nic_layout_port_cage'),
        ]
        for label, value, code in cases:
            with self.subTest(label):
                self._c39_set_map(value)
                self._c39_parse_code(code)
                self.assertIsNone(GenerationState.objects.filter(plan=self.plan).first())
        # No silent fallback at the public generator either (one representative, zero writes).
        self._c39_set_map(variant(version=2))
        self._c39_prewrite_reject('[nic_layout_version]')

    def test_c39_t05_profile_failures_profileless_weak_and_malformed_stored_schema(self):
        """T05/T08/L2: profileless ORM, undeclared property, schema mismatch, malformed stored schema."""
        from dcim.models import ModuleTypeProfile

        fixture = self._c39_fixture('c39c')
        ModuleType.objects.filter(pk=fixture['nic_type'].pk).update(profile=None)
        self._c39_parse_code('nic_layout_profile_missing')
        other = ModuleTypeProfile.objects.create(name='srv29-c39c-undeclared',
                                                 schema={'type': 'object', 'properties': {'x': {}}})
        ModuleType.objects.filter(pk=fixture['nic_type'].pk).update(profile=other)
        self._c39_parse_code('nic_layout_profile_schema')
        ModuleType.objects.filter(pk=fixture['nic_type'].pk).update(profile=fixture['profile'])
        self._c39_set_map(dict(self.C39_MAP, version=7))  # violates strict profile enum
        self._c39_parse_code('nic_layout_profile_schema_invalid')
        self._c39_set_map(self.C39_MAP)
        # Stored profile schema itself malformed (jsonschema.SchemaError) -> typed error, not crash.
        ModuleTypeProfile.objects.filter(pk=fixture['profile'].pk).update(
            schema={'type': 'srv29-not-a-type', 'properties': {'hnp_nic_cage_map': {}}})
        self._c39_parse_code('nic_layout_profile_schema_invalid')
        message = self._c39_prewrite_reject('[nic_layout_profile_schema_invalid]', 'malformed')
        self.assertIn(self.c39['nic_type'].model, message)

    def test_c39_t06_v7_reach_medium_conflict_rejected_before_writes(self):
        """T06/C05/L1/review P2-2: existing V7 invariant enforced on mapped active optic."""
        fixture = self._c39_fixture('c39d')
        ModuleType.objects.filter(pk=fixture['optic'].pk).update(
            attribute_data=dict(self.C39_OPTIC_ATTRS, reach_class='DAC', medium='SMF'))
        self._c39_prewrite_reject('[nic_layout_optic_reach_medium]', 'DAC')
        self.assertFalse(GenerationState.objects.filter(plan=self.plan).exists())

    def test_c39_t06_cross_owner_connection_rejected_before_writes(self):
        """T06/review P2-5: ORM connection of class A pointing at class B's mapped NIC."""
        fixture = self._c39_fixture('c39e')
        other = PlanServerClass.objects.create(
            plan=self.plan, server_class_id='srv29-c39e-other', server_device_type=self.server_device_type,
            quantity=0,
        )
        other_nic = PlanServerNIC.objects.create(server_class=other, nic_id=NIC_ID, module_type=fixture['nic_type'])
        PlanServerConnection.objects.filter(pk=fixture['conn'].pk).update(nic=other_nic)
        message = self._c39_prewrite_reject('[nic_layout_connection_owner]', 'srv29-c39e-other')
        self.assertIn(self.server_class.server_class_id, message)

    def test_c39_t06_inactive_class_structural_evidence_and_no_required_optic(self):
        """T06/review P2-4: inactive mapped class needs valid speed; null optic allowed."""
        from netbox_hedgehog.services.nic_cage_layout import capture_plan_layouts, extension_errors

        fixture = self._c39_fixture('c39f')
        idle = PlanServerClass.objects.create(
            plan=self.plan, server_class_id='srv29-c39f-idle', server_device_type=self.server_device_type,
            quantity=0,
        )
        idle_nic = PlanServerNIC.objects.create(server_class=idle, nic_id=NIC_ID, module_type=fixture['nic_type'])
        conn = PlanServerConnection.objects.create(
            server_class=idle, connection_id='srv29-c39f-idle-conn', nic=idle_nic, port_index=0,
            ports_per_connection=1, hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.SAME_SWITCH, target_zone=fixture['zone'], speed=400,
        )
        capture = capture_plan_layouts(self.plan)  # null optic on inactive class admitted
        self.assertEqual(extension_errors(capture.extension, active_classes={self.server_class.server_class_id}), [])
        self.assertTrue(extension_errors(capture.extension), 'strict all-active view must need the optic')
        PlanServerConnection.objects.filter(pk=conn.pk).update(speed=0)
        self._c39_prewrite_reject('[nic_layout_connection_speed]', 'srv29-c39f-idle-conn')
        self.assertFalse(GenerationState.objects.filter(plan=self.plan).exists())

    def _c39_catalog_snapshot(self):
        """Broader full-row evidence: existing _a35_snapshot (inventory, terminations, tags,
        state, plan/server/NIC/connection/zone intent, extensions, BreakoutOption, DeviceType,
        ModuleType, InterfaceTemplate) PLUS ModuleBayTemplate and ModuleTypeProfile rows."""
        from dcim.models import ModuleBayTemplate, ModuleTypeProfile

        snap = self._a35_snapshot()
        for model in (ModuleBayTemplate, ModuleTypeProfile):
            snap[model.__name__] = list(model.objects.order_by('pk').values())
        return snap

    def _c39_public_reject_after_generation(self, code, prior):
        """Public generate_all AFTER a valid prior generation, under the existing mutation-
        denying wrapper: exact typed code, zero attempted mutations, and every full row
        (old generated inventory, GenerationState, the bad current intent, catalog) intact."""
        generator = DeviceGenerator(self.plan)  # constructor Site/Tag setup outside the proof
        before = self._c39_catalog_snapshot()
        message = self._reject_without_mutation(generator)
        self.assertIn(f'[{code}]', message)
        self.assertEqual(self._c39_catalog_snapshot(), before, f'{code}: persisted rows changed')
        for model, pks in prior.items():
            self.assertTrue(pks <= _pks(model), f'{code}: prior generated {model.__name__} lost')
        state = GenerationState.objects.get(plan=self.plan)
        self.assertEqual(state.status, GenerationStatusChoices.GENERATED, code)
        self.assertEqual((state.device_count, state.interface_count, state.cable_count), (10, 40, 24), code)
        return message

    def test_c39_t06_used_port_matrix_specific_preflight_errors(self):
        """T06/review02 P2-3: range, null optic, speed, optic mode, collision, two CONFLICTING
        non-null optic FKs, BreakoutOption capacity and missing bay template, each through
        UNMOCKED public generate_all after a valid prior mapped generation: exact code, SQL
        mutation attempts denied, full prior inventory/state + bad intent + catalog preserved."""
        from dcim.models import ModuleBayTemplate, ModuleTypeProfile

        fixture = self._c39_fixture('c39g')
        conn, optic = fixture['conn'], fixture['optic']
        other_optic = ModuleType(manufacturer=_manufacturer(), model='srv29-c39g-fictional-osfp-2x400g-b',
                                 profile=ModuleTypeProfile.objects.get(name='Network Transceiver'),
                                 attribute_data=dict(self.C39_OPTIC_ATTRS))
        other_optic.full_clean()
        other_optic.save()
        # Positive generation FIRST: proves the fixture valid and creates the prior inventory.
        self._c39_generate()
        prior = {model: _pks(model) - self.baseline[model] for model in INVENTORY_MODELS}
        for model, pks in prior.items():
            self.assertTrue(pks, f'positive generation produced no {model.__name__}')
        self._c39_assert_physical(('cage-0',), 1)
        conns = PlanServerConnection.objects.filter(pk=conn.pk)
        optics = ModuleType.objects.filter(pk=optic.pk)
        breakout = BreakoutOption.objects.filter(breakout_id='2x400g')
        self.assertEqual(list(breakout.values_list('from_speed', 'logical_ports', 'logical_speed')), [(800, 2, 400)])

        with self.subTest('range'):
            conns.update(port_index=1)  # ports 1..2 of a 2-port NIC
            self._c39_public_reject_after_generation('nic_layout_index_range', prior)
            conns.update(port_index=0)
        with self.subTest('null_optic'):
            conns.update(transceiver_module_type=None)
            self._c39_public_reject_after_generation('nic_layout_null_optic', prior)
            conns.update(transceiver_module_type=optic)
        with self.subTest('speed'):
            conns.update(speed=800)
            self._c39_public_reject_after_generation('nic_layout_speed', prior)
            conns.update(speed=400)
        with self.subTest('optic_mode'):
            optics.update(attribute_data=dict(self.C39_OPTIC_ATTRS, breakout_topology='1x800g'))
            self._c39_public_reject_after_generation('nic_layout_optic_mode', prior)
            optics.update(attribute_data=dict(self.C39_OPTIC_ATTRS))
        nic = PlanServerNIC.objects.get(server_class=self.server_class)
        conns.update(ports_per_connection=1)
        second = PlanServerConnection.objects.create(
            server_class=self.server_class, connection_id='srv29-c39g-conn2', nic=nic, port_index=0,
            ports_per_connection=1, hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.SAME_SWITCH, target_zone=fixture['zone'], speed=400,
            transceiver_module_type=optic,
        )
        with self.subTest('collision'):
            self._c39_public_reject_after_generation('nic_layout_port_collision', prior)
        with self.subTest('conflicting_nonnull_optics'):
            # Channel 1 of the same cage, DIFFERENT non-null optic FK than channel 0.
            PlanServerConnection.objects.filter(pk=second.pk).update(port_index=1, transceiver_module_type=other_optic)
            self.assertEqual(
                sorted(PlanServerConnection.objects.filter(server_class=self.server_class)
                       .values_list('port_index', 'transceiver_module_type_id')),
                [(0, optic.pk), (1, other_optic.pk)])
            self._c39_public_reject_after_generation('nic_layout_conflicting_optic', prior)
        second.delete()
        conns.update(ports_per_connection=2)
        with self.subTest('breakout_capacity'):
            # Selected mode declares 2 x 400 on an 800 cage; shrinking from_speed makes it incoherent.
            breakout.update(from_speed=400)
            self._c39_public_reject_after_generation('nic_layout_mode_capacity', prior)
            breakout.update(from_speed=800)
        with self.subTest('missing_bay_template'):
            ModuleBayTemplate.objects.filter(module_type=fixture['nic_type'], name='cage-0').delete()
            self._c39_public_reject_after_generation('nic_layout_missing_bay_template', prior)

    def test_c39_t06_weak_schema_unhashable_optic_attrs_typed_rejection(self):
        """Review02 P2-1 regression: a weak (object-accepting) schema on the 'Network Transceiver'
        profile lets container/non-string reach_class/medium be stored; public generate_all must
        raise the typed nic_layout_optic_attr_type error (never TypeError) with zero attempted
        mutations. Existing scalar V7 outcome and valid scalar generation are unchanged. The
        shared profile schema change is an ORM update inside this test's rolled-back transaction."""
        from dcim.models import ModuleTypeProfile

        fixture = self._c39_fixture('c39w')
        optic = fixture['optic']
        xcvr = ModuleTypeProfile.objects.get(name='Network Transceiver')
        ModuleTypeProfile.objects.filter(pk=xcvr.pk).update(schema={'type': 'object'})
        optics = ModuleType.objects.filter(pk=optic.pk)
        for label, change in (('reach_class_list', {'reach_class': ['DR']}),
                              ('reach_class_dict', {'reach_class': {'DR': True}}),
                              ('medium_list', {'medium': ['SMF']}),
                              ('medium_int', {'medium': 7})):
            with self.subTest(label):
                optics.update(attribute_data=dict(self.C39_OPTIC_ATTRS, **change))
                message = self._c39_prewrite_reject('[nic_layout_optic_attr_type]')
                self.assertIn(optic.model, message)
                self.assertFalse(GenerationState.objects.filter(plan=self.plan).exists())
        with self.subTest('scalar_v7_conflict_unchanged'):
            optics.update(attribute_data=dict(self.C39_OPTIC_ATTRS, reach_class='DAC', medium='SMF'))
            self._c39_prewrite_reject('[nic_layout_optic_reach_medium]')
        optics.update(attribute_data=dict(self.C39_OPTIC_ATTRS))
        self._c39_generate()
        self._c39_assert_physical(('cage-0',), 1)

    def test_c39_t11_rehashed_mapped_module_token_template_incomplete_not_in_sync(self):
        """Review02 P2-2 regression: valid mapped evidence whose interface-template name is changed
        to literal '{module}-p0' and RE-HASHED is invalid (layout_template_module_token); identical
        such snapshots are never in sync through the public methods. Live parse also rejects it."""
        import copy

        from netbox_hedgehog.models.topology_planning.generation import SYNC_SNAPSHOT_INCOMPLETE
        from netbox_hedgehog.services.nic_cage_layout import SNAPSHOT_KEY, extension_errors
        from netbox_hedgehog.utils.snapshot_builder import build_plan_snapshot

        fixture = self._c39_fixture('c39u')
        snapshot = build_plan_snapshot(self.plan)
        self.assertEqual(extension_errors(snapshot[SNAPSHOT_KEY], base_snapshot=snapshot), [])
        bad = copy.deepcopy(snapshot)
        names = [t['name'] for t in bad[SNAPSHOT_KEY]['nics'][0]['interface_templates']]
        self.assertEqual(names, ['p0', 'p1'])
        bad[SNAPSHOT_KEY]['nics'][0]['interface_templates'][0]['name'] = '{module}-p0'
        self._c39_rehash(bad[SNAPSHOT_KEY])
        self.assertEqual(extension_errors(bad[SNAPSHOT_KEY], base_snapshot=bad), ['layout_template_module_token'])
        probe = GenerationState(plan=self.plan, device_count=0, interface_count=0, cable_count=0,
                                snapshot=copy.deepcopy(bad))
        self.assertTrue(probe.is_dirty())
        self.assertEqual(probe.sync_display_state(current=copy.deepcopy(bad)), SYNC_SNAPSHOT_INCOMPLETE)
        InterfaceTemplate.objects.filter(module_type=fixture['nic_type'], name='p0').update(name='{module}-p0')
        self._c39_parse_code('nic_layout_template_module_token')

    def test_c39_t07_population_prewrite_declared_cages_idempotent_preserves_extras(self):
        """T07/C04/review02 P2-4: invalid later layout in the passed scope -> specific layout
        error with ZERO attempted SQL mutations (execute_wrapper denial, not a rollback-only
        row comparison); mapped creation only declared cages, idempotent, extras/unpassed kept."""
        from dcim.models import ModuleBayTemplate, ModuleTypeProfile
        from netbox_hedgehog.management.commands.populate_transceiver_bays import populate_bays

        fixture = self._c39_fixture('c39h')
        nic_type = ModuleType.objects.select_related('profile').get(pk=fixture['nic_type'].pk)
        self.assertEqual(sorted(ModuleBayTemplate.objects.filter(module_type=nic_type).values_list('name', flat=True)),
                         ['cage-0'], 'mapped population creates declared cages only')
        extra = ModuleBayTemplate.objects.create(module_type=nic_type, name='srv29-historical-extra')
        weak = ModuleTypeProfile(name='srv29-c39h-weak-profile',
                                 schema={'type': 'object', 'properties': {'hnp_nic_cage_map': {}}})
        weak.full_clean()
        weak.save()
        bad = ModuleType.objects.create(manufacturer=_manufacturer(), model='srv29-c39h-bad-nic', profile=weak)
        InterfaceTemplate.objects.create(module_type=bad, name='p0', type=T400)
        bad_map = dict(self.C39_MAP, version=2)  # exact root shape, unknown version
        ModuleType.objects.filter(pk=bad.pk).update(attribute_data={'hnp_nic_cage_map': bad_map})
        bad = ModuleType.objects.select_related('profile').get(pk=bad.pk)  # setup: the stored row
        self.assertEqual(bad.attribute_data, {'hnp_nic_cage_map': bad_map})
        unpassed = ModuleType.objects.create(manufacturer=_manufacturer(), model='srv29-c39h-unpassed-nic')
        InterfaceTemplate.objects.create(module_type=unpassed, name='p0', type=T400)

        def rows():
            return {m.__name__: list(m.objects.order_by('pk').values())
                    for m in (ModuleBayTemplate, ModuleType, ModuleTypeProfile, InterfaceTemplate)}

        before = rows()
        attempts = []

        def deny(execute, sql, params, many, context):
            text = sql.strip() if isinstance(sql, str) else str(sql).strip()
            head = text.split(None, 1)[0].upper() if text else ''
            if head not in ('SELECT', 'SAVEPOINT', 'RELEASE', 'ROLLBACK'):
                attempts.append(text[:200])
                raise AssertionError(f'mutation/unexpected SQL during population admission: {text[:200]}')
            return execute(sql, params, many, context)

        with connection.execute_wrapper(deny):
            with self.assertRaises(ValidationError) as ctx:
                populate_bays(device_types=[self.leaf_device_type], module_types=[nic_type, bad])
        self.assertEqual(attempts, [], 'population attempted SQL mutation before layout rejection')
        message = ' '.join(ctx.exception.messages)
        self.assertIn('[nic_layout_version]', message)
        self.assertIn('srv29-c39h-bad-nic', message)
        self.assertEqual(rows(), before, 'population changed rows')
        first = populate_bays(device_types=[self.leaf_device_type], module_types=[nic_type])
        second = populate_bays(device_types=[self.leaf_device_type], module_types=[nic_type])
        self.assertEqual((first['nic_added'], second['nic_added']), (0, 0), 'declared cage already present')
        self.assertEqual(second['switch_added'], 0)
        self.assertEqual(
            sorted(ModuleBayTemplate.objects.filter(module_type=nic_type).values_list('name', flat=True)),
            ['cage-0', 'srv29-historical-extra'], 'idempotent; extra preserved; no per-logical cage-1',
        )
        self.assertTrue(ModuleBayTemplate.objects.filter(pk=extra.pk).exists())
        self.assertFalse(ModuleBayTemplate.objects.filter(module_type=bad).exists(), 'invalid type populated')
        self.assertFalse(ModuleBayTemplate.objects.filter(module_type=unpassed).exists(), 'unpassed type reached')
        self.assertEqual(ModuleType.objects.get(pk=nic_type.pk).attribute_data, {'hnp_nic_cage_map': self.C39_MAP})

    def test_c39_t04_legacy_absent_key_two_independent_cages_and_no_snapshot_key(self):
        """T04: key absent -> unchanged per-logical-port cages/optics; no extension key."""
        from netbox_hedgehog.management.commands.populate_transceiver_bays import populate_bays
        from netbox_hedgehog.services.nic_cage_layout import SNAPSHOT_KEY
        from dcim.models import ModuleTypeProfile

        self._build('c39i', 4, BREAKOUT)
        nic_type = self.nic_module_type
        InterfaceTemplate.objects.create(module_type=nic_type, name='p1', type=T400)
        optic = ModuleType(manufacturer=_manufacturer(), model='srv29-c39i-fictional-osfp-2x400g',
                           profile=ModuleTypeProfile.objects.get(name='Network Transceiver'),
                           attribute_data=dict(self.C39_OPTIC_ATTRS))
        optic.full_clean()
        optic.save()
        conn = PlanServerConnection.objects.get(server_class=self.server_class)
        conn.ports_per_connection = 2
        conn.transceiver_module_type = optic
        conn.full_clean()
        conn.save()
        zone = SwitchPortZone.objects.get(switch_class=self.leaf_class, zone_type=PortZoneTypeChoices.SERVER)
        zone.transceiver_module_type = optic
        zone.full_clean()
        zone.save()
        populate_bays(device_types=[self.leaf_device_type, self.spine_device_type], module_types=[nic_type])
        self._calculate(leaves=4, spines=2)
        self.c39 = {'nic_type': nic_type, 'optic': optic}
        self._c39_generate()
        self._c39_assert_physical(('cage-0', 'cage-1'), 2)
        state = GenerationState.objects.get(plan=self.plan)
        self.assertNotIn(SNAPSHOT_KEY, state.snapshot)
        self.assertEqual(sorted(state.snapshot), ['connections', 'mclag_domains', 'port_zones',
                                                  'server_classes', 'switch_classes'])
        self.assertFalse(state.is_dirty())

    def test_c39_t10_regeneration_removes_all_old_modules_and_keeps_bom(self):
        """T10/C09: repeated public generation -> no stale Module/ModuleBay PKs, same BOM."""
        from netbox_hedgehog.services.bom_export import get_plan_bom

        fixture = self._c39_fixture('c39j')
        self._c39_generate()
        _, _, _, first_modules, first_bays = self._new_inventory()
        first_module_pks = {m.pk for m in first_modules}
        first_bay_pks = {b.pk for b in first_bays}
        self.assertEqual(len(first_module_pks), 12)
        self._generate(devices_total=10, generated_interfaces=40, cables_total=24)
        _, _, _, modules, bays = self._new_inventory()
        self.assertFalse(Module.objects.filter(pk__in=first_module_pks).exists(), 'old Module PK remains')
        self.assertFalse(ModuleBay.objects.filter(pk__in=first_bay_pks).exists(), 'old ModuleBay PK remains')
        self.assertEqual(Counter(m.module_type_id for m in modules),
                         Counter({fixture['nic_type'].pk: 4, fixture['optic'].pk: 8}))
        for module in modules:
            if module.module_type_id != fixture['optic'].pk or module.module_bay.module_id is None:
                continue
            parent_nic = module.module_bay.module
            self.assertEqual(parent_nic.module_type_id, fixture['nic_type'].pk)
            self.assertEqual(parent_nic.device_id, module.device_id)
            self.assertIsNone(parent_nic.module_bay.module_id, 'NIC installed in a nested bay')
        self._c39_assert_physical(('cage-0',), 1)
        bom = get_plan_bom(self.plan)
        self.assertEqual(
            {(i.section, i.module_type_id): i.quantity for i in bom.line_items},
            {('nic', fixture['nic_type'].pk): 4, ('server_transceiver', fixture['optic'].pk): 4,
             ('switch_transceiver', fixture['optic'].pk): 4},
        )

    def test_c39_t11_validator_rejects_rehashed_internally_invalid_evidence(self):
        """T11/review P2-3/L3: corrupt relationships, RE-HASH digests, expect specific invalid."""
        import copy

        from netbox_hedgehog.services.nic_cage_layout import capture_plan_layouts, extension_errors

        self._c39_fixture('c39k')
        valid = capture_plan_layouts(self.plan).extension
        self.assertEqual(extension_errors(valid), [])

        def mutate(fn):
            ext = copy.deepcopy(valid)
            fn(ext)
            return self._c39_rehash(ext)

        def nic(ext):
            return ext['nics'][0]

        def add_cage(ext):
            n = nic(ext)
            n['layout']['cages'].append({'cage': 'cage-9', 'breakout_id': '2x400g'})
            n['modes'].append(dict(n['modes'][0], cage='cage-9'))

        def overlap(ext):
            n = nic(ext)
            extra = dict(n['connections'][0], connection_id='srv29-c39k-dup', ports_per_connection=1)
            n['connections'].append(extra)
            ext['expected_connection_keys'] = sorted(ext['expected_connection_keys']
                                                     + [[extra['server_class_id'], extra['connection_id']]])

        def swap_names(ext, name):
            n = nic(ext)
            for row in n['layout']['ports'] + n['layout']['cages'] + n['modes']:
                row['cage'] = name

        cases = [
            ('unreferenced_cage', add_cage, 'layout_unreferenced_cage'),
            ('consumed_cage_bay_removed', lambda e: nic(e).update(bay_templates=[]), 'used_cage_missing_bay'),
            ('optic_mode_mismatch', lambda e: nic(e)['optics'][0].update(breakout_topology='1x800g'),
             'used_cage_optic_mode'),
            ('overlapping_ranges', overlap, 'connection_index_collision'),
            ('speed_vs_mode', lambda e: nic(e)['connections'][0].update(speed=800), 'used_cage_speed'),
            ('empty_geometry', lambda e: nic(e)['layout'].update(ports=[]), 'layout_empty_geometry'),
            ('substitution_name', lambda e: swap_names(e, '{module}'), 'layout_cage_name'),
            ('trim_unstable_name', lambda e: swap_names(e, 'cage-0 '), 'layout_cage_name'),
            ('null_target_zone', lambda e: nic(e)['connections'][0].update(target_zone_id=None),
             'connection_fields'),
            ('cross_owner', lambda e: nic(e)['connections'][0].update(server_class_id='srv29-other'),
             'connection_owner'),
            ('omitted_nic', lambda e: e.update(nics=[]), 'nic_completeness'),
            ('duplicate_nic', lambda e: e['nics'].append(copy.deepcopy(e['nics'][0])), 'nic_completeness'),
            ('empty_manifest', lambda e: e.update(expected_nic_keys=[], nics=[]), 'nic_manifest_empty'),
            ('omitted_connection', lambda e: nic(e).update(connections=[], optics=[]), 'connection_completeness'),
            ('omitted_optic', lambda e: nic(e).update(optics=[]), 'optic_coverage'),
            ('omitted_template', lambda e: nic(e).update(interface_templates=nic(e)['interface_templates'][:1]),
             'layout_index'),
            ('omitted_mode', lambda e: nic(e).update(modes=[]), 'mode_coverage'),
            ('version_bool', lambda e: e.update(version=True), 'version'),
            ('version_unknown', lambda e: e.update(version=2), 'version'),
            ('bool_module_type_id', lambda e: nic(e).update(module_type_id=True), 'nic_fields'),
        ]
        for label, fn, code in cases:
            with self.subTest(label):
                self.assertEqual(extension_errors(mutate(fn)), [code])
        marker = {'version': 1, 'status': 'invalid', 'errors': ['nic_layout_version']}
        self.assertEqual(extension_errors(marker), ['invalid_marker'])
        tampered = copy.deepcopy(valid)
        tampered['nics'][0]['connections'][0]['target_zone_id'] += 1000  # semantically valid, NOT rehashed
        self.assertEqual(extension_errors(tampered), ['nic_digest_mismatch'])

    def test_c39_t11_public_sync_methods_invalid_equal_fk_attrs_ports_swap_last_map(self):
        """T11: is_dirty + sync_display_state for invalid-equal, unchanged-FK attribute/mode,
        ordered ports swap and last-map removal; read-only (state row unchanged)."""
        import copy

        from netbox_hedgehog.models.topology_planning.generation import (
            SYNC_CHANGED,
            SYNC_IN_SYNC,
            SYNC_SNAPSHOT_INCOMPLETE,
        )
        from netbox_hedgehog.services.nic_cage_layout import SNAPSHOT_KEY
        from netbox_hedgehog.utils.snapshot_builder import build_plan_snapshot

        fixture = self._c39_fixture('c39l')
        self._c39_generate()
        state = GenerationState.objects.get(plan=self.plan)
        saved_row = list(GenerationState.objects.filter(pk=state.pk).values())
        self.assertFalse(state.is_dirty())
        self.assertEqual(state.sync_display_state(), SYNC_IN_SYNC)

        # Serialized re-hashed invalid saved evidence: sync_display_state(current=identical) is
        # incomplete. is_dirty() here compares against the VALID live current, so it only proves
        # saved-invalid -> dirty; the genuine identical-invalid-current proof (live marker equal
        # to saved, equality verified first) is test_c39_t11_live_invalid_current_...
        invalid = copy.deepcopy(state.snapshot)
        invalid[SNAPSHOT_KEY]['nics'][0]['bay_templates'] = []
        self._c39_rehash(invalid[SNAPSHOT_KEY])
        probe = GenerationState(plan=self.plan, device_count=0, interface_count=0, cable_count=0,
                                snapshot=copy.deepcopy(invalid))
        self.assertTrue(self._c39_sync_guarded(probe.is_dirty))
        self.assertEqual(self._c39_sync_guarded(lambda: probe.sync_display_state(current=copy.deepcopy(invalid))),
                         SYNC_SNAPSHOT_INCOMPLETE)

        def assert_changed(label):
            state.refresh_from_db()
            self.assertTrue(self._c39_sync_guarded(state.is_dirty), label)
            self.assertEqual(self._c39_sync_guarded(state.sync_display_state), SYNC_CHANGED, label)

        # Unchanged optic FK, changed optic attributes (still valid/coherent) -> changed.
        ModuleType.objects.filter(pk=fixture['optic'].pk).update(
            attribute_data=dict(self.C39_OPTIC_ATTRS, host_serdes_gbps_per_lane=50))
        assert_changed('optic attribute change behind unchanged FK')
        ModuleType.objects.filter(pk=fixture['optic'].pk).update(attribute_data=dict(self.C39_OPTIC_ATTRS))
        self.assertFalse(state.is_dirty())
        # Ordered port swap (lanes exchanged): same multiset, different index association.
        swapped = copy.deepcopy(self.C39_MAP)
        swapped['ports'] = [{'cage': 'cage-0', 'logical_lane': 1}, {'cage': 'cage-0', 'logical_lane': 0}]
        self._c39_set_map(swapped)
        assert_changed('ports swap')
        self._c39_set_map(self.C39_MAP)
        self.assertFalse(state.is_dirty())
        # Last map removal: extension disappears from current -> changed, never projected away.
        self._c39_set_map(None, key_present=False)
        self.assertNotIn(SNAPSHOT_KEY, build_plan_snapshot(self.plan))
        assert_changed('last map removal')
        self.assertEqual(list(GenerationState.objects.filter(pk=state.pk).values()), saved_row,
                         'sync methods wrote/persisted a projection')

    def test_c39_snapshot_extension_normalizes_dict_form_validation_error(self):
        """Item1: native dict-form (model V7-style) ValidationError never escapes as 500."""
        from netbox_hedgehog.services.nic_cage_layout import validation_error_codes

        dict_form = ValidationError({'transceiver_module_type': ValidationError('V7 conflict', code='v7_reach')})
        self.assertFalse(hasattr(dict_form, 'error_list'), 'fixture must be genuine dict-form')
        self.assertEqual(validation_error_codes(dict_form), ['v7_reach'])
        self.assertEqual(validation_error_codes(ValidationError('x', code='nic_layout_shape')),
                         ['nic_layout_shape'])
        self.assertEqual(validation_error_codes(ValidationError('uncoded')), ['nic_layout_invalid'])
        self.assertEqual(validation_error_codes(ValidationError({'f': ['a', 'b']})), ['nic_layout_invalid'])

    def test_c39_t02_two_one_port_connections_two_fabrics_share_one_nic_cage(self):
        """T02: TWO one-port connections of ONE NIC/physical cage to two eligible fabrics.

        Explicitly declared ordinary spine-leaf fabrics A (existing BREAKOUT fixture) and B
        (duplicated leaf/spine classes on the same synthetic device types, fabric
        'srv29-fabric-b'). 8 servers: p0 -> fabric A server zone, p1 -> fabric B server zone,
        channels 0/1 of cage-0. Expected: 8 physical servers (not 16), one NIC, one nested
        cage-0, one optic each; 4 leaves + 2 spines per fabric. Expected edges are literal
        declared slots, never allocator output. Unbundled physical semantics only.
        """
        from netbox_hedgehog.services.bom_export import get_plan_bom

        fixture = self._c39_fixture('c39t02')
        optic = fixture['optic']
        self.server_class.quantity = 8
        self.server_class.save()
        conn_a = PlanServerConnection.objects.get(pk=fixture['conn'].pk)
        conn_a.ports_per_connection = 1
        conn_a.port_index = 0
        conn_a.full_clean()
        conn_a.save()

        fabric_b = 'srv29-fabric-b'
        leaf_ext = self.leaf_class.device_type_extension
        spine_ext = self.spine_class.device_type_extension
        leaf_b = PlanSwitchClass.objects.create(
            plan=self.plan, switch_class_id='srv29-c39t02b-leaf', fabric_name=fabric_b,
            fabric_class=FabricClassChoices.MANAGED, hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            topology_mode=TopologyModeChoices.SPINE_LEAF, device_type_extension=leaf_ext,
            override_quantity=None, calculated_quantity=0,
        )
        spine_b = PlanSwitchClass.objects.create(
            plan=self.plan, switch_class_id='srv29-c39t02b-spine', fabric_name=fabric_b,
            fabric_class=FabricClassChoices.MANAGED, hedgehog_role=HedgehogRoleChoices.SPINE,
            topology_mode=TopologyModeChoices.SPINE_LEAF, device_type_extension=spine_ext,
            override_quantity=None, calculated_quantity=0,
        )
        breakout = _breakout('2x400g')
        zone_b = self._zone(leaf_b, 'srv29-c39t02b-server', PortZoneTypeChoices.SERVER, '1', breakout)
        zone_b.transceiver_module_type = optic
        zone_b.full_clean()
        zone_b.save()
        self._zone(leaf_b, 'srv29-c39t02b-uplink', PortZoneTypeChoices.UPLINK, '2-3', breakout)
        self._zone(spine_b, 'srv29-c39t02b-fabric', PortZoneTypeChoices.FABRIC, '1-4', breakout)
        nic = PlanServerNIC.objects.get(server_class=self.server_class, nic_id=NIC_ID)
        conn_b = PlanServerConnection(
            server_class=self.server_class, connection_id='srv29-c39t02-conn-b', nic=nic, port_index=1,
            ports_per_connection=1, hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.SAME_SWITCH, target_zone=zone_b, speed=400,
            transceiver_module_type=optic,
        )
        conn_b.full_clean()
        conn_b.save()

        result = update_plan_calculations(self.plan)
        self.assertEqual(result['errors'], [])
        self.assertEqual(result['summary'], {
            self.leaf_class.switch_class_id: {'calculated': 4, 'override': None, 'effective': 4},
            self.spine_class.switch_class_id: {'calculated': 2, 'override': None, 'effective': 2},
            leaf_b.switch_class_id: {'calculated': 4, 'override': None, 'effective': 4},
            spine_b.switch_class_id: {'calculated': 2, 'override': None, 'effective': 2},
        })
        self._capture_baseline()
        self._generate(devices_total=20, generated_interfaces=80, cables_total=48)

        servers = [f'srv29-c39t02-server-{i:02d}' for i in range(1, 9)]
        leaves_a = [f'srv29-c39t02-leaf-{i:02d}' for i in range(1, 5)]
        spines_a = [f'srv29-c39t02-spine-{i:02d}' for i in range(1, 3)]
        leaves_b = [f'srv29-c39t02b-leaf-{i:02d}' for i in range(1, 5)]
        spines_b = [f'srv29-c39t02b-spine-{i:02d}' for i in range(1, 3)]
        server_slots = ['E1/1/1', 'E1/1/2']
        leaf_uplinks = ['E1/2/1', 'E1/2/2', 'E1/3/1', 'E1/3/2']
        spine_slots = [f'E1/{p}/{lane}' for p in (1, 2, 3, 4) for lane in (1, 2)]
        server_edges, fabric_edges = Counter(), Counter()
        for i, server in enumerate(servers):
            server_edges[(server, f'{NIC_ID}-p0', leaves_a[i // 2], server_slots[i % 2])] += 1
            server_edges[(server, f'{NIC_ID}-p1', leaves_b[i // 2], server_slots[i % 2])] += 1
        for leaves, spines in ((leaves_a, spines_a), (leaves_b, spines_b)):
            for i, leaf in enumerate(leaves):
                for j, spine in enumerate(spines):
                    for n in range(2):
                        fabric_edges[(leaf, leaf_uplinks[j * 2 + n], spine, spine_slots[i * 2 + n])] += 1
        self.assertEqual((sum(server_edges.values()), sum(fabric_edges.values())), (16, 32))

        devices, interfaces, cables, modules, bays = self._new_inventory()
        by_name = {d.name: d for d in devices.values()}
        self.assertEqual(set(by_name), set(servers + leaves_a + spines_a + leaves_b + spines_b),
                         'exactly 8 physical servers (no duplicate hosts) + 4/2 per fabric')
        for name in leaves_b + spines_b:
            self.assertEqual(by_name[name].custom_field_data.get('hedgehog_fabric'), fabric_b, name)
        for name in leaves_a + spines_a:
            self.assertEqual(by_name[name].custom_field_data.get('hedgehog_fabric'), FABRIC, name)
        self.assertEqual(len(cables), 48)
        self._assert_cables(by_name, (servers, leaves_a + leaves_b, spines_a + spines_b), cables,
                            server_edges, fabric_edges)

        for name in servers:
            pk = by_name[name].pk
            dev_bays = [b for b in bays if b.device_id == pk]
            dev_mods = [m for m in modules if m.device_id == pk]
            roots = [b for b in dev_bays if b.module_id is None]
            self.assertEqual([b.name for b in roots], [NIC_ID], name)
            nics = [m for m in dev_mods if m.module_bay_id == roots[0].pk]
            self.assertEqual([m.module_type_id for m in nics], [fixture['nic_type'].pk], name)
            nested = [b for b in dev_bays if b.module_id is not None]
            self.assertEqual([(b.name, b.module_id) for b in nested], [('cage-0', nics[0].pk)], name)
            optics = [m for m in dev_mods if m.pk != nics[0].pk]
            self.assertEqual([(m.module_type_id, m.module_bay_id) for m in optics],
                             [(optic.pk, nested[0].pk)], f'{name}: one shared optic for both fabrics')
            ifaces = sorted(i.name for i in interfaces if i.device_id == pk)
            self.assertEqual(ifaces, [f'{NIC_ID}-p0', f'{NIC_ID}-p1'], name)

        bom = get_plan_bom(self.plan)
        self.assertEqual(
            {(i.section, i.module_type_id): i.quantity for i in bom.line_items},
            {('nic', fixture['nic_type'].pk): 8, ('server_transceiver', optic.pk): 8,
             ('switch_transceiver', optic.pk): 8},
        )

    # ------------- CAGE39 SOURCE6: T03/C12/T10 physical cards (declared literal oracles)
    # Fictional test-owned NIC/optic types and profiles only. Expected graphs/counts are
    # literals from the declared fixture, never allocator/generator output.

    C39_STRONG_SCHEMA = {
        'type': 'object', 'required': ['hnp_nic_cage_map'],
        'properties': {'hnp_nic_cage_map': {
            'type': 'object', 'required': ['version', 'ports', 'cages'], 'additionalProperties': False,
            'properties': {'version': {'type': 'integer', 'enum': [1]},
                           'ports': {'type': 'array', 'minItems': 1},
                           'cages': {'type': 'object', 'minProperties': 1}}}},
    }
    # Declared cages 'data' and 'b-slot'; p0 -> data ch0 (used), p1 -> b-slot ch0 (unused).
    C39_CARD_MAP = {
        'version': 1,
        'ports': [{'cage': 'data', 'logical_lane': 0}, {'cage': 'b-slot', 'logical_lane': 0}],
        'cages': {'b-slot': {'breakout_id': '2x400g'}, 'data': {'breakout_id': '2x400g'}},
    }
    # Four logical ports on two physical cages (two channels each).
    C39_FOUR_PORT_MAP = {
        'version': 1,
        'ports': [{'cage': 'cage-0', 'logical_lane': 0}, {'cage': 'cage-0', 'logical_lane': 1},
                  {'cage': 'cage-1', 'logical_lane': 0}, {'cage': 'cage-1', 'logical_lane': 1}],
        'cages': {'cage-0': {'breakout_id': '2x400g'}, 'cage-1': {'breakout_id': '2x400g'}},
    }

    def _c39_mapped_type(self, case, suffix, port_names, layout):
        """Test-owned mapped NIC ModuleType under a strong schema-bearing profile (native full_clean)."""
        import copy

        from dcim.models import ModuleTypeProfile

        _breakout('2x400g')
        profile = ModuleTypeProfile(name=f'srv29-{case}-{suffix}-profile',
                                    schema=copy.deepcopy(self.C39_STRONG_SCHEMA))
        profile.full_clean()
        profile.save()
        module_type = ModuleType(manufacturer=_manufacturer(), model=f'srv29-{case}-{suffix}', profile=profile,
                                 attribute_data={'hnp_nic_cage_map': copy.deepcopy(layout)})
        module_type.full_clean()
        module_type.save()
        for name in port_names:
            InterfaceTemplate.objects.create(module_type=module_type, name=name, type=T400)
        module_type.refresh_from_db()
        self.assertEqual(module_type.attribute_data, {'hnp_nic_cage_map': layout})
        self.assertEqual(module_type.profile_id, profile.pk)
        return module_type

    def _c39_cards_fixture(self, case, cards):
        """BREAKOUT, 4 servers. ``cards`` = [(nic_id, module_type, port_index)]: one PlanServerNIC
        per card and one one-port 400G connection per card (declaration order conn-a, conn-b)
        to the existing two-slot leaf SERVER zone, same fictional optic on both ends.
        Scoped populate_bays and real calculation (4 leaves, 2 spines); NOT generated."""
        from dcim.models import ModuleTypeProfile
        from netbox_hedgehog.management.commands.populate_transceiver_bays import populate_bays

        self._build(case, 4, BREAKOUT)
        # Replace the default single nic0 declaration; its unused unmapped type is not in scope.
        PlanServerConnection.objects.filter(server_class=self.server_class).delete()
        PlanServerNIC.objects.filter(server_class=self.server_class).delete()
        optic = ModuleType(manufacturer=_manufacturer(), model=f'srv29-{case}-fictional-osfp-2x400g',
                           profile=ModuleTypeProfile.objects.get(name='Network Transceiver'),
                           attribute_data=dict(self.C39_OPTIC_ATTRS))
        optic.full_clean()
        optic.save()
        zone = SwitchPortZone.objects.get(switch_class=self.leaf_class, zone_type=PortZoneTypeChoices.SERVER)
        zone.transceiver_module_type = optic
        zone.full_clean()
        zone.save()
        module_types, nics = [], {}
        for suffix, (nic_id, module_type, port_index) in zip('abcd', cards):
            nic = nics.get(nic_id)
            if nic is None:  # one PlanServerNIC per declared card; repeated nic_id shares it
                nic = nics[nic_id] = PlanServerNIC.objects.create(
                    server_class=self.server_class, nic_id=nic_id, module_type=module_type)
            self.assertEqual(nic.module_type_id, module_type.pk, 'fixture: one type per card')
            conn = PlanServerConnection(
                server_class=self.server_class, connection_id=f'srv29-{case}-conn-{suffix}', nic=nic,
                port_index=port_index, ports_per_connection=1, hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
                distribution=ConnectionDistributionChoices.SAME_SWITCH, target_zone=zone, speed=400,
                transceiver_module_type=optic,
            )
            conn.full_clean()
            conn.save()
            if module_type not in module_types:
                module_types.append(module_type)
        populate_bays(device_types=[self.leaf_device_type, self.spine_device_type], module_types=module_types)
        self._calculate(leaves=4, spines=2)
        self.c39 = {'optic': optic, 'zone': zone, 'module_types': module_types}
        return optic

    def _c39_card_edges(self, used_ifaces):
        """Declared oracle: server i -> leaf i; k-th declared connection -> leaf slot E1/1/(k+1)."""
        server_names, leaf_names, _ = self._names(4, 4, 2)
        server_edges = Counter()
        for i, server in enumerate(server_names):
            for k, iface in enumerate(used_ifaces):
                server_edges[(server, iface, leaf_names[i], ('E1/1/1', 'E1/1/2')[k])] += 1
        _, fabric_edges = self._expected_edges(4, 4, 2, 2)
        self.assertEqual((sum(server_edges.values()), sum(fabric_edges.values())), (8, 16))
        return server_edges, fabric_edges

    def _c39_assert_logical(self, used_ifaces):
        names = self._names(4, 4, 2)
        server_edges, fabric_edges = self._c39_card_edges(used_ifaces)
        devices, interfaces, cables, _, _ = self._new_inventory()
        self.assertEqual(len(devices), 10)
        by_name = self._assert_devices(devices, names)
        self._assert_switch_interfaces(by_name, names, interfaces, server_edges, fabric_edges)
        self.assertEqual(len(cables), 24)
        self._assert_cables(by_name, names, cables, server_edges, fabric_edges)
        return by_name, interfaces

    def _c39_server_ifaces(self, by_name, interfaces, name):
        """{iface name: (owning card's bay name, card is in a ROOT bay, cabled)} from actual rows."""
        out = {}
        for iface in interfaces:
            if iface.device_id != by_name[name].pk:
                continue
            self.assertIsNotNone(iface.module_id, f'{name} {iface.name} not on a module')
            module = Module.objects.select_related('module_bay').get(pk=iface.module_id)
            out[iface.name] = (module.module_bay.name, module.module_bay.module_id is None,
                               iface.cable_id is not None)
        return out

    def _c39_card_graph(self, server_names):
        """Actual ORM per-server graph {root bay: (card type, {nested bay: occupant type | None})}.

        Asserts plan ownership of every module, root bays parentless, nested bays parented
        by their card's root bay, nothing nested inside an optic, and that every bay and
        module on the device is accounted for (no hidden deeper/misparented rows).
        """
        plan_id = str(self.plan.pk)
        devices, _, _, modules, bays = self._new_inventory()
        by_name = {d.name: d for d in devices.values()}
        graph = {}
        for name in server_names:
            pk = by_name[name].pk
            dev_bays = {b.pk: b for b in bays if b.device_id == pk}
            dev_mods = [m for m in modules if m.device_id == pk]
            occupant = {}
            for module in dev_mods:
                self.assertIn(module.module_bay_id, dev_bays, f'{name}: module {module.pk} in foreign bay')
                self.assertNotIn(module.module_bay_id, occupant, f'{name}: two modules in one bay')
                occupant[module.module_bay_id] = module
                self.assertEqual(module.custom_field_data.get('hedgehog_plan_id'), plan_id,
                                 f'{name}: module {module.pk} plan ownership')
            seen_bays, seen_mods, cards = set(), set(), {}
            for root in sorted((b for b in dev_bays.values() if b.module_id is None), key=lambda b: b.name):
                self.assertIsNone(root.parent_id, f'{name}: root bay {root.name} has a parent')
                self.assertNotIn(root.name, cards, f'{name}: duplicate root bay {root.name}')
                seen_bays.add(root.pk)
                card = occupant.get(root.pk)
                if card is None:
                    cards[root.name] = None
                    continue
                seen_mods.add(card.pk)
                nested = {}
                for child in (b for b in dev_bays.values() if b.module_id == card.pk):
                    self.assertEqual(child.parent_id, root.pk, f'{name}: {child.name} parent bay')
                    self.assertNotIn(child.name, nested, f'{name}: duplicate nested {child.name}')
                    seen_bays.add(child.pk)
                    inner = occupant.get(child.pk)
                    if inner is not None:
                        seen_mods.add(inner.pk)
                        self.assertFalse(any(b.module_id == inner.pk for b in dev_bays.values()),
                                         f'{name}: bay nested inside optic {inner.pk}')
                    nested[child.name] = None if inner is None else inner.module_type_id
                cards[root.name] = (card.module_type_id, nested)
            self.assertEqual(seen_bays, set(dev_bays), f'{name}: unaccounted (deeper/misparented) bays')
            self.assertEqual(seen_mods, {m.pk for m in dev_mods}, f'{name}: unaccounted modules')
            graph[name] = cards
        return graph

    def _c39_assert_boms(self, server_rows, optic_pk, aggregate):
        """Public per-device and aggregate BOM vs independent literals (``aggregate`` is stated,
        not summed from ``server_rows``). One switch optic per leaf physical cage E1/1."""
        from netbox_hedgehog.services.bom_export import get_plan_bom, get_plan_bom_by_device

        server_names, leaf_names, _ = self._names(4, 4, 2)
        expected = {}
        for server in server_names:
            for (section, module_type_id), qty in server_rows.items():
                expected[(server, self.server_class.server_class_id, DeviceCategoryChoices.SERVER,
                          section, module_type_id)] = qty
        for leaf in leaf_names:
            expected[(leaf, self.leaf_class.switch_class_id, DeviceCategoryChoices.LEAF,
                      'switch_transceiver', optic_pk)] = 1
        per_device = get_plan_bom_by_device(self.plan)
        self.assertEqual(per_device.suppressed_switch_cable_assembly_count, 0)
        actual = {}
        for item in per_device.line_items:
            key = (item.device_name, item.hedgehog_class, item.device_role, item.section, item.module_type_id)
            self.assertNotIn(key, actual, f'duplicate per-device BOM row {key}')
            actual[key] = item.quantity
        self.assertEqual(actual, expected, 'per-device BOM')
        bom = get_plan_bom(self.plan)
        self.assertEqual(bom.suppressed_switch_cable_assembly_count, 0)
        self.assertEqual(len(bom.line_items), len(aggregate))
        self.assertEqual({(i.section, i.module_type_id): i.quantity for i in bom.line_items}, aggregate,
                         'aggregate BOM')
        self.assertEqual(bom.base_device_total_qty, 10)

    def test_c39_t03_four_ports_two_cages_partial_channels_two_optics(self):
        """T03: 4 logical ports / 2 physical cages; p0 (cage-0 ch0) and p2 (cage-1 ch0) used by
        two one-port definitions -> exactly two optics per NIC, partial channels valid."""
        nic_type = self._c39_mapped_type('c39m', 'nic-4x', ['p0', 'p1', 'p2', 'p3'], self.C39_FOUR_PORT_MAP)
        optic = self._c39_cards_fixture('c39m', [(NIC_ID, nic_type, 0), (NIC_ID, nic_type, 2)])
        # Both one-port connections belong to ONE PlanServerNIC (one physical card).
        nics = list(PlanServerNIC.objects.filter(server_class=self.server_class))
        self.assertEqual([(n.nic_id, n.module_type_id) for n in nics], [(NIC_ID, nic_type.pk)])
        self.assertEqual(sorted(PlanServerConnection.objects.filter(server_class=self.server_class)
                                .values_list('port_index', 'ports_per_connection')), [(0, 1), (2, 1)])
        self._capture_baseline()
        self._generate(devices_total=10, generated_interfaces=40, cables_total=24)
        by_name, interfaces = self._c39_assert_logical([f'{NIC_ID}-p0', f'{NIC_ID}-p2'])
        server_names = self._names(4, 4, 2)[0]
        for name in server_names:
            self.assertEqual(self._c39_server_ifaces(by_name, interfaces, name), {
                f'{NIC_ID}-p0': (NIC_ID, True, True), f'{NIC_ID}-p1': (NIC_ID, True, False),
                f'{NIC_ID}-p2': (NIC_ID, True, True), f'{NIC_ID}-p3': (NIC_ID, True, False),
            }, name)
        expected_card = {NIC_ID: (nic_type.pk, {'cage-0': optic.pk, 'cage-1': optic.pk})}
        self.assertEqual(self._c39_card_graph(server_names), {n: expected_card for n in server_names})
        _, _, _, modules, bays = self._new_inventory()
        self.assertEqual(len(modules), 4 * 3 + 4 * 1, 'modules: per server 1 NIC + 2 optics; 1 per leaf')
        self.assertEqual(len(bays), 4 * 3 + 4 * 3 + 2 * 4, 'bays: per server 1 root + 2 cages')
        self._c39_assert_boms({('nic', nic_type.pk): 1, ('server_transceiver', optic.pk): 2}, optic.pk,
                              {('nic', nic_type.pk): 4, ('server_transceiver', optic.pk): 8,
                               ('switch_transceiver', optic.pk): 4})

    def _c39_same_type_cards(self, case):
        nic_type = self._c39_mapped_type(case, 'nic-card', ['p0', 'p1'], self.C39_CARD_MAP)
        optic = self._c39_cards_fixture(case, [('a-card', nic_type, 0), ('b-slot', nic_type, 0)])
        expected_card = (nic_type.pk, {'data': optic.pk, 'b-slot': None})
        return nic_type, optic, {'a-card': expected_card, 'b-slot': expected_card}

    def _c39_assert_same_type_cards(self, nic_type, optic, expected_cards):
        by_name, interfaces = self._c39_assert_logical(['a-card-p0', 'b-slot-p0'])
        server_names = self._names(4, 4, 2)[0]
        for name in server_names:
            self.assertEqual(self._c39_server_ifaces(by_name, interfaces, name), {
                'a-card-p0': ('a-card', True, True), 'a-card-p1': ('a-card', True, False),
                'b-slot-p0': ('b-slot', True, True), 'b-slot-p1': ('b-slot', True, False),
            }, f'{name}: each card in its own ROOT bay')
        self.assertEqual(self._c39_card_graph(server_names), {n: expected_cards for n in server_names},
                         'b-slot card must be ROOT, a-card nested b-slot must stay empty')
        _, _, _, modules, bays = self._new_inventory()
        self.assertEqual(len(modules), 4 * 4 + 4 * 1, 'per server 2 NICs + 2 optics; 1 per leaf')
        self.assertEqual(len(bays), 4 * 6 + 4 * 3 + 2 * 4, 'per server 2 roots + 2x2 nested cages')
        self._c39_assert_boms({('nic', nic_type.pk): 2, ('server_transceiver', optic.pk): 2}, optic.pk,
                              {('nic', nic_type.pk): 8, ('server_transceiver', optic.pk): 8,
                               ('switch_transceiver', optic.pk): 4})
        return {m.pk for m in modules}, {b.pk for b in bays}

    def test_c39_t03_c12_same_type_cards_a_card_b_slot_root_isolation_and_regeneration(self):
        """T03/T10/C12: two cards of the SAME mapped type, nic ids 'a-card'/'b-slot', declared cages
        'data'/'b-slot', only p0/data used. b-slot card occupies its own top-level bay (never
        a-card's nested b-slot); both nested b-slot cages stay empty; one optic per card/data.
        Regeneration removes every old Module/ModuleBay PK and reproduces the same graph/BOM."""
        nic_type, optic, expected_cards = self._c39_same_type_cards('c39n')
        self._capture_baseline()
        self._generate(devices_total=10, generated_interfaces=40, cables_total=24)
        first_modules, first_bays = self._c39_assert_same_type_cards(nic_type, optic, expected_cards)
        state = GenerationState.objects.get(plan=self.plan)
        self.assertFalse(state.is_dirty())

        self._generate(devices_total=10, generated_interfaces=40, cables_total=24)
        second_modules, second_bays = self._c39_assert_same_type_cards(nic_type, optic, expected_cards)
        self.assertFalse(Module.objects.filter(pk__in=first_modules).exists(), 'old Module PK remains')
        self.assertFalse(ModuleBay.objects.filter(pk__in=first_bays).exists(), 'old ModuleBay PK remains')
        self.assertEqual(first_modules & second_modules, set())

    def test_c39_t03_c12_mixed_legacy_sibling_b_slot_stays_root(self):
        """T03/T10/C12 control: mapped 'a-card' (declared nested 'b-slot') + LEGACY unmapped
        sibling 'b-slot' (key absent, per-port cage-0). The legacy card must be ROOT and keep its
        legacy cage-0 optic; a-card's nested b-slot stays empty. No name ban. Review03 P2-4: a
        second public generate_all reasserts the exact parent graph, interfaces, typed physical
        counts and per-device + aggregate BOM, and every first-run Module/ModuleBay PK is gone."""
        from netbox_hedgehog.services.nic_cage_layout import has_layout

        mapped = self._c39_mapped_type('c39o', 'nic-card', ['p0', 'p1'], self.C39_CARD_MAP)
        legacy = ModuleType.objects.create(manufacturer=_manufacturer(), model='srv29-c39o-legacy-nic')
        InterfaceTemplate.objects.create(module_type=legacy, name='p0', type=T400)
        self.assertFalse(has_layout(legacy))
        optic = self._c39_cards_fixture('c39o', [('a-card', mapped, 0), ('b-slot', legacy, 0)])
        self._capture_baseline()
        self._generate(devices_total=10, generated_interfaces=40, cables_total=24)
        first_modules, first_bays = self._c39_assert_mixed_cards(mapped, legacy, optic)
        self.assertFalse(GenerationState.objects.get(plan=self.plan).is_dirty())

        # Same-intent regeneration through public generate_all (baseline = original pre-first run).
        self._generate(devices_total=10, generated_interfaces=40, cables_total=24)
        second_modules, second_bays = self._c39_assert_mixed_cards(mapped, legacy, optic)
        self.assertFalse(Module.objects.filter(pk__in=first_modules).exists(), 'old Module PK remains')
        self.assertFalse(ModuleBay.objects.filter(pk__in=first_bays).exists(), 'old ModuleBay PK remains')
        self.assertEqual(first_modules & second_modules, set(), 'Module PK reused')
        self.assertEqual(first_bays & second_bays, set(), 'ModuleBay PK reused')
        self.assertFalse(GenerationState.objects.get(plan=self.plan).is_dirty())

    def _c39_assert_mixed_cards(self, mapped, legacy, optic):
        """Exact declared mixed-card oracle (logical graph, interfaces, parent graph, typed
        physical counts, per-device + aggregate BOM); returns this run's Module/ModuleBay PKs."""
        by_name, interfaces = self._c39_assert_logical(['a-card-p0', 'b-slot-p0'])
        server_names = self._names(4, 4, 2)[0]
        for name in server_names:
            self.assertEqual(self._c39_server_ifaces(by_name, interfaces, name), {
                'a-card-p0': ('a-card', True, True), 'a-card-p1': ('a-card', True, False),
                'b-slot-p0': ('b-slot', True, True),
            }, name)
        expected_cards = {'a-card': (mapped.pk, {'data': optic.pk, 'b-slot': None}),
                          'b-slot': (legacy.pk, {'cage-0': optic.pk})}
        self.assertEqual(self._c39_card_graph(server_names), {n: expected_cards for n in server_names})
        _, _, _, modules, bays = self._new_inventory()
        self.assertEqual(len(modules), 4 * 4 + 4 * 1)
        self.assertEqual(Counter(m.module_type_id for m in modules),
                         Counter({mapped.pk: 4, legacy.pk: 4, optic.pk: 8 + 4}),
                         'typed modules: per server 1 mapped + 1 legacy NIC + 2 optics; 1 optic per leaf')
        self.assertEqual(len(bays), 4 * 5 + 4 * 3 + 2 * 4, 'per server 2 roots + 2 mapped + 1 legacy cage')
        self._c39_assert_boms({('nic', mapped.pk): 1, ('nic', legacy.pk): 1,
                               ('server_transceiver', optic.pk): 2}, optic.pk,
                              {('nic', mapped.pk): 4, ('nic', legacy.pk): 4,
                               ('server_transceiver', optic.pk): 8, ('switch_transceiver', optic.pk): 4})
        return {m.pk for m in modules}, {b.pk for b in bays}

    def _c39_generate_with_injection(self, trigger, inject):
        """Public generate_all with ONE real owned DB change injected mid-run by a guarded
        execute_wrapper. Expects ValidationError through the atomic boundary, that writes had
        begun (no zero-SQL claim), and full rollback of prior inventory/terminations/tags/
        GenerationState/intent/catalog rows (including the injected change)."""
        generator = DeviceGenerator(self.plan)  # constructor Site/Tag setup outside the proof
        before = self._a35_snapshot()
        probe = {'fired': 0, 'writes': 0, 'busy': False}

        def fire():
            probe['busy'] = True
            try:
                inject()
            finally:
                probe['busy'] = False
            probe['fired'] += 1

        def wrapper(execute, sql, params, many, context):
            if probe['busy']:
                return execute(sql, params, many, context)
            text = sql if isinstance(sql, str) else str(sql)
            head = text.lstrip().split(None, 1)[0].upper() if text.strip() else ''
            if head in ('INSERT', 'UPDATE', 'DELETE'):
                probe['writes'] += 1
            flat = tuple(params) if (not many and isinstance(params, (list, tuple))) else ()
            when = None if probe['fired'] else trigger(head, text, flat)
            if when == 'before':
                fire()
            result = execute(sql, params, many, context)
            if when == 'after':
                fire()
            return result

        with connection.execute_wrapper(wrapper):
            with self.assertRaises(ValidationError) as ctx:
                generator.generate_all()
        self.assertEqual(probe['fired'], 1, 'injected owned DB change did not happen')
        self.assertGreater(probe['writes'], 0, 'runtime failure is after writes began (no zero-SQL claim)')
        self.assertEqual(self._a35_snapshot(), before, 'atomic rollback did not restore full prior state')
        return ' '.join(ctx.exception.messages)

    def test_c39_t06_t10_runtime_missing_instance_bay_and_wrong_root_occupant_roll_back(self):
        """T06/T10/C05/C06/C12 runtime: after a valid prior generation, a mid-run injected owned
        change (nested 'data' instance bay renamed; conflicting module installed in the fresh
        root 'a-card' bay) must raise through public generate_all and roll back everything."""
        nic_type, optic, expected_cards = self._c39_same_type_cards('c39p')
        self._capture_baseline()
        self._generate(devices_total=10, generated_interfaces=40, cables_total=24)
        prior_modules, prior_bays = self._c39_assert_same_type_cards(nic_type, optic, expected_cards)
        plan_id = str(self.plan.pk)

        def modulebay_sql(head, text, wanted_head):
            return head == wanted_head and '"dcim_modulebay"' in text

        def rename_new_data_bays():
            moved = ModuleBay.objects.filter(name='data', module__isnull=False).exclude(
                pk__in=prior_bays).update(name='srv29-injected-moved')
            self.assertGreater(moved, 0)

        with self.subTest('missing nested instance bay'):
            message = self._c39_generate_with_injection(
                lambda head, text, flat: 'before' if modulebay_sql(head, text, 'SELECT') and 'data' in flat
                else None,
                rename_new_data_bays,
            )
            self.assertIn('[nic_layout_runtime_missing_bay]', message)
            self.assertIn("'data'", message)

        def occupy_root(module_type, owned):
            def inject():
                bay = ModuleBay.objects.filter(name='a-card', module__isnull=True).exclude(pk__in=prior_bays).get()
                occupant = Module(device_id=bay.device_id, module_bay=bay, module_type=module_type,
                                  status='planned', serial='srv29-injected-occupant')
                occupant.custom_field_data = {'hedgehog_plan_id': plan_id} if owned else {}
                occupant.save()
            return inject

        root_insert = (lambda head, text, flat: 'after'
                       if modulebay_sql(head, text, 'INSERT') and 'NIC slot a-card' in flat else None)
        for label, module_type, owned in (('wrong-type owned occupant', optic, True),
                                          ('same-type unowned occupant', nic_type, False)):
            with self.subTest(label):
                message = self._c39_generate_with_injection(root_insert, occupy_root(module_type, owned))
                self.assertIn('[nic_root_bay_conflict]', message)
                self.assertIn("'a-card'", message)

        for model, pks in ((Module, prior_modules), (ModuleBay, prior_bays)):
            self.assertEqual(set(model.objects.filter(pk__in=pks).values_list('pk', flat=True)), pks,
                             f'prior {model.__name__} rows lost')
        state = GenerationState.objects.get(plan=self.plan)
        self.assertEqual(state.status, GenerationStatusChoices.GENERATED)
        self.assertEqual((state.device_count, state.interface_count, state.cable_count), (10, 40, 24))
        # Uninjected public regeneration still succeeds with the exact declared graph.
        self._generate(devices_total=10, generated_interfaces=40, cables_total=24)
        self._c39_assert_same_type_cards(nic_type, optic, expected_cards)
        self.assertFalse(Module.objects.filter(pk__in=prior_modules).exists())

    # ------------------------------------------- CAGE39 SOURCE6: T08 native catalog API

    def test_c39_t08_native_api_profile_map_roundtrip_bad_schema_profileless_permission(self):
        """T08/C01: authenticated native dcim REST API (real APIClient + Token) configures a
        test-owned schema-bearing ModuleTypeProfile and a ModuleType carrying hnp_nic_cage_map
        plus an unrelated schema-backed attribute; POST/PATCH then GET must persist the exact
        profile/map. Bad-schema input -> native 400 with a validation body, nothing persisted.
        Profileless request: observed native 2xx; the GET-persisted result is NOT admitted as a
        configured layout (no fabricated 400). Unprivileged token -> 403, no change. No HNP REST
        editor/GUI; all objects fictional test-owned rows."""
        import copy

        from rest_framework.test import APIClient
        from users.models import Token

        from dcim.models import ModuleTypeProfile
        from netbox_hedgehog.services.nic_cage_layout import has_layout, parse_layout

        _breakout('2x400g')
        manufacturer = _manufacturer()
        model = get_user_model()
        admin = model.objects.create_superuser(username='srv29-c39-api-admin',
                                               email='srv29-c39-api-admin@example.invalid', password=None)
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Token {Token.objects.create(user=admin).key}')

        schema = copy.deepcopy(self.C39_STRONG_SCHEMA)
        schema['properties']['srv29_form_factor'] = {'type': 'string', 'enum': ['ocp3', 'pcie']}
        response = api.post(reverse('dcim-api:moduletypeprofile-list'),
                            {'name': 'srv29-c39-api-nic-profile', 'schema': schema}, format='json')
        self.assertEqual(response.status_code, 201, response.content[:1000])
        profile_id = response.json()['id']
        got = api.get(reverse('dcim-api:moduletypeprofile-detail', kwargs={'pk': profile_id}))
        self.assertEqual(got.status_code, 200)
        self.assertEqual(got.json()['schema'], schema, 'persisted profile schema not exact')

        def admitted(body, expected_attrs):
            """Authoring-client admission: exact GET-persisted profile AND attributes."""
            return (isinstance(body.get('profile'), dict) and body['profile'].get('id') == profile_id
                    and body.get('attributes') == expected_attrs)

        attrs = {'hnp_nic_cage_map': copy.deepcopy(self.C39_MAP), 'srv29_form_factor': 'ocp3'}
        response = api.post(reverse('dcim-api:moduletype-list'), {
            'manufacturer': manufacturer.pk, 'model': 'srv29-c39-api-nic', 'profile': profile_id,
            'attributes': copy.deepcopy(attrs)}, format='json')
        self.assertEqual(response.status_code, 201, response.content[:1000])
        type_id = response.json()['id']
        detail = reverse('dcim-api:moduletype-detail', kwargs={'pk': type_id})
        body = api.get(detail).json()
        self.assertTrue(admitted(body, attrs), body)
        self.assertEqual(body['profile']['name'], 'srv29-c39-api-nic-profile')
        for name in ('p0', 'p1'):  # fixture templates; layout parse needs the 2 logical ports
            InterfaceTemplate.objects.create(module_type_id=type_id, name=name, type=T400)
        layout = parse_layout(ModuleType.objects.select_related('profile').get(pk=type_id))
        self.assertEqual([(p.cage, p.logical_lane) for p in layout.ports], [('cage-0', 0), ('cage-0', 1)])

        # PATCH (complete attributes) changes the map; unrelated schema-backed attr preserved.
        swapped = copy.deepcopy(attrs)
        swapped['hnp_nic_cage_map']['ports'] = [{'cage': 'cage-0', 'logical_lane': 1},
                                                {'cage': 'cage-0', 'logical_lane': 0}]
        response = api.patch(detail, {'attributes': copy.deepcopy(swapped)}, format='json')
        self.assertEqual(response.status_code, 200, response.content[:1000])
        body = api.get(detail).json()
        self.assertTrue(admitted(body, swapped), body)
        # Unrelated-field PATCH: native clean re-validates; map + unrelated attr preserved exactly.
        response = api.patch(detail, {'description': 'srv29 fictional card'}, format='json')
        self.assertEqual(response.status_code, 200, response.content[:1000])
        body = api.get(detail).json()
        self.assertTrue(admitted(body, swapped), body)
        self.assertEqual(body['description'], 'srv29 fictional card')
        persisted = ModuleType.objects.get(pk=type_id)
        self.assertEqual((persisted.profile_id, persisted.attribute_data), (profile_id, swapped))

        # Bad schema: real native 400 with a meaningful validation body; nothing persisted.
        bad = copy.deepcopy(swapped)
        bad['hnp_nic_cage_map']['version'] = 'one'
        response = api.patch(detail, {'attributes': bad}, format='json')
        self.assertEqual(response.status_code, 400, response.content[:1000])
        text = response.content.decode('utf-8')
        self.assertIn('Invalid schema', text)
        self.assertIn('one', text)
        self.assertTrue(admitted(api.get(detail).json(), swapped), 'rejected PATCH changed persisted row')
        response = api.post(reverse('dcim-api:moduletype-list'), {
            'manufacturer': manufacturer.pk, 'model': 'srv29-c39-api-bad', 'profile': profile_id,
            'attributes': bad}, format='json')
        self.assertEqual(response.status_code, 400, response.content[:1000])
        self.assertIn('Invalid schema', response.content.decode('utf-8'))
        self.assertFalse(ModuleType.objects.filter(model='srv29-c39-api-bad').exists())

        # Profileless: observe native outcome; never fabricate a 400; GET result is NOT admitted.
        response = api.post(reverse('dcim-api:moduletype-list'), {
            'manufacturer': manufacturer.pk, 'model': 'srv29-c39-api-unprofiled',
            'attributes': {'hnp_nic_cage_map': copy.deepcopy(self.C39_MAP)}}, format='json')
        self.assertTrue(200 <= response.status_code < 300,
                        f'observed native profileless status {response.status_code}: {response.content[:500]}')
        unprofiled_id = response.json()['id']
        body = api.get(reverse('dcim-api:moduletype-detail', kwargs={'pk': unprofiled_id})).json()
        self.assertIsNone(body.get('profile'))
        self.assertFalse(admitted(body, {'hnp_nic_cage_map': self.C39_MAP}),
                         'profileless layout must not be admitted as configured')
        stored = ModuleType.objects.select_related('profile').get(pk=unprofiled_id)
        InterfaceTemplate.objects.create(module_type=stored, name='p0', type=T400)
        InterfaceTemplate.objects.create(module_type=stored, name='p1', type=T400)
        if has_layout(stored):
            # Native API kept the unprofiled key: strong runtime parser still refuses it.
            with self.assertRaises(ValidationError) as ctx:
                parse_layout(stored)
            self.assertIn('[nic_layout_profile_missing]', ' '.join(ctx.exception.messages))
        else:
            # Native clean cleared the attrs: the layout is lost, legacy path, nothing admitted.
            self.assertIsNone(parse_layout(stored))
            self.assertNotEqual(body.get('attributes'), {'hnp_nic_cage_map': self.C39_MAP})

        # Unprivileged authenticated token: native permission denial, no change.
        plain = model.objects.create_user(username='srv29-c39-api-noperm',
                                          email='srv29-c39-api-noperm@example.invalid', password=None)
        denied = APIClient()
        denied.credentials(HTTP_AUTHORIZATION=f'Token {Token.objects.create(user=plain).key}')
        response = denied.post(reverse('dcim-api:moduletype-list'), {
            'manufacturer': manufacturer.pk, 'model': 'srv29-c39-api-denied', 'profile': profile_id,
            'attributes': copy.deepcopy(attrs)}, format='json')
        self.assertEqual(response.status_code, 403, response.content[:500])
        self.assertFalse(ModuleType.objects.filter(model='srv29-c39-api-denied').exists())
        self.assertEqual(ModuleType.objects.get(pk=type_id).attribute_data, swapped)
        self.assertEqual(ModuleTypeProfile.objects.get(pk=profile_id).schema, schema)

    # --------------------------- CAGE39 SOURCE7: T10 mapped logical wiring + public export

    def _c39_mapped_edges(self):
        """Declared oracle for the AP-equivalent mapped fixture (never allocator/YAML output):
        server i -> leaf i, nic0-p0 -> E1/1/1 and nic0-p1 -> E1/1/2 (two channels of ONE cage);
        fabric part is the existing declared slot table for 4 leaves x 2 spines, k=2."""
        names = self._names(4, 4, 2)
        server_names, leaf_names, _ = names
        server_edges = Counter()
        for i, server in enumerate(server_names):
            for port, slot in enumerate(('E1/1/1', 'E1/1/2')):
                server_edges[(server, f'{NIC_ID}-p{port}', leaf_names[i], slot)] += 1
        _, fabric_edges = self._expected_edges(4, 4, 2, 2)
        self.assertEqual((sum(server_edges.values()), sum(fabric_edges.values())), (8, 16))
        return names, server_edges, fabric_edges

    def _c39_assert_artifact(self, text, names, server_edges, fabric_edges, labels, kinds, modes_expected):
        """Complete typed wiring artifact vs independently declared Counters/literals."""
        import re
        import yaml

        wiring = 'wiring.githedgehog.com/v1beta1'
        dns = re.compile(r'^[a-z0-9]([-a-z0-9]*[a-z0-9])?$')
        server_names, leaf_names, spine_names = names
        self.assertIsInstance(text, str)
        docs = list(yaml.safe_load_all(text))
        identities, by_kind = Counter(), {}
        for doc in docs:
            self.assertIsInstance(doc, dict, f'unstructured document {doc!r}')
            self.assertEqual(set(doc), {'apiVersion', 'kind', 'metadata', 'spec'}, doc)
            meta = doc['metadata']
            self.assertIsInstance(meta, dict)
            self.assertEqual(set(meta), {'name', 'namespace'}, meta)
            for value in (meta['name'], meta['namespace']):
                self.assertIsInstance(value, str)
                self.assertLessEqual(len(value), 63, value)
                self.assertRegex(value, dns)
            identities[(doc['apiVersion'], doc['kind'], meta['namespace'], meta['name'])] += 1
            by_kind.setdefault(doc['kind'], []).append(doc)
        self.assertEqual({i: n for i, n in identities.items() if n > 1}, {}, 'duplicate identity')
        self.assertEqual(Counter({k: len(v) for k, v in by_kind.items()}), kinds, 'document kinds/counts')
        switches = {}
        for doc in by_kind['Switch']:
            self.assertEqual(doc['apiVersion'], wiring)
            switches[doc['metadata']['name']] = (doc['spec'].get('role'), doc['spec'].get('profile'))
        expected_switches = {n: (HedgehogRoleChoices.SERVER_LEAF, labels['leaf']) for n in leaf_names}
        expected_switches.update({n: (HedgehogRoleChoices.SPINE, labels['spine']) for n in spine_names})
        self.assertEqual(switches, expected_switches, 'Switch identities/roles/profile labels')
        self.assertEqual({d['metadata']['name'] for d in by_kind['Server']}, set(server_names))
        server_links, fabric_links, endpoints, modes = Counter(), Counter(), Counter(), Counter()
        for doc in by_kind['Connection']:
            self.assertEqual(doc['apiVersion'], wiring)
            spec = doc['spec']
            self.assertIsInstance(spec, dict)
            self.assertEqual(len(spec), 1, f'connection has multiple/no modes: {spec}')
            (mode, body), = spec.items()
            self.assertIn(mode, ('unbundled', 'fabric'), f'unexpected connection mode {mode!r}')
            modes[mode] += 1
            if mode == 'unbundled':
                self.assertEqual(set(body), {'link'}, body)
                self.assertEqual(set(body['link']), {'server', 'switch'}, body)
                server = self._a35_port(body['link']['server'])
                switch = self._a35_port(body['link']['switch'])
                self.assertIn(server[0], server_names, server)
                self.assertIn(switch[0], leaf_names, switch)
                server_links[server + switch] += 1
                endpoints[server] += 1
                endpoints[switch] += 1
                continue
            self.assertEqual(set(body), {'links'}, body)
            pairs = set()
            for link in body['links']:
                self.assertEqual(set(link), {'leaf', 'spine'}, link)
                leaf, spine = self._a35_port(link['leaf']), self._a35_port(link['spine'])
                self.assertIn(leaf[0], leaf_names, leaf)
                self.assertIn(spine[0], spine_names, spine)
                fabric_links[leaf + spine] += 1
                endpoints[leaf] += 1
                endpoints[spine] += 1
                pairs.add((leaf[0], spine[0]))
            self.assertEqual(len(pairs), 1, f'fabric connection mixes pairs {pairs}')
        self.assertEqual(modes, modes_expected, 'connection modes')
        self.assertEqual(server_links, server_edges, 'exported server links (logical, shared optic)')
        self.assertEqual(fabric_links, fabric_edges, 'exported fabric links')
        self.assertEqual({e: n for e, n in endpoints.items() if n > 1}, {}, 'endpoint exported twice')
        expected_endpoints = set()
        for edge in list(server_edges) + list(fabric_edges):
            expected_endpoints.update({edge[:2], edge[2:]})
        self.assertEqual(set(endpoints), expected_endpoints, 'dropped/extra endpoints')
        return docs, (server_links, fabric_links)

    def _c39_export(self, names, server_edges, fabric_edges, labels, kinds, modes):
        """Public generate_yaml_for_plan + authenticated GET + repeat GET, each under a non-read
        SQL denial; full catalog/inventory/state/intent rows unchanged; returns bytes + graph."""
        import json

        from netbox_hedgehog.services.yaml_generator import generate_yaml_for_plan

        url = self._a35_export_url()
        before = self._c39_catalog_snapshot()
        service_text = self._a35_guarded(lambda: generate_yaml_for_plan(self.plan))
        first = self._a35_guarded(lambda: self.client.get(url))
        repeat = self._a35_guarded(lambda: self.client.get(url))
        self.assertEqual(self._c39_catalog_snapshot(), before, 'export changed persisted rows')
        disposition = f'attachment; filename="{self.plan.name}-{FABRIC}.yaml"'
        for response in (first, repeat):
            self.assertEqual(response.status_code, 200, response.content[:500])
            self.assertEqual(response['Content-Type'], 'text/yaml; charset=utf-8')
            self.assertEqual(response['Content-Disposition'], disposition)
        self.assertEqual(first.content, repeat.content, 'repeat download not byte-identical')
        args = (names, server_edges, fabric_edges, labels, kinds, modes)
        service_docs, _ = self._c39_assert_artifact(service_text, *args)
        download_docs, graph = self._c39_assert_artifact(first.content.decode('utf-8'), *args)

        def canonical(docs):
            return sorted(json.dumps(doc, sort_keys=True) for doc in docs)

        self.assertEqual(canonical(service_docs), canonical(download_docs), 'service and download differ')
        return first.content, graph

    def test_c39_t10_mapped_generation_export_bom_and_regeneration_agree(self):
        """T10/C09/C10: one shared optic per mapped cage. In the SAME generation the public BOM
        (one NIC + one server optic per server) and the public wiring service + authenticated
        download (8 logical unbundled links on the two channels, 16 fabric links, breakout
        suffixes preserved) agree with declared literals; same-intent regeneration replaces every
        Module PK and re-exports the identical logical graph. Fictional profile labels declared
        BEFORE generation; no real-hardware/hhfab/diagram qualification."""
        from netbox_hedgehog.services.bom_export import get_plan_bom

        fixture = self._c39_fixture('c39x')
        labels = self._a35_assign_profiles('c39x')
        self._c39_generate()
        names, server_edges, fabric_edges = self._c39_mapped_edges()
        kinds = Counter({'VLANNamespace': 1, 'IPv4Namespace': 1, 'Switch': 6, 'Server': 4, 'Connection': 16})
        modes = Counter({'unbundled': 8, 'fabric': 8})
        aggregate = {('nic', fixture['nic_type'].pk): 4, ('server_transceiver', fixture['optic'].pk): 4,
                     ('switch_transceiver', fixture['optic'].pk): 4}

        def physical_and_bom():
            self._c39_assert_physical(('cage-0',), 1)
            bom = get_plan_bom(self.plan)
            self.assertEqual({(i.section, i.module_type_id): i.quantity for i in bom.line_items}, aggregate)
            self.assertEqual(bom.module_total_qty, 12)

        physical_and_bom()
        self._a35_login()  # user/session setup BEFORE the read-only export boundary
        first_content, first_graph = self._c39_export(names, server_edges, fabric_edges, labels, kinds, modes)
        self.assertEqual(first_graph, (server_edges, fabric_edges))
        self.assertIn(b'/E1/1/1', first_content)
        self.assertIn(b'/E1/1/2', first_content)
        _, _, _, first_modules, _ = self._new_inventory()
        first_module_pks = {m.pk for m in first_modules}
        self.assertEqual(len(first_module_pks), 12)

        self._generate(devices_total=10, generated_interfaces=40, cables_total=24)
        self.assertFalse(Module.objects.filter(pk__in=first_module_pks).exists(), 'stale Module PK remains')
        physical_and_bom()
        _, second_graph = self._c39_export(names, server_edges, fabric_edges, labels, kinds, modes)
        self.assertEqual(second_graph, first_graph, 'regenerated logical graph differs')

    # ------------------------ CAGE39 SOURCE7: T11 captured-layout change during generation

    def test_c39_t11_optic_attribute_change_mid_generation_raises_and_rolls_back(self):
        """T11/C08 capture rule: after a valid prior generation, a scoped execute_wrapper applies
        ONE real test-owned optic attribute_data change (standard string) right after the first
        generation write (recursion-guarded). Placement uses the captured layout; the final
        provenance recheck must raise [nic_layout_provenance_changed] through public
        generate_all's atomic boundary, restoring the full prior inventory/terminations/tags/
        state/intent AND the optic attributes. Writes had begun (no zero-SQL claim). This is a
        controlled same-transaction fault, not a cross-process concurrency/fencing claim."""
        fixture = self._c39_fixture('c39v')
        optic = fixture['optic']
        self._c39_generate()
        prior = {model: _pks(model) - self.baseline[model] for model in INVENTORY_MODELS}
        state_rows = list(GenerationState.objects.filter(plan=self.plan).values())
        changed = dict(self.C39_OPTIC_ATTRS, standard='400GBASE-FR4')
        self.assertNotEqual(changed, self.C39_OPTIC_ATTRS)

        def after_first_write(head, text, flat):
            return 'after' if head in ('INSERT', 'UPDATE', 'DELETE') else None

        def change_optic():
            self.assertEqual(ModuleType.objects.filter(pk=optic.pk).update(attribute_data=changed), 1)

        message = self._c39_generate_with_injection(after_first_write, change_optic)
        self.assertIn('[nic_layout_provenance_changed]', message)
        self.assertEqual(ModuleType.objects.get(pk=optic.pk).attribute_data, self.C39_OPTIC_ATTRS)
        self.assertEqual(list(GenerationState.objects.filter(plan=self.plan).values()), state_rows)
        for model, pks in prior.items():
            self.assertTrue(pks and pks <= _pks(model), f'prior {model.__name__} rows lost')
        self.assertFalse(GenerationState.objects.get(plan=self.plan).is_dirty())

    # --------------------------------- CAGE39 SOURCE7: T09 real public YAML case ingest

    C39_INGEST_EXTRA = {'srv29_form_factor': 'ocp3'}

    def _c39_ingest_fixture(self, case):
        """Preconfigured test-owned mapped NIC type (map + unrelated schema-backed attribute, native
        full_clean), its declared cage already populated, a foreign mapped control type with an
        extra bay, a legacy type, and a server DeviceType. No plan yet."""
        import copy

        from dcim.models import ModuleBayTemplate, ModuleTypeProfile
        from netbox_hedgehog.management.commands.populate_transceiver_bays import populate_bays

        _breakout('2x400g')
        manufacturer = _manufacturer()
        server_type = DeviceType.objects.create(manufacturer=manufacturer, model=f'srv29-{case}-server',
                                                slug=f'srv29-{case}-server', u_height=1)
        schema = copy.deepcopy(self.C39_STRONG_SCHEMA)
        schema['properties']['srv29_form_factor'] = {'type': 'string', 'enum': ['ocp3', 'pcie']}
        profile = ModuleTypeProfile(name=f'srv29-{case}-ingest-profile', schema=schema)
        profile.full_clean()
        profile.save()
        attrs = dict(self.C39_INGEST_EXTRA, hnp_nic_cage_map=copy.deepcopy(self.C39_MAP))
        types = {}
        for key in ('mapped', 'foreign'):
            module_type = ModuleType(manufacturer=manufacturer, model=f'srv29-{case}-{key}-nic', profile=profile,
                                     attribute_data=copy.deepcopy(attrs))
            module_type.full_clean()
            module_type.save()
            for name in ('p0', 'p1'):
                InterfaceTemplate.objects.create(module_type=module_type, name=name, type=T400)
            types[key] = ModuleType.objects.select_related('profile').get(pk=module_type.pk)
            self.assertEqual(types[key].attribute_data, attrs)
        populate_bays(device_types=[], module_types=[types['mapped']])
        ModuleBayTemplate.objects.create(module_type=types['foreign'], name='srv29-foreign-extra')
        self.assertEqual(list(ModuleBayTemplate.objects.filter(module_type=types['mapped'])
                              .values_list('name', flat=True)), ['cage-0'])
        legacy = ModuleType.objects.create(manufacturer=manufacturer, model=f'srv29-{case}-legacy-nic')
        return {'server_type': server_type, 'mapped': types['mapped'], 'foreign': types['foreign'],
                'legacy': legacy, 'profile': profile, 'attrs': attrs}

    def _c39_v1_case(self, case_id, fx, nic_item_extra=None):
        """Genuinely valid minimal V1 case: one server class/NIC referencing the mapped type."""
        manufacturer = _manufacturer()
        nic_item = {'id': 'nic', 'manufacturer': 'mfr', 'model': fx['mapped'].model}
        nic_item.update(nic_item_extra or {})
        return {
            'meta': {'case_id': case_id, 'name': f'Case {case_id}', 'version': 1, 'managed_by': 'yaml'},
            'plan': {'name': f'srv29 plan {case_id}', 'status': 'draft'},
            'reference_data': {
                'manufacturers': [{'id': 'mfr', 'name': manufacturer.name, 'slug': manufacturer.slug}],
                'device_types': [{'id': 'srv', 'manufacturer': 'mfr', 'model': fx['server_type'].model,
                                  'slug': fx['server_type'].slug}],
                'module_types': [nic_item],
            },
            'switch_classes': [],
            'server_classes': [{'server_class_id': 'srv29-c39-srv', 'server_device_type': 'srv', 'quantity': 1}],
            'server_nics': [{'server_class': 'srv29-c39-srv', 'nic_id': NIC_ID, 'module_type': 'nic'}],
            'server_connections': [],
        }

    def _c39_catalog_rows(self):
        from dcim.models import ModuleBayTemplate, ModuleTypeProfile

        return {m.__name__: list(m.objects.order_by('pk').values())
                for m in (Manufacturer, DeviceType, ModuleType, ModuleTypeProfile, InterfaceTemplate,
                          ModuleBayTemplate, BreakoutOption)}

    def _c39_ingest_rows(self):
        rows = self._c39_catalog_rows()
        for model in (TopologyPlan, PlanServerClass, PlanServerNIC, PlanServerConnection, PlanSwitchClass,
                      SwitchPortZone, GenerationState):
            rows[model.__name__] = list(model.objects.order_by('pk').values())
        return rows

    @staticmethod
    def _c39_ingest_codes(exc):
        errors = getattr(exc, 'errors', None)
        if errors is None and exc.args:
            errors = exc.args[0]
        return sorted({e.get('code') for e in (errors or []) if isinstance(e, dict)})

    def _c39_ingest_reject(self, case, mode, code):
        """Real public apply_case must raise the specific typed code; the atomic ingest leaves
        every persisted row unchanged (writes may have been attempted: NO zero-SQL claim)."""
        from netbox_hedgehog.test_cases.exceptions import TestCaseValidationError
        from netbox_hedgehog.test_cases.ingest import apply_case

        before = self._c39_ingest_rows()
        with self.assertRaises(TestCaseValidationError) as ctx:
            apply_case(case, reference_mode=mode)
        self.assertEqual(self._c39_ingest_codes(ctx.exception), [code], getattr(ctx.exception, 'errors', None))
        self.assertEqual(self._c39_ingest_rows(), before, f'{code}: persistent partial change')

    def _c39_assert_mapped_intact(self, fx):
        for key in ('mapped', 'foreign'):
            row = ModuleType.objects.get(pk=fx[key].pk)
            self.assertEqual((row.profile_id, row.attribute_data), (fx['profile'].pk, fx['attrs']), key)
            self.assertEqual(sorted(InterfaceTemplate.objects.filter(module_type=row).values_list('name', 'type')),
                             [('p0', T400), ('p1', T400)], key)

    def test_c39_t09_v1_mapped_reference_consumed_read_only_both_modes(self):
        """T09/C02 positive: in BOTH require and ensure mode, a configured mapped type is consumed
        when attribute_data is ABSENT or the EXACT whole typed payload (with exact existing
        templates); no attribute/profile/InterfaceTemplate/bay/foreign-catalog row changes."""
        import copy

        from netbox_hedgehog.test_cases.ingest import apply_case

        fx = self._c39_ingest_fixture('c39q')
        exact = {'attribute_data': copy.deepcopy(fx['attrs']),
                 'interface_templates': [{'name': 'p0', 'type': T400}, {'name': 'p1', 'type': T400}]}
        for mode in ('require', 'ensure'):
            for label, extra in (('absent', {}), ('exact', exact)):
                with self.subTest(mode=mode, variant=label):
                    case_id = f'srv29_c39q_{mode}_{label}'
                    catalog_before = self._c39_catalog_rows()
                    plan = apply_case(self._c39_v1_case(case_id, fx, copy.deepcopy(extra)), reference_mode=mode)
                    self.assertEqual(self._c39_catalog_rows(), catalog_before, 'catalog rows rewritten')
                    nics = list(PlanServerNIC.objects.filter(server_class__plan=plan)
                                .values_list('nic_id', 'module_type_id'))
                    self.assertEqual(nics, [(NIC_ID, fx['mapped'].pk)])
                    self.assertFalse(PlanServerConnection.objects.filter(server_class__plan=plan).exists())
                    self._c39_assert_mapped_intact(fx)

    def test_c39_t09_v1_mapped_reference_alterations_rejected_atomically_both_modes(self):
        """T09/C02 negative matrix (both modes) after a positive control: omitted unrelated attr,
        changed unrelated, explicit null, empty, changed map, extra attr, new template, wrong-type
        template and name-only template -> mapped_catalog_reference_conflict; atomic, intact."""
        import copy

        from netbox_hedgehog.test_cases.ingest import apply_case

        fx = self._c39_ingest_fixture('c39r')
        apply_case(self._c39_v1_case('srv29_c39r_control', fx), reference_mode='require')  # fixture valid
        swapped = copy.deepcopy(self.C39_MAP)
        swapped['ports'] = [{'cage': 'cage-0', 'logical_lane': 1}, {'cage': 'cage-0', 'logical_lane': 0}]
        attrs = fx['attrs']
        variants = [
            ('subset_map_only', {'attribute_data': {'hnp_nic_cage_map': copy.deepcopy(self.C39_MAP)}}),
            ('changed_unrelated', {'attribute_data': dict(copy.deepcopy(attrs), srv29_form_factor='pcie')}),
            ('explicit_null', {'attribute_data': None}),
            ('empty', {'attribute_data': {}}),
            ('changed_map', {'attribute_data': dict(copy.deepcopy(attrs), hnp_nic_cage_map=swapped)}),
            ('extra_attr', {'attribute_data': dict(copy.deepcopy(attrs), srv29_extra='x')}),
            ('new_template', {'interface_templates': [{'name': 'p2', 'type': T400}]}),
            ('wrong_type_template', {'interface_templates': [{'name': 'p0', 'type': T100}]}),
            ('name_only_template', {'interface_templates': [{'name': 'p0'}]}),
        ]
        for mode in ('require', 'ensure'):
            for label, extra in variants:
                with self.subTest(mode=mode, variant=label):
                    case = self._c39_v1_case(f'srv29_c39r_{mode}_{label}', fx, copy.deepcopy(extra))
                    self._c39_ingest_reject(case, mode, 'mapped_catalog_reference_conflict')
                    self._c39_assert_mapped_intact(fx)
                    self.assertFalse(InterfaceTemplate.objects.filter(module_type=fx['mapped'], name='p2').exists())

    def test_c39_t09_v1_duplicate_reference_id_rejected_before_effects(self):
        """T09/review01 P2-1 counterexample: a NEW type with a map then a legacy type under the SAME
        rid cannot author the first row; an existing mapped declaration with a conflicting payload
        then a same-rid legacy declaration cannot overwrite the mapped raw payload. Both modes:
        duplicate_reference_id before effects, no new type created, mapped payload intact."""
        import copy

        fx = self._c39_ingest_fixture('c39s')
        new_model = 'srv29-c39s-new-mapped-nic'
        changed = dict(copy.deepcopy(fx['attrs']), srv29_form_factor='pcie')
        legacy_row = list(ModuleType.objects.filter(pk=fx['legacy'].pk).values())
        for mode in ('require', 'ensure'):
            for label, first in (
                    ('new_type_with_map', {'model': new_model,
                                           'attribute_data': {'hnp_nic_cage_map': copy.deepcopy(self.C39_MAP)}}),
                    ('existing_mapped_conflicting', {'model': fx['mapped'].model, 'attribute_data': changed})):
                with self.subTest(mode=mode, variant=label):
                    case = self._c39_v1_case(f'srv29_c39s_{mode}_{label}', fx)
                    case['reference_data']['module_types'] = [
                        dict({'id': 'nic', 'manufacturer': 'mfr'}, **copy.deepcopy(first)),
                        {'id': 'nic', 'manufacturer': 'mfr', 'model': fx['legacy'].model},
                    ]
                    self._c39_ingest_reject(case, mode, 'duplicate_reference_id')
                    self.assertFalse(ModuleType.objects.filter(model=new_model).exists(), 'first new type authored')
                    self._c39_assert_mapped_intact(fx)
                    self.assertEqual(list(ModuleType.objects.filter(pk=fx['legacy'].pk).values()), legacy_row)

    def test_c39_t09_v2_configured_reference_survives_layout_authoring_rejected(self):
        """T09/C03: genuinely valid V2 case referencing the configured mapped NIC type ingests;
        map/profile/templates survive and NO PlanServerConnection is produced (current V2 is not
        a server_connections producer). Layout authoring under the NIC, its module_type
        reference or test_fixtures -> nic_layout_authoring_forbidden before normalization."""
        import copy

        from netbox_hedgehog.test_cases.ingest import apply_case

        fx = self._c39_ingest_fixture('c39t')
        manufacturer = _manufacturer()
        layout = {'hnp_nic_cage_map': copy.deepcopy(self.C39_MAP)}

        def v2(case_id, nic_extra=None, mt_extra=None, fixtures=None):
            nic = {'server_class': 'srv29-c39t-srv', 'nic_id': NIC_ID,
                   'module_type': dict({'manufacturer': manufacturer.slug, 'model': fx['mapped'].model},
                                       **copy.deepcopy(mt_extra or {}))}
            nic.update(copy.deepcopy(nic_extra or {}))
            case = {
                'apiVersion': 'diet/v2', 'kind': 'TopologyPlan',
                'metadata': {'case_id': case_id, 'name': f'Case {case_id}', 'version': 2, 'managed_by': 'yaml'},
                'spec': {
                    'plan': {'name': f'srv29 plan {case_id}', 'status': 'draft'},
                    'server_classes': [{'server_class_id': 'srv29-c39t-srv',
                                        'server_device_type': fx['server_type'].slug, 'quantity': 1}],
                    'server_nics': [nic],
                    'server_connections': [{'server_class': 'srv29-c39t-srv', 'connection_id': 'srv29-c39t-conn',
                                            'nic': NIC_ID, 'port_index': 0, 'ports_per_connection': 2,
                                            'speed': 400}],
                },
            }
            if fixtures is not None:
                case['test_fixtures'] = copy.deepcopy(fixtures)
            return case

        catalog_before = self._c39_catalog_rows()
        plan = apply_case(v2('srv29_c39t_valid'))
        self.assertEqual(self._c39_catalog_rows(), catalog_before, 'V2 ingest rewrote catalog rows')
        self.assertEqual(list(PlanServerNIC.objects.filter(server_class__plan=plan)
                              .values_list('nic_id', 'module_type_id')), [(NIC_ID, fx['mapped'].pk)])
        self.assertFalse(PlanServerConnection.objects.filter(server_class__plan=plan).exists(),
                         'V2 must not be treated as a server_connections producer')
        self._c39_assert_mapped_intact(fx)
        for label, kwargs in (
                ('nic', {'nic_extra': layout}),
                ('module_type', {'mt_extra': layout}),
                ('test_fixtures', {'fixtures': {'module_types': [{
                    'manufacturer': manufacturer.slug, 'model': 'srv29-c39t-fixture-nic',
                    'attribute_data': layout}]}})):
            with self.subTest(label):
                self._c39_ingest_reject(v2(f'srv29_c39t_{label}', **kwargs), 'ensure', 'nic_layout_authoring_forbidden')
                self.assertFalse(ModuleType.objects.filter(model='srv29-c39t-fixture-nic').exists())
                self._c39_assert_mapped_intact(fx)

    # ------- CAGE39 SOURCE9: read-only sync guard, complete public T11 matrix, virtual controls
    # Fictional test-owned rows only. Nothing mocked; no production helper patched.

    def _c39_sync_rows(self):
        """Full rows for read-only proofs: ``_c39_catalog_snapshot`` (inventory, cable
        terminations, tag memberships, this plan's GenerationState, plan/server/NIC/
        connection/zone intent, DeviceTypeExtension, BreakoutOption, DeviceType, ModuleType,
        InterfaceTemplate, ModuleBayTemplate, ModuleTypeProfile) PLUS every GenerationState row
        of every plan (complete saved history)."""
        snap = self._c39_catalog_snapshot()
        snap['GenerationStateAll'] = list(GenerationState.objects.order_by('pk').values())
        return snap

    def _c39_sync_guarded(self, operation):
        """Run ONE public read (is_dirty / sync_display_state / live build_plan_snapshot /
        population admission probe) under an execute_wrapper that allows only SELECT and
        transaction control. Any other statement is RECORDED independently and refused: the
        live snapshot builder deliberately converts exceptions into an invalid marker, so the
        recorded list (not a propagated exception) is the mutation-attempt proof. Full rows
        before == after. Returns the call's actual result. No auth/session setup needed."""
        attempts = []
        allowed_heads = ('SELECT', 'SAVEPOINT', 'RELEASE', 'ROLLBACK', 'BEGIN', 'COMMIT')

        def deny(execute, sql, params, many, context):
            text = sql.strip() if isinstance(sql, str) else str(sql).strip()
            head = text.split(None, 1)[0].upper() if text else ''
            if head not in allowed_heads:
                attempts.append(text[:200])
                raise AssertionError(f'mutation/unexpected SQL during read-only call: {text[:200]}')
            return execute(sql, params, many, context)

        before = self._c39_sync_rows()
        with connection.execute_wrapper(deny):
            result = operation()
        self.assertEqual(attempts, [], 'SQL mutation/unexpected statement attempted during read-only call')
        self.assertEqual(self._c39_sync_rows(), before, 'read-only call changed persisted rows')
        return result

    def test_c39_t11_public_matrix_rehashed_invalid_saved_evidence_both_methods(self):
        """T11/C08 complete public matrix on an ACTUAL generated mapped plan/state.

        Every snapshot_contract_v1 missing/duplicate/provenance/version/bool-ID/template/
        ordinal/mode/optic/bay/connection/manifest/base-linkage/internal-coherence variant is
        derived from the real saved evidence and (where the defect is structural/semantic)
        RE-HASHED at NIC and root level, so it is never merely a checksum failure. For each:
        the exact typed extension_errors code; pure classify_snapshot_sync(bad, bad)
        incomplete; public is_dirty() with that saved evidence vs the VALID live current
        (honest label: saved-invalid -> dirty, NOT an equal-invalid proof); public
        sync_display_state() live and with current=identical bad (these record corruptions
        are not producible through DB constraints). The genuine live invalid-EQUAL journey is
        test_c39_t11_live_invalid_current_equal_saved_dirty_and_incomplete. Then unchanged-FK
        breakout_topology change (explicitly INVALID current -> incomplete) and BreakoutOption
        provenance change (from_speed doubled, still coherent -> valid CHANGED). Every public
        read/live build is mutation-denied with full-row preservation; saved history is never
        rewritten."""
        import copy

        from netbox_hedgehog.models.topology_planning.generation import (
            SYNC_CHANGED,
            SYNC_IN_SYNC,
            SYNC_SNAPSHOT_INCOMPLETE,
            classify_snapshot_sync,
        )
        from netbox_hedgehog.services.nic_cage_layout import SNAPSHOT_KEY, extension_errors
        from netbox_hedgehog.utils.snapshot_builder import build_plan_snapshot

        fixture = self._c39_fixture('c39pm')
        self._c39_generate()
        state = GenerationState.objects.get(plan=self.plan)
        saved_row = list(GenerationState.objects.filter(pk=state.pk).values())
        valid = copy.deepcopy(state.snapshot)
        self.assertEqual(extension_errors(valid[SNAPSHOT_KEY], base_snapshot=valid), [])
        self.assertFalse(self._c39_sync_guarded(state.is_dirty))
        self.assertEqual(self._c39_sync_guarded(state.sync_display_state), SYNC_IN_SYNC)
        record = valid[SNAPSHOT_KEY]['nics'][0]
        self.assertEqual(len(valid[SNAPSHOT_KEY]['nics']), 1)
        self.assertEqual([(t['logical_index'], t['name']) for t in record['interface_templates']],
                         [(0, 'p0'), (1, 'p1')])
        self.assertEqual([b['name'] for b in record['bay_templates']], ['cage-0'])
        self.assertEqual((len(record['connections']), len(record['optics']), len(record['modes'])), (1, 1, 1))
        self.assertTrue(record['layout_present'])

        def ext(s):
            return s[SNAPSHOT_KEY]

        def nic(s):
            return s[SNAPSHOT_KEY]['nics'][0]

        def conn(s):
            return nic(s)['connections'][0]

        def names(*new):
            def fn(s):
                for row, name in zip(nic(s)['interface_templates'], new):
                    row['name'] = name
            return fn

        def add_cage(s):
            n = nic(s)
            n['layout']['cages'].append({'cage': 'cage-9', 'breakout_id': '2x400g'})
            n['modes'].append(dict(n['modes'][0], cage='cage-9'))

        def overlap(s):
            extra = dict(conn(s), connection_id='srv29-c39pm-dup', ports_per_connection=1)
            nic(s)['connections'].append(extra)
            ext(s)['expected_connection_keys'] = sorted(
                ext(s)['expected_connection_keys'] + [[extra['server_class_id'], extra['connection_id']]])

        def ghost(key, pair):
            def fn(s):
                ext(s)[key] = sorted(ext(s)[key] + [list(pair)])
            return fn

        def cage_names(name):
            def fn(s):
                n = nic(s)
                for row in n['layout']['ports'] + n['layout']['cages'] + n['modes']:
                    row['cage'] = name
            return fn

        def null_optic(s):
            conn(s)['transceiver_module_type_id'] = None
            nic(s)['optics'] = []

        def claim_legacy(s):
            nic(s)['layout_present'] = False

        def demote_to_legacy(s):
            nic(s).update(layout_present=False, layout=None, modes=[])

        def set_ext(value):
            def fn(s):
                s[SNAPSHOT_KEY] = copy.deepcopy(value)
            return fn

        def tamper_zone(s):
            conn(s)['target_zone_id'] += 1000  # semantically valid, deliberately NOT rehashed

        marker = {'version': 1, 'status': 'invalid', 'errors': ['nic_layout_version']}
        # (label, mutation, exact code, rehash NIC+root digests)
        cases = [
            # --- root / version / manifests
            ('extension_not_object', set_ext(['srv29']), 'not_object', False),
            ('extension_null', set_ext(None), 'not_object', False),
            ('saved_invalid_marker', set_ext(marker), 'invalid_marker', False),
            ('extra_root_key', lambda s: ext(s).update(srv29_extra=1), 'root_keys', True),
            ('version_bool', lambda s: ext(s).update(version=True), 'version', True),
            ('version_unknown', lambda s: ext(s).update(version=2), 'version', True),
            ('nic_manifest_not_list', lambda s: ext(s).update(expected_nic_keys='srv29'), 'nic_manifest', True),
            ('empty_manifest', lambda s: ext(s).update(expected_nic_keys=[], nics=[]), 'nic_manifest_empty', True),
            ('nics_not_list', lambda s: ext(s).update(nics={}), 'nics', False),
            ('ghost_nic_key', ghost('expected_nic_keys', ('srv29-zz-class', 'srv29-zz-nic')), 'nic_completeness', True),
            ('ghost_connection_key', ghost('expected_connection_keys', ('srv29-zz-class', 'srv29-zz-conn')),
             'connection_completeness', True),
            ('base_connection_linkage', lambda s: s.update(connections=[]), 'base_connection_linkage', True),
            # --- NIC rows: missing / duplicate / shape / bool IDs / provenance
            ('omitted_nic', lambda s: ext(s).update(nics=[]), 'nic_completeness', True),
            ('duplicate_nic', lambda s: ext(s)['nics'].append(copy.deepcopy(nic(s))), 'nic_completeness', True),
            ('nic_missing_required_field', lambda s: nic(s).pop('optics'), 'nic_record', True),
            ('bool_module_type_id', lambda s: nic(s).update(module_type_id=True), 'nic_fields', True),
            ('bool_profile_id', lambda s: nic(s).update(profile_id=True), 'nic_fields', True),
            ('layout_present_not_bool', lambda s: nic(s).update(layout_present='yes'), 'nic_fields', True),
            ('optin_profile_id_null', lambda s: nic(s).update(profile_id=None), 'optin_profile', True),
            ('optin_profile_schema_hash_null', lambda s: nic(s).update(profile_schema_sha256=None),
             'optin_profile', True),
            ('mapped_claims_legacy', claim_legacy, 'legacy_layout', True),
            ('no_opted_in_nic', demote_to_legacy, 'no_opted_in_nic', True),
            ('layout_version_unknown', lambda s: nic(s)['layout'].update(version=2), 'layout_record', True),
            ('layout_version_bool', lambda s: nic(s)['layout'].update(version=True), 'layout_record', True),
            # --- interface templates / ordinals / natural order
            ('bool_template_id', lambda s: nic(s)['interface_templates'][0].update(template_id=True),
             'template_record', True),
            ('template_ordinals_permuted', lambda s: nic(s)['interface_templates'].reverse(), 'template_index', True),
            ('template_duplicate_id', lambda s: nic(s)['interface_templates'][1].update(
                template_id=nic(s)['interface_templates'][0]['template_id']), 'template_duplicate', True),
            ('omitted_template', lambda s: nic(s).update(interface_templates=nic(s)['interface_templates'][:1]),
             'layout_index', True),
            ('natural_order_p1_at_0_p0_at_1', names('p1', 'p0'), 'template_order', True),
            ('lexical_order_p10_at_0_p2_at_1', names('p10', 'p2'), 'template_order', True),
            ('mapped_module_token_first', names('{module}-p0', 'p1'), 'layout_template_module_token', True),
            # --- layout geometry / ports / cages
            ('empty_geometry', lambda s: nic(s)['layout'].update(ports=[]), 'layout_empty_geometry', True),
            ('bool_logical_lane', lambda s: nic(s)['layout']['ports'][0].update(logical_lane=True),
             'layout_port', True),
            ('substitution_cage_name', cage_names('{module}'), 'layout_cage_name', True),
            ('trim_unstable_cage_name', cage_names('cage-0 '), 'layout_cage_name', True),
            ('unreferenced_cage', add_cage, 'layout_unreferenced_cage', True),
            # --- modes
            ('omitted_mode', lambda s: nic(s).update(modes=[]), 'mode_coverage', True),
            ('duplicate_mode', lambda s: nic(s)['modes'].append(copy.deepcopy(nic(s)['modes'][0])),
             'mode_duplicate', True),
            ('mode_binding', lambda s: nic(s)['modes'][0].update(breakout_id='1x800g'), 'mode_binding', True),
            ('mode_capacity_incoherent', lambda s: nic(s)['modes'][0].update(from_speed=400), 'mode_record', True),
            ('bool_breakout_pk', lambda s: nic(s)['modes'][0].update(breakout_pk=True), 'mode_record', True),
            # --- bays
            ('omitted_used_cage_bay', lambda s: nic(s).update(bay_templates=[]), 'used_cage_missing_bay', True),
            ('duplicate_bay', lambda s: nic(s)['bay_templates'].append(copy.deepcopy(nic(s)['bay_templates'][0])),
             'bay_duplicate', True),
            # --- optics / provenance
            ('omitted_optic', lambda s: nic(s).update(optics=[]), 'optic_coverage', True),
            ('duplicate_optic', lambda s: nic(s)['optics'].append(copy.deepcopy(nic(s)['optics'][0])),
             'optic_duplicate', True),
            ('bool_optic_id', lambda s: nic(s)['optics'][0].update(module_type_id=True), 'optic_fields', True),
            ('optic_attribute_hash_null', lambda s: nic(s)['optics'][0].update(attribute_data_sha256=None),
             'optic_fields', True),
            ('optic_profile_null', lambda s: nic(s)['optics'][0].update(profile_id=None),
             'optin_optic_provenance', True),
            ('optic_topology_null', lambda s: nic(s)['optics'][0].update(breakout_topology=None),
             'optin_optic_provenance', True),
            ('optic_mode_mismatch', lambda s: nic(s)['optics'][0].update(breakout_topology='1x800g'),
             'used_cage_optic_mode', True),
            # --- connections / internal coherence
            ('omitted_connection', lambda s: nic(s).update(connections=[], optics=[]),
             'connection_completeness', True),
            ('duplicate_connection', lambda s: nic(s)['connections'].append(copy.deepcopy(conn(s))),
             'connection_duplicate', True),
            ('overlapping_ranges', overlap, 'connection_index_collision', True),
            ('range_beyond_templates', lambda s: conn(s).update(port_index=1), 'connection_range', True),
            ('speed_vs_mode', lambda s: conn(s).update(speed=800), 'used_cage_speed', True),
            ('cross_owner', lambda s: conn(s).update(server_class_id='srv29-other'), 'connection_owner', True),
            ('null_target_zone', lambda s: conn(s).update(target_zone_id=None), 'connection_fields', True),
            ('bool_port_index', lambda s: conn(s).update(port_index=False), 'connection_fields', True),
            ('used_cage_null_optic', null_optic, 'used_cage_null_optic', True),
            # --- digests (deliberately NOT rehashed)
            ('nic_digest_mismatch', tamper_zone, 'nic_digest_mismatch', False),
            ('nic_digest_not_hex', lambda s: nic(s).update(evidence_sha256='srv29'), 'nic_digest', False),
            ('root_digest_mismatch', lambda s: ext(s).update(evidence_sha256='0' * 64), 'root_digest_mismatch', False),
            ('root_digest_not_hex', lambda s: ext(s).update(evidence_sha256='srv29'), 'root_digest', False),
        ]
        self.assertEqual(len({label for label, _, _, _ in cases}), len(cases), 'duplicate case label')
        for label, mutate, code, rehash in cases:
            with self.subTest(label):
                bad = copy.deepcopy(valid)
                mutate(bad)
                if rehash:
                    self._c39_rehash(bad[SNAPSHOT_KEY])
                self.assertEqual(extension_errors(bad[SNAPSHOT_KEY], base_snapshot=bad), [code], label)
                self.assertEqual(classify_snapshot_sync(copy.deepcopy(bad), copy.deepcopy(bad)),
                                 SYNC_SNAPSHOT_INCOMPLETE, f'{label}: pure identical-invalid')
                probe = GenerationState.objects.get(pk=state.pk)  # actual generated row ...
                probe.snapshot = copy.deepcopy(bad)  # ... with in-memory saved evidence only (never saved)
                # Saved-invalid vs VALID live current: dirty. NOT an equal-invalid proof.
                self.assertTrue(self._c39_sync_guarded(probe.is_dirty), f'{label}: saved-invalid is_dirty')
                self.assertEqual(self._c39_sync_guarded(probe.sync_display_state), SYNC_SNAPSHOT_INCOMPLETE,
                                 f'{label}: saved-invalid vs live current')
                # Identical bad current (record corruption not producible via DB constraints).
                self.assertEqual(
                    self._c39_sync_guarded(lambda: probe.sync_display_state(current=copy.deepcopy(bad))),
                    SYNC_SNAPSHOT_INCOMPLETE, f'{label}: public identical-invalid current')

        # Positive controls: the classifier is not blanket-incomplete. Natural multi-digit order
        # (p2 at 0, p10 at 1) is internally VALID evidence; identical -> in_sync, vs live -> changed.
        natural = copy.deepcopy(valid)
        names('p2', 'p10')(natural)
        self._c39_rehash(natural[SNAPSHOT_KEY])
        self.assertEqual(extension_errors(natural[SNAPSHOT_KEY], base_snapshot=natural), [])
        self.assertEqual(classify_snapshot_sync(copy.deepcopy(natural), copy.deepcopy(natural)), SYNC_IN_SYNC)
        probe = GenerationState.objects.get(pk=state.pk)
        probe.snapshot = copy.deepcopy(natural)
        self.assertTrue(self._c39_sync_guarded(probe.is_dirty))
        self.assertEqual(self._c39_sync_guarded(probe.sync_display_state), SYNC_CHANGED)
        probe.snapshot = copy.deepcopy(valid)
        self.assertFalse(self._c39_sync_guarded(probe.is_dirty))
        self.assertEqual(self._c39_sync_guarded(probe.sync_display_state), SYNC_IN_SYNC)

        # Unchanged optic FK, changed breakout_topology -> live current is the typed INVALID
        # marker (explicit classification: incomplete, never in_sync, never a fake 'changed').
        optics = ModuleType.objects.filter(pk=fixture['optic'].pk)
        optics.update(attribute_data=dict(self.C39_OPTIC_ATTRS, breakout_topology='1x800g'))
        state.refresh_from_db()
        current = self._c39_sync_guarded(lambda: build_plan_snapshot(self.plan))
        self.assertEqual(current[SNAPSHOT_KEY], {'version': 1, 'status': 'invalid',
                                                 'errors': ['nic_layout_optic_mode']})
        self.assertEqual(PlanServerConnection.objects.get(pk=fixture['conn'].pk).transceiver_module_type_id,
                         fixture['optic'].pk, 'FK unchanged')
        self.assertTrue(self._c39_sync_guarded(state.is_dirty), 'unchanged-FK mode change dirty')
        self.assertEqual(self._c39_sync_guarded(state.sync_display_state), SYNC_SNAPSHOT_INCOMPLETE)
        optics.update(attribute_data=dict(self.C39_OPTIC_ATTRS))
        self.assertFalse(self._c39_sync_guarded(state.is_dirty))

        # BreakoutOption provenance value change (from_speed doubled 800 -> 1600; 2x400 still
        # coherent): unchanged PK/breakout_id, valid current with different mode evidence -> CHANGED.
        breakout = BreakoutOption.objects.filter(breakout_id='2x400g')
        self.assertEqual(list(breakout.values_list('from_speed', 'logical_ports', 'logical_speed')), [(800, 2, 400)])
        breakout_pk = breakout.get().pk
        breakout.update(from_speed=1600)
        current = self._c39_sync_guarded(lambda: build_plan_snapshot(self.plan))
        self.assertEqual(extension_errors(current[SNAPSHOT_KEY], base_snapshot=current), [], 'still coherent')
        self.assertEqual([(m['breakout_pk'], m['from_speed']) for m in current[SNAPSHOT_KEY]['nics'][0]['modes']],
                         [(breakout_pk, 1600)])
        self.assertEqual([(m['breakout_pk'], m['from_speed']) for m in valid[SNAPSHOT_KEY]['nics'][0]['modes']],
                         [(breakout_pk, 800)])
        self.assertTrue(self._c39_sync_guarded(state.is_dirty), 'BreakoutOption provenance change dirty')
        self.assertEqual(self._c39_sync_guarded(state.sync_display_state), SYNC_CHANGED)
        breakout.update(from_speed=800)
        self.assertFalse(self._c39_sync_guarded(state.is_dirty))
        self.assertEqual(self._c39_sync_guarded(state.sync_display_state), SYNC_IN_SYNC)
        self.assertEqual(list(GenerationState.objects.filter(pk=state.pk).values()), saved_row,
                         'saved history rewritten')

    def test_c39_t11_live_invalid_current_equal_saved_dirty_and_incomplete(self):
        """T11 genuine invalid-EQUAL journey (no builder patch, no fake current injection).

        After a valid generation, an owned ORM fixture mutation makes the DB current genuinely
        invalid: (1) malformed stored profile.schema -> LIVE build_plan_snapshot yields the
        typed marker with exact code nic_layout_profile_schema_invalid (no exception/500);
        (2) key-present bad map (duplicate channel). The saved snapshot is then set (test-owned
        ORM fixture write, outside the guards) to the EXACT fresh current invalid snapshot and
        fresh current == saved is asserted BEFORE the read-method calls. Public is_dirty() must
        be True and sync_display_state() snapshot_incomplete although both are equal; all reads
        are mutation-denied and full rows preserved; the original saved history is restored."""
        import copy

        from dcim.models import ModuleTypeProfile
        from netbox_hedgehog.models.topology_planning.generation import (
            SYNC_IN_SYNC,
            SYNC_SNAPSHOT_INCOMPLETE,
            classify_snapshot_sync,
        )
        from netbox_hedgehog.services.nic_cage_layout import SNAPSHOT_KEY
        from netbox_hedgehog.utils.snapshot_builder import build_plan_snapshot, compare_snapshots

        fixture = self._c39_fixture('c39li')
        self._c39_generate()
        state = GenerationState.objects.get(plan=self.plan)
        saved_row = list(GenerationState.objects.filter(pk=state.pk).values())
        original_saved = copy.deepcopy(state.snapshot)
        self.assertIn(SNAPSHOT_KEY, original_saved)
        self.assertFalse(self._c39_sync_guarded(state.is_dirty))
        profiles = ModuleTypeProfile.objects.filter(pk=fixture['profile'].pk)
        original_schema = copy.deepcopy(profiles.get().schema)
        duplicate_channel = copy.deepcopy(self.C39_MAP)
        duplicate_channel['ports'] = [{'cage': 'cage-0', 'logical_lane': 0}, {'cage': 'cage-0', 'logical_lane': 0}]

        def base(snapshot):
            return {k: v for k, v in snapshot.items() if k != SNAPSHOT_KEY}

        journeys = (
            ('malformed_stored_profile_schema', 'nic_layout_profile_schema_invalid',
             lambda: profiles.update(schema={'type': 'srv29-not-a-type', 'properties': {'hnp_nic_cage_map': {}}}),
             lambda: profiles.update(schema=copy.deepcopy(original_schema))),
            ('key_present_duplicate_channel_map', 'nic_layout_duplicate_channel',
             lambda: self._c39_set_map(copy.deepcopy(duplicate_channel)),
             lambda: self._c39_set_map(copy.deepcopy(self.C39_MAP))),
        )
        for label, code, corrupt, restore in journeys:
            with self.subTest(label):
                corrupt()
                fresh = self._c39_sync_guarded(lambda: build_plan_snapshot(self.plan))
                self.assertEqual(fresh[SNAPSHOT_KEY], {'version': 1, 'status': 'invalid', 'errors': [code]})
                self.assertTrue(compare_snapshots(base(fresh), base(original_saved)), 'only the extension differs')
                GenerationState.objects.filter(pk=state.pk).update(snapshot=copy.deepcopy(fresh))
                state.refresh_from_db()
                current = self._c39_sync_guarded(lambda: build_plan_snapshot(self.plan))
                self.assertEqual(current, state.snapshot, f'{label}: fresh current must EQUAL saved first')
                self.assertTrue(compare_snapshots(current, state.snapshot))
                self.assertTrue(self._c39_sync_guarded(state.is_dirty), f'{label}: equal-invalid is_dirty')
                self.assertEqual(self._c39_sync_guarded(state.sync_display_state), SYNC_SNAPSHOT_INCOMPLETE,
                                 f'{label}: equal-invalid live sync_display_state')
                self.assertEqual(
                    self._c39_sync_guarded(lambda: state.sync_display_state(current=copy.deepcopy(current))),
                    SYNC_SNAPSHOT_INCOMPLETE)
                self.assertEqual(classify_snapshot_sync(copy.deepcopy(current), copy.deepcopy(current)),
                                 SYNC_SNAPSHOT_INCOMPLETE)
                state.refresh_from_db()
                self.assertEqual(state.snapshot, fresh, 'read methods rewrote the saved snapshot')
                restore()
                GenerationState.objects.filter(pk=state.pk).update(snapshot=copy.deepcopy(original_saved))
                state.refresh_from_db()
                self.assertFalse(self._c39_sync_guarded(state.is_dirty), f'{label}: restored')
                self.assertEqual(self._c39_sync_guarded(state.sync_display_state), SYNC_IN_SYNC)
        self.assertEqual(list(GenerationState.objects.filter(pk=state.pk).values()), saved_row)

    def test_c39_t11_template_natural_order_mapped_and_legacy_controls(self):
        """T11/review03 P2-2 natural ordering on a live mixed mapped+legacy capture (pure
        classification; no generation): re-hashed recorded names that contradict natural
        ordinals are invalid for BOTH mapped and legacy records; natural multi-digit order,
        equal-natural-key case variants and LEGACY {module} templates remain valid; the mapped
        {module} token keeps its specific code even when it would also sort out of order."""
        import copy

        from netbox_hedgehog.models.topology_planning.generation import (
            SYNC_CHANGED,
            SYNC_IN_SYNC,
            SYNC_SNAPSHOT_INCOMPLETE,
            classify_snapshot_sync,
        )
        from netbox_hedgehog.services.nic_cage_layout import SNAPSHOT_KEY, extension_errors
        from netbox_hedgehog.utils.snapshot_builder import build_plan_snapshot

        mapped = self._c39_mapped_type('c39lt', 'nic-card', ['p0', 'p1'], self.C39_CARD_MAP)
        legacy = ModuleType.objects.create(manufacturer=_manufacturer(), model='srv29-c39lt-legacy-nic')
        for name in ('p0', 'p1'):
            InterfaceTemplate.objects.create(module_type=legacy, name=name, type=T400)
        self._c39_cards_fixture('c39lt', [('a-card', mapped, 0), ('b-slot', legacy, 0)])
        current = self._c39_sync_guarded(lambda: build_plan_snapshot(self.plan))
        self.assertEqual(extension_errors(current[SNAPSHOT_KEY], base_snapshot=current), [])
        self.assertEqual(classify_snapshot_sync(copy.deepcopy(current), copy.deepcopy(current)), SYNC_IN_SYNC)
        position = {n['nic_id']: i for i, n in enumerate(current[SNAPSHOT_KEY]['nics'])}
        self.assertEqual(sorted(position), ['a-card', 'b-slot'])
        for nic_id, present in (('a-card', True), ('b-slot', False)):
            row = current[SNAPSHOT_KEY]['nics'][position[nic_id]]
            self.assertEqual(row['layout_present'], present, nic_id)
            self.assertEqual([(t['logical_index'], t['name']) for t in row['interface_templates']],
                             [(0, 'p0'), (1, 'p1')], nic_id)

        def rename(nic_id, *new):
            def fn(s):
                rows = s[SNAPSHOT_KEY]['nics'][position[nic_id]]['interface_templates']
                for row, name in zip(rows, new):
                    row['name'] = name
            return fn

        cases = [
            ('legacy_module_token_allowed', rename('b-slot', '{module}-p0', '{module}-p1'), []),
            ('legacy_natural_multi_digit', rename('b-slot', 'p2', 'p10'), []),
            ('legacy_equal_natural_key_case_variant', rename('b-slot', 'p0', 'P0'), []),
            ('legacy_lexical_order', rename('b-slot', 'p10', 'p2'), ['template_order']),
            ('legacy_swapped_names', rename('b-slot', 'p1', 'p0'), ['template_order']),
            ('mapped_equal_natural_key_case_variant', rename('a-card', 'P0', 'p0'), []),
            ('mapped_swapped_names', rename('a-card', 'p1', 'p0'), ['template_order']),
            ('mapped_module_token_in_order', rename('a-card', 'p0', '{module}-p1'), ['layout_template_module_token']),
            ('mapped_module_token_out_of_order', rename('a-card', '{module}-p0', 'p1'),
             ['layout_template_module_token']),
        ]
        for label, mutate, codes in cases:
            with self.subTest(label):
                bad = copy.deepcopy(current)
                mutate(bad)
                self._c39_rehash(bad[SNAPSHOT_KEY])
                self.assertEqual(extension_errors(bad[SNAPSHOT_KEY], base_snapshot=bad), codes)
                if codes:
                    self.assertEqual(classify_snapshot_sync(copy.deepcopy(bad), copy.deepcopy(bad)),
                                     SYNC_SNAPSHOT_INCOMPLETE)
                    self.assertEqual(classify_snapshot_sync(copy.deepcopy(current), copy.deepcopy(bad)),
                                     SYNC_SNAPSHOT_INCOMPLETE)
                else:
                    self.assertEqual(classify_snapshot_sync(copy.deepcopy(bad), copy.deepcopy(bad)), SYNC_IN_SYNC)
                    self.assertEqual(classify_snapshot_sync(copy.deepcopy(current), copy.deepcopy(bad)),
                                     SYNC_CHANGED, 'valid but different evidence is a change, not in sync')

    def test_c39_virtual_placeholder_absent_key_legacy_present_key_rejected_before_cleanup(self):
        """C04/C05/design 'virtual' control with the EXACT bundled predicate
        (transceiver_bay_policy.is_virtual_placeholder_module_type: model.strip() starts with
        'Virtual '), on a test-owned synthetic NIC type; no ordinary shared-optic fixture uses
        this path and no policy/seed/core change.

        Key ABSENT: scoped populate_bays removes the stale nested cage template as before (and
        leaves a foreign type's bay), real generation (NATIVE, null optic FKs) yields exactly one
        NIC Module per server with no nested bay/optic, and the saved snapshot has NO extension
        key. Key PRESENT: populate_bays rejects [nic_layout_virtual] with ZERO attempted SQL
        mutations BEFORE placeholder cleanup or switch bay writes (stale/foreign rows intact);
        public generate_all after the prior virtual generation rejects pre-write with the full
        prior inventory/state preserved; the live snapshot is the typed invalid marker and both
        public sync methods report dirty/incomplete without rewriting saved history."""
        import copy

        from dcim.models import ModuleBayTemplate
        from netbox_hedgehog.management.commands.populate_transceiver_bays import populate_bays
        from netbox_hedgehog.models.topology_planning.generation import SYNC_IN_SYNC, SYNC_SNAPSHOT_INCOMPLETE
        from netbox_hedgehog.services.nic_cage_layout import SNAPSHOT_KEY, has_layout
        from netbox_hedgehog.services.transceiver_bay_policy import is_virtual_placeholder_module_type
        from netbox_hedgehog.utils.snapshot_builder import build_plan_snapshot

        self._build('c39vp', 8, NATIVE)
        virtual_model = 'Virtual srv29-c39vp-nic'
        ModuleType.objects.filter(pk=self.nic_module_type.pk).update(model=virtual_model)
        self.nic_module_type.refresh_from_db()
        nic_type = self.nic_module_type
        self.assertTrue(is_virtual_placeholder_module_type(nic_type), 'actual predicate recognises fixture')
        self.assertFalse(has_layout(nic_type))
        foreign = ModuleType.objects.create(manufacturer=_manufacturer(), model='srv29-c39vp-foreign-nic')
        self.assertFalse(is_virtual_placeholder_module_type(foreign), 'ordinary model is not virtual')
        foreign_bay = ModuleBayTemplate.objects.create(module_type=foreign, name='cage-0')
        stale = ModuleBayTemplate.objects.create(module_type=nic_type, name='cage-0')

        # --- key ABSENT: unchanged placeholder behavior
        counts = populate_bays(device_types=[], module_types=[nic_type])
        self.assertEqual((counts['nic_removed'], counts['nic_added']), (1, 0))
        self.assertFalse(ModuleBayTemplate.objects.filter(pk=stale.pk).exists(), 'stale placeholder cage kept')
        self.assertTrue(ModuleBayTemplate.objects.filter(pk=foreign_bay.pk).exists(), 'foreign bay touched')
        self._calculate(leaves=4, spines=2)
        self._capture_baseline()
        self._generate(devices_total=14, generated_interfaces=40, cables_total=24)
        _, prior_ids = self._verify(servers=8, leaves=4, spines=2, links_per_pair=2, cables_total=24,
                                    devices_total=14)  # one NIC Module, NO nested bay/optic per server
        state = GenerationState.objects.get(plan=self.plan)
        self.assertNotIn(SNAPSHOT_KEY, state.snapshot)
        self.assertEqual(sorted(state.snapshot), ['connections', 'mclag_domains', 'port_zones',
                                                  'server_classes', 'switch_classes'])
        self.assertNotIn(SNAPSHOT_KEY, self._c39_sync_guarded(lambda: build_plan_snapshot(self.plan)))
        self.assertFalse(self._c39_sync_guarded(state.is_dirty))
        self.assertEqual(self._c39_sync_guarded(state.sync_display_state), SYNC_IN_SYNC)
        saved_row = list(GenerationState.objects.filter(pk=state.pk).values())

        # --- key PRESENT on the virtual placeholder: reject before cleanup/any write
        stale = ModuleBayTemplate.objects.create(module_type=nic_type, name='cage-0')
        virtual_map = {'version': 1, 'ports': [{'cage': 'cage-0', 'logical_lane': 0}],
                       'cages': {'cage-0': {'breakout_id': '1x100g'}}}
        ModuleType.objects.filter(pk=nic_type.pk).update(attribute_data={'hnp_nic_cage_map': copy.deepcopy(virtual_map)})
        nic_type = ModuleType.objects.select_related('profile').get(pk=nic_type.pk)
        self.assertTrue(has_layout(nic_type))
        self.assertTrue(is_virtual_placeholder_module_type(nic_type))
        self.assertFalse(ModuleBayTemplate.objects.filter(device_type=self.leaf_device_type).exists())

        def population():
            with self.assertRaises(ValidationError) as ctx:
                populate_bays(device_types=[self.leaf_device_type], module_types=[foreign, nic_type])
            return ' '.join(ctx.exception.messages)

        message = self._c39_sync_guarded(population)  # zero attempted mutations + full rows unchanged
        self.assertIn('[nic_layout_virtual]', message)
        self.assertIn(virtual_model, message)
        self.assertTrue(ModuleBayTemplate.objects.filter(pk=stale.pk).exists(), 'placeholder cleanup ran first')
        self.assertTrue(ModuleBayTemplate.objects.filter(pk=foreign_bay.pk).exists())
        self.assertFalse(ModuleBayTemplate.objects.filter(device_type=self.leaf_device_type).exists(),
                         'switch bays written before rejection')

        generator = DeviceGenerator(self.plan)  # constructor Site/Tag setup outside the proof
        before = self._c39_sync_rows()
        message = self._reject_without_mutation(generator)
        self.assertIn('[nic_layout_virtual]', message)
        self.assertIn(virtual_model, message)
        self.assertEqual(self._c39_sync_rows(), before, 'rejected generation changed persisted rows')
        for model in INVENTORY_MODELS:
            self.assertTrue(prior_ids[model] <= _pks(model), f'prior virtual-generation {model.__name__} lost')
        state = GenerationState.objects.get(plan=self.plan)
        self.assertEqual(state.status, GenerationStatusChoices.GENERATED)
        self.assertEqual((state.device_count, state.interface_count, state.cable_count), (14, 40, 24))

        current = self._c39_sync_guarded(lambda: build_plan_snapshot(self.plan))
        self.assertEqual(current[SNAPSHOT_KEY], {'version': 1, 'status': 'invalid', 'errors': ['nic_layout_virtual']})
        self.assertTrue(self._c39_sync_guarded(state.is_dirty))
        self.assertEqual(self._c39_sync_guarded(state.sync_display_state), SYNC_SNAPSHOT_INCOMPLETE)
        self.assertEqual(list(GenerationState.objects.filter(pk=state.pk).values()), saved_row,
                         'saved history rewritten')

    # ------------- CAGE39 SOURCE10: Review04 P2 regressions (appended; fictional rows only)

    def test_c39_t11_rehashed_duplicate_literal_template_and_bay_names_mapped_and_legacy(self):
        """Review04 P2-1 / C08 / T11: native uniqueness is (module_type, name) for both
        InterfaceTemplate and ModuleBayTemplate, so RE-HASHED evidence holding two equal EXACT
        literal names under distinct IDs inside ONE NIC record is internally invalid, for the
        mapped AND the legacy record of a live mixed capture: exact typed code, pure identical-
        invalid classify incomplete, public is_dirty / sync_display_state (live and identical
        current) under the existing mutation-denying full-row guard. Controls stay VALID (and
        differ from live -> changed): case variants P0/p0 and DATA/data, and the same cage name
        recorded under a DIFFERENT NIC owner (no global name rule)."""
        import copy

        from netbox_hedgehog.models.topology_planning.generation import (
            SYNC_CHANGED,
            SYNC_IN_SYNC,
            SYNC_SNAPSHOT_INCOMPLETE,
            classify_snapshot_sync,
        )
        from netbox_hedgehog.services.nic_cage_layout import SNAPSHOT_KEY, extension_errors
        from netbox_hedgehog.utils.snapshot_builder import build_plan_snapshot

        mapped = self._c39_mapped_type('c39dn', 'nic-card', ['p0', 'p1'], self.C39_CARD_MAP)
        legacy = ModuleType.objects.create(manufacturer=_manufacturer(), model='srv29-c39dn-legacy-nic')
        for name in ('p0', 'p1'):
            InterfaceTemplate.objects.create(module_type=legacy, name=name, type=T400)
        self._c39_cards_fixture('c39dn', [('a-card', mapped, 0), ('b-slot', legacy, 0)])
        current = self._c39_sync_guarded(lambda: build_plan_snapshot(self.plan))
        self.assertEqual(extension_errors(current[SNAPSHOT_KEY], base_snapshot=current), [])
        self.assertEqual(classify_snapshot_sync(copy.deepcopy(current), copy.deepcopy(current)), SYNC_IN_SYNC)
        position = {n['nic_id']: i for i, n in enumerate(current[SNAPSHOT_KEY]['nics'])}
        self.assertEqual(sorted(position), ['a-card', 'b-slot'])
        rows = {nic_id: current[SNAPSHOT_KEY]['nics'][i] for nic_id, i in position.items()}
        self.assertEqual((rows['a-card']['layout_present'], rows['b-slot']['layout_present']), (True, False))
        for nic_id in ('a-card', 'b-slot'):
            self.assertEqual([t['name'] for t in rows[nic_id]['interface_templates']], ['p0', 'p1'], nic_id)
        self.assertEqual(sorted(b['name'] for b in rows['a-card']['bay_templates']), ['b-slot', 'data'])
        self.assertTrue(rows['b-slot']['bay_templates'], 'legacy record needs recorded bays for this matrix')
        legacy_bay = rows['b-slot']['bay_templates'][0]['name']
        self.assertNotEqual(legacy_bay, 'data', 'fixture: cross-owner control must be a NEW name for legacy')
        fresh_id = 1000 + max(
            [t['template_id'] for r in rows.values() for t in r['interface_templates']]
            + [b['template_id'] for r in rows.values() for b in r['bay_templates']])

        def nic(s, nic_id):
            return s[SNAPSHOT_KEY]['nics'][position[nic_id]]

        def rename(nic_id, *new):
            def fn(s):
                for row, name in zip(nic(s, nic_id)['interface_templates'], new):
                    row['name'] = name
            return fn

        def add_bay(nic_id, name):
            def fn(s):
                bays = nic(s, nic_id)['bay_templates']
                bays.append({'template_id': fresh_id, 'name': name, 'position': bays[0]['position']})
            return fn

        invalid = [
            ('mapped_template_p1_renamed_p0', rename('a-card', 'p0', 'p0'), 'template_duplicate_name'),
            ('legacy_template_p1_renamed_p0', rename('b-slot', 'p0', 'p0'), 'template_duplicate_name'),
            ('mapped_bay_second_data_distinct_id', add_bay('a-card', 'data'), 'bay_duplicate_name'),
            ('legacy_bay_second_same_name_distinct_id', add_bay('b-slot', legacy_bay), 'bay_duplicate_name'),
        ]
        valid = [
            ('mapped_template_case_variant', rename('a-card', 'P0', 'p0')),
            ('legacy_template_case_variant', rename('b-slot', 'p0', 'P0')),
            ('mapped_bay_case_variant', add_bay('a-card', 'DATA')),
            ('same_cage_name_other_nic_owner', add_bay('b-slot', 'data')),
        ]
        labels = [label for label, *_ in invalid + valid]
        self.assertEqual(len(set(labels)), len(labels), 'duplicate case label')
        for label, mutate, code in invalid:
            with self.subTest(label):
                bad = copy.deepcopy(current)
                mutate(bad)
                self._c39_rehash(bad[SNAPSHOT_KEY])
                self.assertEqual(extension_errors(bad[SNAPSHOT_KEY], base_snapshot=bad), [code], label)
                self.assertEqual(classify_snapshot_sync(copy.deepcopy(bad), copy.deepcopy(bad)),
                                 SYNC_SNAPSHOT_INCOMPLETE, f'{label}: pure identical-invalid')
                probe = GenerationState(plan=self.plan, device_count=0, interface_count=0, cable_count=0,
                                        snapshot=copy.deepcopy(bad))  # in-memory saved evidence, never saved
                self.assertTrue(self._c39_sync_guarded(probe.is_dirty), f'{label}: saved-invalid is_dirty')
                self.assertEqual(self._c39_sync_guarded(probe.sync_display_state), SYNC_SNAPSHOT_INCOMPLETE,
                                 f'{label}: saved-invalid vs live current')
                self.assertEqual(
                    self._c39_sync_guarded(lambda: probe.sync_display_state(current=copy.deepcopy(bad))),
                    SYNC_SNAPSHOT_INCOMPLETE, f'{label}: public identical-invalid current')
        for label, mutate in valid:
            with self.subTest(label):
                good = copy.deepcopy(current)
                mutate(good)
                self._c39_rehash(good[SNAPSHOT_KEY])
                self.assertEqual(extension_errors(good[SNAPSHOT_KEY], base_snapshot=good), [], label)
                self.assertEqual(classify_snapshot_sync(copy.deepcopy(good), copy.deepcopy(good)), SYNC_IN_SYNC)
                self.assertEqual(classify_snapshot_sync(copy.deepcopy(current), copy.deepcopy(good)),
                                 SYNC_CHANGED, f'{label}: valid but different evidence is a change')
                probe = GenerationState(plan=self.plan, device_count=0, interface_count=0, cable_count=0,
                                        snapshot=copy.deepcopy(good))
                self.assertTrue(self._c39_sync_guarded(probe.is_dirty), label)
                self.assertEqual(self._c39_sync_guarded(probe.sync_display_state), SYNC_CHANGED, label)

    def test_c39_t09_v1_mapped_reference_malformed_template_shapes_rejected_both_modes(self):
        """Review04 P2-2 / C02 / T09 extension of the public V1 mapped-reference matrix: the V1
        validator does not check reference interface_templates shapes, so a non-list container,
        a non-mapping item, or a non-string / empty / unhashable name or type must yield the
        actionable typed mapped_catalog_reference_conflict (never AttributeError/TypeError)
        through real apply_case in BOTH require and ensure mode, with every catalog/plan/
        generation row preserved (existing full-row helper; no zero-SQL claim)."""
        import copy

        from netbox_hedgehog.test_cases.ingest import apply_case

        fx = self._c39_ingest_fixture('c39ms')
        apply_case(self._c39_v1_case('srv29_c39ms_control', fx), reference_mode='require')  # fixture valid
        good = {'name': 'p0', 'type': T400}
        variants = [
            ('container_string', 'p0'),
            ('container_mapping', dict(good)),
            ('container_int', 7),
            ('item_string', ['p0']),
            ('item_list', [['p0', T400]]),
            ('item_null', [None]),
            ('valid_then_string_item', [dict(good), 'p1']),
            ('type_list', [{'name': 'p0', 'type': []}]),
            ('type_mapping', [{'name': 'p0', 'type': {'x': 1}}]),
            ('type_int', [{'name': 'p0', 'type': 7}]),
            ('type_empty', [{'name': 'p0', 'type': ''}]),
            ('name_list', [{'name': ['p0'], 'type': T400}]),
            ('name_mapping', [{'name': {'p0': 1}, 'type': T400}]),
            ('name_int', [{'name': 0, 'type': T400}]),
            ('name_empty', [{'name': '', 'type': T400}]),
            ('name_null', [{'name': None, 'type': T400}]),
        ]
        self.assertEqual(len({label for label, _ in variants}), len(variants), 'duplicate case label')
        for mode in ('require', 'ensure'):
            for label, templates in variants:
                with self.subTest(mode=mode, variant=label):
                    case = self._c39_v1_case(f'srv29_c39ms_{mode}_{label}', fx,
                                             {'interface_templates': copy.deepcopy(templates)})
                    self._c39_ingest_reject(case, mode, 'mapped_catalog_reference_conflict')
                    self._c39_assert_mapped_intact(fx)
                    self.assertFalse(TopologyPlan.objects.filter(name=f'srv29 plan srv29_c39ms_{mode}_{label}')
                                     .exists(), 'rejected case left a plan')
        # Positive control after the matrix: exact well-formed declarations are still consumed.
        exact = {'interface_templates': [dict(good), {'name': 'p1', 'type': T400}]}
        for mode in ('require', 'ensure'):
            with self.subTest(mode=mode, variant='exact_control'):
                catalog_before = self._c39_catalog_rows()
                plan = apply_case(self._c39_v1_case(f'srv29_c39ms_{mode}_exact', fx, copy.deepcopy(exact)),
                                  reference_mode=mode)
                self.assertEqual(self._c39_catalog_rows(), catalog_before, 'catalog rows rewritten')
                self.assertEqual(list(PlanServerNIC.objects.filter(server_class__plan=plan)
                                      .values_list('nic_id', 'module_type_id')), [(NIC_ID, fx['mapped'].pk)])
                self._c39_assert_mapped_intact(fx)

    # ------------- CAGE40 SOURCE11: Codex review02 P2 regressions (appended; fictional rows only)

    def _c40_assert_invalid_public(self, state, bad, code, label):
        """Exact typed code, pure identical-invalid classify incomplete, and public reads on the
        ACTUAL generated row with in-memory saved evidence (never saved), all mutation-denied
        with full-row preservation. Honest category: is_dirty / live sync_display_state compare
        saved-INVALID vs the VALID live current (NOT an equal-invalid proof); the identical-
        invalid public proof is sync_display_state(current=identical bad)."""
        import copy

        from netbox_hedgehog.models.topology_planning.generation import (
            SYNC_SNAPSHOT_INCOMPLETE,
            classify_snapshot_sync,
        )
        from netbox_hedgehog.services.nic_cage_layout import SNAPSHOT_KEY, extension_errors

        self.assertEqual(extension_errors(bad[SNAPSHOT_KEY], base_snapshot=bad), [code], label)
        self.assertEqual(classify_snapshot_sync(copy.deepcopy(bad), copy.deepcopy(bad)),
                         SYNC_SNAPSHOT_INCOMPLETE, f'{label}: pure identical-invalid')
        probe = GenerationState.objects.get(pk=state.pk)
        probe.snapshot = copy.deepcopy(bad)
        self.assertTrue(self._c39_sync_guarded(probe.is_dirty), f'{label}: saved-invalid is_dirty')
        self.assertEqual(self._c39_sync_guarded(probe.sync_display_state), SYNC_SNAPSHOT_INCOMPLETE,
                         f'{label}: saved-invalid vs valid live current')
        self.assertEqual(
            self._c39_sync_guarded(lambda: probe.sync_display_state(current=copy.deepcopy(bad))),
            SYNC_SNAPSHOT_INCOMPLETE, f'{label}: public identical-invalid current')

    def _c40_assert_valid_control(self, state, valid, good, label):
        import copy

        from netbox_hedgehog.models.topology_planning.generation import (
            SYNC_CHANGED,
            SYNC_IN_SYNC,
            classify_snapshot_sync,
        )
        from netbox_hedgehog.services.nic_cage_layout import SNAPSHOT_KEY, extension_errors

        self.assertEqual(extension_errors(good[SNAPSHOT_KEY], base_snapshot=good), [], label)
        self.assertEqual(classify_snapshot_sync(copy.deepcopy(good), copy.deepcopy(good)), SYNC_IN_SYNC, label)
        self.assertEqual(classify_snapshot_sync(copy.deepcopy(valid), copy.deepcopy(good)), SYNC_CHANGED,
                         f'{label}: valid but different evidence is a change')
        probe = GenerationState.objects.get(pk=state.pk)
        probe.snapshot = copy.deepcopy(good)
        self.assertTrue(self._c39_sync_guarded(probe.is_dirty), label)
        self.assertEqual(self._c39_sync_guarded(probe.sync_display_state), SYNC_CHANGED, label)

    def test_c40_p2a_base_connection_speed_and_count_cross_checked(self):
        """Codex review02 P2a / C08 / T11 on an ACTUAL generated mapped plan/state: the base
        connection record and the extension record of the same identity must carry typed
        positive-int speed and ports_per_connection that agree EXACTLY (no bool/float/str
        coercion). Base-only contradictions need NO digest change (base is not hashed) and are
        base_connection_fields; an extension-side change RE-HASHED is the same code; typed
        extension omissions keep their existing specific codes. base target_zone_id (display
        string) vs extension target_zone_id (integer PK) is never compared: a rehashed
        extension zone change stays valid. These record corruptions are not producible through
        live DB reads (both sections read the same row), so no live equal-invalid claim."""
        import copy

        from netbox_hedgehog.models.topology_planning.generation import SYNC_IN_SYNC
        from netbox_hedgehog.services.nic_cage_layout import SNAPSHOT_KEY, extension_errors

        fixture = self._c39_fixture('c40a')
        self._c39_generate()
        state = GenerationState.objects.get(plan=self.plan)
        saved_row = list(GenerationState.objects.filter(pk=state.pk).values())
        valid = copy.deepcopy(state.snapshot)
        self.assertEqual(extension_errors(valid[SNAPSHOT_KEY], base_snapshot=valid), [])
        self.assertFalse(self._c39_sync_guarded(state.is_dirty))
        self.assertEqual(self._c39_sync_guarded(state.sync_display_state), SYNC_IN_SYNC)
        conn_id = fixture['conn'].connection_id
        base_rows = [r for r in valid['connections'] if r['connection_id'] == conn_id]
        self.assertEqual(len(base_rows), 1)
        ext_row = valid[SNAPSHOT_KEY]['nics'][0]['connections'][0]
        self.assertEqual(ext_row['connection_id'], conn_id)
        self.assertEqual((base_rows[0]['speed'], base_rows[0]['ports_per_connection']), (400, 2))
        self.assertEqual((ext_row['speed'], ext_row['ports_per_connection']), (400, 2))
        self.assertIsInstance(base_rows[0]['target_zone_id'], str)
        self.assertEqual(ext_row['target_zone_id'], fixture['zone'].pk)
        missing = object()

        def base(field, value):
            def fn(s):
                (row,) = [r for r in s['connections'] if r['connection_id'] == conn_id]
                if value is missing:
                    row.pop(field)
                else:
                    row[field] = value
            return fn

        def ext(field, value):
            def fn(s):
                row = s[SNAPSHOT_KEY]['nics'][0]['connections'][0]
                if value is missing:
                    row.pop(field)
                else:
                    row[field] = value
            return fn

        # (label, mutation, code, rehash extension digests)
        cases = [
            ('base_speed_800_vs_ext_and_mode_400', base('speed', 800), 'base_connection_fields', False),
            ('base_count_1_vs_ext_2', base('ports_per_connection', 1), 'base_connection_fields', False),
            ('base_speed_float_equal', base('speed', 400.0), 'base_connection_fields', False),
            ('base_count_float_equal', base('ports_per_connection', 2.0), 'base_connection_fields', False),
            ('base_speed_string', base('speed', '400'), 'base_connection_fields', False),
            ('base_speed_bool', base('speed', True), 'base_connection_fields', False),
            ('base_speed_null', base('speed', None), 'base_connection_fields', False),
            ('base_speed_missing', base('speed', missing), 'base_connection_fields', False),
            ('base_count_zero', base('ports_per_connection', 0), 'base_connection_fields', False),
            ('ext_count_1_rehashed_vs_base_2', ext('ports_per_connection', 1), 'base_connection_fields', True),
            ('ext_speed_bool_rehashed', ext('speed', True), 'connection_fields', True),
            ('ext_count_missing_rehashed', ext('ports_per_connection', missing), 'connection_record', True),
        ]
        self.assertEqual(len({c[0] for c in cases}), len(cases), 'duplicate case label')
        for label, mutate, code, rehash in cases:
            with self.subTest(label):
                bad = copy.deepcopy(valid)
                mutate(bad)
                if rehash:
                    self._c39_rehash(bad[SNAPSHOT_KEY])
                else:
                    self.assertEqual(bad[SNAPSHOT_KEY], valid[SNAPSHOT_KEY], f'{label}: extension/digests untouched')
                self._c40_assert_invalid_public(state, bad, code, label)
        # Unlike target_zone representations are never compared: rehashed ext PK change is valid.
        good = copy.deepcopy(valid)
        ext('target_zone_id', ext_row['target_zone_id'] + 1000)(good)
        self._c39_rehash(good[SNAPSHOT_KEY])
        self.assertEqual(good['connections'], valid['connections'])
        self._c40_assert_valid_control(state, valid, good, 'ext_zone_pk_vs_base_label_not_compared')
        self.assertFalse(self._c39_sync_guarded(state.is_dirty))
        self.assertEqual(list(GenerationState.objects.filter(pk=state.pk).values()), saved_row,
                         'saved history rewritten')

    def test_c40_p2b_legacy_record_range_and_collision_in_mixed_extension(self):
        """Codex review02 P2b / C08 / T11 on an ACTUAL generated mixed plan: mapped 'a-card'
        (declared cages data/b-slot, only data used) + LEGACY 'b-slot' (key absent, p0/p1). The
        layout-independent range and per-NIC collision checks apply to the LEGACY record too
        (active or inactive): re-hashed out-of-range logical indices -> connection_range,
        overlapping distinct connection ranges -> connection_index_collision, with pure
        identical-invalid and public read classification under the mutation-denying full-row
        guard. Valid controls: distinct non-overlapping legacy ports, the same index 0 / names
        p0,p1 under DIFFERENT NIC owners, a legacy case variant, the mapped partial cage. Live
        DB journeys (genuine current == saved invalid marker): legacy out-of-range ->
        nic_layout_index_range, legacy overlap -> nic_layout_port_collision, each also rejected
        by public generate_all with zero attempted mutations and prior inventory intact."""
        import copy

        from netbox_hedgehog.models.topology_planning.generation import (
            SYNC_IN_SYNC,
            SYNC_SNAPSHOT_INCOMPLETE,
            classify_snapshot_sync,
        )
        from netbox_hedgehog.services.nic_cage_layout import SNAPSHOT_KEY, extension_errors, has_layout
        from netbox_hedgehog.utils.snapshot_builder import build_plan_snapshot

        mapped = self._c39_mapped_type('c40b', 'nic-card', ['p0', 'p1'], self.C39_CARD_MAP)
        legacy = ModuleType.objects.create(manufacturer=_manufacturer(), model='srv29-c40b-legacy-nic')
        for name in ('p0', 'p1'):
            InterfaceTemplate.objects.create(module_type=legacy, name=name, type=T400)
        self.assertFalse(has_layout(legacy))
        optic = self._c39_cards_fixture('c40b', [('a-card', mapped, 0), ('b-slot', legacy, 0)])
        self._capture_baseline()
        self._generate(devices_total=10, generated_interfaces=40, cables_total=24)
        prior = {model: _pks(model) - self.baseline[model] for model in INVENTORY_MODELS}
        state = GenerationState.objects.get(plan=self.plan)
        saved_row = list(GenerationState.objects.filter(pk=state.pk).values())
        valid = copy.deepcopy(state.snapshot)
        self.assertEqual(extension_errors(valid[SNAPSHOT_KEY], base_snapshot=valid), [])
        self.assertFalse(self._c39_sync_guarded(state.is_dirty))
        self.assertEqual(self._c39_sync_guarded(state.sync_display_state), SYNC_IN_SYNC)
        position = {n['nic_id']: i for i, n in enumerate(valid[SNAPSHOT_KEY]['nics'])}
        self.assertEqual(sorted(position), ['a-card', 'b-slot'])
        rows = {k: valid[SNAPSHOT_KEY]['nics'][i] for k, i in position.items()}
        self.assertEqual((rows['a-card']['layout_present'], rows['b-slot']['layout_present']), (True, False))
        for nic_id in ('a-card', 'b-slot'):  # same names/index 0 under DIFFERENT owners: valid
            self.assertEqual([t['name'] for t in rows[nic_id]['interface_templates']], ['p0', 'p1'], nic_id)
            self.assertEqual([(c['port_index'], c['ports_per_connection']) for c in rows[nic_id]['connections']],
                             [(0, 1)], nic_id)
        self.assertEqual(sorted(p['cage'] for p in rows['a-card']['layout']['ports']), ['b-slot', 'data'],
                         'mapped partial cage occupancy: b-slot declared, unused')
        legacy_conn_id = rows['b-slot']['connections'][0]['connection_id']
        new_id = 'srv29-c40b-conn-z'

        def lnic(s):
            return s[SNAPSHOT_KEY]['nics'][position['b-slot']]

        def base_row(s, cid):
            (row,) = [r for r in s['connections'] if r['connection_id'] == cid]
            return row

        def set_legacy(**fields):
            """Change the legacy connection; shared base fields kept consistent (single defect)."""
            def fn(s):
                lnic(s)['connections'][0].update(fields)
                for key in ('speed', 'ports_per_connection'):
                    if key in fields:
                        base_row(s, legacy_conn_id)[key] = fields[key]
            return fn

        def add_legacy_conn(port_index, first_count=None):
            """Second distinct legacy connection (manifest + base linkage kept complete)."""
            def fn(s):
                n = lnic(s)
                first = n['connections'][0]
                if first_count is not None:
                    first['ports_per_connection'] = first_count
                    base_row(s, legacy_conn_id)['ports_per_connection'] = first_count
                extra = dict(first, connection_id=new_id, port_index=port_index, ports_per_connection=1)
                n['connections'] = sorted(n['connections'] + [extra], key=lambda r: r['connection_id'])
                s[SNAPSHOT_KEY]['expected_connection_keys'] = sorted(
                    s[SNAPSHOT_KEY]['expected_connection_keys'] + [[extra['server_class_id'], new_id]])
                s['connections'].append(dict(base_row(s, legacy_conn_id), connection_id=new_id,
                                             ports_per_connection=1))
            return fn

        def rename_legacy(*names):
            def fn(s):
                for row, name in zip(lnic(s)['interface_templates'], names):
                    row['name'] = name
            return fn

        invalid = [
            ('legacy_port_index_beyond_templates', set_legacy(port_index=2), 'connection_range'),
            ('legacy_count_overflows_templates', set_legacy(port_index=1, ports_per_connection=2),
             'connection_range'),
            ('legacy_overlap_same_start', add_legacy_conn(0), 'connection_index_collision'),
            ('legacy_overlap_partial_range', add_legacy_conn(1, first_count=2), 'connection_index_collision'),
        ]
        for label, mutate, code in invalid:
            with self.subTest(label):
                bad = copy.deepcopy(valid)
                mutate(bad)
                self._c39_rehash(bad[SNAPSHOT_KEY])
                self._c40_assert_invalid_public(state, bad, code, label)
                # Inactive classes are NOT exempt (same as the existing mapped rule).
                self.assertEqual(extension_errors(bad[SNAPSHOT_KEY], active_classes=set()), [code],
                                 f'{label}: inactive view')
        with self.subTest('legacy_base_count_bool_coercion'):
            bad = copy.deepcopy(valid)
            base_row(bad, legacy_conn_id)['ports_per_connection'] = True  # True == 1 must not pass
            self.assertEqual(bad[SNAPSHOT_KEY], valid[SNAPSHOT_KEY])
            self._c40_assert_invalid_public(state, bad, 'base_connection_fields', 'legacy_base_count_bool')
        for label, mutate in (('legacy_distinct_nonoverlap_ports', add_legacy_conn(1)),
                              ('legacy_case_variant_names', rename_legacy('p0', 'P0'))):
            with self.subTest(label):
                good = copy.deepcopy(valid)
                mutate(good)
                self._c39_rehash(good[SNAPSHOT_KEY])
                self._c40_assert_valid_control(state, valid, good, label)

        # --- live DB journeys: genuine current == saved invalid marker; public generate_all
        legacy_conns = PlanServerConnection.objects.filter(server_class=self.server_class,
                                                           connection_id=legacy_conn_id)
        legacy_nic = PlanServerNIC.objects.get(server_class=self.server_class, nic_id='b-slot')
        self.assertEqual(legacy_nic.module_type_id, legacy.pk)

        def live_equal_invalid(code, label):
            self._c39_public_reject_after_generation(code, prior)
            try:
                fresh = self._c39_sync_guarded(lambda: build_plan_snapshot(self.plan))
                self.assertEqual(fresh[SNAPSHOT_KEY], {'version': 1, 'status': 'invalid', 'errors': [code]}, label)
                GenerationState.objects.filter(pk=state.pk).update(snapshot=copy.deepcopy(fresh))  # fixture write
                state.refresh_from_db()
                current = self._c39_sync_guarded(lambda: build_plan_snapshot(self.plan))
                self.assertEqual(current, state.snapshot, f'{label}: fresh current must EQUAL saved first')
                self.assertTrue(self._c39_sync_guarded(state.is_dirty), f'{label}: equal-invalid is_dirty')
                self.assertEqual(self._c39_sync_guarded(state.sync_display_state), SYNC_SNAPSHOT_INCOMPLETE, label)
                self.assertEqual(classify_snapshot_sync(copy.deepcopy(current), copy.deepcopy(current)),
                                 SYNC_SNAPSHOT_INCOMPLETE, label)
            finally:
                GenerationState.objects.filter(pk=state.pk).update(snapshot=copy.deepcopy(valid))  # restore
                state.refresh_from_db()

        with self.subTest('live_legacy_out_of_range'):
            legacy_conns.update(port_index=2)
            try:
                live_equal_invalid('nic_layout_index_range', 'live_legacy_out_of_range')
            finally:
                legacy_conns.update(port_index=0)
        with self.subTest('live_legacy_overlap'):
            from netbox_hedgehog.services.port_allocator import PortAllocatorV2

            # Fixture-only genuine spare SERVER capacity: the overlap adds a 3rd connection per
            # server/leaf, but BREAKOUT leaf SERVER zone '1' (2x400g) has only 2 logical ports, so
            # the earlier valid capacity guard would fire first. Temporarily add a test-owned
            # native 800G parent E1/4 on this fictional leaf DeviceType and widen the SERVER zone
            # to '1,4' (capacity 4); UPLINK 2-3, quantities, breakout and speeds unchanged.
            server_zone = SwitchPortZone.objects.get(pk=self.c39['zone'].pk)
            zone_rows = SwitchPortZone.objects.filter(pk=server_zone.pk)
            zone_before = list(zone_rows.values())
            leaf_templates = InterfaceTemplate.objects.filter(device_type=self.leaf_device_type)
            leaf_templates_before = list(leaf_templates.order_by('pk').values())
            uplink_zones = SwitchPortZone.objects.filter(switch_class=self.leaf_class,
                                                         zone_type=PortZoneTypeChoices.UPLINK)
            uplink_before = list(uplink_zones.order_by('pk').values())
            self.assertEqual([(z['port_spec'], z['zone_name']) for z in uplink_before],
                             [('2-3', 'srv29-c40b-uplink')])
            self.assertEqual(server_zone.port_spec, '1')
            self.assertEqual(server_zone.breakout_option.breakout_id, '2x400g')
            self.assertEqual(PortAllocatorV2().capacity_for_zone(server_zone), 2)
            self.assertEqual(sorted(leaf_templates.values_list('name', 'type')),
                             [('E1/1', T800), ('E1/2', T800), ('E1/3', T800)])
            self.assertFalse(leaf_templates.filter(name='E1/4').exists(), 'E1/4 must not preexist')
            spare = extra = None
            try:
                spare = InterfaceTemplate(device_type=self.leaf_device_type, name='E1/4', type=T800)
                spare.full_clean()
                spare.save()
                server_zone.port_spec = '1,4'
                server_zone.full_clean()
                server_zone.save()
                server_zone.refresh_from_db()
                self.assertEqual(server_zone.port_spec, '1,4')
                self.assertEqual(PortAllocatorV2().capacity_for_zone(server_zone), 4)
                self.assertEqual(list(uplink_zones.order_by('pk').values()), uplink_before, 'UPLINK changed')
                extra = PlanServerConnection.objects.create(
                    server_class=self.server_class, connection_id=new_id, nic=legacy_nic, port_index=0,
                    ports_per_connection=1, hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
                    distribution=ConnectionDistributionChoices.SAME_SWITCH, target_zone=self.c39['zone'],
                    speed=400, transceiver_module_type=optic,
                )
                live_equal_invalid('nic_layout_port_collision', 'live_legacy_overlap')
            finally:
                if extra is not None:
                    PlanServerConnection.objects.filter(pk=extra.pk).delete()
                zone_rows.update(port_spec=zone_before[0]['port_spec'],
                                 last_updated=zone_before[0]['last_updated'])
                if spare is not None and spare.pk is not None:
                    InterfaceTemplate.objects.filter(pk=spare.pk).delete()
            self.assertFalse(PlanServerConnection.objects.filter(connection_id=new_id).exists())
            self.assertEqual(list(zone_rows.values()), zone_before, 'SERVER zone not restored exactly')
            self.assertEqual(list(leaf_templates.order_by('pk').values()), leaf_templates_before,
                             'leaf catalog not restored to three parents')
        self.assertFalse(self._c39_sync_guarded(state.is_dirty), 'restored intent and saved history')
        self.assertEqual(self._c39_sync_guarded(state.sync_display_state), SYNC_IN_SYNC)
        self.assertEqual(list(GenerationState.objects.filter(pk=state.pk).values()), saved_row,
                         'saved history not restored exactly')
