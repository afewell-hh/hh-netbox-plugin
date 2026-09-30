"""Test-only #701 contracts for the absent secure raw-ingress capability.

Nothing in this module is production ingress code.  It gives RED tests a
single deliberately narrow future seam, while its filesystem and subprocess
helpers exercise the observer controls for real today.
"""

from __future__ import annotations

import importlib
import os
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from netbox_hedgehog.tests.seam_evidence import EmissionPath, SeamInventory


PRODUCTION_MODULE = "netbox_hedgehog.secure_ingress"
REQUIRED_ENTRY_POINTS = (
    "QuarantineStore",
    "ingest_raw",
    "reap_orphans",
    "reaper_schedule",
    "listener_regression_probe",
    "LengthRejected",
    "UnsafeQuarantineEntry",
    "t3_evidence",
)


class SecureIngressAbsent(AssertionError):
    """The #686/#701 ingress seam is intentionally not implemented yet."""


def require_secure_ingress():
    """Get the future seam, failing RED solely when it is absent/incomplete."""
    try:
        module = importlib.import_module(PRODUCTION_MODULE)
    except ImportError as exc:
        raise SecureIngressAbsent(
            f"secure ingress seam absent: {PRODUCTION_MODULE} ({exc}); "
            "this #701 contract is RED because production ingress is absent") from None
    missing = [name for name in REQUIRED_ENTRY_POINTS if not hasattr(module, name)]
    if missing:
        raise SecureIngressAbsent(
            f"secure ingress seam is incomplete: missing {missing}")
    return module


@dataclass(frozen=True)
class IngressTestConfig:
    """Every numeric value is an explicit fixture input, never a ship default."""

    quarantine_root: Path
    media_root: Path
    static_root: Path
    scripts_root: Path
    reports_root: Path
    default_storage_root: Path
    ordinary_temp_root: Path
    application_root: Path
    max_raw_bytes: int
    active_write_grace_seconds: int
    clock_skew_seconds: int
    reaper_interval_seconds: int
    orphan_bound_seconds: int
    health_failure_threshold: int


def direct_entries(root: Path) -> dict[str, os.stat_result]:
    """Observe immediate entries without following a link or recursing."""
    return {entry.name: entry.stat(follow_symlinks=False) for entry in os.scandir(root)}


def entry_kind(mode: int) -> str:
    if stat.S_ISREG(mode):
        return "regular"
    if stat.S_ISLNK(mode):
        return "symlink"
    if stat.S_ISDIR(mode):
        return "directory"
    return "other"


def launch_writer(path: Path, payload: bytes) -> subprocess.Popen:
    """Create a real child that confirms its exclusive write then waits.

    The parent test kills this process rather than asking it to cooperate.  The
    surviving entry is a fixture control for a future orphan reaper, not a
    substitute for one.
    """
    code = """
import os, sys, time
path, payload = sys.argv[1], bytes.fromhex(sys.argv[2])
fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
os.write(fd, payload)
os.fsync(fd)
print('Q-WRITTEN', flush=True)
time.sleep(60)
"""
    return subprocess.Popen(
        [sys.executable, "-c", code, str(path), payload.hex()],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


# Every listed surface has paired GREEN evidence. This remains intentionally
# separate from the live paste inventory: the capability is internal only.
T3_INGRESS_ROWS = {
    "web_raw_ingress": ("R03", "raw body/client metadata absent from response, logs, audit"),
    "quarantine_filesystem": ("R04", "raw bytes/path absent after terminal cleanup"),
    "cleanup": ("R05", "cleanup failure is incident/health evidence, never a false success"),
    "isolated_reaper": ("R10", "aggregate health only; no raw bytes/path/client metadata"),
    "unit_access_error_logs": ("R11", "admission log is not an application audit"),
    "container_logs": ("R12", "sentinel/path/client metadata absent"),
    "interchange_audit": ("R07", "minimal failure audit present; no raw bytes/path/filename"),
    "exception_logging": ("R12", "handled and incident paths omit submitted content"),
    "media_default_storage": ("R01", "Q is outside media/default storage and non-web reachable"),
}


INGRESS_RED_INVENTORY = SeamInventory(
    seam="interchange-secure-raw-ingress-red",
    secret_fields=("password", "token", "secret", "credential", "kubernetes_token"),
    touches_credentials=True,
    touches_audit=True,
    notes=("#703 internal-only quarantine/reaper evidence. Each asserted path is "
           "paired with its #701 GREEN row; no public upload surface exists."),
    paths=(
        EmissionPath("web raw ingress", "import_template", "asserted", "R03 raw-byte and metadata absence"),
        EmissionPath("quarantine filesystem", "retention_backup", "asserted", "R04 real Q cleanup observation"),
        EmissionPath("terminal cleanup", "retention_backup", "asserted", "R05 terminal delete/incident evidence"),
        EmissionPath("isolated reaper", "retention_backup", "asserted", "R10 aggregate health, no raw content"),
        EmissionPath("Unit access/error logs", "log", "asserted", "R11 admission record, not application audit"),
        EmissionPath("container logs", "log", "asserted", "R12 sentinel/path metadata absence"),
        EmissionPath("InterchangeAudit", "changelog", "asserted", "R07 minimal failure audit, no raw content"),
        EmissionPath("exception/logging", "error_handling", "asserted", "R12 handled and incident paths"),
        EmissionPath("media/default storage", "retention_backup", "asserted", "R01 Q isolation/non-web access"),
    ),
)
