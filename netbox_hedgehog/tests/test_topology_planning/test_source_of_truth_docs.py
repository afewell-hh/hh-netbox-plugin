"""
RED tests for DIET-563: source-of-truth documentation and bootstrap contract.

Three categories:
1. README presence  — 5 required files must exist at specified paths.
2. README content   — each file must contain governing language pinned by spec #564.
3. Pointer comments — 3 code files must reference the owning README.

Expected RED failures (pre-GREEN state):
  - All 5 presence tests (files do not yet exist)
  - All content tests are skipped until the files exist
  - All 3 pointer tests (exact reference text absent from source files)

Bootstrap inventory assertions live in test_reference_data_bootstrap.py
(BootstrapInventoryContractTestCase) and are mostly green regression guards.
"""
from pathlib import Path

from django.test import SimpleTestCase


# netbox_hedgehog/ package root — three levels up from this file:
#   test_topology_planning/ -> tests/ -> netbox_hedgehog/
PLUGIN_ROOT = Path(__file__).resolve().parents[2]


class ReadmePresenceTestCase(SimpleTestCase):
    """Fail if any of the 5 required README files are missing."""

    def _assert_exists(self, rel_path):
        p = PLUGIN_ROOT / rel_path
        self.assertTrue(p.exists(), f"Missing required README: {p}")

    def test_plugin_root_readme_exists(self):
        self._assert_exists("README.md")

    def test_fabric_profiles_readme_exists(self):
        self._assert_exists("fabric_profiles/README.md")

    def test_management_commands_readme_exists(self):
        self._assert_exists("management/commands/README.md")

    def test_migrations_readme_exists(self):
        self._assert_exists("migrations/README.md")

    def test_test_topology_planning_readme_exists(self):
        self._assert_exists("tests/test_topology_planning/README.md")


class ReadmeContentContractTestCase(SimpleTestCase):
    """
    Each README must contain the governing language pinned by spec #564.

    Tests skip when the file is absent so presence failures (above) are the
    only noise in RED state; content failures surface once the file exists.
    """

    def _read(self, rel_path):
        p = PLUGIN_ROOT / rel_path
        if not p.exists():
            self.skipTest(f"README not yet present — checked by ReadmePresenceTestCase: {p}")
        return p.read_text()

    # --- netbox_hedgehog/README.md ---

    def test_plugin_root_readme_has_bootstrap_path_section(self):
        text = self._read("README.md")
        self.assertIn("Bootstrap Path", text,
                      "netbox_hedgehog/README.md must contain a 'Bootstrap Path' section")

    def test_plugin_root_readme_contains_canonical_command(self):
        text = self._read("README.md")
        self.assertIn(
            "load_diet_reference_data",
            text,
            "netbox_hedgehog/README.md must include the canonical bootstrap command",
        )

    # --- netbox_hedgehog/fabric_profiles/README.md ---

    def test_fabric_profiles_readme_has_ownership_section(self):
        text = self._read("fabric_profiles/README.md")
        self.assertIn("Ownership", text,
                      "fabric_profiles/README.md must contain an 'Ownership' section")

    def test_fabric_profiles_readme_forbids_fabric_ref_import(self):
        text = self._read("fabric_profiles/README.md")
        self.assertIn(
            "--fabric-ref",
            text,
            "fabric_profiles/README.md must document that --fabric-ref profiles do not belong here",
        )

    # --- netbox_hedgehog/management/commands/README.md ---

    def test_management_commands_readme_has_taxonomy_section(self):
        text = self._read("management/commands/README.md")
        self.assertIn("Command Taxonomy", text,
                      "management/commands/README.md must contain a 'Command Taxonomy' section")

    def test_management_commands_readme_names_canonical_command(self):
        text = self._read("management/commands/README.md")
        self.assertIn(
            "load_diet_reference_data",
            text,
            "management/commands/README.md must name load_diet_reference_data as canonical bootstrap path",
        )

    def test_management_commands_readme_marks_deprecated_command(self):
        text = self._read("management/commands/README.md")
        self.assertIn(
            "seed_diet_device_types",
            text,
            "management/commands/README.md must mark seed_diet_device_types as deprecated",
        )

    # --- netbox_hedgehog/migrations/README.md ---

    def test_migrations_readme_has_scope_section(self):
        text = self._read("migrations/README.md")
        self.assertIn("Scope", text,
                      "migrations/README.md must contain a 'Scope' section")

    def test_migrations_readme_forbids_seed_data(self):
        text = self._read("migrations/README.md")
        has_rule = any(phrase in text for phrase in ["seed data", "reference data", "DeviceType"])
        self.assertTrue(
            has_rule,
            "migrations/README.md must document that seed data / DeviceType creation does not belong in migrations",
        )

    # --- netbox_hedgehog/tests/test_topology_planning/README.md ---

    def test_test_topology_planning_readme_has_bootstrap_contract_section(self):
        text = self._read("tests/test_topology_planning/README.md")
        self.assertIn("Bootstrap Contract", text,
                      "tests/test_topology_planning/README.md must contain a 'Bootstrap Contract' section")

    def test_test_topology_planning_readme_names_contract_test_class(self):
        text = self._read("tests/test_topology_planning/README.md")
        self.assertIn(
            "BootstrapInventoryContractTestCase",
            text,
            "tests/test_topology_planning/README.md must reference BootstrapInventoryContractTestCase",
        )


class PointerDocstringTestCase(SimpleTestCase):
    """
    Three source files must contain pointer comments linking to the owning README.

    Spec #564 exact pointer text:
      load_diet_reference_data.py: reference to management/commands/README.md
      seed_catalog.py:             reference to fabric_profiles/README.md
      seed_diet_device_types.py:   reference to management/commands/README.md
    """

    def _read_source(self, rel_path):
        p = PLUGIN_ROOT / rel_path
        self.assertTrue(p.exists(), f"Source file not found: {p}")
        return p.read_text()

    def test_load_diet_reference_data_has_readme_pointer(self):
        """load_diet_reference_data.py must reference management/commands/README.md."""
        text = self._read_source("management/commands/load_diet_reference_data.py")
        self.assertIn(
            "management/commands/README.md",
            text,
            "load_diet_reference_data.py must contain a pointer to management/commands/README.md "
            "(spec: '# Canonical bootstrap command. See management/commands/README.md ...')",
        )

    def test_seed_catalog_has_readme_pointer(self):
        """seed_catalog.py must reference fabric_profiles/README.md."""
        text = self._read_source("seed_catalog.py")
        self.assertIn(
            "fabric_profiles/README.md",
            text,
            "seed_catalog.py must contain a pointer to fabric_profiles/README.md "
            "(spec: '# Repo-owned static inventory only. For ownership rules see fabric_profiles/README.md.')",
        )

    def test_seed_diet_device_types_has_readme_pointer(self):
        """seed_diet_device_types.py must reference management/commands/README.md."""
        text = self._read_source("management/commands/seed_diet_device_types.py")
        self.assertIn(
            "management/commands/README.md",
            text,
            "seed_diet_device_types.py must contain a pointer to management/commands/README.md",
        )
