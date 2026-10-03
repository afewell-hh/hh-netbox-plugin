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
    "HarnessEvidenceMissing",
    "RunOutcome",
)

#: Mount points a reaper identity must not be able to reach. Named rather than
#: derived so a new storage root added to NetBox does not silently widen what
#: the adapter is allowed to see.
FORBIDDEN_REAPER_MOUNTS = (
    "media", "static", "scripts", "reports", "default_storage", "ordinary_temp",
)

#: What a lane harness run must independently observe. ``mount_isolation`` is
#: listed separately from ``uid_isolation``: a correct uid with a media mount
#: is still a broken deployment, and #705 requires both.
REQUIRED_HARNESS_OBSERVATIONS = frozenset({
    "accepted_raw", "oversize_413", "chunked_411", "no_listener_spool",
    "uid_isolation", "mount_isolation", "no_public_upload_route",
})

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
    body_buffer_size: int = 10485760
    max_concurrent_bodies: int = 8
    capacity_budget_bytes: int = 83886080

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
DEPLOYMENT_EVIDENCE_ROWS = frozenset({"A01", "A02", "A11", "A12", "A15", "A17"})


@dataclass(frozen=True)
class AdapterRow:
    identifier: str
    method: str
    claim: str
    requirement: str


def rows_for(requirement: str, rows) -> tuple[AdapterRow, ...]:
    return tuple(row for row in rows if row.requirement == requirement)


class ShippedConfigurationUnavailable(AssertionError):
    """The repository checkout could not be located, so containment is unproven."""


def repository_checkout_root(root=None) -> Path:
    """Use an explicit root/environment input, otherwise walk this file's parents.

    Under the CI mount the package is grafted into the NetBox tree, so
    ``parents[3]`` is ``/opt/netbox/netbox`` -- a directory with no workflows
    and a ``scripts/`` holding one ``__init__.py``. A containment scan rooted
    there silently inspects nothing and passes. Locate a checkout marker
    instead, and fail closed when there is none. An invalid explicit root
    never falls back to a different checkout.
    """
    explicit = root if root is not None else os.environ.get("HNP_TEST_CHECKOUT_ROOT")
    if explicit is None:
        # Supplied by the local test wrapper: an explicit temporary snapshot,
        # not a claim that a live CI mount exists. Invalid CI roots never fall back.
        explicit = os.environ.get("HNP_TEST_LOCAL_CHECKOUT_ROOT")
    candidates = [Path(explicit)] if explicit is not None else Path(__file__).resolve().parents
    for candidate in candidates:
        # Identify this repository, not NetBox or an unrelated pyproject above
        # a grafted package. The explicit CI input never falls back elsewhere.
        if (candidate.is_absolute()
                and (candidate / "AGENTS.md").is_file()
                and (candidate / "netbox_hedgehog/__init__.py").is_file()
                and (candidate / ".github/workflows").is_dir()
                and (candidate / "scripts").is_dir()):
            return candidate.resolve(strict=True)
    raise ShippedConfigurationUnavailable(
        "no repository checkout found above "
        f"{Path(__file__).resolve()}; containment cannot be demonstrated from "
        "a grafted package mount, so this must fail rather than pass vacuously")


SHIPPED_CONFIGURATION_TREES = (
    ".github", "scripts", "netbox_hedgehog/scripts", "deploy", "deployment",
    "deployments", "docker", "dev-setup",
)


def shipped_configuration_inventory(root=None) -> list[Path]:
    """Every shipped file a harness artifact must not appear in.

    Fails closed: an empty inventory means the scan found nothing to check,
    which is indistinguishable from a clean result and must not be reported
    as one.
    """
    root = repository_checkout_root(root)
    selected = set()
    for relative in SHIPPED_CONFIGURATION_TREES:
        tree = root / relative
        if tree.is_symlink():
            raise ShippedConfigurationUnavailable("shipped inventory tree must not be a symlink")
        if not tree.exists():
            continue
        # os.walk's default silently ignores inaccessible directories. Inventory
        # errors must not produce an apparently clean, partial scan.
        def unavailable(error):
            raise ShippedConfigurationUnavailable("cannot enumerate shipped inventory") from error
        for parent, directories, files in os.walk(tree, onerror=unavailable):
            for name in directories + files:
                entry = Path(parent) / name
                if entry.is_symlink():
                    raise ShippedConfigurationUnavailable("shipped inventory must not contain symlinks")
            selected.update(Path(parent) / name for name in files)
    for pattern in ("docker-compose*.yml", "docker-compose*.yaml", "compose*.yml", "compose*.yaml"):
        selected.update(root.glob(pattern))
    inventory = sorted(selected)
    if any(path.is_symlink() or not path.is_file() for path in inventory):
        raise ShippedConfigurationUnavailable("shipped inventory contains a non-regular file")
    if not inventory:
        raise ShippedConfigurationUnavailable(
            f"no shipped workflow, script, or compose file found under {root}")
    return inventory


