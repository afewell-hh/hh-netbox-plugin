"""RED core YAML/JSON interchange contract (#673, rows I1-I14/I17/I18/I26/I30).

Every test here is RED because `netbox_hedgehog.interchange` does not exist.
None of them is satisfied by weakening an invariant, skipping a path, mocking
the only real path, or treating T1 as a product schema.
"""

from __future__ import annotations

import copy
import json
import pathlib

from django.test import SimpleTestCase, TestCase

from netbox_hedgehog.tests.corpus.interchange_comparator import compare_interchange
from netbox_hedgehog.tests.corpus.interchange_model import (
    BINDING_ALGORITHM,
    RestrictedProfileError,
    canonicalize,
    content_integrity_digest,
)
from netbox_hedgehog.tests.test_interchange import fixtures
from netbox_hedgehog.tests.test_interchange._support import require_interchange

import netbox_hedgehog

CASE_DIR = pathlib.Path(netbox_hedgehog.__file__).resolve().parent / "test_cases"


class RestrictedProfileTestCase(SimpleTestCase):
    """I1 support: the profile itself is test-only infrastructure and GREEN.

    These protect the number hazard that would otherwise surface as spurious
    content-integrity mismatches between YAML and JSON encodings of the same
    catalog, rather than as an obvious bug.
    """

    def test_canonical_form_sorts_keys_and_strips_whitespace(self):
        self.assertEqual(canonicalize({"b": 1, "a": 2}), b'{"a":2,"b":1}')

    def test_canonical_form_preserves_array_order(self):
        self.assertEqual(canonicalize({"a": [3, 1, 2]}), b'{"a":[3,1,2]}')

    def test_key_sort_is_by_code_unit_for_non_ascii(self):
        self.assertEqual(canonicalize({"é": 1, "a": 2}), '{"a":2,"é":1}'.encode())

    def test_floats_are_rejected_not_rendered(self):
        with self.assertRaises(RestrictedProfileError):
            canonicalize({"ratio": 1.5})

    def test_integers_beyond_exact_range_are_rejected(self):
        with self.assertRaises(RestrictedProfileError):
            canonicalize({"serial": 2 ** 53})

    def test_non_bmp_key_is_rejected(self):
        with self.assertRaises(RestrictedProfileError):
            canonicalize({"\U0001F600": 1})

    def test_digest_is_stable_across_equivalent_key_order(self):
        self.assertEqual(
            content_integrity_digest({"a": 1, "b": 2}),
            content_integrity_digest({"b": 2, "a": 1}))


