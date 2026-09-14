"""Mutation and matching controls for the full-model comparator (#672 I11b).

These are deliberately GREEN in the RED phase. The comparator is evidence
infrastructure, and evidence infrastructure must be proven BEFORE anything
relies on it -- an unvalidated oracle that returns "equal" for a fact class it
does not model would let a round trip drop exactly the facts it claims to
protect.

Every claimed fact class carries two controls:

* a **mutation control** -- perturb exactly that fact class and require the
  comparator to name it, and
* a **matching control** -- an unperturbed pair that must compare equal, so a
  comparator that reports everything as different cannot pass by over-reporting.

Detection alone is not enough, so the comparator is additionally required to
fail closed on what it cannot see. Mutation controls are structurally blind
there: you can only perturb a fact class you already modelled.
"""

from django.test import SimpleTestCase

from netbox_hedgehog.tests.corpus.interchange_comparator import (
    AUTHORED_PROVENANCE_KEYS,
    CLAIMED_FACT_CLASSES,
    EXPORT_DERIVED_PROVENANCE_KEYS,
    REQUIRED_EXPORT_PROVENANCE_KEYS,
    FactDifference,
    compare_interchange,
)
from netbox_hedgehog.tests.test_interchange import fixtures

#: Classes whose perturbation must surface as a true value difference. The two
#: excluded classes are detected through the fail-closed path instead:
#: `envelope` because an unsupported schema version is unmeasured rather than
#: comparable, and `extension` because no namespace is registered.
VALUE_DIFFERENCE_CLASSES = (
    "identity", "catalog_reference", "content_integrity",
    "assumption", "maturity", "provenance", "topology",
    "bundle_manifest", "catalog_content",
)


class ComparatorControlTestCase(SimpleTestCase):
    """One mutation control plus one matching control per claimed fact class."""

    def _findings(self, outcome):
        return [(d.fact_class, d.path) for d in outcome.differences] + \
               [(u.fact_class, u.path) for u in outcome.unmeasured]

    def test_every_claimed_fact_class_has_a_declared_perturbation(self):
        """A class may not be claimed without a control, so the two lists are
        the same set. This is the guard that stops coverage drifting."""
        self.assertEqual(
            set(CLAIMED_FACT_CLASSES), set(fixtures.PERTURBATIONS),
            'each claimed fact class needs exactly one declared perturbation')

    def test_matching_control_is_equal_for_every_fact_class(self):
        """The over-reporting guard: an unperturbed pair must compare equal."""
        outcome = compare_interchange(fixtures.valid_bundle(), fixtures.valid_bundle())
        self.assertTrue(
            outcome.full_model_equal,
            f'unperturbed bundles must compare equal, got: {outcome.describe()}')
        self.assertEqual(outcome.unmeasured, ())

    def test_mutation_control_detects_each_fact_class_by_name_and_path(self):
        for fact_class in CLAIMED_FACT_CLASSES:
            label = fixtures.PERTURBATIONS[fact_class][0]
            with self.subTest(fact_class=fact_class, perturbation=label):
                outcome = compare_interchange(
                    fixtures.valid_bundle(), fixtures.perturbed(fact_class))
                findings = self._findings(outcome)
                named = [(fc, path) for fc, path in findings if fc == fact_class]
                self.assertTrue(
                    named,
                    f'perturbing {fact_class} ({label}) was not reported; '
                    f'comparator said: {outcome.describe()}')
                self.assertTrue(
                    all(path for _, path in named),
                    f'{fact_class} finding must carry a path')
                self.assertFalse(
                    outcome.full_model_equal,
                    f'a perturbed {fact_class} must block full-model equality')

    def test_mutation_control_is_symmetric(self):
        """Order must not decide detection."""
        for fact_class in CLAIMED_FACT_CLASSES:
            with self.subTest(fact_class=fact_class):
                outcome = compare_interchange(
                    fixtures.perturbed(fact_class), fixtures.valid_bundle())
                self.assertFalse(outcome.full_model_equal)

    def test_value_classes_produce_a_true_difference_not_only_unmeasured(self):
        """Detection via unmeasured is fail-closed and acceptable, but these
        classes must actually be compared, not merely refused."""
        for fact_class in VALUE_DIFFERENCE_CLASSES:
            with self.subTest(fact_class=fact_class):
                outcome = compare_interchange(
                    fixtures.valid_bundle(), fixtures.perturbed(fact_class))
                self.assertTrue(
                    any(isinstance(d, FactDifference) and d.fact_class == fact_class
                        for d in outcome.differences),
                    f'{fact_class} must be compared by value; got '
                    f'{outcome.describe()}')


