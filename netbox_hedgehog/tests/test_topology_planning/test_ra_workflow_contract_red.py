"""
RED tests for #585: Tier 1 RA workflow artifact contract.

These tests encode the required CR-level asset contract defined in issues #581/#583
and will fail until #586 GREEN fixes the shell scripts.

Contract summary — every RA composition root must contain:
  README.md                              (out of scope here; authored manually)
  topology-map.yaml                      (case file; already works)
  connectivity-map.csv                   ← currently buried in generated/netbox/
  netbox_inventory.json                  ← currently buried in generated/netbox/
  bom.csv                                ← does not exist yet
  wiring/wiring-{fabric}.yaml            (already works)
  diagrams/hhfab/{fabric}.drawio         (already works)
  diagrams/hhfab/hhfab_validate_{f}.log  (already works)

XOC-64 managed fabrics: scale-out, soc-storage, inb-mgmt (oob-mgmt is unmanaged).

Test categories
---------------
Category 1 (3 tests, FAIL now):
    publish_ra_assets.sh does NOT yet copy the 3 new CR-level assets to the
    composition root.  These tests assert the files ARE present after publish;
    they will PASS once #586 fixes the script.

Category 2 (3 tests, FAIL now):
    verify_ra_artifacts.sh does NOT yet check for the 3 required CR-level assets.
    Currently exits 0 even when those files are absent.  These tests assert the
    script exits non-zero when each file is missing; they will PASS once #586 adds
    the missing-asset checks.

Category 3 (1 test, FAIL now):
    run_ra_pipeline.sh has no BOM export step.  This test asserts the string
    'export_plan_bom' appears in the script; it will PASS once #586 adds that step.

Category 4 (2 tests, PASS now — regression guards):
    verify_ra_artifacts.sh correctly accepts XOC-64 per-fabric wiring names and
    rejects a legacy backend-only layout that silently dropped per-fabric exports.
"""

import os
import subprocess
import tempfile
import unittest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
#
# Resolution order for SCRIPTS_DIR:
#   1. HEDGEHOG_SCRIPTS_DIR environment variable (explicit override)
#   2. Relative path from test file (works when the full repo root is mounted
#      or when tests are run directly on the host)
#   3. Known host path — works when running inside the netbox-docker container
#      on the afewell-hh dev machine, where the host filesystem is reachable
#      at /home/ubuntu/afewell-hh/hh-netbox-plugin/scripts.
#
# If none of the candidates contain all three scripts the tests are skipped
# via @unittest.skipUnless(_SCRIPTS_PRESENT, ...).

def _find_scripts_dir():
    """Return the first candidate scripts directory that contains all three scripts."""
    required = ('publish_ra_assets.sh', 'verify_ra_artifacts.sh', 'run_ra_pipeline.sh')

    candidates = []

    # 1. Environment variable override
    env_dir = os.environ.get('HEDGEHOG_SCRIPTS_DIR', '')
    if env_dir:
        candidates.append(os.path.abspath(env_dir))

    # 2. Relative path from test file (repo root → scripts/)
    rel_dir = os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'scripts')
    )
    candidates.append(rel_dir)

    # 3. Volume-mounted path inside the netbox container
    #    (docker-compose.override.yml mounts scripts/ → /opt/netbox/netbox/netbox_hedgehog_scripts)
    candidates.append('/opt/netbox/netbox/netbox_hedgehog_scripts')

    # 4. Known host path (works when tests run directly on the host, not inside the container)
    candidates.append('/home/ubuntu/afewell-hh/hh-netbox-plugin/scripts')

    for candidate in candidates:
        if os.path.isdir(candidate) and all(
            os.path.isfile(os.path.join(candidate, s)) for s in required
        ):
            return candidate

    # Return the relative path as a non-existent fallback so error messages
    # point to the expected location.
    return rel_dir


SCRIPTS_DIR = _find_scripts_dir()

