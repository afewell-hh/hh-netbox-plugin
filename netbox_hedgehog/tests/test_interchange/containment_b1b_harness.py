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


def evidence_write_paths(path, max_depth=2):
    tree = ast.parse(pathlib.Path(path).read_text())
    out = set()
    for n in ast.walk(tree):
        # evidence = {...}
        if (isinstance(n, ast.Assign) and len(n.targets) == 1
                and isinstance(n.targets[0], ast.Name)
                and n.targets[0].id == "evidence"):
            _dict_paths([], n.value, out, max_depth)
        tgt = (n.targets[0] if isinstance(n, ast.Assign) and len(n.targets) == 1
               else n.target if isinstance(n, ast.AugAssign) else None)
        if tgt is not None:
            ch = _chain(tgt)
            if ch:
                out.add(".".join(ch))
                _dict_paths(ch, getattr(n, "value", None), out,
                            max_depth - len(ch) + 1)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
            base = _chain(n.func.value)
            if n.func.attr == "setdefault" and n.args and isinstance(
                    n.args[0], ast.Constant):
                if isinstance(n.func.value, ast.Name) and \
                        n.func.value.id == "evidence":
                    out.add(n.args[0].value)
                elif base:
                    out.add(".".join(base + [n.args[0].value]))
            if n.func.attr == "update" and n.args:
                root = ([] if (isinstance(n.func.value, ast.Name)
                               and n.func.value.id == "evidence") else base)
                if root is not None:
                    _dict_paths(root, n.args[0], out, max_depth)
    return out

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


# ----------------------------------------------------------------------
# Evidence-coverage: a BOUNDED SUPPORTED GRAMMAR.
#
# Three rounds of enumerate-the-bypass-and-patch each left another form
# uncounted, because an unrecognised write was silently invisible. The
# burden is inverted here: every construct that stores into `evidence`
# must match one of the forms below, and anything else is reported as a
# violation that fails the control. A new form cannot slip past by being
# unrecognised -- being unrecognised is itself the failure.
#
# SUPPORTED WRITE FORMS (keys must be string literals; paths <= depth 2):
#   W1  evidence = {...}                     initialiser
#   W2  evidence["k"] = expr                 top-level assignment
#   W3  evidence["k"]["j"] = expr            nested assignment
#   W4  evidence.setdefault("k", expr)       with expr's dict keys counted
#   W5  evidence["k"].update({...})          and evidence.update({...})
#   W6  evidence["k"].append(...) / .extend(...)   mutates a value, adds
#                                            no key
#   W7  evidence.setdefault("k", []).append(...)   same, on the result
#   In W2/W4/W5, a dict-literal value contributes its own nested paths.
#
# REJECTED (each fails the control rather than going uncounted):
#   keyword form          evidence.update(k=1)
#   computed key          evidence[expr] = v, {expr: v}
#   dict unpacking        evidence.update({**other})
#   depth overflow        any path deeper than 2
#   aliasing              ev = evidence; ev["k"] = v
#   nested aliasing       p = evidence["k"]; p["j"] = v
#   escaped setdefault    evidence.setdefault(...) bound to a name, or
#                         mutated by anything but append/extend
#   name escape           evidence passed to a local function whose
#                         parameter is not also named `evidence`
# ----------------------------------------------------------------------

MAX_PATH_DEPTH = 2
_MUTATORS = ("append", "extend")
_READ_METHODS = ("get", "pop", "keys", "items", "values", "copy")
# Foreign callables that may receive `evidence` whole. Anything else
# outside the module could retain it and write through the reference,
# which the scanner cannot see -- so it is rejected rather than assumed
# safe. Local functions are checked separately, by parameter name.
_SAFE_FOREIGN_CALLS = ("json.dump", "json.dumps", "len", "bool", "repr",
                       "sorted", "id", "print")
# Non-retaining uses: they inspect the object and let no reference
# outlive the expression. RETAINING uses -- a container, a return, a
# yield, a closure -- are rejected instead, because a write through the
# retained reference is invisible exactly as an alias write is.
_READ_CONTEXTS = (ast.Compare, ast.BoolOp, ast.UnaryOp, ast.BinOp,
                  ast.IfExp, ast.FormattedValue, ast.JoinedStr,
                  ast.Expr, ast.Assert, ast.Subscript,
                  ast.For, ast.If, ast.While)


