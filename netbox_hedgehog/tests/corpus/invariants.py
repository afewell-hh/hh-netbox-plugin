"""Test-only executable topology-contract invariants (#662 T2 / #668).

These OBSERVE and CLASSIFY current HNP output against the #661 contract. They
never repair, rewrite, or select an implementation, and they are not weakened to
make HNP green -- per #668 a failing invariant is evidence.

`TopologyGraph` from T1 is used purely as a comparison representation. Nothing
here promotes it to a runtime, public, or canonical interface (#662 R2).
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Sequence


class Family(str, Enum):
    """#661 invariant families."""

    TOPOLOGY_FAMILY = "topology-family"
    CAPACITY = "capacity-bandwidth"
    ALLOCATION = "allocation-identity"
    PHYSICAL = "physical-realization"
    REDUNDANCY = "redundancy-envelope"
    RAIL_GROUPING = "rail-grouping"


class Finding(str, Enum):
    """Triage classification. #668 forbids resolving a failure by weakening.

    HYPOTHESIS exists for the #620 rail-grouping enhancement, which #661
    explicitly says is not yet an established contract.
    """

    HOLDS = "holds"
    HNP_DEFECT = "hnp-defect"
    CONTRACT_DEFECT = "contract-defect-or-ambiguity"
    DOCUMENTED_DIVERGENCE = "intentional-documented-divergence"
    UNMEASURED = "unmeasured"
    HYPOTHESIS = "hypothesis-not-yet-contract"


@dataclass(frozen=True)
class InvariantResult:
    family: Family
    name: str
    finding: Finding
    detail: str

    @property
    def is_failure(self) -> bool:
        return self.finding in (Finding.HNP_DEFECT, Finding.CONTRACT_DEFECT)


# --- topology family --------------------------------------------------------

def check_declared_family(case: Mapping[str, Any]) -> InvariantResult:
    """A fabric declares exactly one family; silent substitution is forbidden."""
    modes = {s.get("topology_mode") for s in case["switch_classes"] if s.get("topology_mode")}
    roles = {s.get("hedgehog_role") for s in case["switch_classes"]}
    if "mesh" in modes:
        return InvariantResult(Family.TOPOLOGY_FAMILY, "declared-family",
                               Finding.HOLDS, f"mesh declared explicitly: {sorted(modes)}")
    if "spine" in roles:
        return InvariantResult(Family.TOPOLOGY_FAMILY, "declared-family",
                               Finding.HOLDS, "Clos expressed via leaf/spine roles")
    return InvariantResult(
        Family.TOPOLOGY_FAMILY, "declared-family", Finding.CONTRACT_DEFECT,
        "neither an explicit topology_mode nor a spine role; family is inferred, "
        "which #661 forbids")


def check_clos_spine_cardinality(spine_counts: Mapping[str, Any]) -> list:
    """#661 F2: a Clos fabric has S >= 2, so equal-spine checks are non-vacuous.

    S == 1 must be declared capacity-bounded single switch, not Clos; S == 0 is
    under-specified and cannot satisfy Clos invariants.

    ``None`` means the quantity was never calculated, which is a gap in the
    MEASUREMENT and not a statement about HNP. Conflating that with a genuine
    S == 0 would manufacture a false defect, so it is reported UNMEASURED.
    """
    results = []
    for fabric, spines in sorted(spine_counts.items(), key=lambda item: item[0]):
        if spines is None:
            results.append(InvariantResult(
                Family.TOPOLOGY_FAMILY, f"clos-spine-cardinality[{fabric}]",
                Finding.UNMEASURED,
                "spine quantity not calculated for this plan; cardinality cannot "
                "be evaluated and no defect is implied"))
            continue
        if spines >= 2:
            finding, detail = Finding.HOLDS, f"S={spines}"
        elif spines == 1:
            finding, detail = (Finding.HNP_DEFECT,
                               "S=1 declared Clos; must be the capacity-bounded "
                               "single-switch family")
        else:
            finding, detail = (Finding.HNP_DEFECT,
                               "S=0; Clos invariants would be vacuously satisfied")
        results.append(InvariantResult(
            Family.TOPOLOGY_FAMILY, f"clos-spine-cardinality[{fabric}]", finding, detail))
    return results