PUBLISH_SCRIPT = os.path.join(SCRIPTS_DIR, 'publish_ra_assets.sh')
VERIFY_SCRIPT = os.path.join(SCRIPTS_DIR, 'verify_ra_artifacts.sh')
PIPELINE_SCRIPT = os.path.join(SCRIPTS_DIR, 'run_ra_pipeline.sh')

_SCRIPTS_PRESENT = (
    os.path.isdir(SCRIPTS_DIR)
    and os.path.isfile(PUBLISH_SCRIPT)
    and os.path.isfile(VERIFY_SCRIPT)
    and os.path.isfile(PIPELINE_SCRIPT)
)


# ---------------------------------------------------------------------------
# Helper: build a minimal valid artifact root
# ---------------------------------------------------------------------------

def _create_valid_artifact_root(tmpdir, fabric_names=('scale-out',), extra_files=None):
    """Populate *tmpdir* so that all EXISTING verify_ra_artifacts.sh checks pass.

    Creates:
      wiring/wiring-<fabric>.yaml  for every fabric in fabric_names
      hhfab/hhfab_validate_<fabric>.log  for every fabric in fabric_names
      hhfab/<fabric>.drawio  for every fabric in fabric_names

    Optional extra_files: dict of {relative_path: content_bytes} to write
    on top (e.g. to add connectivity-map.csv before verifying its absence
    drives a failure vs. its presence drives a pass).
    """
    wiring_dir = os.path.join(tmpdir, 'wiring')
    hhfab_dir = os.path.join(tmpdir, 'hhfab')
    logs_dir = os.path.join(tmpdir, 'logs')
    os.makedirs(wiring_dir, exist_ok=True)
    os.makedirs(hhfab_dir, exist_ok=True)
    os.makedirs(logs_dir, exist_ok=True)

    for fab in fabric_names:
        # Wiring YAML
        wiring_path = os.path.join(wiring_dir, f'wiring-{fab}.yaml')
        with open(wiring_path, 'wb') as f:
            f.write(b'# dummy wiring for ' + fab.encode() + b'\n')

        # hhfab validate log
        validate_log = os.path.join(hhfab_dir, f'hhfab_validate_{fab}.log')
        with open(validate_log, 'wb') as f:
            f.write(b'hhfab validate OK\n')

        # drawio diagram (verify script does not check for these but publish does)
        drawio = os.path.join(hhfab_dir, f'{fab}.drawio')
        with open(drawio, 'wb') as f:
            f.write(b'<drawio/>\n')

    if extra_files:
        for rel_path, content in extra_files.items():
            abs_path = os.path.join(tmpdir, rel_path)
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            with open(abs_path, 'wb') as f:
                f.write(content)

    return tmpdir


# ===========================================================================
# Category 1: publish_ra_assets.sh publication gap
# ===========================================================================

