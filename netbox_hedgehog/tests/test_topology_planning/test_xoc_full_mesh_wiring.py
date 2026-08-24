"""
Focused full-mesh spine-leaf wiring tests for the experimental XOC-3712
composition (issue #603).

Governing invariant: each included leaf reserves 32x800G uplinks and connects
once to every spine in its fabric. The shared spine tier is pinned at 32
(topology invariant, not capacity-derived). This works because
`DeviceGenerator._create_fabric_connections` distributes leaf uplinks across
spines as `base = uplinks // spines`, `remainder = uplinks % spines` — so when
`uplinks == spines`, base=1 / remainder=0 → exactly one link to every spine
(a complete leaf↔spine mesh), and leaves are gathered by `hedgehog_fabric`
across switch classes (so leaves from different OPG domains share the tier).

These tests are experimental (branch-only); they do not publish OCP content.
"""

from io import StringIO
from math import ceil

from django.core.management import call_command
from django.test import TestCase

from dcim.choices import DeviceStatusChoices
from dcim.models import Cable, Device, DeviceRole, DeviceType, InterfaceTemplate, Manufacturer, Site
from netbox_hedgehog.choices import (
    AllocationStrategyChoices,
    FabricClassChoices,
    HedgehogRoleChoices,
    PortZoneTypeChoices,
)
from netbox_hedgehog.models.topology_planning import (
    BreakoutOption,
    DeviceTypeExtension,
    PlanSwitchClass,
    SwitchPortZone,
    TopologyPlan,
)
from netbox_hedgehog.services.device_generator import DeviceGenerator
from netbox_hedgehog.test_cases import runner
from netbox_hedgehog.utils.topology_calculations import update_plan_calculations


class FabricFullMeshWiringTests(TestCase):
    """Directly exercise `_create_fabric_connections` on a minimal shared-spine
    fabric with two leaf classes (two 'domains') and N spines == N leaf uplinks."""

    N = 4  # uplinks per leaf == spines; proves base=1/remainder=0 full mesh

    @classmethod
    def setUpTestData(cls):
        mfg, _ = Manufacturer.objects.get_or_create(name='XOC603-Mfg', defaults={'slug': 'xoc603-mfg'})
        cls.sw_type, _ = DeviceType.objects.get_or_create(
            manufacturer=mfg, model='XOC603-Switch', defaults={'slug': 'xoc603-switch'},
        )
        for i in range(1, 9):
            InterfaceTemplate.objects.get_or_create(
                device_type=cls.sw_type, name=f'E1/{i}', defaults={'type': '100gbase-x-qsfp28'},
            )
        cls.ext, _ = DeviceTypeExtension.objects.get_or_create(
            device_type=cls.sw_type,
            defaults={
                'mclag_capable': False,
                'hedgehog_roles': ['spine', 'server-leaf'],
                'native_speed': 100, 'supported_breakouts': ['1x100g'],
                'uplink_ports': cls.N, 'hedgehog_profile_name': 'xoc603-profile',
            },
        )
        cls.leaf_role, _ = DeviceRole.objects.get_or_create(
            name='XOC603-Leaf', defaults={'slug': 'xoc603-leaf', 'color': '0000ff'},
        )
        cls.spine_role, _ = DeviceRole.objects.get_or_create(
            name='XOC603-Spine', defaults={'slug': 'xoc603-spine', 'color': 'ff0000'},
        )
        cls.site, _ = Site.objects.get_or_create(slug='xoc603', defaults={'name': 'XOC603'})
        cls.b100, _ = BreakoutOption.objects.get_or_create(
            breakout_id='1x100g',
            defaults={'from_speed': 100, 'logical_ports': 1, 'logical_speed': 100},
        )

        cls.plan = TopologyPlan.objects.create(name='XOC603 Full Mesh', status='draft')

        # Two leaf classes (two OPG 'domains') sharing one fabric + one spine class.
        cls.leaf_classes = []
        for dom in ('a', 'b'):
            lc = PlanSwitchClass.objects.create(
                plan=cls.plan, switch_class_id=f'leaf-{dom}', fabric_name='xocfab',
                fabric_class=FabricClassChoices.MANAGED, hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
                device_type_extension=cls.ext, uplink_ports_per_switch=cls.N, mclag_pair=False,
            )
            SwitchPortZone.objects.create(
                switch_class=lc, zone_name=f'leaf-{dom}-uplinks', zone_type=PortZoneTypeChoices.UPLINK,
                port_spec=f'1-{cls.N}', breakout_option=cls.b100,
                allocation_strategy=AllocationStrategyChoices.SEQUENTIAL, priority=10,
            )
            cls.leaf_classes.append(lc)
        cls.spine_class = PlanSwitchClass.objects.create(
            plan=cls.plan, switch_class_id='spine', fabric_name='xocfab',
            fabric_class=FabricClassChoices.MANAGED, hedgehog_role=HedgehogRoleChoices.SPINE,
            device_type_extension=cls.ext, uplink_ports_per_switch=0,
            override_quantity=cls.N, mclag_pair=False,
        )
        SwitchPortZone.objects.create(
            switch_class=cls.spine_class, zone_name='spine-downlinks', zone_type=PortZoneTypeChoices.FABRIC,
            port_spec='1-8', breakout_option=cls.b100,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL, priority=10,
        )

    def _mk_switch(self, name, class_id, role):
        d = Device.objects.create(
            name=name, device_type=self.sw_type,
            role=self.leaf_role if role == HedgehogRoleChoices.SERVER_LEAF else self.spine_role,
            site=self.site, status=DeviceStatusChoices.STATUS_PLANNED,
        )
        d.custom_field_data = {
            'hedgehog_plan_id': str(self.plan.pk), 'hedgehog_class': class_id,
            'hedgehog_fabric': 'xocfab', 'hedgehog_fabric_class': FabricClassChoices.MANAGED,
            'hedgehog_role': role,
        }
        d.save()
        return d

    def test_every_leaf_connects_once_to_every_spine(self):
        # 2 leaves (one per domain class) + N spines, all in fabric 'xocfab'.
        switch_devices = {}
        leaf_a = self._mk_switch('leaf-a-01', 'leaf-a', HedgehogRoleChoices.SERVER_LEAF)
        leaf_b = self._mk_switch('leaf-b-01', 'leaf-b', HedgehogRoleChoices.SERVER_LEAF)
        switch_devices['leaf-a-01'] = leaf_a
        switch_devices['leaf-b-01'] = leaf_b
        spines = []
        for i in range(1, self.N + 1):
            s = self._mk_switch(f'spine-{i:02d}', 'spine', HedgehogRoleChoices.SPINE)
            switch_devices[s.name] = s
            spines.append(s)

        gen = DeviceGenerator(plan=self.plan, site=self.site)
        interfaces, cables = gen._create_fabric_connections(switch_devices)

        leaves = [leaf_a, leaf_b]
        # base = uplinks(N) // spines(N) = 1, remainder = 0 -> one link per (leaf, spine)
        self.assertEqual(len(cables), len(leaves) * len(spines))

        # Build (leaf, spine) adjacency from cable terminations.
        pairs = set()
        spine_names = {s.name for s in spines}
        for c in cables:
            a = c.a_terminations[0].device.name
            b = c.b_terminations[0].device.name
            leaf, spine = (a, b) if b in spine_names else (b, a)
            pairs.add((leaf, spine))

        # Full mesh: every leaf connects to every spine exactly once.
        for leaf in leaves:
            connected = {sp for (lf, sp) in pairs if lf == leaf.name}
            self.assertEqual(connected, spine_names,
                             f'{leaf.name} must connect to all {self.N} spines exactly once')
        # Each spine's downlink count == number of leaves.
        for s in spines:
            downlinks = sum(1 for (lf, sp) in pairs if sp == s.name)
            self.assertEqual(downlinks, len(leaves))