class DecodeContractTestCase(TestCase):
    """I1, I1a, I3, I4, I5, I6 - decoding one semantic model from two formats."""

    def test_i1_yaml_and_json_decode_to_the_same_semantic_model(self):
        decode = require_interchange().decode_document
        document = fixtures.valid_bundle()
        from_json = decode(fixtures.to_json(document))
        from_yaml = decode(fixtures.to_yaml(document))
        outcome = compare_interchange(from_json, from_yaml)
        self.assertTrue(outcome.full_model_equal, outcome.describe())

    def test_i1a_transport_metadata_does_not_decide_format(self):
        """Filename, MIME type, and request origin are deliberately wrong."""
        decode = require_interchange().decode_document
        document = fixtures.valid_bundle()
        decoded = decode(
            fixtures.to_json(document), media_type="application/x-yaml",
            filename="bundle.yaml")
        self.assertTrue(
            compare_interchange(decoded, document).full_model_equal,
            'classification must follow content, not misleading transport metadata')

    def test_i3_missing_envelope_fields_are_source_located(self):
        decode = require_interchange().decode_document
        for field in ("apiVersion", "kind", "schemaVersion", "identity"):
            with self.subTest(field=field):
                document = fixtures.valid_bundle()
                document["objects"][1].pop(field)
                with self.assertRaises(Exception) as caught:
                    decode(fixtures.to_json(document))
                self.assertTrue(
                    getattr(caught.exception, "source_location", None),
                    f'missing {field} must report a source location')

    def test_i4_unknown_core_field_is_rejected_not_preserved(self):
        decode = require_interchange().decode_document
        document = fixtures.valid_bundle()
        document["objects"][1]["invented"] = "value"
        with self.assertRaises(Exception):
            decode(fixtures.to_json(document))

    def test_i5_unregistered_extension_namespace_is_rejected(self):
        """Accepted policy: no third-party namespace is enabled by default, and
        unknown extensions are neither preserved opaquely nor ignored."""
        decode = require_interchange().decode_document
        document = fixtures.valid_bundle()
        document["objects"][1]["extensions"] = {"com.example.ext/v1": {"a": 1}}
        with self.assertRaises(Exception):
            decode(fixtures.to_json(document))

    def test_i6_duplicate_mapping_key_is_rejected(self):
        decode = require_interchange().decode_document
        raw = '{"apiVersion":"aid.hedgehog.com/v1","kind":"Bundle",' \
              '"schemaVersion":"1.0","objects":[],"objects":[]}'
        with self.assertRaises(Exception):
            decode(raw)

    def test_i6_display_name_identity_is_rejected(self):
        decode = require_interchange().decode_document
        document = fixtures.valid_bundle()
        document["objects"][1]["identity"] = {"name": "XOC-64 Mesh"}
        with self.assertRaises(Exception):
            decode(fixtures.to_json(document))

    def test_i6_duplicate_identity_in_declared_scope_is_rejected(self):
        decode = require_interchange().decode_document
        document = fixtures.valid_bundle()
        document["objects"].append(copy.deepcopy(document["objects"][1]))
        with self.assertRaises(Exception):
            decode(fixtures.to_json(document))

    def test_i6_same_local_slug_under_distinct_parents_is_valid(self):
        """The accepted identity decision makes reuse valid across scopes, so
        the duplicate rule must not over-fire."""
        decode = require_interchange().decode_document
        first = fixtures.design_revision("plan-a")
        second = fixtures.design_revision("plan-b")
        decoded = decode(fixtures.to_json(fixtures.bundle(first, second)))
        self.assertIsNotNone(decoded)

    def test_i6_unsafe_numeric_is_rejected(self):
        decode = require_interchange().decode_document
        document = fixtures.valid_bundle()
        document["objects"][1]["topology"]["fabrics"][0]["switchClasses"][0][
            "quantity"] = 2 ** 53
        with self.assertRaises(Exception):
            decode(json.dumps(document))


class CatalogReferenceTestCase(TestCase):
    """I7, I8, I8a - explicit catalog references and content integrity."""

    def test_i7_topology_without_an_explicit_catalog_version_cannot_import(self):
        """Must fail even though a matching current NetBox catalog object
        exists; ambient resolution is the failure this row exists for."""
        module = require_interchange()
        document = fixtures.valid_bundle()
        document["objects"][1]["catalogRefs"] = []
        with self.assertRaises(Exception):
            module.import_bundle(module.decode_document(fixtures.to_json(document)),
                                 user=None)

    def test_i8_unresolvable_catalog_reference_fails(self):
        module = require_interchange()
        document = fixtures.valid_bundle()
        document["objects"] = [document["objects"][1]]
        document["objects"][0]["catalogRefs"][0]["identity"]["slug"] = "absent"
        with self.assertRaises(Exception):
            module.import_bundle(module.decode_document(fixtures.to_json(document)),
                                 user=None)

    def test_i8a_matching_version_with_mismatched_binding_is_rejected(self):
        """Right identity, right version, different content. Without this the
        no-ambient-catalog guarantee re-enters through mutable published
        versions."""
        module = require_interchange()
        document = fixtures.valid_bundle()
        document["objects"][1]["catalogRefs"][0]["contentIntegrity"]["digest"] = "0" * 64
        with self.assertRaises(Exception):
            module.import_bundle(module.decode_document(fixtures.to_json(document)),
                                 user=None)

    def test_i8a_same_version_alone_is_never_proof_of_equal_content(self):
        module = require_interchange()
        document = fixtures.valid_bundle()
        document["objects"][1]["catalogRefs"][0].pop("contentIntegrity")
        with self.assertRaises(Exception):
            module.import_bundle(module.decode_document(fixtures.to_json(document)),
                                 user=None)

    def test_i8a_unknown_binding_algorithm_is_not_silently_equivalent(self):
        module = require_interchange()
        document = fixtures.valid_bundle()
        document["objects"][1]["catalogRefs"][0]["contentIntegrity"]["algorithm"] = \
            "aid-jcs-rfc8785-sha256-v2"
        with self.assertRaises(Exception):
            module.import_bundle(module.decode_document(fixtures.to_json(document)),
                                 user=None)

    def test_i8a_binding_uses_the_accepted_algorithm_identifier(self):
        self.assertEqual(BINDING_ALGORITHM, "aid-jcs-rfc8785-sha256-v1")


