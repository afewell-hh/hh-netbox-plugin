"""RED YAML safety, reference graph, and topology/physical semantics (#673).

Added after Dev B's #674 review, which correctly found that I1/I3/I6 carried no
YAML-specific safety coverage, that I8 had no cycle or cross-bundle case, and
that I9/I10 were absent entirely.
"""

from __future__ import annotations

import copy

from django.test import TestCase

from netbox_hedgehog.tests.test_interchange import fixtures
from netbox_hedgehog.tests.test_interchange._support import require_interchange


class SourceLocationMixin:
    """A source location must be usable, not merely present.

    `assertTrue(source_location)` was too weak: a bare JSON pointer satisfies it
    while telling an author nothing about WHICH bundle member or line failed.
    """

    REQUIRED_KEYS = ("member", "path", "line", "column")

    def assert_source_located(self, exception, *, allow_missing_position=False):
        location = getattr(exception, "source_location", None)
        self.assertIsNotNone(
            location, f'{type(exception).__name__} carries no source_location')
        for key in self.REQUIRED_KEYS:
            if key in ("line", "column") and allow_missing_position:
                continue
            with self.subTest(key=key):
                self.assertIsNotNone(
                    getattr(location, key, None) if not isinstance(location, dict)
                    else location.get(key),
                    f'source_location must carry {key!r}; a path alone is '
                    f'insufficient for a bundle, and a line alone is insufficient '
                    f'for identifying the member')


class YamlSafetyTestCase(SourceLocationMixin, TestCase):
    """I1/I3/I6 - YAML must decode to the restricted I-JSON model, or reject."""

    def _reject(self, text, label):
        module = require_interchange()
        with self.assertRaises(Exception, msg=f'{label} must be rejected') as caught:
            module.decode_document(text)
        return caught.exception

    def test_duplicate_mapping_key_in_yaml_is_rejected(self):
        text = (
            "apiVersion: aid.hedgehog.com/v1\n"
            "kind: Bundle\n"
            "schemaVersion: '1.0'\n"
            "manifest: {}\n"
            "objects: []\n"
            "objects: []\n"
        )
        self.assert_source_located(self._reject(text, 'duplicate YAML key'))

    def test_yaml_anchor_and_alias_are_rejected(self):
        """Aliases let one document expand to a different graph than it reads as."""
        text = (
            "apiVersion: &v aid.hedgehog.com/v1\n"
            "kind: Bundle\n"
            "schemaVersion: '1.0'\n"
            "manifest: {}\n"
            "objects: []\n"
            "aliased: *v\n"
        )
        self._reject(text, 'YAML alias')

    def test_unsupported_yaml_tag_is_rejected(self):
        text = (
            "apiVersion: aid.hedgehog.com/v1\n"
            "kind: Bundle\n"
            "schemaVersion: '1.0'\n"
            "manifest: !!python/object:os.system {}\n"
            "objects: []\n"
        )
        self._reject(text, 'unsupported YAML tag')

    def test_yaml_merge_key_is_rejected(self):
        text = (
            "base: &b {kind: Bundle}\n"
            "apiVersion: aid.hedgehog.com/v1\n"
            "schemaVersion: '1.0'\n"
            "manifest: {}\n"
            "objects: []\n"
            "merged:\n  <<: *b\n"
        )
        self._reject(text, 'YAML merge key')

    def test_implicit_yaml_typing_cannot_change_a_value(self):
        """The Norway problem and friends: an unquoted scalar must not silently
        become a bool, a sexagesimal integer, or a timestamp."""
        module = require_interchange()
        for label, scalar in (
            ("norway", "no"), ("sexagesimal", "1:30"), ("timestamp", "2026-01-01"),
            ("octal", "0o17"), ("float", "1.0"),
        ):
            with self.subTest(case=label):
                document = fixtures.valid_bundle()
                document["objects"][1]["revision"] = scalar
                text = fixtures.to_yaml(document)
                decoded = module.decode_document(text)
                revision = decoded["objects"][1]["revision"]
                self.assertIsInstance(
                    revision, str,
                    f'{label}: YAML typing must not change {scalar!r} into '
                    f'{revision!r} of type {type(revision).__name__}')

    def test_unsafe_numeric_in_yaml_is_rejected(self):
        text = (
            "apiVersion: aid.hedgehog.com/v1\n"
            "kind: Bundle\n"
            "schemaVersion: '1.0'\n"
            "manifest: {}\n"
            "objects: []\n"
            "count: 9007199254740993\n"
        )
        self._reject(text, 'integer beyond exact range')


