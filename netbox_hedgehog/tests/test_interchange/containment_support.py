"""Test-only support for the #716 in-container containment contract.

RED phase. The contract itself does not exist; `require_containment()` names
the single module that must appear, so every row fails for that one reason
rather than for fixture or import trouble.

Three ideas carry the safety properties this suite is specified against:

* **Unknown is not clean.** A probe that could not run returns UNKNOWN, never
  "no survivors" or "database absent". Today's #711 driver reads stdout
  without checking the exit status, so an unreachable container reports the
  two most reassuring answers available. Nothing here may repeat that.
* **Ownership precedes risk.** A record published after setup cannot
  authorize cleanup for a timeout during setup. Records are therefore
  two-stage: container identity before launch, process identity before any
  timeout-exposed work.
* **Verification precedes signalling.** A self-reported PGID is a claim. A
  PID or group can be reused. Nothing is signalled until the claim is
  independently confirmed inside the intended container.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


CONTAINMENT_MODULE = "netbox_hedgehog.tests.test_interchange.containment"

#: Where a scenario publishes its two-stage ownership record, inside its own
#: container, before anything that can time out.
OWNERSHIP_PATH = "/tmp/hh716_ownership.json"


class ContainmentAbsent(AssertionError):
    """The #716 containment contract is intentionally not implemented yet."""


def require_containment():
    """Get the future containment module, failing RED only when absent."""
    import importlib

    try:
        module = importlib.import_module(CONTAINMENT_MODULE)
    except ImportError as exc:
        raise ContainmentAbsent(
            f"containment contract absent: {CONTAINMENT_MODULE} ({exc}); this "
            "#716 suite is RED because no in-container containment contract "
            "exists") from None
    missing = [name for name in REQUIRED_CONTAINMENT_ENTRY_POINTS
               if not hasattr(module, name)]
    if missing:
        raise ContainmentAbsent(
            f"containment contract is incomplete: missing {missing}")
    return module


#: What the contract must expose. Checked both ways by a control, so an
#: incomplete seam fails as "absent" rather than AttributeError.
REQUIRED_CONTAINMENT_ENTRY_POINTS = (
    "publish_container_identity",
    "publish_process_identity",
    "verify_ownership",
    "cleanup_owned",
    "lane_state",
    "OwnershipInvalid",
)


class Probe(Enum):
    """Three outcomes. UNKNOWN is the whole point.

    A two-valued probe forces an unreachable container into a definite
    answer, and the convenient one at that.
    """

    TRUE = "true"
    FALSE = "false"
    UNKNOWN = "unknown"

    @property
    def is_known(self) -> bool:
        return self is not Probe.UNKNOWN


@dataclass(frozen=True)
class ProbeResult:
    outcome: Probe
    detail: str = ""
    raw: str = ""

    def __bool__(self):  # pragma: no cover - deliberately unsupported
        raise TypeError(
            "a ProbeResult must not be used as a boolean: UNKNOWN would "
            "silently read as False, which is how a failed probe becomes "
            "'no survivors'. Compare .outcome explicitly.")


@dataclass(frozen=True)
class OwnershipRecord:
    """Everything needed to authorize a narrow signal, or refuse one."""

    run_id: str = ""
    container_id: str = ""
    pid: int = 0
    pgid: int = 0
    sid: int = 0
    command: str = ""
    stage: str = ""

    REQUIRED = ("run_id", "container_id", "pid", "pgid", "sid", "command", "stage")

    @classmethod
    def from_text(cls, text):
        """Parse, or return None. Malformed-but-parseable must still fail."""
        try:
            data = json.loads(text)
        except (TypeError, ValueError):
            return None
        if not isinstance(data, dict):
            return None
        return cls(**{k: data.get(k, cls.__dataclass_fields__[k].default)
                      for k in cls.__dataclass_fields__})

    def missing_fields(self):
        return [name for name in self.REQUIRED if not getattr(self, name)]


PROVER_EVIDENCE_VARIABLE = "HH716_CONTAINMENT_EVIDENCE"
PROVER_EVIDENCE_MAX_AGE = 3600


class ProverEvidenceUnusable(AssertionError):
    """Prover evidence is absent, stale, or not bound to this lane."""


def load_prover_evidence(expected_lane):
    """Host-observed facts, or a loud refusal.

    Container-side rows never touch Docker: Dev B ruled out giving the inner
    Django container a socket, and a first version of this suite mounted one.
    Observation happens host-side and arrives here bound to a lane,
    container id and run, with a freshness window -- the same discipline as
    the #711 driver evidence.
    """
    location = os.environ.get(PROVER_EVIDENCE_VARIABLE)
    if not location:
        raise ProverEvidenceUnusable(
            f"{PROVER_EVIDENCE_VARIABLE} is unset: run containment_prover.py "
            "host-side for this lane first")
    try:
        evidence = json.loads(Path(location).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ProverEvidenceUnusable(f"evidence at {location} unreadable: {exc}") from None
    age = time.time() - evidence.get("observed_at", 0)
    if not 0 <= age <= PROVER_EVIDENCE_MAX_AGE:
        raise ProverEvidenceUnusable(
            f"evidence is {int(age)}s old (window {PROVER_EVIDENCE_MAX_AGE}s)")
    if evidence.get("lane") != expected_lane:
        raise ProverEvidenceUnusable(
            f"evidence is bound to lane {evidence.get('lane')!r}, not {expected_lane!r}")
    if evidence.get("lane") == "netbox-docker":
        raise ProverEvidenceUnusable("evidence names the shared stack")
    if not evidence.get("container_id"):
        raise ProverEvidenceUnusable("evidence carries no container identity")
    return evidence


def compose_exec(netbox_docker: Path, lane: str, service: str, argv):
    """Run a command in a lane service with structured, shell-safe argv.

    `argv` is a list and is never joined into a shell string: a PGID
    interpolated into `sh -c` is both an injection surface and unreviewable.
    Returns the CompletedProcess so callers can inspect `returncode` --
    which the #711 driver never does.
    """
    if isinstance(argv, str):
        raise TypeError("argv must be a list; string commands are not accepted")
    import os

    return subprocess.run(
        ["docker", "compose", "exec", "-T", service, *argv],
        cwd=str(netbox_docker), capture_output=True, text=True, timeout=120,
        env={**os.environ, "COMPOSE_PROJECT_NAME": lane})


def probe_members(netbox_docker: Path, lane: str, pgid: int) -> ProbeResult:
    """How many processes are in `pgid`, or UNKNOWN if we could not look."""
    try:
        done = compose_exec(netbox_docker, lane, "netbox",
                            ["sh", "-c", f"ps -eo pgid | awk '$1=={int(pgid)}' | wc -l"])
    except (OSError, subprocess.SubprocessError) as exc:
        return ProbeResult(Probe.UNKNOWN, f"probe could not run: {exc}")
    if done.returncode != 0:
        return ProbeResult(Probe.UNKNOWN,
                           f"probe exited {done.returncode}: {done.stderr.strip()[:120]}")
    text = done.stdout.strip()
    if not text.isdigit():
        return ProbeResult(Probe.UNKNOWN, f"probe returned {text!r}, not a count")
    return ProbeResult(Probe.TRUE if int(text) else Probe.FALSE, raw=text)