def scan_for_artifact_references(artifact_names, config_files) -> list[str]:
    """Report every shipped file that mentions a harness artifact name.

    Extracted so the positive scan and its controlled negative run the *same*
    code. An assertion written inline beside the loop tests the assertion
    helper, not the scan: disabling the loop would leave such a negative
    passing, which is how the previous version of this control was hollow.
    """
    violations = []
    for config in config_files:
        try:
            text = config.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:
            # Fail closed. A file the scan could not read is a file it did not
            # search, and "no violations found" would then be indistinguishable
            # from "nothing was looked at" -- the same hollow result this
            # scanner exists to prevent. Verified: an unreadable config
            # containing an artifact name previously reported clean.
            raise ShippedConfigurationUnavailable(
                f"cannot read shipped configuration {config}: {exc}; "
                "containment is unproven while any inventory file is "
                "unreadable or missing") from exc
        for name in artifact_names:
            if name == config.name or name in text:
                violations.append(f"{config.name}: {name}")
    return violations


class ArtifactContainmentViolation(AssertionError):
    """A lane-only artifact or reference was found in shipped configuration."""


def check_shipped_artifact_containment(artifact_names, root=None) -> int:
    """Shared by A17 and the always-running #707 CI control.

    Names come from the rendered lane artifacts, not a guessed name convention.
    Check both misplaced files and references. Return only the inventory count;
    diagnostics never copy source contents or evidence payloads into CI logs.
    """
    names = set(artifact_names)
    if not names or any(not isinstance(name, str) or not name or Path(name).name != name for name in names):
        raise ShippedConfigurationUnavailable("non-empty artifact basenames are required")
    inventory = shipped_configuration_inventory(root)
    if scan_for_artifact_references(names, inventory):
        raise ArtifactContainmentViolation("lane-only artifact or reference in shipped configuration")
    return len(inventory)


# --- deficient stand-ins used by the vacuity controls ---------------------

def build_permissive_stub():
    """A module whose every entry point is a MagicMock.

    Rejects rows that assert nothing at all. Necessary but, as #706 review
    showed, nowhere near sufficient.
    """
    import types
    from unittest.mock import MagicMock

    module = types.ModuleType(ADAPTER_MODULE)
    for name in REQUIRED_ENTRY_POINTS:
        setattr(module, name, MagicMock(name=name))
    module.DeploymentRejected = type("DeploymentRejected", (Exception,), {})
    module.HarnessEvidenceMissing = type("HarnessEvidenceMissing", (Exception,), {})
    return module


