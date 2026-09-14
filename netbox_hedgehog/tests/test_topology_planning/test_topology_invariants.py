"""Executable topology-contract invariants against current HNP output (#668 / T2).

Read-only. Ingests each pilot case and evaluates the #661 invariant families
against HNP's calculated plan. Nothing here mutates topology artifacts,
generated NetBox data, or product behavior.

T1's TopologyGraph is used only as a comparison representation (#662 R2).

Triage rule (#668): a failing invariant is evidence. No check is weakened to
make HNP green; findings are classified as HNP defect, contract defect, or
intentional documented divergence, and unmeasured dimensions are recorded
rather than invented.
"""

from io import StringIO

from django.test import TestCase

from netbox_hedgehog.models.topology_planning import (
    PlanServerConnection,
    PlanSwitchClass,
    SwitchPortZone,
    TopologyPlan,
)
from netbox_hedgehog.test_cases.loader import load_case
from netbox_hedgehog.test_cases.runner import apply_case_id
from netbox_hedgehog.utils.topology_calculations import update_plan_calculations
from netbox_hedgehog.tests.corpus.invariants import (
    Family,
    Finding,
    InvariantResult,
    collect_fabric_facts,
    reconcile_findings,
    validate_ledger,
    check_clos_spine_cardinality,
    check_declared_family,
    check_equal_spine_divisibility,
    check_rail_grouping,
    check_redundancy_group_declared,
    check_zone_breakout_declared,
    summarize,
)
from netbox_hedgehog.tests.corpus.topology_graph import (
    ComparisonIdentity,
    ExportMode,
    ProvenanceEnvelope,
    TopologyGraph,
    UnmeasuredEndpoint,
)

#: Findings already triaged and recorded in the PR. A finding here does NOT fail
#: the suite -- #668 says a failing invariant is evidence, and failing the build
#: on a correctly-classified finding would pressure someone to weaken the check,
#: which is the one thing the triage rule forbids.
#:
#: Anything NOT listed here fails loudly, so a new or regressed finding is
#: visible rather than absorbed.
KNOWN_FINDINGS = {
    "training_xoc256_2xopg128_clos_ro": {
        "clos-spine-cardinality[frontend]": {
            "finding": "attribution-unresolved",
            "detail_contains": "S=1 on a declared Clos fabric",
                        "owner": "product owner",
            "resolution": "pending-governed-decision",
            "provenance": "#668 / PR 670 Dev B review; see PR body",
            "note":
            "S=1. HNP's arithmetic is correct -- fe-leaf 2 leaves x 32 uplinks = 64, "
            "and one fe-spine fabric zone supplies exactly 64 downlinks, so 1 is the "
            "capacity minimum. The conflict is with #661 F2, which requires S>=2 for a "
            "declared Clos fabric. ATTRIBUTION NOT RESOLVED HERE: either HNP should "
            "reject/flag a Clos fabric whose capacity minimum is 1, or F2 needs to say "
            "what an implementation must do when capacity yields 1. #668 reserves "
            "contract correction for a recorded amendment with a named owner and "
            "independent review, so this tranche reports and does not decide.",
        },
    },
    "training_xoc64_1xopg64_mesh_conv_ro": {
        # Surfaced only once the family check became per-fabric: the global
        # check let these hide behind the well-declared mesh fabric.
        "declared-family[inb-mgmt]": {
            "finding": "attribution-unresolved",
            "detail_contains": "family would be inferred",
                        "owner": "product owner",
            "resolution": "pending-governed-decision",
            "provenance": "#668 / PR 670; surfaced by the per-fabric repair",
            "note": "single management leaf class with no topology_mode and no "
                    "spine role. Attribution open between the case, HNP, and "
                    "#661's treatment of single-class management fabrics.",
        },
        "declared-family[oob-mgmt]": {
            "finding": "attribution-unresolved",
            "detail_contains": "family would be inferred",
                        "owner": "product owner",
            "resolution": "pending-governed-decision",
            "provenance": "#668 / PR 670; surfaced by the per-fabric repair",
            "note": "as above; this is also the surrogate fabric, so its family "
                    "declaration interacts with the unmanaged/surrogate rules.",
        },
    },
}

