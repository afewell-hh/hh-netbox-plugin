"""Sound stand-in for the prerequisite-decision seam. Test-only.

Deliberately limited: this adapter proves the fixture's *plumbing* — that a
selector shape reaches the seam, with the module it claims — and nothing
more. It does not refuse, does not emit the contract's exit code, and does
not emit its diagnostic.

That limitation is the point. If a stand-in could satisfy the selector rows,
those rows would be measuring the stand-in rather than the mechanism under
test, which is how the previous fixture ended up unsatisfiable in the
opposite direction: it failed for a reason no implementation could change.
Here the rows stay RED until something real supplies the refusal, while the
plumbing itself becomes verifiable today.
"""

from __future__ import annotations

import json
import os
from pathlib import Path


LEDGER_VARIABLE = "HH711_SEAM_LEDGER"


def record_only(module: str) -> None:
    """Record that the seam was reached for `module`, then return normally.

    Returning normally is deliberate: the protected fixture proceeds, its
    bodies run, and any row demanding a refusal still fails. Plumbing is
    observable; the contract is not simulated.
    """
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
    entries.append({"module": module, "pid": os.getpid()})
    path.write_text(json.dumps(entries), encoding="utf-8")
