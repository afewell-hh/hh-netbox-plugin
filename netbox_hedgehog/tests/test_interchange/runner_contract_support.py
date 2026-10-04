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
import os
import subprocess
import sys
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

    @property
    def combined(self) -> str:
        return f"{self.stdout}\n{self.stderr}"

    @property
    def reported_a_test_result(self) -> bool:
        """True if unittest printed a result line -- i.e. bodies were reached.

        Checked instead of 'ok' counts because verbosity can hide those, and a
        refusal must happen before any result line exists at all.
        """
        return "Ran " in self.combined and " test" in self.combined

    def wrote(self, marker: Path) -> bool:
        return marker.exists()


def manage_py() -> Path:
    return Path(sys.executable).parent.parent / "netbox" / "manage.py"


def raw_django(*labels: str, extra: tuple[str, ...] = (), env: dict | None = None,
               timeout: int = 300) -> RunOutcome:
    """Run `manage.py test` in a genuinely fresh process.

    Fresh because the import hook under contract can only fire once per
    interpreter; an in-process check would pass or fail for reasons unrelated
    to the behaviour being claimed.
    """
    argv = [sys.executable, "manage.py", "test", *labels, "--keepdb", *extra]
    environment = dict(os.environ)
    environment.pop("HNP_TEST_CHECKOUT_ROOT", None)
    environment.pop("HNP_TEST_LOCAL_CHECKOUT_ROOT", None)
    environment.pop("HNP_REAPER_CONTAINER_EVIDENCE", None)
    if env:
        environment.update(env)
    def _text(value):
        if isinstance(value, bytes):
            return value.decode(errors="replace")
        return value or ""

    try:
        done = subprocess.run(argv, capture_output=True, text=True, timeout=timeout,
                              cwd=str(Path(__file__).resolve().parents[3]),
                              env=environment)
    except subprocess.TimeoutExpired as expired:
        return RunOutcome(tuple(argv), -1, _text(expired.stdout),
                          _text(expired.stderr), timed_out=True)
    return RunOutcome(tuple(argv), done.returncode, done.stdout, done.stderr)


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
    environment.pop("HNP_TEST_CHECKOUT_ROOT", None)
    environment.pop("HNP_TEST_LOCAL_CHECKOUT_ROOT", None)
    environment.pop("HNP_REAPER_CONTAINER_EVIDENCE", None)
    if env:
        environment.update(env)
    done = subprocess.run([sys.executable, "-c", code], capture_output=True,
                          text=True, timeout=timeout, env=environment)
    return RunOutcome((sys.executable, "-c", f"import {module}"),
                      done.returncode, done.stdout, done.stderr)


@dataclass(frozen=True)
class ContractRow:
    identifier: str
    method: str
    claim: str
    area: str
