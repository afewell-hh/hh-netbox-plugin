"""Host-side safe prover for #716. Test-only.

Replaces the prover that used four unverified `pkill -9 -f <tag>` calls --
the construct #716 names as prohibited, which I had used in the fixture for
a suite specifying its prohibition.

Ownership requires two independent sides to agree:

* a **creation registry** written here, before each launch, recording a
  per-launch nonce, the immutable container ID, and the expected argv;
* a **publication** written by the child from inside its own process,
  carrying the same nonce plus pid and start ticks.

Neither alone authorizes anything. A self-marked impostor has no registry
entry; a registry entry with no matching publication is unresolved.

Signalling happens only in `containment_rescue.py`, inside the container,
through a pinned pidfd. Teardown destroys only immutable container IDs this
prover recorded creating -- never a label query result, which is a claim
rather than proof of origin.

Order matters and is enforced: the rescue owner is installed and proven on
a disposable subject BEFORE any host-exec orphan is induced.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path


SHARED_PROJECT = "netbox-docker"
PUBLICATION_DIR = "/tmp/hh716_pub"
RESCUE_PATH = "/tmp/hh716_rescue.py"
UNKNOWN = "unknown"


@dataclass
class LaunchRecord:
    """What the prover created, written before the child can publish."""

    nonce: str
    sequence: int
    container_id: str
    expected_cmdline: str
    created_at: int


@dataclass
class Registry:
    run_id: str
    lane: str
    container_id: str
    launches: list = field(default_factory=list)
    containers: list = field(default_factory=list)

    def next_nonce(self):
        return f"{self.run_id}:{len(self.launches)}:{uuid.uuid4().hex[:8]}"


def in_scenario(container_id: str, argv, timeout=120, stdin=None, detach=False,
                env=None):
    """Exec inside the registered scenario container, addressed by its ID.

    Addressed by immutable ID, never by service name: a service name can be
    re-resolved to a recreated container, which is how a scenario loses
    track of what it owns.
    """
    if isinstance(argv, str):
        raise TypeError("argv must be a list")
    command = ["docker", "exec"]
    if stdin is not None:
        # Without -i the exec has no stdin, so a script reading it sees EOF
        # and exits non-zero. That made every rescue invocation return None,
        # which the prover recorded as a failed proof rather than as a
        # harness fault.
        command.append("-i")
    if detach:
        command.append("-d")
    for key, value in (env or {}).items():
        command += ["-e", f"{key}={value}"]
    command += [container_id, *argv]
    return subprocess.run(command, capture_output=True, text=True,
                          timeout=timeout, input=stdin)


def create_scenario_container(image: str, run_id: str, registry=None,
                              order=None):
    """Create -> register -> verify -> start, recording the order as it happens.

    Registration happens immediately after `docker create`, before anything
    else can fail. A previous version verified first and registered second,
    so a failed verification returned without registering a container that
    had already been created -- an orphan the registry could not name.

    `docker start` is wrapped: a timeout previously propagated out of this
    function and out of `main` before the try/finally was entered, so no
    evidence was written and the container was left running.
    """
    def note(event):
        # Snapshot the ACTUAL registry at each step. Hand-placed labels can
        # be left in position while the real `registry.containers.append`
        # moves after start, which the previous label-only control could
        # not detect. The snapshot makes the claim falsifiable: if
        # registration has not happened yet, the id is simply not here.
        if order is not None:
            order.append({
                "event": event,
                "at": time.time(),
                "registered_containers": list(
                    registry.containers if registry is not None else []),
            })

    try:
        created = subprocess.run(
            ["docker", "create", "--label", f"hh716.run={run_id}",
             image, "sleep", "3600"],
            capture_output=True, text=True, timeout=120)
    except (subprocess.SubprocessError, OSError) as exc:
        return None, f"create raised: {exc}"
    if created.returncode != 0:
        return None, f"create failed: {created.stderr.strip()[:160]}"
    container_id = created.stdout.strip()
    if len(container_id) < 64:
        return None, f"create returned a short id: {container_id!r}"
    note("create")

    # Register FIRST. Everything after this point is recoverable because the
    # registry can name what to destroy.
    if registry is not None:
        registry.containers.append(container_id)
    note("register")

    try:
        verified = subprocess.run(
            ["docker", "inspect", container_id, "--format",
             "{{.Id}} {{index .Config.Labels \"hh716.run\"}}"],
            capture_output=True, text=True, timeout=60)
    except (subprocess.SubprocessError, OSError) as exc:
        return None, f"inspect raised after create: {exc}"
    if verified.returncode != 0:
        return None, f"inspect failed: {verified.stderr.strip()[:160]}"
    got_id, _, got_run = verified.stdout.strip().partition(" ")
    if got_id != container_id or got_run != run_id:
        return None, f"identity mismatch: {got_id[:12]}/{got_run}"
    note("verify")

    try:
        started = subprocess.run(["docker", "start", container_id],
                                 capture_output=True, text=True, timeout=120)
    except (subprocess.SubprocessError, OSError) as exc:
        return None, f"start raised: {exc}"
    if started.returncode != 0:
        return None, f"start failed: {started.stderr.strip()[:160]}"
    note("start")
    return container_id, ""


def acquire_container_identity(lane: str):
    """The immutable 64-hex ID, frozen before anything is launched."""
    done = subprocess.run(
        ["docker", "inspect", f"{lane}-netbox-1", "--format", "{{.Id}}"],
        capture_output=True, text=True, timeout=60)
    if done.returncode != 0 or len(done.stdout.strip()) < 64:
        return None
    return done.stdout.strip()


def install_rescue_owner(container_id: str, source: Path):
    """Copy the rescue owner in. It, not this prover, does any signalling."""
    done = subprocess.run(
        ["docker", "cp", str(source), f"{container_id}:{RESCUE_PATH}"],
        capture_output=True, text=True, timeout=120)
    return done.returncode == 0


def launch_owned_subject(container_id: str, registry: Registry, marker: str,
                         order=None):
    """Launch a child in the scenario container that publishes its own identity.

    The published record carries pid, start ticks, PGID and SID -- all four
    are compared by exact equality later, and PGID/SID were named in the
    accepted design but absent from the first implementation.
    """
    nonce = registry.next_nonce()
    expected_argv = ["python3", "-c", "import time; time.sleep(900)", marker]
    # /proc/<pid>/stat field 2 is the parenthesised comm, so splitting the
    # whole line on whitespace misaligns every later index -- the first
    # version published start_ticks="(python3)2". Strip through the closing
    # paren first, exactly as the rescue owner does with rsplit(")", 1).
    # After the strip: $1 state, $2 ppid, $3 pgrp, $4 session, $20 starttime.
    script = (
        f"mkdir -p {PUBLICATION_DIR}; "
        f"stat=$(cat /proc/$$/stat); "
        f"set -- ${{stat#*) }}; "
        f"printf '%s' "
        f"\"{{\\\"nonce\\\":\\\"{nonce}\\\",\\\"pid\\\":$$,"
        f"\\\"start_ticks\\\":\\\"${{20}}\\\","
        f"\\\"pgid\\\":\\\"$3\\\",\\\"sid\\\":\\\"$4\\\"}}\" "
        f"> {PUBLICATION_DIR}/{nonce}.json; "
        f"exec python3 -c 'import time; time.sleep(900)' {marker}")
    # Register the launch BEFORE starting the child, for the same reason:
    # a child that starts and is then not recorded is unowned.
    registry.launches.append(asdict(LaunchRecord(
        nonce=nonce, sequence=len(registry.launches),
        container_id=container_id, expected_cmdline=" ".join(expected_argv),
        created_at=int(time.time()))))
    registry.launches[-1]["expected_argv"] = expected_argv
    if order is not None:
        order.append({"event": f"launch_register:{nonce}", "at": time.time(),
                      "registered_nonces": [l["nonce"] for l in registry.launches]})
    in_scenario(container_id, ["sh", "-c", script], detach=True,
                env={"HH716_NONCE": nonce})
    if order is not None:
        order.append({"event": f"launch_start:{nonce}", "at": time.time(),
                      "registered_nonces": [l["nonce"] for l in registry.launches]})
    return nonce


def read_publication(container_id: str, nonce: str):
    """The child's own claim. Absent or unreadable is UNKNOWN, not absent."""
    done = in_scenario(container_id, ["cat", f"{PUBLICATION_DIR}/{nonce}.json"])
    if done.returncode != 0:
        return None, f"publication unreadable: {done.stderr.strip()[:120]}"
    try:
        return json.loads(done.stdout), ""
    except ValueError as exc:
        return None, f"publication malformed: {exc}"


