"""
Integration tests for export completeness contract (DIET-225).

Tests verify that:
- _count_kinds() helper correctly parses multi-doc YAML and counts CRDs by kind
- Export includes all expected CRD kinds for a plan with inventory
- CRD counts match actual DB inventory for switches, servers, and connections
- Truncated/partial YAML is detectable via kind count checks
- VLANNamespace and IPv4Namespace are always present (minimum guaranteed docs)

The 128GPU completeness test is tagged @slow (tagged 'slow', 'regression')
and requires a fully generated plan; it is excluded from standard CI runs.

## Invariants
- Unchanged: export command behavior, generate_yaml_for_plan() output
- Changed: test enforcement of completeness contracts per DIET-225 scope
"""

import textwrap

import yaml
from django.core.management import call_command
from django.test import TestCase, tag

from dcim.models import Device, DeviceRole, DeviceType, InterfaceTemplate, Manufacturer, Site

from netbox_hedgehog.choices import (
    AllocationStrategyChoices,
    ConnectionDistributionChoices,
    ConnectionTypeChoices,
    FabricTypeChoices,
    GenerationStatusChoices,
    HedgehogRoleChoices,
    PortZoneTypeChoices,
    ServerClassCategoryChoices,
)
from netbox_hedgehog.models.topology_planning import (
    BreakoutOption,
    DeviceTypeExtension,
    GenerationState,
    PlanServerClass,
    PlanServerConnection,
    PlanSwitchClass,
    SwitchPortZone,
    TopologyPlan,
)
from netbox_hedgehog.services.device_generator import DeviceGenerator
from netbox_hedgehog.services.yaml_generator import generate_yaml_for_plan


# ---------------------------------------------------------------------------
# Helper: count CRD kinds in a multi-doc YAML stream
# ---------------------------------------------------------------------------

def _count_kinds(yaml_content):
    """Parse a multi-doc YAML string and return {kind: count} mapping.

    Only documents that are dicts with a 'kind' key are counted.
    Separator-only documents (None) are ignored.

    Returns a dict mapping kind string -> integer count.
    """
    kinds = {}
    for doc in yaml.safe_load_all(yaml_content):
        if isinstance(doc, dict) and 'kind' in doc:
            k = doc['kind']
            kinds[k] = kinds.get(k, 0) + 1
    return kinds


# ---------------------------------------------------------------------------
# Unit tests for _count_kinds() helper
# ---------------------------------------------------------------------------

class CountKindsHelperTestCase(TestCase):
    """Verify that _count_kinds() parses multi-doc YAML correctly."""

    def test_empty_string_returns_empty(self):
        self.assertEqual(_count_kinds(''), {})

    def test_single_doc_with_kind(self):
        result = _count_kinds('kind: Switch\nmetadata:\n  name: sw1\n')
        self.assertEqual(result.get('Switch'), 1)

    def test_counts_multiple_same_kind(self):
        content = textwrap.dedent("""\
            ---
            kind: Connection
            spec: {}
            ---
            kind: Connection
            spec: {}
            ---
            kind: Connection
            spec: {}
        """)
        result = _count_kinds(content)
        self.assertEqual(result.get('Connection'), 3)

    def test_counts_mixed_kinds(self):
        content = textwrap.dedent("""\
            ---
            kind: Switch
            ---
            kind: Server
            ---
            kind: Connection
            ---
            kind: Connection
            ---
            kind: VLANNamespace
            ---
            kind: IPv4Namespace
        """)
        result = _count_kinds(content)
        self.assertEqual(result['Switch'], 1)
        self.assertEqual(result['Server'], 1)
        self.assertEqual(result['Connection'], 2)
        self.assertEqual(result['VLANNamespace'], 1)
        self.assertEqual(result['IPv4Namespace'], 1)

    def test_separator_only_docs_ignored(self):
        """Null/separator-only YAML documents do not add to counts."""
        content = textwrap.dedent("""\
            ---
            kind: Switch
            ---
            ---
            kind: Server
        """)
        result = _count_kinds(content)
        self.assertEqual(result.get('Switch'), 1)
        self.assertEqual(result.get('Server'), 1)
        self.assertNotIn(None, result)

    def test_docs_without_kind_not_counted(self):
        content = textwrap.dedent("""\
            ---
            apiVersion: v1
            metadata:
              name: no-kind
            ---
            kind: Switch
        """)
        result = _count_kinds(content)
        self.assertEqual(result.get('Switch'), 1)
        self.assertEqual(len(result), 1)


