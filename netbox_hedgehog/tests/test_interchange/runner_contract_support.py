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

#: What Phase D must expose -- and no more. This list shrank from seven to
#: three when the wrapper rows stopped asking the contract about itself and
#: started judging what the real command did (Dev B's disposition on #713).
#: `selection_requires_evidence`, `remediation_command` and
#: `ContractDeclarationInvalid` are gone from it because R13, R10 and R12 now
#: observe behaviour through the supported wrapper instead of consulting an
#: API that would have been free to agree with itself.
#:
#: Checked in both directions by a control, so an incomplete seam fails as
#: "contract absent" rather than AttributeError, and a declared-but-unused
#: entry point cannot quietly widen the surface Phase D has to build.
REQUIRED_ENTRY_POINTS = (
    "EVIDENCE_REQUIREMENTS",
    "PREREQUISITE_DIAGNOSTIC",
    "PREREQUISITE_EXIT_CODE",
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


#: Where the host-side driver publishes what it observed, and how long an
#: observation stays usable. The window matches the lane convention already
#: in `reaper_lane.py`; an observation older than this is not evidence about
#: the current tree.
#: Scenarios the lead has authorized as #715-blocked. The loader consults
#: this, so adding `blocked_by` to any other evidence record is rejected
#: rather than silently excusing a row.
AUTHORIZED_BLOCKED_SCENARIOS = frozenset({
    "declared_ok", "declaration_removed", "broad_supported",
    "preflight_then_invalidated", "remediation_round_trip",
})

DRIVER_EVIDENCE_VARIABLE = "HH711_DRIVER_EVIDENCE"
DRIVER_EVIDENCE_MAX_AGE = 3600
SHARED_STACK_LANE = "netbox-docker"


class DriverEvidenceUnusable(AssertionError):
    """Driver evidence is absent, stale, or not bound to this run.

    Separate from `RunnerContractAbsent` on purpose: "nobody ran the host
    driver" and "the contract is not implemented" are different facts, and a
    row that cannot tell them apart reports the wrong thing.
    """


def load_driver_evidence(scenario: str, expected_selection: tuple[str, ...]) -> dict:
    """Return one driver observation, or refuse to return anything.

    Every binding Dev B required is checked here, and each failure is loud.
    There is no path that returns a record when a binding cannot be
    established -- including the case where the expected head is simply
    unknown, which fails closed rather than skipping the check.
    """
    location = os.environ.get(DRIVER_EVIDENCE_VARIABLE)
    if not location:
        raise DriverEvidenceUnusable(
            f"{DRIVER_EVIDENCE_VARIABLE} is unset: the host-side driver "
            "(runner_contract_driver.py) has not published observations for "
            "this lane; wrapper rows cannot be judged without them")
    path = Path(location)
    try:
        evidence = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise DriverEvidenceUnusable(f"driver evidence at {path} unreadable: {exc}") from None

    age = time.time() - evidence.get("observed_at", 0)
    if not 0 <= age <= DRIVER_EVIDENCE_MAX_AGE:
        raise DriverEvidenceUnusable(
            f"driver evidence is {int(age)}s old (window {DRIVER_EVIDENCE_MAX_AGE}s); "
            "re-run the host driver rather than trusting a previous lane")

    lane = evidence.get("lane")
    if not lane or lane == SHARED_STACK_LANE:
        raise DriverEvidenceUnusable(
            f"driver evidence names lane {lane!r}; observations must come from an "
            "isolated lane, never the shared stack")

    expected_head = _expected_head()
    if evidence.get("head") != expected_head:
        raise DriverEvidenceUnusable(
            f"driver evidence is bound to head {evidence.get('head')!r}, but this "
            f"tree is {expected_head!r}; evidence from another commit is not "
            "evidence about this one")

    # An observation that never reached the system under test is not an
    # observation of it. Without this, a broken lane produces records that
    # satisfy every binding -- correct head, correct selection, correct lane,
    # fresh timestamp -- while every field describes infrastructure failing.
    # A first driver run did exactly that: six scenarios, all
    # `service "netbox" is not running`, all perfectly bound. The rows would
    # have read "the wrapper did not prepare" and been wrong about why.
    infrastructure_failures = (
        'service "netbox" is not running',
        "no such service",
        "Cannot connect to the Docker daemon",
        "dependency failed to start",
    )
    # Loop variables deliberately not named `scenario`: an earlier version
    # shadowed this function's own parameter, so by the time the record was
    # looked up the name held the last dict from this loop. Every evidence
    # consumer failed with "unhashable type: 'dict'".
    for other_name, other in (evidence.get("scenarios") or {}).items():
        text = f"{other.get('stderr_tail', '')}{other.get('stdout_tail', '')}"
        for marker in infrastructure_failures:
            if marker in text:
                raise DriverEvidenceUnusable(
                    f"scenario {other_name!r} never reached the system under "
                    f"test ({marker!r}); the lane was broken, so nothing here is "
                    "evidence about the contract")

    if not evidence.get("run_id"):
        raise DriverEvidenceUnusable("driver evidence carries no run identity")

    record = (evidence.get("scenarios") or {}).get(scenario)
    if record is None:
        raise DriverEvidenceUnusable(
            f"driver evidence has no scenario {scenario!r}; it was produced by a "
            "driver that does not observe what this row claims")
    # A scenario the driver recorded as blocked is not evidence of anything,
    # and must not reach a row as a KeyError. Blocked rows then fail with the
    # block cited, which is what "annotated, not suppressed" means in
    # practice: loud, specific, and obviously not a contract finding.
    if record.get("blocked_by") and scenario not in AUTHORIZED_BLOCKED_SCENARIOS:
        raise DriverEvidenceUnusable(
            f"scenario {scenario!r} claims blocked_by #{record['blocked_by']} but "
            "is not an authorized #715 block; an injected block marker must not "
            "excuse a row")
    if record.get("blocked_by"):
        raise DriverEvidenceUnusable(
            f"scenario {scenario!r} is blocked by #{record['blocked_by']}: "
            f"{record.get('reason', 'no reason recorded')}")

    if tuple(record.get("selection") or ()) != tuple(expected_selection):
        raise DriverEvidenceUnusable(
            f"scenario {scenario!r} observed selection {record.get('selection')!r}, "
            f"but this row claims {list(expected_selection)!r}")
    record = dict(record)
    record["_run_id"] = evidence["run_id"]
    record["_lane"] = lane
    return record


def _expected_head() -> str:
    """The commit this tree actually is, or a loud failure.

    Fails closed. An unknown head would otherwise turn the strongest binding
    into a no-op, which is the "clean result that examined nothing" shape
    this programme keeps finding.
    """
    pinned = os.environ.get("HH711_EXPECTED_HEAD")
    if pinned:
        return pinned
    root = os.environ.get("HNP_TEST_CHECKOUT_ROOT") or os.environ.get(
        "HNP_TEST_LOCAL_CHECKOUT_ROOT")
    if root:
        try:
            done = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root,
                                  capture_output=True, text=True, timeout=30)
            if done.returncode == 0 and done.stdout.strip():
                return done.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            pass
    raise DriverEvidenceUnusable(
        "cannot establish this tree's head: set HH711_EXPECTED_HEAD or provide a "
        "checkout root with git metadata; an unverifiable head binding is not a "
        "binding")


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
#: Names the injected prerequisite-decision seam the protected fixture
#: delegates to. The fixture decides nothing itself; supplying a seam that
#: implements the real mechanism is what must make the selector rows green.
SEAM_VARIABLE = "HH711_PREREQUISITE_SEAM"

