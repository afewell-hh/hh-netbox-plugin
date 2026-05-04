"""RED tests — Topology Plan YAML Contract v2 (#486).

Categories:
  V2SchemaValidationTestCase   — schema gating (apiVersion, kind, metadata, forbidden keys)
  V2IngestReferenceTestCase    — slug/composite reference resolution + missing-ref errors
  V2TestFixturesTestCase       — test_fixtures object bootstrap
  V2StatusSectionTestCase      — status block ignored on ingest, schema-allowed
  V2ContractSectionTestCase    — contract schema validation + validate_contract assertions
  V2DumpPlanStatusTestCase     — dump_plan_status command writes status to YAML file
  V1CompatRegressionTestCase   — v1 YAML still processes correctly (should PASS)
"""
from __future__ import annotations

from django.test import TestCase

from netbox_hedgehog.test_cases.exceptions import TestCaseValidationError
from netbox_hedgehog.test_cases.schema import validate_case_dict
from netbox_hedgehog.test_cases import ingest


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _v2_base(case_id="v2_test"):
    return {
        "apiVersion": "diet/v2",
        "kind": "TopologyPlan",
        "metadata": {
            "case_id": case_id,
            "name": f"V2 Test {case_id}",
            "version": 2,
            "managed_by": "yaml",
        },
        "spec": {
            "plan": {"name": f"Plan {case_id}", "status": "draft"},
            "switch_classes": [],
            "server_classes": [],
            "server_connections": [],
        },
    }


def _seed_inventory():
    """Create minimal inventory objects for v2 reference-resolution tests."""
    from dcim.models import DeviceType, Manufacturer, ModuleType
    from netbox_hedgehog.models.topology_planning import (
        BreakoutOption, DeviceTypeExtension,
    )

    mfr, _ = Manufacturer.objects.get_or_create(
        slug="v2-test-mfr", defaults={"name": "V2 Test Mfr"}
    )
    dt, _ = DeviceType.objects.get_or_create(
        slug="v2-test-switch",
        defaults={"manufacturer": mfr, "model": "V2 Test Switch"},
    )
    DeviceTypeExtension.objects.get_or_create(
        device_type=dt,
        defaults={
            "hedgehog_roles": ["server-leaf"],
            "uplink_ports": 8,
            "supported_breakouts": [],
            "native_speed": 400,
        },
    )
    srv_dt, _ = DeviceType.objects.get_or_create(
        slug="v2-test-server",
        defaults={"manufacturer": mfr, "model": "V2 Test Server"},
    )
    bo, _ = BreakoutOption.objects.get_or_create(
        breakout_id="v2-1x400g",
        defaults={"from_speed": 400, "logical_ports": 1, "logical_speed": 400},
    )
    mt, _ = ModuleType.objects.get_or_create(
        manufacturer=mfr, model="V2 Test NIC",
    )
    return mfr, dt, srv_dt, bo, mt


# ---------------------------------------------------------------------------
# S1: Schema validation
# ---------------------------------------------------------------------------