# ---------------------------------------------------------------------------
# Truncation detection regression
# ---------------------------------------------------------------------------

class TruncationDetectionTestCase(TestCase):
    """Partial/truncated YAML is detectable via kind count contract checks.

    This test does not require device generation. It uses hardcoded YAML
    strings that simulate what a truncated wiring artifact looks like
    (e.g., wd3-5-856.yaml in the repo root was truncated mid-stream).
    """

    COMPLETE_YAML = textwrap.dedent("""\
        ---
        kind: VLANNamespace
        metadata:
          name: default
        ---
        kind: IPv4Namespace
        metadata:
          name: default
        ---
        kind: Switch
        metadata:
          name: be-rail-leaf-01
        ---
        kind: Server
        metadata:
          name: gpu-server-001
        ---
        kind: Connection
        spec: {}
        ---
        kind: Connection
        spec: {}
    """)

    # Simulates truncation: Connection docs cut off mid-stream
    TRUNCATED_YAML = textwrap.dedent("""\
        ---
        kind: VLANNamespace
        metadata:
          name: default
        ---
        kind: IPv4Namespace
        metadata:
          name: default
        ---
        kind: Switch
        metadata:
          name: be-rail-leaf-01
        ---
        kind: Server
        metadata:
          name: gpu-server-001
        # Connection docs missing - truncated here
    """)

    def test_complete_yaml_has_all_required_kinds(self):
        kinds = _count_kinds(self.COMPLETE_YAML)
        self.assertIn('VLANNamespace', kinds)
        self.assertIn('IPv4Namespace', kinds)
        self.assertIn('Switch', kinds)
        self.assertIn('Server', kinds)
        self.assertIn('Connection', kinds)

    def test_truncated_yaml_missing_connections_is_detectable(self):
        """A truncated artifact missing Connection docs fails the contract."""
        complete_kinds = _count_kinds(self.COMPLETE_YAML)
        truncated_kinds = _count_kinds(self.TRUNCATED_YAML)

        expected_connections = complete_kinds.get('Connection', 0)
        actual_connections = truncated_kinds.get('Connection', 0)

        self.assertGreater(expected_connections, 0,
                           "Complete YAML should include Connection CRDs")
        self.assertEqual(actual_connections, 0,
                         "Truncated YAML should have zero Connection CRDs")
        self.assertLess(actual_connections, expected_connections,
                        "Truncated artifact has fewer Connection CRDs than expected: "
                        f"expected {expected_connections}, got {actual_connections}")

    def test_truncated_yaml_still_parses_but_fails_contract(self):
        """Truncated YAML may still be valid YAML but violates the completeness contract."""
        # A truncated file does not necessarily raise a parse error
        truncated_kinds = _count_kinds(self.TRUNCATED_YAML)
        # But the connection count is wrong (0 vs expected > 0)
        self.assertEqual(truncated_kinds.get('Connection', 0), 0,
                         "Truncated YAML parses but has zero Connection docs")
        # Namespace docs still present (truncation cut only Connection docs)
        self.assertIn('VLANNamespace', truncated_kinds)
        self.assertIn('IPv4Namespace', truncated_kinds)


# ---------------------------------------------------------------------------
# Completeness contract: small fixture with real DeviceGenerator
# ---------------------------------------------------------------------------

