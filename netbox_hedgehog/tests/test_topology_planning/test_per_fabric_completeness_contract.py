"""
Per-fabric managed wiring completeness contract (DIET-528 Phase 3 RED).

Locks in the invariant that the canonical 128-GPU plan produces exactly two
managed-fabric artifacts (frontend, backend) with exact CRD counts, and that
each artifact is independently complete and switch-isolated.

Live count verification (2026-05-10, pk=206, branch diet-517-green):
  frontend: VLANNamespace=1 IPv4Namespace=1 SwitchGroup=4 Switch=10 Server=159 Connection=342
  backend:  VLANNamespace=1 IPv4Namespace=1 SwitchGroup=0 Switch=6  Server=32  Connection=264

RED matrix: 19 tests (T1-T17 run without hhfab; T18-T19 skip when hhfab absent).

Setup architecture:
  setUpTestData — plan creation + populate_transceiver_bays + generate_all()
                  + export_wiring_yaml, all within Django's class-level
                  savepoint (same pattern as UC128GPUExportCompletenessTestCase,
                  which runs in ~7-10 min).  YAML content is read into
                  class-level string attributes and the temp dir is cleaned up
                  via addClassCleanup.
  No setUpModule — reference data (BreakoutOptions, DeviceTypes, etc.) must
                   exist in the test DB.  Run with --keepdb after first
                   seeding via load_diet_reference_data + populate_transceiver_bays,
                   or run setup_case_128gpu_odd_ports once interactively.
                   Calling load_diet_reference_data from setUpModule caused a
                   select_for_update deadlock when concurrent test runs tried
                   to acquire the same breakoutoption row lock.
"""

import glob
import os
import shutil
import tempfile
import unittest
from io import StringIO

import yaml
from django.core.management import call_command
from django.test import TestCase, tag

from netbox_hedgehog.models.topology_planning import TopologyPlan
from netbox_hedgehog.services import hhfab

_PLAN_NAME = "UX Case 128GPU Odd Ports"
_FE_FABRIC = 'frontend'
_BE_FABRIC = 'backend'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _count_kinds(content):
    counts = {}
    for doc in yaml.safe_load_all(content):
        if isinstance(doc, dict) and 'kind' in doc:
            k = doc['kind']
            counts[k] = counts.get(k, 0) + 1
    return counts


def _names_for_kind(content, kind):
    return {
        doc['metadata']['name']
        for doc in yaml.safe_load_all(content)
        if isinstance(doc, dict) and doc.get('kind') == kind and 'metadata' in doc
    }


def _connection_switch_names(content):
    """Extract all switch names referenced by Connection CRDs (all spec types)."""
    names = set()
    for doc in yaml.safe_load_all(content):
        if not isinstance(doc, dict) or doc.get('kind') != 'Connection':
            continue
        spec = doc.get('spec', {})
        port = spec.get('unbundled', {}).get('link', {}).get('switch', {}).get('port', '')
        if port:
            names.add(port.split('/')[0])
        for link in spec.get('fabric', {}).get('links', []):
            for role in ('leaf', 'spine'):
                port = link.get(role, {}).get('port', '')
                if port:
                    names.add(port.split('/')[0])
        for conn_type in ('mclag', 'eslag'):
            for link in spec.get(conn_type, {}).get('links', []):
                port = link.get('switch', {}).get('port', '')
                if port:
                    names.add(port.split('/')[0])
    return names


# ---------------------------------------------------------------------------
# Base contract class — 17 tests, no hhfab required
# ---------------------------------------------------------------------------

