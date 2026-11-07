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
