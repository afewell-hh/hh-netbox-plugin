"""
RED tests for DIET fabric class abstraction (Epic #276, Phase 3 / #280).

These tests intentionally codify the target behavior before implementation:
- `fabric` becomes `fabric_name` + `fabric_class`
- managed/unmanaged behavior gates on class, not fabric name
- generated inventory gains `hedgehog_fabric_class`
- export scoping discovers managed fabric names dynamically
"""

from __future__ import annotations

import importlib
import os
import tempfile
from io import StringIO

import yaml
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse

from dcim.models import Device, DeviceRole, DeviceType, Interface, InterfaceTemplate, Manufacturer, Site

from netbox_hedgehog.models.topology_planning import (
    DeviceTypeExtension,
    GenerationState,
    PlanSwitchClass,
    TopologyPlan,
)
from netbox_hedgehog.choices import GenerationStatusChoices, HedgehogRoleChoices
from netbox_hedgehog.services.yaml_generator import generate_yaml_for_plan

User = get_user_model()


def _switch_names_in_yaml(content: str) -> set[str]:
    return {
        doc["metadata"]["name"]
        for doc in yaml.safe_load_all(content)
        if doc and doc.get("kind") == "Switch"
    }


def _server_names_in_yaml(content: str) -> set[str]:
    return {
        doc["metadata"]["name"]
        for doc in yaml.safe_load_all(content)
        if doc and doc.get("kind") == "Server"
    }


class FabricClassUiRedTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="fabric-ui-admin",
            password="fabric-ui-admin",
            is_staff=True,
            is_superuser=True,
        )
        cls.manufacturer, _ = Manufacturer.objects.get_or_create(
            name="Fabric UI Mfg",
            defaults={"slug": "fabric-ui-mfg"},
        )
        cls.device_type, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.manufacturer,
            model="Fabric UI Switch",
            defaults={"slug": "fabric-ui-switch"},
        )
        cls.device_type_extension, _ = DeviceTypeExtension.objects.get_or_create(
            device_type=cls.device_type,
            defaults={
                "mclag_capable": False,
                "hedgehog_roles": ["server-leaf", "spine"],
                "supported_breakouts": ["1x100g"],
                "native_speed": 100,
                "uplink_ports": 4,
                "hedgehog_profile_name": "fabric-ui-switch",
            },
        )
        cls.plan = TopologyPlan.objects.create(name="Fabric Class UI Plan", created_by=cls.user)
        cls.legacy_switch_class = PlanSwitchClass.objects.create(
            plan=cls.plan,
            switch_class_id="legacy-fe",
            fabric="frontend",
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=cls.device_type_extension,
            uplink_ports_per_switch=4,
        )

    def setUp(self):
        self.client = Client()
        self.client.login(username="fabric-ui-admin", password="fabric-ui-admin")

    def test_add_form_shows_fabric_name_field(self):
        response = self.client.get(reverse("plugins:netbox_hedgehog:planswitchclass_add"))
        self.assertContains(response, 'name="fabric_name"')

    def test_add_form_shows_fabric_class_field(self):
        response = self.client.get(reverse("plugins:netbox_hedgehog:planswitchclass_add"))
        self.assertContains(response, 'name="fabric_class"')

    def test_add_form_hides_legacy_fabric_field(self):
        response = self.client.get(reverse("plugins:netbox_hedgehog:planswitchclass_add"))
        self.assertNotContains(response, 'name="fabric"')

    def test_create_missing_fabric_name_shows_error(self):
        response = self.client.post(
            reverse("plugins:netbox_hedgehog:planswitchclass_add"),
            {
                "plan": self.plan.pk,
                "switch_class_id": "missing-fabric-name",
                "fabric_class": "managed",
                "hedgehog_role": HedgehogRoleChoices.SERVER_LEAF,
                "device_type_extension": self.device_type_extension.pk,
                "uplink_ports_per_switch": 4,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "fabric_name")

    def test_create_missing_fabric_class_shows_error(self):
        response = self.client.post(
            reverse("plugins:netbox_hedgehog:planswitchclass_add"),
            {
                "plan": self.plan.pk,
                "switch_class_id": "missing-fabric-class",
                "fabric_name": "frontend",
                "hedgehog_role": HedgehogRoleChoices.SERVER_LEAF,
                "device_type_extension": self.device_type_extension.pk,
                "uplink_ports_per_switch": 4,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "fabric_class")

    def test_create_with_explicit_name_and_class_persists_fields(self):
        response = self.client.post(
            reverse("plugins:netbox_hedgehog:planswitchclass_add"),
            {
                "plan": self.plan.pk,
                "switch_class_id": "future-switch",
                "fabric_name": "converged",
                "fabric_class": "managed",
                "hedgehog_role": HedgehogRoleChoices.SPINE,
                "device_type_extension": self.device_type_extension.pk,
                "uplink_ports_per_switch": 0,
            },
            follow=False,
        )
        self.assertEqual(response.status_code, 302)
        created = PlanSwitchClass.objects.get(switch_class_id="future-switch")
        self.assertEqual(created.fabric_name, "converged")
        self.assertEqual(created.fabric_class, "managed")

    def test_detail_view_shows_fabric_name_row(self):
        response = self.client.get(
            reverse("plugins:netbox_hedgehog:planswitchclass_detail", args=[self.legacy_switch_class.pk])
        )
        self.assertContains(response, "Fabric Name")

    def test_detail_view_shows_fabric_class_row(self):
        response = self.client.get(
            reverse("plugins:netbox_hedgehog:planswitchclass_detail", args=[self.legacy_switch_class.pk])
        )
        self.assertContains(response, "<th scope=\"row\">Fabric Class</th>", html=True)


class FabricClassYamlIngestionRedTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manufacturer, _ = Manufacturer.objects.get_or_create(
            name="Fabric YAML Mfg",
            defaults={"slug": "fabric-yaml-mfg"},
        )
        cls.device_type, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.manufacturer,
            model="Fabric YAML Switch",
            defaults={"slug": "fabric-yaml-switch"},
        )
        InterfaceTemplate.objects.get_or_create(
            device_type=cls.device_type,
            name="E1/1",
            defaults={"type": "100gbase-x-qsfp28"},
        )

    def _import_ingest(self):
        return importlib.import_module("netbox_hedgehog.test_cases.ingest")

    def _base_case(self, case_id: str) -> dict:
        return {
            "meta": {
                "case_id": case_id,
                "name": case_id,
                "version": 1,
                "managed_by": "yaml",
            },
            "plan": {
                "name": f"Plan {case_id}",
                "status": "draft",
            },
            "reference_data": {
                "manufacturers": [
                    {"id": "m1", "name": self.manufacturer.name, "slug": self.manufacturer.slug}
                ],
                "device_types": [
                    {
                        "id": "dt1",
                        "manufacturer": "m1",
                        "model": self.device_type.model,
                        "slug": self.device_type.slug,
                    }
                ],
                "device_type_extensions": [
                    {
                        "id": "dte1",
                        "device_type": "dt1",
                        "mclag_capable": False,
                        "hedgehog_roles": ["server-leaf"],
                        "supported_breakouts": ["1x100g"],
                        "native_speed": 100,
                        "uplink_ports": 4,
                        "hedgehog_profile_name": "fabric-yaml-switch",
                    }
                ],
            },
            "switch_classes": [],
            "server_classes": [],
            "server_connections": [],
        }

    def test_canonical_yaml_ingests_explicit_fabric_name_and_class(self):
        ingest = self._import_ingest()
        case = self._base_case("canonical_fabric_case")
        case["switch_classes"] = [
            {
                "switch_class_id": "sw-canonical",
                "fabric_name": "converged",
                "fabric_class": "managed",
                "hedgehog_role": "server-leaf",
                "device_type_extension": "dte1",
            }
        ]

        plan = ingest.apply_case(case, clean=False, prune=False, reference_mode="ensure")
        switch_class = PlanSwitchClass.objects.get(plan=plan, switch_class_id="sw-canonical")
        self.assertEqual(switch_class.fabric_name, "converged")
        self.assertEqual(switch_class.fabric_class, "managed")

    def test_legacy_frontend_fabric_infers_managed(self):
        ingest = self._import_ingest()
        case = self._base_case("legacy_frontend_case")
        case["switch_classes"] = [
            {
                "switch_class_id": "sw-legacy-fe",
                "fabric": "frontend",
                "hedgehog_role": "server-leaf",
                "device_type_extension": "dte1",
            }
        ]

        plan = ingest.apply_case(case, clean=False, prune=False, reference_mode="ensure")
        switch_class = PlanSwitchClass.objects.get(plan=plan, switch_class_id="sw-legacy-fe")
        self.assertEqual(switch_class.fabric_name, "frontend")
        self.assertEqual(switch_class.fabric_class, "managed")

    def test_legacy_oob_mgmt_fabric_infers_unmanaged(self):
        ingest = self._import_ingest()
        case = self._base_case("legacy_oob_case")
        case["switch_classes"] = [
            {
                "switch_class_id": "sw-legacy-oob",
                "fabric": "oob-mgmt",
                "hedgehog_role": "server-leaf",
                "device_type_extension": "dte1",
            }
        ]

        plan = ingest.apply_case(case, clean=False, prune=False, reference_mode="ensure")
        switch_class = PlanSwitchClass.objects.get(plan=plan, switch_class_id="sw-legacy-oob")
        self.assertEqual(switch_class.fabric_name, "oob-mgmt")
        self.assertEqual(switch_class.fabric_class, "unmanaged")

    def test_yaml_rejects_mismatched_fabric_and_fabric_name(self):
        ingest = self._import_ingest()
        case = self._base_case("mismatch_case")
        case["switch_classes"] = [
            {
                "switch_class_id": "sw-mismatch",
                "fabric": "frontend",
                "fabric_name": "backend",
                "fabric_class": "managed",
                "hedgehog_role": "server-leaf",
                "device_type_extension": "dte1",
            }
        ]

        with self.assertRaises(Exception):
            ingest.apply_case(case, clean=False, prune=False, reference_mode="ensure")

    def test_yaml_rejects_blank_fabric_name(self):
        ingest = self._import_ingest()
        case = self._base_case("blank_name_case")
        case["switch_classes"] = [
            {
                "switch_class_id": "sw-blank-name",
                "fabric_name": "",
                "fabric_class": "managed",
                "hedgehog_role": "server-leaf",
                "device_type_extension": "dte1",
            }
        ]

        with self.assertRaises(Exception):
            ingest.apply_case(case, clean=False, prune=False, reference_mode="ensure")


class SharedFabricUtilsRedTestCase(TestCase):
    def _import_fabric_utils(self):
        try:
            return importlib.import_module("netbox_hedgehog.services._fabric_utils")
        except ModuleNotFoundError as exc:
            self.fail(
                "Missing shared helper module netbox_hedgehog.services._fabric_utils. "
                "Phase 4 must provide a single shared location for fabric-class compatibility helpers. "
                f"Original error: {exc}"
            )

    def test_legacy_frontend_maps_to_managed(self):
        utils = self._import_fabric_utils()
        self.assertEqual(utils._legacy_fabric_name_to_class("frontend"), "managed")

    def test_explicit_managed_class_with_arbitrary_name_is_managed(self):
        utils = self._import_fabric_utils()

        class DummyDevice:
            custom_field_data = {
                "hedgehog_fabric": "converged",
                "hedgehog_fabric_class": "managed",
            }

        self.assertEqual(utils._device_fabric_class(DummyDevice()), "managed")

    def test_explicit_unmanaged_class_overrides_frontend_name(self):
        utils = self._import_fabric_utils()

        class DummyDevice:
            custom_field_data = {
                "hedgehog_fabric": "frontend",
                "hedgehog_fabric_class": "unmanaged",
            }

        self.assertEqual(utils._device_fabric_class(DummyDevice()), "unmanaged")

    def test_legacy_unknown_name_maps_to_unmanaged(self):
        utils = self._import_fabric_utils()
        self.assertEqual(utils._legacy_fabric_name_to_class("legacy-mgmt"), "unmanaged")


class FabricClassExportRedTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="fabric-export-admin",
            password="fabric-export-admin",
            is_staff=True,
            is_superuser=True,
        )
        cls.manufacturer, _ = Manufacturer.objects.get_or_create(
            name="Fabric Export Mfg",
            defaults={"slug": "fabric-export-mfg"},
        )
        cls.switch_type, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.manufacturer,
            model="Fabric Export Switch",
            defaults={"slug": "fabric-export-switch"},
        )
        cls.server_type, _ = DeviceType.objects.get_or_create(
            manufacturer=cls.manufacturer,
            model="Fabric Export Server",
            defaults={"slug": "fabric-export-server"},
        )
        for name in ("E1/1", "E1/2", "eth0"):
            target = cls.switch_type if name.startswith("E1/") else cls.server_type
            InterfaceTemplate.objects.get_or_create(
                device_type=target,
                name=name,
                defaults={"type": "100gbase-x-qsfp28"},
            )
        cls.device_ext, _ = DeviceTypeExtension.objects.get_or_create(
            device_type=cls.switch_type,
            defaults={
                "mclag_capable": False,
                "hedgehog_roles": ["server-leaf"],
                "supported_breakouts": ["1x100g"],
                "native_speed": 100,
                "uplink_ports": 0,
                "hedgehog_profile_name": "fabric-export-switch",
            },
        )
        cls.site, _ = Site.objects.get_or_create(
            name="Fabric Export Site",
            defaults={"slug": "fabric-export-site"},
        )
        cls.leaf_role, _ = DeviceRole.objects.get_or_create(
            slug="fabric-export-leaf",
            defaults={"name": "Fabric Export Leaf", "color": "008000"},
        )
        cls.server_role, _ = DeviceRole.objects.get_or_create(
            slug="server",
            defaults={"name": "Server", "color": "0000ff"},
        )

    def _generated_plan(self, name: str) -> TopologyPlan:
        plan = TopologyPlan.objects.create(name=name, created_by=self.user)
        GenerationState.objects.create(
            plan=plan,
            device_count=0,
            interface_count=0,
            cable_count=0,
            snapshot={},
            status=GenerationStatusChoices.GENERATED,
        )
        return plan

    def _make_switch(self, plan: TopologyPlan, name: str, fabric_name: str, fabric_class: str) -> Device:
        return Device.objects.create(
            name=name,
            device_type=self.switch_type,
            role=self.leaf_role,
            site=self.site,
            custom_field_data={
                "hedgehog_plan_id": str(plan.pk),
                "hedgehog_class": name,
                "hedgehog_fabric": fabric_name,
                "hedgehog_fabric_class": fabric_class,
                "hedgehog_role": "server-leaf",
                "boot_mac": f"02:00:00:aa:bb:{abs(hash(name)) % 255:02x}",
            },
        )

    def _make_server(self, plan: TopologyPlan, name: str) -> Device:
        return Device.objects.create(
            name=name,
            device_type=self.server_type,
            role=self.server_role,
            site=self.site,
            custom_field_data={"hedgehog_plan_id": str(plan.pk)},
        )

    def _iface(self, device: Device, name: str) -> Interface:
        iface, _ = Interface.objects.get_or_create(
            device=device,
            name=name,
            defaults={"type": "100gbase-x-qsfp28"},
        )
        return iface

    def _cable(self, plan: TopologyPlan, iface_a: Interface, iface_b: Interface, zone: str = "server") -> None:
        from dcim.models import Cable

        cable = Cable(a_terminations=[iface_a], b_terminations=[iface_b])
        cable.custom_field_data = {
            "hedgehog_plan_id": str(plan.pk),
            "hedgehog_zone": zone,
        }
        cable.save()

    def test_generate_yaml_uses_explicit_managed_class_for_arbitrary_name(self):
        plan = self._generated_plan("Arbitrary Managed Export")
        switch = self._make_switch(plan, "converged-sw-01", "converged", "managed")
        server = self._make_server(plan, "converged-server-01")
        self._cable(plan, self._iface(server, "eth0"), self._iface(switch, "E1/1"))

        content = generate_yaml_for_plan(plan)
        self.assertIn("converged-sw-01", _switch_names_in_yaml(content))

    def test_generate_yaml_uses_explicit_unmanaged_class_over_frontend_name(self):
        plan = self._generated_plan("Explicit Unmanaged Override")
        switch = self._make_switch(plan, "frontend-oob-01", "frontend", "unmanaged")
        server = self._make_server(plan, "frontend-oob-server-01")
        self._cable(plan, self._iface(server, "eth0"), self._iface(switch, "E1/1"), zone="oob")

        content = generate_yaml_for_plan(plan)
        self.assertIn("frontend-oob-01", _server_names_in_yaml(content))
        self.assertNotIn("frontend-oob-01", _switch_names_in_yaml(content))

    def test_generate_yaml_with_no_managed_fabrics_raises_value_error(self):
        plan = self._generated_plan("No Managed Fabrics Plan")
        self._make_switch(plan, "oob-only-01", "oob-mgmt", "unmanaged")

        with self.assertRaises(ValueError):
            generate_yaml_for_plan(plan)

    def test_export_wiring_yaml_accepts_arbitrary_managed_fabric_name(self):
        plan = self._generated_plan("Arbitrary Fabric Selector")
        switch = self._make_switch(plan, "selector-sw-01", "converged", "managed")
        server = self._make_server(plan, "selector-server-01")
        self._cable(plan, self._iface(server, "eth0"), self._iface(switch, "E1/1"))

        with tempfile.TemporaryDirectory() as tmpdir:
            output = os.path.join(tmpdir, "converged.yaml")
            call_command("export_wiring_yaml", str(plan.pk), "--output", output, "--fabric", "converged")
            self.assertTrue(os.path.exists(output))

    def test_split_by_fabric_writes_discovered_managed_fabric_names(self):
        plan = self._generated_plan("Dynamic Split Fabrics")
        sw1 = self._make_switch(plan, "conv-sw-01", "converged", "managed")
        sw2 = self._make_switch(plan, "storage-sw-01", "storage-rail", "managed")
        srv1 = self._make_server(plan, "conv-server-01")
        srv2 = self._make_server(plan, "storage-server-01")
        self._cable(plan, self._iface(srv1, "eth0"), self._iface(sw1, "E1/1"))
        self._cable(plan, self._iface(srv2, "eth0"), self._iface(sw2, "E1/1"))

        with tempfile.TemporaryDirectory() as tmpdir:
            base = os.path.join(tmpdir, "dynamic")
            call_command("export_wiring_yaml", str(plan.pk), "--output", base, "--split-by-fabric")
            self.assertTrue(os.path.exists(f"{base}-converged.yaml"))
            self.assertTrue(os.path.exists(f"{base}-storage-rail.yaml"))

    def test_scoped_export_excludes_other_managed_fabric(self):
        plan = self._generated_plan("Partitioned Fabrics")
        sw_conv = self._make_switch(plan, "conv-part-sw-01", "converged", "managed")
        self._make_switch(plan, "stor-part-sw-01", "storage-rail", "managed")
        srv = self._make_server(plan, "part-server-01")
        self._cable(plan, self._iface(srv, "eth0"), self._iface(sw_conv, "E1/1"))

        content = generate_yaml_for_plan(plan, fabric="converged")
        switch_names = _switch_names_in_yaml(content)
        self.assertIn("conv-part-sw-01", switch_names)
        self.assertNotIn("stor-part-sw-01", switch_names)