class RoundTripTestCase(TestCase):
    """I11a, I11b - topology-subset and full-model comparison, kept separate."""

    def test_i11a_topology_subset_survives_the_round_trip(self):
        """Compares actual topology facts through T1, which is used purely as a
        test helper. Asserting only that an export is non-None proved nothing."""
        from netbox_hedgehog.tests.corpus.topology_graph import (
            ComparisonDisposition, compare_graphs)
        from netbox_hedgehog.tests.test_interchange.t1_adapter import to_topology_graph
        module = require_interchange()
        document = fixtures.valid_bundle()
        result = module.import_bundle(
            module.decode_document(fixtures.to_json(document)), user=None)
        exported = module.export_revision(result.design_revision, fmt="yaml")
        report = compare_graphs(
            to_topology_graph(document, case_id="fixture"),
            to_topology_graph(module.decode_document(exported), case_id="fixture"))
        self.assertEqual(report.disposition, ComparisonDisposition.EQUIVALENCE_ELIGIBLE,
                         f'topology subset changed across the round trip: '
                         f'{dict(report.differences)}')

    def test_i11a_topology_perturbation_is_detected_by_the_subset_comparison(self):
        """Control: the subset comparison must be able to fail, or the row above
        proves nothing."""
        from netbox_hedgehog.tests.corpus.topology_graph import (
            ComparisonDisposition, compare_graphs)
        from netbox_hedgehog.tests.test_interchange.t1_adapter import to_topology_graph
        require_interchange()
        perturbed = fixtures.valid_bundle()
        fixtures._p_topology_edge(perturbed)
        report = compare_graphs(
            to_topology_graph(fixtures.valid_bundle(), case_id="fixture"),
            to_topology_graph(perturbed, case_id="fixture"))
        self.assertEqual(report.disposition, ComparisonDisposition.DIAGNOSTIC)

    def test_i11b_full_model_round_trip_preserves_every_claimed_fact_class(self):
        """YAML -> JSON and JSON -> YAML, judged by the full-model comparator
        rather than the topology subset, so a dropped catalog pin cannot pass."""
        module = require_interchange()
        document = fixtures.valid_bundle()
        for source_fmt, target_fmt in (("json", "yaml"), ("yaml", "json")):
            with self.subTest(source=source_fmt, target=target_fmt):
                text = (fixtures.to_json(document) if source_fmt == "json"
                        else fixtures.to_yaml(document))
                result = module.import_bundle(module.decode_document(text), user=None)
                exported = module.export_revision(result.design_revision, fmt=target_fmt)
                outcome = compare_interchange(module.decode_document(exported), document)
                self.assertTrue(outcome.full_model_equal, outcome.describe())