def run_rescue(container_id: str, entries, send_signal: bool):
    """Invoke the in-container rescue owner. Never signals from the host."""
    payload = json.dumps({"entries": entries, "send_signal": send_signal})
    done = in_scenario(container_id, ["python3", RESCUE_PATH], stdin=payload)
    if done.returncode != 0:
        return None, f"rescue owner failed: {done.stderr.strip()[:200]}"
    try:
        return json.loads(done.stdout), ""
    except ValueError as exc:
        return None, f"rescue output malformed: {exc}"


def bind(registry: Registry, publication):
    """Registry and publication must agree, or the entry is unresolved."""
    if not publication:
        return None, "no publication"
    nonce = publication.get("nonce")
    matching = [l for l in registry.launches if l["nonce"] == nonce]
    if len(matching) != 1:
        return None, f"nonce {nonce!r} matches {len(matching)} registry entries"
    launch = matching[0]
    if launch["container_id"] != registry.container_id:
        return None, "publication observed in a container the registry did not record"
    # expected_argv is what the rescue owner compares by exact equality. An
    # earlier edit to add it here silently failed to apply, so every entry
    # carried no expected argv and the rescue owner compared the real argv
    # against [] -- rejecting the legitimate subject on every run while the
    # adversaries were "correctly" rejected for the same wrong reason.
    return {**publication,
            "expected_cmdline": launch["expected_cmdline"],
            "expected_argv": launch.get("expected_argv", [])}, ""


