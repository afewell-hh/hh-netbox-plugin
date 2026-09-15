"""RED core YAML/JSON interchange contract (#673, rows I1-I14/I17/I18/I26/I30).

Every test here is RED because `netbox_hedgehog.interchange` does not exist.
None of them is satisfied by weakening an invariant, skipping a path, mocking
the only real path, or treating T1 as a product schema.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import pathlib
import subprocess
import sys

from django.db import connection, transaction
from django.test import SimpleTestCase, TestCase

from netbox_hedgehog.tests.corpus.interchange_comparator import (
    REQUIRED_EXPORT_PROVENANCE_KEYS,
    compare_interchange,
)
from netbox_hedgehog.tests.corpus.interchange_model import (
    BINDING_ALGORITHM,
    RestrictedProfileError,
    canonicalize,
    content_integrity_digest,
)
from netbox_hedgehog.tests.test_interchange import fixtures
from netbox_hedgehog.tests.test_interchange._support import (
    require_interchange,
    require_interchange_models,
)

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

    # Expected bytes/digests are fixed independently of the implementation.
    # RFC 8785 §§3.2.1-3.2.4 specify no whitespace, literal/string emission,
    # recursive sorting, and UTF-8. Its full primitive vector contains floats
    # and its full sorting vector contains a non-BMP key, both rejected by this
    # repository's restricted profile; these are their in-profile projections.
    RFC8785_RESTRICTED_VECTORS = (
        (
            {"z": {"b": True, "a": None}, "a": [False, 1, "€"]},
            b'{"a":[false,1,"\xe2\x82\xac"],"z":{"a":null,"b":true}}',
            "df93c9ff6927b7dd2f1e63ee5afb96650fc682d509f84923f27f6901f90bc6d8",
        ),
        (
            {"literals": [None, True, False], "string": "€$\x0f\nA'B\"\\\"/"},
            b'{"literals":[null,true,false],"string":"\xe2\x82\xac$\\u000f\\nA\'B\\"\\\\\\"/"}',
            "3b682bc213c1fa88d5931e98b2efabfa60a236fb621f05437d6aa51daaa8031d",
        ),
    )

    def test_rfc8785_restricted_profile_vectors(self):
        for value, expected_bytes, expected_digest in self.RFC8785_RESTRICTED_VECTORS:
            with self.subTest(expected_digest=expected_digest):
                self.assertEqual(hashlib.sha256(expected_bytes).hexdigest(), expected_digest)
                self.assertEqual(canonicalize(value), expected_bytes)
                self.assertEqual(content_integrity_digest(value), expected_digest)


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
                # Authored-only: a deterministic export legitimately ADDS
                # provenance the author could not have written (exporter build
                # revision, content-integrity binding). Demanding exact
                # provenance equality here contradicted I13 and made the pair
                # unsatisfiable. Authored facts must still survive unchanged,
                # and the derived keys are checked by I13 and by the fixed-point
                # row below.
                outcome = compare_interchange(
                    module.decode_document(exported), document,
                    authored_provenance_only=True)
                self.assertTrue(outcome.full_model_equal, outcome.describe())

    def test_i11b_export_is_a_fixed_point_including_derived_provenance(self):
        """Re-importing an export and exporting again must reproduce it exactly.

        This is where derived provenance IS compared. Authored-only comparison
        above would hide export drift, so the two rows are complementary: one
        proves authored facts survive, this one proves the export is stable.
        """
        module = require_interchange()
        first = module.export_revision(
            module.import_bundle(
                module.decode_document(fixtures.to_json(fixtures.valid_bundle())),
                user=None).design_revision, fmt="json")
        second = module.export_revision(
            module.import_bundle(module.decode_document(first), user=None).design_revision,
            fmt="json")
        outcome = compare_interchange(
            module.decode_document(first), module.decode_document(second))
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
        # Unrelated rows in a TARGET table shift its primary keys, so a
        # PK-ordered export changes while a deterministic one does not. Created
        # test-side: a production helper that wrote to an unrelated table would
        # not perturb the ordering this row exists to test.
        models = require_interchange_models()
        for index in range(3):
            payload = {"filler": index}
            models.InterchangeCatalogVersion.objects.create(
                namespace="com.example.filler", slug=f"filler-{index}", version="1",
                content=payload, content_algorithm=BINDING_ALGORITHM,
                content_digest=content_integrity_digest(payload),
                published=False, artifact_digest=content_integrity_digest(payload))

        for label, document in (("reversed members", reversed_members),
                                ("interleaved unrelated rows", interleaved)):
            with self.subTest(perturbation=label):
                self.assertEqual(self._exported_digest(module, document), baseline)

    #: Runs the whole import/export cycle in a SEPARATE process and connection
    #: and prints the digest. Test-owned on purpose: a production helper that
    #: re-ran in-process could not demonstrate independence, and asking the code
    #: under test to attest to its own independence is not evidence.
    INDEPENDENT_RUN = (
        "import json, os, django;\n"
        "django.setup();\n"
        "from django.db import connection, transaction;\n"
        "connection.settings_dict['NAME'] = os.environ['HH_TEST_DB'];\n"
        "from netbox_hedgehog import interchange;\n"
        "from netbox_hedgehog.tests.test_interchange import fixtures;\n"
        "from netbox_hedgehog.tests.corpus.interchange_model import "
        "content_integrity_digest;\n"
        "class _Rollback(Exception): pass\n"
        "try:\n"
        "    with transaction.atomic():\n"
        "        r = interchange.import_bundle(\n"
        "            interchange.decode_document(\n"
        "                fixtures.to_json(fixtures.valid_bundle())), user=None);\n"
        "        d = content_integrity_digest(json.loads(\n"
        "            interchange.export_revision(r.design_revision, fmt='json')));\n"
        "        print('DIGEST=' + d);\n"
        "        raise _Rollback\n"
        "except _Rollback:\n"
        "    pass\n"
    )

    def test_i12_export_is_deterministic_across_independent_runs(self):
        """A second run in a separate process and connection must agree.

        Two exports in one process cannot demonstrate this, and neither can a
        production helper that claims independence while running in-process.
        The in-process digest is computed and rolled back FIRST so the child's
        insert cannot block on this transaction's uncommitted rows.
        """
        module = require_interchange()

        class _Rollback(Exception):
            pass

        baseline = None
        try:
            with transaction.atomic():
                baseline = self._exported_digest(module, fixtures.valid_bundle())
                raise _Rollback
        except _Rollback:
            pass

        completed = subprocess.run(
            [sys.executable, "-c", self.INDEPENDENT_RUN], capture_output=True,
            env={**os.environ, "HH_TEST_DB": connection.settings_dict["NAME"]},
        )
        self.assertEqual(
            completed.returncode, 0,
            f'independent run failed: {completed.stderr[-500:]!r}')
        printed = [line for line in completed.stdout.decode().splitlines()
                   if line.startswith("DIGEST=")]
        self.assertTrue(printed, f'no digest printed: {completed.stdout[-300:]!r}')
        self.assertEqual(printed[-1].split("=", 1)[1], baseline)

    def test_i13_export_provenance_names_required_elements(self):
        module = require_interchange()
        result = module.import_bundle(
            module.decode_document(fixtures.to_json(fixtures.valid_bundle())), user=None)
        exported = json.loads(module.export_revision(result.design_revision, fmt="json"))
        provenance = exported["objects"][1]["provenance"]
        # Imported, not restated: stating the required set independently here is
        # what let it drift out of step with the comparison rule.
        for element in sorted(REQUIRED_EXPORT_PROVENANCE_KEYS):
            with self.subTest(element=element):
                self.assertIn(
                    element, provenance,
                    f'provenance must identify {element}; an incomplete envelope '
                    f'cannot support a maturity or equivalence claim')
        self.assertEqual(provenance.get("canonicalizationAlgorithm"), BINDING_ALGORITHM)
        self.assertEqual(provenance.get("exporter"), module.EXPORTER_ID)
        # Computed INDEPENDENTLY from the shipped file rather than by calling
        # the exporter's own helper. Comparing the export against
        # module._exporter_revision() is self-referential: if that helper became
        # a constant, both sides would still agree and the prefix check would
        # still pass, so the row would no longer prove the revision tracks the
        # shipped code. It also avoids coupling the suite to a private name.
        expected = "source-sha256:" + hashlib.sha256(
            pathlib.Path(module.__file__).read_bytes()).hexdigest()
        self.assertEqual(
            provenance.get("exporterRevision"), expected,
            'exporterRevision must be a fingerprint of the shipped exporter '
            'implementation, independently reproducible from its source')
        self.assertIn(
            provenance.get("artifactKind"), ("intent", "derived"),
            'an artifact must declare whether it is intent or derived')

    def test_i13_author_supplied_emitter_identity_does_not_survive_export(self):
        """Reclassifying `exporter` as export-derived is right -- emitter
        identity is a property of the emitting software, not an author claim.

        But it removed the only check that noticed a forged one: an authored
        `exporter` is now excluded from the authored-mode round trip, and the
        fixed-point row compares export against export where both already carry
        the emitter's own value. A hostile or stale author-supplied emitter
        identity would surface in neither. This is that missing negative.
        """
        module = require_interchange()
        document = fixtures.valid_bundle()
        document["objects"][1]["provenance"]["exporter"] = "evil-corp"
        document["objects"][1]["provenance"]["exporterRevision"] = "source-sha256:0"
        result = module.import_bundle(
            module.decode_document(fixtures.to_json(document)), user=None)
        exported = json.loads(module.export_revision(result.design_revision, fmt="json"))
        provenance = exported["objects"][1]["provenance"]
        self.assertEqual(
            provenance.get("exporter"), module.EXPORTER_ID,
            'an author must not be able to assert who exported the artifact')
        self.assertNotEqual(
            provenance.get("exporterRevision"), "source-sha256:0",
            'an author must not be able to assert which build exported it')

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


class CorpusLedgerGuardTestCase(TestCase):
    """Supplemental binding for the #677 I30 real-pilot measurement.

    #677 executes the pilot and owns I30's row mapping. This test stays
    test-only: it keeps the binding to #668's recorded ledger and the real
    pilot inputs explicit, without importing or duplicating the measurement
    harness in the production interchange implementation.
    """

    @classmethod
    def expected_unresolved(cls):
        from netbox_hedgehog.tests.test_topology_planning.test_topology_invariants \
            import KNOWN_FINDINGS
        return {
            case_id: frozenset(entries)
            for case_id, entries in KNOWN_FINDINGS.items() if entries
        }

    def test_ledger_still_records_unresolved_pilot_findings(self):
        expected = self.expected_unresolved()
        self.assertTrue(expected, '#668 recorded no unresolved findings to bind to')
        for case_id in expected:
            with self.subTest(case=case_id):
                self.assertTrue(
                    (CASE_DIR / f"{case_id}.yaml").is_file(),
                    f'{case_id} must be a real pilot input, not a label')