class AuthoredProvenanceModeTestCase(SimpleTestCase):
    """Controls for `authored_provenance_only`.

    An exclusion is a potential hiding place, so each side of it is pinned:
    authored keys stay compared in BOTH modes, derived keys are compared in the
    default mode, and the mode is only ever legitimate for authored-vs-export.
    """

    def _exported_like(self):
        """A bundle as an exporter would emit it: authored plus derived."""
        document = fixtures.valid_bundle()
        for obj in document["objects"]:
            obj["provenance"].update(
                {key: "derived-value" for key in EXPORT_DERIVED_PROVENANCE_KEYS})
        return document

    def test_key_sets_are_disjoint_and_cover_the_required_set(self):
        self.assertFalse(AUTHORED_PROVENANCE_KEYS & EXPORT_DERIVED_PROVENANCE_KEYS)
        self.assertEqual(
            REQUIRED_EXPORT_PROVENANCE_KEYS,
            AUTHORED_PROVENANCE_KEYS | EXPORT_DERIVED_PROVENANCE_KEYS)

    def test_fixture_authors_exactly_the_authored_key_set(self):
        """Stops the fixture and the contract drifting apart again."""
        self.assertEqual(
            set(fixtures.design_revision()["provenance"]), set(AUTHORED_PROVENANCE_KEYS))

    def test_added_derived_provenance_is_not_a_difference_in_authored_mode(self):
        """The contradiction this mode exists to resolve: I13 requires these
        keys, so I11b must not reject an export for carrying them."""
        outcome = compare_interchange(
            self._exported_like(), fixtures.valid_bundle(),
            authored_provenance_only=True)
        self.assertTrue(outcome.full_model_equal, outcome.describe())

    def test_added_derived_provenance_IS_a_difference_in_the_default_mode(self):
        """So export-to-export drift cannot hide behind the exclusion."""
        outcome = compare_interchange(self._exported_like(), fixtures.valid_bundle())
        self.assertFalse(outcome.full_model_equal)

    def test_changed_authored_provenance_is_detected_in_both_modes(self):
        for authored_only in (False, True):
            with self.subTest(authored_provenance_only=authored_only):
                document = fixtures.valid_bundle()
                document["objects"][1]["provenance"]["sourceRevision"] = "r2"
                outcome = compare_interchange(
                    document, fixtures.valid_bundle(),
                    authored_provenance_only=authored_only)
                self.assertFalse(
                    outcome.full_model_equal,
                    'an authored provenance change must never be excluded')

    def test_dropped_authored_provenance_is_detected_in_authored_mode(self):
        document = fixtures.valid_bundle()
        document["objects"][1]["provenance"].pop("sourceRevision")
        outcome = compare_interchange(
            document, fixtures.valid_bundle(), authored_provenance_only=True)
        self.assertFalse(outcome.full_model_equal)

    def test_manifest_provenance_follows_the_same_rule(self):
        document = fixtures.valid_bundle()
        document["manifest"]["provenance"].update(
            {key: "derived-value" for key in EXPORT_DERIVED_PROVENANCE_KEYS})
        self.assertTrue(
            compare_interchange(document, fixtures.valid_bundle(),
                                authored_provenance_only=True).full_model_equal)
        self.assertFalse(
            compare_interchange(document, fixtures.valid_bundle()).full_model_equal)


