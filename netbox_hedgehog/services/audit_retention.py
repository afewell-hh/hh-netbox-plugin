"""30-day retention for InterchangeAudit failure records (#689).

#672 approved two halves of the audit policy: a minimal non-secret failure
record, and 30-day retention of it. #684/#685 shipped the first half on the
paste surface; #686 R2 found the second had never been implemented anywhere,
so failure audits accumulate without bound today. This module is the second
half, and nothing more.

Deliberately narrow. It deletes one outcome class and leaves every other
InterchangeAudit row, every other model, and NetBox's own changelog untouched
(#658 owns historical changelog remediation). It makes no claim about #678
upload quarantine or reaper behaviour.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.utils import timezone

from netbox_hedgehog.models.interchange import InterchangeAudit


logger = logging.getLogger("netbox_hedgehog.audit_retention")

#: The approved window (#672). Not a tunable: widening it deletes records no
#: decision authorized removing, so it is a constant here and has no command
#: line switch. Changing it is a policy decision, not an operator action.
RETENTION_DAYS = 30

#: The one outcome ``views.interchange.audit_failure`` writes. Success and
#: lifecycle outcomes (ui-import, ui-edit, ui-delete, download, approve,
#: success, ingress-accepted, idempotent-no-create) are history rather than
#: failure records and are outside this policy.
ELIGIBLE_OUTCOMES = frozenset({"ui-import-failed"})


def retention_cutoff(now=None):
    """The instant before which an eligible record has expired.

    Timezone-aware because ``created`` is; comparing an aware column to a
    naive value would raise, and silently coercing one would move the
    boundary by the server's offset.
    """
    return (now or timezone.now()) - timedelta(days=RETENTION_DAYS)


def eligible_queryset(now=None):
    """Records the policy permits deleting.

    Both filters are load-bearing. ``outcome__in`` keeps non-failure history;
    ``created__lt`` keeps anything inside the window. A record aged exactly to
    the cutoff is not *older* than it and survives -- the boundary is closed
    on the retained side so that "30 days" means at least 30 days.
    """
    return InterchangeAudit.objects.filter(
        outcome__in=ELIGIBLE_OUTCOMES, created__lt=retention_cutoff(now))


def purge_expired_failure_audits(now=None, *, dry_run=False) -> dict:
    """Delete expired failure audits; return an aggregate, non-secret result.

    The result and the log line carry counts and policy values only. Record
    payloads may hold a source location or a stage, and the point of the
    retention rule is that such material stops existing -- copying it into a
    log on the way out would defeat it.

    Deliberately writes no audit row of its own: a per-run record would be a
    non-eligible outcome that nothing ever removes, so the fix for one
    unbounded class would create another.
    """
    queryset = eligible_queryset(now)
    cutoff = retention_cutoff(now)

    if dry_run:
        eligible = queryset.count()
        logger.info(
            "interchange audit retention dry run: %d record(s) eligible, "
            "retention_days=%d, cutoff=%s", eligible, RETENTION_DAYS, cutoff.isoformat())
        return {"deleted": 0, "eligible": eligible, "dry_run": True,
                "retention_days": RETENTION_DAYS, "cutoff": cutoff.isoformat()}

    # delete() returns (total, {label: count}); with no cascades from this
    # model the total is the row count. Take it from the call rather than a
    # prior count() so the number reported is the number actually removed.
    deleted, _by_model = queryset.delete()
    logger.info(
        "interchange audit retention purge: %d record(s) deleted, "
        "retention_days=%d, cutoff=%s", deleted, RETENTION_DAYS, cutoff.isoformat())
    return {"deleted": deleted, "eligible": deleted, "dry_run": False,
            "retention_days": RETENTION_DAYS, "cutoff": cutoff.isoformat()}
