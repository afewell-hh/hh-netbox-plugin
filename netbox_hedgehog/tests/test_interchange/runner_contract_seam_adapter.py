"""Sound stand-in for the prerequisite-decision boundary. Test-only.

Implements the boundary's input/output contract so the fixture's plumbing is
verifiable today: it receives the full request -- child invocation,
normalized requested selection, evidence context, protected module -- and
returns a structured decision.

Deliberately limited: it always ALLOWS. It never refuses, never emits an
exit code, never emits the contract's diagnostic. So a healthy child runs to
completion, and every row demanding a refusal still fails. A stand-in that
could satisfy those rows would mean the rows were measuring the stand-in.

A second emitter below exists only to be rejected: it fakes a refusal by
inventing a private exit code, and the mutation control requires binding and
decision validation to catch it.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path


LEDGER_VARIABLE = "HH711_SEAM_LEDGER"


@dataclass(frozen=True)
class PrerequisiteDecision:
    """What a boundary returns. The fixture applies this and nothing else."""

    allow: bool
    exit_code: int | None = None
    diagnostic: str | None = None
    #: Echoes the invocation the request carried, so a consumer can bind the
    #: decision to the run that produced it rather than trusting that some
    #: decision happened.
    invocation: str = ""
    #: The selection as the boundary normalized it -- labels only, options
    #: and their values removed. Without this every selector shape writes an
    #: indistinguishable record.
    normalized_selection: tuple = ()


OPTIONS_WITH_VALUES = ("--exclude-tag", "--tag", "--parallel", "--settings",
                       "--pythonpath", "--testrunner", "-k")


def normalize_selection(argv) -> tuple:
    labels, skip = [], False
    for argument in argv:
        if skip:
            skip = False
            continue
        if argument in OPTIONS_WITH_VALUES:
            skip = True
            continue
        if argument.startswith("-"):
            continue
        labels.append(argument)
    return tuple(labels)


def _append(entry: dict) -> None:
    ledger = os.environ.get(LEDGER_VARIABLE)
    if not ledger:
        return
    path = Path(ledger)
    entries = []
    if path.exists():
        try:
            entries = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            entries = []
    entries.append(entry)
    path.write_text(json.dumps(entries), encoding="utf-8")


def sound_decision(request: dict) -> PrerequisiteDecision:
    """Allow, and record the full bound request."""
    decision = PrerequisiteDecision(
        allow=True,
        invocation=request.get("invocation", ""),
        normalized_selection=normalize_selection(request.get("selection") or ()),
    )
    _append({"request": request, "decision": asdict(decision)})
    return decision


def unbound_emitter(request: dict) -> PrerequisiteDecision:
    """Mutation target: refuses without binding anything.

    Exists so a control can prove the row rejects a boundary that invents a
    refusal from a private source instead of returning a bound decision. It
    carries no invocation and no normalized selection.
    """
    decision = PrerequisiteDecision(
        allow=False,
        exit_code=int(os.environ.get("HH711_FAKE_EXIT", "9")),
        diagnostic="fabricated refusal from a private source",
    )
    _append({"request": {"module": request.get("module")},
             "decision": asdict(decision)})
    return decision