class V2SchemaValidationTestCase(TestCase):
    """T-SV-*: validate_case_dict must handle v2 document shape."""

    def test_v2_valid_minimal_passes_schema(self):
        # T-P-01 / T-SV-04: well-formed v2 YAML with empty spec lists passes
        result = validate_case_dict(_v2_base())
        self.assertIsNotNone(result)

    def test_v2_reference_data_forbidden(self):
        # T-N-01: reference_data at root in v2 → v2_forbidden_key
        case = _v2_base()
        case["reference_data"] = {"manufacturers": []}
        with self.assertRaises(TestCaseValidationError) as ctx:
            validate_case_dict(case)
        codes = [e["code"] for e in ctx.exception.errors]
        self.assertIn("v2_forbidden_key", codes, codes)

    def test_v2_requires_kind(self):
        # T-N-08: missing kind → missing_required
        case = _v2_base()
        del case["kind"]
        with self.assertRaises(TestCaseValidationError) as ctx:
            validate_case_dict(case)
        codes = [e["code"] for e in ctx.exception.errors]
        self.assertIn("missing_required", codes, codes)

    def test_v2_kind_must_be_topology_plan(self):
        case = _v2_base()
        case["kind"] = "WrongKind"
        with self.assertRaises(TestCaseValidationError) as ctx:
            validate_case_dict(case)
        codes = [e["code"] for e in ctx.exception.errors]
        self.assertIn("invalid_value", codes, codes)

    def test_v2_metadata_version_must_be_2(self):
        # T-N-09
        case = _v2_base()
        case["metadata"]["version"] = 1
        with self.assertRaises(TestCaseValidationError) as ctx:
            validate_case_dict(case)
        codes = [e["code"] for e in ctx.exception.errors]
        self.assertIn("invalid_value", codes, codes)

    def test_v2_uses_metadata_not_meta(self):
        # v2 uses metadata:; meta: alone with apiVersion is invalid
        case = _v2_base()
        case["meta"] = case.pop("metadata")
        with self.assertRaises(TestCaseValidationError) as ctx:
            validate_case_dict(case)
        self.assertTrue(len(ctx.exception.errors) > 0)

    def test_v2_spec_required(self):
        case = _v2_base()
        del case["spec"]
        with self.assertRaises(TestCaseValidationError) as ctx:
            validate_case_dict(case)
        codes = [e["code"] for e in ctx.exception.errors]
        self.assertIn("missing_required", codes, codes)

    def test_v2_status_section_allowed_not_required(self):
        # T-SV-04: status present → no error
        case = _v2_base()
        case["status"] = {
            "calculated_at": "2026-05-04T00:00:00Z",
            "switch_classes": [],
            "generation": {"status": "generated", "device_count": 0,
                           "interface_count": 0, "cable_count": 0,
                           "generated_at": "2026-05-04T00:01:00Z"},
        }
        result = validate_case_dict(case)
        self.assertIsNotNone(result)

    def test_v2_contract_section_allowed_not_required(self):
        # T-SV-05: contract present → no error
        case = _v2_base()
        case["contract"] = {"counts": {"server_classes": 0, "switch_classes": 0, "connections": 0}}
        result = validate_case_dict(case)
        self.assertIsNotNone(result)

    def test_v2_contract_counts_must_be_integers(self):
        # T-SV-03: non-integer device_count in contract.generation → invalid_type
        case = _v2_base()
        case["contract"] = {"generation": {"device_count": "not-an-int"}}
        with self.assertRaises(TestCaseValidationError) as ctx:
            validate_case_dict(case)
        codes = [e["code"] for e in ctx.exception.errors]
        self.assertIn("invalid_type", codes, codes)

    def test_v2_contract_zones_required_needs_switch_class(self):
        # T-SV-02: zones.required entry missing switch_class → missing_required
        case = _v2_base()
        case["contract"] = {"zones": {"required": [{"zone_name": "x", "zone_type": "server"}]}}
        with self.assertRaises(TestCaseValidationError) as ctx:
            validate_case_dict(case)
        codes = [e["code"] for e in ctx.exception.errors]
        self.assertIn("missing_required", codes, codes)

    def test_v2_test_fixtures_allowed(self):
        # T-SV-05: test_fixtures block present → no schema error
        case = _v2_base()
        case["test_fixtures"] = {"device_types": []}
        result = validate_case_dict(case)
        self.assertIsNotNone(result)


# ---------------------------------------------------------------------------
# S2: v2 ingest — reference resolution
# ---------------------------------------------------------------------------

