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
    #: A real, reproducible finding whose attribution between HNP and the
    #: contract is genuinely open. Distinct from HNP_DEFECT: naming a side
    #: would decide a question #668 reserves for a governed amendment.
    UNRESOLVED = "attribution-unresolved"


@dataclass(frozen=True)
class InvariantResult:
    family: Family
    name: str
    finding: Finding
    detail: str

    @property
    def is_failure(self) -> bool:
        """Findings requiring triage. UNRESOLVED counts: it is a real finding
        awaiting a governed decision, not a clean result."""
        return self.finding in (
            Finding.HNP_DEFECT, Finding.CONTRACT_DEFECT, Finding.UNRESOLVED)


#: PlanSwitchClass.topology_mode value meaning Clos (TopologyModeChoices.SPINE_LEAF).
CLOS_MODE = "spine-leaf"


def collect_fabric_facts(switch_classes: Sequence[Mapping[str, Any]]) -> dict:
    """Reduce persisted switch-class records to the facts the invariants need.

    Declared-Clos fabrics are SEEDED at zero spines. Without that a fabric that
    declares Clos but carries no spine class never enters the collection at all,
    so ``check_clos_spine_cardinality`` emits nothing and S=0 -- the very case
    the invariant exists to catch -- is undetectable.

    A fabric is declared Clos when any of its classes sets
    ``topology_mode='spine-leaf'`` or carries the ``spine`` role. Seeding is
    keyed on the declaration, never on inferring intent from uplink counts,
    which #661 forbids.
    """
    fabric_classes: dict = {}
    for record in switch_classes:
        fabric_classes.setdefault(record["fabric_name"], []).append(record)

    spine_counts: dict = {}
    unknown_spine_fabrics: set = set()
    leaf_uplinks: dict = {}
    leaf_fabric: dict = {}

    for fabric, classes in fabric_classes.items():
        modes = {c.get("topology_mode") for c in classes if c.get("topology_mode")}
        roles = {c.get("hedgehog_role") for c in classes}
        if CLOS_MODE in modes or "spine" in roles:
            spine_counts[fabric] = 0

        for record in classes:
            quantity = record.get("quantity")
            if record.get("hedgehog_role") == "spine":
                if fabric in unknown_spine_fabrics:
                    continue
                if quantity is None:
                    # A fabric mixing known and unknown spine quantities has an
                    # UNKNOWN total; summing only the known ones would report a
                    # confident subtotal that could satisfy S>=2 on partial data.
                    unknown_spine_fabrics.add(fabric)
                    spine_counts[fabric] = None
                else:
                    spine_counts[fabric] = (spine_counts.get(fabric) or 0) + quantity
            else:
                leaf_uplinks[record["switch_class_id"]] = record.get("uplink_ports") or 0
                leaf_fabric[record["switch_class_id"]] = fabric

    return {
        "fabric_classes": fabric_classes,
        "spine_counts": spine_counts,
        "leaf_uplinks": leaf_uplinks,
        "leaf_fabric": leaf_fabric,
    }


# --- ledger reconciliation --------------------------------------------------

#: Every ledger entry must carry these, so a recorded finding names who decides,
#: where the triage lives, and what state it is in -- not just that it is known.
LEDGER_REQUIRED_FIELDS = ("finding", "detail_contains", "owner", "resolution", "provenance")

#: A recorded finding is pending a decision, or an accepted divergence with a
#: reason. There is deliberately no "ignored" state.
LEDGER_RESOLUTIONS = ("pending-governed-decision", "accepted-divergence")


def validate_ledger(known: Mapping[str, Mapping[str, Any]]) -> list:
    """Return structural problems in a findings ledger."""
    problems = []
    for name, entry in sorted(known.items()):
        for field_name in LEDGER_REQUIRED_FIELDS:
            if not str(entry.get(field_name, "")).strip():
                problems.append(f"{name}: missing or empty {field_name!r}")
        resolution = entry.get("resolution")
        if resolution and resolution not in LEDGER_RESOLUTIONS:
            problems.append(
                f"{name}: resolution {resolution!r} not one of {list(LEDGER_RESOLUTIONS)}")
    return problems


