"""
RED phase tests -- zone-targeted connections: UI, CRUD, model validation (#201).
All tests FAIL with current code. Passes after GREEN phase implementation.
"""
from django.core.exceptions import FieldError, ValidationError
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

from dcim.models import DeviceType, InterfaceTemplate, Manufacturer, ModuleType

from netbox_hedgehog.models.topology_planning import (
    DeviceTypeExtension, GenerationState, PlanServerClass,
    PlanServerConnection, PlanSwitchClass, SwitchPortZone, TopologyPlan,
)
from netbox_hedgehog.choices import (
    FabricTypeChoices, HedgehogRoleChoices, ServerClassCategoryChoices,
    ConnectionTypeChoices, ConnectionDistributionChoices,
)
from netbox_hedgehog.utils.snapshot_builder import build_plan_snapshot

User = get_user_model()


def _base_fixtures(cls):
    cls.mfr, _ = Manufacturer.objects.get_or_create(
        name="ZT-UI", defaults={"slug": "zt-ui"})
    cls.server_dt, _ = DeviceType.objects.get_or_create(
        manufacturer=cls.mfr, model="SRV-UI", defaults={"slug": "srv-ui"})
    cls.switch_dt, _ = DeviceType.objects.get_or_create(
        manufacturer=cls.mfr, model="SW-UI", defaults={"slug": "sw-ui"})
    cls.ext, _ = DeviceTypeExtension.objects.get_or_create(
        device_type=cls.switch_dt,
        defaults={"mclag_capable": False, "hedgehog_roles": ["server-leaf"],
                  "native_speed": 100, "uplink_ports": 2,
                  "supported_breakouts": ["1x100g"]})
    cls.nic_mfr, _ = Manufacturer.objects.get_or_create(
        name="NIC-UI", defaults={"slug": "nic-ui"})
    cls.nic = ModuleType.objects.create(manufacturer=cls.nic_mfr, model="CX7-UI-TEST")
    InterfaceTemplate.objects.create(module_type=cls.nic, name="{module}p0", type="other")
    InterfaceTemplate.objects.create(module_type=cls.nic, name="{module}p1", type="other")
    cls.user = User.objects.create_user(
        username="ztui-user", password="pass", is_staff=True, is_superuser=True)


