"""Test-only #711 harness for the absent supported-runner contract.

No runner, script, workflow, documentation or production behaviour is added
here. This module supplies one named seam for the contract that Phase D will
implement, plus subprocess helpers that exercise the real raw Django path.

Two constraints shaped it, both from Phase A/B review:

* Every claim about refusal must be observed in a **fresh process**. Python
  caches modules, so an in-process import of a protected module proves nothing
  about the next run and -- once the import hook exists -- would terminate the
  test process itself. Nothing here imports a protected module.
* A protected module must be named as a string, never imported, for the same
  reason.
"""

from __future__ import annotations

import importlib
import json
import re
import os
import signal
import subprocess
import sys
import textwrap
import time
from dataclasses import dataclass
from pathlib import Path


CONTRACT_MODULE = "netbox_hedgehog.tests.test_interchange.runner_contract"

#: What Phase D must expose. Checked in both directions by a control, so an
#: incomplete seam fails as "contract absent" rather than AttributeError --
#: the #702 lesson.
REQUIRED_ENTRY_POINTS = (
    "EVIDENCE_REQUIREMENTS",
    "selection_requires_evidence",
    "PREREQUISITE_DIAGNOSTIC",
    "PREREQUISITE_EXIT_CODE",
    "remediation_command",
    "ContractDeclarationInvalid",
    "wrapper_prepares_selection",
)

#: Modules that need externally prepared lane evidence. Named as strings and
#: never imported: importing one is precisely what the contract forbids
#: outside the wrapper.
PROTECTED_MODULES = (
    "netbox_hedgehog.tests.test_interchange.test_reaper_adapter_red",
    "netbox_hedgehog.tests.test_interchange.test_checkout_containment",
)

#: Interchange modules that must keep their raw fast path. Their presence in
#: the suite is what stops the contract degenerating into a blanket refusal.
UNPROTECTED_MODULES = (
    "netbox_hedgehog.tests.test_interchange_audit_retention",
    "netbox_hedgehog.tests.test_interchange.test_core_contract",
)

#: An unrelated suite, to prove the hook does not leak beyond interchange.
UNRELATED_MODULE = "netbox_hedgehog.tests.test_topology_planning.test_port_allocator"

#: A selection two levels above a protected module. Dev B's acceptance lists
#: grandparent alongside parent, so it is probed as its own raw selector
#: rather than inferred from the parent row.
GRANDPARENT_SELECTION = "netbox_hedgehog.tests"

#: Everything that could supply evidence to a child process and so conceal a
#: missing declaration. `raw_django` scrubs all of these; T04d additionally
#: proves the scrub was effective rather than assuming it.
EVIDENCE_VARIABLES = (
    "HNP_TEST_CHECKOUT_ROOT",
    "HNP_TEST_LOCAL_CHECKOUT_ROOT",
    "HNP_REAPER_CONTAINER_EVIDENCE",
)


class RunnerContractAbsent(AssertionError):
    """The #711 runner contract is intentionally not implemented yet."""


def require_runner_contract():
    """Get the future contract, failing RED solely when it is absent."""
    try:
        module = importlib.import_module(CONTRACT_MODULE)
    except ImportError as exc:
        raise RunnerContractAbsent(
            f"runner contract absent: {CONTRACT_MODULE} ({exc}); this #711 "
            "contract is RED because no supported-runner contract exists") from None
    missing = [name for name in REQUIRED_ENTRY_POINTS if not hasattr(module, name)]
    if missing:
        raise RunnerContractAbsent(f"runner contract is incomplete: missing {missing}")
    return module


#: Markers a fixture body writes to stdout. B3: a unittest summary is not a
#: body observer in either direction -- `Ran 0 tests` counts as a summary, and
#: a body can run before a SystemExit suppresses one -- so bodies say so
#: themselves and rows assert on these.
ORDINARY_MARKER = "HH711_ORDINARY_BODY_RAN"
PROTECTED_MARKER = "HH711_PROTECTED_BODY_RAN"


@dataclass(frozen=True)
class FixtureTree:
    """A disposable importable test tree that cannot rediscover the driver.

    B2: broad selections -- parent, grandparent, options-only -- necessarily
    discover every sibling of their target. Pointed at the real tree they
    rediscover `test_runner_contract_red` and respawn it, which was measured
    four levels deep and still descending. Pointed here they cannot: nothing
    in this tree names or imports the driver.

    Every case is a `SimpleTestCase`, so Django creates no test database for
    these children. That removes the `--keepdb` sharing hazard at the root
    rather than coordinating around it.
    """

    root: Path
    grandparent: str
    parent: str
    protected: str
    ordinary: str

    @property
    def protected_class(self) -> str:
        return f"{self.protected}.ProtectedFixture"

    @property
    def protected_method(self) -> str:
        return f"{self.protected_class}.test_body_must_not_run"


