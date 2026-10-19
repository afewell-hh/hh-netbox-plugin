"""#719 RED harness, not containment or an evidence producer.

The .source inputs are byte-for-byte reviewed code at REVIEWED_HEAD, never
daemon evidence. Only the safety tests and their pure diagnostic helper run.
The prover/rescue entry points are never invoked. Generated B1a-shaped JSON is
synthetic input to the original assertions, not an observation of the world.

The default subject is the reviewed, UNSPLIT class. Its missing-evidence and
freshness defects must remain RED. ``partition_model`` is solely a positive
control for the inventory/observer, using the original method objects unchanged;
it is not an installed split or an implementation of the future evidence gate.
"""

from __future__ import annotations

import hashlib
import json
import marshal
import os
from pathlib import Path
import subprocess
import sys
import time
import types
import uuid


REVIEWED_HEAD = "927d8b1d29b9d7b11e3bd52efe09d8b616ec8869"
SOURCE_DIR = Path(__file__).with_name("safety_g1_sources")
SOURCE_HASHES = {
    "test_containment_prover_safety.py": "7424bc428d027319c7707a54e7c0409996be9b091b2d25e2c15112365709b498",
    "containment_prover.py": "01ca71172dc1886b5193f928f4295a7c52ea9938f2001f8865b457e47e266722",
    "containment_rescue.py": "03501f189a33752df5302c3ed29e707fc6e6d4dc73be682d6041c8ac0c178029",
}
MODULE = "netbox_hedgehog.tests.test_interchange.test_containment_prover_safety"
ORIGINAL_CLASS = "ProverSafetyControls"
SOURCE_CLASS = "ProverSourceControls"
EVIDENCE_CLASS = "ProverB1aControls"

# Independent reviewed requirement baseline, not derived from candidate discovery.
# A coordinated deletion from the candidate declaration and implementation must
# still disagree with this baseline. Changes here require explicit issue review.
ROWS = (
    ("S01", "test_no_prohibited_cleanup_command_is_executed", "source"),
    ("S02", "test_the_prohibited_detector_actually_detects", "source"),
    ("S03", "test_the_host_prover_signals_only_its_own_host_side_exec", "source"),
    ("S04", "test_not_found_association_is_enforced_by_the_real_function", "source"),
    ("B01", "test_b1a_induces_no_host_kill_baseline", "b1a"),
    ("B02", "test_registration_precedes_start_in_recorded_state", "b1a"),
    ("B03", "test_every_adversary_mutates_exactly_one_field", "b1a"),
    ("B04", "test_a_sound_positive_is_paired_with_the_negatives", "b1a"),
    ("B05", "test_observation_errors_are_unknown_never_a_result", "b1a"),
    ("B06", "test_teardown_failure_and_empty_registry_do_not_prove", "b1a"),
    ("B07", "test_the_rm_f_observation_is_scoped_to_this_environment", "b1a"),
)


def identifier(method, obligation, *, partitioned=True):
    cls = (SOURCE_CLASS if obligation == "source" else EVIDENCE_CLASS)
    return f"{MODULE}.{cls if partitioned else ORIGINAL_CLASS}.{method}"


def declaration():
    return [dict(requirement=req, old=f"{MODULE}.{ORIGINAL_CLASS}.{method}",
                 new=identifier(method, kind), obligation=kind)
            for req, method, kind in ROWS]


def source_bytes(name):
    data = (SOURCE_DIR / (name + ".source")).read_bytes()
    if hashlib.sha256(data).hexdigest() != SOURCE_HASHES[name]:
        raise AssertionError(f"reviewed source changed: {name}")
    return data


def reviewed_codes():
    """Compile, without executing, to derive expected callable identities.

    Stable virtual filename permits cross-process comparison on this runtime.
    The trusted parent reads the pinned source, not child-supplied digests.
    """
    code = compile(source_bytes("test_containment_prover_safety.py"),
                   "hh719-reviewed-safety", "exec")
    cls = next(c for c in code.co_consts
               if isinstance(c, types.CodeType) and c.co_name == ORIGINAL_CLASS)
    return {c.co_name: hashlib.sha256(marshal.dumps(c)).hexdigest()
            for c in cls.co_consts if isinstance(c, types.CodeType)
            and c.co_name.startswith("test_")}


def validate_inventory(candidate, discovered):
    """Independent test guard. No daemon evidence or test-class setup needed."""
    if (len(candidate) != len(declaration())
            or sorted(candidate, key=lambda r: r["requirement"]) !=
            sorted(declaration(), key=lambda r: r["requirement"])):
        raise AssertionError("requirement declaration differs from reviewed baseline")
    expected = [r["new"] for r in declaration()]
    if len(discovered) != len(set(discovered)):
        raise AssertionError("duplicate discovered test ID")
    if set(discovered) != set(expected):
        raise AssertionError(f"discovery/mapping mismatch: missing={sorted(set(expected)-set(discovered))}; "
                             f"extra={sorted(set(discovered)-set(expected))}")


