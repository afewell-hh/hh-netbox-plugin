"""Mocked harness that drives the REAL #716 B1b main()/preflight(). Test-only.

Exists because every previous B1b control was a source-position check, a
copied predicate, or an independent snippet. Dev B showed all eighteen
still passed when nonce validation was removed, start-identity comparison
disabled, and fixture registration commented out -- so none of them was
bound to behaviour.

This harness substitutes every Docker and in-container interaction with
scripted values and then calls the real entry points, so a mutation to the
implementation changes the control's result. No Docker, no containers, no
signals.
"""

from __future__ import annotations

import ast
import json
import pathlib
import subprocess
import sys
import time as _real_time
from pathlib import Path

_HERE = Path(__file__).resolve().parent


def load_b1b():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "hh716_b1b_under_test", _HERE / "containment_b1b.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["hh716_b1b_under_test"] = module
    spec.loader.exec_module(module)
    return module


class Completed:
    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


SCENARIO_ID = "a" * 64
DECOY_ID = "b" * 64
CHILD_PID = 4242
#: The readiness subject must be a DIFFERENT process from the baseline
#: child. Sharing a pid made preflight's readiness signal look like the
#: baseline's, so the post-kill probe reported the baseline child already
#: gone and the sound positive failed.
READINESS_PID = 1111
PARENT_PID = 4200
START_TICKS = "777777"


class FakeClient:
    """Stands in for the non-detached host exec client."""

    def __init__(self):
        self.pid = 99999
        self.returncode = None
        self.killed = False

    def kill(self):
        self.killed = True
        self.returncode = -9

    def communicate(self, timeout=None):
        return ("", "")

    def poll(self):
        return self.returncode


def install(b1b, *, published_child_nonce=None, published_parent_nonce=None,
            observed_start_ticks=None, scenario_id=SCENARIO_ID,
            after_kill_state="S", after_rescue_found=False,
            rescue_outcome="reaped", decoy_state_after_rescue="present",
            child_found_after_kill=True, probe_unknown_after_kill=False,
            readiness_outcome="reaped", verification_verified=True):
    """Patch every outward call of the module under test.

    Returns a dict of recorders so a control can assert what the real code
    did, not what a reimplementation would have done.
    """
    # Container-aware. A previous version recorded only the entries, so
    # redirecting the rescue to the decoy container was invisible to every
    # control.
    # `events` is an ORDERED log. Ownership ordering -- readiness proven by
    # execution before any orphan is induced -- cannot be read off
    # unordered per-kind lists.
    recorded = {"removed": [], "signalled": [], "bind_calls": [],
                "rescue_calls": [], "events": [], "launches": []}

    def _baseline_signalled():
        return any(entry.get("pid") == CHILD_PID
                   for entries in recorded["signalled"] for entry in entries)

    def fake_run(argv, **kwargs):
        if not isinstance(argv, list):
            return Completed(returncode=1)
        text = " ".join(str(part) for part in argv)
        # The decoy carries a second label; the scenario container does not.
        if argv[:2] == ["docker", "create"]:
            return Completed(stdout=DECOY_ID if "hh716.fixture" in text
                             else scenario_id)
        if argv[:2] == ["docker", "start"]:
            return Completed()
        if argv[:2] == ["docker", "rm"]:
            recorded["removed"].append(argv[-1])
            return Completed()
        if argv[:2] == ["docker", "cp"]:
            return Completed()
        if argv[:2] == ["docker", "inspect"]:
            target = argv[2]
            # The verifying query must be answered BEFORE any id-specific
            # branch: a previous version let the decoy branch intercept it,
            # so create_scenario_container saw an identity mismatch and the
            # whole harness aborted in preflight.
            if "{{.Id}} {{index" in text:
                return Completed(stdout=f"{target} {b1b_run_id[0]}")
            if "com.docker.compose.project" in text:
                return Completed(stdout=lane_holder[0])
            if target in recorded["removed"]:
                return Completed(stderr=f"No such container: {target}",
                                 returncode=1)
            # Decoy destruction, injected through the real `_inspect_state`
            # rather than by patching it: `decoy_state_after_rescue` was
            # previously accepted and never used, so a control passing it
            # injected nothing at all.
            if (decoy_state_after_rescue == "absent" and target == DECOY_ID
                    and _baseline_signalled()):
                return Completed(stderr=f"No such container: {target}",
                                 returncode=1)
            return Completed(stdout=target)
        if argv[:2] == ["docker", "ps"]:
            if "label=hh716.run=" in text:
                return Completed(
                    stdout=DECOY_ID[:12] + chr(10) + scenario_id[:12])
            if "name=netbox-docker-" in text:
                return Completed(stdout="")
            return Completed(stdout="someid")
        if argv[:1] == ["git"]:
            return Completed(stdout="/tmp/wt716b" if "toplevel" in text
                             else "/repo/.git/worktrees/x")
        return Completed()

    b1b_run_id = [""]
    lane_holder = ["diet716-mock"]

    def fake_in_scenario(container_id, argv, timeout=120, stdin=None,
                         detach=False, env=None):
        joined = " ".join(str(part) for part in argv)
        if "containment_rescue" in joined or "hh716_rescue" in joined:
            payload = json.loads(stdin or "{}")
            entries = payload.get("entries", [])
            recorded["bind_calls"].append(entries)
            send = payload.get("send_signal")
            recorded["rescue_calls"].append({"container_id": container_id,
                                             "send_signal": bool(send),
                                             "entries": entries})
            is_baseline = bool(entries) and entries[0].get("pid") == CHILD_PID
            if send:
                recorded["signalled"].append(entries)
                pids = [e.get("pid") for e in entries]
                kind = "baseline" if CHILD_PID in pids else "readiness"
                recorded["events"].append(("rescue_signal", kind))
            if not send:
                outcome = "verified_not_signalled"
            elif is_baseline:
                outcome = rescue_outcome
            else:
                outcome = readiness_outcome        # preflight readiness
            # The verification pass can report NOT verified; without that
            # injection the ownership gate was never exercised and removing
            # it changed nothing observable.
            # Scoped to the BASELINE child, like rescue_outcome: applied to
            # preflight readiness too, the run aborts in preflight and the
            # control passes for the wrong reason.
            verified_flag = (verification_verified
                             if (not send and is_baseline) else True)
            return Completed(stdout=json.dumps({"reports": [{
                "verified": verified_flag, "signalled": bool(send),
                "outcome": outcome,
                "nonce": entries[0].get("nonce") if entries else None,
                "pid": CHILD_PID, "reasons": []}]}))
        if argv and argv[0] == "cat":
            path = argv[1]
            nonce = Path(path).name.split(".")[0]
            if path.endswith(".parent.json"):
                return Completed(stdout=json.dumps({
                    "role": "exec_parent",
                    "nonce": published_parent_nonce or nonce,
                    "pid": PARENT_PID, "start_ticks": START_TICKS,
                    "pgid": str(PARENT_PID), "sid": str(PARENT_PID)}))
            if path.endswith(".child.json"):
                return Completed(stdout=json.dumps({
                    "role": "inner_child",
                    "nonce": published_child_nonce or nonce,
                    "pid": CHILD_PID, "ppid": str(PARENT_PID),
                    "start_ticks": START_TICKS,
                    "pgid": str(PARENT_PID), "sid": str(PARENT_PID)}))
            if path.endswith(".json"):   # read_publication's plain record
                return Completed(stdout=json.dumps(
                    {"nonce": nonce, "pid": READINESS_PID,
                     "start_ticks": START_TICKS, "pgid": "1", "sid": "1"}))
            return Completed(returncode=1, stderr="no such file")
        if argv and argv[0] == "python3" and "PROBE" not in joined:
            # The liveness probe. Keyed on whether the BASELINE child has
            # been signalled, not on whether anything has: preflight's
            # readiness subject signals first.
            ticks = (observed_start_ticks if observed_start_ticks is not None
                     else START_TICKS)
            if not _baseline_signalled():
                # A probe that could not run at all -> UNKNOWN, which must
                # never read as a clean result.
                if probe_unknown_after_kill:
                    return Completed(returncode=1, stderr="probe failed")
                # The child not surviving host termination means the
                # baseline did not reproduce the defect it reports.
                if not child_found_after_kill:
                    return Completed(stdout=json.dumps({"found": False}))
                return Completed(stdout=json.dumps(
                    {"found": True, "state": after_kill_state,
                     "start_ticks": ticks}))
            if after_rescue_found:
                return Completed(stdout=json.dumps(
                    {"found": True, "state": "S", "start_ticks": ticks}))
            return Completed(stdout=json.dumps({"found": False}))
        return Completed()

    # Replace the MODULE REFERENCES, never attributes on the shared stdlib
    # modules. A previous version did `b1b.subprocess.run = fake_run` and
    # `b1b.time.sleep = ...`, which mutates the real `subprocess` and `time`
    # for the whole test process: each suite passed alone and two failed
    # when run together, because the fakes leaked into every other test.
    class _SubprocessShim:
        run = staticmethod(fake_run)
        PIPE = subprocess.PIPE
        STDOUT = subprocess.STDOUT
        SubprocessError = subprocess.SubprocessError
        TimeoutExpired = subprocess.TimeoutExpired
        CalledProcessError = subprocess.CalledProcessError
        Popen = staticmethod(lambda *a, **k: FakeClient())

    class _TimeShim:
        sleep = staticmethod(lambda *a, **k: None)
        time = staticmethod(_real_time.time)
        monotonic = staticmethod(_real_time.monotonic)
        gmtime = staticmethod(_real_time.gmtime)
        strftime = staticmethod(_real_time.strftime)

    original_create = b1b.PROVER.create_scenario_container

    def fake_create(image, run_id, registry=None, order=None):
        b1b_run_id[0] = run_id
        return original_create(image, run_id, registry, order)

    b1b.subprocess = _SubprocessShim
    b1b.time = _TimeShim
    b1b.PROVER.subprocess = _SubprocessShim
    b1b.PROVER.in_scenario = fake_in_scenario
    b1b.PROVER.install_rescue_owner = lambda *a, **k: True
    b1b.PROVER.create_scenario_container = fake_create
    def fake_baseline_launch(*a, **k):
        recorded["events"].append(("launch", "baseline"))
        recorded["launches"].append("baseline")
        return FakeClient(), ["python3", "-c", "x", "m"]

    original_launch_owned = b1b.PROVER.launch_owned_subject

    def fake_launch_owned(container_id, registry, role, lifecycle=None,
                          *a, **k):
        recorded["events"].append(("launch", role))
        recorded["launches"].append(role)
        return original_launch_owned(container_id, registry, role,
                                     lifecycle, *a, **k)

    b1b.launch_inner_subject_non_detached = fake_baseline_launch
    b1b.PROVER.launch_owned_subject = fake_launch_owned
    return recorded


