"""Test-only containment: production code may not depend on test packages.

#672 I11c. Written to scan the ENTIRE production package rather than only the
future interchange modules, so it asserts something real today and starts
covering interchange code automatically when that code appears. A test that
would pass vacuously until the feature exists is the kind of false assurance
this suite is supposed to prevent.

Known limit, stated rather than implied: an import-edge scan proves nothing
about COPIED logic. The durable prevention for canonicalization is that the
production implementation must satisfy RFC 8785 and its published test vectors
-- a public specification, so there is nothing to copy from here (#672 N3).
"""

from __future__ import annotations

import ast
import pathlib

from django.test import SimpleTestCase

import netbox_hedgehog

PACKAGE_ROOT = pathlib.Path(netbox_hedgehog.__file__).resolve().parent
TESTS_ROOT = PACKAGE_ROOT / "tests"

#: Test-only modules that must never be reachable from production code.
TEST_ONLY_MODULES = (
    "netbox_hedgehog.tests",
    "netbox_hedgehog.tests.corpus.topology_graph",
    "netbox_hedgehog.tests.corpus.interchange_comparator",
    "netbox_hedgehog.tests.corpus.interchange_model",
)


def _production_modules():
    for path in sorted(PACKAGE_ROOT.rglob("*.py")):
        if TESTS_ROOT in path.parents or path == TESTS_ROOT:
            continue
        yield path


def _imported_names(path: pathlib.Path):
    """Yield every module name imported by a source file."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError:  # pragma: no cover - would fail elsewhere first
        return
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                # Resolve a relative import to its absolute module path.
                parts = path.relative_to(PACKAGE_ROOT.parent).with_suffix("").parts
                base = parts[:-1] if path.name != "__init__.py" else parts
                anchor = base[:len(base) - node.level + 1]
                yield ".".join([*anchor, node.module or ""]).rstrip(".")
            elif node.module:
                yield node.module


class ProductionDoesNotImportTestCodeTestCase(SimpleTestCase):

    def test_scan_covers_a_meaningful_number_of_production_modules(self):
        """Guard against the scan silently covering nothing."""
        modules = list(_production_modules())
        self.assertGreater(
            len(modules), 20,
            'the containment scan found almost no production modules, which '
            'would make every other assertion in this class vacuous')

    def test_no_production_module_imports_a_test_package(self):
        offenders = []
        for path in _production_modules():
            for name in _imported_names(path):
                if any(name == m or name.startswith(m + ".") for m in TEST_ONLY_MODULES):
                    offenders.append(
                        f"{path.relative_to(PACKAGE_ROOT)} imports {name}")
        self.assertEqual(
            offenders, [],
            'production code must not import test-only modules; T1 and the '
            'interchange comparator are evidence infrastructure, never runtime '
            f'dependencies: {offenders}')

    def test_test_only_modules_actually_live_under_tests(self):
        """The fence is meaningless if the modules migrate out of tests/."""
        for relative in ("corpus/topology_graph.py", "corpus/interchange_comparator.py",
                         "corpus/interchange_model.py"):
            with self.subTest(module=relative):
                self.assertTrue(
                    (TESTS_ROOT / relative).is_file(),
                    f'{relative} must remain under tests/')

    def test_comparator_does_not_import_t1(self):
        """The full-model comparator must not be a wrapper around the narrower
        topology representation it exists to replace (#672 B3)."""
        source = TESTS_ROOT / "corpus" / "interchange_comparator.py"
        imported = list(_imported_names(source))
        self.assertFalse(
            [name for name in imported if "topology_graph" in name],
            f'the full-model comparator must not import T1; got {imported}')