def reconcile_findings(failures: Sequence[InvariantResult],
                       known: Mapping[str, Mapping[str, Any]]) -> dict:
    """Compare observed failures against the ledger.

    Returns unrecorded, changed and stale sets. A ledger entry covers ONE
    specific finding -- classification and substance -- not an invariant name,
    so the same check failing differently is unrecorded rather than inherited.
    """
    observed = {failure.name for failure in failures}
    unrecorded = sorted(name for name in observed if name not in known)

    changed = []
    for failure in failures:
        entry = known.get(failure.name)
        if entry is None:
            continue
        if failure.finding.value != entry.get("finding"):
            changed.append(
                f"{failure.name}: classification {entry.get('finding')} -> "
                f"{failure.finding.value}")
        elif str(entry.get("detail_contains")) not in failure.detail:
            changed.append(
                f"{failure.name}: substance changed; expected to contain "
                f"{entry.get('detail_contains')!r}")

    stale = sorted(name for name in known if name not in observed)
    return {"unrecorded": unrecorded, "changed": sorted(changed), "stale": stale}


# --- topology family --------------------------------------------------------

def check_declared_family(fabric_classes: Mapping[str, Sequence[Mapping[str, Any]]]) -> list:
    """Each fabric declares exactly one family; silent substitution is forbidden.

    Evaluated PER FABRIC from persisted HNP state, not once over a whole source
    document. A plan may hold several fabrics with different families, and a
    single global verdict would let an under-declared fabric hide behind a
    well-declared one. Reading persisted PlanSwitchClass rows also keeps this an
    observation of HNP output rather than of the input YAML (#668).
    """
    results = []
    for fabric, classes in sorted(fabric_classes.items()):
        modes = {c.get("topology_mode") for c in classes if c.get("topology_mode")}
        roles = {c.get("hedgehog_role") for c in classes}
        name = f"declared-family[{fabric}]"
        if len(modes) > 1:
            results.append(InvariantResult(
                Family.TOPOLOGY_FAMILY, name, Finding.HNP_DEFECT,
                f"fabric declares conflicting topology modes: {sorted(modes)}"))
        elif "mesh" in modes:
            results.append(InvariantResult(
                Family.TOPOLOGY_FAMILY, name, Finding.HOLDS,
                "mesh declared explicitly"))
        elif CLOS_MODE in modes:
            results.append(InvariantResult(
                Family.TOPOLOGY_FAMILY, name, Finding.HOLDS,
                f"Clos declared explicitly via topology_mode={CLOS_MODE!r}"))
        elif "spine" in roles:
            results.append(InvariantResult(
                Family.TOPOLOGY_FAMILY, name, Finding.HOLDS,
                "Clos expressed via leaf/spine roles"))
        else:
            results.append(InvariantResult(
                Family.TOPOLOGY_FAMILY, name, Finding.UNRESOLVED,
                "neither an explicit topology_mode nor a spine role, so the family "
                "would be inferred, which #661 forbids. Attribution is open: the "
                "case may need to declare a capacity-bounded single-switch family, "
                "HNP may need to require one, or #661 may need to address "
                "single-class management fabrics. NOT decided here"))
    return results


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
            finding, detail = (Finding.UNRESOLVED,
                               "S=1 on a declared Clos fabric. #661 F2 requires "
                               "S>=2; HNP computes the capacity minimum. "
                               "Attribution between an HNP defect and a contract "
                               "gap is NOT decided here (#668 reserves contract "
                               "correction for a governed amendment)")
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
        spines = spine_counts.get(fabric)
        name = f"equal-spine-divisibility[{leaf}]"
        if spines is None:
            # Guard before any comparison: `None < 2` raises TypeError, which
            # would surface as a harness crash rather than an honest result.
            results.append(InvariantResult(
                Family.CAPACITY, name, Finding.UNMEASURED,
                f"fabric {fabric!r} spine quantity is not known; divisibility "
                f"cannot be evaluated"))
            continue
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
