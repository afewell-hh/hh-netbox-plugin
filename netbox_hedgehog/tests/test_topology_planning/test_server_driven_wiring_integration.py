"""
SERVER29: server demand -> leaf/spine sizing -> physical wiring integration tests.

Scope: synthetic server classes (quantity is the only sizing input; every leaf and
spine ``override_quantity`` stays NULL and ``calculated_quantity`` starts at 0) are
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
feasible count. Current source appears to compute ceil(20/8)=3, so case E is an
expected controlled RED against the current product until the rule is implemented.

Not covered: real hardware, optics/transceivers/BOM, UI/jobs, whole workbook flows,
YAML export or all fabric families. All device/module models are synthetic
``srv29-*``. Nothing is mocked; no private generator helper is called.
"""

from collections import Counter

from django.test import TestCase

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
        # Expected controlled RED on current source if it still chooses ceil(20/8)=3.
        self._build('e', 9, NATIVE)
        self._run(servers=9, leaves=5, spines=4, links_per_pair=1, cables_total=29, devices_total=18,
                  generated_interfaces=49)
