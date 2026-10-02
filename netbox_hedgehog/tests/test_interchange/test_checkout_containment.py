"""#707 executable checkout boundary, independent of the absent adapter.

A17 will supply the GREEN harness's actual artifact names. This control runs
the same checker now, against the real read-only checkout and independently
planted copies. It proves the checker, not a deployed adapter or a T3 sink.
"""
import os
import shutil
import tempfile
from pathlib import Path

import yaml
from django.test import SimpleTestCase

from . import reaper_adapter_red_support as support


class CheckoutContainmentTests(SimpleTestCase):
    def test_ci_checkout_containment_and_negative_fixtures(self):
        checkout = support.repository_checkout_root()
        self.assertTrue(os.statvfs(checkout).f_flag & os.ST_RDONLY,
                        "the CI checkout must be a read-only mount, not merely mode-protected")
        self.assertNotEqual(checkout, Path(__file__).resolve().parents[3],
                            "checkout and plugin mounts must be distinct")
        self.assertTrue((checkout / "netbox_hedgehog/tests/test_interchange/"
                         "test_checkout_containment.py").read_bytes() == Path(__file__).read_bytes(),
                        "the checkout must match the code under test")
        workflow = yaml.safe_load((checkout / ".github/workflows/interchange-security-tests.yml").read_text())
        checkout_step = next(step for step in workflow["jobs"]["interchange-security"]["steps"]
                             if step.get("name") == "Checkout plugin code")
        self.assertIs(checkout_step["with"].get("persist-credentials"), False,
                      "the mounted checkout must not persist CI authentication headers")
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
            self.assertEqual(support.check_shipped_artifact_containment(names, copied), len(inventory))
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
        print(f"HH707_CONTAINMENT checkout=explicit-read-only inventory_files={len(inventory)} "
              f"clean=PASS negative_cases={len(cases)} result=PASS", flush=True)

    def test_missing_checkout_and_empty_names_fail_closed(self):
        with tempfile.TemporaryDirectory(prefix="hh707-invalid-") as temp:
            with self.assertRaises(support.ShippedConfigurationUnavailable):
                support.shipped_configuration_inventory(Path(temp))
        with self.assertRaises(support.ShippedConfigurationUnavailable):
            support.check_shipped_artifact_containment(set(), support.repository_checkout_root())
