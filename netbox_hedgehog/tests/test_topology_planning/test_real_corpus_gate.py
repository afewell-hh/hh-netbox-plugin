"""#677 real, diagnostic corpus-gate execution.

Evidence infrastructure only. It runs the real HNP ingest and calculation path,
evaluates the real T2 invariants, projects persisted state through the REAL
versioned interchange path, and refuses to promote either pilot beyond
DIAGNOSTIC while any requirement is unmet.

No AID/HNP parity, canonical-format, or seam-selection claim is made here, and
none can be while a recorded T2 finding is unresolved.
"""

from __future__ import annotations

from django.test import TestCase, tag

from netbox_hedgehog.models.topology_planning import (
    PlanServerConnection, PlanSwitchClass, SwitchPortZone, TopologyPlan,
)
from netbox_hedgehog.test_cases.loader import load_case
from netbox_hedgehog.test_cases.runner import apply_case_id
from netbox_hedgehog.tests.corpus import pilot_evidence
from netbox_hedgehog.tests.corpus.invariants import (
    Family, Finding, InvariantResult, check_clos_spine_cardinality,
    check_declared_family, check_equal_spine_divisibility, check_rail_grouping,
    check_redundancy_group_declared, check_zone_breakout_declared,
    collect_fabric_facts, reconcile_findings,
)
from netbox_hedgehog.tests.corpus.topology_graph import (
    ComparisonDisposition, ComparisonIdentity, ExportMode, GraphNode,
    ProvenanceEnvelope, TopologyGraph, compare_graphs,
)
from netbox_hedgehog.tests.test_topology_planning.test_topology_invariants import (
    KNOWN_FINDINGS,
)

PILOTS = ("training_xoc64_1xopg64_mesh_conv_ro", "training_xoc256_2xopg128_clos_ro")


def measure(case_id):
    """Run the REAL ingest, calculation, and T2 invariants for one pilot."""
    from netbox_hedgehog.utils.topology_calculations import update_plan_calculations

    apply_case_id(case_id, clean=True)
    document = load_case(case_id)
    plan = TopologyPlan.objects.get(name=document["plan"]["name"])
    update_plan_calculations(plan)
    plan.refresh_from_db()

    classes = list(PlanSwitchClass.objects.filter(plan=plan)
                   .order_by("fabric_name", "switch_class_id"))
    records = [{
        "switch_class_id": c.switch_class_id, "fabric_name": c.fabric_name,
        "hedgehog_role": c.hedgehog_role, "topology_mode": c.topology_mode,
        "quantity": (c.override_quantity if c.override_quantity is not None
                     else c.calculated_quantity),
        "uplink_ports": c.uplink_ports_per_switch,
        "redundancy_type": c.redundancy_type, "redundancy_group": c.redundancy_group,
    } for c in classes]

    facts = collect_fabric_facts(records)
    results = list(check_declared_family(facts["fabric_classes"]))
    results += check_clos_spine_cardinality(facts["spine_counts"])
    results += check_equal_spine_divisibility(
        facts["leaf_uplinks"], facts["spine_counts"], facts["leaf_fabric"])
    results += check_zone_breakout_declared([
        {"zone_name": z.zone_name, "breakout_option": z.breakout_option_id,
         "zone_type": z.zone_type}
        for z in SwitchPortZone.objects.filter(switch_class__plan=plan)])
    results += check_redundancy_group_declared(records)
    results.append(check_rail_grouping([
        {"connection_id": c.connection_id, "rail": getattr(c, "rail", None)}
        for c in PlanServerConnection.objects.filter(server_class__plan=plan)]))
    results.append(InvariantResult(
        Family.PHYSICAL, "physical-realization", Finding.UNMEASURED,
        "requires generated modules and cables; generation is out of scope for "
        "this diagnostic tranche"))
    return classes, results


