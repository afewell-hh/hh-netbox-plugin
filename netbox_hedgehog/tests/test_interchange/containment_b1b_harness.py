"""Mocked harness that drives the REAL #716 B1b main()/preflight(). Test-only.

Exists because every previous B1b control was a source-position check, a
copied predicate, or an independent snippet. Dev B showed all eighteen
still passed when nonce validation was removed, start-identity comparison
disabled, and fixture registration commented out -- so none of them was
bound to behaviour.

This harness substitutes every Docker and in-container interaction with
scripted values and then calls the real entry points, so a mutation to the
implementation changes the control's result. No Docker, no containers, no
signals.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent


def load_b1b():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "hh716_b1b_under_test", _HERE / "containment_b1b.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["hh716_b1b_under_test"] = module
    spec.loader.exec_module(module)
    return module


class Completed:
    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


SCENARIO_ID = "a" * 64
DECOY_ID = "b" * 64
CHILD_PID = 4242
#: The readiness subject must be a DIFFERENT process from the baseline
#: child. Sharing a pid made preflight's readiness signal look like the
#: baseline's, so the post-kill probe reported the baseline child already
#: gone and the sound positive failed.
READINESS_PID = 1111
PARENT_PID = 4200
START_TICKS = "777777"


class FakeClient:
    """Stands in for the non-detached host exec client."""

    def __init__(self):
        self.pid = 99999
        self.returncode = None
        self.killed = False

    def kill(self):
        self.killed = True
        self.returncode = -9

    def communicate(self, timeout=None):
        return ("", "")

    def poll(self):
        return self.returncode


def install(b1b, *, published_child_nonce=None, published_parent_nonce=None,
            observed_start_ticks=None, scenario_id=SCENARIO_ID,
            after_kill_state="S", after_rescue_found=False,
            rescue_outcome="reaped", decoy_state_after_rescue="present"):
    """Patch every outward call of the module under test.

    Returns a dict of recorders so a control can assert what the real code
    did, not what a reimplementation would have done.
    """
    recorded = {"removed": [], "signalled": [], "bind_calls": []}

    def fake_run(argv, **kwargs):
        if not isinstance(argv, list):
            return Completed(returncode=1)
        text = " ".join(str(part) for part in argv)
        # The decoy carries a second label; the scenario container does not.
        if argv[:2] == ["docker", "create"]:
            return Completed(stdout=DECOY_ID if "hh716.fixture" in text
                             else scenario_id)
        if argv[:2] == ["docker", "start"]:
            return Completed()
        if argv[:2] == ["docker", "rm"]:
            recorded["removed"].append(argv[-1])
            return Completed()
        if argv[:2] == ["docker", "cp"]:
            return Completed()
        if argv[:2] == ["docker", "inspect"]:
            target = argv[2]
            # The verifying query must be answered BEFORE any id-specific
            # branch: a previous version let the decoy branch intercept it,
            # so create_scenario_container saw an identity mismatch and the
            # whole harness aborted in preflight.
            if "{{.Id}} {{index" in text:
                return Completed(stdout=f"{target} {b1b_run_id[0]}")
            if "com.docker.compose.project" in text:
                return Completed(stdout=lane_holder[0])
            if target in recorded["removed"]:
                return Completed(stderr=f"No such container: {target}",
                                 returncode=1)
            return Completed(stdout=target)
        if argv[:2] == ["docker", "ps"]:
            if "label=hh716.run=" in text:
                return Completed(
                    stdout=DECOY_ID[:12] + chr(10) + scenario_id[:12])
            if "name=netbox-docker-" in text:
                return Completed(stdout="")
            return Completed(stdout="someid")
        if argv[:1] == ["git"]:
            return Completed(stdout="/tmp/wt716b" if "toplevel" in text
                             else "/repo/.git/worktrees/x")
        return Completed()

    b1b_run_id = [""]
    lane_holder = ["diet716-mock"]

    def fake_in_scenario(container_id, argv, timeout=120, stdin=None,
                         detach=False, env=None):
        joined = " ".join(str(part) for part in argv)
        if "containment_rescue" in joined or "hh716_rescue" in joined:
            payload = json.loads(stdin or "{}")
            entries = payload.get("entries", [])
            recorded["bind_calls"].append(entries)
            send = payload.get("send_signal")
            if send:
                recorded["signalled"].append(entries)
            return Completed(stdout=json.dumps({"reports": [{
                "verified": True, "signalled": bool(send),
                "outcome": rescue_outcome if send else "verified_not_signalled",
                "nonce": entries[0].get("nonce") if entries else None,
                "pid": CHILD_PID, "reasons": []}]}))
        if argv and argv[0] == "cat":
            path = argv[1]
            nonce = Path(path).name.split(".")[0]
            if path.endswith(".parent.json"):
                return Completed(stdout=json.dumps({
                    "role": "exec_parent",
                    "nonce": published_parent_nonce or nonce,
                    "pid": PARENT_PID, "start_ticks": START_TICKS,
                    "pgid": str(PARENT_PID), "sid": str(PARENT_PID)}))
            if path.endswith(".child.json"):
                return Completed(stdout=json.dumps({
                    "role": "inner_child",
                    "nonce": published_child_nonce or nonce,
                    "pid": CHILD_PID, "ppid": str(PARENT_PID),
                    "start_ticks": START_TICKS,
                    "pgid": str(PARENT_PID), "sid": str(PARENT_PID)}))
            if path.endswith(".json"):   # read_publication's plain record
                return Completed(stdout=json.dumps(
                    {"nonce": nonce, "pid": READINESS_PID,
                     "start_ticks": START_TICKS, "pgid": "1", "sid": "1"}))
            return Completed(returncode=1, stderr="no such file")
        if argv and argv[0] == "python3" and "PROBE" not in joined:
            # The liveness probe. Keyed on whether the BASELINE child has
            # been signalled, not on whether anything has: preflight's
            # readiness subject signals first.
            ticks = (observed_start_ticks if observed_start_ticks is not None
                     else START_TICKS)
            baseline_signalled = any(
                entry.get("pid") == CHILD_PID
                for entries in recorded["signalled"] for entry in entries)
            if not baseline_signalled:
                return Completed(stdout=json.dumps(
                    {"found": True, "state": after_kill_state,
                     "start_ticks": ticks}))
            if after_rescue_found:
                return Completed(stdout=json.dumps(
                    {"found": True, "state": "S", "start_ticks": ticks}))
            return Completed(stdout=json.dumps({"found": False}))
        return Completed()

    b1b.subprocess.run = fake_run
    b1b.PROVER.in_scenario = fake_in_scenario
    b1b.PROVER.install_rescue_owner = lambda *a, **k: True
    b1b.launch_inner_subject_non_detached = (
        lambda *a, **k: (FakeClient(), ["python3", "-c", "x", "m"]))
    b1b.time.sleep = lambda *a, **k: None

    original_create = b1b.PROVER.create_scenario_container

    def fake_create(image, run_id, registry=None, order=None):
        b1b_run_id[0] = run_id
        return original_create(image, run_id, registry, order)

    b1b.PROVER.create_scenario_container = fake_create
    b1b.PROVER.subprocess.run = fake_run
    return recorded


def run_main(b1b, output, lane="diet716-mock"):
    return b1b.main(["--lane", lane, "--output", str(output)])