XOC64 = "training_xoc64_1xopg64_mesh_conv_ro"
XOC256 = "training_xoc256_2xopg128_clos_ro"


class _PilotInvariantMixin:
    """Ingest one pilot and evaluate the contract against HNP's own output."""

    case_id: str

    @classmethod
    def _ingest(cls):
        apply_case_id(cls.case_id, clean=True)
        document = load_case(cls.case_id)
        plan = TopologyPlan.objects.get(name=document["plan"]["name"])
        # Ingest alone does not populate calculated quantities. Without this the
        # invariants would read unset fields and report a false S=0 defect --
        # a measurement gap presented as an HNP finding.
        update_plan_calculations(plan)
        plan.refresh_from_db()
        return document, plan

    @classmethod
    def _plan_facts(cls, plan):
        """Read HNP's persisted calculation output -- not the source YAML."""
        classes = list(PlanSwitchClass.objects.filter(plan=plan))
        records = [
            {
                "switch_class_id": c.switch_class_id,
                "fabric_name": c.fabric_name,
                "hedgehog_role": c.hedgehog_role,
                "topology_mode": c.topology_mode,
                # Preserve None: "not calculated" is not the same fact as zero.
                "quantity": (c.override_quantity if c.override_quantity is not None
                             else c.calculated_quantity),
                "uplink_ports": c.uplink_ports_per_switch,
                "redundancy_type": c.redundancy_type,
                "redundancy_group": c.redundancy_group,
            }
            for c in classes
        ]
        return records, collect_fabric_facts(records)

    @classmethod
    def _evaluate(cls):
        document, plan = cls._ingest()
        records, facts = cls._plan_facts(plan)
        zones = [
            {"zone_name": z.zone_name, "breakout_option": z.breakout_option_id,
             "zone_type": z.zone_type}
            for z in SwitchPortZone.objects.filter(switch_class__plan=plan)
        ]
        connections = [
            {"connection_id": c.connection_id, "rail": getattr(c, "rail", None)}
            for c in PlanServerConnection.objects.filter(server_class__plan=plan)
        ]
        switch_class_records = records

        results: list = list(check_declared_family(facts["fabric_classes"]))
        results += check_clos_spine_cardinality(facts["spine_counts"])
        results += check_equal_spine_divisibility(
            facts["leaf_uplinks"], facts["spine_counts"], facts["leaf_fabric"])
        results += check_zone_breakout_declared(zones)
        results += check_redundancy_group_declared(switch_class_records)
        results.append(check_rail_grouping(connections))

        # Physical-realization facts require generated modules/cables, which
        # this read-only tranche does not produce. Recorded, not invented.
        results.append(InvariantResult(
            Family.PHYSICAL, "physical-realization", Finding.UNMEASURED,
            "requires generated modules and cables; device generation is out of "
            "scope for this read-only tranche"))
        return results

    def _by_family(self, family):
        return [r for r in self.results if r.family is family]

    def test_no_invariant_reports_an_unclassified_failure(self):
        """Every result carries an explicit triage classification.

        This is the #668 rule made mechanical: a failure must be classified,
        never silently dropped or resolved by weakening the check.
        """
        for result in self.results:
            self.assertIsInstance(result.finding, Finding)
            self.assertTrue(result.detail.strip(), f'{result.name} must state its basis')

    def test_declared_topology_family_is_evaluated_per_fabric(self):
        """Every fabric gets its own verdict; none inherits another's.

        Under-declared fabrics are recorded findings, not assertion failures --
        see KNOWN_FINDINGS and test_findings_are_reported_and_none_is_unrecorded.
        """
        family = [r for r in self.results if r.name.startswith('declared-family[')]
        self.assertTrue(family, 'each plan must produce per-fabric family verdicts')
        for result in family:
            self.assertNotEqual(
                result.finding, Finding.HNP_DEFECT,
                f'conflicting topology modes persisted: {result.detail}')

    def test_rail_grouping_is_not_asserted_as_an_established_contract(self):
        """#661 family 6: rail grouping stays a hypothesis until its harness
        assertion is accepted. Reporting HOLDS would be the error."""
        rail = self._by_family(Family.RAIL_GROUPING)[0]
        self.assertIn(rail.finding, (Finding.HYPOTHESIS, Finding.UNMEASURED))
        self.assertNotEqual(rail.finding, Finding.HOLDS)

    def test_unmeasured_dimensions_are_recorded_not_invented(self):
        physical = self._by_family(Family.PHYSICAL)[0]
        self.assertEqual(physical.finding, Finding.UNMEASURED)
        self.assertIn("out of scope", physical.detail)

    def test_findings_are_reported_and_none_is_unrecorded(self):
        """Surface classifications, and fail only on an UNRECORDED finding.

        A recorded finding is evidence awaiting triage. An unrecorded one is a
        change nobody has looked at, so it fails.
        """
        counts = summarize(self.results)
        failures = [r for r in self.results if r.is_failure]
        print(f"\n[{self.case_id}] invariant findings: {counts}")
        for failure in failures:
            print(f"  {failure.finding.value.upper()}: {failure.name} -- {failure.detail}")

        known = KNOWN_FINDINGS.get(self.case_id, {})
        self.assertEqual(validate_ledger(known), [],
                         'ledger entries must carry owner/resolution/provenance')

        outcome = reconcile_findings(failures, known)
        self.assertEqual(
            outcome['unrecorded'], [],
            f"unrecorded invariant findings for {self.case_id}: {outcome['unrecorded']}. "
            f'Triage and record them -- do not weaken the check.')
        self.assertEqual(
            outcome['changed'], [],
            f"recorded findings changed for {self.case_id}: {outcome['changed']}. "
            f'A ledger entry covers one specific finding, not an invariant name.')
        self.assertEqual(
            outcome['stale'], [],
            f"ledger lists findings that no longer occur: {outcome['stale']}. "
            f'Remove them so the ledger cannot hide a future regression.')