def build_deficient_stub():
    """A *typed* adapter that looks right and behaves wrongly.

    Dev B built this during #706 review and it passed eleven of twelve rows,
    which the MagicMock control could not detect. It is kept here so that
    adversary runs on every suite execution instead of depending on a reviewer
    thinking of it again. Each deficiency below is a real failure mode:

      * a validator that implements only the checks the rows happen to probe;
      * one that repairs an unsafe mode and *then* rejects, so rejection alone
        looks correct while the evidence has been destroyed;
      * an adapter that re-derives the alert verdict instead of reading it;
      * health that fabricates its age, always alerts, and retains everything;
      * a harness that is a manifest and nothing more.
    """
    import os as _os
    import stat as _stat
    import types
    from types import SimpleNamespace

    module = types.ModuleType(ADAPTER_MODULE)

    class DeploymentRejected(Exception):
        pass

    class HarnessEvidenceMissing(Exception):
        pass

    @dataclass(frozen=True)
    class _RunOutcome:
        started_at: int
        succeeded: bool

    class _HarnessResult:
        """The result shape A16 consumes, so the row can reach its assertion."""

        def __init__(self, observations, unit_version):
            self.observations = dict(observations)
            self.unit_version = unit_version

        def without(self, name):
            remaining = dict(self.observations)
            remaining.pop(name, None)
            return _HarnessResult(remaining, self.unit_version)

        def with_observation(self, name, observed=True, evidence="no"):
            replaced = dict(self.observations)
            replaced[name] = SimpleNamespace(observed=observed, evidence=evidence)
            return _HarnessResult(replaced, self.unit_version)

    def adapter_spec(fixture):
        return SimpleNamespace(
            reaper_uid=fixture.reaper_uid,
            quarantine_owner_uid=fixture.reaper_uid,
            web_service_name="web",
            reaper_service_name="reaper",
            reaper_mount_points=[str(fixture.quarantine_root)])

    def validate_deployment(fixture):
        if fixture.max_raw_bytes != fixture.unit_route_cap_bytes:
            raise DeploymentRejected()
        if fixture.derived_eligibility_seconds <= fixture.active_write_grace_seconds:
            raise DeploymentRejected()
        for root in fixture.forbidden_roots.values():
            if (fixture.quarantine_root == root
                    or str(fixture.quarantine_root).startswith(f"{root}/")):
                raise DeploymentRejected()
        if fixture.reaper_uid == 0 or fixture.reaper_uid != fixture.web_uid:
            raise DeploymentRejected()
        if not fixture.quarantine_root.exists():
            raise DeploymentRejected()
        st = _os.lstat(fixture.quarantine_root)
        if _stat.S_IMODE(st.st_mode) != 0o700:
            _os.chmod(fixture.quarantine_root, 0o700)
            raise DeploymentRejected()
        return True

    def run_scheduled_reap(fixture, report=None, missed=False):
        if missed:
            return SimpleNamespace(alerting=True, state="missed")
        return SimpleNamespace(
            alerting=report.failed or report.bound_exceeded_count > 0, state="ran")

    def health_state(fixture, now=0, last_success_at=0, runs=(),
                     last_report=None, history_limit=None, previous=None):
        # Echoes what it is told and keeps nothing: the #706 re-review's
        # remaining false pass.
        return SimpleNamespace(
            alerting=bool(runs and not all(run.succeeded for run in runs)),
            seconds_since_success=now - last_success_at,
            history=[], history_limit=history_limit or 1)

    def lane_harness_spec(fixture, artifact_dir=None):
        # A complete, correctly-shaped result whose verifier accepts anything.
        # The deficiency under test is "treats missing evidence as success";
        # an incomplete result shape would make the row fail with
        # AttributeError instead, which is a plumbing error and not detection.
        def _result():
            return _HarnessResult(
                observations={
                    name: SimpleNamespace(observed=True, evidence="no")
                    for name in REQUIRED_HARNESS_OBSERVATIONS},
                unit_version="1.34.2")

        return SimpleNamespace(
            is_lane_only=True,
            unit_route_cap_bytes=fixture.unit_route_cap_bytes,
            required_observations=set(REQUIRED_HARNESS_OBSERVATIONS),
            exposes_public_upload=False,
            pinned_unit_version="1.34.2",
            render=lambda: [],
            observe=_result,
            verify=lambda result: True)

    module.DeploymentRejected = DeploymentRejected
    module.HarnessEvidenceMissing = HarnessEvidenceMissing
    module.RunOutcome = _RunOutcome
    module.AdapterSpec = adapter_spec
    module.validate_deployment = validate_deployment
    module.run_scheduled_reap = run_scheduled_reap
    module.health_state = health_state
    module.lane_harness_spec = lane_harness_spec
    return module


def build_single_fault_stub(fault: str):
    """A competent adapter with exactly one deficiency.

    #706 re-review: one increasingly multi-fault stand-in can mask rows,
    because an early assertion rejects it before a later rule is reached --
    A11 tripped on capacity before secrecy was ever evaluated. Each fault is
    therefore injected on its own, into an otherwise sound stub.

    This is still a test double, not a reference implementation: it exists to
    be rejected, and only the named fault distinguishes it from a stub that
    the rows would accept.
    """
    import copy as _copy
    import os as _os
    import stat as _stat
    import types
    from dataclasses import dataclass as _dc
    from types import SimpleNamespace

    base = build_deficient_stub()
    module = types.ModuleType(ADAPTER_MODULE)
    for name in REQUIRED_ENTRY_POINTS:
        setattr(module, name, getattr(base, name))

    DeploymentRejected = base.DeploymentRejected
    HarnessEvidenceMissing = base.HarnessEvidenceMissing
    RunOutcome = base.RunOutcome

    def sound_health(fixture, now=0, last_success_at=0, runs=(),
                     last_report=None, history_limit=None, previous=None,
                     _unbounded=False, _raw=False):
        history = list(previous.history) if previous is not None else []
        if last_report is not None:
            kept = last_report if _raw else _redacted(last_report)
            history.append(kept)
        limit = history_limit or 1
        if not _unbounded:
            history = history[-limit:]
        elapsed = now - last_success_at
        failed = any(not run.succeeded for run in runs)
        return SimpleNamespace(
            alerting=bool(failed or elapsed > fixture.reaper_interval_seconds),
            seconds_since_success=elapsed,
            history=history, history_limit=limit)

    def _redacted(report):
        return SimpleNamespace(oldest_orphan_seconds=report.oldest_orphan_seconds,
                               incident_count=report.incident_count)

    if fault == "health_unbounded":
        module.health_state = lambda *a, **k: sound_health(*a, _unbounded=True, **k)
    elif fault == "health_retains_raw":
        module.health_state = lambda *a, **k: sound_health(*a, _raw=True, **k)
    elif fault == "health_empty_history":
        def empty(*a, **k):
            state = sound_health(*a, **k)
            state.history = []
            return state
        module.health_state = empty
    else:
        module.health_state = sound_health

    return module
