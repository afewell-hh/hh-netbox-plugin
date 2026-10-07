"""Host-side prover for the #716 containment contract. Test-only.

Runs on the host, like `scripts/prove_reaper_lane.py` and the #711 driver.
It performs every Docker observation and publishes bound facts; the
container-side rows consume those facts and never touch Docker.

That split is not convenience. Dev B ruled out granting the inner Django
container a Docker socket on #711, and a first version of this suite did
exactly that -- mounted the socket and called `docker inspect` from inside
the test container. It failed on a missing binary, which was the lucky
outcome: had the image carried a docker CLI, it would have worked and
quietly violated the constraint.

Nothing here exercises #711's unsafe pre-acknowledgement path. The baseline
subject is this prover's own disposable child in a dedicated lane.
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


SUBJECT_TAG = "HH716_OWNED_SUBJECT"
BYSTANDER_TAG = "HH716_UNRELATED_BYSTANDER"
#: Deliberately NOT a superstring of SUBJECT_TAG. A first version named this
#: `{SUBJECT_TAG}_HOSTSIDE`, so a substring grep counted both populations and
#: the baseline read "1 before, 2 after" -- true, but conflating the subject
#: with the thing under test.
HOSTKILLED_TAG = "HH716_HOSTKILLED_CHILD"
SHARED_PROJECT = "netbox-docker"


def _compose(netbox_docker: Path, lane: str, argv, timeout=120):
    return subprocess.run(
        ["docker", "compose", "exec", "-T", *argv],
        cwd=str(netbox_docker), capture_output=True, text=True, timeout=timeout,
        env={**os.environ, "COMPOSE_PROJECT_NAME": lane})


def _count(netbox_docker: Path, lane: str, tag: str):
    """Returns (known, count). Never collapses a failed probe into zero."""
    try:
        done = _compose(netbox_docker, lane,
                        ["netbox", "sh", "-c",
                         f"ps -eo args | grep -c '[{tag[0]}]{tag[1:]}'"])
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"probe could not run: {exc}"
    if done.returncode not in (0, 1):   # grep -c exits 1 on zero matches
        return False, f"probe exited {done.returncode}: {done.stderr.strip()[:120]}"
    text = done.stdout.strip()
    return (True, int(text)) if text.isdigit() else (False, f"non-numeric {text!r}")


def observe_baseline(netbox_docker: Path, lane: str) -> dict:
    """Gate 1: host termination does not reach an in-container child."""
    for tag in (SUBJECT_TAG, BYSTANDER_TAG):
        _compose(netbox_docker, lane,
                 ["-d", "netbox", "sh", "-c", f"sleep 900 # {tag}"])
    time.sleep(3)
    before_known, before = _count(netbox_docker, lane, SUBJECT_TAG)

    host_child = subprocess.Popen(
        ["docker", "compose", "exec", "-T", "netbox", "sh", "-c",
         f"sleep 900 # {HOSTKILLED_TAG}"],
        cwd=str(netbox_docker), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env={**os.environ, "COMPOSE_PROJECT_NAME": lane}, start_new_session=True)
    time.sleep(3)
    host_child.kill()
    time.sleep(2)
    after_known, after = _count(netbox_docker, lane, HOSTKILLED_TAG)
    bystander_known, bystander = _count(netbox_docker, lane, BYSTANDER_TAG)

    _compose(netbox_docker, lane, ["netbox", "sh", "-c",
                                   f"pkill -9 -f {SUBJECT_TAG} || true"])
    _compose(netbox_docker, lane, ["netbox", "sh", "-c",
                                   f"pkill -9 -f {BYSTANDER_TAG} || true"])
    _compose(netbox_docker, lane, ["netbox", "sh", "-c",
                                   f"pkill -9 -f {HOSTKILLED_TAG} || true"])
    return {
        "subject_before_known": before_known, "subject_before": before,
        "hostkilled_child_alive_known": after_known,
        "hostkilled_child_alive": after,
        "bystander_known": bystander_known, "bystander": bystander,
    }


def observe_unreachable_probe(netbox_docker: Path) -> dict:
    """Gate 6/8: a probe against a lane that does not exist must be unknown."""
    known, value = _count(netbox_docker, "hh716-definitely-no-such-lane", SUBJECT_TAG)
    return {"known": known, "value": value if known else str(value)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--netbox-docker", type=Path, required=True)
    parser.add_argument("--lane", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    if args.lane == SHARED_PROJECT or not args.lane:
        print(f"refusing to operate on {args.lane!r}: shared stack", file=sys.stderr)
        return 2

    identity = subprocess.run(
        ["docker", "inspect", f"{args.lane}-netbox-1", "--format", "{{.Id}}"],
        capture_output=True, text=True, timeout=60)
    if identity.returncode != 0 or not identity.stdout.strip():
        print(f"lane {args.lane!r} has no netbox container", file=sys.stderr)
        return 3

    evidence = {
        "version": 1,
        "lane": args.lane,
        "container_id": identity.stdout.strip(),
        "run_id": uuid.uuid4().hex,
        "observed_at": int(time.time()),
        "baseline": observe_baseline(args.netbox_docker, args.lane),
        "unreachable_probe": observe_unreachable_probe(args.netbox_docker),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True),
                           encoding="utf-8")
    print(f"wrote {args.output} (lane {args.lane}, container "
          f"{evidence['container_id'][:12]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
