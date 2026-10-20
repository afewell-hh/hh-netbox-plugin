"""Child probe for #719 observer controls. Never a daemon-evidence producer.

Tracing and unittest run IN THE SAME INTERPRETER. The separate parent checks
bindings and stream/result consistency, not independent Python execution.
The partitioned positive is a deliberately named harness model, not the subject.
"""

import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest

from . import safety_g1_support as S


def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item


def load_reference(root, partition_model):
    for name in S.SOURCE_HASHES:
        (root / name).write_bytes(S.source_bytes(name))
    module = types.ModuleType(S.MODULE)
    module.__file__ = str(root / "test_containment_prover_safety.py")
    sys.modules[S.MODULE] = module
    exec(compile(S.source_bytes("test_containment_prover_safety.py"),
                 "hh719-reviewed-safety", "exec", dont_inherit=True), module.__dict__)
    if partition_model:
        # Positive-control fixture only. Keep all eleven ORIGINAL callables;
        # don't rewrite their assertions or fabricate body-entry records.
        original = module.ProverSafetyControls
        from django.test import SimpleTestCase

        def source_setup(cls):
            SimpleTestCase.setUpClass.__func__(cls)

        for name, obligation in ((S.SOURCE_CLASS, "source"), (S.EVIDENCE_CLASS, "b1a")):
            attributes = {"__module__": S.MODULE}
            for _, method, kind in S.ROWS:
                if kind != obligation:
                    attributes[method] = None
            if obligation == "source":
                attributes["setUpClass"] = classmethod(source_setup)
            setattr(module, name, type(name, (original,), attributes))
        del module.ProverSafetyControls
    return module


class CapturedResult(unittest.TestResult):
    def __init__(self):
        super().__init__()
        self.outcomes = []
        self.setup_errors = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.outcomes.append({"id": test.id(), "outcome": "success"})

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.outcomes.append({"id": test.id(), "outcome": "failure"})

    def addError(self, test, err):
        super().addError(test, err)
        if isinstance(test, unittest.TestCase):
            self.outcomes.append({"id": test.id(), "outcome": "error"})
        else:
            self.setup_errors.append({"id": test.id(), "error": str(err[1]),
                                      "type": type(err[1]).__name__,
                                      "reason": getattr(err[1], "reason", None)})

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.outcomes.append({"id": test.id(), "outcome": "skip"})

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self.outcomes.append({"id": test.id(), "outcome": "expectedFailure"})

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self.outcomes.append({"id": test.id(), "outcome": "unexpectedSuccess"})


def probe(request):
    from django.conf import settings
    if not settings.configured:
        settings.configure(SECRET_KEY="fixture-only", DATABASES={}, INSTALLED_APPS=[])
    import django
    django.setup()

    # A newly added accidental probe/command must fail, not invoke a daemon or
    # signal a process. Source reads and classify_not_found are the only uses
    # of the frozen prover/rescue inputs. No socket is mounted in the lane.
    def deny_external(event, args):
        if event in ("subprocess.Popen", "os.system", "os.kill", "os.killpg",
                     "socket.connect", "socket.bind"):
            raise RuntimeError(f"external action forbidden in fixture probe: {event}")
    sys.addaudithook(deny_external)

    with tempfile.TemporaryDirectory(prefix="hh719-source-fixture-") as tmp:
        root = Path(tmp)
        os.environ.pop("HH716_B1A_EVIDENCE", None)
        if request["payload"] is not None:
            if request["mutation"] == "runner-failure":
                # Fail an ORIGINAL assertion, with its original code identity.
                request["payload"]["host_kill_baseline_attempted"] = True
            payload = root / "synthetic-fixture.json"
            payload.write_text(json.dumps(request["payload"]))
            os.environ["HH716_B1A_EVIDENCE"] = str(payload)
        module = load_reference(root, request["partition_model"])
        mutation = request["mutation"]
        if mutation == "crash-observer":
            raise RuntimeError("deliberate observer process failure")
        if mutation == "drop-evidence-class":
            delattr(module, S.EVIDENCE_CLASS)
        elif mutation == "rename-evidence-class":
            cls = getattr(module, S.EVIDENCE_CLASS)
            cls.__name__ = "RenamedB1aControls"
            cls.__qualname__ = "RenamedB1aControls"
        elif mutation == "rename-method":
            cls = getattr(module, S.SOURCE_CLASS)
            method = S.ROWS[0][1]
            setattr(cls, method + "_renamed", getattr(cls, method))
            setattr(cls, method, None)
        elif mutation == "move-across-gate":
            method = S.ROWS[-1][1]
            evidence_cls = getattr(module, S.EVIDENCE_CLASS)
            setattr(getattr(module, S.SOURCE_CLASS), method, getattr(evidence_cls, method))
            setattr(evidence_cls, method, None)
        elif mutation == "undiscover-evidence":
            module.load_tests = lambda loader, suite, pattern: loader.loadTestsFromTestCase(
                getattr(module, S.SOURCE_CLASS))
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromModule(module)
        cases = list(flatten(suite))
        discovered = [t.id() for t in cases]
        entries = []

        def profile(frame, event, arg):
            if event != "call":
                return
            test = frame.f_locals.get("self")
            if not isinstance(test, unittest.TestCase):
                return
            method = getattr(test, getattr(test, "_testMethodName", ""), None)
            if getattr(method, "__code__", None) is frame.f_code:
                entries.append({"id": test.id(),
                                "code": S.callable_digest(frame.f_code)})

        result = CapturedResult()
        if mutation == "noop-original-id":
            first = cases[0]
            def replacement(self):
                pass
            setattr(type(first), first._testMethodName, replacement)
        sys.setprofile(profile)
        try:
            if mutation in ("disable-observer", "restore-after-bypass"):
                sys.setprofile(None)
            if mutation == "bypass-bodies":
                # Real defective runner: reports success without invoking tests.
                # Do not fake the trace channel: it must remain empty.
                for case in cases:
                    result.startTest(case)
                    result.addSuccess(case)
                    result.stopTest(case)
            else:
                suite.run(result)
            if mutation == "restore-after-bypass":
                sys.setprofile(profile)
            intact = sys.getprofile() is profile
        finally:
            sys.setprofile(None)
        report = {"context": request["context"], "complete": True,
                  "observer": "in-process-profile/1;shared-interpreter",
                  "observer_intact": intact, "discovered": discovered,
                  "entries": entries, "outcomes": result.outcomes,
                  "receipts": [dict(o) for o in result.outcomes],
                  "setup_errors": result.setup_errors,
                  "successful": result.wasSuccessful(), "ran": result.testsRun}
        if mutation == "runner-failure":
            report["receipts"] = [{"id": o["id"], "outcome": "success"}
                                  for o in result.outcomes]
        if mutation == "corrupt-stream":
            print("not JSON")
            return
        print(json.dumps(report))


if __name__ == "__main__":
    probe(json.load(sys.stdin))