class DeterminismAndProvenanceTestCase(TestCase):
    """I12, I13, I14."""

    def _exported_digest(self, module, document):
        result = module.import_bundle(
            module.decode_document(fixtures.to_json(document)), user=None)
        return content_integrity_digest(
            json.loads(module.export_revision(result.design_revision, fmt="json")))

    def test_i12_export_is_deterministic_under_specified_perturbations(self):
        """Member reversal alone does not perturb database or query order, so
        each named perturbation is exercised separately."""
        module = require_interchange()
        baseline = self._exported_digest(module, fixtures.valid_bundle())

        reversed_members = fixtures.valid_bundle()
        reversed_members["objects"].reverse()

        interleaved = fixtures.valid_bundle()
        # Unrelated rows created between the members shift primary keys, so a
        # PK-ordered export changes while a deterministic one does not.
        module.create_unrelated_rows(count=3)

        for label, document in (("reversed members", reversed_members),
                                ("interleaved unrelated rows", interleaved)):
            with self.subTest(perturbation=label):
                self.assertEqual(self._exported_digest(module, document), baseline)

    def test_i12_export_is_deterministic_across_independent_runs(self):
        """A second run in a separate process/connection must agree, which
        two exports in one process cannot demonstrate."""
        module = require_interchange()
        baseline = self._exported_digest(module, fixtures.valid_bundle())
        self.assertEqual(
            module.export_digest_from_independent_run(fixtures.valid_bundle()),
            baseline)

    def test_i13_export_provenance_names_required_elements(self):
        module = require_interchange()
        result = module.import_bundle(
            module.decode_document(fixtures.to_json(fixtures.valid_bundle())), user=None)
        exported = json.loads(module.export_revision(result.design_revision, fmt="json"))
        provenance = exported["objects"][1]["provenance"]
        for element in (
            "sourceRevision", "schemaVersion", "apiVersion", "exporter",
            "exporterRevision", "maturity", "artifactKind",
            "catalogContentIntegrity", "canonicalizationAlgorithm",
            "assumptions", "exceptions",
        ):
            with self.subTest(element=element):
                self.assertIn(
                    element, provenance,
                    f'provenance must identify {element}; an incomplete envelope '
                    f'cannot support a maturity or equivalence claim')
        self.assertEqual(provenance.get("canonicalizationAlgorithm"), BINDING_ALGORITHM)
        self.assertIn(
            provenance.get("artifactKind"), ("intent", "derived"),
            'an artifact must declare whether it is intent or derived')

    def test_i13_volatile_invocation_facts_stay_out_of_the_payload(self):
        """Requested-at time, actor, and run id belong in the audit envelope."""
        module = require_interchange()
        result = module.import_bundle(
            module.decode_document(fixtures.to_json(fixtures.valid_bundle())), user=None)
        exported = json.loads(module.export_revision(result.design_revision, fmt="json"))

        def field_paths(node, prefix=""):
            if isinstance(node, dict):
                for key, value in node.items():
                    yield f"{prefix}.{key}"
                    yield from field_paths(value, f"{prefix}.{key}")
            elif isinstance(node, list):
                for index, value in enumerate(node):
                    yield from field_paths(value, f"{prefix}[{index}]")

        # Inspect parsed FIELD PATHS, not a substring of the raw text: a raw
        # search both false-fails on an innocent string value and misses a
        # nested field whose name is spelled differently at the top level.
        paths = list(field_paths(exported))
        for volatile in ("requestedAt", "requestId", "jobId", "actor", "exportedAt"):
            with self.subTest(fact=volatile):
                self.assertFalse(
                    [p for p in paths if p.split(".")[-1] == volatile],
                    f'{volatile} is a volatile invocation fact and belongs in the '
                    f'audit/run envelope, not the deterministic payload')

    def test_i14_unsupported_fact_cannot_be_silently_dropped(self):
        module = require_interchange()
        document = fixtures.valid_bundle()
        document["objects"][1]["topology"]["fabrics"][0]["switchClasses"][0][
            "unsupportedTrackedFact"] = "value"
        with self.assertRaises(Exception):
            module.import_bundle(module.decode_document(fixtures.to_json(document)),
                                 user=None)


