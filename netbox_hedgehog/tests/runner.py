"""DIET test harness runner (DIET-643 Phase 2).

Why this exists
---------------
Django ``TestCase`` wraps each class in a transaction that is rolled back at
``tearDownClass``. When a DIET class that generates the 128-GPU case rolls back,
it leaves dead tuples behind, and autovacuum then runs against the now-empty
tables. Autovacuum writes ``pg_class`` statistics *outside* the test transaction,
so those writes survive the rollback:

    dcim_modulebay  reltuples=0  relpages=67

The next class generates thousands of rows that are visible only to its own
connection, while the planner still reads ``reltuples=0`` over non-zero
``relpages``. Row estimates collapse to 1, and NetBox's own ``ModuleBay.save()``
query -- issued ~3,416 times per generation and returning zero rows every time --
flips from a hash join to a nested loop. Measured: 13.9 s per execution with
4.4M buffer hits, degrading 5.1 s -> 86.9 s. At that repetition count the suite
appears to hang.

The predecessor's *rows* do not survive; only autovacuum's statistics do. This
runner therefore disables autovacuum for the three implicated relations in the
**disposable test database only**, which prevents the empty-table statistics from
being written in the first place.

Deliberately NOT done here: no change to product generation, MPTT maintenance,
custom-field caching, transaction semantics, generated inventory, or any
production database. See #643 for the full measurement record.

Usage::

    python manage.py test netbox_hedgehog.tests.test_topology_planning \
        --testrunner=netbox_hedgehog.tests.runner.DietTestRunner
"""

import logging

from django.db import connections
from django.test.runner import DiscoverRunner

logger = logging.getLogger('netbox_hedgehog.tests.runner')

#: Only these relations are touched. Widening this set is not a supported fix --
#: if the guard proves insufficient, stop and re-measure rather than adding tables.
GUARDED_TABLES = ('dcim_modulebay', 'dcim_module', 'dcim_device')


def _is_test_database(conn) -> bool:
    """True only for a Django-created test database.

    Django prefixes test databases with TEST['NAME'] or 'test_'. We refuse to
    alter anything else: this guard must never reach a lane or production DB.
    """
    name = conn.settings_dict.get('NAME') or ''
    configured_test_name = (conn.settings_dict.get('TEST') or {}).get('NAME')
    if configured_test_name and name == configured_test_name:
        return True
    return name.startswith('test_')


def apply_autovacuum_guard(alias: str = 'default') -> list:
    """Disable autovacuum for the guarded relations on a test database.

    Returns the list of tables actually altered. Refuses, loudly, if the target
    is not a test database.
    """
    conn = connections[alias]
    if not _is_test_database(conn):
        raise RuntimeError(
            f"refusing to apply the DIET-643 autovacuum guard to non-test database "
            f"{conn.settings_dict.get('NAME')!r}; this guard is for disposable test "
            f"databases only"
        )

    altered = []
    with conn.cursor() as cursor:
        for table in GUARDED_TABLES:
            cursor.execute(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = current_schema() AND table_name = %s",
                [table],
            )
            if cursor.fetchone() is None:
                logger.warning('DIET-643 guard: table %s absent; skipping', table)
                continue
            # Identifiers are from the module-level constant, never user input.
            cursor.execute(f'ALTER TABLE "{table}" SET (autovacuum_enabled = false)')
            altered.append(table)

    logger.info('DIET-643 guard applied on %s: %s', conn.settings_dict.get('NAME'), altered)
    return altered


class DietTestRunner(DiscoverRunner):
    """DiscoverRunner that installs the DIET-643 autovacuum guard.

    The guard is applied after the test database exists and before any test
    runs, so no class can leave empty-table statistics for its successor.
    """

    def setup_databases(self, **kwargs):
        config = super().setup_databases(**kwargs)
        for alias in connections:
            try:
                altered = apply_autovacuum_guard(alias)
            except RuntimeError as exc:
                # A non-test alias is a configuration problem worth surfacing,
                # not a reason to silently continue.
                raise
            if altered and self.verbosity >= 1:
                print(f'DIET-643: autovacuum disabled on {alias} for {", ".join(altered)}')
        return config