def check_equal_spine_divisibility(leaf_uplinks: Mapping[str, int],
                                   spine_counts: Mapping[str, int],
                                   leaf_fabric: Mapping[str, str]) -> list:
    """#622 S4 / #661: a leaf class's uplink allocation must divide exactly
    across its fabric's spine count, absent an approved asymmetric policy."""
    results = []
    for leaf, uplinks in sorted(leaf_uplinks.items()):
        fabric = leaf_fabric.get(leaf)
        spines = spine_counts.get(fabric, 0)
        name = f"equal-spine-divisibility[{leaf}]"
        if spines < 2:
            results.append(InvariantResult(
                Family.CAPACITY, name, Finding.UNMEASURED,
                f"fabric {fabric!r} has S={spines}; divisibility undefined below S>=2"))
        elif uplinks == 0:
            results.append(InvariantResult(
                Family.CAPACITY, name, Finding.UNMEASURED,
                "leaf declares no uplink allocation in this representation"))
        elif uplinks % spines == 0:
            results.append(InvariantResult(
                Family.CAPACITY, name, Finding.HOLDS,
                f"{uplinks} uplinks divide exactly across S={spines}"))
        else:
            results.append(InvariantResult(
                Family.CAPACITY, name, Finding.HNP_DEFECT,
                f"{uplinks} uplinks do not divide across S={spines} "
                f"(remainder {uplinks % spines})"))
    return results


# --- allocation / breakout identity ----------------------------------------

def check_zone_breakout_declared(zones: Sequence[Mapping[str, Any]]) -> list:
    """Every allocating zone declares a breakout option.

    A zone without one cannot yield deterministic parent+lane identity, which
    is the #620 C2 requirement the comparison representation depends on.
    """
    results = []
    for zone in zones:
        name = zone.get("zone_name", "<unnamed>")
        if zone.get("breakout_option"):
            results.append(InvariantResult(
                Family.ALLOCATION, f"zone-breakout-declared[{name}]", Finding.HOLDS,
                f"breakout_option={zone['breakout_option']}"))
        else:
            results.append(InvariantResult(
                Family.ALLOCATION, f"zone-breakout-declared[{name}]", Finding.HNP_DEFECT,
                "allocating zone declares no breakout_option; parent+lane identity "
                "cannot be derived"))
    return results


# --- redundancy / envelope --------------------------------------------------

def check_redundancy_group_declared(switch_classes: Sequence[Mapping[str, Any]]) -> list:
    """#246: a class declaring a redundancy type must name its group."""
    results = []
    for switch_class in switch_classes:
        cid = switch_class.get("switch_class_id", "<unnamed>")
        rtype = switch_class.get("redundancy_type")
        rgroup = switch_class.get("redundancy_group")
        name = f"redundancy-group-declared[{cid}]"
        if not rtype:
            results.append(InvariantResult(
                Family.REDUNDANCY, name, Finding.HOLDS, "no redundancy declared"))
        elif rgroup:
            results.append(InvariantResult(
                Family.REDUNDANCY, name, Finding.HOLDS, f"{rtype} -> {rgroup}"))
        else:
            results.append(InvariantResult(
                Family.REDUNDANCY, name, Finding.HNP_DEFECT,
                f"redundancy_type={rtype} without redundancy_group"))
    return results


# --- rail grouping: hypothesis, not contract -------------------------------

def check_rail_grouping(connections: Sequence[Mapping[str, Any]]) -> InvariantResult:
    """#620 C5 / #661 family 6 -- deliberately NOT asserted as a contract.

    #661 states the rail-grouping property remains a named corpus enhancement
    until its harness assertion is accepted. Reporting HOLDS here would treat an
    unestablished property as proven, so this records observation only.
    """
    railed = [c for c in connections if c.get("rail") is not None]
    if not railed:
        return InvariantResult(
            Family.RAIL_GROUPING, "rail-grouping", Finding.UNMEASURED,
            "no rail-bearing connections in this case")
    return InvariantResult(
        Family.RAIL_GROUPING, "rail-grouping", Finding.HYPOTHESIS,
        f"{len(railed)} rail-bearing connections observed; grouping rule is not "
        f"yet an established contract (#620 C5) and is not asserted here")


def summarize(results: Sequence[InvariantResult]) -> dict:
    counts: dict = {}
    for result in results:
        counts[result.finding.value] = counts.get(result.finding.value, 0) + 1
    return counts