@tag('slow', 'regression')
class UCCase128PerFabricContractTestCase(TestCase):
    """Per-fabric completeness contract for the canonical 128-GPU plan.

    SLOW TEST: Full device generation required (~7-10 min), runs once per
    class in setUpTestData (same pattern as UC128GPUExportCompletenessTestCase).
    Run with: python manage.py test --tag=slow --keepdb
    Skip with: python manage.py test --exclude-tag=slow
    """

    FE_FABRIC = _FE_FABRIC
    BE_FABRIC = _BE_FABRIC

    EXPECTED_FE = {
        'VLANNamespace': 1, 'IPv4Namespace': 1,
        'SwitchGroup': 4, 'Switch': 10, 'Server': 159, 'Connection': 342,
    }
    EXPECTED_BE = {
        'VLANNamespace': 1, 'IPv4Namespace': 1,
        'SwitchGroup': 0, 'Switch': 6, 'Server': 32, 'Connection': 264,
    }

    @classmethod
    def setUpTestData(cls):
        from netbox_hedgehog.services.device_generator import DeviceGenerator

        stdout = StringIO()

        # Step 1: clean slate for the plan (uses _cleanup_case_data() to handle
        # the protected FK deletion order for PlanServerClass/PlanSwitchClass).
        call_command('setup_case_128gpu_odd_ports', '--clean', stdout=stdout)
        plan = TopologyPlan.objects.get(name=_PLAN_NAME)

        # Step 3: add NIC ModuleBayTemplates now that PlanServerNIC records exist.
        call_command('populate_transceiver_bays', verbosity=0, stdout=stdout)

        # Step 4: generate devices inside the class-level savepoint.
        # Disable MPTT tree-structure updates on ModuleBay during generation to
        # avoid the O(n²) per-save tree-rebuild query.  Each ModuleBay.save()
        # normally rebuilds the MPTT tree via a seq scan of all uncommitted bays;
        # with statistics showing 0 rows the planner uses seq scan regardless of
        # indexes, making total cost O(n²) when the buffer pool is cold.
        # Disabling during generation + a single rebuild at the end is O(n log n).
        from dcim.models import ModuleBay
        with ModuleBay.objects.disable_mptt_updates():
            DeviceGenerator(plan).generate_all()
        ModuleBay.objects.rebuild()
        plan.refresh_from_db()
        gs = plan.generation_state
        if gs.status != 'generated':
            raise RuntimeError(
                f"DeviceGenerator failed: status={gs.status}, "
                f"report={gs.mismatch_report}"
            )

        # Step 5: export per-fabric artifacts to a temp dir, read into memory,
        # then schedule cleanup so the temp dir is removed after the class runs.
        tmpdir = tempfile.mkdtemp(prefix='diet532_')
        cls.addClassCleanup(shutil.rmtree, tmpdir, True)

        base = os.path.join(tmpdir, 'wiring')
        call_command(
            'export_wiring_yaml', str(plan.pk),
            '--output', base, '--split-by-fabric',
            stdout=StringIO(),
        )
        with open(f'{base}-{_FE_FABRIC}.yaml', encoding='utf-8') as f:
            cls._fe_content = f.read()
        with open(f'{base}-{_BE_FABRIC}.yaml', encoding='utf-8') as f:
            cls._be_content = f.read()
        cls._artifact_basenames = {
            os.path.basename(p) for p in glob.glob(f'{base}-*.yaml')
        }

        # Pre-compute sets used by isolation tests.
        cls._fe_switch_names = _names_for_kind(cls._fe_content, 'Switch')
        cls._be_switch_names = _names_for_kind(cls._be_content, 'Switch')
        cls._fe_sg_names = _names_for_kind(cls._fe_content, 'SwitchGroup')
        cls._be_sg_names = _names_for_kind(cls._be_content, 'SwitchGroup')
        cls._fe_conn_refs = _connection_switch_names(cls._fe_content)
        cls._be_conn_refs = _connection_switch_names(cls._be_content)

    # T1 -------------------------------------------------------------------
    def test_split_produces_exactly_two_managed_fabric_files(self):
        """T1: --split-by-fabric yields exactly two artifacts: frontend and backend."""
        expected = {f'wiring-{self.FE_FABRIC}.yaml', f'wiring-{self.BE_FABRIC}.yaml'}
        self.assertEqual(
            self._artifact_basenames, expected,
            f"Expected 2 managed-fabric artifacts {expected}; got: {self._artifact_basenames}",
        )

    # T2-T5: namespace invariants ------------------------------------------
    def test_fe_has_one_vlan_namespace(self):
        """T2: FE has exactly 1 VLANNamespace."""
        actual = _count_kinds(self._fe_content).get('VLANNamespace', 0)
        self.assertEqual(actual, self.EXPECTED_FE['VLANNamespace'],
            f"FE VLANNamespace: expected {self.EXPECTED_FE['VLANNamespace']}, got {actual}")

    def test_fe_has_one_ipv4_namespace(self):
        """T3: FE has exactly 1 IPv4Namespace."""
        actual = _count_kinds(self._fe_content).get('IPv4Namespace', 0)
        self.assertEqual(actual, self.EXPECTED_FE['IPv4Namespace'],
            f"FE IPv4Namespace: expected {self.EXPECTED_FE['IPv4Namespace']}, got {actual}")

    def test_be_has_one_vlan_namespace(self):
        """T4: BE has exactly 1 VLANNamespace."""
        actual = _count_kinds(self._be_content).get('VLANNamespace', 0)
        self.assertEqual(actual, self.EXPECTED_BE['VLANNamespace'],
            f"BE VLANNamespace: expected {self.EXPECTED_BE['VLANNamespace']}, got {actual}")

    def test_be_has_one_ipv4_namespace(self):
        """T5: BE has exactly 1 IPv4Namespace."""
        actual = _count_kinds(self._be_content).get('IPv4Namespace', 0)
        self.assertEqual(actual, self.EXPECTED_BE['IPv4Namespace'],
            f"BE IPv4Namespace: expected {self.EXPECTED_BE['IPv4Namespace']}, got {actual}")

    # T6-T7: switch counts -------------------------------------------------
    def test_fe_switch_count(self):
        """T6: FE has exactly 10 Switch CRDs (fabric=frontend)."""
        actual = _count_kinds(self._fe_content).get('Switch', 0)
        self.assertEqual(actual, self.EXPECTED_FE['Switch'],
            f"FE Switch: expected {self.EXPECTED_FE['Switch']}, got {actual} "
            f"(fabric=frontend, artifact=wiring-frontend.yaml)")

    def test_be_switch_count(self):
        """T7: BE has exactly 6 Switch CRDs (fabric=backend)."""
        actual = _count_kinds(self._be_content).get('Switch', 0)
        self.assertEqual(actual, self.EXPECTED_BE['Switch'],
            f"BE Switch: expected {self.EXPECTED_BE['Switch']}, got {actual} "
            f"(fabric=backend, artifact=wiring-backend.yaml)")

    # T8-T9: switch group counts -------------------------------------------
    def test_fe_switch_group_count(self):
        """T8: FE has exactly 4 SwitchGroup CRDs."""
        actual = _count_kinds(self._fe_content).get('SwitchGroup', 0)
        self.assertEqual(actual, self.EXPECTED_FE['SwitchGroup'],
            f"FE SwitchGroup: expected {self.EXPECTED_FE['SwitchGroup']}, got {actual} "
            f"(fabric=frontend, artifact=wiring-frontend.yaml)")

    def test_be_switch_group_count(self):
        """T9: BE has exactly 0 SwitchGroup CRDs."""
        actual = _count_kinds(self._be_content).get('SwitchGroup', 0)
        self.assertEqual(actual, self.EXPECTED_BE['SwitchGroup'],
            f"BE SwitchGroup: expected {self.EXPECTED_BE['SwitchGroup']}, got {actual} "
            f"(fabric=backend, artifact=wiring-backend.yaml)")

    # T10-T11: server counts -----------------------------------------------
    def test_fe_server_count(self):
        """T10: FE has exactly 159 Server CRDs."""
        actual = _count_kinds(self._fe_content).get('Server', 0)
        self.assertEqual(actual, self.EXPECTED_FE['Server'],
            f"FE Server: expected {self.EXPECTED_FE['Server']}, got {actual} "
            f"(fabric=frontend, artifact=wiring-frontend.yaml)")

    def test_be_server_count(self):
        """T11: BE has exactly 32 Server CRDs."""
        actual = _count_kinds(self._be_content).get('Server', 0)
        self.assertEqual(actual, self.EXPECTED_BE['Server'],
            f"BE Server: expected {self.EXPECTED_BE['Server']}, got {actual} "
            f"(fabric=backend, artifact=wiring-backend.yaml)")

    # T12-T13: connection counts -------------------------------------------
    def test_fe_connection_count(self):
        """T12: FE has exactly 342 Connection CRDs."""
        actual = _count_kinds(self._fe_content).get('Connection', 0)
        self.assertEqual(actual, self.EXPECTED_FE['Connection'],
            f"FE Connection: expected {self.EXPECTED_FE['Connection']}, got {actual} "
            f"(fabric=frontend, artifact=wiring-frontend.yaml)")

    def test_be_connection_count(self):
        """T13: BE has exactly 264 Connection CRDs."""
        actual = _count_kinds(self._be_content).get('Connection', 0)
        self.assertEqual(actual, self.EXPECTED_BE['Connection'],
            f"BE Connection: expected {self.EXPECTED_BE['Connection']}, got {actual} "
            f"(fabric=backend, artifact=wiring-backend.yaml)")

    # T14-T15: switch isolation invariants ---------------------------------
    def test_switch_names_disjoint_across_fabrics(self):
        """T14: No Switch name appears in both FE and BE artifacts."""
        overlap = self._fe_switch_names & self._be_switch_names
        self.assertEqual(overlap, set(),
            f"Switch names in both FE and BE (isolation violated): {overlap}")

    def test_switch_group_names_disjoint_across_fabrics(self):
        """T15: No SwitchGroup name appears in both FE and BE artifacts."""
        overlap = self._fe_sg_names & self._be_sg_names
        self.assertEqual(overlap, set(),
            f"SwitchGroup names in both FE and BE (isolation violated): {overlap}")

    # T16-T17: connection endpoint invariants ------------------------------
    def test_fe_connections_only_reference_fe_switches(self):
        """T16: Every Connection switch ref in FE names a FE switch."""
        foreign = self._fe_conn_refs - self._fe_switch_names
        self.assertEqual(foreign, set(),
            f"FE Connections reference non-FE switches (fabric=frontend): {foreign}")

    def test_be_connections_only_reference_be_switches(self):
        """T17: Every Connection switch ref in BE names a BE switch."""
        foreign = self._be_conn_refs - self._be_switch_names
        self.assertEqual(foreign, set(),
            f"BE Connections reference non-BE switches (fabric=backend): {foreign}")


# ---------------------------------------------------------------------------
# hhfab validation subclass — T18-T19, skips cleanly when hhfab absent
# ---------------------------------------------------------------------------

@unittest.skipUnless(hhfab.is_hhfab_available(), "hhfab not installed — skipping per-fabric hhfab validation")
class UCCase128PerFabricHHFabValidationTestCase(UCCase128PerFabricContractTestCase):
    """T18-T19: Each per-fabric artifact independently passes hhfab validate."""

    def _assert_hhfab_valid(self, content, label):
        success, stdout, stderr = hhfab.validate_yaml(content, timeout=60)
        if not success:
            self.fail(
                f"hhfab validate FAILED for {label}:\n"
                f"stdout:\n{stdout}\nstderr:\n{stderr}"
            )

    def test_fe_artifact_passes_hhfab_validate(self):
        """T18: wiring-frontend.yaml independently passes hhfab validate."""
        self._assert_hhfab_valid(self._fe_content, 'wiring-frontend.yaml')

    def test_be_artifact_passes_hhfab_validate(self):
        """T19: wiring-backend.yaml independently passes hhfab validate."""
        self._assert_hhfab_valid(self._be_content, 'wiring-backend.yaml')
