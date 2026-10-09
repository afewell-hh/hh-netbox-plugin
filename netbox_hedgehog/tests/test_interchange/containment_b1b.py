"""#716 B1b: the single controlled host-exec orphan baseline. Test-only.

One purpose: deliberately create an orphan in a disposable scenario
container in order to demonstrate the B1a-reviewed rescue path on it. Not a
general driver run.

It reuses B1a's accepted primitives rather than reimplementing them, so the
reviewed verification and teardown are the ones exercised here.

Two properties the first (invalidated) baseline lacked:

* the inner subject is launched by the SAME single non-detached
  `docker compose exec` that is later terminated, so its survival is
  attributable to that termination. The earlier version launched a detached
  subject and killed an unrelated exec.
* the child publishes its inner parent/child relationship, so "this is the
  child of the exec we killed" is evidence rather than assumption.

Every preflight item must be present and verified. If any is absent,
stale, mismatched or unknown, the subject is never launched.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

_HERE = Path(__file__).resolve().parent


def _load(name):
    import importlib.util
    spec = importlib.util.spec_from_file_location(f"hh716_{name}", _HERE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"hh716_{name}"] = module
    spec.loader.exec_module(module)
    return module


PROVER = _load("containment_prover")
UNKNOWN = "unknown"
PUBLICATION_DIR = PROVER.PUBLICATION_DIR
# The decoy must wear the run's ACTUAL label value. A first version used a
# distinct value ("copied-label-decoy"), which a label-discovery destroyer
# filtering on hh716.run=<run_id> would never have selected -- so it tested
# nothing about same-label discrimination. It is the identical label, plus
# deliberate absence from the registry, that makes it a trap.


def preflight(image, lane, run_id, evidence):
    """Every item verified before anything is launched. Abort on any unknown."""
    checks = {}

    checks["dedicated_lane"] = lane not in ("netbox-docker", "")
    checks["worktree"] = (_HERE.parents[2].name.startswith("wt")
                          or "wt716" in str(_HERE))

    container_id, why = PROVER.create_scenario_container(
        image, run_id, registry=None, order=None)
    checks["scenario_container_created"] = bool(container_id)
    if not container_id:
        evidence["preflight_failure"] = f"scenario container: {why}"
        return None, None, checks

    state, detail = PROVER._inspect_state(container_id)
    checks["container_present_and_identified"] = state == "present"
    checks["immutable_id_is_64_hex"] = len(container_id) == 64

    # The scenario must not target shared resources.
    shared = subprocess.run(
        ["docker", "ps", "-q", "--filter", "name=netbox-docker-"],
        capture_output=True, text=True, timeout=60).stdout.split()
    checks["no_shared_target"] = container_id not in shared

    rescue_ready = PROVER.install_rescue_owner(
        container_id, _HERE / "containment_rescue.py")
    checks["rescue_owner_ready"] = rescue_ready

    # A live unrelated bystander, and an unregistered decoy wearing a copied
    # label, both independently identified as NOT owned by this run.
    bystander = subprocess.run(
        ["docker", "run", "-d", "--label", f"hh716.run={run_id}",
         image, "sleep", "600"],
        capture_output=True, text=True, timeout=180)
    decoy_id = bystander.stdout.strip()
    checks["same_label_decoy_live"] = len(decoy_id) >= 12
    checks["decoy_is_not_registered"] = decoy_id != container_id

    # Prove the decoy really is selectable by label, or it is not a trap.
    discovered = subprocess.run(
        ["docker", "ps", "-q", "--filter", f"label=hh716.run={run_id}"],
        capture_output=True, text=True, timeout=60).stdout.split()
    short = {entry[:12] for entry in discovered}
    checks["label_discovery_would_select_decoy"] = decoy_id[:12] in short
    checks["label_discovery_selects_more_than_registered"] = len(short) > 1

    evidence["preflight"] = {
        "checks": checks,
        "label_discovery_candidates": sorted(short) if 'short' in dir() else [],
        "container_id": container_id,
        "decoy_container_id": decoy_id,
        "lane": lane,
        "run_id": run_id,
        "observation_deadline_seconds": 180,
    }
    return container_id, decoy_id, checks


def launch_inner_subject_non_detached(container_id, run_id, nonce, marker):
    """ONE non-detached exec which itself launches the registered inner child.

    The exec'd shell publishes its own identity, spawns the inner subject,
    publishes the child's identity including its ppid, then waits. Because
    the exec is not detached, the host holds a client process -- the exact
    one that gets terminated.
    """
    expected_argv = ["python3", "-c", "import time; time.sleep(900)", marker]
    script = (
        f"mkdir -p {PUBLICATION_DIR}; "
        f"pstat=$(cat /proc/$$/stat); set -- ${{pstat#*) }}; "
        f"printf '%s' \"{{\\\"role\\\":\\\"exec_parent\\\",\\\"nonce\\\":\\\"{nonce}\\\","
        f"\\\"pid\\\":$$,\\\"start_ticks\\\":\\\"${{20}}\\\","
        f"\\\"pgid\\\":\\\"$3\\\",\\\"sid\\\":\\\"$4\\\"}}\" "
        f"> {PUBLICATION_DIR}/{nonce}.parent.json; "
        f"python3 -c 'import time; time.sleep(900)' {marker} & "
        f"child=$!; "
        f"cstat=$(cat /proc/$child/stat); set -- ${{cstat#*) }}; "
        f"printf '%s' \"{{\\\"role\\\":\\\"inner_child\\\",\\\"nonce\\\":\\\"{nonce}\\\","
        f"\\\"pid\\\":$child,\\\"ppid\\\":\\\"$2\\\","
        f"\\\"start_ticks\\\":\\\"${{20}}\\\",\\\"pgid\\\":\\\"$3\\\","
        f"\\\"sid\\\":\\\"$4\\\"}}\" "
        f"> {PUBLICATION_DIR}/{nonce}.child.json; "
        f"wait")
    client = subprocess.Popen(
        ["docker", "exec", "-e", f"HH716_NONCE={nonce}", container_id,
         "sh", "-c", script],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    return client, expected_argv


def read_json_in(container_id, path):
    done = PROVER.in_scenario(container_id, ["cat", path])
    if done.returncode != 0:
        return None, f"unreadable: {done.stderr.strip()[:120]}"
    try:
        return json.loads(done.stdout), ""
    except ValueError as exc:
        return None, f"malformed: {exc}"


def alive_in(container_id, pid):
    """TRUE/FALSE/UNKNOWN for a pid, excluding zombies from 'alive'."""
    done = PROVER.in_scenario(
        container_id,
        ["sh", "-c", f"cat /proc/{int(pid)}/stat 2>/dev/null || echo MISSING"])
    text = done.stdout.strip()
    if done.returncode != 0:
        return UNKNOWN, f"probe exited {done.returncode}"
    if text == "MISSING" or not text:
        return "false", "no process entry"
    try:
        state = text.rsplit(")", 1)[1].split()[0]
    except IndexError:
        return UNKNOWN, f"unparseable stat: {text[:60]}"
    if state == "Z":
        return "false", "terminated (zombie: entry remains, not executing)"
    return "true", f"state={state}"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lane", required=True)
    parser.add_argument("--image", default="netbox:latest-plugins-dev")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    run_id = uuid.uuid4().hex
    started_at = time.time()
    evidence = {"step": "B1b", "lane": args.lane, "run_id": run_id,
                "observed_at": int(started_at), "lane_dirty": False,
                "dirty_reasons": [], "timing": {}}

    def dirty(reason):
        evidence["lane_dirty"] = True
        evidence["dirty_reasons"].append(reason)

    container_id, decoy_id, checks = preflight(
        args.image, args.lane, run_id, evidence)

    def finish(code):
        evidence["timing"]["total_seconds"] = round(time.time() - started_at, 1)
        # Reconcile and dispose only registered scenario resources, by exact ID.
        disposal = {}
        # Fixture disposal, by exact ID, AFTER evidence capture. Distinct
        # from the rescue path, which must never have touched the decoy.
        for label, cid in (("scenario_registered", container_id),
                           ("decoy_unregistered_fixture_cleanup", decoy_id)):
            if not cid:
                continue
            removed = subprocess.run(["docker", "rm", "-f", cid],
                                     capture_output=True, text=True, timeout=120)
            state, detail = PROVER._inspect_state(cid)
            disposal[label] = {"id": cid, "state_after": state, "detail": detail}
            if state != "absent":
                dirty(f"{label} resource {cid[:12]} not verifiably disposed")
        evidence["disposal"] = disposal
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True),
                               encoding="utf-8")
        print(f"wrote {args.output} (dirty={evidence['lane_dirty']})")
        return code

    if not container_id or not all(checks.values()):
        failed = [name for name, ok in checks.items() if not ok]
        dirty(f"preflight incomplete: {failed}")
        print(f"PREFLIGHT FAILED {failed}; subject never launched", file=sys.stderr)
        return finish(3)
    evidence["preflight_passed"] = True

    nonce = f"{run_id}:0:{uuid.uuid4().hex[:8]}"
    marker = f"hh716b1b-{nonce.split(':')[-1]}"

    # --- one non-detached exec, which launches the registered inner child ---
    launch_at = time.time()
    client, expected_argv = launch_inner_subject_non_detached(
        container_id, run_id, nonce, marker)
    evidence["host_client_pid"] = client.pid
    evidence["expected_argv"] = expected_argv

    deadline = launch_at + evidence["preflight"]["observation_deadline_seconds"]
    parent = child = None
    while time.time() < deadline:
        parent, _ = read_json_in(container_id, f"{PUBLICATION_DIR}/{nonce}.parent.json")
        child, _ = read_json_in(container_id, f"{PUBLICATION_DIR}/{nonce}.child.json")
        if parent and child:
            break
        time.sleep(2)
    evidence["timing"]["publication_seconds"] = round(time.time() - launch_at, 1)

    if not (parent and child):
        dirty("publication did not appear before the observation deadline")
        client.kill(); client.communicate()
        return finish(4)

    evidence["publication"] = {"parent": parent, "child": child}
    # Inner parent/child relationship must be real, not assumed.
    if str(child.get("ppid")) != str(parent.get("pid")):
        dirty(f"child ppid {child.get('ppid')} is not the exec parent "
              f"{parent.get('pid')}")
        client.kill(); client.communicate()
        return finish(5)
    evidence["inner_parent_child_verified"] = True

    # --- verify with the B1a rescue owner BEFORE terminating anything ---
    entry = {"nonce": nonce, "pid": child["pid"],
             "start_ticks": child["start_ticks"], "pgid": child["pgid"],
             "sid": child["sid"], "expected_argv": expected_argv}
    verified, why = PROVER.run_rescue(container_id, [entry], False)
    evidence["pre_termination_verification"] = verified or {"error": why}
    if not verified or not verified["reports"][0]["verified"]:
        dirty("ownership not verified before termination")
        client.kill(); client.communicate()
        return finish(6)

    # --- terminate the exact host-side compose-exec client ---
    kill_at = time.time()
    client.kill()
    client.communicate()
    evidence["timing"]["host_client_terminated_after_seconds"] = round(
        kill_at - launch_at, 1)
    evidence["host_client_returncode"] = client.returncode
    time.sleep(3)

    # --- the defect: host-client termination does not PROPAGATE inward ---
    # Stated carefully. The child's survival is not *caused* by the
    # termination; it would have run on regardless. What this shows is that
    # terminating the host-side client did not terminate its own inner
    # child -- the kill failed to cross the container boundary.
    state, detail = alive_in(container_id, child["pid"])
    evidence["inner_subject_after_host_kill"] = {
        "alive": state, "detail": detail,
        "claim": "host-client termination did not propagate to its inner "
                 "child; survival is not caused by the termination",
    }
    if state == UNKNOWN:
        dirty("could not determine whether the inner subject survived")
        return finish(7)
    if state != "true":
        dirty("the inner subject did not survive host termination; this "
              "baseline does not demonstrate the defect it claims")
        return finish(8)

    # --- rescue, via the B1a verified exact-ID/pidfd path only ---
    rescued, why = PROVER.run_rescue(container_id, [entry], True)
    evidence["rescue"] = rescued or {"error": why}
    if not rescued:
        dirty(f"rescue owner failed: {why}")
        return finish(9)
    report = rescued["reports"][0]
    if report["outcome"] not in ("reaped", "terminated_zombie"):
        dirty(f"rescue outcome {report['outcome']!r} is not a cleanup")
        return finish(10)

    after, after_detail = alive_in(container_id, child["pid"])
    evidence["owned_membership_after_rescue"] = {"alive": after,
                                                 "detail": after_detail}
    if after == UNKNOWN:
        dirty("survivor state unknown after rescue")
        return finish(11)
    if after != "false":
        dirty("an owned member survived the rescue")
        return finish(12)

    # --- the same-label, unregistered decoy must survive the rescue ---
    decoy_state, decoy_detail = PROVER._inspect_state(decoy_id)
    evidence["same_label_decoy_after_rescue"] = {
        "state": decoy_state, "detail": decoy_detail,
        "label": f"hh716.run={run_id}",
        "note": "identical label to the registered scenario container, and "
                "absent from the registry; survives because disposal goes by "
                "exact registered ID, not by label discovery",
    }
    if decoy_state != "present":
        dirty("an unregistered same-label resource was destroyed by the "
              "rescue path")
        return finish(13)

    evidence["baseline_complete"] = True
    return finish(0)


if __name__ == "__main__":
    raise SystemExit(main())
