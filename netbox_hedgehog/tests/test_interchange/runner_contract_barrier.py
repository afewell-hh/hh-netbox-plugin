"""Test-only blocking barrier for the #711 driver. Lane-local, never imported
by product code.

Deployed into a disposable lane as `sitecustomize.py` on the child's
PYTHONPATH, so it is active only for interpreters that lane starts. It wraps
`DiscoverRunner.run_suite`, which runs after dispatch and suite construction
complete, so nothing about the wrapper decision under observation changes.

Why a barrier and not `Found N test(s)`: that line is a notification. By the
time a host reads it from a pipe the child has moved on, so there is a race
between observing and acting. A barrier blocks the child until released or
killed, which is the difference between knowing a decision was made and being
able to act on it before bodies run.
"""

import os

# HH711_BARRIER_DELAY exists only to make the "delayed barrier" negative
# real: a barrier that engages late must be reported unresolved, not as a
# successful hold.
if os.environ.get("HH711_BARRIER"):
    _path = os.environ["HH711_BARRIER"]
    try:
        from django.test.runner import DiscoverRunner
        _original = DiscoverRunner.run_suite

        def run_suite(self, suite, **kwargs):
            # Test-only decoy descendant, so process-group cleanup can be
            # proven against a tree that actually has one. A real Django run
            # of a small selection spawns no children, which is why the
            # earlier wrapper-path cleanup check saw a single-member group
            # and could not exercise reparenting at all.
            if os.environ.get("HH711_SPAWN_ORPHAN"):
                import subprocess as _sp
                _sp.Popen(["sh", "-c",
                           "( sleep 1200 & ) ; sleep 2   # HH711_ORPHAN_DECOY"])

            _delay = float(os.environ.get("HH711_BARRIER_DELAY", "0") or 0)
            if _delay:
                import time as _t; _t.sleep(_delay)
            # Dispatch and suite construction are already complete here;
            # nothing observable about the wrapper's decision changes.
            #
            # A count is not an identity: two different selections can both
            # yield 8 tests, so `tests=8` cannot tell a row which selection
            # the wrapper actually resolved. Record the argv the wrapper
            # built and the resolved test ids themselves.
            import json as _json, sys as _sys

            def _ids(node, out):
                if hasattr(node, "__iter__"):
                    for child in node:
                        _ids(child, out)
                else:
                    out.append(node.id())
                return out

            resolved = _ids(suite, [])
            payload = {
                # Binding: everything a row needs to tie this observation to
                # one invocation. A count, an argv, or a PID alone can all be
                # satisfied by a different run; together with the invocation
                # id they cannot.
                "invocation": os.environ.get("HH711_INVOCATION", ""),
                "pid": os.getpid(),
                "pgid": os.getpgid(0),
                "sid": os.getsid(0),
                "argv": _sys.argv,
                "test_count": suite.countTestCases(),
                "resolved_ids": sorted(resolved),
                "resolved_modules": sorted({i.rsplit(".", 2)[0] for i in resolved}),
            }
            with open(_path, "w") as handle:
                handle.write(_json.dumps(payload, sort_keys=True))
            print("HH711_BARRIER_REACHED " + _json.dumps(
                {k: payload[k] for k in
                 ("invocation", "pid", "pgid", "sid", "test_count", "resolved_modules")},
                sort_keys=True), flush=True)
            while os.path.exists(_path + ".hold"):
                import time; time.sleep(0.2)
            return _original(self, suite, **kwargs)

        DiscoverRunner.run_suite = run_suite
    except Exception as exc:   # never break the run being observed
        print(f"HH711_BARRIER_UNAVAILABLE {type(exc).__name__}", flush=True)
