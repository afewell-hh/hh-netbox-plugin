"""#716 B1b: the single controlled host-exec orphan baseline. Test-only.

One purpose: deliberately create an orphan in a disposable scenario
container in order to demonstrate the B1a-reviewed rescue path on it. Not a
general driver run.

It reuses B1a's accepted primitives rather than reimplementing them, so the
reviewed verification and teardown are the ones exercised here.

Two properties the first (invalidated) baseline lacked:

* the inner subject is launched by the SAME single non-detached
  `docker compose exec` that is later terminated, so its survival is
  attributable to that termination. The earlier version launched a detached
  subject and killed an unrelated exec.
* the child publishes its inner parent/child relationship, so "this is the
  child of the exec we killed" is evidence rather than assumption.

Every preflight item must be present and verified. If any is absent,
stale, mismatched or unknown, the subject is never launched.
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

_HERE = Path(__file__).resolve().parent


def _load(name):
    import importlib.util
    spec = importlib.util.spec_from_file_location(f"hh716_{name}", _HERE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"hh716_{name}"] = module
    spec.loader.exec_module(module)
    return module


PROVER = _load("containment_prover")
UNKNOWN = "unknown"
PUBLICATION_DIR = PROVER.PUBLICATION_DIR
# The decoy must wear the run's ACTUAL label value. A first version used a
# distinct value ("copied-label-decoy"), which a label-discovery destroyer
# filtering on hh716.run=<run_id> would never have selected -- so it tested
# nothing about same-label discrimination. It is the identical label, plus
# deliberate absence from the registry, that makes it a trap.


def _observe(argv, timeout=60):
    """Run a read-only command and report whether the observation happened.

    Returns {"ok": bool, "out": str, "why": str}. `ok` is False for a
    non-zero exit, a timeout or an OSError, so a caller cannot mistake a
    failed observation for an empty result.
    """
    try:
        done = subprocess.run(argv, capture_output=True, text=True,
                              timeout=timeout)
    except (subprocess.SubprocessError, OSError) as exc:
        return {"ok": False, "out": "", "why": f"{type(exc).__name__}: {exc}"}
    if done.returncode != 0:
        return {"ok": False, "out": "",
                "why": f"exit {done.returncode}: {done.stderr.strip()[:120]}"}
    return {"ok": True, "out": done.stdout.strip(), "why": ""}


def prove_rescue_readiness(container_id, registry, lifecycle):
    """Readiness means the owner RAN and cleaned a disposable subject.

    The previous check asserted `docker cp` exited 0, which is installation.
    A syntactically broken or non-runnable owner passed preflight, and
    preflight's whole job is to refuse launch unless rescue is known to
    work.
    """
    nonce = PROVER.launch_owned_subject(container_id, registry, "readiness",
                                        lifecycle)
    time.sleep(2)
    publication, why = PROVER.read_publication(container_id, nonce)
    bound, bind_why = PROVER.bind(registry, publication)
    if not bound:
        return False, {"stage": "bind", "why": why or bind_why}
    verified, vwhy = PROVER.run_rescue(container_id, [bound], False)
    if not verified or not verified["reports"][0]["verified"]:
        return False, {"stage": "verify", "report": verified or vwhy}
    cleaned, cwhy = PROVER.run_rescue(container_id, [bound], True)
    if not cleaned:
        return False, {"stage": "signal", "why": cwhy}
    outcome = cleaned["reports"][0]["outcome"]
    return outcome in ("reaped", "terminated_zombie"), {
        "verify": verified["reports"][0], "clean": cleaned["reports"][0]}


def preflight(image, lane, run_id, evidence, registry, lifecycle,
              fixture_registry, workspace):
    """Every item verified, through B1a registration, before any launch.

    Each check below can fail. The previous set could not: a typo'd lane
    name passed `dedicated_lane`, a substring match passed `worktree`, a
    freshly created id trivially passed `no_shared_target`, and
    `rescue_owner_ready` only meant a file had been copied.
    """
    checks = {}

    # The lane must be a real Compose project that is not the shared one.
    projects = _observe(
        ["docker", "ps", "--filter", f"label=com.docker.compose.project={lane}",
         "--format", "{{.ID}}"])
    checks["lane_observed"] = projects["ok"]
    checks["lane_is_a_real_compose_project"] = projects["ok"] and bool(
        projects["out"])
    checks["lane_is_not_the_shared_project"] = lane != "netbox-docker"

    # A worktree distinct from the primary checkout, asserted via git.
    toplevel = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                              cwd=str(_HERE), capture_output=True, text=True,
                              timeout=60).stdout.strip()
    common = subprocess.run(["git", "rev-parse", "--git-common-dir"],
                            cwd=str(_HERE), capture_output=True, text=True,
                            timeout=60).stdout.strip()
    checks["is_a_dedicated_worktree"] = bool(toplevel) and bool(common) and (
        Path(common).resolve() != Path(toplevel, ".git").resolve())

    # Scenario SERVICE, created through Compose and registered by its
    # resolved exact immutable ID. The supported wrapper reaches NetBox
    # through compose exec, so the subject boundary must be the same;
    # the Docker CLI stays for read-only inspection and exact-ID
    # teardown only.
    project, container_id, why = create_scenario_compose_service(
        image, run_id, workspace, registry, lifecycle)
    checks["compose_project_is_scenario_specific"] = (
        project == compose_project_name(run_id) and project != lane)
    checks["scenario_container_created_and_registered"] = bool(
        container_id) and container_id in registry.containers
    if not container_id:
        evidence["preflight_failure"] = f"compose scenario service: {why}"
        return None, None, checks, project
    registry.container_id = container_id

    # The service must STILL resolve to the registered id. Re-resolved
    # here rather than reused from creation: a recreated service
    # container answers to the same service name under a different id,
    # and adopting it silently is the failure this proves against.
    resolved, resolve_why = resolve_compose_container(project, workspace)
    checks["compose_service_resolves_to_registered_id"] = (
        resolved == container_id)
    identity_ok, identity_why = verify_compose_identity(container_id, project)
    checks["compose_identity_matches_project_and_service"] = identity_ok
    if resolved != container_id or not identity_ok:
        evidence["preflight_failure"] = (
            f"compose identity: resolved={resolved} "
            f"registered={container_id} {resolve_why or identity_why}")
        return None, None, checks, project

    state, _ = PROVER._inspect_state(container_id)
    checks["container_present_and_identified"] = state == "present"
    checks["immutable_id_is_64_hex"] = (
        len(container_id) == 64
        and all(character in "0123456789abcdef" for character in container_id))

    # Its Compose/ownership labels must not be the shared project's.
    # Each observation's status is checked. Previously a failed inspect
    # produced "" which merely differed from "netbox-docker", so the check
    # passed on an observation that never happened.
    label_probe = _observe(
        ["docker", "inspect", container_id, "--format",
         "{{index .Config.Labels \"com.docker.compose.project\"}}"])
    checks["scenario_project_label_observed"] = label_probe["ok"]
    checks["scenario_not_in_shared_project"] = (
        label_probe["ok"] and label_probe["out"] != "netbox-docker")

    shared_probe = _observe(
        ["docker", "ps", "-aq", "--filter", "name=netbox-docker-"])
    checks["shared_containers_observed"] = shared_probe["ok"]
    checks["no_shared_container_is_a_target"] = shared_probe["ok"] and all(
        not container_id.startswith(entry)
        for entry in shared_probe["out"].split())

    if not PROVER.install_rescue_owner(container_id,
                                       _HERE / "containment_rescue.py"):
        checks["rescue_owner_installed"] = False
        evidence["preflight"] = {"checks": checks, "container_id": container_id}
        return container_id, None, checks, project
    checks["rescue_owner_installed"] = True

    # READINESS BY EXECUTION, before the baseline subject exists.
    ready, detail = prove_rescue_readiness(container_id, registry, lifecycle)
    checks["rescue_owner_proven_by_execution"] = ready
    evidence["rescue_readiness"] = detail

    # An unregistered decoy wearing the run's ACTUAL label.
    # The decoy is created the same way the scenario container is:
    # `docker create` returns the immutable id synchronously, the id is
    # registered in a fixture registry, and only then is it started.
    #
    # Name-based recovery is gone. It resolved a name to whatever id
    # currently held it, so a foreign container left by an earlier run -- or
    # belonging to someone else -- would have been adopted and deleted. A
    # name is not ownership, for the same reason a label is not.
    decoy_id = ""
    created = _observe(
        ["docker", "create", "--label", f"hh716.run={run_id}",
         "--label", f"hh716.fixture={run_id}", image, "sleep", "600"])
    checks["decoy_create_observed"] = created["ok"]
    if created["ok"] and len(created["out"]) == 64:
        decoy_id = created["out"]
        fixture_registry.append(decoy_id)          # registered BEFORE start
        evidence.setdefault("fixture_registry", []).append(decoy_id)
        # The registry's real contents at the moment the container is
        # started. Asserting only that the id ends up registered is
        # satisfied by registering after start; this snapshot is not.
        evidence["fixture_registry_at_decoy_start"] = list(fixture_registry)
        started = _observe(["docker", "start", decoy_id])
        checks["decoy_started"] = started["ok"]
    else:
        checks["decoy_started"] = False

    checks["same_label_decoy_live"] = bool(decoy_id)
    checks["decoy_is_not_in_scenario_registry"] = decoy_id not in registry.containers
    checks["decoy_is_in_fixture_registry"] = decoy_id in fixture_registry

    discovery = _observe(
        ["docker", "ps", "-q", "--filter", f"label=hh716.run={run_id}"])
    checks["label_discovery_observed"] = discovery["ok"]
    discovered = discovery["out"].split() if discovery["ok"] else []
    short = {entry[:12] for entry in discovered}
    checks["label_discovery_would_select_decoy"] = decoy_id[:12] in short

    # THE PURPOSE, stated directly: label discovery can see a same-label
    # resource the scenario registry does not own.
    #
    # The former `len(short) > 1` was an implementation-era proxy. It
    # held only because the scenario container was created by
    # `docker create --label hh716.run=...`; once Compose correctly
    # stopped carrying that label the count fell to one and the proxy
    # became false while the property it stood for stayed true. Live
    # run 2 failed on the proxy, not on the property.
    #
    # Matched on the exact immutable ID, never a display name, and the
    # selected decoy must be absent from the scenario registry.
    selected_unowned = [entry for entry in discovered
                        if decoy_id.startswith(entry)
                        and entry not in registry.containers
                        and decoy_id not in registry.containers]
    checks["label_discovery_selects_an_unowned_same_label_resource"] = (
        discovery["ok"] and bool(selected_unowned))

    # And discovery must never feed the authorized teardown set: that
    # set is the registry, by exact registered ID, and nothing a filter
    # returned may enter it.
    checks["discovery_ids_are_not_in_the_teardown_set"] = not any(
        any(candidate.startswith(entry) for entry in short)
        for candidate in registry.containers)

    evidence["preflight"] = {
        "checks": checks,
        "label_discovery_candidates": sorted(short),
        "container_id": container_id,
        "compose_project": project,
        "compose_service": SCENARIO_SERVICE,
        "decoy_container_id": decoy_id,
        "lane": lane,
        "run_id": run_id,
        "observation_deadline_seconds": 180,
    }
    return container_id, decoy_id, checks, project


def _subject_script(nonce, marker):
    """The shell the exec runs: publish self, spawn child, publish
    child, wait. Unchanged by the Compose repair -- only the client
    boundary that carries it changed."""
    script = (
        f"mkdir -p {PUBLICATION_DIR}; "
        f"pstat=$(cat /proc/$$/stat); set -- ${{pstat#*) }}; "
        f"printf '%s' \"{{\\\"role\\\":\\\"exec_parent\\\",\\\"nonce\\\":\\\"{nonce}\\\","
        f"\\\"pid\\\":$$,\\\"start_ticks\\\":\\\"${{20}}\\\","
        f"\\\"pgid\\\":\\\"$3\\\",\\\"sid\\\":\\\"$4\\\"}}\" "
        f"> {PUBLICATION_DIR}/{nonce}.parent.json; "
        f"python3 -c 'import time; time.sleep(900)' {marker} & "
        f"child=$!; "
        f"cstat=$(cat /proc/$child/stat); set -- ${{cstat#*) }}; "
        f"printf '%s' \"{{\\\"role\\\":\\\"inner_child\\\",\\\"nonce\\\":\\\"{nonce}\\\","
        f"\\\"pid\\\":$child,\\\"ppid\\\":\\\"$2\\\","
        f"\\\"start_ticks\\\":\\\"${{20}}\\\",\\\"pgid\\\":\\\"$3\\\","
        f"\\\"sid\\\":\\\"$4\\\"}}\" "
        f"> {PUBLICATION_DIR}/{nonce}.child.json; "
        f"wait")
    return script


# ----------------------------------------------------------------------
# Compose fidelity (#716 lead disposition).
#
# The supported wrapper reaches NetBox through `docker compose exec`, so
# a plain `docker exec` client cannot establish the behaviour of the
# client boundary this baseline exists to demonstrate. The subject is
# launched and terminated through one `docker compose -p <project> exec
# <service>` invocation.
#
# The Docker CLI remains only for read-only exact-ID inspection and
# registry-authorized exact-ID teardown. It is never a substitute
# subject-launch or host-client boundary.
# ----------------------------------------------------------------------

#: One service, named once, so the name cannot drift between the file,
#: the resolve step and the exec.
SCENARIO_SERVICE = "subject"


def compose_project_name(run_id):
    """A fresh project per run, so nothing is shared or reused."""
    return f"hh716b-{run_id[:12]}"


def compose_file_text(image):
    return (
        "services:\n"
        f"  {SCENARIO_SERVICE}:\n"
        f"    image: {image}\n"
        '    command: ["sleep", "3600"]\n'
        "    labels:\n"
        "      hh716.role: scenario-subject\n")


def compose_argv(project, workspace, *rest):
    """The ONE canonical Compose invocation shape.

    Every Compose call in this module is built here, so a control can
    assert the baseline command is a compose exec and cannot be swapped
    for plain `docker exec` without this function changing.
    """
    return ["docker", "compose", "-p", project,
            "-f", str(workspace / "compose.yaml"), *rest]


def resolve_compose_container(project, workspace):
    """The exact immutable ID Compose resolved for the service.

    `-a` is REQUIRED, not cosmetic. This runs between `create` and
    `start`, and `docker compose ps` without `--all` lists only running
    services -- so the resolve returned nothing, the registry was never
    given an exact ID, and the one authorized live baseline aborted at
    preflight. The mocked fake had answered regardless of container
    state, so the whole suite passed over a sequence that cannot work
    against a real daemon.
    """
    done = _observe(compose_argv(project, workspace, "ps", "-a", "-q",
                                 SCENARIO_SERVICE))
    if not done["ok"]:
        return None, f"compose ps failed: {done['why']}"
    ids = [line.strip() for line in done["out"].splitlines() if line.strip()]
    if len(ids) != 1:
        return None, f"compose ps resolved {len(ids)} containers, not 1"
    container_id = ids[0]
    if len(container_id) != 64 or any(
            c not in "0123456789abcdef" for c in container_id):
        return None, f"compose ps returned a non-exact id: {container_id!r}"
    return container_id, ""


def verify_compose_identity(container_id, project):
    """The container must BE the registered id and belong to this
    project and service.

    Checked by inspecting the resolved id, not by trusting the name
    Compose was asked about: a recreated service container answers to
    the same service name under a different id, which is exactly the
    adoption this must refuse.
    """
    done = _observe([
        "docker", "inspect", container_id, "--format",
        '{{.Id}} {{index .Config.Labels "com.docker.compose.project"}} '
        '{{index .Config.Labels "com.docker.compose.service"}}'])
    if not done["ok"]:
        return False, f"inspect failed: {done['why']}"
    parts = done["out"].split()
    if len(parts) != 3:
        return False, f"inspect returned {len(parts)} fields, not 3"
    got_id, got_project, got_service = parts
    if got_id != container_id:
        return False, f"inspect id {got_id[:12]} != {container_id[:12]}"
    if got_project != project:
        return False, f"project {got_project!r} != {project!r}"
    if got_service != SCENARIO_SERVICE:
        return False, f"service {got_service!r} != {SCENARIO_SERVICE!r}"
    return True, ""


def create_scenario_compose_service(image, run_id, workspace, registry,
                                    lifecycle=None):
    """create -> resolve exact ID -> register -> verify identity -> start.

    Registration happens as soon as an exact ID exists and before any
    verification, so a failed check never leaves an unnameable
    container, which is the ordering B1a already established.
    """
    project = compose_project_name(run_id)

    def note(event, container_id=None):
        if lifecycle is not None:
            lifecycle.append({
                "event": event, "at": time.time(), "project": project,
                "service": SCENARIO_SERVICE, "container_id": container_id,
                "registered_containers": list(
                    registry.containers if registry is not None else []),
            })

    try:
        (workspace / "compose.yaml").write_text(compose_file_text(image),
                                                encoding="utf-8")
    except OSError as exc:
        return None, None, f"could not write the compose file: {exc}"

    created = _observe(compose_argv(project, workspace, "create",
                                    SCENARIO_SERVICE))
    if not created["ok"]:
        return project, None, f"compose create failed: {created['why']}"
    note("compose_create")

    container_id, why = resolve_compose_container(project, workspace)
    if container_id is None:
        return project, None, why

    if registry is not None:
        registry.containers.append(container_id)
    note("register", container_id)

    ok, why = verify_compose_identity(container_id, project)
    if not ok:
        return project, container_id, f"compose identity: {why}"
    note("verify_identity", container_id)

    # The registry's REAL contents at the moment the start is issued.
    # Asserting the create/resolve/start call ordering is satisfied by
    # registering after start -- an isolated mutation that moved the
    # append below the start call passed every control. This snapshot
    # is not: a container that starts before it is registered is
    # unowned for that interval, however briefly.
    note("before_compose_start", container_id)
    started = _observe(compose_argv(project, workspace, "start",
                                    SCENARIO_SERVICE))
    if not started["ok"]:
        return project, container_id, f"compose start failed: {started['why']}"
    note("compose_start", container_id)
    return project, container_id, ""


def launch_inner_subject_non_detached(project, workspace, nonce, marker):
    """ONE non-detached `docker compose exec` which launches the child.

    This is the client the host later terminates, and it is the same
    boundary the supported wrapper uses. A plain `docker exec` here
    would demonstrate the wrong boundary.
    """
    expected_argv = ["python3", "-c", "import time; time.sleep(900)", marker]
    script = _subject_script(nonce, marker)
    argv = compose_argv(project, workspace, "exec", "-T",
                        "-e", f"HH716_NONCE={nonce}",
                        SCENARIO_SERVICE, "sh", "-c", script)
    client = subprocess.Popen(
        argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        start_new_session=True)
    return client, expected_argv, argv

def read_json_in(container_id, path):
    done = PROVER.in_scenario(container_id, ["cat", path])
    if done.returncode != 0:
        return None, f"unreadable: {done.stderr.strip()[:120]}"
    try:
        return json.loads(done.stdout), ""
    except ValueError as exc:
        return None, f"malformed: {exc}"


#: Linux process states from proc(5). Anything outside this set means the
#: observation was not understood, which is UNKNOWN rather than alive.
KNOWN_PROCESS_STATES = frozenset("RSDZTtWXxKPI")

#: Every preflight key that must be present AND literally True. `all(
#: checks.values())` passed when a key was simply absent -- an early return
#: that skipped adding one satisfied the gate.
REQUIRED_PREFLIGHT_CHECKS = (
    "lane_observed", "lane_is_a_real_compose_project",
    "lane_is_not_the_shared_project", "is_a_dedicated_worktree",
    "compose_project_is_scenario_specific",
    "compose_service_resolves_to_registered_id",
    "compose_identity_matches_project_and_service",
    "scenario_container_created_and_registered",
    "container_present_and_identified", "immutable_id_is_64_hex",
    "scenario_project_label_observed", "scenario_not_in_shared_project",
    "shared_containers_observed", "no_shared_container_is_a_target",
    "rescue_owner_installed", "rescue_owner_proven_by_execution",
    "decoy_create_observed", "decoy_started", "same_label_decoy_live",
    "decoy_is_not_in_scenario_registry", "decoy_is_in_fixture_registry",
    "label_discovery_observed", "label_discovery_would_select_decoy",
    "label_discovery_selects_an_unowned_same_label_resource",
    "discovery_ids_are_not_in_the_teardown_set",
)


def preflight_shortfall(checks):
    """Missing or non-True required checks. Empty means the gate is satisfied."""
    missing = [name for name in REQUIRED_PREFLIGHT_CHECKS if name not in checks]
    untrue = [name for name in REQUIRED_PREFLIGHT_CHECKS
              if checks.get(name) is not True]
    unexpected_false = [name for name, value in checks.items() if value is not True]
    return {"missing": missing, "not_literally_true": untrue,
            "any_false": sorted(set(unexpected_false) - set(missing))}


PROBE_SOURCE = """
import json, os, sys
pid = int(sys.argv[1])
try:
    with open("/proc/%d/stat" % pid, "rb") as handle:
        raw = handle.read().decode("utf-8", "replace")