class Xoc64MeshInvariantTestCase(_PilotInvariantMixin, TestCase):
    """xoc64 mesh pilot."""

    case_id = XOC64

    @classmethod
    def setUpTestData(cls):
        cls.results = cls._evaluate()

    def test_mesh_case_declares_no_clos_spine_domain(self):
        """A mesh fabric has no spine domain; Clos cardinality must not be
        asserted over it, which would be vacuous."""
        clos = [r for r in self.results if r.name.startswith("clos-spine-cardinality")]
        self.assertEqual(clos, [], 'mesh pilot must not produce Clos spine findings')


class Xoc256ClosInvariantTestCase(_PilotInvariantMixin, TestCase):
    """xoc256 Clos pilot."""

    case_id = XOC256

    @classmethod
    def setUpTestData(cls):
        cls.results = cls._evaluate()

    def test_clos_spine_cardinality_is_evaluated_and_non_vacuous(self):
        """The Clos pilot must actually exercise the cardinality rule.

        This asserts the invariant RAN and produced a real, classified result --
        not that HNP is clean. Asserting cleanliness would make a genuine finding
        fail the build, and the only way back to green would be weakening the
        check. Known findings are pinned in KNOWN_FINDINGS; unknown ones fail.
        """
        clos = [r for r in self.results if r.name.startswith("clos-spine-cardinality")]
        self.assertTrue(clos, 'Clos pilot must produce spine-cardinality findings')
        self.assertTrue(
            any(r.finding is not Finding.UNMEASURED for r in clos),
            'at least one Clos fabric must be measurable, or the rule is untested here')