#: Carries the child-side invocation identity into the fixture, so a decision
#: can be bound to the run that produced it rather than merely recorded.
INVOCATION_VARIABLE = "HH711_INVOCATION"

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
        from django.test import SimpleTestCase

        import importlib
        import json
        import os
        import sys

        # This module decides nothing. It asks a prerequisite boundary and
        # applies whatever that boundary returns.
        #
        # DEFAULT PATH: with no seam injected it delegates to the production
        # contract module, {CONTRACT_MODULE!r}. While that module does not
        # exist the import fails, and *that* is the contract-absent form the
        # rows are specified against -- not an unrelated fixture error.
        # Implementing the contract is therefore sufficient to change this
        # path, which is what makes the selector rows satisfiable.
        #
        # A previous version raised a hardcoded RuntimeError here, then a
        # differently hardcoded RuntimeError when a seam was absent. Both
        # made the rows unsatisfiable: no implementation of the contract
        # could alter what this fixture did.
        _request = {{
            "module": "hh711_root.pkg.test_protected",
            "invocation": os.environ.get("{INVOCATION_VARIABLE}", ""),
            "selection": sys.argv[2:],
            "evidence_context": {{
                name: os.environ.get(name, "")
                for name in {list(EVIDENCE_VARIABLES)!r}
            }},
        }}

        _seam = os.environ.get("{SEAM_VARIABLE}")
        if _seam:
            _module_name, _, _attribute = _seam.rpartition(".")
            _decide = getattr(importlib.import_module(_module_name), _attribute)
        else:
            _contract = importlib.import_module("{CONTRACT_MODULE}")
            _decide = _contract.prerequisite_decision

        _decision = _decide(_request)

        # The boundary owns the outcome. Nothing here invents an exit code or
        # a diagnostic; both come from the decision.
        if not getattr(_decision, "allow", False):
            print(getattr(_decision, "diagnostic", ""), flush=True)
            sys.exit(getattr(_decision, "exit_code", 1))


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
    # Absolute, because `cwd` is overridden for the options-only shape:
    # discovery with no labels must start in the fixture tree, and a relative
    # "manage.py" simply does not exist there. The run failed before Django
    # started, which read as "the selection never reached the boundary".
    repository_root = Path(__file__).resolve().parents[3]
    argv = [sys.executable, str(repository_root / "manage.py"), "test", *labels]
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