@tag('slow')
class RealCorpusGateTestCase(TestCase):
    """Both pilots, measured for real."""

    #: Measured ONCE per class. Re-ingesting both pilots in every test method
    #: is slow and provoked DeviceType deadlocks under repeated
    #: get_or_create storms; the invariant suite caches the same way.
    MEASURED: dict = {}

    @classmethod
    def setUpTestData(cls):
        cls.MEASURED = {}
        for case_id in PILOTS:
            classes, results = measure(case_id)
            failures = [r for r in results if r.is_failure]
            provenance = pilot_evidence.measure_c4(
                pilot_evidence.CASE_DIR / f"{case_id}.yaml")
            cls.MEASURED[case_id] = {
                "class_count": len(classes),
                "results": results,
                "failures": failures,
                "evidence": pilot_evidence.evaluate(
                    case_id, classes, failures, provenance),
            }

    def _evidence(self, case_id):
        measured = self.MEASURED[case_id]
        return (measured["class_count"], measured["results"],
                measured["failures"], measured["evidence"])

    def test_both_pilots_are_measured_and_remain_diagnostic(self):
        for case_id in PILOTS:
            with self.subTest(case=case_id):
                class_count, results, failures, evidence = self._evidence(case_id)

                self.assertTrue(
                    class_count, 'the pilot must actually ingest switch classes')
                self.assertEqual(
                    evidence.disposition, ComparisonDisposition.DIAGNOSTIC,
                    f'{case_id} must stay diagnostic while requirements are unmet; '
                    f'reasons: {evidence.reasons}')
                self.assertTrue(
                    evidence.reasons, 'a diagnostic verdict must say why')
                self.assertFalse(
                    evidence.claims_parity,
                    'this harness must never assert AID/HNP parity')

                # A diagnostic gate must SHOW its evidence. Asserting a verdict
                # without emitting the reasons makes a green run indistinguishable
                # from a vacuous one.
                print(f"\n[{case_id}] disposition={evidence.disposition.value} "
                      f"stale={evidence.stale} "
                      f"t2_failures={[f.name for f in evidence.t2_failures]} "
                      f"round_trip_error={evidence.round_trip_error} "
                      f"t1_differences={sorted(evidence.t1_differences)} "
                      f"provenance_missing={list(evidence.provenance_missing)}")
                for reason in evidence.reasons:
                    print(f"    reason: {reason}")

    def test_recorded_t2_findings_are_preserved_not_resolved_away(self):
        """The known findings must still be produced by real execution."""
        for case_id in PILOTS:
            with self.subTest(case=case_id):
                _, _, failures, _ = self._evidence(case_id)
                outcome = reconcile_findings(failures, KNOWN_FINDINGS.get(case_id, {}))
                self.assertEqual(outcome["unrecorded"], [], f'{case_id}: {outcome}')
                self.assertEqual(outcome["changed"], [], f'{case_id}: {outcome}')
                self.assertEqual(outcome["stale"], [], f'{case_id}: {outcome}')

    def test_edges_are_reported_unmeasured_not_compared_as_empty(self):
        """An empty edge set would trivially match and read as agreement."""
        _, _, _, evidence = self._evidence(PILOTS[0])
        self.assertTrue(
            any("edges" in axis for axis in evidence.unmeasured_axes),
            f'edges must be recorded unmeasured; got {evidence.unmeasured_axes}')

    def test_source_digest_drift_is_reported_stale(self):
        """Derived from the actual file, not asserted from a literal."""
        for case_id in PILOTS:
            with self.subTest(case=case_id):
                _, _, _, evidence = self._evidence(case_id)
                self.assertFalse(
                    evidence.stale,
                    f'{case_id} source drifted from its recorded digest; the '
                    f'baseline must be re-measured and re-reviewed, not updated '
                    f'silently')