def _ev_chain(node, root="evidence"):
    """['a','b'] for <root>['a']['b']; None if not rooted at <root>, and
    ('COMPUTED', depth) if rooted there through a non-literal key."""
    parts, computed = [], False
    while isinstance(node, ast.Subscript):
        if (isinstance(node.slice, ast.Constant)
                and isinstance(node.slice.value, str)):
            parts.append(node.slice.value)
        else:
            computed = True
            parts.append(None)
        node = node.value
    if isinstance(node, ast.Name) and node.id == root:
        if computed:
            return ("COMPUTED", len(parts))
        return list(reversed(parts))
    return None


def _dict_literal_paths(prefix, node, out, bad, where):
    if not isinstance(node, ast.Dict):
        return
    for key, value in zip(node.keys, node.values):
        if key is None:
            bad.append(f"{where}: dict unpacking inside an evidence literal")
            continue
        if not (isinstance(key, ast.Constant) and isinstance(key.value, str)):
            bad.append(f"{where}: computed key inside an evidence "
                       f"dict literal")
            continue
        path = prefix + [key.value]
        if len(path) > MAX_PATH_DEPTH:
            bad.append(f"{where}: path {'.'.join(path)} is deeper than "
                       f"{MAX_PATH_DEPTH}")
            continue
        out.add(".".join(path))
        _dict_literal_paths(path, value, out, bad, where)


def _is_evidence_accessor_call(node):
    """`evidence.setdefault(...)` / `evidence["k"].get(...)` -- a call
    returning an object that lives inside evidence."""
    return (isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in ("setdefault", "get")
            and _ev_chain(node.func.value) is not None)