# --- hold evaluation -------------------------------------------------------

#: Binding a barrier observation must carry before it can be certified. Any
#: one of these alone can be satisfied by a different run; together with the
#: invocation id they cannot. The first mechanical use of this list caught an
#: observation whose `invocation` was empty -- raw fields had looked fine.
REQUIRED_BINDING = ("invocation", "pid", "pgid", "sid", "argv",
                    "resolved_ids", "resolved_modules", "test_count")

#: Only the dedicated persistence control waits this long. Applying it to
#: every held row would add a minute of pure sleeping per row for a property
#: that needs proving once -- the same mistake as re-running an 870-test
#: default to re-learn a resolved label.
PERSISTENCE_GAP_SECONDS = 125


def evaluate_hold(marker_text, log_text, process_alive, observation_gap_s=None,
                  require_persistence=False):
    """Judge one barrier observation. Returns (verdict, reasons).

    Three verdicts, not two. "The barrier never engaged" and "it engaged and
    failed to hold" are different facts; collapsing them is how a timeout
    once read as a successful hold.
    """
    if not marker_text:
        return "rejected", ["no barrier marker: the run was never held"]
    try:
        marker = json.loads(marker_text)
    except ValueError:
        return "unresolved", ["marker present but unparseable"]

    missing = [name for name in REQUIRED_BINDING if not marker.get(name)]
    if missing:
        return "unresolved", [f"marker lacks binding fields: {missing}"]

    reasons = []
    if "Ran " in log_text and " test" in log_text:
        return "rejected", ["a result line exists: bodies ran despite the marker"]
    reasons.append("no result line in log")

    if not process_alive:
        return "rejected", ["the child is gone: a dead process is not a held one"]
    reasons.append("child alive at marker pid")

    if require_persistence:
        if observation_gap_s is None or observation_gap_s < PERSISTENCE_GAP_SECONDS:
            return "unresolved", [
                f"observation gap {observation_gap_s}s is below "
                f"{PERSISTENCE_GAP_SECONDS}s; too short to show the hold persists "
                "while the host is not watching"]
        reasons.append(f"still held {observation_gap_s}s after acknowledgement, unobserved")
    return "held", reasons


# --- decision binding ------------------------------------------------------

def validate_decision_binding(ledger_entries, expected_invocation,
                              expected_selection, expected_module):
    """Is this refusal backed by a decision bound to *this* run?

    Returns (ok, reasons). Exists because exit code, diagnostic token and an
    absence of bodies are all forgeable: a stand-in that invents a refusal
    from a private variable produces exactly those three. Dev B demonstrated
    it against `assert_refused`, which passed an emitter-shaped outcome with
    matching exit and token and no binding at all.

    What cannot be forged without actually reaching the boundary is a
    decision that echoes the invocation this run generated and the selection
    the boundary itself normalized.
    """
    if not ledger_entries:
        return False, ["no decision was recorded: the refusal is unattributed"]
    bound = [entry for entry in ledger_entries
             if (entry.get("decision") or {}).get("invocation") == expected_invocation]
    if not bound:
        seen = sorted({(e.get("decision") or {}).get("invocation", "")
                       for e in ledger_entries})
        return False, [
            f"no decision carried this run's invocation {expected_invocation!r}; "
            f"saw {seen}. A refusal whose decision is not bound to this run "
            "could have been fabricated by anything."]
    decision = bound[0]["decision"]
    request = bound[0].get("request") or {}
    reasons = [f"decision bound to {expected_invocation!r}"]

    if tuple(decision.get("normalized_selection") or ()) != tuple(expected_selection):
        return False, [
            f"decision normalized the selection to "
            f"{tuple(decision.get('normalized_selection') or ())!r}, expected "
            f"{tuple(expected_selection)!r}"]
    reasons.append("normalized selection matches")

    if request.get("module") != expected_module:
        return False, [f"decision was made for module {request.get('module')!r}, "
                       f"expected {expected_module!r}"]
    reasons.append("decision made for the protected module")
    return True, reasons