class V2IngestReferenceTestCase(TestCase):
    """T-P-02 to T-P-08, T-N-02 to T-N-07: slug/composite lookup at ingest."""

    def setUp(self):
        self.mfr, self.dt, self.srv_dt, self.bo, self.mt = _seed_inventory()

    def _case_with_switch(self, device_type_slug=None):
        case = _v2_base("v2_ingest_sw")
        case["spec"]["switch_classes"] = [{
            "switch_class_id": "v2-leaf",
            "fabric_name": "backend",
            "fabric_class": "managed",
            "hedgehog_role": "server-leaf",
            "device_type": device_type_slug or "v2-test-switch",
        }]
        case["spec"]["switch_port_zones"] = [{
            "switch_class": "v2-leaf",
            "zone_name": "downlinks",
            "zone_type": "server",
            "port_spec": "1-4",
            "breakout_option": "v2-1x400g",
        }]
        return case

    def _case_with_server(self, server_dt_slug=None):
        case = _v2_base("v2_ingest_srv")
        case["spec"]["server_classes"] = [{
            "server_class_id": "v2-gpu",
            "category": "gpu",
            "quantity": 2,
            "server_device_type": server_dt_slug or "v2-test-server",
        }]
        return case

    def test_v2_ingest_resolves_device_type_by_slug(self):
        # T-P-02: device_type slug resolves DeviceType + DeviceTypeExtension
        from netbox_hedgehog.models.topology_planning import PlanSwitchClass
        case = self._case_with_switch()
        plan = ingest.apply_case(case, reference_mode="require")
        sw = PlanSwitchClass.objects.get(plan=plan, switch_class_id="v2-leaf")
        self.assertEqual(sw.device_type_extension.device_type.slug, "v2-test-switch")

    def test_v2_ingest_resolves_breakout_option_by_breakout_id(self):
        # T-P-03
        from netbox_hedgehog.models.topology_planning import SwitchPortZone
        case = self._case_with_switch()
        plan = ingest.apply_case(case, reference_mode="require")
        zone = SwitchPortZone.objects.get(switch_class__plan=plan, zone_name="downlinks")
        self.assertEqual(zone.breakout_option.breakout_id, "v2-1x400g")

    def test_v2_ingest_resolves_server_device_type_by_slug(self):
        # T-P-02 (server side)
        from netbox_hedgehog.models.topology_planning import PlanServerClass
        case = self._case_with_server()
        plan = ingest.apply_case(case, reference_mode="require")
        sc = PlanServerClass.objects.get(plan=plan, server_class_id="v2-gpu")
        self.assertEqual(sc.server_device_type.slug, "v2-test-server")

    def test_v2_ingest_resolves_nic_module_type_by_composite(self):
        # T-P-05: module_type {manufacturer, model} resolves ModuleType
        from netbox_hedgehog.models.topology_planning import PlanServerNIC
        case = self._case_with_server()
        case["spec"]["server_nics"] = [{
            "server_class": "v2-gpu",
            "nic_id": "fe",
            "module_type": {"manufacturer": "v2-test-mfr", "model": "V2 Test NIC"},
        }]
        plan = ingest.apply_case(case, reference_mode="require")
        nic = PlanServerNIC.objects.get(server_class__plan=plan, nic_id="fe")
        self.assertEqual(nic.module_type.model, "V2 Test NIC")

    def test_v2_ingest_missing_device_type_slug_raises(self):
        # T-N-02
        case = self._case_with_switch(device_type_slug="slug-does-not-exist")
        with self.assertRaises(TestCaseValidationError) as ctx:
            ingest.apply_case(case, reference_mode="require")
        codes = [e["code"] for e in ctx.exception.errors]
        self.assertIn("missing_reference", codes, codes)

    def test_v2_ingest_missing_dte_raises(self):
        # T-N-03: DeviceType exists but has no DeviceTypeExtension
        from dcim.models import DeviceType
        from netbox_hedgehog.models.topology_planning import DeviceTypeExtension
        no_dte_dt, _ = DeviceType.objects.get_or_create(
            slug="v2-no-dte-switch",
            defaults={"manufacturer": self.mfr, "model": "V2 No DTE Switch"},
        )
        DeviceTypeExtension.objects.filter(device_type=no_dte_dt).delete()
        case = self._case_with_switch(device_type_slug="v2-no-dte-switch")
        with self.assertRaises(TestCaseValidationError) as ctx:
            ingest.apply_case(case, reference_mode="require")
        codes = [e["code"] for e in ctx.exception.errors]
        self.assertIn("missing_dte", codes, codes)

    def test_v2_ingest_missing_breakout_option_raises(self):
        # T-N-04
        case = self._case_with_switch()
        case["spec"]["switch_port_zones"][0]["breakout_option"] = "nonexistent-breakout"
        with self.assertRaises(TestCaseValidationError) as ctx:
            ingest.apply_case(case, reference_mode="require")
        codes = [e["code"] for e in ctx.exception.errors]
        self.assertIn("missing_reference", codes, codes)

    def test_v2_ingest_missing_server_device_type_raises(self):
        # T-N-06
        case = self._case_with_server(server_dt_slug="nonexistent-server-slug")
        with self.assertRaises(TestCaseValidationError) as ctx:
            ingest.apply_case(case, reference_mode="require")
        codes = [e["code"] for e in ctx.exception.errors]
        self.assertIn("missing_reference", codes, codes)

    def test_v2_ingest_is_idempotent(self):
        # T-P-08
        from netbox_hedgehog.models.topology_planning import TopologyPlan
        case = self._case_with_server()
        ingest.apply_case(case, reference_mode="require")
        ingest.apply_case(case, reference_mode="require")
        self.assertEqual(TopologyPlan.objects.filter(name="Plan v2_ingest_srv").count(), 1)

    def test_v2_status_section_ignored_on_ingest(self):
        # T-P-06: status present → ignored, ingest succeeds
        case = _v2_base("v2_status_ignored")
        case["status"] = {"generation": {"status": "generated", "device_count": 999,
                                         "interface_count": 0, "cable_count": 0,
                                         "generated_at": "2026-01-01T00:00:00Z"}}
        plan = ingest.apply_case(case, reference_mode="require")
        self.assertIsNotNone(plan)

    def test_v2_contract_section_ignored_on_ingest(self):
        # T-P-07: contract present → ignored, ingest succeeds
        case = _v2_base("v2_contract_ignored")
        case["contract"] = {"counts": {"server_classes": 99}}
        plan = ingest.apply_case(case, reference_mode="require")
        self.assertIsNotNone(plan)


