"""
ACCEPT27: spine sizing -> physical leaf/spine wiring integration tests.

Scope: for an EXPLICIT leaf population (leaf ``override_quantity`` fixed as input,
spine ``override_quantity`` left NULL) these tests call the real public
``calculate_spine_quantity``, assert an independently stated literal spine count,
persist it as ``calculated_quantity`` and then run the real
``DeviceGenerator.generate_all``. They verify sizing-to-physical-wiring: the
persisted generated devices, complete interface inventory, cables, endpoints,
physical parent cages and breakout lanes.

Discovery is by baseline difference (every Device/Interface/Cable PK created by
generation), not by ownership filters; ownership metadata is then asserted on all
discovered rows. The expected endpoint multiset is declared from fixture slot tables
and simple sequential fixture arithmetic, never from observed output or generator
internals.

Not covered: server demand / leaf sizing, transceivers/optics/module BOM, jobs/UI,
complete workbook flows, YAML export, release or any hardware equivalence. All
device models are synthetic ``accept27-*`` with synthetic capabilities. Nothing is
mocked; no private generator helper is called.
"""

from collections import Counter

from django.test import TestCase

from dcim.choices import InterfaceTypeChoices
from dcim.models import Cable, Device, DeviceType, Interface, InterfaceTemplate, Manufacturer

from netbox_hedgehog.choices import (
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
    PlanSwitchClass,
    SwitchPortZone,
    TopologyPlan,
)
from netbox_hedgehog.services.device_generator import DeviceGenerator
from netbox_hedgehog.utils.topology_calculations import calculate_spine_quantity

FABRIC = 'accept27-fabric'
TAG = 'hedgehog-generated'
T100 = InterfaceTypeChoices.TYPE_100GE_QSFP28
T400 = InterfaceTypeChoices.TYPE_400GE_QSFP_DD
T800 = InterfaceTypeChoices.TYPE_800GE_QSFP_DD

# Pinned plan-scoped naming: '{class}-{index:02d}' -> e.g. 'accept27-a-leaf-x-01'.
NAME_PATTERN = '{class}-{index:02d}'

BREAKOUTS = {
    # breakout_id: (from_speed, logical_ports, logical_speed)
    '1x100g': (100, 1, 100),
    '1x400g': (400, 1, 400),
    '1x800g': (800, 1, 800),
    '2x400g': (800, 2, 400),
}

# Declared logical-slot tables, in sequential allocation order: (name, parent, lane).
NATIVE_LEAF_4 = [(f'E1/{p}', p, None) for p in (1, 2, 3, 4)]
NATIVE_SPINE_8 = [(f'E1/{p}', p, None) for p in (1, 2, 3, 4, 5, 6, 7, 8)]
BREAKOUT_LEAF_2X2 = [('E1/1/1', 1, 1), ('E1/1/2', 1, 2), ('E1/2/1', 2, 1), ('E1/2/2', 2, 2)]
BREAKOUT_SPINE_4X2 = [(f'E1/{p}/{lane}', p, lane) for p in (1, 2, 3, 4) for lane in (1, 2)]


def _breakout(breakout_id):
    from_speed, logical_ports, logical_speed = BREAKOUTS[breakout_id]
    option, _ = BreakoutOption.objects.get_or_create(
        breakout_id=breakout_id,
        defaults={
            'from_speed': from_speed,
            'logical_ports': logical_ports,
            'logical_speed': logical_speed,
        },
    )
    # A pre-existing row with different semantics must fail, not silently change the case.
    assert (option.from_speed, option.logical_ports, option.logical_speed) == (
        from_speed, logical_ports, logical_speed,
    ), f'BreakoutOption {breakout_id} inconsistent: {option.from_speed}/{option.logical_ports}/{option.logical_speed}'
    return option


def _device_type_ext(model, ports, native_speed, native_type, supported_breakouts, roles):
    manufacturer, _ = Manufacturer.objects.get_or_create(
        name='accept27-synthetic', defaults={'slug': 'accept27-synthetic'},
    )
    device_type = DeviceType.objects.create(
        manufacturer=manufacturer, model=model, slug=model, u_height=1,
    )
    for port in ports:
        InterfaceTemplate.objects.create(device_type=device_type, name=f'E1/{port}', type=native_type)
    return DeviceTypeExtension.objects.create(
        device_type=device_type,
        mclag_capable=False,
        hedgehog_roles=roles,
        supported_breakouts=supported_breakouts,
        native_speed=native_speed,
    )


