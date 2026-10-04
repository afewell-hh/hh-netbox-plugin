"""Host-side, test-only driver for the #711 supported-runner contract.

Not a product entry point and not imported by any shipped code path. It is
run on the host before the container suite, in the same shape as
`scripts/prove_reaper_lane.py`: it observes real behaviour and publishes
facts that container tests consume. The container never invokes it, has no
Docker socket, and no production preparation API is added for it (Dev B's
disposition on #713).

What it observes
----------------
It invokes the **real** supported wrapper -- `scripts/run_diet_tests.sh` --
inside a disposable copy of the checkout at a known commit, against an
isolated Compose lane, and records what actually happened: exit status,
parsed execution count, whether fixture bodies announced themselves,
whether preparation ran, and the emitted remediation command.

Why every record is bound
-------------------------
An observation that cannot be tied to what produced it can be replayed. Each
record carries the exact head, the selection, the lane, and a per-run
identity with a timestamp, and the consuming rows verify all four. Stale,
borrowed or mismatched evidence must fail rather than quietly satisfy a row.

Recursion
---------
The measured #713 failure was broad selections rediscovering and respawning
the driver. Two independent guards here: no scenario selection may name this
suite (asserted, not assumed), and the driver refuses to start if it finds
its own guard variable already set in the environment.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path


GUARD_VARIABLE = "HH711_DRIVER_ACTIVE"
DRIVER_SUITE = "netbox_hedgehog.tests.test_interchange.test_runner_contract_red"
EVIDENCE_VERSION = 1

#: The declaration the wrapper consults to decide what needs preparation.
#: Scenario `declaration_removed` deletes exactly one entry from a disposable
#: copy of this, never from the real checkout.
WRAPPER_SELECTION_GUARD = "netbox_hedgehog.tests.test_interchange"


@dataclass
class ScenarioRecord:
    name: str
    selection: tuple[str, ...]
    returncode: int
    tests_executed: int
    prepared: bool
    markers: tuple[str, ...]
    remediation: str
    stdout_tail: str
    stderr_tail: str
    notes: str = ""


@dataclass
class DriverEvidence:
    version: int
    head: str
    lane: str
    checkout: str
    run_id: str
    observed_at: int
    scenarios: dict = field(default_factory=dict)


def _run(argv, cwd=None, env=None, timeout=1800):
    environment = dict(os.environ)
    environment[GUARD_VARIABLE] = "1"
    if env:
        environment.update(env)
    process = subprocess.Popen(
        argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        cwd=str(cwd) if cwd else None, env=environment, start_new_session=True)
    try:
        out, err = process.communicate(timeout=timeout)
        return process.returncode, out, err
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(process.pid), 9)
        except OSError:
            pass
        out, err = process.communicate()
        return -1, out or "", err or ""


def _tests_executed(text: str) -> int:
    import re
    match = re.search(r"^Ran (\d+) test", text, re.MULTILINE)
    return int(match.group(1)) if match else 0


#: Supported options that take a separate value. The value after one of
#: these is an argument to the option, never a test label.
OPTIONS_WITH_VALUES = ("--exclude-tag", "--tag", "--parallel", "--settings",
                       "--pythonpath", "--testrunner", "-k")


def positional_labels(selection) -> tuple:
    """The test labels in an argv, excluding options and their values.

    This exists because the first version did not have it, and the guard
    below refused the `option_value_lookalike` scenario -- reading
    `--exclude-tag netbox_hedgehog.tests.test_interchange` as a selection of
    that package. That is exactly the defect T12 describes: an option value
    that resembles a protected label is not a selection of it. The guard
    made the mistake the row exists to catch.
    """
    labels, skip_next = [], False
    for argument in selection:
        if skip_next:
            skip_next = False
            continue
        if argument in OPTIONS_WITH_VALUES:
            skip_next = True
            continue
        if argument.startswith("-"):
            continue
        labels.append(argument)
    return tuple(labels)


def _reaches_driver_suite(selection) -> bool:
    return any(label == DRIVER_SUITE or DRIVER_SUITE.startswith(f"{label}.")
               for label in positional_labels(selection))


def _assert_recursion_safe(name: str, selection, broad: bool) -> None:
    """Allow a broad selection to include this suite only deliberately.

    A first version refused any selection reaching the driver suite, which
    would have refused `broad_supported` -- the very scenario the review
    requires, since "the supported wrapper broad selection must prepare"
    cannot be observed without selecting broadly.

    Including it is safe now, and only now, for two reasons that are
    asserted rather than hoped:

    * The driver cannot be re-entered. It sets `GUARD_VARIABLE` for every
      child and refuses to start when it sees it, so nothing beneath this
      invocation can start another driver.
    * Since the B2 rework the container rows spawn only a disposable fixture
      tree that names nothing in the suite. The recursive rediscovery
      measured on #713 came from rows spawning broad *real* selections; that
      path no longer exists.

    A narrow scenario that reaches the driver suite is still refused, because
    there is no reason for one to and it would signal the hazard returning.
    """
    if _reaches_driver_suite(selection) and not broad:
        raise SystemExit(
            f"refusing scenario {name!r}: narrow selection {selection!r} reaches "
            f"{DRIVER_SUITE}; this is the recursive rediscovery measured on #713")


def make_disposable_checkout(source: Path, head: str, destination: Path) -> Path:
    """A copy of the checkout at `head` that scenarios may mutate freely.

    Mutating a disposable copy is appropriate; mutating the shared checkout
    is not, and nothing here writes to `source`.
    """
    destination.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "worktree", "add", "--detach", str(destination), head],
                   cwd=str(source), check=True, capture_output=True, text=True)
    return destination


def observe_lifecycle(lane: str, since: float, until: float) -> list:
    """Container create/start events attributable to one scenario's window.

    Dev B's T02 is explicit that an end-of-run `docker ps` is the vacuous
    version: real preparation creates containers and removes them again, so
    a snapshot afterwards sees nothing and a check built on one passes
    whether or not preparation ever happened. Events are read for the
    scenario's own time window instead.
    """
    done = subprocess.run(
        ["docker", "events", "--since", str(int(since)), "--until", str(int(until)),
         "--filter", "event=create", "--filter", "event=start", "--format",
         "{{.Action}} {{.Actor.Attributes.name}}"],
        capture_output=True, text=True, timeout=120)
    events = []
    for line in done.stdout.splitlines():
        parts = line.split(None, 1)
        if len(parts) == 2 and lane in parts[1]:
            events.append({"action": parts[0], "name": parts[1]})
    return events


def run_scenarios(checkout: Path, netbox_docker: Path, lane: str,
                  selections: dict) -> dict:
    """Invoke the real wrapper once per scenario and record what happened."""
    wrapper = checkout / "scripts" / "run_diet_tests.sh"
    if not wrapper.is_file():
        raise SystemExit(f"supported wrapper not found at {wrapper}")

    records = {}
    for name, (selection, broad) in selections.items():
        _assert_recursion_safe(name, selection, broad)
        env = {"NETBOX_DOCKER_DIR": str(netbox_docker), "COMPOSE_PROJECT_NAME": lane}
        started = time.time()
        code, out, err = _run([str(wrapper), *selection], cwd=checkout, env=env)
        elapsed = time.time() - started
        combined = f"{out}\n{err}"
        lifecycle = observe_lifecycle(lane, started, time.time() + 1)
        markers = tuple(m for m in ("HH711_ORDINARY_BODY_RAN", "HH711_PROTECTED_BODY_RAN")
                        if m in combined)
        remediation = ""
        for line in combined.splitlines():
            if "run_diet_tests.sh" in line and line.strip().startswith(("Run", "run", "$", "scripts/")):
                remediation = line.strip()
                break
        records[name] = asdict(ScenarioRecord(
            name=name,
            selection=tuple(selection),
            returncode=code,
            tests_executed=_tests_executed(combined),
            prepared="prove_reaper_lane" in combined or "snapshot" in combined,
            markers=markers,
            remediation=remediation,
            stdout_tail=out[-2000:],
            stderr_tail=err[-2000:],
            notes=json.dumps({"elapsed_seconds": round(elapsed, 1),
                              "lifecycle": lifecycle}),
        ))
    return records


def observe_preflight_then_invalidate(checkout: Path, netbox_docker: Path,
                                      lane: str, selection) -> dict:
    """Prepare for real, invalidate the evidence, then run the real consumer.

    The claim under test is narrow: a preflight that has *succeeded* must not
    become a standing exemption from the integrity checks that run later. So
    the sequence matters. Preparation runs through the supported path and has
    to succeed first -- otherwise any later rejection could simply be the
    preflight refusing, which proves the opposite of the claim. Only then is
    the evidence invalidated, and only then does the real consumer run.

    Corrupting the evidence up front would be the weaker experiment Dev B
    warned against: a stronger prerequisite validator could legitimately
    reject it at the gate, and the row would pass while the downstream
    checks stayed untested.
    """
    prepare = checkout / "scripts" / "prove_reaper_lane.py"
    evidence_path = Path(f"/tmp/hh711-consumer-evidence-{uuid.uuid4().hex[:8]}.json")
    env = {"NETBOX_DOCKER_DIR": str(netbox_docker), "COMPOSE_PROJECT_NAME": lane}

    code, out, err = _run([sys.executable, str(prepare), "--output", str(evidence_path)],
                          cwd=checkout, env=env, timeout=900)
    preflight_ok = code == 0 and evidence_path.is_file()

    invalidated = False
    if preflight_ok:
        try:
            data = json.loads(evidence_path.read_text(encoding="utf-8"))
            # Invalidate without deleting: the file still exists and parses,
            # so a consumer that merely checks for presence will not notice.
            data["observed_at"] = int(time.time()) - 86_400
            evidence_path.write_text(json.dumps(data), encoding="utf-8")
            invalidated = True
        except (OSError, ValueError):
            invalidated = False

    consumer_code, consumer_out, consumer_err = _run(
        ["docker", "compose", "exec", "-T", "netbox", "python", "-u", "manage.py",
         "test", *selection, "--keepdb"],
        cwd=netbox_docker,
        env={"COMPOSE_PROJECT_NAME": lane,
             "HNP_REAPER_CONTAINER_EVIDENCE": str(evidence_path)},
        timeout=900)
    combined = f"{consumer_out}\n{consumer_err}"
    evidence_path.unlink(missing_ok=True)
    return {
        "name": "preflight_then_invalidated",
        "selection": list(selection),
        "preflight_ok": preflight_ok,
        "invalidated": invalidated,
        "returncode": consumer_code,
        "timed_out": consumer_code == -1,
        "tests_executed": _tests_executed(combined),
        "integrity_token_seen": "HarnessEvidenceMissing" in combined,
        "stdout_tail": consumer_out[-2000:],
        "stderr_tail": consumer_err[-2000:],
        "prepare_tail": (out + err)[-1000:],
    }


def observe_remediation_round_trip(checkout: Path, netbox_docker: Path, lane: str,
                                   selection) -> dict:
    """Take the command the refusal prints, and actually run it.

    A remediation row that only matches substrings passes on a command that
    cannot work. The emitted string is executed verbatim in the same isolated
    lane, and the result of that execution is what the row judges.
    """
    wrapper = checkout / "scripts" / "run_diet_tests.sh"
    env = {"NETBOX_DOCKER_DIR": str(netbox_docker), "COMPOSE_PROJECT_NAME": lane}
    code, out, err = _run([sys.executable, "-c", "import sys; sys.exit(0)"], cwd=checkout)

    # Provoke the refusal on the raw path, which is what prints remediation.
    raw_code, raw_out, raw_err = _run(
        ["docker", "compose", "exec", "-T", "netbox", "python", "-u", "manage.py",
         "test", *selection, "--keepdb"],
        cwd=netbox_docker, env={"COMPOSE_PROJECT_NAME": lane}, timeout=900)
    raw_combined = f"{raw_out}\n{raw_err}"

    emitted = ""
    for line in raw_combined.splitlines():
        if "run_diet_tests.sh" in line:
            emitted = line.strip().lstrip("$").strip()
            break

    executed_code, executed_out, executed_err = -2, "", ""
    if emitted:
        executed_code, executed_out, executed_err = _run(
            ["bash", "-lc", emitted], cwd=checkout, env=env, timeout=1800)
    executed_combined = f"{executed_out}\n{executed_err}"
    return {
        "name": "remediation_round_trip",
        "selection": list(selection),
        "raw_returncode": raw_code,
        "emitted": emitted,
        "executed_returncode": executed_code,
        "executed_tests": _tests_executed(executed_combined),
        "stdout_tail": executed_out[-2000:],
        "stderr_tail": executed_err[-2000:],
    }


def observe_declaration_removal(checkout: Path, netbox_docker: Path, lane: str,
                                protected_module: str) -> dict:
    """Remove one real declaration in the disposable copy, then restore it.

    The declaration today lives in the supported wrapper itself, which names
    the evidence-requiring modules. Removing one there is removing a real
    declaration, not simulating one. The shared checkout is never touched:
    `checkout` is a throwaway worktree.
    """
    wrapper = checkout / "netbox_hedgehog" / "scripts" / "run_diet_tests.sh"
    original = wrapper.read_text(encoding="utf-8")
    env = {"NETBOX_DOCKER_DIR": str(netbox_docker), "COMPOSE_PROJECT_NAME": lane}
    # The wrapper declares evidence-requiring modules by source path, e.g.
    # `netbox_hedgehog/tests/test_interchange/test_checkout_containment.py`,
    # not by dotted name. A first version searched for the dotted tail,
    # matched nothing, and reported declaration_actually_removed=False --
    # the row asserted that flag and failed loudly rather than passing on a
    # mutation that never happened.
    declared_path = protected_module.replace(".", "/") + ".py"

    # Substitute, do not delete. The declaration sits inside a shell `case`
    # arm, and deleting the line left `run_diet_tests.sh` with a syntax error
    # at line 43 -- so the previous run observed bash failing to parse the
    # script, not the wrapper failing to prepare. Replacing the path with a
    # name that matches nothing removes the declaration while keeping the
    # script valid, which is the mutation actually intended.
    sentinel = "netbox_hedgehog/tests/test_interchange/hh711_no_such_declaration.py"
    mutated = original.replace(declared_path, sentinel)
    actually_removed = mutated != original
    wrapper.write_text(mutated, encoding="utf-8")
    syntax = subprocess.run(["bash", "-n", str(wrapper)], capture_output=True, text=True)
    try:
        removed_code, removed_out, removed_err = _run(
            [str(checkout / "scripts" / "run_diet_tests.sh"), protected_module],
            cwd=checkout, env=env, timeout=1800)
        removed_combined = f"{removed_out}\n{removed_err}"
    finally:
        wrapper.write_text(original, encoding="utf-8")

    restored_code, restored_out, restored_err = _run(
        [str(checkout / "scripts" / "run_diet_tests.sh"), protected_module],
        cwd=checkout, env=env, timeout=1800)
    restored_combined = f"{restored_out}\n{restored_err}"
    return {
        "name": "declaration_removed",
        "selection": [protected_module],
        "declaration_actually_removed": actually_removed,
        "mutated_script_still_parses": syntax.returncode == 0,
        "mutated_script_syntax_error": syntax.stderr[-300:],
        "removed_returncode": removed_code,
        "removed_tests": _tests_executed(removed_combined),
        "removed_prepared": "prove_reaper_lane" in removed_combined,
        "restored_returncode": restored_code,
        "restored_tests": _tests_executed(restored_combined),
        "restored_prepared": "prove_reaper_lane" in restored_combined,
        "stdout_tail": removed_out[-2000:],
        "stderr_tail": removed_err[-2000:],
    }


def main(argv=None) -> int:
    if os.environ.get(GUARD_VARIABLE):
        print(f"{GUARD_VARIABLE} is set: refusing to run the driver inside itself",
              file=sys.stderr)
        return 2

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", type=Path, required=True,
                        help="source checkout; never mutated")
    parser.add_argument("--netbox-docker", type=Path, required=True)
    parser.add_argument("--lane", required=True,
                        help="isolated Compose project name; must not be the shared stack")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workdir", type=Path, default=None)
    args = parser.parse_args(argv)

    if args.lane in ("netbox-docker", ""):
        print("refusing to drive the shared stack", file=sys.stderr)
        return 2

    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(args.checkout),
                          capture_output=True, text=True, check=True).stdout.strip()

    workdir = args.workdir or Path(f"/tmp/hh711-driver-{uuid.uuid4().hex[:8]}")
    disposable = make_disposable_checkout(args.checkout, head, workdir / "checkout")
    try:
        # (selection, broad): `broad` marks a scenario that must select
        # widely enough to include this suite. See _assert_recursion_safe.
        selections = {
            "declared_ok": (
                ("netbox_hedgehog.tests.test_interchange.test_reaper_adapter_red",), False),
            "broad_supported": (("netbox_hedgehog.tests.test_interchange",
                                 "--exclude-tag", "slow"), True),
            "sibling_not_inside": (
                ("netbox_hedgehog.tests.test_interchange_audit_retention",), False),
            # T10/T02-negative: the topology fast path must stay fast and
            # create no preparation containers. Timing is reported, not gated
            # on a ratio, per Dev B.
            "topology_fast_path": (
                ("netbox_hedgehog.tests.test_topology_planning.test_port_allocator",), False),
            # T12: a supported option whose *value* resembles a protected
            # label must not trigger preparation.
            "option_value_lookalike": (
                ("netbox_hedgehog.tests.test_topology_planning.test_port_allocator",
                 "--exclude-tag", "netbox_hedgehog.tests.test_interchange"), False),
            # T11: no-argument invocation keeps its explicit topology default.
            "no_argument_default": ((), False),
        }
        scenarios = run_scenarios(disposable, args.netbox_docker, args.lane, selections)
        protected = "netbox_hedgehog.tests.test_interchange.test_reaper_adapter_red"
        scenarios["remediation_round_trip"] = observe_remediation_round_trip(
            disposable, args.netbox_docker, args.lane, (protected,))
        # The wrapper declares exactly one evidence-requiring module by path,
        # so that is the declaration a removal test can genuinely remove.
        # Targeting a module the wrapper never declared would mutate nothing
        # and prove nothing.
        declared = "netbox_hedgehog.tests.test_interchange.test_checkout_containment"
        scenarios["declaration_removed"] = observe_declaration_removal(
            disposable, args.netbox_docker, args.lane, declared)
        scenarios["preflight_then_invalidated"] = observe_preflight_then_invalidate(
            disposable, args.netbox_docker, args.lane,
            ("netbox_hedgehog.tests.test_interchange.test_reaper_adapter_red",))

        evidence = DriverEvidence(
            version=EVIDENCE_VERSION, head=head, lane=args.lane,
            checkout=str(disposable), run_id=uuid.uuid4().hex,
            observed_at=int(time.time()), scenarios=scenarios)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(asdict(evidence), indent=2, sort_keys=True),
                               encoding="utf-8")
        print(f"wrote {args.output} ({len(scenarios)} scenarios, head {head[:9]})")
        return 0
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", str(disposable)],
                       cwd=str(args.checkout), capture_output=True, text=True)
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