class ZoneTargetedCRUDTestCase(TestCase):
    """T01-T06: CRUD flows reference target_zone. FAILS RED: field absent."""

    @classmethod
    def setUpTestData(cls):
        _base_fixtures(cls)
        cls.plan = TopologyPlan.objects.create(name="CRUD-Plan")
        cls.sc = PlanServerClass.objects.create(
            plan=cls.plan, server_class_id="srv-crud",
            category=ServerClassCategoryChoices.GPU, quantity=1,
            server_device_type=cls.server_dt)
        cls.sw = PlanSwitchClass.objects.create(
            plan=cls.plan, switch_class_id="sw-crud",
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=cls.ext, calculated_quantity=1)
        cls.zone = SwitchPortZone.objects.create(
            switch_class=cls.sw, zone_name="server-downlinks",
            zone_type="server", port_spec="1-4", allocation_strategy="sequential")
        cls.oob_zone = SwitchPortZone.objects.create(
            switch_class=cls.sw, zone_name="oob-ports",
            zone_type="oob", port_spec="5-6", allocation_strategy="sequential")

    def setUp(self):
        self.client = Client()
        self.client.login(username="ztui-user", password="pass")

    def test_connection_list_shows_target_zone_column(self):
        """T01: list view must show 'Target Zone' not 'Target Switch Class'. FAILS RED."""
        resp = self.client.get(reverse("plugins:netbox_hedgehog:planserverconnection_list"))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        # FAILS RED: old heading still says "Target Switch Class"
        self.assertIn("Target Zone", content)
        self.assertNotIn("Target Switch Class", content)

    def test_add_form_has_target_zone_not_switch_class(self):
        """T02: add form renders target_zone field. FAILS RED: field not in form."""
        resp = self.client.get(reverse("plugins:netbox_hedgehog:planserverconnection_add"))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        # FAILS RED: form renders target_switch_class, not target_zone
        self.assertIn("target_zone", content)
        self.assertNotIn("target_switch_class", content)

    def test_create_connection_with_target_zone(self):
        """T03: POST with target_zone PK creates object. FAILS RED: field absent."""
        url = reverse("plugins:netbox_hedgehog:planserverconnection_add")
        data = {
            "server_class": self.sc.pk, "connection_id": "zt-crud-01",
            "nic_module_type": self.nic.pk, "port_index": 0,
            "ports_per_connection": 1, "hedgehog_conn_type": "unbundled",
            "distribution": "same-switch",
            "target_zone": self.zone.pk,  # FAILS RED: form field doesn't exist
            "speed": 100,
        }
        resp = self.client.post(url, data, follow=False)
        self.assertEqual(resp.status_code, 302)
        conn = PlanServerConnection.objects.get(connection_id="zt-crud-01")
        # FAILS RED: AttributeError
        self.assertEqual(conn.target_zone, self.zone)

    def test_detail_shows_zone_name(self):
        """T04: detail view shows zone_name. FAILS RED: template uses target_switch_class."""
        conn = PlanServerConnection.objects.create(
            server_class=self.sc, connection_id="zt-detail",
            nic_module_type=self.nic, port_index=0,
            ports_per_connection=1, hedgehog_conn_type="unbundled",
            distribution="same-switch", target_switch_class=self.sw, speed=100)
        url = reverse("plugins:netbox_hedgehog:planserverconnection_detail", args=[conn.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        # FAILS RED: template still shows switch class, not zone name
        self.assertIn("server-downlinks", resp.content.decode())

    def test_edit_connection_with_target_zone(self):
        """T05: edit form accepts target_zone. FAILS RED: field absent."""
        conn = PlanServerConnection.objects.create(
            server_class=self.sc, connection_id="zt-edit",
            nic_module_type=self.nic, port_index=0,
            ports_per_connection=1, hedgehog_conn_type="unbundled",
            distribution="same-switch", target_switch_class=self.sw, speed=100)
        url = reverse("plugins:netbox_hedgehog:planserverconnection_edit", args=[conn.pk])
        data = {
            "server_class": self.sc.pk, "connection_id": "zt-edit",
            "nic_module_type": self.nic.pk, "port_index": 0,
            "ports_per_connection": 2, "hedgehog_conn_type": "unbundled",
            "distribution": "same-switch",
            "target_zone": self.zone.pk,  # FAILS RED: form field absent
            "speed": 100,
        }
        resp = self.client.post(url, data, follow=False)
        self.assertEqual(resp.status_code, 302)
        conn.refresh_from_db()
        self.assertEqual(conn.target_zone, self.zone)  # FAILS RED


class ZonePickerFilterTestCase(TestCase):
    """T07-T09: zone picker filters. FAILS RED: form uses target_switch_class."""

    @classmethod
    def setUpTestData(cls):
        _base_fixtures(cls)
        cls.plan1 = TopologyPlan.objects.create(name="ZP-Plan1")
        cls.plan2 = TopologyPlan.objects.create(name="ZP-Plan2")
        cls.sc1 = PlanServerClass.objects.create(
            plan=cls.plan1, server_class_id="srv-zp1",
            category=ServerClassCategoryChoices.GPU, quantity=1,
            server_device_type=cls.server_dt)
        cls.sw1 = PlanSwitchClass.objects.create(
            plan=cls.plan1, switch_class_id="sw-zp1",
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=cls.ext, calculated_quantity=1)
        cls.sw2 = PlanSwitchClass.objects.create(
            plan=cls.plan2, switch_class_id="sw-zp2",
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=cls.ext, calculated_quantity=1)
        cls.zone1 = SwitchPortZone.objects.create(
            switch_class=cls.sw1, zone_name="server-p1",
            zone_type="server", port_spec="1-4", allocation_strategy="sequential")
        cls.zone2 = SwitchPortZone.objects.create(
            switch_class=cls.sw2, zone_name="server-p2",
            zone_type="server", port_spec="1-4", allocation_strategy="sequential")
        cls.uplink_zone = SwitchPortZone.objects.create(
            switch_class=cls.sw1, zone_name="uplinks",
            zone_type="uplink", port_spec="5-8", allocation_strategy="sequential")

    def setUp(self):
        self.client = Client()
        self.client.login(username="ztui-user", password="pass")

    def test_zone_picker_same_plan_only(self):
        """T07: form queryset excludes zones from other plan. FAILS RED: no target_zone field."""
        from netbox_hedgehog.forms.topology_planning import PlanServerConnectionForm
        form = PlanServerConnectionForm(initial={"server_class": self.sc1.pk})
        # FAILS RED: 'target_zone' field not in form.fields
        qs = form.fields["target_zone"].queryset
        self.assertIn(self.zone1, qs)
        self.assertNotIn(self.zone2, qs)

    def test_zone_picker_excludes_uplink_zones(self):
        """T08: uplink zone must not appear in picker. FAILS RED: no target_zone field."""
        from netbox_hedgehog.forms.topology_planning import PlanServerConnectionForm
        form = PlanServerConnectionForm(initial={"server_class": self.sc1.pk})
        qs = form.fields["target_zone"].queryset  # FAILS RED
        self.assertNotIn(self.uplink_zone, qs)

    def test_cross_plan_zone_rejected_by_form(self):
        """T09: POSTing zone from wrong plan returns form error. FAILS RED."""
        self.client.login(username="ztui-user", password="pass")
        url = reverse("plugins:netbox_hedgehog:planserverconnection_add")
        data = {
            "server_class": self.sc1.pk, "connection_id": "xplan-01",
            "nic_module_type": self.nic.pk, "port_index": 0,
            "ports_per_connection": 1, "hedgehog_conn_type": "unbundled",
            "distribution": "same-switch",
            "target_zone": self.zone2.pk,  # wrong plan zone -- FAILS RED: field absent
            "speed": 100,
        }
        resp = self.client.post(url, data, follow=False)
        # Should re-render form (200) with error, not redirect (302)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(PlanServerConnection.objects.filter(connection_id="xplan-01").exists())


class ZoneTargetedModelValidationTestCase(TestCase):
    """T11-T15: model clean() enforces zone constraints. FAILS RED: field absent."""

    @classmethod
    def setUpTestData(cls):
        _base_fixtures(cls)
        cls.plan = TopologyPlan.objects.create(name="MV-Plan1")
        cls.plan2 = TopologyPlan.objects.create(name="MV-Plan2")
        cls.sc = PlanServerClass.objects.create(
            plan=cls.plan, server_class_id="srv-mv",
            category=ServerClassCategoryChoices.GPU, quantity=1,
            server_device_type=cls.server_dt)
        cls.sw = PlanSwitchClass.objects.create(
            plan=cls.plan, switch_class_id="sw-mv",
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=cls.ext, calculated_quantity=1)
        cls.sw2 = PlanSwitchClass.objects.create(
            plan=cls.plan2, switch_class_id="sw-mv2",
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=cls.ext, calculated_quantity=1)
        cls.server_zone = SwitchPortZone.objects.create(
            switch_class=cls.sw, zone_name="server-mv",
            zone_type="server", port_spec="1-4", allocation_strategy="sequential")
        cls.oob_zone = SwitchPortZone.objects.create(
            switch_class=cls.sw, zone_name="oob-mv",
            zone_type="oob", port_spec="5-6", allocation_strategy="sequential")
        cls.uplink_zone = SwitchPortZone.objects.create(
            switch_class=cls.sw, zone_name="uplink-mv",
            zone_type="uplink", port_spec="7-8", allocation_strategy="sequential")
        cls.cross_plan_zone = SwitchPortZone.objects.create(
            switch_class=cls.sw2, zone_name="server-mv2",
            zone_type="server", port_spec="1-4", allocation_strategy="sequential")

    def _make_conn(self, **kwargs):
        base = dict(server_class=self.sc, connection_id="mv-tmp",
                    nic_module_type=self.nic, port_index=0,
                    ports_per_connection=1, hedgehog_conn_type="unbundled",
                    distribution="same-switch", speed=100)
        base.update(kwargs)
        return PlanServerConnection(**base)

    def test_model_rejects_cross_plan_zone(self):
        """T11: zone from different plan raises ValidationError. FAILS RED: no target_zone."""
        conn = self._make_conn()
        conn.target_zone = self.cross_plan_zone  # FAILS RED: AttributeError
        with self.assertRaises(ValidationError) as ctx:
            conn.full_clean()
        self.assertIn("target_zone", ctx.exception.message_dict)

    def test_model_rejects_uplink_zone_type(self):
        """T12: uplink zone raises ValidationError. FAILS RED: no target_zone."""
        conn = self._make_conn()
        conn.target_zone = self.uplink_zone  # FAILS RED
        with self.assertRaises(ValidationError) as ctx:
            conn.full_clean()
        self.assertIn("target_zone", ctx.exception.message_dict)

    def test_model_rejects_ipmi_with_server_zone(self):
        """T13: IPMI + SERVER zone raises ValidationError. FAILS RED."""
        conn = self._make_conn(port_type="ipmi")
        conn.target_zone = self.server_zone  # FAILS RED
        with self.assertRaises(ValidationError) as ctx:
            conn.full_clean()
        self.assertIn("target_zone", ctx.exception.message_dict)

    def test_model_rejects_data_with_oob_zone(self):
        """T14: DATA + OOB zone raises ValidationError. FAILS RED."""
        conn = self._make_conn(port_type="data")
        conn.target_zone = self.oob_zone  # FAILS RED
        with self.assertRaises(ValidationError) as ctx:
            conn.full_clean()
        self.assertIn("target_zone", ctx.exception.message_dict)

    def test_target_switch_class_property(self):
        """T15: target_switch_class @property returns zone.switch_class. FAILS RED."""
        conn = self._make_conn()
        conn.target_zone = self.server_zone  # FAILS RED
        # Property must return the switch class, not trigger a DB lookup
        self.assertEqual(conn.target_switch_class, self.sw)


class OrmTargetZoneGuardrailTestCase(TestCase):
    """
    Mandatory ORM guardrails (Dev C requirement).
    Verify target_zone ORM operations work and target_switch_class ORM operations fail.
    ALL tests FAIL RED.
    """

    @classmethod
    def setUpTestData(cls):
        _base_fixtures(cls)
        cls.plan = TopologyPlan.objects.create(name="ORM-Plan")
        cls.sc = PlanServerClass.objects.create(
            plan=cls.plan, server_class_id="srv-orm",
            category=ServerClassCategoryChoices.GPU, quantity=1,
            server_device_type=cls.server_dt)
        cls.sw = PlanSwitchClass.objects.create(
            plan=cls.plan, switch_class_id="sw-orm",
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=cls.ext, calculated_quantity=1)
        cls.zone = SwitchPortZone.objects.create(
            switch_class=cls.sw, zone_name="server-orm",
            zone_type="server", port_spec="1-4", allocation_strategy="sequential")

    def test_orm_filter_by_target_zone_works(self):
        """ORM filter(target_zone=zone) must not raise FieldError. FAILS RED: no DB column."""
        # FAILS RED: FieldError -- cannot resolve keyword 'target_zone'
        list(PlanServerConnection.objects.filter(target_zone=self.zone))

    def test_orm_select_related_target_zone_works(self):
        """select_related('target_zone__switch_class') must work. FAILS RED: no DB column."""
        # FAILS RED: ValueError/FieldError
        list(PlanServerConnection.objects.select_related(
            "target_zone", "target_zone__switch_class"))

    def test_orm_filter_by_target_switch_class_raises_field_error(self):
        """
        After migration, target_switch_class is a @property, not a DB column.
        ORM filter must raise FieldError.
        FAILS RED: filter WORKS today (column still exists).
        """
        with self.assertRaises(FieldError):
            list(PlanServerConnection.objects.filter(target_switch_class_id__isnull=False))

    def test_orm_select_related_target_switch_class_raises_error(self):
        """
        select_related('target_switch_class') must fail after column removal.
        FAILS RED: select_related WORKS today.
        """
        with self.assertRaises((FieldError, ValueError)):
            list(PlanServerConnection.objects.select_related("target_switch_class"))

    def test_snapshot_uses_target_zone_key_not_switch_class_key(self):
        """snapshot builder must emit 'target_zone_id', not 'target_switch_class_id'. FAILS RED."""
        conn = PlanServerConnection.objects.create(
            server_class=self.sc, connection_id="orm-snap",
            nic_module_type=self.nic, port_index=0,
            ports_per_connection=1, hedgehog_conn_type="unbundled",
            distribution="same-switch", target_switch_class=self.sw, speed=100)
        snap = build_plan_snapshot(self.plan)
        self.assertTrue(len(snap["connections"]) > 0)
        keys = snap["connections"][0].keys()
        # FAILS RED: key is still 'target_switch_class_id'
        self.assertIn("target_zone_id", keys)
        self.assertNotIn("target_switch_class_id", keys)
