"""#719 independent inventory controls: never gated by B1a setup.

All candidate mutations act on actual discovered classes/methods or their
declaration. The immutable source/requirement baseline remains separate.
"""

import ast
from django.test import SimpleTestCase

from . import safety_g1_support as S


class IndependentSafetyInventory(SimpleTestCase):
    def test_reviewed_bytes_and_exact_four_seven_requirements(self):
        for name in S.SOURCE_HASHES:
            S.source_bytes(name)  # rejects any unreviewed fixture-source change
        tree = ast.parse(S.source_bytes("test_containment_prover_safety.py"))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef)
                   and n.name == S.ORIGINAL_CLASS)
        methods = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)
                   and n.name.startswith("test_")}
        self.assertEqual(set(methods), {m for _, m, _ in S.ROWS})
        for _, name, obligation in S.ROWS:
            reads_evidence = any(isinstance(n, ast.Attribute) and n.attr == "b1a"
                                 and isinstance(n.value, ast.Name) and n.value.id == "self"
                                 for n in ast.walk(methods[name]))
            self.assertEqual(reads_evidence, obligation == "b1a", name)
        self.assertEqual(sum(kind == "source" for _, _, kind in S.ROWS), 4)
        self.assertEqual(sum(kind == "b1a" for _, _, kind in S.ROWS), 7)

    def test_positive_model_preserves_original_callables_and_mapping(self):
        context, report = S.invoke_probe(partition_model=True)
        S.validate_inventory(S.declaration(), report["discovered"])
        S.validate_inventory(list(reversed(S.declaration())),
                             list(reversed(report["discovered"])))
        S.reconcile(context, report, partitioned=True)
        self.assertEqual(report["ran"], 11)

    def test_old_to_new_mapping_has_unique_stable_requirements(self):
        rows = S.declaration()
        self.assertEqual(len({r["requirement"] for r in rows}), 11)
        self.assertEqual(len({r["old"] for r in rows}), 11)
        self.assertEqual(len({r["new"] for r in rows}), 11)
        self.assertTrue(all(f".{S.ORIGINAL_CLASS}." in r["old"] for r in rows))

    def test_deleted_class_is_detected_outside_its_setup(self):
        _, report = S.invoke_probe(partition_model=True, mutation="drop-evidence-class")
        self.assertEqual(len(report["discovered"]), 4)
        self.assertTrue(report["successful"])  # the dangerous false-green candidate
        with self.assertRaisesRegex(AssertionError, "discovery/mapping mismatch"):
            S.validate_inventory(S.declaration(), report["discovered"])

    def test_renames_moves_and_load_tests_suppression_are_rejected(self):
        for mutation in ("rename-evidence-class", "rename-method", "move-across-gate",
                         "undiscover-evidence"):
            with self.subTest(mutation=mutation):
                _, report = S.invoke_probe(partition_model=True, mutation=mutation)
                with self.assertRaisesRegex(AssertionError, "discovery/mapping mismatch"):
                    S.validate_inventory(S.declaration(), report["discovered"])

    def test_coordinated_declaration_and_class_deletion_cannot_shrink_baseline(self):
        _, report = S.invoke_probe(partition_model=True, mutation="drop-evidence-class")
        reduced = [r for r in S.declaration() if r["obligation"] == "source"]
        self.assertEqual({r["new"] for r in reduced}, set(report["discovered"]))
        with self.assertRaisesRegex(AssertionError, "reviewed baseline"):
            S.validate_inventory(reduced, report["discovered"])

    def test_duplicate_binding_and_extra_discovery_fail_bidirectionally(self):
        _, report = S.invoke_probe(partition_model=True)
        rows = S.declaration()
        for candidate in (rows + [rows[0]], rows[:-1],
                          [dict(r, obligation="source") for r in rows]):
            with self.subTest(candidate=candidate):
                with self.assertRaisesRegex(AssertionError, "reviewed baseline"):
                    S.validate_inventory(candidate, report["discovered"])
        for discovered in (report["discovered"] + [report["discovered"][0]],
                           report["discovered"] + ["unmapped.Extra.test_added"]):
            with self.subTest(discovered=discovered):
                with self.assertRaises(AssertionError):
                    S.validate_inventory(rows, discovered)

    def test_restore_shared_setup_gate_loses_four_real_bodies(self):
        # Reverting the positive model to the original shared gate is the
        # actual reviewed defect, not an injected empty observation list.
        context, report = S.invoke_probe(evidence="missing")
        S.reconcile(context, report, partitioned=False, missing=True)
        self.assertEqual(report["ran"], 0)
        self.assertEqual(report["entries"], [])
        with self.assertRaisesRegex(AssertionError, "undiscovered/extra/duplicate"):
            S.reconcile(context, report, partitioned=True, missing=True)

