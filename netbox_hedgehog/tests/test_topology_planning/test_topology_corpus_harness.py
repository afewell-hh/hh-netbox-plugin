"""#664 test-only executable checks for the #620 corpus comparison contract."""

from __future__ import annotations

import hashlib
from pathlib import Path

import yaml
from django.test import TestCase

from netbox_hedgehog.tests.corpus.topology_graph import (
    ComparisonDisposition,
    ComparisonIdentity,
    Endpoint,
    ExportMode,
    GraphNode,
    NodePlacement,
    ProvenanceEnvelope,
    TopologyGraph,
    compare_graphs,
)


TEST_CASE_DIR = Path(__file__).resolve().parents[2] / "test_cases"
PILOTS = {
    "training_xoc64_1xopg64_mesh_conv_ro": {
        "path": "training_xoc64_1xopg64_mesh_conv_ro.yaml",
        "sha256": "b67b1e0455055569cccfd7e5462a3f34e83c8fa1d64887fbf246f60c1e3bd745",
        "shape": "mesh",
    },
    "training_xoc256_2xopg128_clos_ro": {
        "path": "training_xoc256_2xopg128_clos_ro.yaml",
        "sha256": "f272e0d413ab5c66a307425c92e379cbfce0280bb14d0797e5e0df8511899c1b",
        "shape": "clos",
    },
}


def complete_provenance(mode: ExportMode) -> ProvenanceEnvelope:
    return ProvenanceEnvelope({field: f"recorded:{field}" for field in ProvenanceEnvelope.REQUIRED_FIELDS} | {
        "export_mode": mode.value,
    })


class TopologyCorpusPilotBindingTestCase(TestCase):
    """The initial pilots bind tracked HNP inputs; they do not assert parity."""

    def test_xoc64_mesh_input_is_bound_to_its_recorded_source_hash(self):
        self._assert_pilot_source("training_xoc64_1xopg64_mesh_conv_ro")

    def test_xoc256_clos_input_is_bound_to_its_recorded_source_hash(self):
        self._assert_pilot_source("training_xoc256_2xopg128_clos_ro")

    def _assert_pilot_source(self, case_id: str) -> None:
        pilot = PILOTS[case_id]
        content = (TEST_CASE_DIR / pilot["path"]).read_bytes()
        self.assertEqual(hashlib.sha256(content).hexdigest(), pilot["sha256"])
        document = yaml.safe_load(content)
        self.assertEqual(document["meta"]["case_id"], case_id)
        if pilot["shape"] == "mesh":
            topology_modes = {item.get("topology_mode") for item in document["switch_classes"]}
            self.assertIn("mesh", topology_modes)
        else:
            # This v1 input expresses the Clos shape through explicit
            # server-leaf/spine classes, not a ``topology_mode: clos`` field.
            classes = {item["switch_class_id"]: item["hedgehog_role"] for item in document["switch_classes"]}
            self.assertEqual(classes["fe-spine"], "spine")
            self.assertEqual(classes["be-spine"], "spine")