@unittest.skipUnless(_SCRIPTS_PRESENT, 'scripts/ directory or required scripts not found')
class PublishCRLevelAssetsTestCase(unittest.TestCase):
    """Category 1 — RED.

    publish_ra_assets.sh currently copies only wiring/ and hhfab/ contents.
    It does NOT copy connectivity-map.csv, netbox_inventory.json, or bom.csv
    to the composition root.

    These 3 tests assert that the files ARE present after running the script.
    They FAIL on current code and will PASS after #586 GREEN fixes the script.
    """

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.artifact_root = self._td.name

        # Build a valid artifact root with the 3 new source files present
        _create_valid_artifact_root(
            self.artifact_root,
            fabric_names=('scale-out',),
            extra_files={
                'connectivity-map.csv': b'device,port,peer\ndummy,E1/1,server-01\n',
                'netbox_inventory.json': b'{"devices": []}\n',
                'bom.csv': b'part,qty\nQSFP-800G,4\n',
            },
        )

        # Create a separate empty composition directory
        self._comp_td = tempfile.TemporaryDirectory()
        self.comp_dir = self._comp_td.name

        self.assertTrue(
            os.access(PUBLISH_SCRIPT, os.X_OK),
            f'publish_ra_assets.sh is not executable: {PUBLISH_SCRIPT}',
        )

    def tearDown(self):
        self._td.cleanup()
        self._comp_td.cleanup()

    def _run_publish(self):
        result = subprocess.run(
            [PUBLISH_SCRIPT,
             '--artifact-root', self.artifact_root,
             '--composition-dir', self.comp_dir],
            capture_output=True,
            text=True,
        )
        return result

    def test_publish_copies_connectivity_map_to_cr_level(self):
        """publish_ra_assets.sh must copy connectivity-map.csv to the composition root.

        RED: script does not copy this file; assertion will fail until #586 is applied.
        After #586: connectivity-map.csv should appear flat at comp_dir root.
        """
        result = self._run_publish()
        dest = os.path.join(self.comp_dir, 'connectivity-map.csv')
        self.assertTrue(
            os.path.isfile(dest),
            f'connectivity-map.csv missing from composition root after publish '
            f'(script exit={result.returncode}).\n'
            f'stdout: {result.stdout}\nstderr: {result.stderr}\n'
            f'Gap: publish_ra_assets.sh does not yet copy connectivity-map.csv '
            f'(issue #586).',
        )

    def test_publish_copies_netbox_inventory_to_cr_level(self):
        """publish_ra_assets.sh must copy netbox_inventory.json to the composition root.

        RED: script does not copy this file; assertion will fail until #586 is applied.
        After #586: netbox_inventory.json should appear flat at comp_dir root.
        """
        result = self._run_publish()
        dest = os.path.join(self.comp_dir, 'netbox_inventory.json')
        self.assertTrue(
            os.path.isfile(dest),
            f'netbox_inventory.json missing from composition root after publish '
            f'(script exit={result.returncode}).\n'
            f'stdout: {result.stdout}\nstderr: {result.stderr}\n'
            f'Gap: publish_ra_assets.sh does not yet copy netbox_inventory.json '
            f'(issue #586).',
        )

    def test_publish_copies_bom_csv_to_cr_level(self):
        """publish_ra_assets.sh must copy bom.csv to the composition root.

        RED: script does not copy this file; assertion will fail until #586 is applied.
        After #586: bom.csv should appear flat at comp_dir root.
        """
        result = self._run_publish()
        dest = os.path.join(self.comp_dir, 'bom.csv')
        self.assertTrue(
            os.path.isfile(dest),
            f'bom.csv missing from composition root after publish '
            f'(script exit={result.returncode}).\n'
            f'stdout: {result.stdout}\nstderr: {result.stderr}\n'
            f'Gap: publish_ra_assets.sh does not yet copy bom.csv '
            f'(issue #586).',
        )


# ===========================================================================
# Category 2: verify_ra_artifacts.sh verification gap
# ===========================================================================

