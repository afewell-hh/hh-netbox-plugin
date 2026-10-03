"""#707 executable checkout boundary, independent of the absent adapter.

A17 will supply the GREEN harness's actual artifact names. This control runs
the same checker now, against the real read-only checkout and independently
planted copies. It proves the checker, not a deployed adapter or a T3 sink.
"""
import os
import copy
import re
import shutil
import stat
import tempfile
from pathlib import Path
from unittest.mock import patch

import yaml
from django.test import SimpleTestCase

from . import reaper_adapter_red_support as support


def assert_workflow_contract(case, workflow):
    """Parse the actual Compose heredoc, not comments or a truthy :ro token."""
    steps = workflow["jobs"]["interchange-security"]["steps"]
    checkout = next(step for step in steps if step.get("name") == "Checkout plugin code")
    case.assertIs(checkout["with"].get("persist-credentials"), False)
    configure = next(step for step in steps if step.get("name") == "Configure plugin-enabled NetBox")
    match = re.search(r"(?m)^cat > docker-compose\.override\.yml << 'EOF'\n(.*?)^EOF$",
                      configure["run"], re.S)
    case.assertIsNotNone(match, "expected executable Compose override heredoc")
    service = yaml.safe_load(match.group(1))["services"]["netbox"]
    root = service["environment"]["HNP_TEST_CHECKOUT_ROOT"]
    case.assertEqual(root, "/opt/hnp-test-checkout")
    case.assertIn(f"../hh-netbox-plugin:{root}:ro", service["volumes"])
    # Duplicate mounts for the same target could override the protected one.
    case.assertEqual(sum(volume.split(":")[1] == root for volume in service["volumes"]), 1)
    case.assertIn("../hh-netbox-plugin/netbox_hedgehog:/opt/netbox/netbox/netbox_hedgehog:ro",
                  service["volumes"])


def assert_live_checkout_readonly(case, checkout):
    if "HNP_TEST_CHECKOUT_ROOT" in os.environ:
        case.assertTrue(os.statvfs(checkout).f_flag & os.ST_RDONLY,
                        "the CI checkout must be a read-only mount, not merely mode-protected")


def set_copy_readonly(root, readonly):
    # A local snapshot is permission-read-only, not claimed as a kernel mount.
    for path in [root, *root.rglob("*")]:
        path.chmod((0o555 if path.is_dir() else 0o444) if readonly
                   else (0o755 if path.is_dir() else 0o644))


class CheckoutContainmentTests(SimpleTestCase):
    def test_ci_checkout_containment_and_negative_fixtures(self):
        checkout = support.repository_checkout_root()
        assert_live_checkout_readonly(self, checkout)
        self.assertNotEqual(checkout, Path(__file__).resolve().parents[3],
                            "checkout and plugin mounts must be distinct")
        self.assertTrue((checkout / "netbox_hedgehog/tests/test_interchange/"
                         "test_checkout_containment.py").read_bytes() == Path(__file__).read_bytes(),
                        "the checkout must match the code under test")
        workflow = yaml.safe_load((checkout / ".github/workflows/interchange-security-tests.yml").read_text())
        assert_workflow_contract(self, workflow)
        inventory = support.shipped_configuration_inventory(checkout)
        self.assertGreater(len(inventory), 0)

        with tempfile.TemporaryDirectory(prefix="hh707-containment-") as temp:
            root = Path(temp)
            artifacts = root / "lane"
            artifacts.mkdir()
            for name in ("hh707-lane-runner.py", "hh707-unit-evidence.json"):
                (artifacts / name).write_text("lane-only fixture\n", encoding="utf-8")
            names = {path.name for path in artifacts.iterdir()}
            self.assertEqual(support.check_shipped_artifact_containment(names, checkout), len(inventory))

            # Copy only the selected shipped files and checkout identity markers;
            # never write to the real checkout or copy .git/config or host secrets.
            copied = root / "checkout"
            for source in [*inventory, checkout / "AGENTS.md", checkout / "netbox_hedgehog/__init__.py"]:
                destination = copied / source.relative_to(checkout)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)
            set_copy_readonly(copied, True)
            try:
                self.assertTrue(all(not stat.S_IMODE(path.stat().st_mode) & 0o222
                                    for path in [copied, *copied.rglob("*")]))
                self.assertEqual(support.check_shipped_artifact_containment(names, copied), len(inventory))
            finally:
                set_copy_readonly(copied, False)
            cases = (
                (".github/workflows/hh707-decoy.yml", "reference"),
                ("scripts/nested/hh707-decoy.sh", "reference"),
                ("compose.hh707.yml", "reference"),
                ("deployments/nested/hh707-decoy.yaml", "reference"),
                ("netbox_hedgehog/scripts/hh707-lane-runner.py", "artifact"),
                ("deployment/hh707-unit-evidence.json", "artifact"),
            )
            for relative, shape in cases:
                with self.subTest(location=relative, shape=shape):
                    target = copied / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(("run hh707-lane-runner.py\n" if shape == "reference" else "fixture\n")
                                      + "HH707_PRIVATE_PAYLOAD_SENTINEL\n",
                                      encoding="utf-8")
                    try:
                        with self.assertRaises(support.ArtifactContainmentViolation) as caught:
                            support.check_shipped_artifact_containment(names, copied)
                        self.assertNotIn("HH707_PRIVATE_PAYLOAD_SENTINEL", str(caught.exception))
                    finally:
                        target.unlink()
            self.assertEqual(support.check_shipped_artifact_containment(names, copied), len(inventory))
        # Aggregate-only evidence in the existing stderr/stdout CI artifact.
        plane = "live-read-only" if "HNP_TEST_CHECKOUT_ROOT" in os.environ else "local-read-only-copy"
        print(f"HH707_CONTAINMENT checkout={plane} workflow_contract=PASS inventory_files={len(inventory)} "
              f"clean=PASS negative_cases={len(cases)} result=PASS", flush=True)

    def test_local_contract_rejects_removed_readonly_mount(self):
        checkout = support.repository_checkout_root()
        workflow = yaml.safe_load((checkout / ".github/workflows/interchange-security-tests.yml").read_text())
        assert_workflow_contract(self, workflow)
        broken = copy.deepcopy(workflow)
        configure = next(step for step in broken["jobs"]["interchange-security"]["steps"]
                         if step.get("name") == "Configure plugin-enabled NetBox")
        configure["run"] = configure["run"].replace(
            "../hh-netbox-plugin:/opt/hnp-test-checkout:ro",
            "../hh-netbox-plugin:/opt/hnp-test-checkout")
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(AssertionError):
                assert_workflow_contract(self, broken)

    def test_ci_contract_rejects_real_writable_filesystem(self):
        with tempfile.TemporaryDirectory(prefix="hh707-writable-") as temp:
            root = Path(temp)
            with patch.dict(os.environ, {"HNP_TEST_CHECKOUT_ROOT": temp}):
                with self.assertRaises(AssertionError):
                    assert_live_checkout_readonly(self, root)

    def test_missing_checkout_and_empty_names_fail_closed(self):
        with tempfile.TemporaryDirectory(prefix="hh707-invalid-") as temp:
            with self.assertRaises(support.ShippedConfigurationUnavailable):
                support.shipped_configuration_inventory(Path(temp))
        with self.assertRaises(support.ShippedConfigurationUnavailable):
            support.check_shipped_artifact_containment(set(), support.repository_checkout_root())