class ComparatorFailsClosedTestCase(SimpleTestCase):
    """The half mutation controls cannot reach: facts the comparator cannot see."""

    def _assert_blocked(self, document, reason_fragment):
        outcome = compare_interchange(document, document)
        self.assertFalse(
            outcome.full_model_equal,
            'identical documents must NOT compare equal when a dimension is '
            'unmeasured; silently ignoring it is the oracle failure this '
            'comparator exists to avoid')
        self.assertTrue(
            any(reason_fragment in u.reason for u in outcome.unmeasured),
            f'expected an unmeasured reason containing {reason_fragment!r}, '
            f'got {[u.reason for u in outcome.unmeasured]}')

    def test_unknown_kind_is_unmeasured_and_blocks_equality(self):
        document = fixtures.valid_bundle()
        document["objects"][1]["kind"] = "SomethingNew"
        self._assert_blocked(document, "unknown kind")

    def test_unknown_field_is_unmeasured_and_blocks_equality(self):
        document = fixtures.valid_bundle()
        document["objects"][1]["invented"] = "value"
        self._assert_blocked(document, "unknown field")

    def test_unsupported_schema_version_is_unmeasured_and_blocks_equality(self):
        document = fixtures.valid_bundle()
        document["objects"][1]["schemaVersion"] = "2.0"
        self._assert_blocked(document, "unsupported schemaVersion")

    def test_unsupported_api_version_is_unmeasured_and_blocks_equality(self):
        document = fixtures.valid_bundle()
        document["objects"][1]["apiVersion"] = "aid.hedgehog.com/v2"
        self._assert_blocked(document, "unsupported apiVersion")

    def test_unregistered_extension_namespace_is_unmeasured_and_blocks_equality(self):
        document = fixtures.valid_bundle()
        document["objects"][1]["extensions"] = {"com.example.ext/v1": {"a": 1}}
        self._assert_blocked(document, "unregistered extension namespace")

    def test_identity_that_is_not_qualified_is_unmeasured(self):
        """A display-name-shaped identity must not be guessed at."""
        document = fixtures.valid_bundle()
        document["objects"][1]["identity"] = {"name": "XOC-64 Mesh"}
        self._assert_blocked(document, "namespace and slug")

    def test_removing_a_required_field_is_unmeasured_never_equal(self):
        """Both sides extracting None is not agreement. Checking only for
        UNKNOWN fields let a dropped required field compare equal (#674 B1)."""
        for name in sorted(fixtures.REQUIRED_FIELD_REMOVALS):
            with self.subTest(required_field=name):
                document = fixtures.without_required_field(name)
                outcome = compare_interchange(document, document)
                self.assertFalse(
                    outcome.full_model_equal,
                    f'dropping {name} must be unmeasured, not equal')

    def test_malformed_identity_is_unmeasured(self):
        """The accepted identity decision is reverse-DNS namespace plus lowercase
        slug; "is a string" was not enough."""
        for label, identity in sorted(fixtures.MALFORMED_IDENTITIES.items()):
            with self.subTest(identity=label):
                document = fixtures.with_identity(identity)
                outcome = compare_interchange(document, document)
                self.assertFalse(
                    outcome.full_model_equal, f'{label} must not be accepted')

    def test_altering_published_catalog_content_is_detected(self):
        """Dev B's case: change CatalogVersion.catalogContent while leaving the
        design's reference binding untouched."""
        document = fixtures.valid_bundle()
        document["objects"][0]["catalogContent"]["portCount"] = 32
        outcome = compare_interchange(fixtures.valid_bundle(), document)
        self.assertTrue(
            any(d.fact_class == "catalog_content" for d in outcome.differences),
            f'catalog content change not detected: {outcome.describe()}')

    def test_altering_bundle_manifest_is_detected(self):
        document = fixtures.valid_bundle()
        document["manifest"]["provenance"]["exporter"] = "elsewhere"
        outcome = compare_interchange(fixtures.valid_bundle(), document)
        self.assertTrue(
            any(d.fact_class == "bundle_manifest" for d in outcome.differences),
            f'manifest change not detected: {outcome.describe()}')

    def test_missing_objects_list_is_unmeasured(self):
        self._assert_blocked(
            {"apiVersion": fixtures.API_VERSION, "kind": "Bundle",
             "schemaVersion": fixtures.SCHEMA_VERSION, "manifest": {}},
            "no objects list")