# ---------------------------------------------------------------------------
# S3: test_fixtures
# ---------------------------------------------------------------------------

class V2TestFixturesTestCase(TestCase):
    """T-P-09 to T-P-11: test_fixtures bootstraps test-isolation objects."""

    def _case_with_fixtures(self):
        case = _v2_base("v2_fixtures_test")
        case["test_fixtures"] = {
            "device_types": [{
                "slug": "tf-switch-unique",
                "manufacturer": "tf-mfr",
                "model": "TF Switch",
                "interface_templates": [{"name": "E1/1", "type": "800gbase-x-osfp"}],
                "device_type_extension": {
                    "hedgehog_roles": ["server-leaf"],
                    "uplink_ports": 4,
                    "native_speed": 800,
                    "supported_breakouts": [],
                },
            }],
            "breakout_options": [{
                "breakout_id": "tf-1x800g",
                "from_speed": 800,
                "logical_ports": 1,
                "logical_speed": 800,
            }],
            "module_types": [{
                "manufacturer": "tf-mfr",
                "model": "TF NIC",
            }],
        }
        case["spec"]["switch_classes"] = [{
            "switch_class_id": "tf-leaf",
            "fabric_name": "backend",
            "fabric_class": "managed",
            "hedgehog_role": "server-leaf",
            "device_type": "tf-switch-unique",
        }]
        return case

    def test_test_fixtures_creates_device_type(self):
        # T-P-09
        from dcim.models import DeviceType
        ingest.apply_case(self._case_with_fixtures(), reference_mode="require")
        self.assertTrue(DeviceType.objects.filter(slug="tf-switch-unique").exists())

    def test_test_fixtures_creates_device_type_extension(self):
        # T-P-09 (DTE side)
        from netbox_hedgehog.models.topology_planning import DeviceTypeExtension
        ingest.apply_case(self._case_with_fixtures(), reference_mode="require")
        self.assertTrue(
            DeviceTypeExtension.objects.filter(device_type__slug="tf-switch-unique").exists()
        )

    def test_test_fixtures_creates_breakout_option(self):
        # T-P-10
        from netbox_hedgehog.models.topology_planning import BreakoutOption
        ingest.apply_case(self._case_with_fixtures(), reference_mode="require")
        self.assertTrue(BreakoutOption.objects.filter(breakout_id="tf-1x800g").exists())

    def test_test_fixtures_creates_module_type(self):
        # T-P-11
        from dcim.models import ModuleType
        ingest.apply_case(self._case_with_fixtures(), reference_mode="require")
        self.assertTrue(ModuleType.objects.filter(model="TF NIC").exists())

    def test_test_fixtures_is_idempotent(self):
        # T-P-09: get_or_create semantics — second apply does not error
        ingest.apply_case(self._case_with_fixtures(), reference_mode="require")
        ingest.apply_case(self._case_with_fixtures(), reference_mode="require")


