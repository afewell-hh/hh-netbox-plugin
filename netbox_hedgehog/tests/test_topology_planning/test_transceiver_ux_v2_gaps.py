"""
Phase 3 RED tests for DIET-458 / #463 — transceiver UX v2 gaps.

Scope
-----
DIET-460 implemented the Server-Link Review panel, Switch-Fabric Link Review
panel, and transceiver picker description labels.  Those surfaces are tested in:
  - test_server_link_review.py   (31 tests, all GREEN)
  - test_switch_fabric_review.py (27 tests, all GREEN)
  - test_transceiver_picker.py   (8 tests, all GREEN)

The remaining gap identified in #463 Phase 3 is discoverability from the ZONE
edit form.  The zone form transceiver help text is technically worded and does
not help users understand the ownership split:
  - server-side transceiver  → set on PlanServerConnection
  - switch-side transceiver  → set on SwitchPortZone

RED failures (will fail until GREEN implementation updates zone form help text):
  Z1  Zone form must use "switch-side transceiver" language (not just
      "switch-side Module generation" buried in a technical parenthetical).
  Z2  Zone form must direct users to PlanServerConnection for the server-side
      pairing (currently no reference to "server connection" at all).
  Z3  Zone form help text must distinguish server-zone vs uplink-zone roles so
      users understand when to edit the zone for server links vs switch uplinks.

All other #463 scope items are confirmed GREEN on current origin/main.
See report in the accompanying PR / issue comment for the full coverage map.
"""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from dcim.models import DeviceType, InterfaceTemplate, Manufacturer
from netbox_hedgehog.choices import (
    AllocationStrategyChoices,
    ConnectionDistributionChoices,
    ConnectionTypeChoices,
    FabricClassChoices,
    FabricTypeChoices,
    HedgehogRoleChoices,
    PortZoneTypeChoices,
    TopologyPlanStatusChoices,
)
from netbox_hedgehog.models.topology_planning import (
    BreakoutOption,
    DeviceTypeExtension,
    PlanServerClass,
    PlanSwitchClass,
    SwitchPortZone,
    TopologyPlan,
)
from netbox_hedgehog.tests.test_topology_planning import get_test_nic_module_type

User = get_user_model()


def _make_ux_v2_fixtures(cls):
    mfr, _ = Manufacturer.objects.get_or_create(
        name='UXv2-Mfg', defaults={'slug': 'uxv2-mfg'}
    )
    cls.server_dt, _ = DeviceType.objects.get_or_create(
        manufacturer=mfr, model='UXv2-SRV', defaults={'slug': 'uxv2-srv'}
    )
    cls.switch_dt, _ = DeviceType.objects.get_or_create(
        manufacturer=mfr, model='UXv2-SW', defaults={'slug': 'uxv2-sw'}
    )
    for n in range(1, 9):
        InterfaceTemplate.objects.get_or_create(
            device_type=cls.switch_dt, name=f'E1/{n}',
            defaults={'type': '100gbase-x-qsfp28'},
        )
    cls.ext, _ = DeviceTypeExtension.objects.update_or_create(
        device_type=cls.switch_dt,
        defaults={
            'native_speed': 100, 'uplink_ports': 0,
            'supported_breakouts': ['1x100g'], 'mclag_capable': False,
            'hedgehog_roles': ['server-leaf'],
        },
    )
    cls.bo, _ = BreakoutOption.objects.get_or_create(
        breakout_id='1x100g-uxv2',
        defaults={'from_speed': 100, 'logical_ports': 1, 'logical_speed': 100},
    )
    cls.superuser = User.objects.create_user(
        username='uxv2-su', password='pass', is_staff=True, is_superuser=True,
    )


