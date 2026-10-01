"""Test-only #705 contracts for the absent deployable reaper adapter.

Nothing here is a deployment adapter, Compose file, or shipped configuration.
It gives the RED rows one narrow future seam, and its identity/mount/process
helpers read real kernel and filesystem state today so the observer controls
mean something before the adapter exists.

#703 merged the internal service and proved it in a lane that was then thrown
away. #705 turns the deployment assumptions that lane embodied -- who runs the
reaper, what it may mount, what the listener may do, what happens when a run
is missed -- into falsifiable requirements.
"""

from __future__ import annotations

import importlib
import os
import re
import stat
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


ADAPTER_MODULE = "netbox_hedgehog.reaper_adapter"

#: Everything the rows below reference. Kept complete deliberately: on #702 a
#: short list meant two rows failed with AttributeError instead of the single
#: declared "seam absent" error, which reads like a test bug at GREEN time.
REQUIRED_ENTRY_POINTS = (
    "AdapterSpec",
    "validate_deployment",
    "run_scheduled_reap",
    "health_state",
    "lane_harness_spec",
    "DeploymentRejected",
)

#: Mount points a reaper identity must not be able to reach. Named rather than
#: derived so a new storage root added to NetBox does not silently widen what
#: the adapter is allowed to see.
FORBIDDEN_REAPER_MOUNTS = (
    "media", "static", "scripts", "reports", "default_storage", "ordinary_temp",
)

#: #703 approved v1 defaults. Declared here only so a row can prove the adapter
#: reads them from configuration instead of hardcoding them; #705 invents no
#: value and these must stay overridable.
V1_DEFAULTS = {
    "max_raw_bytes": 10 * 1024 * 1024,
    "active_write_grace_seconds": 5 * 60,
    "clock_skew_seconds": 60,
    "reaper_interval_seconds": 60 * 60,
    "orphan_bound_seconds": 24 * 60 * 60,
}


class AdapterAbsent(AssertionError):
    """The #705 deployment adapter is intentionally not implemented yet."""


def require_reaper_adapter():
    """Get the future adapter, failing RED solely when it is absent.

    A named exception, so a row that fails for any other reason -- a typo, a
    fixture error, a missing database table -- is distinguishable from the
    capability simply not existing.
    """
    try:
        module = importlib.import_module(ADAPTER_MODULE)
    except ImportError as exc:
        raise AdapterAbsent(
            f"reaper adapter seam absent: {ADAPTER_MODULE} ({exc}); this #705 "
            "contract is RED because no deployment adapter exists") from None
    missing = [name for name in REQUIRED_ENTRY_POINTS if not hasattr(module, name)]
    if missing:
        raise AdapterAbsent(f"reaper adapter seam is incomplete: missing {missing}")
    return module


@dataclass(frozen=True)
class DeploymentFixture:
    """A candidate deployment, entirely injectable.

    Every value a row varies lives here. No host setting is read or mutated:
    #705 forbids adding another host-wide mutation, and a validation contract
    that needs one could not be tested without disturbing the shared stack.
    """

    quarantine_root: Path
    web_uid: int
    reaper_uid: int
    reaper_mounts: tuple[str, ...]
    forbidden_roots: dict[str, Path]
    unit_route_cap_bytes: int
    max_raw_bytes: int
    active_write_grace_seconds: int
    clock_skew_seconds: int
    reaper_interval_seconds: int
    orphan_bound_seconds: int
    exposes_public_upload: bool = False
    quarantine_mount_is_dedicated: bool = True

    @property
    def derived_eligibility_seconds(self) -> int:
        return (self.orphan_bound_seconds - self.reaper_interval_seconds
                - self.clock_skew_seconds)


# --- real observers, used by the controls that must pass today -------------

def read_self_mounts() -> list[str]:
    """Mount points of this process, read from the kernel, not declared."""
    entries = []
    with open("/proc/self/mountinfo", encoding="utf-8") as handle:
        for line in handle:
            parts = line.split()
            if len(parts) > 4:
                entries.append(parts[4])
    return entries


def directory_identity(path: Path) -> tuple[int, int, int]:
    """(uid, gid, mode) of a real directory, following no link."""
    st = os.lstat(path)
    return st.st_uid, st.st_gid, stat.S_IMODE(st.st_mode)


def run_as_child(code: str, *args: str) -> subprocess.CompletedProcess:
    """Execute a real child process; used where in-process state would lie.

    Scheduler liveness and process identity cannot be honestly asserted by a
    test that only inspects itself.
    """
    return subprocess.run(
        [sys.executable, "-c", code, *args],
        capture_output=True, text=True, timeout=30)


#: Rows whose claim is about deployment shape rather than Python behaviour.
#: Recorded so a reader can tell which evidence a GREEN implementation must
#: supply from a real container rather than from this suite.
DEPLOYMENT_EVIDENCE_ROWS = frozenset({"A01", "A02", "A11", "A12"})


@dataclass(frozen=True)
class AdapterRow:
    identifier: str
    method: str
    claim: str
    requirement: str


def rows_for(requirement: str, rows) -> tuple[AdapterRow, ...]:
    return tuple(row for row in rows if row.requirement == requirement)
