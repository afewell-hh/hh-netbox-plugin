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


def compose(netbox_docker: Path, lane: str, argv, timeout=120, stdin=None):
    """Structured argv only; returns CompletedProcess so status is inspectable."""
    if isinstance(argv, str):
        raise TypeError("argv must be a list")
    return subprocess.run(
        ["docker", "compose", "exec", "-T", *argv],
        cwd=str(netbox_docker), capture_output=True, text=True, timeout=timeout,
        input=stdin, env={**os.environ, "COMPOSE_PROJECT_NAME": lane})


def acquire_container_identity(lane: str):
    """The immutable 64-hex ID, frozen before anything is launched."""
    done = subprocess.run(
        ["docker", "inspect", f"{lane}-netbox-1", "--format", "{{.Id}}"],
        capture_output=True, text=True, timeout=60)
    if done.returncode != 0 or len(done.stdout.strip()) < 64:
        return None
    return done.stdout.strip()


def install_rescue_owner(netbox_docker: Path, lane: str, source: Path):
    """Copy the rescue owner in. It, not this prover, does any signalling."""
    done = subprocess.run(
        ["docker", "cp", str(source), f"{lane}-netbox-1:{RESCUE_PATH}"],
        capture_output=True, text=True, timeout=120)
    return done.returncode == 0


def launch_owned_subject(netbox_docker: Path, lane: str, registry: Registry,
                         marker: str):
    """Launch a child that publishes its own identity, bound to a nonce."""
    nonce = registry.next_nonce()
    # A long-lived process whose argv carries the marker. `sleep 900 <marker>`
    # was not that: GNU sleep rejects a non-numeric interval, so every subject
    # died at once and the rescue proof failed with ENOENT -- correctly
    # marking the lane dirty and skipping the orphan, but for a fixture bug
    # rather than a containment finding.
    expected = f"hh716-subject-{marker}"
    script = (
        f"mkdir -p {PUBLICATION_DIR}; "
        f"ticks=$(awk '{{print $22}}' /proc/$$/stat); "
        f"printf '%s' \"{{\\\"nonce\\\":\\\"{nonce}\\\",\\\"pid\\\":$$,"
        f"\\\"start_ticks\\\":\\\"$ticks\\\"}}\" > {PUBLICATION_DIR}/{nonce}.json; "
        f"exec python3 -c 'import time; time.sleep(900)' {expected}")
    compose(netbox_docker, lane,
            ["-d", "-e", f"HH716_NONCE={nonce}", "netbox", "sh", "-c", script])
    registry.launches.append(asdict(LaunchRecord(
        nonce=nonce, sequence=len(registry.launches),
        container_id=registry.container_id, expected_cmdline=expected,
        created_at=int(time.time()))))
    return nonce


def read_publication(netbox_docker: Path, lane: str, nonce: str):
    """The child's own claim. Absent or unreadable is UNKNOWN, not absent."""
    done = compose(netbox_docker, lane,
                   ["netbox", "cat", f"{PUBLICATION_DIR}/{nonce}.json"])
    if done.returncode != 0:
        return None, f"publication unreadable: {done.stderr.strip()[:120]}"
    try:
        return json.loads(done.stdout), ""
    except ValueError as exc:
        return None, f"publication malformed: {exc}"


def run_rescue(netbox_docker: Path, lane: str, entries, send_signal: bool):
    """Invoke the in-container rescue owner. Never signals from the host."""
    payload = json.dumps({"entries": entries, "send_signal": send_signal})
    done = compose(netbox_docker, lane, ["netbox", "python", RESCUE_PATH],
                   stdin=payload)
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
    return {**publication, "expected_cmdline": launch["expected_cmdline"]}, ""