class ZoneFormDiscoverabilityTestCase(TestCase):
    """
    Z1-Z3 RED: Zone edit form transceiver help text must communicate ownership
    boundaries clearly to users.

    Current state (fails):
      The help text reads: "Intended transceiver/DAC SKU for all ports in this
      zone.  Must have the Network Transceiver profile.  Used for plan-save
      compatibility validation (Stage 2: switch-side Module generation)."

      This text is technically accurate but fails discoverability:
        - "switch-side transceiver" never appears (only "switch-side Module
          generation" in a technical parenthetical)
        - No mention that the server-side pairing transceiver is set on
          PlanServerConnection
        - No distinction between a server zone and an uplink zone

    Expected state (after GREEN implementation):
      The help text must:
        Z1  Use "switch-side transceiver" as the primary noun phrase
        Z2  Point the user to PlanServerConnection for the server-side pairing
        Z3  Differentiate the role: server zone vs switch-fabric uplink zone
    """

    @classmethod
    def setUpTestData(cls):
        _make_ux_v2_fixtures(cls)

        cls.plan = TopologyPlan.objects.create(
            name='ZoneDiscoverPlan', status=TopologyPlanStatusChoices.DRAFT,
        )
        cls.sw_cls = PlanSwitchClass.objects.create(
            plan=cls.plan,
            switch_class_id='uxv2-leaf',
            fabric_name=FabricTypeChoices.FRONTEND,
            fabric_class=FabricClassChoices.MANAGED,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=cls.ext,
            uplink_ports_per_switch=0,
            mclag_pair=False,
            override_quantity=2,
            redundancy_type='eslag',
        )
        cls.server_zone = SwitchPortZone.objects.create(
            switch_class=cls.sw_cls,
            zone_name='uxv2-server-zone',
            zone_type=PortZoneTypeChoices.SERVER,
            port_spec='1-4',
            breakout_option=cls.bo,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL,
            priority=100,
        )
        cls.uplink_zone = SwitchPortZone.objects.create(
            switch_class=cls.sw_cls,
            zone_name='uxv2-uplink-zone',
            zone_type=PortZoneTypeChoices.UPLINK,
            port_spec='5-8',
            breakout_option=cls.bo,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL,
            priority=200,
        )

    def setUp(self):
        self.client = Client()
        self.client.login(username='uxv2-su', password='pass')

    def _get_server_zone_html(self):
        url = reverse('plugins:netbox_hedgehog:switchportzone_edit',
                      args=[self.server_zone.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        return resp.content.decode()

    def _get_uplink_zone_html(self):
        url = reverse('plugins:netbox_hedgehog:switchportzone_edit',
                      args=[self.uplink_zone.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        return resp.content.decode()

    # Z1 RED: zone form must use "switch-side transceiver" language
    def test_z1_zone_form_uses_switch_side_transceiver_language(self):
        """
        Z1 RED: Zone form transceiver help text must explicitly say
        'switch-side transceiver', not just bury 'switch-side' in a technical
        parenthetical about Module generation.

        Current: 'Stage 2: switch-side Module generation'  → no 'switch-side transceiver'
        Expected: 'switch-side transceiver' as the primary noun phrase
        """
        content = self._get_server_zone_html()
        self.assertIn(
            'switch-side transceiver',
            content.lower(),
            "Zone form help text must use 'switch-side transceiver' as the primary noun phrase "
            "(currently only uses 'switch-side Module generation' which is technical jargon, "
            "not user-facing guidance).",
        )

    # Z2 RED: zone form must direct users to the server connection for server-side pairing
    def test_z2_zone_form_directs_to_server_connection_for_server_side(self):
        """
        Z2 RED: Zone form must mention that the server-side (pairing) transceiver
        is set on the server connection (PlanServerConnection), not here.

        Current: no mention of 'server connection' at all
        Expected: help text includes 'server connection' to close the ownership loop
        """
        content = self._get_server_zone_html()
        self.assertIn(
            'server connection',
            content.lower(),
            "Zone form help text must point users to the server connection for server-side "
            "transceiver selection (currently no reference to server connection at all).",
        )

    # Z3 RED: uplink zone form communicates switch-fabric link role
    def test_z3_uplink_zone_form_identifies_switch_fabric_role(self):
        """
        Z3 RED: Uplink-type zone form must indicate this zone controls switch-to-switch
        (switch-fabric) link transceivers, distinct from server-facing downlinks.

        Current: help text is generic ('all ports in this zone') — same for every zone type
        Expected: uplink zone form communicates 'switch-fabric' or 'switch uplink' context
        """
        content = self._get_uplink_zone_html()
        has_fabric_mention = any(
            phrase in content.lower()
            for phrase in ('switch-fabric', 'switch uplink', 'switch link', 'uplink transceiver')
        )
        self.assertTrue(
            has_fabric_mention,
            "Uplink zone form help text must communicate switch-fabric / switch uplink role "
            "(currently uses the same generic help text as server zones, giving no discoverability "
            "guidance for switch-to-switch link intent).",
        )