def run_main(b1b, output, lane="diet716-mock"):
    return b1b.main(["--lane", lane, "--output", str(output)])


# ----------------------------------------------------------------------
# Evidence-coverage collectors.
#
# A recorded fact no control reads is an unfalsified claim. These collect
# what the subject WRITES and what the controls READ so a control can
# require every written path to be read or explicitly declared diagnostic.
#
# GUARANTEE AND ITS BOUNDARY. Tracked: direct subscript assignment, the
# `evidence = {...}` initialiser, `setdefault`, `update`, nested writes
# `evidence[a][b] = v`, and nested keys inside assigned dict literals --
# to a depth of 2. Reads resolve one level of local aliasing
# (`p = evidence["preflight"]` then `p["container_id"]`).
#
# NOT tracked: writes deeper than depth 2, aliases of aliases, and keys
# built from non-literal expressions. The first is not merely documented
# -- `deeper_write_chains` reports any such write so the control can fail
# rather than silently skip it. The last two cannot arise while the
# subject uses literal keys, which the same control checks.
# ----------------------------------------------------------------------

def _chain(node):
    """['a','b'] for evidence['a']['b'], or None if not rooted at evidence."""
    parts = []
    while isinstance(node, ast.Subscript):
        if not (isinstance(node.slice, ast.Constant)
                and isinstance(node.slice.value, str)):
            return None
        parts.append(node.slice.value)
        node = node.value
    if isinstance(node, ast.Name) and node.id == "evidence":
        return list(reversed(parts))
    return None

def _dict_paths(prefix, node, out, depth):
    if not isinstance(node, ast.Dict) or depth <= 0:
        return
    for k, v in zip(node.keys, node.values):
        if isinstance(k, ast.Constant) and isinstance(k.value, str):
            path = prefix + [k.value]
            out.add(".".join(path))
            _dict_paths(path, v, out, depth - 1)