class TopologyGraphContractTestCase(TestCase):
    """Focused #620 behavior checks; all graphs here are synthetic test evidence."""

    def _graph(
        self,
        mode=ExportMode.FULL_PLAN,
        provenance=None,
        edges=(),
        nodes=(),
        required_surrogates=(),
        forbidden_surrogates=(),
    ):
        return TopologyGraph.from_records(
            ComparisonIdentity("training_xoc64_1xopg64_mesh_conv_ro", mode, "hnp"),
            nodes,
            edges,
            provenance or complete_provenance(mode),
            required_surrogates=required_surrogates,
            forbidden_surrogates=forbidden_surrogates,
        )

    def test_export_mode_is_part_of_comparison_identity(self):
        full = self._graph()
        scoped = self._graph(mode=ExportMode.FABRIC_SCOPED)
        report = compare_graphs(full, scoped)
        self.assertEqual(report.disposition, ComparisonDisposition.DIAGNOSTIC)
        self.assertEqual(report.differences["export_mode"], ("full-plan", "fabric-scoped"))

    def test_unmanaged_surrogate_positive_and_negative_contracts_are_preserved(self):
        managed = GraphNode("fe-leaf-01", "Switch", NodePlacement.MANAGED_FABRIC)
        surrogate = GraphNode("oob-leaf-01", "Server", NodePlacement.UNMANAGED_FABRIC, surrogate=True)
        excluded = GraphNode("inb-mgmt-01", "Server", NodePlacement.UNMANAGED_FABRIC)
        graph = self._graph(
            nodes=(managed, surrogate, excluded),
            edges=(
                {"left": {"device": "fe-leaf-01", "interface": "E1/1"},
                 "right": {"device": "oob-leaf-01", "interface": "E1/1"}},
            ),
            required_surrogates=("oob-leaf-01",),
            forbidden_surrogates=("inb-mgmt-01",),
        )
        report = compare_graphs(graph, graph)
        self.assertEqual(report.disposition, ComparisonDisposition.DIAGNOSTIC)
        self.assertIn("forbidden non-surrogate unmanaged node: inb-mgmt-01", report.exclusions)
        self.assertNotIn("forbidden server-to-surrogate connection", " ".join(report.exclusions))

    def test_scoped_export_requires_only_cabled_surrogates_and_excludes_uncabled_ones(self):
        managed = GraphNode("fe-leaf-01", "Switch", NodePlacement.MANAGED_FABRIC)
        cabled = GraphNode("oob-leaf-cabled", "Server", NodePlacement.UNMANAGED_FABRIC, surrogate=True)
        uncabled = GraphNode("oob-leaf-uncabled", "Server", NodePlacement.UNMANAGED_FABRIC, surrogate=True)
        good = self._graph(
            mode=ExportMode.FABRIC_SCOPED,
            nodes=(managed, cabled),
            required_surrogates=("oob-leaf-cabled",),
            forbidden_surrogates=("oob-leaf-uncabled",),
        )
        bad = self._graph(
            mode=ExportMode.FABRIC_SCOPED,
            nodes=(managed, cabled, uncabled),
            required_surrogates=("oob-leaf-cabled",),
            forbidden_surrogates=("oob-leaf-uncabled",),
        )
        self.assertEqual(compare_graphs(good, good).disposition, ComparisonDisposition.EQUIVALENCE_ELIGIBLE)
        self.assertIn(
            "forbidden scoped surrogate node: oob-leaf-uncabled",
            compare_graphs(bad, bad).exclusions,
        )

    def test_default_server_encoding_rejects_server_to_surrogate_connection(self):
        server = GraphNode("server-01", "Server")
        surrogate = GraphNode("oob-leaf-01", "Server", NodePlacement.UNMANAGED_FABRIC, surrogate=True)
        graph = self._graph(
            nodes=(server, surrogate),
            edges=(
                {"left": {"device": "server-01", "interface": "eth0"},
                 "right": {"device": "oob-leaf-01", "interface": "E1/1"}},
            ),
        )
        report = compare_graphs(graph, graph)
        self.assertIn(
            "forbidden server-to-surrogate connection: server-01<->oob-leaf-01",
            report.exclusions,
        )
        self.assertNotIn("forbidden non-surrogate unmanaged node: server-01", report.exclusions)

    def test_breakout_without_parent_and_lane_is_unmeasured_not_collapsed(self):
        graph = self._graph(edges=(
            {"left": {"device": "leaf-01", "interface": "E1/1", "is_breakout": True},
             "right": {"device": "server-01", "interface": "eth0"}},
        ))
        report = compare_graphs(graph, graph)
        self.assertEqual(report.disposition, ComparisonDisposition.DIAGNOSTIC)
        self.assertEqual(len(report.unmeasured), 1)
        self.assertEqual(graph.edges, frozenset())
        self.assertIn("physical_parent", report.unmeasured[0].reason)

    def test_incomplete_c4_envelope_is_diagnostic_not_an_equivalence_claim(self):
        incomplete = ProvenanceEnvelope({"source_hash": "known"})
        graph = self._graph(provenance=incomplete)
        report = compare_graphs(graph, graph)
        self.assertEqual(report.disposition, ComparisonDisposition.DIAGNOSTIC)
        self.assertIn("platform_image_digest", report.missing_provenance)
        self.assertIn("provenance", report.differences)

    def test_complete_equal_graphs_are_eligible_but_do_not_assert_parity(self):
        graph = self._graph(nodes=(GraphNode("fe-leaf-01", "Switch"),))
        report = compare_graphs(graph, graph)
        self.assertEqual(report.disposition, ComparisonDisposition.EQUIVALENCE_ELIGIBLE)
        self.assertEqual(report.matches["nodes"], (GraphNode("fe-leaf-01", "Switch"),))
        self.assertNotIsInstance(report, bool)

    def test_breakout_identity_includes_parent_and_lane(self):
        first = Endpoint("leaf-01", "E1/1", "E1/1", 0)
        second = Endpoint("leaf-01", "E1/1", "E1/1", 1)
        self.assertNotEqual(first, second)