# ---------------------------------------------------------------------------
# S4: status section
# ---------------------------------------------------------------------------

class V2StatusSectionTestCase(TestCase):
    """Status block must be ignored on ingest and schema-validated if present."""

    def test_status_generation_invalid_type_rejected_by_schema(self):
        # device_count must be integer
        case = _v2_base("v2_status_schema")
        case["status"] = {"generation": {"device_count": "bad"}}
        with self.assertRaises(TestCaseValidationError) as ctx:
            validate_case_dict(case)
        codes = [e["code"] for e in ctx.exception.errors]
        self.assertIn("invalid_type", codes, codes)

    def test_status_not_written_to_db_on_ingest(self):
        # status.generation.device_count=999 must not affect GenerationState
        from netbox_hedgehog.models.topology_planning import GenerationState
        case = _v2_base("v2_status_nodb")
        case["status"] = {
            "generation": {"status": "generated", "device_count": 999,
                           "interface_count": 0, "cable_count": 0,
                           "generated_at": "2026-01-01T00:00:00Z"}
        }
        plan = ingest.apply_case(case, reference_mode="require")
        self.assertFalse(GenerationState.objects.filter(plan=plan).exists())


# ---------------------------------------------------------------------------
# S5: contract section + validate_contract
# ---------------------------------------------------------------------------