@unittest.skipUnless(_SCRIPTS_PRESENT, 'scripts/ directory or required scripts not found')
class VerifyRequiredCRAssetsTestCase(unittest.TestCase):
    """Category 2 — RED.

    verify_ra_artifacts.sh currently checks only wiring presence, silent-drop
    regression, and hhfab log pairing.  It does NOT check for the required
    CR-level assets (bom.csv, connectivity-map.csv, netbox_inventory.json).

    Each test creates an artifact root that satisfies all EXISTING checks but
    is missing exactly one of the 3 new required files.  The tests assert the
    script exits non-zero (i.e. detects the gap).

    These tests FAIL now because the script exits 0 and will PASS after #586
    adds the missing-asset checks.
    """

    def _run_verify(self, artifact_root):
        self.assertTrue(
            os.access(VERIFY_SCRIPT, os.X_OK),
            f'verify_ra_artifacts.sh is not executable: {VERIFY_SCRIPT}',
        )
        return subprocess.run(
            [VERIFY_SCRIPT, '--artifact-root', artifact_root],
            capture_output=True,
            text=True,
        )

    def test_verify_fails_when_bom_csv_absent(self):
        """verify_ra_artifacts.sh must exit non-zero when bom.csv is absent.

        RED: script currently exits 0 even when bom.csv is missing.
        After #586: script must exit 1 and report the missing file.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_valid_artifact_root(
                tmpdir,
                fabric_names=('scale-out',),
                # connectivity-map.csv and netbox_inventory.json present; bom.csv absent
                extra_files={
                    'connectivity-map.csv': b'dummy\n',
                    'netbox_inventory.json': b'{}\n',
                },
            )
            result = self._run_verify(tmpdir)
            self.assertNotEqual(
                result.returncode, 0,
                f'verify_ra_artifacts.sh should exit non-zero when bom.csv is absent '
                f'but exited {result.returncode}.\n'
                f'stdout: {result.stdout}\nstderr: {result.stderr}\n'
                f'Gap: script does not yet check for bom.csv (issue #586).',
            )

    def test_verify_fails_when_connectivity_map_absent(self):
        """verify_ra_artifacts.sh must exit non-zero when connectivity-map.csv is absent.

        RED: script currently exits 0 even when connectivity-map.csv is missing.
        After #586: script must exit 1 and report the missing file.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_valid_artifact_root(
                tmpdir,
                fabric_names=('scale-out',),
                # bom.csv and netbox_inventory.json present; connectivity-map.csv absent
                extra_files={
                    'bom.csv': b'part,qty\n',
                    'netbox_inventory.json': b'{}\n',
                },
            )
            result = self._run_verify(tmpdir)
            self.assertNotEqual(
                result.returncode, 0,
                f'verify_ra_artifacts.sh should exit non-zero when connectivity-map.csv '
                f'is absent but exited {result.returncode}.\n'
                f'stdout: {result.stdout}\nstderr: {result.stderr}\n'
                f'Gap: script does not yet check for connectivity-map.csv (issue #586).',
            )

    def test_verify_fails_when_netbox_inventory_absent(self):
        """verify_ra_artifacts.sh must exit non-zero when netbox_inventory.json is absent.

        RED: script currently exits 0 even when netbox_inventory.json is missing.
        After #586: script must exit 1 and report the missing file.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_valid_artifact_root(
                tmpdir,
                fabric_names=('scale-out',),
                # bom.csv and connectivity-map.csv present; netbox_inventory.json absent
                extra_files={
                    'bom.csv': b'part,qty\n',
                    'connectivity-map.csv': b'dummy\n',
                },
            )
            result = self._run_verify(tmpdir)
            self.assertNotEqual(
                result.returncode, 0,
                f'verify_ra_artifacts.sh should exit non-zero when netbox_inventory.json '
                f'is absent but exited {result.returncode}.\n'
                f'stdout: {result.stdout}\nstderr: {result.stderr}\n'
                f'Gap: script does not yet check for netbox_inventory.json (issue #586).',
            )


# ===========================================================================
# Category 3: run_ra_pipeline.sh BOM export gap
# ===========================================================================

@unittest.skipUnless(_SCRIPTS_PRESENT, 'scripts/ directory or required scripts not found')
class PipelineBomExportStepTestCase(unittest.TestCase):
    """Category 3 — RED.

    run_ra_pipeline.sh has no BOM export step.  This test reads the script as
    text and asserts that 'export_plan_bom' appears in it.

    RED: the string is absent; test FAILS now.
    After #586: the pipeline adds a BOM export step and the test will PASS.
    """

    def test_pipeline_script_includes_bom_export_step(self):
        """run_ra_pipeline.sh must contain an 'export_plan_bom' management command call.

        RED: script has no BOM export step; assertion fails until #586 adds one.
        The string 'export_plan_bom' is the management command name that will be
        introduced by #586 to generate bom.csv during the pipeline run.
        """
        with open(PIPELINE_SCRIPT, 'r', encoding='utf-8') as f:
            content = f.read()

        self.assertIn(
            'export_plan_bom',
            content,
            f'run_ra_pipeline.sh does not contain an export_plan_bom step.\n'
            f'Gap: BOM export is required for CR-level bom.csv (issue #586).\n'
            f'Script path: {PIPELINE_SCRIPT}',
        )


# ===========================================================================
# Category 4: XOC-64 wiring naming contract (regression guards — PASS now)
# ===========================================================================

@unittest.skipUnless(_SCRIPTS_PRESENT, 'scripts/ directory or required scripts not found')
class Xoc64WiringNamingContractTestCase(unittest.TestCase):
    """Category 4 — regression guards for XOC-64 per-fabric wiring naming.

    These two tests verify behaviour that already works correctly (DIET-573/578).
    They should PASS now and continue to PASS after #586.

    XOC-64 managed fabrics: scale-out, soc-storage, inb-mgmt.
    oob-mgmt is unmanaged and does not produce a wiring artifact.
    """

    def _run_verify(self, artifact_root):
        self.assertTrue(
            os.access(VERIFY_SCRIPT, os.X_OK),
            f'verify_ra_artifacts.sh is not executable: {VERIFY_SCRIPT}',
        )
        return subprocess.run(
            [VERIFY_SCRIPT, '--artifact-root', artifact_root],
            capture_output=True,
            text=True,
        )

    def test_verify_accepts_xoc64_per_fabric_wiring_names(self):
        """verify_ra_artifacts.sh exits 0 for a valid XOC-64 per-fabric artifact root.

        Regression guard: the script must accept scale-out, soc-storage, and
        inb-mgmt wiring names with matching hhfab validate logs.  This locks in
        the fix from DIET-573/578 and ensures it is not accidentally reverted.
        """
        xoc64_fabrics = ('scale-out', 'soc-storage', 'inb-mgmt')
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_valid_artifact_root(tmpdir, fabric_names=xoc64_fabrics)
            result = self._run_verify(tmpdir)
            self.assertEqual(
                result.returncode, 0,
                f'verify_ra_artifacts.sh should accept XOC-64 per-fabric wiring names '
                f'(scale-out, soc-storage, inb-mgmt) but exited {result.returncode}.\n'
                f'stdout: {result.stdout}\nstderr: {result.stderr}',
            )

    def test_verify_rejects_legacy_backend_only_wiring(self):
        """verify_ra_artifacts.sh exits non-zero when scale-out was exported but is absent.

        Regression guard: simulates the old DIET-326 bug where per-fabric artifacts
        were deleted after export.  A wiring_export.log mentions scale-out but the
        wiring/ dir contains only wiring-backend.yaml.  The script must detect this
        silent-drop and exit 1.

        This locked-in check (Check 2 in verify_ra_artifacts.sh) already works;
        this test ensures it stays working after #586 modifies the script.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            wiring_dir = os.path.join(tmpdir, 'wiring')
            hhfab_dir = os.path.join(tmpdir, 'hhfab')
            logs_dir = os.path.join(tmpdir, 'logs')
            os.makedirs(wiring_dir)
            os.makedirs(hhfab_dir)
            os.makedirs(logs_dir)

            # Only the legacy backend wiring file is present
            with open(os.path.join(wiring_dir, 'wiring-backend.yaml'), 'wb') as f:
                f.write(b'# legacy backend-only wiring\n')

            # hhfab log only for backend
            with open(os.path.join(hhfab_dir, 'hhfab_validate_backend.log'), 'wb') as f:
                f.write(b'hhfab validate OK\n')

            # Export log mentions scale-out was exported (simulates silent deletion)
            with open(os.path.join(logs_dir, 'wiring_export.log'), 'w') as f:
                f.write('Exporting fabric scale-out → wiring-scale-out.yaml\n')
                f.write('Exporting fabric backend → wiring-backend.yaml\n')

            result = self._run_verify(tmpdir)
            self.assertNotEqual(
                result.returncode, 0,
                f'verify_ra_artifacts.sh should exit non-zero when scale-out appears in '
                f'wiring_export.log but wiring-scale-out.yaml is absent (DIET-326 regression).\n'
                f'stdout: {result.stdout}\nstderr: {result.stderr}',
            )