NOT_FOUND_MARKERS = ("No such container", "No such object")


def _inspect_state(container_id: str):
    """'present' | 'absent' | 'unknown'.

    A nonzero `docker inspect` exit does not prove absence: a daemon
    failure, a timeout and a permission denial all exit nonzero too. Only a
    nonzero exit whose stderr explicitly reports the container is unknown to
    the daemon counts as confirmed absence; everything else is UNKNOWN.
    """
    try:
        done = subprocess.run(["docker", "inspect", container_id],
                              capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        return "unknown", "inspect timed out"
    except OSError as exc:
        return "unknown", f"inspect could not run: {exc}"
    if done.returncode == 0:
        return "present", ""
    stderr = done.stderr or ""
    # The diagnostic must name THIS container. A daemon message mentioning
    # some other id would otherwise be accepted as proof of our absence.
    # The full id only. A 12-character prefix is not unique: another
    # container sharing those leading characters would have satisfied it.
    names_this = container_id in stderr
    if any(marker in stderr for marker in NOT_FOUND_MARKERS) and names_this:
        return "absent", stderr.strip()[:120]
    if any(marker in stderr for marker in NOT_FOUND_MARKERS):
        return "unknown", ("not-found diagnostic did not name this container: "
                           + stderr.strip()[:100])
    return "unknown", f"inspect exited {done.returncode}: {stderr.strip()[:120]}"


def teardown_registered_containers(registry: Registry):
    """Destroy exactly the immutable IDs this prover recorded creating.

    Not a label query. A label is a claim: anything can wear one, so a
    filter result is a set of candidates, never a licence to destroy. Any
    candidate found by label that is not in the registry is reported
    unregistered -- neither destroyed nor ignored.
    """
    if not registry.containers:
        # An empty registry is not a successful teardown. The previous
        # version iterated nothing, found no failures, and returned
        # proved=True -- a teardown that destroyed nothing reporting success.
        return {"destroyed": [], "failed": [], "proved": False,
                "outcome": UNKNOWN,
                "reason": "no immutable container ID was registered; teardown "
                          "cannot be proved against an empty registry"}
    destroyed, failed, unknown = [], [], []
    for container_id in registry.containers:
        # A registered ID that is absent BEFORE teardown is not a success.
        # The registry asserts this prover created it; if the daemon has
        # never heard of it, the two disagree and that is UNKNOWN. Without
        # this, an ID that never existed read as "destroyed" -- which is how
        # the failure control reported proved=True.
        state, _ = _inspect_state(container_id)
        if state != "present":
            unknown.append(container_id)
            continue
        try:
            subprocess.run(["docker", "rm", "-f", container_id],
                           capture_output=True, text=True, timeout=120)
        except (subprocess.SubprocessError, OSError) as exc:
            # A cleanup exception must become UNKNOWN, not escape the
            # teardown and prevent the evidence from being written at all.
            unknown.append({"id": container_id, "why": f"remove raised: {exc}"})
            continue
        # `docker rm -f` exits 0 even for a container that does not exist,
        # so its status proves nothing. Measured: removing an absent
        # all-zeros ID returns 0 with "No such container" on stderr. Absence
        # is therefore confirmed by inspection, not by the remove's exit code.
        state, detail = _inspect_state(container_id)
        if state == "absent":
            destroyed.append(container_id)
        elif state == "present":
            failed.append(container_id)
        else:
            unknown.append({"id": container_id, "why": detail})
    # Only a verified-absent set counts. Anything unverifiable is UNKNOWN,
    # which is not a successful teardown.
    proved = bool(destroyed) and not failed and not unknown
    return {"destroyed": destroyed, "failed": failed, "unknown": unknown,
            "proved": proved,
            "outcome": "destroyed" if proved else UNKNOWN}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--netbox-docker", type=Path, required=True)
    parser.add_argument("--lane", required=True)
    parser.add_argument("--image", default="netbox:latest-plugins-dev")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--force-rescue-unproven", action="store_true",
        help="deliberately fail the rescue proof, evidencing that nothing "
             "downstream of it proceeds")
    args = parser.parse_args(argv)

    if not args.lane or args.lane == SHARED_PROJECT:
        print(f"refusing lane {args.lane!r}: shared stack", file=sys.stderr)
        return 2

    run_id = uuid.uuid4().hex
    docker_version = subprocess.run(
        ["docker", "version", "--format", "{{.Server.Version}}"],
        capture_output=True, text=True, timeout=60).stdout.strip()

    evidence = {"version": 3, "step": "B1a", "lane": args.lane,
                "environment": {
                    "docker_server_version": docker_version,
                    "rm_f_exit_on_absent_container": 0,
                    "rm_f_note": "Observed in THIS environment only: "
                                 "`docker rm -f <absent id>` exits 0 with "
                                 "'No such container' on stderr. Absence is "
                                 "therefore confirmed by inspection, not by "
                                 "the remove's exit status. Not asserted as "
                                 "universal Docker behaviour.",
                },
                "run_id": run_id, "observed_at": int(time.time()),
                "lane_dirty": False, "dirty_reasons": [],
                "host_kill_baseline_attempted": False}

    def mark_dirty(reason):
        evidence["lane_dirty"] = True
        evidence["dirty_reasons"].append(reason)

    # ---- B1a.1: scenario-owned container, created and registered before use
    registry = Registry(run_id=run_id, lane=args.lane, container_id="")
    lifecycle = []
    evidence["lifecycle_order"] = lifecycle
    container_id, why = create_scenario_container(args.image, run_id, registry,
                                                  lifecycle)
    registry.container_id = container_id or ""
    if not container_id:
        mark_dirty(f"scenario container unavailable: {why}")
        evidence["registry"] = asdict(registry)
        evidence["teardown"] = teardown_registered_containers(registry)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True))
        print(f"wrote {args.output} (dirty=True, no scenario container)")
        return 4
    evidence["container_id"] = container_id

    try:
        rescue_source = Path(__file__).resolve().parent / "containment_rescue.py"
        if not install_rescue_owner(container_id, rescue_source):
            mark_dirty("rescue owner could not be installed")
            evidence["rescue_owner_ready"] = False
        else:
            evidence["rescue_owner_ready"] = True

            # ---- B1a.6: rescue owner proven before anything else ----
            nonce = launch_owned_subject(container_id, registry, "rescueproof",
                                             lifecycle)
            time.sleep(2)
            publication, why = read_publication(container_id, nonce)
            bound, bind_why = bind(registry, publication)
            if not bound:
                mark_dirty(f"rescue proof unbound: {why or bind_why}")
            else:
                verified, _ = run_rescue(container_id, [bound], False)
                evidence["verifies_without_signalling"] = verified

                # ---- B1a.3: adversaries that must NOT verify ----
                # Each adversary mutates EXACTLY ONE identity field and
                # leaves every other field valid. Without that, a rejection
                # could come from any of several faults and would not
                # demonstrate the specific check.
                adversaries_expect = {
                    "nonce_prefix": "nonce_exact",
                    "nonce_superstring": "nonce_exact",
                    "argv_substring": "argv_exact",
                    "wrong_pgid": "pgid_exact",
                    "wrong_sid": "sid_exact",
                    "wrong_start_ticks": "start_ticks",
                }
                adversaries = {
                    "nonce_prefix": {**bound, "nonce": bound["nonce"][:-2]},
                    "nonce_superstring": {**bound,
                                          "nonce": bound["nonce"] + "XY"},
                    "argv_substring": {
                        **bound,
                        "expected_argv": (bound.get("expected_argv") or [])[:1]},
                    "wrong_pgid": {**bound, "pgid": "999999"},
                    "wrong_sid": {**bound, "sid": "999999"},
                    "wrong_start_ticks": {**bound, "start_ticks": "1"},
                }
                rejected = {}
                for name, entry in adversaries.items():
                    report, _ = run_rescue(container_id, [entry], True)
                    record = report["reports"][0] if report else None
                    if record:
                        checks = record.get("checks") or {}
                        record["mutated_field"] = adversaries_expect[name]
                        record["failing_checks"] = sorted(
                            k for k, v in checks.items() if not v)
                        record["unrelated_fields_valid"] = (
                            record["failing_checks"] == [adversaries_expect[name]])
                    rejected[name] = record
                evidence["adversaries_rejected"] = rejected

                # ---- observation-error controls: UNKNOWN, never a result ----
                observation_errors = {}

                # (a) a subject that has already exited cannot be pinned.
                gone_nonce = launch_owned_subject(container_id, registry, "gonesoon",
                                                  lifecycle)
                time.sleep(2)
                gone_pub, _ = read_publication(container_id, gone_nonce)
                gone_bound, _ = bind(registry, gone_pub)
                if gone_bound:
                    run_rescue(container_id, [gone_bound], True)   # terminate it
                    time.sleep(1)
                    again, _ = run_rescue(container_id, [gone_bound], True)
                    observation_errors["already_exited"] = (
                        again["reports"][0] if again else None)

                # (b) a publication whose pid cannot be read at all.
                unreadable = {**bound, "pid": 999999}
                report, _ = run_rescue(container_id, [unreadable], True)
                observation_errors["unpinnable_pid"] = (
                    report["reports"][0] if report else None)

                # (c) a malformed publication.
                malformed = {**bound, "pid": "not-an-int"}
                report, _ = run_rescue(container_id, [malformed], True)
                observation_errors["malformed_pid"] = (
                    report["reports"][0] if report else None)
                evidence["observation_errors"] = observation_errors

                cleaned, _ = run_rescue(container_id, [bound], True)
                evidence["rescue_owner_proof"] = cleaned
                proven = (cleaned and cleaned["reports"][0]["outcome"]
                          in ("reaped", "terminated_zombie"))
                if args.force_rescue_unproven:
                    proven = False
                    mark_dirty("rescue proof deliberately forced unproven")
                if not proven:
                    mark_dirty("rescue owner could not clean its own subject")
                evidence["rescue_owner_proven"] = bool(proven)

        # B1a ends here. No host-exec termination, by construction.
        evidence["host_kill_baseline_attempted"] = False
        # ---- teardown-failure evidence, on a throwaway registry ----
        # Successful disposal alone does not show the failure path works.
        bogus = Registry(run_id=run_id, lane=args.lane, container_id="")
        bogus.containers.append("0" * 64)          # a well-formed, absent ID
        evidence["teardown_failure_control"] = teardown_registered_containers(bogus)
        empty = Registry(run_id=run_id, lane=args.lane, container_id="")
        evidence["teardown_empty_registry_control"] = (
            teardown_registered_containers(empty))
    finally:
        evidence["registry"] = asdict(registry)
        evidence["teardown"] = teardown_registered_containers(registry)
        if not evidence["teardown"]["proved"]:
            mark_dirty("registered container teardown could not be proved")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True),
                               encoding="utf-8")
        print(f"wrote {args.output} (dirty={evidence['lane_dirty']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
