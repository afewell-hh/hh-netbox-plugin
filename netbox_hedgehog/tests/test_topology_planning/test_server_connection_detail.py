"""
RED tests for DIET-460: Server connection detail page improvements.

Tests reference the updated planserverconnection.html template which does not
yet include the Switch-Side Transceiver row or the corrected Target Zone link.
DET-1 through DET-4 from #461 spec.
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

from dcim.models import DeviceType, Manufacturer, ModuleType, ModuleTypeProfile

from netbox_hedgehog.choices import (
    AllocationStrategyChoices,
    ConnectionDistributionChoices,
    ConnectionTypeChoices,
    FabricTypeChoices,
    HedgehogRoleChoices,
    PortZoneTypeChoices,
    ServerClassCategoryChoices,
    TopologyPlanStatusChoices,
)
from netbox_hedgehog.models.topology_planning import (
    BreakoutOption,
    DeviceTypeExtension,
    PlanServerClass,
    PlanServerConnection,
    PlanSwitchClass,
    SwitchPortZone,
    TopologyPlan,
)
from netbox_hedgehog.tests.test_topology_planning import get_test_server_nic

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_xcvr_profile():
    profile, _ = ModuleTypeProfile.objects.get_or_create(
        name='Network Transceiver',
        defaults={'schema': {}},
    )
    return profile


def _make_zone_xcvr(model='DET-ZONE-XCVR', description='DET Zone Optic 400G'):
    profile = _ensure_xcvr_profile()
    mfr, _ = Manufacturer.objects.get_or_create(
        name='DET-ZoneVendor', defaults={'slug': 'det-zonevendor'}
    )
    mt, _ = ModuleType.objects.get_or_create(
        manufacturer=mfr, model=model,
        defaults={
            'profile': profile,
            'description': description,
            'attribute_data': {'cage_type': 'QSFP112', 'medium': 'MMF'},
        },
    )
    return mt


def _make_fixtures():
    mfr, _ = Manufacturer.objects.get_or_create(
        name='DET-SwVendor', defaults={'slug': 'det-swvendor'}
    )
    dt, _ = DeviceType.objects.get_or_create(
        manufacturer=mfr, model='DET-Switch', defaults={'slug': 'det-switch'}
    )
    ext, _ = DeviceTypeExtension.objects.update_or_create(
        device_type=dt,
        defaults={
            'native_speed': 400,
            'supported_breakouts': ['1x400g'],
            'mclag_capable': False,
            'hedgehog_roles': ['server-leaf'],
        },
    )
    bo, _ = BreakoutOption.objects.get_or_create(
        breakout_id='det-1x400g',
        defaults={'from_speed': 400, 'logical_ports': 1, 'logical_speed': 400},
    )
    srv_mfr, _ = Manufacturer.objects.get_or_create(
        name='DET-SrvVendor', defaults={'slug': 'det-srvvendor'}
    )
    srv_dt, _ = DeviceType.objects.get_or_create(
        manufacturer=srv_mfr, model='DET-Server', defaults={'slug': 'det-server'}
    )
    return ext, bo, srv_dt


def _build_plan_with_connection(zone_xcvr=None):
    """
    Return (plan, switch_class, zone, server_class, connection).

    If zone_xcvr is provided it is set on the zone's transceiver_module_type.
    """
    ext, bo, srv_dt = _make_fixtures()
    plan = TopologyPlan.objects.create(
        name='DET-Plan', status=TopologyPlanStatusChoices.DRAFT
    )
    sw = PlanSwitchClass.objects.create(
        plan=plan,
        switch_class_id='det-fe-leaf',
        fabric=FabricTypeChoices.FRONTEND,
        hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
        device_type_extension=ext,
        uplink_ports_per_switch=4,
    )
    zone = SwitchPortZone.objects.create(
        switch_class=sw,
        zone_name='det-server-zone',
        zone_type=PortZoneTypeChoices.SERVER,
        port_spec='1-32',
        breakout_option=bo,
        allocation_strategy=AllocationStrategyChoices.SEQUENTIAL,
        priority=100,
        transceiver_module_type=zone_xcvr,
    )
    sc = PlanServerClass.objects.create(
        plan=plan,
        server_class_id='det-gpu',
        category=ServerClassCategoryChoices.GPU,
        quantity=2,
        gpus_per_server=8,
        server_device_type=srv_dt,
    )
    nic = get_test_server_nic(sc, nic_id='nic-det')
    conn = PlanServerConnection.objects.create(
        server_class=sc,
        connection_id='DET-001',
        nic=nic,
        port_index=0,
        target_zone=zone,
        ports_per_connection=1,
        hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
        distribution=ConnectionDistributionChoices.ALTERNATING,
        speed=400,
        port_type='data',
        transceiver_module_type=None,
    )
    return plan, sw, zone, sc, conn


# ---------------------------------------------------------------------------
# TestConnectionDetailSwitchSideRow
# ---------------------------------------------------------------------------

class TestConnectionDetailSwitchSideRow(TestCase):
    """
    RED tests for the Switch-Side Transceiver row on the server connection
    detail page and the corrected Target Zone / Edit zone transceiver links.
    """

    @classmethod
    def setUpTestData(cls):
        _ensure_xcvr_profile()
        cls.zone_xcvr = _make_zone_xcvr()
        cls.superuser = User.objects.create_user(
            username='det-su', password='pass', is_staff=True, is_superuser=True
        )
        # Connection whose zone has a transceiver (DET-1, DET-3, DET-4)
        _, _, cls.zone_with_xcvr, _, cls.conn_with_xcvr = _build_plan_with_connection(
            zone_xcvr=cls.zone_xcvr
        )

    def setUp(self):
        self.client = Client()
        self.client.login(username='det-su', password='pass')

    # DET-1: zone has transceiver_module_type with description →
    #        detail page contains description string in "Switch-Side Transceiver" row
    def test_det1_switch_side_transceiver_shows_description(self):
        url = reverse(
            'plugins:netbox_hedgehog:planserverconnection_detail',
            args=[self.__class__.conn_with_xcvr.pk],
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        # The row heading must be present
        self.assertIn('Switch-Side Transceiver', content)
        # The zone transceiver description must be shown
        self.assertIn('DET Zone Optic 400G', content)

    # DET-2: zone transceiver_module_type=None → detail page shows "—" in that row
    def test_det2_no_zone_transceiver_shows_dash(self):
        # Build a second connection with no zone xcvr
        _, _, zone_no_xcvr, _, conn_no_xcvr = _build_plan_with_connection(
            zone_xcvr=None
        )
        url = reverse(
            'plugins:netbox_hedgehog:planserverconnection_detail',
            args=[conn_no_xcvr.pk],
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        # Row must still be present
        self.assertIn('Switch-Side Transceiver', content)
        # em-dash or literal "—" must appear (template uses &mdash; or —)
        self.assertTrue(
            '&mdash;' in content or '\u2014' in content,
            'Expected an em-dash for empty switch-side transceiver',
        )

    # DET-3: "Edit zone transceiver" link resolves to switchportzone_edit for target_zone.pk
    def test_det3_edit_zone_transceiver_link_targets_switchportzone_edit(self):
        conn = self.__class__.conn_with_xcvr
        zone = self.__class__.zone_with_xcvr
        url = reverse(
            'plugins:netbox_hedgehog:planserverconnection_detail',
            args=[conn.pk],
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        # The edit link must point to the zone edit URL
        expected_href = reverse(
            'plugins:netbox_hedgehog:switchportzone_edit',
            args=[zone.pk],
        )
        self.assertIn(expected_href, content)
        # Anchor text must be discoverable as "Edit zone transceiver" (case-insensitive)
        self.assertIn('edit zone transceiver', content.lower())

    # DET-4: "Target Zone" link resolves to switchportzone detail (zone pk),
    #        NOT to the switch class
    def test_det4_target_zone_link_points_to_zone_not_switch_class(self):
        conn = self.__class__.conn_with_xcvr
        zone = self.__class__.zone_with_xcvr
        url = reverse(
            'plugins:netbox_hedgehog:planserverconnection_detail',
            args=[conn.pk],
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        # Correct link: switchportzone detail for the zone
        zone_detail_href = reverse(
            'plugins:netbox_hedgehog:switchportzone',
            args=[zone.pk],
        )
        self.assertIn(zone_detail_href, content)
        # Wrong link: planswitchclass_detail for the switch class must NOT
        # be the target of the "Target Zone" row (it may appear elsewhere,
        # so check that the zone detail link exists rather than asserting the
        # switch class link is absent)
        # The zone detail href being present is sufficient for DET-4.
        # Additionally confirm the link text "Target Zone" is present.
        self.assertIn('Target Zone', content)