def build_fixture_tree(root: Path) -> FixtureTree:
    """Write the disposable tree. Caller owns `root` and its removal."""
    pkg = root / "hh711_root"
    sub = pkg / "pkg"
    sub.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (sub / "__init__.py").write_text("", encoding="utf-8")

    (sub / "test_ordinary.py").write_text(textwrap.dedent(f"""
        from django.test import SimpleTestCase


        class OrdinaryFixture(SimpleTestCase):
            def test_body_runs(self):
                # Listed before the protected module so an early refusal must
                # prevent this from printing. Its presence is the falsifiable
                # evidence that bodies were reached.
                print("{ORDINARY_MARKER}", flush=True)
    """).lstrip(), encoding="utf-8")

    (sub / "test_protected.py").write_text(textwrap.dedent(f"""
        import os

        from django.test import SimpleTestCase

        # Stands in for a real evidence-requiring module: it refuses at import
        # time when its prerequisite is absent, which is the behaviour the
        # contract must produce on the raw path.
        if not os.environ.get("HH711_FIXTURE_EVIDENCE"):
            raise RuntimeError("HH711_FIXTURE_PREREQUISITE_MISSING")


        class ProtectedFixture(SimpleTestCase):
            def test_body_must_not_run(self):
                print("{PROTECTED_MARKER}", flush=True)
    """).lstrip(), encoding="utf-8")
    return FixtureTree(root=root, grandparent="hh711_root", parent="hh711_root.pkg",
                       protected="hh711_root.pkg.test_protected",
                       ordinary="hh711_root.pkg.test_ordinary")


@dataclass(frozen=True)
class RunOutcome:
    """What a fresh raw-Django process actually did.

    ``timed_out`` is a first-class outcome rather than an exception. An
    unbounded invocation -- notably options-only, which triggers Django's
    whole-tree discovery -- runs the entire suite while the contract is
    absent. A row asserting refusal must be able to say "it did not refuse
    within the bound" instead of hanging the RED suite for half an hour.
    """

    argv: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False
    #: Descendants still alive after the bound expired and the group was
    #: signalled. B2: killing the immediate child is not proof the tree
    #: stopped, so this is observed rather than assumed, and a harness
    #: control asserts it is zero.
    survivors: int = 0

    @property
    def combined(self) -> str:
        return f"{self.stdout}\n{self.stderr}"

    @property
    def tests_executed(self) -> int:
        """How many tests unittest reported running, parsed, not matched.

        B3: `reported_a_test_result` returned true for `Ran 0 tests`, so a
        vacuous success satisfied every positive row. Positive rows now
        require a nonzero count from this.
        """
        match = re.search(r"^Ran (\d+) test", self.combined, re.MULTILINE)
        return int(match.group(1)) if match else 0

    def body_ran(self, marker: str) -> bool:
        """Did a fixture body actually execute and say so?

        B3: the only direction-safe observer. A summary can exist with zero
        bodies, and bodies can run with no summary when SystemExit intervenes.
        """
        return marker in self.combined

    def wrote(self, marker: Path) -> bool:
        return marker.exists()


def manage_py() -> Path:
    return Path(sys.executable).parent.parent / "netbox" / "manage.py"


def _reap_group(process) -> int:
    """Kill the child's whole process group and report what survived.

    B2: `Popen.kill()` signals only the immediate child. A Django test child
    that has itself spawned is left running, which is how four orphaned
    levels accumulated. The child is started in its own session so the entire
    descendant tree can be signalled as one group, and the survivor count is
    observed afterwards rather than assumed to be zero.
    """
    try:
        group = os.getpgid(process.pid)
    except OSError:
        return 0

    def alive() -> int:
        return _running_in_group(group)

    # Poll the GROUP, not the immediate child. Waiting on `process` only
    # reports that the direct child exited, which is exactly the mistake this
    # function exists to prevent: the first version broke out of its escalation
    # loop on `process.wait()` and reported zero survivors while three
    # descendants were still running. The harness control caught it.
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(group, sig)
        except OSError:
            break
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if alive() == 0:
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    pass
                return 0
            time.sleep(0.1)
    return alive()


def _process_state(proc_dir: Path) -> tuple[int, str] | None:
    """`(process group, state)` for one /proc entry, or None if unreadable.

    Deliberately not swallowed into "assume it is gone": an entry that cannot
    be read is reported as None and excluded, which the caller treats as not
    running. That is sound here because the caller's question is "is anything
    still executing", and it is the narrow case -- unlike a blanket
    `except OSError: continue` over an inventory, which is the pattern that
    made a scan look clean in #706.
    """
    try:
        stat = (proc_dir / "stat").read_text()
        after_comm = stat.rsplit(")", 1)[1].split()
        return int(after_comm[2]), after_comm[0]
    except (OSError, ValueError, IndexError):
        return None