class StaleDetectionControlTestCase(TestCase):
    """Control: the stale path must be able to fire."""

    def test_unknown_case_id_is_reported_stale(self):
        provenance = pilot_evidence.measure_c4(
            pilot_evidence.CASE_DIR / f"{PILOTS[0]}.yaml")
        evidence = pilot_evidence.evaluate(PILOTS[0], [], [], provenance)
        self.assertFalse(evidence.stale)
        original = dict(pilot_evidence.PILOT_SOURCE_DIGESTS)
        try:
            pilot_evidence.PILOT_SOURCE_DIGESTS[PILOTS[0]] = "0" * 64
            drifted = pilot_evidence.evaluate(PILOTS[0], [], [], provenance)
            self.assertTrue(drifted.stale)
            self.assertTrue(any("source digest" in r for r in drifted.reasons))
        finally:
            pilot_evidence.PILOT_SOURCE_DIGESTS.clear()
            pilot_evidence.PILOT_SOURCE_DIGESTS.update(original)


class AxisMismatchControlTestCase(TestCase):
    """A deliberate mismatch control for every claimed comparison axis.

    Without these the harness could report agreement on an axis it cannot
    actually distinguish -- the failure mode that made the superseded draft's
    equivalence result meaningless.
    """

    def _graphs(self):
        provenance = pilot_evidence.measure_c4(
            pilot_evidence.CASE_DIR / f"{PILOTS[0]}.yaml")
        nodes = [GraphNode("fabric:leaf", "server-leaf")]
        base = TopologyGraph.from_records(
            ComparisonIdentity(PILOTS[0], ExportMode.FULL_PLAN, "hnp-persisted-plan"),
            nodes, (), provenance)
        return base, nodes, provenance

    def test_nodes_axis_detects_a_difference(self):
        base, nodes, provenance = self._graphs()
        other = TopologyGraph.from_records(
            base.identity, nodes + [GraphNode("fabric:extra", "spine")], (), provenance)
        self.assertIn("nodes", compare_graphs(base, other).differences)

    def test_edges_axis_detects_a_difference(self):
        base, nodes, provenance = self._graphs()
        other = TopologyGraph.from_records(
            base.identity, nodes,
            ({"left": {"device": "a", "interface": "E1/1"},
              "right": {"device": "b", "interface": "E1/2"}},), provenance)
        self.assertIn("edges", compare_graphs(base, other).differences)

    def test_export_mode_axis_detects_a_difference(self):
        base, nodes, provenance = self._graphs()
        other = TopologyGraph.from_records(
            ComparisonIdentity(PILOTS[0], ExportMode.FABRIC_SCOPED, base.identity.source),
            nodes, (), provenance)
        self.assertIn("export_mode", compare_graphs(base, other).differences)

    def test_provenance_axis_detects_an_incomplete_envelope(self):
        base, nodes, _ = self._graphs()
        other = TopologyGraph.from_records(
            base.identity, nodes, (), ProvenanceEnvelope({"source_hash": "known"}))
        report = compare_graphs(base, other)
        self.assertIn("provenance", report.differences)
        self.assertEqual(report.disposition, ComparisonDisposition.DIAGNOSTIC)

    def test_interchange_round_trip_axis_detects_a_rejected_bundle(self):
        """A bundle the versioned path refuses must surface as an error, not as
        silent agreement."""
        decoded, error = pilot_evidence.interchange_round_trip({"kind": "NotABundle"})
        self.assertIsNone(decoded)
        self.assertTrue(error, 'a rejected bundle must be recorded as an error')

    def test_every_claimed_axis_has_a_control(self):
        declared = set(pilot_evidence.CLAIMED_AXES)
        covered = {name.replace("test_", "").replace("_axis_detects_a_difference", "")
                   .replace("_axis_detects_an_incomplete_envelope", "")
                   .replace("_axis_detects_a_rejected_bundle", "")
                   for name in dir(self) if name.startswith("test_") and "_axis_" in name}
        self.assertEqual(
            declared - covered, set(),
            f'claimed axes without a mismatch control: {sorted(declared - covered)}')