def evidence_grammar_scan(path):
    """(write_paths, violations) for the subject at `path`.

    NODE-LEVEL CLASSIFICATION. Every maximal `evidence`-rooted expression
    in the module is located and classified, and the final branch is
    `else: violation`. Earlier versions enumerated statement shapes, so a
    form the walker never looked for -- a loop target, a nested tuple
    target, an annotated assignment -- was neither recorded nor rejected.
    Keying stores on `ctx` instead of on statement type makes every store
    position fall out by construction: assignment, augmented, annotated,
    chained, `for` target, `with ... as`, comprehension target, and
    tuple/list targets nested to any depth.
    """
    tree = ast.parse(pathlib.Path(path).read_text())
    paths, bad = set(), []

    parent = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parent[child] = node

    local_funcs = {n.name: n for n in ast.walk(tree)
                   if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    trusted = _untouched_imports(tree)

    def maximal(node):
        """An evidence-rooted expression not contained in a larger one."""
        if not isinstance(node, (ast.Name, ast.Subscript)):
            return False
        probe = node
        while isinstance(probe, ast.Subscript):
            probe = probe.value
        if not (isinstance(probe, ast.Name) and probe.id == "evidence"):
            return False
        up = parent.get(node)
        return not (isinstance(up, ast.Subscript) and up.value is node)

    def record(expr, where, value=None):
        chain = _ev_chain(expr)
        if chain is None:                       # the bare name as a target
            bad.append(f"{where}: `evidence` itself rebound")
            return
        if isinstance(chain, tuple):
            bad.append(f"{where}: computed key in an evidence write")
            return
        if len(chain) > MAX_PATH_DEPTH:
            bad.append(f"{where}: write to {'.'.join(chain)} is deeper "
                       f"than {MAX_PATH_DEPTH}")
            return
        paths.add(".".join(chain))
        if value is not None:
            _dict_literal_paths(chain, value, paths, bad, where)

    for node in ast.walk(tree):
        if not maximal(node):
            continue
        where = f"line {getattr(node, 'lineno', '?')}"
        up = parent.get(node)
        ctx = getattr(node, "ctx", None)

        # ---- stores: every position, by ctx ----
        if isinstance(ctx, ast.Store):
            value = None
            if isinstance(up, (ast.Assign, ast.AnnAssign)):
                # Nested-literal collection only when this IS the whole
                # target; through unpacking the value cannot be mapped.
                if isinstance(up, ast.AnnAssign) or any(
                        t is node for t in up.targets):
                    value = up.value
            if isinstance(node, ast.Name):
                if isinstance(up, ast.Assign) and isinstance(value, ast.Dict):
                    _dict_literal_paths([], value, paths, bad, where)
                elif isinstance(up, ast.Assign) and isinstance(value, ast.Name):
                    pass                      # evidence = evidence
                else:
                    bad.append(f"{where}: `evidence` bound to an unsupported "
                               f"expression "
                               f"({type(value).__name__ if value else '?'})")
            else:
                record(node, where, value)
            continue

        if isinstance(ctx, ast.Del):
            continue                           # removes a key, adds none

        # ---- loads ----
        if isinstance(up, ast.Attribute):
            call = parent.get(up)
            if not (isinstance(call, ast.Call) and call.func is up):
                bad.append(f"{where}: attribute `.{up.attr}` taken on "
                           f"evidence without calling it")
                continue
            _classify_method(node, up, call, where, paths, bad)
            # What happens to what the call RETURNED. setdefault/get/pop
            # hand back an object living inside evidence; a write through
            # it is invisible. The node-level rewrite initially lost this
            # check, because the result is a Call and so is not itself an
            # evidence-rooted expression that the walker would classify.
            if up.attr in ("setdefault",) + _READ_METHODS:
                _classify_result_use(call, parent, local_funcs, where, bad,
                                     trusted)
            continue

        _classify_value_use(node, parent, local_funcs, where, bad,
                            "an `evidence` object", trusted)

    return paths, sorted(set(bad))


# Value-propagating parents: the enclosing expression can evaluate TO the
# object, so the real use is further up. `evidence or {}` bound to a name
# retains evidence exactly as `ev = evidence` does; classifying the
# immediate parent (a BoolOp, allowed as an inspection) missed it.
_VALUE_PROPAGATORS = (ast.BoolOp, ast.IfExp, ast.NamedExpr)

# Terminal uses that only inspect: they consume the object and let no
# reference outlive the expression.
_INSPECTING = (ast.Compare, ast.UnaryOp, ast.BinOp, ast.FormattedValue,
               ast.JoinedStr, ast.Expr, ast.Assert, ast.Subscript,
               ast.If, ast.While, ast.For, ast.comprehension)

# Terminal uses that retain a reference.
_RETAINING = (ast.Tuple, ast.List, ast.Dict, ast.Set, ast.Return,
              ast.Yield, ast.YieldFrom, ast.Lambda, ast.arguments,
              ast.GeneratorExp, ast.ListComp, ast.SetComp, ast.DictComp,
              ast.Starred, ast.Await)


def _terminal_use(node, parent):
    """Climb while the parent evaluates to this node's value."""
    cur = node
    while True:
        up = parent.get(cur)
        if isinstance(up, ast.BoolOp):
            cur = up
        elif isinstance(up, ast.IfExp) and (up.body is cur or up.orelse is cur):
            cur = up
        else:
            return up, cur


def _classify_value_use(node, parent, local_funcs, where, bad, what,
                        trusted=()):
    """Classify what finally happens to an evidence-derived object.

    Shared by evidence-rooted expressions and by accessor-call results:
    they were classified separately before, and the two code paths did
    not cover the same terminal forms.
    """
    up, cur = _terminal_use(node, parent)

    if isinstance(up, ast.NamedExpr) and up.value is cur:
        bad.append(f"{where}: {what} captured by a walrus binding; writes "
                   f"through it are invisible")
        return
    if isinstance(up, (ast.Assign, ast.AnnAssign)) and up.value is cur:
        # ANY target retains the reference. Restricting this to
        # Name/Tuple/List let `box["e"] = evidence` and `obj.attr =
        # evidence` store it in a container slot and write through it.
        targets = up.targets if isinstance(up, ast.Assign) else [up.target]
        kinds = ", ".join(sorted({type(t).__name__ for t in targets}))
        bad.append(f"{where}: {what} is stored into a {kinds} target; "
                   f"writes through it are invisible")
        return
    if isinstance(up, ast.keyword):
        call = parent.get(up)
        _classify_call_recipient(call, up.arg, local_funcs, where, bad, what,
                                 parent, trusted)
        return
    if isinstance(up, ast.Call):
        if up.func is cur:
            return                       # calling it, not passing it
        index = next((i for i, a in enumerate(up.args) if a is cur), None)
        _classify_call_recipient(up, index, local_funcs, where, bad, what,
                                 parent, trusted)
        return
    if isinstance(up, _RETAINING):
        bad.append(f"{where}: {what} is retained in "
                   f"{type(up).__name__}; writes through it are invisible")
        return
    if isinstance(up, _INSPECTING):
        return
    bad.append(f"{where}: unclassified use of {what} in "
               f"{type(up).__name__}; the coverage guard cannot speak for it")


def _classify_call_recipient(call, where_in_call, local_funcs, where, bad,
                             what, parent, trusted=()):
    """A callable receiving the object may retain and write through it."""
    if call is None:
        bad.append(f"{where}: {what} passed to an unresolvable call")
        return
    callee = _callee_name(call.func)
    fn = local_funcs.get(call.func.id) if isinstance(call.func,
                                                     ast.Name) else None
    if fn is not None:
        params = [a.arg for a in fn.args.args]
        if isinstance(where_in_call, int) and where_in_call < len(params):
            name = params[where_in_call]
        else:
            name = where_in_call
        if name not in (None, "evidence"):
            bad.append(f"{where}: {what} passed to {fn.name}() as "
                       f"`{name}`; writes there are invisible")
        return
    if callee not in _SAFE_FOREIGN_CALLS:
        bad.append(f"{where}: {what} passed to "
                   f"{callee or 'an unnamed callable'}(), which is not a "
                   f"declared-safe recipient")
    elif callee.split(".")[0] not in trusted:
        # The allowlist matches by NAME, and a name can be rebound:
        # `json = something_else` then `json.dumps(evidence)` reaches an
        # arbitrary callable. A safe name must be import-bound and never
        # reassigned in the module.
        bad.append(f"{where}: {what} passed to {callee}(), whose name "
                   f"`{callee.split('.')[0]}` is not an untouched import; "
                   f"the allowlist cannot vouch for it")


def _callee_name(func):
    parts = []
    while isinstance(func, ast.Attribute):
        parts.append(func.attr)
        func = func.value
    if isinstance(func, ast.Name):
        parts.append(func.id)
        return ".".join(reversed(parts))
    return None


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


def _classify_result_use(call, parent, local_funcs, where, bad, trusted=()):
    """What happens to what an accessor returned.

    Routed through the same classifier as evidence-rooted expressions:
    the two paths previously enumerated different terminal forms, so an
    accessor result handed to an undeclared callable was accepted while
    the bare object was rejected.
    """
    up = parent.get(call)
    if isinstance(up, ast.Attribute):
        outer = parent.get(up)
        if not (isinstance(outer, ast.Call) and outer.func is up):
            bad.append(f"{where}: attribute `.{up.attr}` taken on an "
                       f"evidence accessor result without calling it")
        elif up.attr not in _MUTATORS:
            bad.append(f"{where}: .{up.attr}() on the result of an evidence "
                       f"accessor; any key it adds is invisible")
        return
    if isinstance(up, ast.Subscript):
        if isinstance(getattr(up, "ctx", None), (ast.Store, ast.Del)):
            bad.append(f"{where}: store into the result of an evidence "
                       f"accessor; the key is invisible")
            return
        # A Load subscript yields a deeper object still inside evidence.
        # Returning here let `held = evidence.setdefault("k", {})["j"]`
        # retain it unclassified.
        _classify_value_use(up, parent, local_funcs, where, bad,
                            "an indexed evidence accessor result", trusted)
        return
    _classify_value_use(call, parent, local_funcs, where, bad,
                        "an evidence accessor result", trusted)


def _classify_method(expr, attr_node, call, where, paths, bad):
    base = _ev_chain(expr)
    if isinstance(base, tuple):
        bad.append(f"{where}: computed key in an evidence "
                   f".{attr_node.attr}() call")
        return
    if base is None:
        base = []
    name = attr_node.attr
    if name == "setdefault":
        if not (call.args and isinstance(call.args[0], ast.Constant)
                and isinstance(call.args[0].value, str)):
            bad.append(f"{where}: setdefault with a computed key")
            return
        if call.keywords:
            bad.append(f"{where}: setdefault with keyword arguments")
        chain = base + [call.args[0].value]
        if len(chain) > MAX_PATH_DEPTH:
            bad.append(f"{where}: setdefault path {'.'.join(chain)} is "
                       f"deeper than {MAX_PATH_DEPTH}")
            return
        paths.add(".".join(chain))
        if len(call.args) > 1:
            _dict_literal_paths(chain, call.args[1], paths, bad, where)
    elif name == "update":
        if call.keywords:
            bad.append(f"{where}: update() in keyword form; its keys are "
                       f"not collected")
        if not call.args:
            return
        if not isinstance(call.args[0], ast.Dict):
            bad.append(f"{where}: update() with a non-literal mapping "
                       f"({type(call.args[0]).__name__})")
        else:
            _dict_literal_paths(base, call.args[0], paths, bad, where)
    elif name in _MUTATORS or name in _READ_METHODS:
        pass
    else:
        bad.append(f"{where}: unsupported evidence method .{name}()")
