"""DIET-643 Phase 2 — scope and safety of the test-harness autovacuum guard.

Gate 2 of the authorised Phase 2: prove the guard is active only in the test
database and only on the three implicated relations.

The timing proof (that the degraded plan disappears) is a measured run recorded
on #643, not an assertion here -- a test that must stall for 30 minutes to fail
would itself be the problem the guard exists to remove.
"""

from django.db import connection
from django.test import TestCase

from netbox_hedgehog.tests.runner import (
    GUARDED_TABLES,
    _is_test_database,
    apply_autovacuum_guard,
)


def _autovacuum_setting(table):
    """Return the per-table autovacuum_enabled reloption, or None if unset."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT reloptions FROM pg_class WHERE relname = %s AND relkind = 'r'",
            [table],
        )
        row = cursor.fetchone()
    if not row or not row[0]:
        return None
    for opt in row[0]:
        if opt.startswith('autovacuum_enabled='):
            return opt.split('=', 1)[1]
    return None


class AutovacuumGuardScopeTestCase(TestCase):
    """The guard must be precisely scoped: three tables, test database only."""

    def test_runs_against_a_test_database(self):
        """Safety precondition for every other assertion in this file."""
        self.assertTrue(
            _is_test_database(connection),
            'DIET test suite must run against a Django test database',
        )

    def test_guard_names_exactly_the_three_implicated_relations(self):
        """Widening this set is not a supported fix (see #643)."""
        self.assertEqual(
            set(GUARDED_TABLES),
            {'dcim_modulebay', 'dcim_module', 'dcim_device'},
        )

    def test_guard_disables_autovacuum_on_guarded_tables(self):
        altered = apply_autovacuum_guard()
        self.assertEqual(set(altered), set(GUARDED_TABLES))
        for table in GUARDED_TABLES:
            self.assertEqual(
                _autovacuum_setting(table), 'false',
                f'{table} must have autovacuum_enabled=false under the guard',
            )

    def test_guard_leaves_other_tables_untouched(self):
        """Scope check: neighbouring DCIM and plugin tables must be unaffected."""
        apply_autovacuum_guard()
        for table in (
            'dcim_cable',
            'dcim_interface',
            'dcim_moduletype',
            'netbox_hedgehog_topologyplan',
            'netbox_hedgehog_planserverconnection',
        ):
            self.assertIsNone(
                _autovacuum_setting(table),
                f'{table} is outside the guarded set and must not be altered',
            )

    def test_guard_refuses_a_non_test_database(self):
        """The guard must never reach a lane or production database."""
        original = connection.settings_dict['NAME']
        configured_test = (connection.settings_dict.get('TEST') or {}).get('NAME')
        try:
            connection.settings_dict['NAME'] = 'netbox_production_lookalike'
            if configured_test:
                connection.settings_dict['TEST'] = dict(
                    connection.settings_dict['TEST'], NAME='something_else'
                )
            with self.assertRaises(RuntimeError) as ctx:
                apply_autovacuum_guard()
            self.assertIn('refusing', str(ctx.exception).lower())
        finally:
            connection.settings_dict['NAME'] = original
            if configured_test:
                connection.settings_dict['TEST'] = dict(
                    connection.settings_dict['TEST'], NAME=configured_test
                )

    def test_guard_is_idempotent(self):
        """Re-applying must not error or change scope."""
        first = apply_autovacuum_guard()
        second = apply_autovacuum_guard()
        self.assertEqual(first, second)
        for table in GUARDED_TABLES:
            self.assertEqual(_autovacuum_setting(table), 'false')