class InvariantMechanicsTestCase(TestCase):
    """RED evidence: the checks must be able to fail. A suite that only ever
    passes proves nothing was evaluated."""

    def test_clos_cardinality_rejects_zero_spines(self):
        """S=0 is unambiguous. S=1 is covered separately as UNRESOLVED."""
        results = check_clos_spine_cardinality({'fabric-x': 0})
        self.assertEqual(results[0].finding, Finding.HNP_DEFECT)

    def test_uncalculated_spine_quantity_is_unmeasured_not_a_defect(self):
        """A quantity that was never calculated is a gap in the measurement, not
        a statement about HNP.

        This check exists because the first run of this tranche reported
        S=0 HNP defects on both xoc256 fabrics. The cause was that ingest does
        not populate calculated quantities and the evaluation had not run them --
        a false finding produced by my own measurement. Conflating None with 0
        is how that happens, so the two are now distinct.
        """
        results = check_clos_spine_cardinality({'fabric-x': None})
        self.assertEqual(results[0].finding, Finding.UNMEASURED)
        self.assertIn('not calculated', results[0].detail)

    def test_clos_cardinality_accepts_two_or_more(self):
        results = check_clos_spine_cardinality({'fabric-x': 2})
        self.assertEqual(results[0].finding, Finding.HOLDS)

    def test_equal_spine_divisibility_rejects_a_remainder(self):
        results = check_equal_spine_divisibility(
            {'leaf-a': 3}, {'fab': 2}, {'leaf-a': 'fab'})
        self.assertEqual(results[0].finding, Finding.HNP_DEFECT)
        self.assertIn('remainder 1', results[0].detail)

    def test_equal_spine_divisibility_accepts_an_exact_split(self):
        results = check_equal_spine_divisibility(
            {'leaf-a': 4}, {'fab': 2}, {'leaf-a': 'fab'})
        self.assertEqual(results[0].finding, Finding.HOLDS)

    def test_s1_is_unresolved_not_an_hnp_defect(self):
        """S=1 must NOT be attributed to HNP.

        The PR states attribution between an HNP defect and a #661 F2 gap is
        unresolved. Returning HNP_DEFECT would make the code decide what the
        prose explicitly refuses to, and #668 reserves that for a governed
        amendment. It still counts as a failure requiring triage.
        """
        result = check_clos_spine_cardinality({'fab': 1})[0]
        self.assertEqual(result.finding, Finding.UNRESOLVED)
        self.assertTrue(result.is_failure, 'unresolved is a finding, not a clean result')
        self.assertIn('NOT decided here', result.detail)

    def test_zero_spines_remains_an_hnp_defect(self):
        """S=0 is unambiguous: a declared Clos cannot have no spine domain."""
        result = check_clos_spine_cardinality({'fab': 0})[0]
        self.assertEqual(result.finding, Finding.HNP_DEFECT)

    def test_divisibility_handles_unknown_spine_count_without_crashing(self):
        """`None < 2` raises TypeError; the guard must precede any comparison,
        or a harness crash masquerades as a measurement."""
        results = check_equal_spine_divisibility(
            {'leaf-a': 4}, {'fab': None}, {'leaf-a': 'fab'})
        self.assertEqual(results[0].finding, Finding.UNMEASURED)
        self.assertIn('not known', results[0].detail)

    def test_declared_family_is_evaluated_per_fabric(self):
        """One verdict for a whole plan would let an under-declared fabric hide
        behind a well-declared one."""
        results = check_declared_family({
            'frontend': [{'hedgehog_role': 'spine'}, {'hedgehog_role': 'server-leaf'}],
            'orphan': [{'hedgehog_role': 'server-leaf'}],
        })
        by_name = {r.name: r for r in results}
        self.assertEqual(len(results), 2, 'one result per fabric')
        self.assertEqual(by_name['declared-family[frontend]'].finding, Finding.HOLDS)
        self.assertEqual(
            by_name['declared-family[orphan]'].finding, Finding.UNRESOLVED,
            'a fabric with neither mesh nor spine must not inherit another fabric\'s verdict')

    def test_conflicting_topology_modes_in_one_fabric_are_a_defect(self):
        results = check_declared_family({
            'fab': [{'topology_mode': 'mesh'}, {'topology_mode': 'clos'}]})
        self.assertEqual(results[0].finding, Finding.HNP_DEFECT)
        self.assertIn('conflicting', results[0].detail)

    # --- end-to-end-shaped: declared Clos with NO spine class ---------------

    def test_declared_clos_with_no_spine_class_yields_observable_zero(self):
        """The gap Dev B found: a fabric declaring Clos but carrying no spine
        class never entered the collection, so S=0 produced NO result at all --
        the invariant could not catch the case it exists for."""
        facts = collect_fabric_facts([
            {"switch_class_id": "leaf-a", "fabric_name": "fab",
             "hedgehog_role": "server-leaf", "topology_mode": "spine-leaf",
             "quantity": 4, "uplink_ports": 8},
        ])
        self.assertEqual(facts["spine_counts"], {"fab": 0},
                         'a declared Clos fabric must be seeded so zero is observable')
        result = check_clos_spine_cardinality(facts["spine_counts"])[0]
        self.assertEqual(result.finding, Finding.HNP_DEFECT)
        self.assertIn('S=0', result.detail)

    def test_spine_role_without_topology_mode_is_also_seeded(self):
        """The other way a fabric declares Clos."""
        facts = collect_fabric_facts([
            {"switch_class_id": "spine-a", "fabric_name": "fab",
             "hedgehog_role": "spine", "topology_mode": None,
             "quantity": 0, "uplink_ports": 0},
        ])
        self.assertEqual(facts["spine_counts"], {"fab": 0})

    def test_mesh_fabric_is_not_seeded_as_clos(self):
        """Seeding must key on a Clos declaration, not on every fabric --
        otherwise a mesh fabric would be reported as a Clos defect."""
        facts = collect_fabric_facts([
            {"switch_class_id": "leaf-m", "fabric_name": "meshfab",
             "hedgehog_role": "server-leaf", "topology_mode": "mesh",
             "quantity": 2, "uplink_ports": 32},
        ])
        self.assertEqual(facts["spine_counts"], {},
                         'a mesh fabric must not acquire a Clos spine expectation')

    def test_explicit_spine_leaf_mode_is_an_explicit_family(self):
        """topology_mode='spine-leaf' declares Clos even with no spine role."""
        results = check_declared_family({
            'fab': [{'topology_mode': 'spine-leaf', 'hedgehog_role': 'server-leaf'}]})
        self.assertEqual(results[0].finding, Finding.HOLDS)
        self.assertIn('spine-leaf', results[0].detail)

    def test_mixed_known_and_unknown_spine_quantities_yield_unknown(self):
        """A confident subtotal from partial data could satisfy S>=2 while half
        the fabric is unmeasured."""
        facts = collect_fabric_facts([
            {"switch_class_id": "spine-a", "fabric_name": "fab", "hedgehog_role": "spine",
             "topology_mode": None, "quantity": 2, "uplink_ports": 0},
            {"switch_class_id": "spine-b", "fabric_name": "fab", "hedgehog_role": "spine",
             "topology_mode": None, "quantity": None, "uplink_ports": 0},
        ])
        self.assertIsNone(facts["spine_counts"]["fab"],
                          'an unknown spine quantity must poison the fabric total')
        result = check_clos_spine_cardinality(facts["spine_counts"])[0]
        self.assertEqual(result.finding, Finding.UNMEASURED)

    def test_unknown_first_is_not_overwritten_by_a_later_known_quantity(self):
        """Order must not decide the outcome."""
        facts = collect_fabric_facts([
            {"switch_class_id": "spine-a", "fabric_name": "fab", "hedgehog_role": "spine",
             "topology_mode": None, "quantity": None, "uplink_ports": 0},
            {"switch_class_id": "spine-b", "fabric_name": "fab", "hedgehog_role": "spine",
             "topology_mode": None, "quantity": 2, "uplink_ports": 0},
        ])
        self.assertIsNone(facts["spine_counts"]["fab"])

    # --- controlled ledger mechanics ---------------------------------------

    def _finding(self, name, finding=Finding.UNRESOLVED, detail='original substance'):
        return InvariantResult(Family.TOPOLOGY_FAMILY, name, finding, detail)

    def test_ledger_flags_a_same_name_finding_whose_classification_changed(self):
        known = {'x': {'finding': 'attribution-unresolved', 'detail_contains': 'original',
                       'owner': 'o', 'resolution': 'pending-governed-decision', 'provenance': 'p'}}
        outcome = reconcile_findings([self._finding('x', Finding.HNP_DEFECT)], known)
        self.assertEqual(outcome['unrecorded'], [])
        self.assertTrue(outcome['changed'], 'a changed classification must not be inherited')
        self.assertIn('classification', outcome['changed'][0])

    def test_ledger_flags_a_same_name_finding_whose_substance_changed(self):
        known = {'x': {'finding': 'attribution-unresolved', 'detail_contains': 'original',
                       'owner': 'o', 'resolution': 'pending-governed-decision', 'provenance': 'p'}}
        outcome = reconcile_findings([self._finding('x', detail='entirely different reason')], known)
        self.assertTrue(outcome['changed'], 'changed substance must not be inherited')
        self.assertIn('substance changed', outcome['changed'][0])

    def test_ledger_flags_a_stale_entry(self):
        known = {'gone': {'finding': 'attribution-unresolved', 'detail_contains': 'x',
                          'owner': 'o', 'resolution': 'pending-governed-decision', 'provenance': 'p'}}
        outcome = reconcile_findings([], known)
        self.assertEqual(outcome['stale'], ['gone'])

    def test_ledger_accepts_an_unchanged_recorded_finding(self):
        known = {'x': {'finding': 'attribution-unresolved', 'detail_contains': 'original',
                       'owner': 'o', 'resolution': 'pending-governed-decision', 'provenance': 'p'}}
        outcome = reconcile_findings([self._finding('x')], known)
        self.assertEqual((outcome['unrecorded'], outcome['changed'], outcome['stale']), ([], [], []))

    def test_ledger_validation_requires_owner_resolution_provenance(self):
        problems = validate_ledger({'x': {'finding': 'f', 'detail_contains': 'd'}})
        for field in ('owner', 'resolution', 'provenance'):
            self.assertTrue(any(field in p for p in problems), f'{field} must be required')

    def test_ledger_validation_rejects_an_unknown_resolution(self):
        problems = validate_ledger({'x': {'finding': 'f', 'detail_contains': 'd', 'owner': 'o',
                                          'resolution': 'ignored', 'provenance': 'p'}})
        self.assertTrue(any('not one of' in p for p in problems),
                        'there is deliberately no "ignored" resolution')

    def test_zone_without_breakout_is_a_defect(self):
        results = check_zone_breakout_declared([{'zone_name': 'z', 'breakout_option': None}])
        self.assertEqual(results[0].finding, Finding.HNP_DEFECT)

    def test_redundancy_type_without_group_is_a_defect(self):
        results = check_redundancy_group_declared(
            [{'switch_class_id': 'c', 'redundancy_type': 'eslag', 'redundancy_group': ''}])
        self.assertEqual(results[0].finding, Finding.HNP_DEFECT)

    def test_inferred_topology_family_is_unresolved_not_blamed(self):
        """An under-declared family has three possible owners -- the case, HNP,
        or #661. Naming one would repeat the S=1 mistake."""
        results = check_declared_family({'fab': [{'hedgehog_role': 'server-leaf'}]})
        self.assertEqual(results[0].finding, Finding.UNRESOLVED)
        self.assertTrue(results[0].is_failure)
        self.assertIn('NOT decided here', results[0].detail)

    def test_breakout_endpoint_without_identity_stays_unmeasured(self):
        """T1 used strictly as a comparison representation: an endpoint missing
        parent/lane must not be collapsed into a comparable one."""
        graph = TopologyGraph.from_records(
            ComparisonIdentity('c', ExportMode.FULL_PLAN, 's'),
            nodes=(),
            edges=({'left': {'device': 'a', 'interface': 'e1', 'is_breakout': True},
                    'right': {'device': 'b', 'interface': 'e2'}},),
            provenance=ProvenanceEnvelope({}),
        )
        self.assertTrue(graph.unmeasured)
        self.assertIsInstance(graph.unmeasured[0], UnmeasuredEndpoint)
        self.assertEqual(graph.edges, frozenset())