def _chain_via_alias(node, alias):
    parts = []
    while isinstance(node, ast.Subscript):
        if not (isinstance(node.slice, ast.Constant)
                and isinstance(node.slice.value, str)):
            return None
        parts.append(node.slice.value)
        node = node.value
    if isinstance(node, ast.Name) and node.id in alias:
        return alias[node.id] + list(reversed(parts))
    return None


def evidence_read_paths(paths):
    out = set()
    for p in paths:
        tree = ast.parse(pathlib.Path(p).read_text())
        # One level of alias resolution: `x = evidence["a"]` then `x["b"]`
        # is a read of a.b. Without this, genuinely asserted keys look
        # unread, and declaring them diagnostic would be wrong.
        alias = {}
        for n in ast.walk(tree):
            if (isinstance(n, ast.Assign) and len(n.targets) == 1
                    and isinstance(n.targets[0], ast.Name)):
                ch = _chain(n.value)
                if ch:
                    alias[n.targets[0].id] = ch
        excl = set()
        for n in ast.walk(tree):
            if (isinstance(n, ast.Assign) and len(n.targets) == 1
                    and isinstance(n.targets[0], ast.Name)
                    and n.targets[0].id == "DIAGNOSTIC_ONLY"):
                excl.update(id(i) for i in ast.walk(n))
        for n in ast.walk(tree):
            if id(n) in excl:
                continue
            if isinstance(n, ast.Subscript):
                ch = _chain(n) or _chain_via_alias(n, alias)
                if ch:
                    for i in range(1, len(ch) + 1):
                        out.add(".".join(ch[:i]))
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
                if n.func.attr in ("get", "setdefault") and n.args and \
                        isinstance(n.args[0], ast.Constant):
                    base = _chain(n.func.value)
                    if isinstance(n.func.value, ast.Name) and \
                            n.func.value.id == "evidence":
                        out.add(n.args[0].value)
                    elif base:
                        out.add(".".join(base + [n.args[0].value]))
                if n.func.attr in ("assertIn", "assertNotIn") and \
                        len(n.args) >= 2 and isinstance(n.args[0], ast.Constant) \
                        and isinstance(n.args[0].value, str):
                    base = _chain(n.args[1])
                    if isinstance(n.args[1], ast.Name) and \
                            n.args[1].id == "evidence":
                        out.add(n.args[0].value)
                    elif base:
                        out.add(".".join(base + [n.args[0].value]))
    return out


# ======================================================================
# Evidence-coverage: a MANIFEST-BASED, FAIL-CLOSED collector boundary.
#
# CLAIM, precisely. For the versioned collector module under analysis:
# every evidence-derived reference is classified into an approved
# grammar production with declared path semantics, AND the module
# performs no reflective or indirect-reachability operation outside the
# three declared reflection productions -- or the scan fails.
#
# The claim is STATIC and MODULE-SCOPED. It does not extend to foreign
# code, to behaviour at runtime, or to a module that reaches a binding
# namespace: such a module fails the scan rather than being analysed.
# No runtime recorder exists and none is claimed.
#
# The manifest below is derived from the collector module's ACTUAL
# permitted evidence operations -- an inventory of the module found 39
# references in 8 shapes -- not from a hand-curated list of Python
# constructs that might be harmless. There is deliberately NO generic
# "inspection is safe" production: a reference that matches nothing in
# the manifest is a violation, including constructs neither author
# anticipated.
#
# Because of that, the propagation machinery of earlier versions is
# gone. `evidence or {}` is not "a BoolOp that must be followed to its
# terminal use"; it is simply unmatched, and therefore a violation.
# ======================================================================

GRAMMAR_VERSION = "2026-10-18.1"

#: Dotted callables that may receive the whole dict. The spelling alone
#: is never sufficient -- the root name must also be import-bound and
#: never rebound anywhere in the module.
_SERIALIZERS = ("json.dumps",)

MAX_PATH_DEPTH = 2


class Production:
    """One approved evidence operation, with its declared semantics.

    effect:
      records  -- introduces evidence paths, which must then be read by
                  a control or declared diagnostic
      reads    -- consumes an already-recorded path, introduces none
      observes -- hands the object to a declared-identity recipient
                  without retaining a reference
    """

    def __init__(self, pid, shape, consumer, depth, key_form, effect,
                 identity=None):
        self.id = pid
        self.shape = shape
        self.consumer = consumer
        self.depth = depth
        self.key_form = key_form
        self.effect = effect
        self.identity = identity

    def __repr__(self):                                   # pragma: no cover
        return f"<Production {self.id}>"


MANIFEST = (
    Production("INIT", "evidence = {...}", "Assign value", 2,
               "str-literal", "records"),
    Production("ASSIGN_D1", 'evidence["k"] = expr', "Assign target", 1,
               "str-literal", "records"),
    Production("ASSIGN_D2", 'evidence["k"]["j"] = expr', "Assign target", 2,
               "str-literal", "records"),
    Production("APPEND_D1", 'evidence["k"].append(arg)', "Call on Attribute",
               1, "str-literal", "reads"),
    Production("SETDEFAULT_APPEND", 'evidence.setdefault("k", []).append(a)',
               "Call on Attribute of accessor result", 1, "str-literal",
               "records", identity="result consumed only by .append()"),
    Production("ARG_LOCAL_FN", "localfn(..., evidence, ...)", "Call argument",
               0, "n/a", "observes",
               identity="module-local function, parameter named `evidence`"),
    Production("ARG_SERIALIZER", "json.dumps(evidence, ...)", "Call argument",
               0, "n/a", "observes",
               identity="import-bound, never rebound, in _SERIALIZERS"),
    Production("READ_BINOP", 'evidence[...] inside a BinOp', "BinOp", 2,
               "str-literal", "reads"),
    Production("READ_UNARYOP", 'evidence[...] inside a UnaryOp', "UnaryOp", 2,
               "str-literal", "reads"),
    Production("READ_FSTRING", 'evidence[...] in an f-string', "FormattedValue",
               2, "str-literal", "reads"),
)

_BY_ID = {p.id: p for p in MANIFEST}


def _literal_chain(node):
    """['a','b'] for evidence['a']['b']; None if not evidence-rooted;
    ('COMPUTED', n) if rooted but a key is not a string literal."""
    parts, computed = [], False
    while isinstance(node, ast.Subscript):
        if (isinstance(node.slice, ast.Constant)
                and isinstance(node.slice.value, str)):
            parts.append(node.slice.value)
        else:
            computed = True
            parts.append(None)
        node = node.value
    if isinstance(node, ast.Name) and node.id == "evidence":
        return ("COMPUTED", len(parts)) if computed else list(reversed(parts))
    return None