class ExportCompletenessContractTestCase(TestCase):
    """Integration tests: YAML export CRD counts match DB inventory.

    Uses a minimal fixture (1 managed switch + 2 servers) to verify that:
    - Switch CRD count == managed-fabric switch device count in DB
    - Server CRD count == server device count in DB
    - Connection CRDs are present (at least one)
    - VLANNamespace and IPv4Namespace are always emitted

    DeviceGenerator is called directly (not the management command) so
    this test runs in the standard test suite without the @slow tag.
    """

    @classmethod
    def setUpTestData(cls):
        manufacturer, _ = Manufacturer.objects.get_or_create(
            name='Celestica-Completeness',
            defaults={'slug': 'celestica-completeness'}
        )
        nvidia, _ = Manufacturer.objects.get_or_create(
            name='NVIDIA-Completeness',
            defaults={'slug': 'nvidia-completeness'}
        )

        # Server device type with 2 interface templates
        cls.server_type, _ = DeviceType.objects.get_or_create(
            manufacturer=manufacturer,
            model='GPU-Server-Completeness',
            defaults={'slug': 'gpu-server-completeness'}
        )
        for tpl_name in ('enp1s0f0', 'enp1s0f1'):
            InterfaceTemplate.objects.get_or_create(
                device_type=cls.server_type,
                name=tpl_name,
                defaults={'type': '200gbase-x-qsfp56'}
            )

        # Switch device type
        cls.switch_type, _ = DeviceType.objects.get_or_create(
            manufacturer=manufacturer,
            model='DS5000-Completeness',
            defaults={'slug': 'ds5000-completeness'}
        )

        cls.device_ext, _ = DeviceTypeExtension.objects.update_or_create(
            device_type=cls.switch_type,
            defaults={
                'mclag_capable': False,
                'hedgehog_roles': ['server-leaf'],
                'native_speed': 800,
                'supported_breakouts': ['1x800g', '2x400g', '4x200g'],
                'uplink_ports': 0,
                'hedgehog_profile_name': 'celestica-ds5000',
            }
        )

        cls.breakout_4x200, _ = BreakoutOption.objects.get_or_create(
            breakout_id='4x200g-completeness',
            defaults={
                'from_speed': 800,
                'logical_ports': 4,
                'logical_speed': 200,
                'optic_type': 'QSFP-DD',
            }
        )
        cls.breakout_1x800, _ = BreakoutOption.objects.get_or_create(
            breakout_id='1x800g-completeness',
            defaults={
                'from_speed': 800,
                'logical_ports': 1,
                'logical_speed': 800,
                'optic_type': 'QSFP-DD',
            }
        )

        cls.server_role, _ = DeviceRole.objects.get_or_create(
            name='Server-Completeness',
            defaults={'slug': 'server', 'color': 'aa1409'}
        )
        cls.leaf_role, _ = DeviceRole.objects.get_or_create(
            name='Leaf-Completeness',
            defaults={'slug': 'leaf', 'color': '4caf50'}
        )

        cls.site, _ = Site.objects.get_or_create(
            name='Test-Completeness-Site',
            defaults={'slug': 'test-completeness-site'}
        )

        # NIC ModuleType (required by PlanServerConnection since DIET-173)
        from dcim.models import ModuleType
        cls.nic_module_type, created = ModuleType.objects.get_or_create(
            manufacturer=nvidia,
            model='BlueField-3-Completeness',
        )
        if created:
            InterfaceTemplate.objects.create(
                module_type=cls.nic_module_type,
                name='p0',
                type='other'
            )
            InterfaceTemplate.objects.create(
                module_type=cls.nic_module_type,
                name='p1',
                type='other'
            )

        # Build the plan
        cls.plan = TopologyPlan.objects.create(
            name='Completeness Contract Test Plan',
            customer_name='Completeness Test'
        )

        cls.server_class = PlanServerClass.objects.create(
            plan=cls.plan,
            server_class_id='completeness-gpu',
            server_device_type=cls.server_type,
            category=ServerClassCategoryChoices.GPU,
            quantity=2,
            gpus_per_server=8,
        )

        cls.switch_class = PlanSwitchClass.objects.create(
            plan=cls.plan,
            switch_class_id='completeness-leaf',
            fabric=FabricTypeChoices.FRONTEND,
            hedgehog_role=HedgehogRoleChoices.SERVER_LEAF,
            device_type_extension=cls.device_ext,
            uplink_ports_per_switch=0,
            mclag_pair=False,
            calculated_quantity=1,
            override_quantity=1,
        )

        cls.server_zone = SwitchPortZone.objects.create(
            switch_class=cls.switch_class,
            zone_name='server',
            zone_type=PortZoneTypeChoices.SERVER,
            port_spec='1-48',
            breakout_option=cls.breakout_4x200,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL,
            priority=100,
        )
        SwitchPortZone.objects.create(
            switch_class=cls.switch_class,
            zone_name='uplink',
            zone_type=PortZoneTypeChoices.UPLINK,
            port_spec='49-50',
            breakout_option=cls.breakout_1x800,
            allocation_strategy=AllocationStrategyChoices.SEQUENTIAL,
            priority=200,
        )

        PlanServerConnection.objects.create(
            server_class=cls.server_class,
            connection_id='frontend',
            nic_module_type=cls.nic_module_type,
            port_index=0,
            ports_per_connection=2,
            hedgehog_conn_type=ConnectionTypeChoices.UNBUNDLED,
            distribution=ConnectionDistributionChoices.SAME_SWITCH,
            target_zone=cls.server_zone,
            speed=200,
        )

        # Run device generation to create actual NetBox inventory
        generator = DeviceGenerator(plan=cls.plan, site=cls.site)
        generator.generate_all()

    def _yaml_content(self):
        return generate_yaml_for_plan(self.plan)

    def _kinds(self):
        return _count_kinds(self._yaml_content())

    def test_namespace_docs_always_present(self):
        """VLANNamespace and IPv4Namespace are always emitted (minimum guaranteed docs)."""
        kinds = self._kinds()
        self.assertIn('VLANNamespace', kinds,
                      "VLANNamespace CRD must always be present in export")
        self.assertIn('IPv4Namespace', kinds,
                      "IPv4Namespace CRD must always be present in export")

    def test_switch_crd_count_matches_db_inventory(self):
        """Switch CRD count == managed-fabric switch device count in DB."""
        from netbox_hedgehog.choices import FabricTypeChoices
        managed_fabrics = list(FabricTypeChoices.HEDGEHOG_MANAGED_SET)
        expected = Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(self.plan.pk),
            custom_field_data__hedgehog_fabric__in=managed_fabrics,
        ).count()
        self.assertGreater(expected, 0,
                           "Fixture must have at least one managed-fabric switch device")

        kinds = self._kinds()
        self.assertEqual(kinds.get('Switch', 0), expected,
                         f"Switch CRD count must match DB managed-fabric device count "
                         f"(expected {expected}, got {kinds.get('Switch', 0)})")

    def test_server_crd_count_matches_db_inventory(self):
        """Server CRD count == server device count in DB."""
        expected = Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(self.plan.pk),
            role__slug='server',
        ).count()
        self.assertGreater(expected, 0,
                           "Fixture must have at least one server device")

        kinds = self._kinds()
        self.assertEqual(kinds.get('Server', 0), expected,
                         f"Server CRD count must match DB server device count "
                         f"(expected {expected}, got {kinds.get('Server', 0)})")

    def test_connection_crds_present(self):
        """Connection CRDs are present when inventory has cables."""
        from dcim.models import Cable
        cable_count = Cable.objects.filter(
            custom_field_data__hedgehog_plan_id=str(self.plan.pk),
        ).count()
        self.assertGreater(cable_count, 0,
                           "Fixture must have at least one cable")

        kinds = self._kinds()
        self.assertGreater(kinds.get('Connection', 0), 0,
                           "Connection CRDs must be present when inventory has cables")

    def test_no_extra_unknown_kinds(self):
        """Export only emits expected CRD kinds (no unexpected kind leakage)."""
        known_kinds = {
            'Switch', 'Server', 'Connection',
            'VLANNamespace', 'IPv4Namespace', 'SwitchGroup',
        }
        kinds = self._kinds()
        for kind in kinds:
            self.assertIn(kind, known_kinds,
                          f"Unexpected CRD kind '{kind}' in export output")

    def test_total_doc_count_is_nonzero(self):
        """Export must contain at least one document (no empty artifact)."""
        kinds = self._kinds()
        total = sum(kinds.values())
        self.assertGreater(total, 0, "Export must contain at least one CRD document")