class V2ContractSectionTestCase(TestCase):
    """T-VC-*: validate_contract assertions against live DB."""

    def _build_plan_with_counts(self, case_id, num_servers=1, num_switches=1):
        """Helper: ingest a minimal plan and return it."""
        from dcim.models import DeviceType, Manufacturer
        from netbox_hedgehog.models.topology_planning import BreakoutOption, DeviceTypeExtension
        mfr, _ = Manufacturer.objects.get_or_create(
            slug="vc-mfr", defaults={"name": "VC Mfr"}
        )
        sw_dt, _ = DeviceType.objects.get_or_create(
            slug="vc-switch", defaults={"manufacturer": mfr, "model": "VC Switch"}
        )
        DeviceTypeExtension.objects.get_or_create(
            device_type=sw_dt,
            defaults={"hedgehog_roles": ["server-leaf"], "uplink_ports": 4,
                      "native_speed": 400, "supported_breakouts": []},
        )
        srv_dt, _ = DeviceType.objects.get_or_create(
            slug="vc-server", defaults={"manufacturer": mfr, "model": "VC Server"}
        )
        bo, _ = BreakoutOption.objects.get_or_create(
            breakout_id="vc-1x400g",
            defaults={"from_speed": 400, "logical_ports": 1, "logical_speed": 400},
        )
        case = _v2_base(case_id)
        case["spec"]["switch_classes"] = [
            {"switch_class_id": f"vc-leaf-{i}", "fabric_name": "backend",
             "fabric_class": "managed", "hedgehog_role": "server-leaf",
             "device_type": "vc-switch"}
            for i in range(num_switches)
        ]
        case["spec"]["server_classes"] = [
            {"server_class_id": f"vc-gpu-{i}", "category": "gpu",
             "quantity": 2, "server_device_type": "vc-server"}
            for i in range(num_servers)
        ]
        return ingest.apply_case(case, reference_mode="require")

    def _validate_contract(self, plan, contract_dict):
        from netbox_hedgehog.test_cases.assertions import validate_contract
        return validate_contract(plan, contract_dict)

    def test_validate_contract_counts_pass(self):
        # T-VC-01
        plan = self._build_plan_with_counts("vc_counts_pass", num_servers=2, num_switches=2)
        results = self._validate_contract(plan, {"counts": {"server_classes": 2, "switch_classes": 2, "connections": 0}})
        self.assertTrue(all(r.result == "pass" for r in results), results)

    def test_validate_contract_counts_fail_mismatch(self):
        # T-VC-N01
        plan = self._build_plan_with_counts("vc_counts_fail", num_servers=1, num_switches=1)
        results = self._validate_contract(plan, {"counts": {"server_classes": 99}})
        failed = [r for r in results if r.result == "fail"]
        self.assertTrue(len(failed) > 0, "Expected a failure but all passed")

    def test_validate_contract_zones_pass(self):
        # T-VC-02
        from netbox_hedgehog.models.topology_planning import BreakoutOption, SwitchPortZone
        plan = self._build_plan_with_counts("vc_zones_pass", num_switches=1)
        sw_class = plan.switch_classes.first()
        bo = BreakoutOption.objects.get(breakout_id="vc-1x400g")
        SwitchPortZone.objects.get_or_create(
            switch_class=sw_class, zone_name="downlinks",
            defaults={"zone_type": "server", "port_spec": "1-4", "breakout_option": bo},
        )
        results = self._validate_contract(plan, {
            "zones": {"required": [{"switch_class": "vc-leaf-0", "zone_name": "downlinks"}]}
        })
        self.assertTrue(all(r.result == "pass" for r in results), results)

    def test_validate_contract_zones_fail_missing(self):
        # T-VC-N02: required zone doesn't exist
        plan = self._build_plan_with_counts("vc_zones_fail", num_switches=1)
        results = self._validate_contract(plan, {
            "zones": {"required": [{"switch_class": "vc-leaf-0", "zone_name": "no-such-zone"}]}
        })
        failed = [r for r in results if r.result == "fail"]
        self.assertTrue(len(failed) > 0, "Expected a failure")

    def test_validate_contract_generation_skipped_when_no_generation_state(self):
        # T-VC-07: no GenerationState → generation assertions are skipped
        plan = self._build_plan_with_counts("vc_gen_skip", num_switches=1)
        results = self._validate_contract(plan, {"generation": {"device_count": 10}})
        skipped = [r for r in results if r.result == "skipped"]
        self.assertTrue(len(skipped) > 0, "Expected skipped assertions when no GenerationState")

    def test_validate_contract_generation_fail_mismatch(self):
        # T-VC-N05: device_count in contract doesn't match GenerationState
        from netbox_hedgehog.models.topology_planning import GenerationState
        from netbox_hedgehog.choices import GenerationStatusChoices
        plan = self._build_plan_with_counts("vc_gen_fail", num_switches=1)
        GenerationState.objects.create(
            plan=plan, device_count=5, interface_count=10, cable_count=3,
            snapshot={}, status=GenerationStatusChoices.GENERATED,
        )
        results = self._validate_contract(plan, {"generation": {"device_count": 999}})
        failed = [r for r in results if r.result == "fail"]
        self.assertTrue(len(failed) > 0, "Expected failure for device_count mismatch")

    def test_validate_contract_topology_storage_pass(self):
        # T-VC-04
        plan = self._build_plan_with_counts("vc_storage_pass", num_servers=1, num_switches=1)
        results = self._validate_contract(plan, {
            "topology": {"storage": {
                "consolidated": True,
                "switch_class_id": "vc-leaf-0",
                "server_class_id": "vc-gpu-0",
                "server_quantity": 2,
            }}
        })
        self.assertTrue(all(r.result == "pass" for r in results), results)

    def test_validate_contract_topology_storage_wrong_quantity(self):
        # T-VC-N04
        plan = self._build_plan_with_counts("vc_storage_fail", num_servers=1)
        results = self._validate_contract(plan, {
            "topology": {"storage": {
                "consolidated": True,
                "switch_class_id": "vc-leaf-0",
                "server_class_id": "vc-gpu-0",
                "server_quantity": 999,
            }}
        })
        failed = [r for r in results if r.result == "fail"]
        self.assertTrue(len(failed) > 0)


