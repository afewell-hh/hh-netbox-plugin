"""RED-phase support: how these tests fail while the feature is absent.

Acceptance gate 1 of #673 requires the suite to be RED *solely because the
feature is absent*. Two things make that demonstrable:

* the absence is raised as an ``AssertionError`` subclass, so unittest reports
  FAIL rather than ERROR and the reason is the first line of the message; and
* it is raised from inside each test rather than at module import, so one
  missing module cannot mask the rest of the suite or hide an unrelated break.

The seam named below is the RED suite's assumed entry point, not an
implementation selection. #672 deliberately does not choose serializer classes,
URL names, or a REST-versus-UI sequence. GREEN may rename these, in which case
this module changes and the contract assertions do not.
"""

from __future__ import annotations

import importlib

PRODUCTION_MODULE = "netbox_hedgehog.interchange"

#: Entry points the contract tests exercise.
#:   decode_document(text, *, media_type=None, filename=None) -> dict
#:   import_bundle(document, *, user) -> result with .design_revision /
#:       .catalog_version / .created / .idempotent
#:   export_revision(revision, *, fmt) -> str
EXPECTED_ENTRY_POINTS = ("decode_document", "import_bundle", "export_revision")


class FeatureAbsent(AssertionError):
    """The production interchange feature does not exist yet."""


def require_interchange():
    """Return the production interchange module, or fail RED with the reason."""
    try:
        module = importlib.import_module(PRODUCTION_MODULE)
    except ImportError as exc:
        raise FeatureAbsent(
            f"production interchange API absent: {PRODUCTION_MODULE} "
            f"({exc}). This test is RED because the feature is not implemented, "
            f"not because a contract was weakened.") from None
    missing = [name for name in EXPECTED_ENTRY_POINTS if not hasattr(module, name)]
    if missing:
        raise FeatureAbsent(
            f"{PRODUCTION_MODULE} is missing entry points: {missing}")
    return module


def require_entry_point(name: str):
    return getattr(require_interchange(), name)