except FileNotFoundError:
    print(json.dumps({"found": False}))
    raise SystemExit(0)
except OSError as exc:
    print(json.dumps({"error": "%s" % exc.__class__.__name__,
                      "errno": exc.errno}))
    raise SystemExit(0)
try:
    state = raw.rsplit(")", 1)[1].split()[0]
except IndexError:
    print(json.dumps({"error": "unparseable"}))
    raise SystemExit(0)
ticks = raw.rsplit(")", 1)[1].split()[19]
print(json.dumps({"found": True, "state": state, "start_ticks": ticks}))
"""


def alive_in(container_id, pid, expected_start_ticks=None):
    """TRUE / FALSE / UNKNOWN for a pid, with no failure collapsed into absence.

    The previous version ran `cat /proc/<pid>/stat 2>/dev/null || echo
    MISSING`, which discarded the failure reason and turned ANY read error
    -- permission, I/O, an unreadable /proc -- into the same token reported
    as absence. The inner read's status was thrown away while only the outer
    exec's was checked: the Phase A collapse, reintroduced here after being
    fixed twice elsewhere.

    The probe now distinguishes not-found from a read error explicitly, and
    a read error is UNKNOWN.
    """
    done = PROVER.in_scenario(
        container_id, ["python3", "-c", PROBE_SOURCE, str(int(pid))])
    if done.returncode != 0:
        return UNKNOWN, f"probe exited {done.returncode}: {done.stderr.strip()[:120]}"
    try:
        result = json.loads(done.stdout.strip())
    except ValueError:
        return UNKNOWN, f"probe output unparseable: {done.stdout.strip()[:80]}"
    if not isinstance(result, dict):
        return UNKNOWN, f"probe returned {type(result).__name__}, not an object"
    if "error" in result:
        return UNKNOWN, f"read failed: {result['error']} errno={result.get('errno')}"

    # Strict schema. Valid JSON is not a valid observation: `{}` made
    # `found` falsy and reported absence, and `{"found": true}` with no
    # state reported liveness. Anything that does not match exactly is
    # UNKNOWN.
    found = result.get("found")
    if not isinstance(found, bool):
        return UNKNOWN, f"probe omitted a boolean 'found': {result!r}"
    if not found:
        # A record claiming absence must not also describe a live state.
        # `{"found": false, "state": "S"}` previously reported absence while
        # carrying contradictory data.
        if result.get("state") or result.get("start_ticks"):
            return UNKNOWN, (f"contradictory record: found=false with "
                             f"{ {k: v for k, v in result.items() if k != 'found'} }")
        return "false", "no process entry (reaped)"
    state = result.get("state")
    if not isinstance(state, str) or not state:
        return UNKNOWN, f"probe reported found without a state: {result!r}"
    # An unrecognized state is UNKNOWN, not alive. Requiring only a
    # non-empty string let any token -- "Q", "hello" -- report liveness.
    if state not in KNOWN_PROCESS_STATES:
        return UNKNOWN, f"unrecognized process state {state!r}"
    # Instance identity. Without comparing start ticks this interface cannot
    # establish that the SAME process survived: a recycled pid presents as a
    # live process at the same number.
    observed_ticks = result.get("start_ticks")
    if expected_start_ticks is not None:
        if not isinstance(observed_ticks, str) or not observed_ticks:
            return UNKNOWN, "no start identity published; instance cannot be bound"
        if observed_ticks != str(expected_start_ticks):
            return UNKNOWN, (f"pid {pid} now holds a different instance "
                             f"(start_ticks {observed_ticks} != "
                             f"{expected_start_ticks})")
    if state == "Z":
        return "false", "terminated (zombie: entry remains, not executing)"
    return "true", f"state={state} start_ticks={observed_ticks}"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lane", required=True)
    parser.add_argument("--image", default="netbox:latest-plugins-dev")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True,
                        help="scratch directory for this run's compose file")
    args = parser.parse_args(argv)

    run_id = uuid.uuid4().hex
    started_at = time.time()
    workspace = args.workspace
    workspace.mkdir(parents=True, exist_ok=True)
    evidence = {"step": "B1b", "lane": args.lane, "run_id": run_id,
                "observed_at": int(started_at), "lane_dirty": False,
                "dirty_reasons": [], "timing": {}, "stages": []}

    def dirty(reason):
        evidence["lane_dirty"] = True
        evidence["dirty_reasons"].append(reason)

    def stage(name, **data):
        evidence["stages"].append({"stage": name, **data})

    # B1a registry and lifecycle, so ownership goes through the reviewed path
    # rather than being tracked in local variables.
    registry = PROVER.Registry(run_id=run_id, lane=args.lane, container_id="")
    # Fixture resources are registered separately by immutable id. They must
    # never be destroyed by the rescue path, and must still be disposed by
    # this script -- so they need their own registry rather than a name.
    fixture_registry = []
    lifecycle = []
    evidence["lifecycle_order"] = lifecycle

    container_id = decoy_id = None
    # Bound before the try so the finally can tear the project down even
    # if preflight raises before returning it.
    project = None
    client = None

    try:
        container_id, decoy_id, checks, project = preflight(
            args.image, args.lane, run_id, evidence, registry, lifecycle,
            fixture_registry, workspace)
        shortfall = preflight_shortfall(checks)
        evidence["preflight_shortfall"] = shortfall
        if not container_id or any(shortfall.values()):
            dirty(f"preflight incomplete: {shortfall}")
            stage("preflight", passed=False, shortfall=shortfall)
            print(f"PREFLIGHT FAILED {shortfall}; subject never launched",
                  file=sys.stderr)
            return 3
        stage("preflight", passed=True)
        evidence["preflight_passed"] = True

        marker = f"hh716b1b-{uuid.uuid4().hex[:8]}"
        expected_argv = ["python3", "-c", "import time; time.sleep(900)", marker]
        nonce = registry.next_nonce()
        registry.launches.append(PROVER.asdict(PROVER.LaunchRecord(
            nonce=nonce, sequence=len(registry.launches),
            container_id=container_id,
            expected_cmdline=" ".join(expected_argv),
            created_at=int(time.time()))))
        registry.launches[-1]["expected_argv"] = expected_argv
        lifecycle.append({"event": f"baseline_register:{nonce}",
                          "at": time.time(),
                          "registered_nonces": [l["nonce"]
                                                for l in registry.launches]})

        launch_at = time.time()
        # The SAME compose exec client that is terminated below.
        client, _, client_argv = launch_inner_subject_non_detached(
            project, workspace, nonce, marker)
        evidence["client_argv"] = client_argv
        lifecycle.append({"event": f"baseline_start:{nonce}", "at": time.time(),
                          "registered_nonces": [l["nonce"]
                                                for l in registry.launches]})
        evidence["host_client_pid"] = client.pid
        evidence["expected_argv"] = expected_argv

        deadline = launch_at + evidence["preflight"]["observation_deadline_seconds"]
        parent = child = None
        while time.time() < deadline:
            parent, _ = read_json_in(container_id,
                                     f"{PUBLICATION_DIR}/{nonce}.parent.json")
            child, _ = read_json_in(container_id,
                                    f"{PUBLICATION_DIR}/{nonce}.child.json")
            if parent and child:
                break
            time.sleep(2)
        evidence["timing"]["publication_seconds"] = round(
            time.time() - launch_at, 1)

        if not (parent and child):
            dirty("publication did not appear before the observation deadline")
            stage("publication", ok=False)
            return 4
        evidence["publication"] = {"parent": parent, "child": child}
        stage("publication", ok=True)

        if str(child.get("ppid")) != str(parent.get("pid")):
            dirty(f"child ppid {child.get('ppid')} is not the exec parent "
                  f"{parent.get('pid')}")
            return 5
        evidence["inner_parent_child_verified"] = True
        stage("inner_parent_child", verified=True)

        # Validate what the CHILD published. The previous version built the
        # publication with the nonce from a local variable, so bind() never
        # saw the child's own value and a wrong published nonce could not be
        # detected. The launch record is the authority.
        launch = [l for l in registry.launches if l["nonce"] == nonce]
        published_nonce = child.get("nonce")
        if published_nonce != nonce or len(launch) != 1:
            dirty(f"published nonce {published_nonce!r} does not match the "
                  f"launch record {nonce!r}")
            return 16
        if parent.get("nonce") != nonce:
            dirty(f"exec parent published nonce {parent.get('nonce')!r}, "
                  f"expected {nonce!r}")
            return 17
        evidence["published_nonce_validated"] = True

        bound, bind_why = PROVER.bind(registry, {
            "nonce": published_nonce, "pid": child["pid"],
            "start_ticks": child["start_ticks"], "pgid": child["pgid"],
            "sid": child["sid"]})
        if not bound:
            dirty(f"baseline child did not bind to the registry: {bind_why}")
            return 6
        evidence["binding"] = {"nonce": bound["nonce"],
                               "expected_argv": bound.get("expected_argv")}
        stage("two_sided_binding", ok=True)

        verified, why = PROVER.run_rescue(container_id, [bound], False)
        evidence["pre_termination_verification"] = verified or {"error": why}
        if not verified or not verified["reports"][0]["verified"]:
            dirty("ownership not verified before termination")
            return 7
        stage("pre_termination_verification", verified=True)

        kill_at = time.time()
        client.kill()
        try:
            # Bounded. An unbounded communicate() on the main path can hang
            # after the kill, leaving the baseline stalled with a live
            # orphan and no evidence written.
            client.communicate(timeout=60)
        except subprocess.TimeoutExpired:
            dirty("host client did not finish within 60s of termination")
            return 15
        evidence["timing"]["host_client_terminated_after_seconds"] = round(
            kill_at - launch_at, 1)
        evidence["host_client_returncode"] = client.returncode
        time.sleep(3)
        stage("host_client_terminated", pid=client.pid,
              returncode=client.returncode)

        state, detail = alive_in(container_id, child["pid"],
                                 child["start_ticks"])
        evidence["inner_subject_after_host_kill"] = {
            "alive": state, "detail": detail,
            "claim": "host-client termination did not propagate to its inner "
                     "child; survival is not caused by the termination",
        }
        if state == UNKNOWN:
            dirty(f"inner subject state unknown after host kill: {detail}")
            return 8
        if state != "true":
            dirty("the inner subject did not survive host termination; this "
                  "baseline does not demonstrate the defect it claims")
            return 9

        rescued, why = PROVER.run_rescue(container_id, [bound], True)
        evidence["rescue"] = rescued or {"error": why}
        if not rescued:
            dirty(f"rescue owner failed: {why}")
            return 10
        if rescued["reports"][0]["outcome"] not in ("reaped",
                                                     "terminated_zombie"):
            dirty(f"rescue outcome {rescued['reports'][0]['outcome']!r} is "
                  "not a cleanup")
            return 11

        after, after_detail = alive_in(container_id, child["pid"],
                                       child["start_ticks"])
        evidence["owned_membership_after_rescue"] = {"alive": after,
                                                     "detail": after_detail}
        if after == UNKNOWN:
            dirty(f"survivor state unknown after rescue: {after_detail}")
            return 12
        if after != "false":
            dirty("an owned member survived the rescue")
            return 13

        decoy_state, decoy_detail = PROVER._inspect_state(decoy_id)
        evidence["same_label_decoy_after_rescue"] = {
            "state": decoy_state, "detail": decoy_detail,
            "label": f"hh716.run={run_id}",
            "note": "identical label to the registered scenario container, "
                    "and absent from the registry; survives because disposal "
                    "goes by exact registered ID, not label discovery",
        }
        if decoy_state != "present":
            dirty("an unregistered same-label resource was destroyed by the "
                  "rescue path")
            return 14

        evidence["baseline_complete"] = True
        return 0
    except BaseException as exc:
        # Nothing may escape without disposal and evidence. The previous
        # main() had no try/finally, so an exception anywhere left a live
        # orphan, no artifact and no teardown -- in the one script that
        # creates an orphan on purpose.
        dirty(f"unhandled {type(exc).__name__}: {exc}")
        evidence["unhandled_exception"] = {"type": type(exc).__name__,
                                           "message": str(exc)[:300]}
        raise
    finally:
        if client is not None and client.poll() is None:
            try:
                client.kill()
                client.communicate(timeout=30)
            except Exception as exc:          # noqa: BLE001
                dirty(f"host client could not be terminated: {exc}")

        try:
            evidence["registry"] = PROVER.asdict(registry)
            evidence["teardown_registered"] = (
                PROVER.teardown_registered_containers(registry))
            if not evidence["teardown_registered"]["proved"]:
                dirty("registered teardown could not be proved")
        except Exception as exc:              # noqa: BLE001
            dirty(f"registered teardown raised: {exc}")

        # Fixture disposal, by registered immutable id only. Every id here
        # was recorded before its container was started, so a post-creation
        # exception cannot lose one.
        # The Compose project is torn down by NAME after the registry has
        # disposed of the exact IDs it owns: name-based teardown may only
        # follow id-based disposal, never replace it.
        if project:
            down = _observe(compose_argv(project, workspace, "down",
                                         "--remove-orphans", "-t", "5"))
            evidence["compose_down"] = {"project": project,
                                        "ok": down["ok"],
                                        "why": down["why"]}
        evidence["fixture_cleanup"] = []
        for fixture_id in fixture_registry:
            entry = {"id": fixture_id}
            try:
                subprocess.run(["docker", "rm", "-f", fixture_id],
                               capture_output=True, text=True, timeout=120)
                state, detail = PROVER._inspect_state(fixture_id)
                entry.update(state_after=state, detail=detail)
                if state != "absent":
                    dirty(f"fixture {fixture_id[:12]} not verifiably disposed")
            except Exception as exc:          # noqa: BLE001
                entry.update(state_after="unknown", detail=f"raised: {exc}")
                dirty(f"fixture cleanup raised for {fixture_id[:12]}: {exc}")
            evidence["fixture_cleanup"].append(entry)

        evidence["timing"]["total_seconds"] = round(time.time() - started_at, 1)
        try:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(evidence, indent=2, sort_keys=True),
                encoding="utf-8")
            print(f"wrote {args.output} (dirty={evidence['lane_dirty']})")
        except Exception as exc:              # noqa: BLE001
            print(f"EVIDENCE WRITE FAILED: {exc}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