# ---------------------------------------------------------------------------
# S6: dump_plan_status command
# ---------------------------------------------------------------------------

class V2DumpPlanStatusTestCase(TestCase):
    """T-DS-*: dump_plan_status writes status block to YAML file."""

    def _make_plan_with_state(self, case_id):
        from dcim.models import DeviceType, Manufacturer
        from netbox_hedgehog.models.topology_planning import (
            BreakoutOption, DeviceTypeExtension, GenerationState, TopologyPlan,
        )
        from netbox_hedgehog.choices import GenerationStatusChoices
        mfr, _ = Manufacturer.objects.get_or_create(
            slug="ds-mfr", defaults={"name": "DS Mfr"}
        )
        sw_dt, _ = DeviceType.objects.get_or_create(
            slug="ds-switch", defaults={"manufacturer": mfr, "model": "DS Switch"}
        )
        DeviceTypeExtension.objects.get_or_create(
            device_type=sw_dt,
            defaults={"hedgehog_roles": ["server-leaf"], "uplink_ports": 4,
                      "native_speed": 400, "supported_breakouts": []},
        )
        plan = TopologyPlan.objects.create(name=f"DS Plan {case_id}", status="draft")
        plan.custom_field_data = {"managed_by": "yaml", "yaml_case_id": case_id}
        plan.save()
        GenerationState.objects.create(
            plan=plan, device_count=42, interface_count=100, cable_count=50,
            snapshot={}, status=GenerationStatusChoices.GENERATED,
        )
        return plan

    def _run_command(self, case_id, extra_args=None):
        from django.core.management import call_command
        from io import StringIO
        out = StringIO()
        args = {"case": case_id, "stdout": out}
        if extra_args:
            args.update(extra_args)
        call_command("dump_plan_status", **args)
        return out.getvalue()

    def test_dump_plan_status_writes_device_count(self):
        # T-DS-02
        import yaml
        import tempfile, os
        plan = self._make_plan_with_state("ds_write_test")
        # Write a minimal v2 YAML to a temp file and point the command at it
        case_data = _v2_base("ds_write_test")
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            import yaml as _yaml
            _yaml.dump(case_data, f)
            tmppath = f.name
        try:
            self._run_command("ds_write_test", {"file": tmppath})
            with open(tmppath) as f:
                result = yaml.safe_load(f)
            self.assertEqual(result["status"]["generation"]["device_count"], 42)
        finally:
            os.unlink(tmppath)

    def test_dump_plan_status_is_idempotent(self):
        # T-DS-03: run twice → same result
        import yaml, tempfile, os
        plan = self._make_plan_with_state("ds_idem_test")
        case_data = _v2_base("ds_idem_test")
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            import yaml as _yaml; _yaml.dump(case_data, f)
            tmppath = f.name
        try:
            self._run_command("ds_idem_test", {"file": tmppath})
            with open(tmppath) as f:
                first = f.read()
            self._run_command("ds_idem_test", {"file": tmppath})
            with open(tmppath) as f:
                second = f.read()
            self.assertEqual(first, second)
        finally:
            os.unlink(tmppath)

    def test_dump_plan_status_dry_run_does_not_modify_file(self):
        # T-DS-04
        import yaml, tempfile, os
        plan = self._make_plan_with_state("ds_dry_test")
        case_data = _v2_base("ds_dry_test")
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            import yaml as _yaml; _yaml.dump(case_data, f)
            tmppath = f.name
        try:
            original = open(tmppath).read()
            self._run_command("ds_dry_test", {"file": tmppath, "dry_run": True})
            self.assertEqual(original, open(tmppath).read())
        finally:
            os.unlink(tmppath)

    def test_dump_plan_status_fails_when_plan_not_found(self):
        # T-DS-05
        from django.core.management.base import CommandError
        with self.assertRaises(CommandError):
            self._run_command("case_id_does_not_exist")

    def test_dump_plan_status_succeeds_without_generation_state(self):
        # T-DS-06: no GenerationState → status.generation: null, exit 0
        import yaml, tempfile, os
        from netbox_hedgehog.models.topology_planning import TopologyPlan
        plan = TopologyPlan.objects.create(name="DS NoState Plan", status="draft")
        plan.custom_field_data = {"managed_by": "yaml", "yaml_case_id": "ds_nostate"}
        plan.save()
        case_data = _v2_base("ds_nostate")
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            import yaml as _yaml; _yaml.dump(case_data, f)
            tmppath = f.name
        try:
            self._run_command("ds_nostate", {"file": tmppath})
            with open(tmppath) as f:
                result = yaml.safe_load(f)
            self.assertIsNone(result.get("status", {}).get("generation"))
        finally:
            os.unlink(tmppath)