class ReferenceGraphTestCase(SourceLocationMixin, TestCase):
    """I8 - reference resolution, cycles, and cross-bundle scope."""

    def test_i8_cyclic_reference_where_disallowed_fails(self):
        module = require_interchange()
        first = fixtures.design_revision("plan-a")
        second = fixtures.design_revision("plan-b")
        first["dependsOn"] = {"namespace": fixtures.PUBLISHER, "slug": "plan-b"}
        second["dependsOn"] = {"namespace": fixtures.PUBLISHER, "slug": "plan-a"}
        with self.assertRaises(Exception):
            module.import_bundle(
                module.decode_document(
                    fixtures.to_json(fixtures.bundle(first, second))), user=None)

    def test_i8_cross_bundle_unresolved_reference_fails(self):
        """A reference that would resolve only in another bundle must not
        resolve here; there is no ambient cross-bundle scope."""
        module = require_interchange()
        document = fixtures.valid_bundle()
        document["objects"] = [document["objects"][1]]  # design without its catalog
        with self.assertRaises(Exception):
            module.import_bundle(
                module.decode_document(fixtures.to_json(document)), user=None)

    def test_i8_valid_in_bundle_reference_resolves(self):
        """The duplicate rule and reference checks must not over-fire."""
        module = require_interchange()
        result = module.import_bundle(
            module.decode_document(fixtures.to_json(fixtures.valid_bundle())), user=None)
        self.assertIsNotNone(result.design_revision)


class TopologyFamilyTestCase(SourceLocationMixin, TestCase):
    """I9 - explicit Clos/mesh/single-switch family, zones, breakout identity."""

    def _import(self, mutate):  # noqa: D401 - mesh-based negatives
        module = require_interchange()
        document = fixtures.valid_bundle()
        mutate(document["objects"][1]["topology"])
        return module.import_bundle(
            module.decode_document(fixtures.to_json(document)), user=None)

    def test_i9_absent_family_declaration_is_rejected(self):
        """#661 forbids inferring the family; absence must fail, not default."""
        with self.assertRaises(Exception):
            self._import(lambda t: t["fabrics"][0].pop("family"))

    def test_i9_unknown_family_is_rejected(self):
        with self.assertRaises(Exception):
            self._import(lambda t: t["fabrics"][0].update(family="somethingelse"))

    def test_i9_each_family_complete_declaration_is_accepted(self):
        """Positives use FAMILY-COMPLETE intent. Flipping the family string on a
        leaf-only fixture would have asked an implementation to accept a Clos
        with no spine domain or an unbounded single switch -- licensing exactly
        the under-specification #661 forbids."""
        module = require_interchange()
        for family in fixtures.VALID_FAMILIES:
            with self.subTest(family=family):
                result = module.import_bundle(
                    module.decode_document(
                        fixtures.to_json(fixtures.bundle_for_family(family))),
                    user=None)
                self.assertIsNotNone(result)

    def test_i9_under_specified_family_intent_is_rejected(self):
        """The matching negatives, so the positives above cannot be satisfied by
        an implementation that simply accepts anything."""
        module = require_interchange()
        for label in sorted(fixtures.INVALID_FAMILY_INTENT):
            with self.subTest(intent=label):
                # Built from the family it is actually invalid FOR, so the
                # mutator cannot be a no-op against a base that already
                # satisfies it -- which would demand rejection of a valid
                # document and contradict the positive test above.
                document = fixtures.invalid_family_bundle(label)
                with self.assertRaises(Exception, msg=f'{label} must be rejected'):
                    module.import_bundle(
                        module.decode_document(fixtures.to_json(document)), user=None)

    def test_i9_clos_requires_a_non_vacuous_spine_domain(self):
        """S=0 and S=1 are the specific cases #661 F2 and #668 turn on."""
        module = require_interchange()
        for count in (0, 1):
            with self.subTest(spine_count=count):
                document = fixtures.bundle_for_family("clos")
                fixtures._set_spine_count(document["objects"][1], count)  # noqa
                with self.assertRaises(Exception):
                    module.import_bundle(
                        module.decode_document(fixtures.to_json(document)), user=None)

    def test_i9_single_switch_must_declare_its_capacity_bound(self):
        module = require_interchange()
        document = fixtures.bundle_for_family("single-switch")
        document["objects"][1]["topology"]["fabrics"][0].pop("capacityBound")
        with self.assertRaises(Exception):
            module.import_bundle(
                module.decode_document(fixtures.to_json(document)), user=None)

    def test_i9_mesh_declared_with_a_spine_role_is_rejected(self):
        """Self-contradictory persisted family, the #668 finding in text form."""
        def mutate(topology):
            topology["fabrics"][0]["family"] = "mesh"
            topology["fabrics"][0]["switchClasses"].append({
                "identity": {"parent": {"namespace": fixtures.PUBLISHER,
                                        "slug": "xoc64-mesh"}, "slug": "spine-a"},
                "role": "spine", "quantity": 2, "uplinkPorts": 0, "zones": [],
            })
        with self.assertRaises(Exception):
            self._import(mutate)

    def test_i9_zone_without_a_parent_device_class_is_rejected(self):
        def mutate(topology):
            topology["zones"] = [{"identity": {"slug": "orphan"}}]
        with self.assertRaises(Exception):
            self._import(mutate)

    def test_i9_breakout_endpoint_without_parent_or_lane_is_rejected(self):
        """Allocation identity must never be reconstructed from a port string."""
        for missing in ("physical_parent", "lane"):
            with self.subTest(missing=missing):
                with self.assertRaises(Exception):
                    self._import(
                        lambda t, m=missing: t["connections"][0]["left"].pop(m))

    def test_i9_breakout_lane_must_be_an_integer_not_a_string(self):
        with self.assertRaises(Exception):
            self._import(lambda t: t["connections"][0]["left"].update(lane="0"))