class SecretBoundaryTestCase(TestCase):
    """I26a core text boundary. Field-policy enforcement, NOT universal
    secret detection -- the limit is asserted explicitly below."""

    SENTINEL = "hh-sentinel-secret-value-673"

    def test_i26a_designated_credential_field_is_rejected(self):
        module = require_interchange()
        document = fixtures.valid_bundle()
        document["objects"][1]["password"] = self.SENTINEL
        with self.assertRaises(Exception) as caught:
            module.decode_document(fixtures.to_json(document))
        self.assertNotIn(self.SENTINEL, str(caught.exception),
                         'a diagnostic may name the field path, never the value')

    def test_i26a_nested_credential_key_is_rejected(self):
        module = require_interchange()
        document = fixtures.valid_bundle()
        document["objects"][1]["provenance"]["adapter"] = {"token": self.SENTINEL}
        with self.assertRaises(Exception) as caught:
            module.decode_document(fixtures.to_json(document))
        self.assertNotIn(self.SENTINEL, str(caught.exception))

    def test_i26b_free_text_sentinel_documents_the_stated_limit(self):
        """A schema cannot prove an arbitrary authored note is secret-free. This
        records the limit rather than claiming a guarantee the tests cannot
        support; the enforceable guarantee is non-promotion of STORED
        credentials, covered by the T3 seam suite."""
        module = require_interchange()
        document = fixtures.valid_bundle()
        document["objects"][1]["assumptions"][0]["statement"] = self.SENTINEL
        decoded = module.decode_document(fixtures.to_json(document))
        self.assertIsNotNone(
            decoded,
            'field-policy validation is not universal secret detection; if this '
            'ever rejects, the universal claim must be re-examined, not assumed')


class CorpusBaselineTestCase(TestCase):
    """I30 - pilots stay diagnostic while their #668 findings are unresolved.

    The expected set is DERIVED from #668's recorded ledger rather than restated
    here, so this cannot drift from the measured record, and a future module
    cannot satisfy it by hard-coding three strings it read from this file.
    """

    @classmethod
    def expected_unresolved(cls):
        from netbox_hedgehog.tests.test_topology_planning.test_topology_invariants \
            import KNOWN_FINDINGS
        return {
            case_id: frozenset(entries)
            for case_id, entries in KNOWN_FINDINGS.items() if entries
        }

    def test_i30_ledger_is_the_source_of_the_expected_unresolved_set(self):
        """Guard: if #668's ledger empties, this row must stop claiming the
        pilots are downgraded rather than silently passing."""
        expected = self.expected_unresolved()
        self.assertTrue(expected, '#668 recorded no unresolved findings to bind to')
        for case_id in expected:
            with self.subTest(case=case_id):
                self.assertTrue(
                    (CASE_DIR / f"{case_id}.yaml").is_file(),
                    f'{case_id} must be a real pilot input, not a label')

    def test_i30_pilot_round_trip_evidence_is_measured_and_downgraded(self):
        module = require_interchange()
        for case_id, findings in sorted(self.expected_unresolved().items()):
            with self.subTest(case=case_id):
                evidence = module.corpus_round_trip_evidence(case_id)
                self.assertEqual(
                    evidence.disposition, "diagnostic",
                    f'{case_id} carries unresolved #668 findings and may not claim '
                    f'parity, contract conformance, or baseline authority')
                self.assertEqual(
                    frozenset(evidence.unresolved_findings), findings,
                    'the run must surface the EXACT unresolved set, so the '
                    'baseline cannot go quietly green if a finding disappears for '
                    'the wrong reason, nor accumulate new ones unnoticed')
                self.assertEqual(
                    evidence.source_case_path, str(CASE_DIR / f"{case_id}.yaml"),
                    'evidence must be bound to the real pilot input it was '
                    'measured from')
                self.assertTrue(
                    evidence.provenance.get("invariant_run"),
                    'evidence must name the #668 invariant run it derives from')