def _literal_dict_paths(prefix, node, out, bad, where):
    if not isinstance(node, ast.Dict):
        return
    for key, value in zip(node.keys, node.values):
        if key is None:
            bad.append(f"{where}: dict unpacking inside an evidence literal")
            continue
        if not (isinstance(key, ast.Constant) and isinstance(key.value, str)):
            bad.append(f"{where}: computed key inside an evidence dict "
                       f"literal")
            continue
        path = prefix + [key.value]
        if len(path) > MAX_PATH_DEPTH:
            bad.append(f"{where}: path {'.'.join(path)} is deeper than "
                       f"{MAX_PATH_DEPTH}")
            continue
        out.add(".".join(path))
        _literal_dict_paths(path, value, out, bad, where)


def _untouched_imports(tree):
    """Names bound by an import and never reassigned in the module."""
    imported, rebound = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                imported.add((alias.asname or alias.name).split(".")[0])
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                               ast.ClassDef)):
            rebound.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign,
                               ast.For, ast.AsyncFor)):
            targets = (node.targets if isinstance(node, ast.Assign)
                       else [node.target])
            for target in targets:
                for sub in ast.walk(target):
                    if isinstance(sub, ast.Name):
                        rebound.add(sub.id)
        elif isinstance(node, ast.withitem) and node.optional_vars is not None:
            for sub in ast.walk(node.optional_vars):
                if isinstance(sub, ast.Name):
                    rebound.add(sub.id)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            rebound.add(node.name)
    return imported - rebound


# ======================================================================
# Bounded reflection prohibition.
#
# Five successive versions of a namespace-risk predicate were each
# escaped by a spelling it did not match: a subscript store, then
# mapping-method mutation, then `builtins.globals`, then import
# aliases, then `getattr(sys.modules["builtins"], "globals")`. The last
# escape used a key built at runtime -- `"glo" + "bals"` -- where the
# attribute name appears nowhere in the source, which no rule that
# matches names, attributes or resolved spellings can ever catch.
#
# So the collector module is no longer ANALYSED for what its reflection
# might reach. Reflection is PROHIBITED, with an allowlist of the three
# exact productions the module already performs. Each is matched on
# construct AND context; anything else reflective fails the scan. The
# question "what can this reach?" -- the step that failed five times --
# is never asked.
# ======================================================================

#: Callables and attributes that read or rewrite bindings, resolve names
#: at runtime, or walk the object graph to a namespace. Rejected
#: wherever they appear, in any spelling, unless an allowlisted
#: production matches the exact node.
_REFLECTIVE_CALLS = (
    "getattr", "setattr", "delattr", "hasattr",
    "globals", "locals", "vars", "dir",
    "exec", "eval", "compile", "__import__",
    "import_module", "reload", "__build_class__",
)
_REFLECTIVE_ATTRS = (
    "__dict__", "__globals__", "__builtins__", "__class__", "__bases__",
    "__base__", "__subclasses__", "__mro__", "__code__", "__closure__",
    "__func__", "__self__", "__getattribute__", "__getattr__",
    "__setattr__", "__delattr__", "__reduce__", "__init_subclass__",
    "modules", "import_module", "reload",
    # Executing module code. Prohibited unless the exact declared
    # production matches: unmatched, `x.loader.exec_module(y)` runs
    # arbitrary code, and leaving these out meant a refusal to MATCH
    # produced no violation at all.
    "loader", "exec_module",
)
#: `type` is reflective in general; only `type(x).__name__` is allowed.
_GUARDED_BUILTINS = ("type",)


# ----------------------------------------------------------------------
# Approved import manifest.
#
# The import rule was a DENYLIST: reject `builtins`, reject anything
# aliased to a reflective name. `from pkgutil import resolve_name`
# defeated it -- resolve_name turns the string "builtins:globals" into
# the callable, naming nothing the denylist knew. Any finite denylist
# loses this game: pkgutil, ctypes, gc, inspect and pickle all reach a
# namespace, and that list has no end.
#
# So imports are an ALLOWLIST of the exact forms this collector uses.
# A module importing anything else fails, whether or not the import is
# reflective, and whether or not anyone has thought about it.
# ----------------------------------------------------------------------

class ImportForm:
    """One approved import, matched exactly: kind, module, name, alias."""

    def __init__(self, kind, module, name, asname, rationale):
        self.kind = kind                  # "import" | "from"
        self.module = module
        self.name = name
        self.asname = asname
        self.rationale = rationale

    @property
    def key(self):
        return (self.kind, self.module, self.name, self.asname)

    def spelling(self):
        text = (f"import {self.name}" if self.kind == "import"
                else f"from {self.module} import {self.name}")
        return text + (f" as {self.asname}" if self.asname else "")


IMPORT_MANIFEST = (
    ImportForm("from", "__future__", "annotations", None,
               "postponed annotation evaluation"),
    ImportForm("import", None, "argparse", None, "the CLI"),
    ImportForm("import", None, "json", None, "evidence serialisation"),
    ImportForm("import", None, "os", None, "environment and paths"),
    ImportForm("import", None, "subprocess", None, "docker invocations"),
    ImportForm("import", None, "sys", None, "module registration, exit"),
    ImportForm("import", None, "time", None, "timings and waits"),
    ImportForm("import", None, "uuid", None, "run identity"),
    ImportForm("from", "pathlib", "Path", None, "filesystem paths"),
    ImportForm("import", None, "importlib.util", None,
               "RFL_IMPORTLIB_LOAD: loads the sibling modules by path"),
)

_IMPORT_KEYS = {form.key for form in IMPORT_MANIFEST}


def _import_entries(tree):
    """Every import in the module as (kind, module, name, asname, line)."""
    entries = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                entries.append(("import", None, alias.name, alias.asname,
                                node.lineno))
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                entries.append(("relative", "." * node.level,
                                ", ".join(a.name for a in node.names), None,
                                node.lineno))
                continue
            for alias in node.names:
                entries.append(("from", node.module, alias.name,
                                alias.asname, node.lineno))
    return entries