def _switch_class(plan, class_id, role, ext, override_quantity):
    return PlanSwitchClass.objects.create(
        plan=plan,
        switch_class_id=class_id,
        fabric_name=FABRIC,
        fabric_class=FabricClassChoices.MANAGED,
        hedgehog_role=role,
        topology_mode=TopologyModeChoices.SPINE_LEAF,
        device_type_extension=ext,
        override_quantity=override_quantity,
        calculated_quantity=0,
    )


def _zone(switch_class, name, zone_type, port_spec, breakout):
    return SwitchPortZone.objects.create(
        switch_class=switch_class,
        zone_name=name,
        zone_type=zone_type,
        port_spec=port_spec,
        breakout_option=breakout,
        allocation_strategy='sequential',
        priority=100,
    )


def _ports(first, last):
    return list(range(first, last + 1))


def _pks(model):
    return set(model.objects.values_list('pk', flat=True))


class SpineSizingWiringIntegrationTestCase(TestCase):
    """Real calculate_spine_quantity -> real DeviceGenerator.generate_all."""

    def _build(self, *, case, leaves_total, leaf_model, leaf_ports, leaf_native, leaf_type,
               leaf_breakout, leaf_supported, leaf_slots, spine_model, spine_ports,
               spine_native, spine_type, spine_breakout, spine_supported, spine_slots,
               link_type):
        self.case = case
        self.plan = TopologyPlan.objects.create(name=f'accept27-plan-{case}', customer_name='accept27')
        for category in (DeviceCategoryChoices.LEAF, DeviceCategoryChoices.SPINE):
            NamingTemplate.objects.create(plan=self.plan, device_category=category, pattern=NAME_PATTERN)
        leaf_ext = _device_type_ext(
            leaf_model, leaf_ports, leaf_native, leaf_type, leaf_supported, ['server-leaf'],
        )
        spine_ext = _device_type_ext(
            spine_model, spine_ports, spine_native, spine_type, spine_supported, ['spine'],
        )
        self.leaf_zone_name = f'accept27-{case}-uplink'
        self.spine_zone_name = f'accept27-{case}-fabric'
        self.leaf_classes = []
        for suffix in ('x', 'y'):
            leaf_class = _switch_class(
                self.plan, f'accept27-{case}-leaf-{suffix}', HedgehogRoleChoices.SERVER_LEAF,
                leaf_ext, leaves_total // 2,
            )
            _zone(leaf_class, self.leaf_zone_name, PortZoneTypeChoices.UPLINK,
                  f'{leaf_ports[0]}-{leaf_ports[-1]}', _breakout(leaf_breakout))
            self.leaf_classes.append(leaf_class)
        self.spine_class = _switch_class(
            self.plan, f'accept27-{case}-spine', HedgehogRoleChoices.SPINE, spine_ext, None,
        )
        _zone(self.spine_class, self.spine_zone_name, PortZoneTypeChoices.FABRIC,
              f'{spine_ports[0]}-{spine_ports[-1]}', _breakout(spine_breakout))

        self.leaves_total = leaves_total
        self.leaf_device_type = leaf_ext.device_type
        self.spine_device_type = spine_ext.device_type
        self.leaf_parents, self.spine_parents = leaf_ports, spine_ports
        self.leaf_native_type, self.spine_native_type = leaf_type, spine_type
        self.leaf_slots, self.spine_slots = leaf_slots, spine_slots
        self.link_type = link_type

    # ----------------------------------------------------------- expectations

    def _expected_names(self, spines):
        per_class = self.leaves_total // 2
        leaves = sorted(
            f'accept27-{self.case}-leaf-{suffix}-{i:02d}'
            for suffix in ('x', 'y') for i in range(1, per_class + 1)
        )
        spine_names = [f'accept27-{self.case}-spine-{j:02d}' for j in range(1, spines + 1)]
        return leaves, spine_names

    def _expected_edges(self, spines, links_per_pair):
        """Fixture arithmetic: sorted leaf i, sorted spine j, k links per pair.

        Leaf i uses its declared slots [j*k, (j+1)*k) toward spine j; spine j hands
        out its declared slots sequentially per leaf, so leaf i gets [i*k, (i+1)*k).
        """
        leaves, spine_names = self._expected_names(spines)
        k = links_per_pair
        expected = Counter()
        for i, leaf in enumerate(leaves):
            for j, spine in enumerate(spine_names):
                for n in range(k):
                    leaf_slot = self.leaf_slots[j * k + n][0]
                    spine_slot = self.spine_slots[i * k + n][0]
                    expected[(leaf, leaf_slot, spine, spine_slot)] += 1
        return expected

    @staticmethod
    def _expected_inventory(parents, slots):
        """Complete interface name set on one device: declared parents + logical children."""
        names = {f'E1/{p}' for p in parents}
        names |= {name for name, _, _ in slots}
        return names

    # ------------------------------------------------------------- execution

    def _size(self, expected_spines):
        self.spine_class.refresh_from_db()
        self.assertIsNone(self.spine_class.override_quantity)
        for switch_class in self.leaf_classes + [self.spine_class]:
            switch_class.refresh_from_db()
            self.assertEqual(switch_class.topology_mode, TopologyModeChoices.SPINE_LEAF)

        spines = calculate_spine_quantity(self.spine_class)
        self.assertEqual(spines, expected_spines)
        self.spine_class.calculated_quantity = spines
        self.spine_class.save(update_fields=['calculated_quantity'])
        self.spine_class.refresh_from_db()
        self.assertIsNone(self.spine_class.override_quantity)
        self.assertEqual(self.spine_class.effective_quantity, expected_spines)

    def _generate(self):
        DeviceGenerator(self.plan).generate_all()
        state = GenerationState.objects.get(plan=self.plan)
        self.assertEqual(state.status, GenerationStatusChoices.GENERATED)
        self.assertFalse(state.mismatch_report)

    def _capture_baseline(self):
        self.base_devices = _pks(Device)
        self.base_interfaces = _pks(Interface)
        self.base_cables = _pks(Cable)

    # ------------------------------------------------------------ assertions

    def _new_inventory(self):
        """Every object created since the baseline, plus anything touching new devices."""
        self.assertTrue(self.base_devices <= _pks(Device), 'baseline device removed')
        self.assertTrue(self.base_interfaces <= _pks(Interface), 'baseline interface removed')
        self.assertTrue(self.base_cables <= _pks(Cable), 'baseline cable removed')

        devices = {d.pk: d for d in Device.objects.exclude(pk__in=self.base_devices)}
        new_ifaces = list(Interface.objects.exclude(pk__in=self.base_interfaces))
        for iface in new_ifaces:
            self.assertIn(iface.device_id, devices, f'new interface {iface.pk} on foreign device')
        device_ifaces = list(Interface.objects.filter(device_id__in=devices.keys()))
        self.assertEqual({i.pk for i in device_ifaces}, {i.pk for i in new_ifaces})

        cable_ids = set(Cable.objects.exclude(pk__in=self.base_cables).values_list('pk', flat=True))
        incident = {i.cable_id for i in device_ifaces if i.cable_id is not None}
        self.assertEqual(incident - cable_ids, set(), 'baseline cable attached to generated device')
        cables = list(Cable.objects.filter(pk__in=cable_ids | incident))
        return devices, device_ifaces, cables

    def _assert_devices(self, devices, spines):
        leaves, spine_names = self._expected_names(spines)
        by_name = {d.name: d for d in devices.values()}
        self.assertEqual(len(by_name), len(devices), 'duplicate device names')
        self.assertEqual(set(by_name), set(leaves) | set(spine_names))
        plan_id = str(self.plan.pk)
        for name, device in by_name.items():
            cf = device.custom_field_data
            self.assertIn(TAG, set(device.tags.values_list('slug', flat=True)), name)
            self.assertEqual(cf.get('hedgehog_plan_id'), plan_id, name)
            self.assertEqual(cf.get('hedgehog_fabric'), FABRIC, name)
            self.assertEqual(cf.get('hedgehog_fabric_class'), FabricClassChoices.MANAGED, name)
            if name in spine_names:
                self.assertEqual(cf.get('hedgehog_class'), self.spine_class.switch_class_id)
                self.assertEqual(cf.get('hedgehog_role'), HedgehogRoleChoices.SPINE)
                self.assertEqual(device.role.slug, DeviceCategoryChoices.SPINE)
                self.assertEqual(device.device_type, self.spine_device_type)
            else:
                suffix = name.split('-leaf-')[1].split('-')[0]
                self.assertEqual(cf.get('hedgehog_class'), f'accept27-{self.case}-leaf-{suffix}')
                self.assertEqual(cf.get('hedgehog_role'), HedgehogRoleChoices.SERVER_LEAF)
                self.assertEqual(device.role.slug, DeviceCategoryChoices.LEAF)
                self.assertEqual(device.device_type, self.leaf_device_type)
        self.assertEqual(
            Counter(d.custom_field_data.get('hedgehog_class') for d in devices.values()),
            Counter({lc.switch_class_id: self.leaves_total // 2 for lc in self.leaf_classes}
                    | {self.spine_class.switch_class_id: spines}),
        )
        return by_name, set(spine_names)

    def _assert_interfaces(self, by_name, spine_names, device_ifaces):
        """Complete inventory: no undeclared interface, exact types/metadata/cabling."""
        plan_id = str(self.plan.pk)
        per_device = {}
        for iface in device_ifaces:
            per_device.setdefault(iface.device_id, {})[iface.name] = iface
        for name, device in by_name.items():
            is_spine = name in spine_names
            parents = self.spine_parents if is_spine else self.leaf_parents
            slots = self.spine_slots if is_spine else self.leaf_slots
            native_type = self.spine_native_type if is_spine else self.leaf_native_type
            zone = self.spine_zone_name if is_spine else self.leaf_zone_name
            ifaces = per_device.get(device.pk, {})
            self.assertEqual(set(ifaces), self._expected_inventory(parents, slots), name)
            slot_names = set()
            for slot_name, parent, lane in slots:
                slot_names.add(slot_name)
                iface = ifaces[slot_name]
                cf = iface.custom_field_data
                self.assertEqual(iface.type, self.link_type, f'{name} {slot_name}')
                self.assertEqual(cf.get('hedgehog_plan_id'), plan_id)
                self.assertEqual(cf.get('hedgehog_zone'), zone)
                self.assertEqual(cf.get('hedgehog_physical_port'), parent)
                self.assertEqual(cf.get('hedgehog_breakout_index'), lane)
                self.assertIsNotNone(iface.cable_id, f'{name} {slot_name} uncabled')
                self.assertIn(TAG, set(iface.tags.values_list('slug', flat=True)))
            for parent in parents:
                parent_name = f'E1/{parent}'
                if parent_name in slot_names:
                    continue  # native port: is itself the cabled logical slot
                cage = ifaces[parent_name]
                self.assertEqual(cage.type, native_type, f'{name} {parent_name}')
                self.assertIsNone(cage.cable_id, f'breakout parent {name} {parent_name} cabled')

    def _assert_cables(self, by_name, spine_names, cables, expected_edges):
        plan_id = str(self.plan.pk)
        names_by_pk = {d.pk: n for n, d in by_name.items()}
        actual = Counter()
        used_ifaces = Counter()
        for cable in cables:
            self.assertEqual(cable.custom_field_data.get('hedgehog_plan_id'), plan_id, f'cable {cable.pk}')
            self.assertIn(TAG, set(cable.tags.values_list('slug', flat=True)), f'cable {cable.pk}')
            a_terms, b_terms = list(cable.a_terminations), list(cable.b_terminations)
            self.assertEqual((len(a_terms), len(b_terms)), (1, 1), f'cable {cable.pk}')
            ends = a_terms + b_terms
            for end in ends:
                self.assertIsInstance(end, Interface)
                self.assertIn(end.device_id, names_by_pk, 'foreign endpoint')
                used_ifaces[end.pk] += 1
            names = [names_by_pk[e.device_id] for e in ends]
            self.assertEqual(sum(n in spine_names for n in names), 1, f'not leaf<->spine: {names}')
            leaf_end, spine_end = ends if names[1] in spine_names else ends[::-1]
            actual[(names_by_pk[leaf_end.device_id], leaf_end.name,
                    names_by_pk[spine_end.device_id], spine_end.name)] += 1
        self.assertEqual({k: v for k, v in used_ifaces.items() if v > 1}, {}, 'interface reused')
        self.assertEqual(actual, expected_edges)
        return actual

    def _verify(self, spines, links_per_pair, cables_total):
        devices, device_ifaces, cables = self._new_inventory()
        by_name, spine_names = self._assert_devices(devices, spines)
        self._assert_interfaces(by_name, spine_names, device_ifaces)
        expected = self._expected_edges(spines, links_per_pair)
        self.assertEqual(sum(expected.values()), cables_total)
        self.assertEqual(len(cables), cables_total)
        edges = self._assert_cables(by_name, spine_names, cables, expected)
        return edges, (set(devices), {i.pk for i in device_ifaces}, {c.pk for c in cables})

    def _run_case(self, expected_spines, links_per_pair, cables_total, regenerate=False):
        self._size(expected_spines)
        self._capture_baseline()
        self._generate()
        first, first_ids = self._verify(expected_spines, links_per_pair, cables_total)
        if not regenerate:
            return
        self._generate()
        second, second_ids = self._verify(expected_spines, links_per_pair, cables_total)
        self.assertEqual(second, first)
        for old, new, label in zip(first_ids, second_ids, ('device', 'interface', 'cable')):
            self.assertEqual(old & new, set(), f'stale {label} survived regeneration')
            model = {'device': Device, 'interface': Interface, 'cable': Cable}[label]
            self.assertFalse(model.objects.filter(pk__in=old).exists(), f'stale {label} remains')

    # ------------------------------------------------------------------ cases

    def test_a_native_100g_control(self):
        self._build(case='a', leaves_total=4,
                    leaf_model='accept27-leaf-a-100g', leaf_ports=_ports(1, 4), leaf_native=100,
                    leaf_type=T100, leaf_breakout='1x100g', leaf_supported=['1x100g'],
                    leaf_slots=NATIVE_LEAF_4,
                    spine_model='accept27-spine-a-100g', spine_ports=_ports(1, 8), spine_native=100,
                    spine_type=T100, spine_breakout='1x100g', spine_supported=['1x100g'],
                    spine_slots=NATIVE_SPINE_8, link_type=T100)
        self._run_case(expected_spines=2, links_per_pair=2, cables_total=16, regenerate=True)

    def test_b_larger_native_100g(self):
        self._build(case='b', leaves_total=8,
                    leaf_model='accept27-leaf-b-100g', leaf_ports=_ports(1, 4), leaf_native=100,
                    leaf_type=T100, leaf_breakout='1x100g', leaf_supported=['1x100g'],
                    leaf_slots=NATIVE_LEAF_4,
                    spine_model='accept27-spine-b-100g', spine_ports=_ports(1, 8), spine_native=100,
                    spine_type=T100, spine_breakout='1x100g', spine_supported=['1x100g'],
                    spine_slots=NATIVE_SPINE_8, link_type=T100)
        self._run_case(expected_spines=4, links_per_pair=1, cables_total=32)

    def test_c_native_400g_leaves_breakout_800g_spines(self):
        # Native-only spine capacity (4 cages) would give 4 spines; logical capacity is 8.
        self._build(case='c', leaves_total=4,
                    leaf_model='accept27-leaf-c-400g', leaf_ports=_ports(1, 4), leaf_native=400,
                    leaf_type=T400, leaf_breakout='1x400g', leaf_supported=['1x400g'],
                    leaf_slots=NATIVE_LEAF_4,
                    spine_model='accept27-spine-c-800g', spine_ports=_ports(1, 4), spine_native=800,
                    spine_type=T800, spine_breakout='2x400g', spine_supported=['1x800g', '2x400g'],
                    spine_slots=BREAKOUT_SPINE_4X2, link_type=T400)
        self._run_case(expected_spines=2, links_per_pair=2, cables_total=16)

    def test_d_breakout_both_sides(self):
        self._build(case='d', leaves_total=4,
                    leaf_model='accept27-leaf-d-800g', leaf_ports=_ports(1, 2), leaf_native=800,
                    leaf_type=T800, leaf_breakout='2x400g', leaf_supported=['1x800g', '2x400g'],
                    leaf_slots=BREAKOUT_LEAF_2X2,
                    spine_model='accept27-spine-d-800g', spine_ports=_ports(1, 4), spine_native=800,
                    spine_type=T800, spine_breakout='2x400g', spine_supported=['1x800g', '2x400g'],
                    spine_slots=BREAKOUT_SPINE_4X2, link_type=T400)
        self._run_case(expected_spines=2, links_per_pair=2, cables_total=16)