def synthetic_b1a(context):
    """In-memory fixture only. No stored/live evidence is read or generated."""
    cid = "a" * 64
    nonce = "fixture-subject"
    fields = ("nonce_exact", "nonce_exact", "argv_exact", "pgid_exact",
              "sid_exact", "start_ticks")
    return {
        "schema": "hh719.synthetic-b1a/1", "mode": "fixture", "status": "complete",
        "run_id": context["run_id"], "head": context["head"],
        "observed_at": context["now"], "lane": "fixture-only",
        "container_id": cid, "host_kill_baseline_attempted": False,
        "lifecycle_order": [
            {"event": event, "registered_containers": [] if event == "create" else [cid]}
            for event in ("create", "register", "verify", "start")
        ] + [{"event": f"{event}:{nonce}", "registered_nonces": [nonce]}
             for event in ("launch_pre_exec", "launch_start")],
        "registry": {"containers": [cid]},
        "adversaries_rejected": {
            f"fixture-{index}": {"verified": False, "signalled": False,
                                 "unrelated_fields_valid": True,
                                 "mutated_field": name, "failing_checks": [name]}
            for index, name in enumerate(fields)
        },
        "verifies_without_signalling": {"reports": [{"verified": True, "signalled": False}]},
        "rescue_owner_proven": True,
        "observation_errors": {key: {"outcome": "unknown", "signalled": False}
                               for key in ("already_exited", "unpinnable_pid", "malformed_pid")},
        "teardown": {"proved": True},
        "teardown_failure_control": {"proved": False, "outcome": "unknown"},
        "teardown_empty_registry_control": {"proved": False},
        "environment": {"docker_server_version": "SYNTHETIC-NOT-A-DAEMON",
                        "rm_f_note": "fixture only; not asserted as universal"},
    }


def invoke_probe(*, partition_model=False, evidence="fresh", mutation=None):
    """Separate child interpreter; supervisor is this parent, inside test lane.

    Parent owns expected run/source identities. Child tracing and runner share
    an interpreter/import graph: this is NOT independent execution attestation.
    Parent process isolation protects transport/binding, not that shared failure.
    """
    context = {"run_id": uuid.uuid4().hex, "head": REVIEWED_HEAD, "now": time.time()}
    payload = None if evidence == "missing" else synthetic_b1a(context)
    if evidence == "stale":
        payload["observed_at"] -= 3601
    elif evidence == "future":
        payload["observed_at"] += 60
    elif evidence == "wrong-run":
        payload["run_id"] = "different-run"
    elif evidence == "wrong-head":
        payload["head"] = "0" * 40
    elif evidence == "partial":
        payload["status"] = "partial"
    request = dict(context=context, payload=payload, partition_model=partition_model,
                   mutation=mutation)
    done = subprocess.run(
        [sys.executable, "-m", "netbox_hedgehog.tests.test_interchange.safety_g1_probe"],
        input=json.dumps(request), capture_output=True, text=True, timeout=45,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    if done.returncode:
        raise AssertionError(f"observer child failed ({done.returncode}): {done.stderr[-2000:]}")
    try:
        report = json.loads(done.stdout)
    except ValueError as exc:
        raise AssertionError("observer stream missing/corrupt") from exc
    return context, report


def reconcile(context, report, *, partitioned, missing=False):
    """Validate independent expectations, trace entries and runner outcomes.

    This test oracle validates records acquired by the harness, not live facts.
    Inventory failure is separate: historic unsplit execution is also measured.
    No 'success' result is inferred from a receipt alone.
    """
    if report.get("context") != context or report.get("complete") is not True:
        raise AssertionError("unbound or incomplete observer stream")
    if report.get("observer") != "in-process-profile/1;shared-interpreter":
        raise AssertionError("missing or misrepresented observer")
    if report.get("observer_intact") is not True:
        raise AssertionError("observer disabled or replaced")
    expected = {identifier(m, k, partitioned=partitioned): reviewed_codes()[m]
                for _, m, k in ROWS}
    discovered = report["discovered"]
    if len(discovered) != len(set(discovered)) or set(discovered) != set(expected):
        raise AssertionError("undiscovered/extra/duplicate ID")
    entries = report["entries"]
    entered = [e["id"] for e in entries]
    if len(entered) != len(set(entered)):
        raise AssertionError("duplicate body entry")
    for entry in entries:
        if entry["id"] not in expected or entry["code"] != expected[entry["id"]]:
            raise AssertionError("unreviewed callable entry")
    outcomes = report["outcomes"]
    receipts = report["receipts"]
    if receipts != outcomes:
        raise AssertionError("adapter receipt disagrees with runner result")
    if len(outcomes) != len({e["id"] for e in outcomes}):
        raise AssertionError("duplicate terminal receipt")
    if set(entered) != {e["id"] for e in outcomes}:
        raise AssertionError("receipt without body or body without terminal result")
    target = {identifier(m, k, partitioned=partitioned) for _, m, k in ROWS
              if not missing or (partitioned and k == "source")}
    if set(entered) != target:
        raise AssertionError("expected body set did not execute")
    if any(e["outcome"] != "success" for e in outcomes):
        raise AssertionError("runner did not report success")
    if missing:
        cls = EVIDENCE_CLASS if partitioned else ORIGINAL_CLASS
        wanted = f"setUpClass ({MODULE}.{cls})"
        if len(report["setup_errors"]) != 1 or report["setup_errors"][0]["id"] != wanted:
            raise AssertionError("missing evidence was not an attributable class error")
        if "HH716_B1A_EVIDENCE is unset" not in report["setup_errors"][0]["error"]:
            raise AssertionError("unrelated setup failure")
        if report["successful"]:
            raise AssertionError("missing evidence became success")
    elif report["setup_errors"] or not report["successful"]:
        raise AssertionError("fresh fixture did not finish successfully")