def import_scan(tree, *, check_manifest_usage=True):
    """Violations for every import outside the approved manifest."""
    violations, used = [], set()
    for kind, module, name, asname, line in _import_entries(tree):
        if kind == "relative":
            violations.append(
                f"line {line}: relative import `{module}` is not an "
                f"approved import form")
            continue
        key = (kind, module, name, asname)
        if key in _IMPORT_KEYS:
            used.add(key)
            continue
        spelling = (f"import {name}" if kind == "import"
                    else f"from {module} import {name}")
        if asname:
            spelling += f" as {asname}"
        violations.append(
            f"line {line}: `{spelling}` is not an approved import form; "
            f"imports are an allowlist, so a new one must be declared with "
            f"its rationale")

    for form in IMPORT_MANIFEST if check_manifest_usage else ():
        if form.key not in used:
            violations.append(
                f"import manifest declares `{form.spelling()}` but the "
                f"module does not import it; permission must track the "
                f"actual collector imports")
    return sorted(set(violations))


class ReflectionProduction:
    """One permitted reflective operation, matched on shape and context."""

    def __init__(self, pid, shape, rationale):
        self.id = pid
        self.shape = shape
        self.rationale = rationale


REFLECTION_MANIFEST = (
    ReflectionProduction(
        "RFL_IMPORTLIB_LOAD",
        "importlib.util.spec_from_file_location(...) | "
        "importlib.util.module_from_spec(...) | spec.loader.exec_module(m)",
        "loads the sibling prover/rescue modules by path"),
    ReflectionProduction(
        "RFL_SYS_MODULES_REGISTER",
        'sys.modules[<expr>] = <name>   (Store only)',
        "registers the module just built by RFL_IMPORTLIB_LOAD"),
    ReflectionProduction(
        "RFL_TYPE_NAME",
        "type(<expr>).__name__   (read position only)",
        "names an exception class in diagnostic text"),
)

_REFLECTION_IDS = {p.id for p in REFLECTION_MANIFEST}