class PhysicalCapabilityTestCase(TestCase):
    """I10 - physical assembly and media-overlay ownership.

    Native fixed ports are an accepted realization type, so they are tested for
    ACCEPTANCE without an invented optic.

    What stays gated is narrower: media-overlay OWNERSHIP is still open
    (#672 10.2), so where an overlay's admissibility depends on that decision,
    the row asserts only that no inferred substitute is used. That gate does not
    license rejecting native realization itself, which was the error here.
    """

    def _with_physical(self, connection_overlay):
        module = require_interchange()
        document = fixtures.valid_bundle()
        document["objects"][1]["topology"]["connections"][0].update(connection_overlay)
        return module, document

    def test_i10_media_overlay_is_not_silently_accepted_by_inference(self):
        module, document = self._with_physical({"mediaOverlay": {"cage": "osfp"}})
        with self.assertRaises(Exception):
            module.import_bundle(
                module.decode_document(fixtures.to_json(document)), user=None)

    def test_i10_integrated_assembly_is_not_inferred_from_a_pluggable_default(self):
        module, document = self._with_physical(
            {"assembly": {"kind": "integrated-fanout"}})
        with self.assertRaises(Exception):
            module.import_bundle(
                module.decode_document(fixtures.to_json(document)), user=None)

    def test_i10_native_fixed_port_is_accepted_without_a_transceiver(self):
        """Native fixed ports are an ACCEPTED realization type, so this asserts
        acceptance and the absence of an invented optic -- the previous version
        expected rejection, which contradicted both the contract and its own
        name."""
        module, document = self._with_physical({"assembly": {"kind": "native-port"}})
        result = module.import_bundle(
            module.decode_document(fixtures.to_json(document)), user=None)
        connection = module.export_connection(result.design_revision, index=0)
        self.assertEqual(connection["assembly"]["kind"], "native-port")
        for invented in ("transceiver", "optic", "mediaOverlay"):
            with self.subTest(field=invented):
                self.assertNotIn(
                    invented, connection,
                    f'a native fixed port must not acquire {invented} by inference')

    def test_i10_incompatible_overlay_on_a_native_port_is_rejected(self):
        """Accepting native realization does not mean accepting any overlay on
        it; an incompatible one must fail rather than be reconciled."""
        module, document = self._with_physical({
            "assembly": {"kind": "native-port"},
            "mediaOverlay": {"cage": "osfp", "pluggable": True},
        })
        with self.assertRaises(Exception):
            module.import_bundle(
                module.decode_document(fixtures.to_json(document)), user=None)