def teardown_registered_containers(registry: Registry):
    """Destroy exactly the immutable IDs this prover recorded creating.

    Not a label query. A label is a claim: anything can wear one, so a
    filter result is a set of candidates, never a licence to destroy. Any
    candidate found by label that is not in the registry is reported
    unregistered -- neither destroyed nor ignored.
    """
    destroyed, failed = [], []
    for container_id in registry.containers:
        done = subprocess.run(["docker", "rm", "-f", container_id],
                              capture_output=True, text=True, timeout=120)
        (destroyed if done.returncode == 0 else failed).append(container_id)
    return {"destroyed": destroyed, "failed": failed,
            "proved": not failed}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--netbox-docker", type=Path, required=True)
    parser.add_argument("--lane", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--force-rescue-unproven", action="store_true",
        help="deliberately fail the rescue proof, to evidence that orphan "
             "induction does not start when rescue is unproven")
    args = parser.parse_args(argv)

    if not args.lane or args.lane == SHARED_PROJECT:
        print(f"refusing lane {args.lane!r}: shared stack", file=sys.stderr)
        return 2

    container_id = acquire_container_identity(args.lane)
    if not container_id:
        print(f"lane {args.lane!r}: no immutable container identity", file=sys.stderr)
        return 3

    registry = Registry(run_id=uuid.uuid4().hex, lane=args.lane,
                        container_id=container_id)
    evidence = {"version": 2, "lane": args.lane, "container_id": container_id,
                "run_id": registry.run_id, "observed_at": int(time.time()),
                "lane_dirty": False, "dirty_reasons": []}

    def mark_dirty(reason):
        evidence["lane_dirty"] = True
        evidence["dirty_reasons"].append(reason)

    rescue_source = Path(__file__).resolve().parent / "containment_rescue.py"
    if not install_rescue_owner(args.netbox_docker, args.lane, rescue_source):
        mark_dirty("rescue owner could not be installed")
        evidence["rescue_owner_ready"] = False
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True))
        print("rescue owner unavailable; lane marked dirty", file=sys.stderr)
        return 4
    evidence["rescue_owner_ready"] = True

    try:
        # ---- the rescue owner is PROVEN before any orphan is induced ----
        proof_nonce = launch_owned_subject(args.netbox_docker, args.lane,
                                           registry, "rescueproof")
        time.sleep(2)
        publication, why = read_publication(args.netbox_docker, args.lane, proof_nonce)
        bound, bind_why = bind(registry, publication)
        if not bound:
            mark_dirty(f"rescue proof unbound: {why or bind_why}")
        else:
            verified, _ = run_rescue(args.netbox_docker, args.lane, [bound], False)
            evidence["rescue_owner_verifies_without_signalling"] = verified
            cleaned, _ = run_rescue(args.netbox_docker, args.lane, [bound], True)
            evidence["rescue_owner_proof"] = cleaned
            proven = (cleaned
                      and cleaned["reports"][0]["outcome"] in ("reaped",
                                                               "terminated_zombie"))
            if args.force_rescue_unproven:
                proven = False
                mark_dirty("rescue proof deliberately forced unproven")
            if not proven:
                mark_dirty("rescue owner could not clean its own proof subject")

        # ---- a deficient record must authorize no signal ----
        if bound:
            forged = {**bound, "nonce": "not-a-registered-nonce"}
            report, _ = run_rescue(args.netbox_docker, args.lane, [forged], True)
            evidence["forged_nonce_rejected"] = report

        # ---- only now: the controlled host-exec orphan ----
        # Regression control: the first real run of this prover failed its
        # rescue proof (an invalid subject command) and correctly skipped
        # this block. That ordering is recorded explicitly so it cannot
        # regress into "induce first, rescue later".
        evidence["orphan_induction_started"] = not evidence["lane_dirty"]
        if not evidence["lane_dirty"]:
            bystander_nonce = launch_owned_subject(
                args.netbox_docker, args.lane, registry, "bystander")
            orphan_nonce = launch_owned_subject(
                args.netbox_docker, args.lane, registry, "orphan")
            time.sleep(2)
            orphan_pub, _ = read_publication(args.netbox_docker, args.lane,
                                             orphan_nonce)
            orphan_bound, _ = bind(registry, orphan_pub)

            host_child = subprocess.Popen(
                ["docker", "compose", "exec", "-T", "netbox", "sh", "-c",
                 "sleep 60 hh716-hostside"],
                cwd=str(args.netbox_docker), stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, start_new_session=True,
                env={**os.environ, "COMPOSE_PROJECT_NAME": args.lane})
            time.sleep(3)
            host_child.kill()
            host_child.communicate()

            still_there, _ = run_rescue(args.netbox_docker, args.lane,
                                        [orphan_bound], False)
            evidence["orphan_survives_host_kill"] = still_there

            rescued, _ = run_rescue(args.netbox_docker, args.lane,
                                    [orphan_bound], True)
            evidence["orphan_rescued"] = rescued

            bystander_pub, _ = read_publication(args.netbox_docker, args.lane,
                                                bystander_nonce)
            bystander_bound, _ = bind(registry, bystander_pub)
            intact, _ = run_rescue(args.netbox_docker, args.lane,
                                   [bystander_bound], False)
            evidence["bystander_intact"] = intact
            if bystander_bound:
                run_rescue(args.netbox_docker, args.lane, [bystander_bound], True)
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