def _dotted(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return None


def _loader_bindings(tree):
    """Per function: the names bound by the two declared constructors.

    `spec` must come from `spec_from_file_location`, and `module` from
    `module_from_spec(<that spec>)`. A name bound more than once is
    excluded: a second assignment could substitute anything, and the
    binding would no longer identify what the call receives.
    """
    bindings = {}
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        counts, specs, modules = {}, {}, {}
        for node in ast.walk(fn):
            if not (isinstance(node, ast.Assign) and len(node.targets) == 1
                    and isinstance(node.targets[0], ast.Name)):
                continue
            name = node.targets[0].id
            counts[name] = counts.get(name, 0) + 1
            value = node.value
            if not (isinstance(value, ast.Call)
                    and isinstance(value.func, ast.Attribute)):
                continue
            dotted = _dotted(value.func)
            if dotted == "importlib.util.spec_from_file_location":
                specs[name] = True
            elif dotted == "importlib.util.module_from_spec":
                if (len(value.args) == 1
                        and isinstance(value.args[0], ast.Name)):
                    modules[name] = value.args[0].id
        single = {n for n, c in counts.items() if c == 1}
        bindings[id(fn)] = (
            {n for n in specs if n in single},
            {n: s for n, s in modules.items() if n in single})
    return bindings


def _enclosing_function(node, parent):
    probe = parent.get(node)
    while probe is not None:
        if isinstance(probe, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return probe
        probe = parent.get(probe)
    return None


def _is_importlib_load(node, parent, bindings=None):
    """RFL_IMPORTLIB_LOAD, bound structurally.

    The two constructors are matched by their exact dotted name. The
    loader call is matched only as `<spec>.loader.exec_module(<module>)`
    where `<spec>` is a name bound in the SAME function by
    `spec_from_file_location`, and `<module>` is a name bound there by
    `module_from_spec(<that same spec>)`.

    A suffix test on `.loader.exec_module` was accepted here before,
    which let any receiver execute any argument -- the declared
    production named `spec` and `module`, and the matcher checked
    neither.
    """
    if not isinstance(node, ast.Attribute):
        return False
    call = parent.get(node)
    if not (isinstance(call, ast.Call) and call.func is node):
        return False
    dotted = _dotted(node)
    if dotted in ("importlib.util.spec_from_file_location",
                  "importlib.util.module_from_spec"):
        return True
    if node.attr != "exec_module":
        return False
    # Shape: exactly `<name>.loader.exec_module(<name>)`.
    loader = node.value
    if not (isinstance(loader, ast.Attribute) and loader.attr == "loader"
            and isinstance(loader.value, ast.Name)):
        return False
    if call.keywords or len(call.args) != 1:
        return False
    argument = call.args[0]
    if not isinstance(argument, ast.Name):
        return False
    if bindings is None:
        return False
    fn = _enclosing_function(node, parent)
    if fn is None:
        return False
    spec_names, module_names = bindings.get(id(fn), (set(), {}))
    receiver = loader.value.id
    if receiver not in spec_names:
        return False
    # The module must have been built from THIS spec.
    return module_names.get(argument.id) == receiver


def _is_sys_modules_register(node, parent):
    """RFL_SYS_MODULES_REGISTER: a STORE into sys.modules, nothing else.

    A read of `sys.modules` is the first half of the escape Dev B found
    and is not permitted.
    """
    if not (isinstance(node, ast.Attribute) and node.attr == "modules"):
        return False
    if _dotted(node) != "sys.modules":
        return False
    subscript = parent.get(node)
    if not (isinstance(subscript, ast.Subscript) and subscript.value is node):
        return False
    return isinstance(getattr(subscript, "ctx", None), ast.Store)


def _is_type_name(node, parent):
    """RFL_TYPE_NAME: `type(x).__name__`, read position only."""
    if isinstance(node, ast.Name) and node.id == "type":
        call = parent.get(node)
        if not (isinstance(call, ast.Call) and call.func is node):
            return False
        attribute = parent.get(call)
        return (isinstance(attribute, ast.Attribute)
                and attribute.value is call
                and attribute.attr == "__name__"
                and isinstance(getattr(attribute, "ctx", None), ast.Load))
    if isinstance(node, ast.Attribute) and node.attr == "__name__":
        inner = node.value
        return (isinstance(inner, ast.Call)
                and isinstance(inner.func, ast.Name)
                and inner.func.id == "type"
                and isinstance(getattr(node, "ctx", None), ast.Load))
    return False


_REFLECTION_MATCHERS = {
    "RFL_IMPORTLIB_LOAD": _is_importlib_load,     # takes `bindings`
    "RFL_SYS_MODULES_REGISTER": _is_sys_modules_register,
    "RFL_TYPE_NAME": _is_type_name,
}


def reflection_scan(tree, *, check_manifest_usage=True):
    """Violations for every reflective construct outside the allowlist.

    `check_manifest_usage` asserts the reflection manifest describes
    exactly the productions the DESIGNATED collector module performs.
    Off only when scanning a throwaway snippet, which exercises a
    subset by construction.
    """
    violations, used = [], set()
    parent = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parent[child] = node
    loader_bindings = _loader_bindings(tree)

    # Pass 1: mark every node an allowlisted production matches, and
    # record which productions the module actually performs. Usage must
    # be collected here rather than inside the reflective-construct
    # check: RFL_IMPORTLIB_LOAD trips none of the reflective lists, so
    # consulting the matchers only on flagged nodes left it looking
    # unused and failed the manifest-vs-subject check.
    allowed = set()
    for node in ast.walk(tree):
        for pid, matcher in _REFLECTION_MATCHERS.items():
            if pid not in _REFLECTION_IDS:
                continue              # recognition never grants permission
            if pid == "RFL_IMPORTLIB_LOAD":
                matched = matcher(node, parent, loader_bindings)
            else:
                matched = matcher(node, parent)
            if matched:
                allowed.add(id(node))
                # `spec.loader.exec_module(module)` is two attribute
                # nodes; permitting only the outer one leaves `loader`
                # flagged and the declared form failing.
                if (pid == "RFL_IMPORTLIB_LOAD"
                        and isinstance(node, ast.Attribute)
                        and node.attr == "exec_module"):
                    allowed.add(id(node.value))
                used.add(pid)

    def permitted(node):
        return id(node) in allowed

    for node in ast.walk(tree):
        where = f"line {getattr(node, 'lineno', '?')}"
        if isinstance(node, ast.Name):
            if node.id in _REFLECTIVE_CALLS:
                if not permitted(node):
                    violations.append(
                        f"{where}: `{node.id}` is reflective and is not a "
                        f"permitted production")
            elif node.id in _GUARDED_BUILTINS:
                if not permitted(node):
                    violations.append(
                        f"{where}: `{node.id}` is permitted only as "
                        f"`type(x).__name__`")
        elif isinstance(node, ast.Attribute):
            if (node.attr in _REFLECTIVE_ATTRS
                    or node.attr in _REFLECTIVE_CALLS):
                if not permitted(node):
                    violations.append(
                        f"{where}: attribute `{node.attr}` is reflective and "
                        f"is not a permitted production")
            elif node.attr == "__name__" and not permitted(node):
                violations.append(
                    f"{where}: `__name__` is permitted only as "
                    f"`type(x).__name__`")
        # Imports are not screened here. A denylist of reflective
        # module names lost to `from pkgutil import resolve_name`, which
        # resolves "builtins:globals" from a string. `import_scan`
        # allowlists the exact forms this collector uses instead, so an
        # unapproved import fails whether or not it is reflective.

    for production in REFLECTION_MANIFEST if check_manifest_usage else ():
        if production.id not in used:
            violations.append(
                f"reflection manifest declares {production.id} but the "
                f"module performs no such operation; permission must track "
                f"the actual collector operations")
    for pid in _REFLECTION_MATCHERS:
        if pid not in _REFLECTION_IDS:
            violations.append(
                f"reflection matcher {pid} is not declared in the "
                f"manifest; an operation cannot be permitted by "
                f"recognition alone")
    return sorted(set(violations))


def _rebound_names(tree):
    """Every name the module binds, by any means.

    Keyed on `ctx=Store`, not on statement type. A first version
    enumerated Assign/For/withitem/ExceptHandler and so missed walrus
    bindings, comprehension targets and match-case captures -- the same
    enumerate-the-shapes mistake the scanner itself was rewritten to
    avoid, repeated in one of its helpers.
    """
    rebound = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            rebound.add(node.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                rebound.add((alias.asname or alias.name).split(".")[0])
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            rebound.update(node.names)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            rebound.add(node.name)          # a plain str, not a Name node
        elif isinstance(node, getattr(ast, "MatchAs", ())) and node.name:
            rebound.add(node.name)
        elif isinstance(node, getattr(ast, "MatchStar", ())) and node.name:
            rebound.add(node.name)
        elif isinstance(node, getattr(ast, "MatchMapping", ())) and node.rest:
            rebound.add(node.rest)
    return rebound


#: Builtins that expose or rewrite a binding namespace.
_NAMESPACE_BUILTINS = ("globals", "locals", "vars")

#: Builtins that can introduce or replace bindings from data.
_DYNAMIC_BINDING_BUILTINS = ("exec", "eval", "compile", "setattr",
                             "delattr", "__import__", "reload")

#: Attributes and names that hand out, or are, a binding namespace.
_NAMESPACE_ATTRS = ("__dict__", "__globals__", "__builtins__")

#: Modules whose attributes reach the above by any spelling.
_NAMESPACE_MODULES = ("builtins",)

_RISKY_SPELLINGS = frozenset(
    _NAMESPACE_BUILTINS + _DYNAMIC_BINDING_BUILTINS + _NAMESPACE_ATTRS)


def _namespace_rebinding_risk(tree):
    """Reasons the module's name bindings cannot be trusted.

    Deliberately conservative, and matched on the RESOLVED identity
    rather than a bare `Name`. Three successive versions of this check
    were escaped by a spelling it did not look for: first a subscript
    store only, then mapping-method mutation, then `builtins.globals()`
    and its import aliases. So the rule is now:

      * any name that resolves to a namespace or dynamic-binding
        builtin, including through `from builtins import globals as g`
        and through a local alias `g = globals`;
      * any ATTRIBUTE whose name is one of those spellings, whatever
        the base object -- `builtins.globals`, `b.globals`,
        `mod.__dict__`, `importlib.reload`;
      * importing the `builtins` module at all, which hands over every
        one of them under a name of the author's choosing.

    The collector module uses none of these, and a control asserts
    that. If one is ever needed, the answer is a declared production
    for it, not a looser default here.
    """
    reasons = []
    aliases = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module in \
                _NAMESPACE_MODULES:
            for alias in node.names:
                if alias.name in _RISKY_SPELLINGS:
                    aliases[alias.asname or alias.name] = alias.name
        elif isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in _NAMESPACE_MODULES:
                    reasons.append(
                        f"line {node.lineno}: `{alias.name}` is imported, "
                        f"which hands out namespace and dynamic-binding "
                        f"builtins under any name")
        elif (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and isinstance(node.value, ast.Name)
                and node.value.id in _RISKY_SPELLINGS):
            aliases[node.targets[0].id] = node.value.id

    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            resolved = aliases.get(node.id, node.id)
            if resolved in _NAMESPACE_BUILTINS or resolved in \
                    _NAMESPACE_ATTRS:
                reasons.append(f"line {node.lineno}: `{node.id}` resolves to "
                               f"`{resolved}`, which exposes a binding "
                               f"namespace")
            elif resolved in _DYNAMIC_BINDING_BUILTINS:
                reasons.append(f"line {node.lineno}: `{node.id}` resolves to "
                               f"`{resolved}`, which can rebind names from "
                               f"data")
        elif isinstance(node, ast.Attribute) and node.attr in \
                _RISKY_SPELLINGS:
            # Whatever the base: builtins.globals, b.globals,
            # mod.__dict__, importlib.reload.
            reasons.append(f"line {node.lineno}: attribute `{node.attr}` "
                           f"reaches a namespace or dynamic-binding "
                           f"builtin")
    return sorted(set(reasons))


def _namespace_is_writable(tree):
    """Retained as a second, independent line of defence.

    `reflection_scan` now prohibits this whole surface outright, so a
    module reaching it fails the scan regardless. This predicate still
    withdraws callable-identity trust, so a single mistake in the
    prohibition cannot by itself make a rebound callable look stable.
    """
    return bool(_namespace_rebinding_risk(tree))


def _stable_local_functions(tree):
    """`def` names never reassigned anywhere in the module.

    ARG_LOCAL_FN previously resolved a call by matching the `def` name,
    so a module that rebound that name leaked the evidence dict through
    whatever it was rebound to, with a zero-violation scan. This is the
    same identity rule already applied to serializer names: a spelling
    alone is never safe.
    """
    if _namespace_is_writable(tree):
        return {}
    defined, duplicated = {}, set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name in defined:
                duplicated.add(node.name)
            defined[node.name] = node
        elif isinstance(node, ast.ClassDef):
            duplicated.add(node.name)
    unstable = _rebound_names(tree) | duplicated
    return {name: fn for name, fn in defined.items() if name not in unstable}


def _callee_name(func):
    parts = []
    while isinstance(func, ast.Attribute):
        parts.append(func.attr)
        func = func.value
    if isinstance(func, ast.Name):
        parts.append(func.id)
        return ".".join(reversed(parts))
    return None


# ----------------------------------------------------------------------
# Recognizers. One per production id. A recognizer returns
# (matched, paths_to_record, violations) and is consulted ONLY when its
# id appears in MANIFEST -- so adding a recognizer without declaring the
# production leaves the operation unclassified, which is a violation.
# ----------------------------------------------------------------------

def _r_init(ctxt):
    node, up = ctxt.node, ctxt.parent_of_node
    if not (isinstance(node, ast.Name)
            and isinstance(getattr(node, "ctx", None), ast.Store)
            and isinstance(up, ast.Assign) and any(t is node
                                                   for t in up.targets)):
        return None
    out, bad = set(), []
    if not isinstance(up.value, ast.Dict):
        return (True, out, [f"{ctxt.where}: `evidence` bound to "
                            f"{type(up.value).__name__}, not a dict literal"])
    _literal_dict_paths([], up.value, out, bad, ctxt.where)
    return (True, out, bad)


def _r_assign(ctxt, want_depth):
    node, up = ctxt.node, ctxt.parent_of_node
    if not (isinstance(node, ast.Subscript)
            and isinstance(getattr(node, "ctx", None), ast.Store)):
        return None
    if not (isinstance(up, ast.Assign) and any(t is node for t in up.targets)):
        return None                       # chained/unpacked/annotated/loop
    chain = _literal_chain(node)
    if isinstance(chain, tuple):
        return (True, set(), [f"{ctxt.where}: computed key in an evidence "
                              f"write"])
    if chain is None or len(chain) != want_depth:
        return None
    out, bad = {".".join(chain)}, []
    _literal_dict_paths(chain, up.value, out, bad, ctxt.where)
    return (True, out, bad)


def _r_append_d1(ctxt):
    node, up = ctxt.node, ctxt.parent_of_node
    if not (isinstance(node, ast.Subscript)
            and isinstance(getattr(node, "ctx", None), ast.Load)
            and isinstance(up, ast.Attribute) and up.attr == "append"):
        return None
    call = ctxt.parent.get(up)
    if not (isinstance(call, ast.Call) and call.func is up
            and len(call.args) == 1 and not call.keywords):
        return None
    chain = _literal_chain(node)
    if isinstance(chain, tuple) or chain is None or len(chain) != 1:
        return None
    return (True, set(), [])              # reads; adds no key


def _r_setdefault_append(ctxt):
    node, up = ctxt.node, ctxt.parent_of_node
    if not (isinstance(node, ast.Name)
            and isinstance(getattr(node, "ctx", None), ast.Load)
            and isinstance(up, ast.Attribute) and up.attr == "setdefault"):
        return None
    call = ctxt.parent.get(up)
    if not (isinstance(call, ast.Call) and call.func is up):
        return None
    where = ctxt.where
    if call.keywords or len(call.args) != 2:
        return (True, set(), [f"{where}: setdefault must take exactly two "
                              f"positional arguments"])
    key = call.args[0]
    if not (isinstance(key, ast.Constant) and isinstance(key.value, str)):
        return (True, set(), [f"{where}: setdefault with a computed key"])
    # The declared identity: the result may be consumed ONLY by .append().
    outer_attr = ctxt.parent.get(call)
    outer_call = ctxt.parent.get(outer_attr) if outer_attr is not None else None
    if not (isinstance(outer_attr, ast.Attribute)
            and outer_attr.value is call
            and outer_attr.attr == "append"
            and isinstance(outer_call, ast.Call)
            and outer_call.func is outer_attr):
        return (True, set(), [f"{where}: the setdefault result is not "
                              f"consumed by .append(); its fate is "
                              f"undeclared"])
    out, bad = {key.value}, []
    _literal_dict_paths([key.value], call.args[1], out, bad, where)
    return (True, out, bad)


def _r_arg_local_fn(ctxt):
    node, up = ctxt.node, ctxt.parent_of_node
    if not (isinstance(node, ast.Name)
            and isinstance(getattr(node, "ctx", None), ast.Load)
            and isinstance(up, ast.Call) and up.func is not node):
        return None
    if not isinstance(up.func, ast.Name):
        return None
    fn = ctxt.local_funcs.get(up.func.id)
    if fn is None:
        if up.func.id in ctxt.declared_funcs:
            return (True, set(),
                    [f"{ctxt.where}: `evidence` passed to {up.func.id}(), "
                     f"whose name is rebound in this module, so the callable "
                     f"has no stable identity; a spelling alone is never "
                     f"safe"])
        return None
    params = [a.arg for a in fn.args.args]
    for i, arg in enumerate(up.args):
        if arg is node:
            name = params[i] if i < len(params) else None
            if name != "evidence":
                return (True, set(),
                        [f"{ctxt.where}: `evidence` passed to {fn.name}() as "
                         f"`{name}`; writes there are invisible"])
            return (True, set(), [])
    for kw in up.keywords:
        if kw.value is node:
            if kw.arg != "evidence":
                return (True, set(),
                        [f"{ctxt.where}: `evidence` passed to {fn.name}() as "
                         f"`{kw.arg}`"])
            return (True, set(), [])
    return None


def _r_arg_serializer(ctxt):
    node, up = ctxt.node, ctxt.parent_of_node
    if not (isinstance(node, ast.Name)
            and isinstance(getattr(node, "ctx", None), ast.Load)
            and isinstance(up, ast.Call) and up.func is not node):
        return None
    callee = _callee_name(up.func)
    if callee not in _SERIALIZERS:
        return None
    if not any(a is node for a in up.args):
        return (True, set(), [f"{ctxt.where}: `evidence` passed to {callee}() "
                              f"other than positionally"])
    root = callee.split(".")[0]
    if root not in ctxt.trusted:
        return (True, set(),
                [f"{ctxt.where}: `{root}` is not an untouched import, so "
                 f"{callee}() has no stable identity; a spelling alone is "
                 f"never safe"])
    return (True, set(), [])


def _r_read_in(ctxt, consumer):
    node, up = ctxt.node, ctxt.parent_of_node
    if not (isinstance(node, ast.Subscript)
            and isinstance(getattr(node, "ctx", None), ast.Load)
            and isinstance(up, consumer)):
        return None
    chain = _literal_chain(node)
    if isinstance(chain, tuple):
        return (True, set(), [f"{ctxt.where}: computed key in an evidence "
                              f"read"])
    if chain is None or len(chain) > MAX_PATH_DEPTH:
        return None
    return (True, set(), [])


RECOGNIZERS = {
    "INIT": _r_init,
    "ASSIGN_D1": lambda c: _r_assign(c, 1),
    "ASSIGN_D2": lambda c: _r_assign(c, 2),
    "APPEND_D1": _r_append_d1,
    "SETDEFAULT_APPEND": _r_setdefault_append,
    "ARG_LOCAL_FN": _r_arg_local_fn,
    "ARG_SERIALIZER": _r_arg_serializer,
    "READ_BINOP": lambda c: _r_read_in(c, ast.BinOp),
    "READ_UNARYOP": lambda c: _r_read_in(c, ast.UnaryOp),
    "READ_FSTRING": lambda c: _r_read_in(c, ast.FormattedValue),
}


class _Ctxt:
    def __init__(self, node, parent, local_funcs, trusted, where,
                 declared_funcs=frozenset()):
        self.node = node
        self.parent = parent
        self.parent_of_node = parent.get(node)
        self.local_funcs = local_funcs
        self.trusted = trusted
        self.where = where
        #: every `def` name, stable or not, so a call to an unstable one
        #: is reported as an identity failure rather than falling
        #: through to the generic no-production message.
        self.declared_funcs = declared_funcs


def evidence_grammar_scan(path, *, check_manifest_usage=True):
    """(write_paths, violations) under the manifest, fail-closed.

    `check_manifest_usage` asserts the manifest describes exactly the
    operations the DESIGNATED collector module performs. It is on by
    default and switched off only when scanning a throwaway snippet in
    a control, which exercises a few productions by construction.

    Every maximal evidence-rooted reference must match exactly one
    declared production. There is no default-allow branch: the final
    `else` records a violation, and a control asserts that branch still
    fires.
    """
    tree = ast.parse(pathlib.Path(path).read_text())
    paths, bad, used = set(), [], set()

    parent = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parent[child] = node

    # Identity-stable local callables only.
    # Reflection is prohibited outside the three declared productions,
    # so these violations are part of the scan's verdict, not advisory.
    bad.extend(import_scan(tree, check_manifest_usage=check_manifest_usage))
    bad.extend(reflection_scan(tree,
                               check_manifest_usage=check_manifest_usage))
    local_funcs = _stable_local_functions(tree)
    declared_funcs = {n.name for n in ast.walk(tree)
                      if isinstance(n, (ast.FunctionDef,
                                        ast.AsyncFunctionDef))}
    trusted = _untouched_imports(tree)

    for node in ast.walk(tree):
        if not isinstance(node, (ast.Name, ast.Subscript)):
            continue
        if _literal_chain(node) is None:
            continue
        up = parent.get(node)
        if isinstance(up, ast.Subscript) and up.value is node:
            continue                       # not maximal
        where = f"line {getattr(node, 'lineno', '?')}"
        ctxt = _Ctxt(node, parent, local_funcs, trusted, where,
                     declared_funcs)

        matched = None
        for production in MANIFEST:        # manifest order IS the grammar
            recognizer = RECOGNIZERS.get(production.id)
            if recognizer is None:
                bad.append(f"manifest declares {production.id} with no "
                           f"recognizer")
                continue
            result = recognizer(ctxt)
            if result is None:
                continue
            _, recorded, problems = result
            matched = production.id
            used.add(production.id)
            paths.update(recorded)
            bad.extend(problems)
            break

        if matched is None:
            # THE FAIL-CLOSED DEFAULT. Everything unmatched lands here,
            # including forms neither author anticipated.
            bad.append(f"{where}: evidence reference in "
                       f"{type(up).__name__} matches no declared production "
                       f"({GRAMMAR_VERSION}); the collector boundary cannot "
                       f"speak for it")

    # Manifest-vs-subject: a production the module no longer performs must
    # not linger as standing permission.
    for production in MANIFEST if check_manifest_usage else ():
        if production.id not in used:
            bad.append(f"manifest declares {production.id} but the module "
                       f"performs no such operation; permission must track "
                       f"the actual collector operations")

    # A recognizer without a manifest entry can never accept anything, but
    # say so loudly rather than leaving dead code that looks protective.
    for pid in RECOGNIZERS:
        if pid not in _BY_ID:
            bad.append(f"recognizer {pid} is not declared in the manifest; "
                       f"an operation cannot be accepted by recognition "
                       f"alone")

    return paths, sorted(set(bad))