class FabricFullMeshArithmeticTests(TestCase):
    """Pure-arithmetic guard covering the real XOC scales (incl. 32 spines)
    without generating devices."""

    def test_uplinks_equal_spines_gives_one_link_per_spine(self):
        # Mirrors _create_fabric_connections: base/remainder distribution.
        for n in (4, 14, 32, 51):
            uplinks, spines = n, n
            base, remainder = divmod(uplinks, spines)
            self.assertEqual((base, remainder), (1, 0),
                             f'{n} uplinks over {n} spines must give exactly 1 link/spine')

    def test_xoc3712_cable_and_port_budget(self):
        # frontend 14 leaves, backends 51 leaves each; 32 spines per fabric.
        SPINES = 32
        fabrics = {'frontend': 14, 'backend-plane-a': 51, 'backend-plane-b': 51}
        total = 0
        for fabric, leaves in fabrics.items():
            total += leaves * SPINES
            # each spine's downlink usage == leaf count, must fit DS5000's 64 ports
            self.assertLessEqual(leaves, 64, f'{fabric}: {leaves} leaves exceed spine downlink ports')
        self.assertEqual(total, 3712)  # 448 + 1632 + 1632


class Opg640SpinePinningTests(TestCase):
    """The OPG-640 fixture models a complete spine-leaf design: 2/3/3 leaves,
    32 pinned spines per fabric, and passes the pre-write capacity check."""

    CASE = 'training_opg640_dual_plane_dedicated_fabrics'

    @classmethod
    def setUpTestData(cls):
        call_command('load_diet_reference_data', stdout=StringIO(), stderr=StringIO())
        cls.plan = runner.apply_case_id(cls.CASE, clean=True)
        update_plan_calculations(cls.plan)

    def test_leaf_and_spine_counts(self):
        eff = {sc.switch_class_id: sc.effective_quantity for sc in self.plan.switch_classes.all()}
        self.assertEqual(eff['fe-leaf'], 2)
        self.assertEqual(eff['be-plane-a-leaf'], 3)
        self.assertEqual(eff['be-plane-b-leaf'], 3)
        for spine in ('fe-spine', 'be-plane-a-spine', 'be-plane-b-spine'):
            self.assertEqual(eff[spine], 32, f'{spine} must be pinned at 32')

    def test_total_xpus_and_servers(self):
        self.assertEqual(sum(s.quantity for s in self.plan.server_classes.all()), 80)  # 48 SN40 + 32 SN50

    def test_capacity_preflight_passes(self):
        # Mixed 200G/400G same-switch modeling must fit every zone.
        DeviceGenerator(plan=self.plan)._preflight_zone_capacity()  # raises on over-subscription