# ---------------------------------------------------------------------------
# @slow: 128GPU completeness contract (full device generation required)
# ---------------------------------------------------------------------------

@tag('slow', 'regression')
class UC128GPUExportCompletenessTestCase(TestCase):
    """128GPU plan export satisfies the completeness contract.

    SLOW TEST: Requires full device generation (~10-15 min).
    Run with: python manage.py test --tag=slow --keepdb
    Skip with: python manage.py test --exclude-tag=slow

    Uses setup_case_128gpu_odd_ports management command to build
    the canonical 128GPU reference plan, then verifies that the
    exported YAML contains all required CRD kinds and that kind
    counts match the actual DB inventory.
    """

    PLAN_NAME = "UX Case 128GPU Odd Ports"

    @classmethod
    def setUpTestData(cls):
        from io import StringIO
        TopologyPlan.objects.filter(name=cls.PLAN_NAME).delete()
        call_command('setup_case_128gpu_odd_ports', '--clean', '--generate',
                     stdout=StringIO())
        cls.plan = TopologyPlan.objects.get(name=cls.PLAN_NAME)

    def _yaml_content(self):
        return generate_yaml_for_plan(self.plan)

    def _kinds(self):
        return _count_kinds(self._yaml_content())

    def test_128gpu_export_has_namespace_docs(self):
        """VLANNamespace and IPv4Namespace always present in 128GPU export."""
        kinds = self._kinds()
        self.assertIn('VLANNamespace', kinds)
        self.assertIn('IPv4Namespace', kinds)

    def test_128gpu_switch_crd_count_matches_db(self):
        """Switch CRD count matches managed-fabric switch inventory for 128GPU plan."""
        managed_fabrics = list(FabricTypeChoices.HEDGEHOG_MANAGED_SET)
        expected = Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(self.plan.pk),
            custom_field_data__hedgehog_fabric__in=managed_fabrics,
        ).count()
        self.assertGreater(expected, 0)

        kinds = self._kinds()
        self.assertEqual(kinds.get('Switch', 0), expected,
                         f"128GPU Switch CRD count mismatch: expected {expected}, "
                         f"got {kinds.get('Switch', 0)}")

    def test_128gpu_server_crd_count_matches_db(self):
        """Server CRD count matches server device count for 128GPU plan."""
        expected = Device.objects.filter(
            custom_field_data__hedgehog_plan_id=str(self.plan.pk),
            role__slug='server',
        ).count()
        self.assertGreater(expected, 0)

        kinds = self._kinds()
        self.assertEqual(kinds.get('Server', 0), expected,
                         f"128GPU Server CRD count mismatch: expected {expected}, "
                         f"got {kinds.get('Server', 0)}")

    def test_128gpu_connection_crds_present(self):
        """Connection CRDs are present in 128GPU export (no missing wiring)."""
        kinds = self._kinds()
        self.assertGreater(kinds.get('Connection', 0), 0,
                           "128GPU export must contain Connection CRDs")

    def test_128gpu_export_reproducible(self):
        """Two successive exports of the 128GPU plan produce identical YAML."""
        content1 = self._yaml_content()
        content2 = self._yaml_content()
        self.assertEqual(content1, content2,
                         "128GPU export must be reproducible (deterministic YAML)")