def _running_in_group(group: int) -> int:
    """Count processes in `group` that are actually still executing.

    Zombies are excluded, and that distinction is load-bearing rather than
    cosmetic. Inside the test container PID 1 is the Django process, not an
    init that reaps orphans, so a SIGKILLed descendant stays in /proc in
    state `Z` indefinitely. Counting those reported four survivors for a tree
    that had in fact been killed -- a dead process holds a PID slot, no CPU,
    and cannot spawn. On the host systemd reaps immediately, so the naive
    count passed there and failed only in the container.
    """
    total = 0
    for entry in Path("/proc").glob("[0-9]*"):
        state = _process_state(entry)
        if state and state[0] == group and state[1] != "Z":
            total += 1
    return total


def raw_django(*labels: str, extra: tuple[str, ...] = (), env: dict | None = None,
               timeout: int = 300, cwd: Path | None = None,
               keepdb: bool = True) -> RunOutcome:
    """Run `manage.py test` in a genuinely fresh, group-isolated process.

    Fresh because the import hook under contract fires once per interpreter.
    Group-isolated because broad selections spawn, and a bound that cannot
    reap descendants is not a bound (B2).

    `keepdb` is opt-out: fixture-tree children are all `SimpleTestCase`, so
    Django builds no test database for them and they must not join the
    parent's `--keepdb` identity.
    """
    argv = [sys.executable, "manage.py", "test", *labels]
    if keepdb:
        argv.append("--keepdb")
    argv.extend(extra)
    environment = dict(os.environ)
    for name in EVIDENCE_VARIABLES:
        environment.pop(name, None)
    if env:
        environment.update(env)

    process = subprocess.Popen(
        argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        cwd=str(cwd or Path(__file__).resolve().parents[3]),
        env=environment, start_new_session=True)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        survivors = _reap_group(process)
        stdout, stderr = process.communicate()
        return RunOutcome(tuple(argv), -1, stdout or "", stderr or "",
                          timed_out=True, survivors=survivors)
    return RunOutcome(tuple(argv), process.returncode, stdout, stderr)


def import_in_fresh_process(module: str, env: dict | None = None,
                            timeout: int = 120) -> RunOutcome:
    """Import one module in a fresh interpreter and report what happened."""
    code = (
        "import django, os, sys\n"
        "os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')\n"
        "sys.path.insert(0, '/opt/netbox/netbox')\n"
        "django.setup()\n"
        f"import {module}\n"
        "import sys as _s\n"
        "print('IMPORT_COMPLETED')\n"
        "for _m in sorted(_s.modules):\n"
        "    if _m.startswith('netbox_hedgehog.tests.test_interchange.test_'):\n"
        "        print('LOADED:' + _m)\n"
    )
    environment = dict(os.environ)
    for name in EVIDENCE_VARIABLES:
        environment.pop(name, None)
    if env:
        environment.update(env)
    done = subprocess.run([sys.executable, "-c", code], capture_output=True,
                          text=True, timeout=timeout, env=environment)
    return RunOutcome((sys.executable, "-c", f"import {module}"),
                      done.returncode, done.stdout, done.stderr)


def evidence_visible_to_child(timeout: int = 60) -> dict:
    """What evidence a freshly spawned child can actually see.

    T04d requires the omission to be demonstrated with "neither inherited CI
    evidence variables nor usable residual evidence". Asserting that
    `raw_django` scrubs is not the same as observing that the child saw
    nothing, so the child reports its own view and the row checks that.
    """
    code = (
        "import json, os\n"
        f"names = {list(EVIDENCE_VARIABLES)!r}\n"
        "seen = {n: os.environ.get(n) for n in names if os.environ.get(n)}\n"
        "print('EVIDENCE_SEEN=' + json.dumps(seen))\n"
    )
    environment = dict(os.environ)
    for name in EVIDENCE_VARIABLES:
        environment.pop(name, None)
    done = subprocess.run([sys.executable, "-c", code], capture_output=True,
                          text=True, timeout=timeout, env=environment)
    for line in done.stdout.splitlines():
        if line.startswith("EVIDENCE_SEEN="):
            return json.loads(line.split("=", 1)[1])
    raise AssertionError(f"evidence probe produced no reading: {done.stdout!r} {done.stderr!r}")


@dataclass(frozen=True)
class ContractRow:
    identifier: str
    method: str
    claim: str
    area: str