# ---------------------------------------------------------------------------
# S7: v1 compat regression (these should PASS)
# ---------------------------------------------------------------------------

class V1CompatRegressionTestCase(TestCase):
    """T-C-*: v1 YAML continues to work unchanged."""

    def _minimal_v1(self, case_id="v1_compat_min"):
        from dcim.models import DeviceType, Manufacturer
        from netbox_hedgehog.models.topology_planning import BreakoutOption, DeviceTypeExtension
        mfr, _ = Manufacturer.objects.get_or_create(
            slug="v1c-mfr", defaults={"name": "V1C Mfr"}
        )
        dt, _ = DeviceType.objects.get_or_create(
            slug="v1c-switch",
            defaults={"manufacturer": mfr, "model": "V1C Switch"},
        )
        DeviceTypeExtension.objects.get_or_create(
            device_type=dt,
            defaults={"hedgehog_roles": ["server-leaf"], "uplink_ports": 4,
                      "native_speed": 400, "supported_breakouts": []},
        )
        BreakoutOption.objects.get_or_create(
            breakout_id="v1c-1x400g",
            defaults={"from_speed": 400, "logical_ports": 1, "logical_speed": 400},
        )
        return {
            "meta": {"case_id": case_id, "name": "V1 Compat", "version": 1, "managed_by": "yaml"},
            "reference_data": {
                "manufacturers": [{"id": "m1", "name": "V1C Mfr", "slug": "v1c-mfr"}],
                "device_types": [{"id": "sw1", "manufacturer": "m1", "model": "V1C Switch",
                                   "slug": "v1c-switch"}],
                "device_type_extensions": [{"id": "dte1", "device_type": "sw1",
                                             "uplink_ports": 4, "native_speed": 400,
                                             "hedgehog_roles": ["server-leaf"],
                                             "supported_breakouts": []}],
                "breakout_options": [{"id": "bo1", "breakout_id": "v1c-1x400g",
                                       "from_speed": 400, "logical_ports": 1, "logical_speed": 400}],
                "module_types": [],
            },
            "plan": {"name": "V1 Compat Plan", "status": "draft"},
            "switch_classes": [],
            "server_classes": [],
            "server_connections": [],
        }

    def test_v1_yaml_with_reference_data_ingests(self):
        # T-C-01
        case = self._minimal_v1()
        plan = ingest.apply_case(case, reference_mode="ensure")
        self.assertIsNotNone(plan)

    def test_v1_apply_all_discovers_files(self):
        # T-C-02: runner.list_case_ids() returns known cases
        from netbox_hedgehog.test_cases.runner import list_case_ids
        ids = list_case_ids()
        self.assertIn("ux_case_128gpu_odd_ports", ids)

    def test_v1_expected_counts_helper_still_works(self):
        # T-C-03
        from netbox_hedgehog.tests.test_topology_planning.case_128gpu_helpers import (
            expected_128gpu_counts,
        )
        counts = expected_128gpu_counts()
        self.assertIn("server_classes", counts)
        self.assertIsInstance(counts["server_classes"], int)

    def test_v1_contract_helpers_still_work(self):
        # T-C-04
        from netbox_hedgehog.tests.test_topology_planning.case_128gpu_helpers import (
            contract_storage, contract_zones,
        )
        storage = contract_storage()
        self.assertIn("switch_class_id", storage)
        zones = contract_zones()
        self.assertIsInstance(zones, list)
        self.assertGreater(len(zones), 0)
