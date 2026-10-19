"""DIET-715 Phase B: RED rows for the runner lifecycle contract.

Every row here states a property of `DietTestRunner`'s orchestration.
Rows marked RED fail against the current runner for the reason named in
their docstring; rows marked CONTROL pass now and must keep passing, so
a GREEN change cannot buy the RED rows by weakening the guard.

Nothing in `runner.py` or the guard is modified by this suite.
"""

from __future__ import annotations

from django.test import SimpleTestCase

from netbox_hedgehog.tests import runner as runner_module
from .runner_lifecycle_support import (
    FakeConnection, FakeConnections, LifecycleRecord, NotObserved,
    observe_setup, require,
)


def reconciliation_error():
    """The contract type, which the RUNNER must own.

    An earlier version asserted against a class defined in this test
    package. A correct fix raising its own runner-side type would have
    left the rows red, so the suite would have rejected the very change
    it exists to require. The row now asks the runner module for the
    type; its absence is the RED cause and defining it is part of GREEN.
    """
    return getattr(runner_module, "UnpreparedTarget", None)

LANE_DB = "netbox"
TEST_DB = "test_netbox"


def lane_only():
    return FakeConnections({"default": FakeConnection("default", LANE_DB)})


def prepared_default():
    return FakeConnections({"default": FakeConnection("default", TEST_DB)})


class DatabaseFreeSelection(SimpleTestCase):
    """Gate item 1: a database-free selection must not reach the guard."""

    def test_r01_empty_aliases_consults_the_guard_for_nothing(self):
        """RED. Django prepared nothing, so the guard has nothing to apply.

        Today the runner loops over every configured alias and asks the
        guard about `default`, which still points at the lane database.
        """
        record = observe_setup(runner_module, lane_only(),
                               aliases=set(), prepared=())
        self.assertEqual(
            record.guard_calls, [],
            f"the guard was consulted for {record.guarded_aliases()} after "
            f"Django prepared nothing")

    def test_r02_empty_aliases_does_not_fail_the_run(self):
        """RED. A legitimate database-free selection must not abort."""
        record = observe_setup(runner_module, lane_only(),
                               aliases=set(), prepared=())
        self.assertIsNone(
            record.failure,
            f"a database-free selection raised {type(record.failure).__name__}: "
            f"{record.failure}")

    def test_r03_empty_aliases_issues_no_alter(self):
        """RED. Zero ALTERs *and* a clean run.

        Asserting only "no ALTER" passes vacuously today: the run raises
        before reaching one, so the absence of an ALTER is caused by the
        failure rather than by correct behaviour. Measured: guarded
        ['default'], RuntimeError. The no-failure clause is what makes
        this row discriminate.
        """
        record = observe_setup(runner_module, lane_only(),
                               aliases=set(), prepared=())
        self.assertEqual(record.altered, [])
        self.assertEqual(record.sql, [])
        self.assertIsNone(
            record.failure,
            "no ALTER was issued only because the run aborted first")

    def test_r04_empty_aliases_is_not_omitted_aliases(self):
        """RED. `aliases={}` and an omitted argument are different.

        Django treats an omitted argument as its default setup. A fix
        that keys off "the set is falsy" would conflate them, so both
        are observed separately.
        """
        # The omitted branch must model a LEGITIMATE default setup: a
        # prepared disposable target. Pointing it at the ordinary lane
        # database made the two branches differ because the omitted one
        # FAILED, which would have been satisfied by the defect rather
        # than by the distinction the row is about.
        explicit = observe_setup(runner_module, lane_only(),
                                 aliases=set(), prepared=())
        omitted = observe_setup(runner_module, prepared_default(),
                                aliases=None, omit_aliases=True,
                                prepared=(("default", LANE_DB, True),))
        # The argument really was passed differently...
        self.assertFalse(explicit.requested_was_omitted)
        self.assertTrue(omitted.requested_was_omitted)
        self.assertEqual(explicit.requested_aliases, set())
        self.assertIsNone(omitted.requested_aliases)
        # ...and the two must produce DIFFERENT behaviour. Asserting
        # only the recorded flags proved the harness passed the
        # argument, not that the runner distinguishes the cases.
        self.assertEqual(
            explicit.guard_calls, [],
            "an explicitly empty alias set still reached the guard")
        # The omitted branch is a healthy default setup: it guards its
        # prepared target and does not fail.
        self.assertIsNone(
            omitted.failure,
            f"the omitted-alias control is not a healthy default setup: "
            f"{omitted.failure}")
        self.assertEqual(omitted.guarded_aliases(), {"default"})
        self.assertNotEqual(
            explicit.guarded_aliases(), omitted.guarded_aliases(),
            "explicit aliases=set() and an omitted argument produced "
            "identical guard behaviour; Django treats the omitted case "
            "as its default setup and they must not be conflated")


class PreparedTargetsOnly(SimpleTestCase):
    """Gate item 2: guard exactly what Django prepared, and nothing else."""

    def test_r05_guard_follows_the_prepared_target(self):
        """CONTROL, non-discriminating today.

        Passes against the current runner because it guards every alias
        and this fixture's only alias is test-named. It does not
        distinguish correct from current behaviour; it exists so a
        GREEN fix cannot buy the RED rows by guarding nothing.
        """
        record = observe_setup(runner_module, prepared_default(),
                               aliases={"default"},
                               prepared=(("default", LANE_DB, True),))
        self.assertIsNone(record.failure, str(record.failure))
        self.assertEqual(record.guarded_aliases(), {"default"})
        self.assertEqual(record.altered[0]["tables"],
                         list(runner_module.GUARDED_TABLES))

    def test_r06_an_unused_ordinary_secondary_alias_is_untouched(self):
        """RED. Dev B's blocker 1: a database-backed selection also fails
        today when another configured alias is simply unused.

        `default` is prepared; `archive` is an ordinary database nothing
        selected. The guard must never be asked about `archive`.
        """
        connections = FakeConnections({
            "default": FakeConnection("default", TEST_DB),
            "archive": FakeConnection("archive", "netbox_archive"),
        })
        record = observe_setup(runner_module, connections,
                               aliases={"default"},
                               prepared=(("default", LANE_DB, True),))
        self.assertNotIn(
            "archive", record.guarded_aliases(),
            "the guard was asked about an ordinary alias the selection "
            "never required")
        self.assertIsNone(record.failure, str(record.failure))

    def test_r07_two_independent_prepared_targets_are_both_guarded(self):
        """CONTROL, non-discriminating today (both aliases test-named).

        Guards against a fix that narrows to a single alias.
        """
        connections = FakeConnections({
            "default": FakeConnection("default", TEST_DB),
            "other": FakeConnection("other", "test_other"),
        })
        record = observe_setup(runner_module, connections,
                               aliases={"default", "other"},
                               prepared=(("default", LANE_DB, True),
                                         ("other", "other", True)))
        self.assertIsNone(record.failure, str(record.failure))
        self.assertEqual(record.guarded_aliases(), {"default", "other"})

    def test_r08_two_aliases_sharing_one_target(self):
        """CONTROL, non-discriminating today.

        A shared physical database reports destroy=False for the
        follower; a fix must not read that as "not prepared".
        """
        connections = FakeConnections({
            "default": FakeConnection("default", TEST_DB),
            "replica": FakeConnection("replica", TEST_DB),
        })
        record = observe_setup(runner_module, connections,
                               aliases={"default", "replica"},
                               prepared=(("default", LANE_DB, True),
                                         ("replica", LANE_DB, False)))
        self.assertIsNone(record.failure, str(record.failure))
        self.assertEqual(record.guarded_aliases(), {"default", "replica"})

    def test_r09_a_valid_mirror_is_not_treated_as_unprepared(self):
        """CONTROL, non-discriminating today.

        Mirrors are configured separately and omitted from the setup
        return, so a fix that treats "absent from the return" as
        "unprepared" would newly fail this. That is its purpose; it
        does not discriminate against the current runner.
        """
        connections = FakeConnections({
            "default": FakeConnection("default", TEST_DB),
            "mirror": FakeConnection("mirror", TEST_DB, mirror="default"),
        })
        record = observe_setup(runner_module, connections,
                               aliases={"default", "mirror"},
                               prepared=(("default", LANE_DB, True),))
        self.assertIsNone(
            record.failure,
            f"a valid mirror was rejected: {record.failure}")


class FailClosedFamilies(SimpleTestCase):
    """Gate item 4: disagreement between intent, setup and routing stops
    the run before bodies, with the original failure attributable."""

    def test_r10_nonempty_intent_with_empty_setup_fails_closed(self):
        """RED. Required aliases but nothing prepared must fail BECAUSE
        intent and setup disagree.

        Today this already fails -- but for the wrong reason: the guard
        trips on the lane database's name. Measured: guarded ['default'],
        RuntimeError "refusing to apply...". A fix that merely stops
        guarding unprepared aliases would turn this into a silent pass,
        which is why the row requires the failure to be attributable to
        reconciliation rather than to the name check.
        """
        record = observe_setup(runner_module, lane_only(),
                               aliases={"default"}, prepared=())
        self.assertIsNotNone(
            record.failure,
            "a selection that required a database but got none continued")
        # POSITIVE attribution against a RUNNER-owned type. Asserting
        # only that the message is not the guard's refusal would be
        # satisfied by any unrelated exception, including a harness bug.
        contract_type = reconciliation_error()
        self.assertIsNotNone(
            contract_type,
            "netbox_hedgehog.tests.runner defines no UnpreparedTarget; "
            "the reconciliation failure has no named, runner-owned type")
        self.assertIsInstance(
            record.failure, contract_type,
            f"expected the named reconciliation failure, got "
            f"{type(record.failure).__name__}: {record.failure}")
        self.assertEqual(sorted(record.failure.aliases), ["default"])

    def test_r10b_the_guard_is_not_consulted_when_setup_was_missing(self):
        """RED. The reconciliation must happen BEFORE the guard."""
        record = observe_setup(runner_module, lane_only(),
                               aliases={"default"}, prepared=())
        self.assertEqual(
            record.guard_calls, [],
            "the guard was consulted about an alias Django never prepared")

    def test_r11_partial_setup_fails_closed(self):
        """Two required aliases, one prepared."""
        connections = FakeConnections({
            "default": FakeConnection("default", TEST_DB),
            "other": FakeConnection("other", "netbox_other"),
        })
        record = observe_setup(runner_module, connections,
                               aliases={"default", "other"},
                               prepared=(("default", LANE_DB, True),))
        self.assertIsNotNone(
            record.failure,
            "a required alias with no prepared target was accepted")
        # Same wrong-reason trap as R10, closed the same way, and
        # against the runner-owned type.
        contract_type = reconciliation_error()
        self.assertIsNotNone(
            contract_type,
            "netbox_hedgehog.tests.runner defines no UnpreparedTarget")
        self.assertIsInstance(
            record.failure, contract_type,
            f"expected the named reconciliation failure, got "
            f"{type(record.failure).__name__}: {record.failure}")
        self.assertEqual(
            sorted(record.failure.aliases), ["other"],
            "the failure must identify exactly the unprepared alias")
        # And it must stop before guarding the alias that WAS prepared,
        # so a later invalid alias is not discovered after ALTERs ran.
        self.assertEqual(
            record.altered, [],
            "tables were altered before the full mapping was validated")

    def test_r12_a_returned_connection_still_on_an_ordinary_db_fails(self):
        """A teardown tuple is not proof of preparation. If the routing
        still points at an ordinary database the run must stop."""
        connections = FakeConnections({
            "default": FakeConnection("default", LANE_DB),
        })
        record = observe_setup(runner_module, connections,
                               aliases={"default"},
                               prepared=(("default", LANE_DB, True),))
        self.assertIsNotNone(
            record.failure,
            "a connection still routed to the ordinary database was guarded")
        self.assertIsInstance(record.failure, RuntimeError)

    def test_r13_a_setup_exception_is_preserved_unchanged(self):
        """The original failure must reach the caller, not a wrapper."""
        original = OSError("could not create test database")
        record = observe_setup(runner_module, lane_only(),
                               aliases={"default"}, prepared=(),
                               setup_raises=original)
        self.assertIs(
            record.failure, original,
            f"the original setup failure was replaced by {record.failure!r}")
        self.assertEqual(record.guard_calls, [],
                         "the guard ran after setup had already failed")

    def test_r14_a_guard_runtime_error_is_preserved(self):
        original = RuntimeError("guard refused")
        record = observe_setup(runner_module, prepared_default(),
                               aliases={"default"},
                               prepared=(("default", LANE_DB, True),),
                               guard_raises=original)
        self.assertIs(record.failure, original)

    def test_r15_a_sql_failure_is_preserved(self):
        original = Exception("connection reset during ALTER")
        record = observe_setup(runner_module, prepared_default(),
                               aliases={"default"},
                               prepared=(("default", LANE_DB, True),),
                               guard_sql_raises=original)
        self.assertIs(record.failure, original)

    def test_r16_refusal_precedes_any_cursor(self):
        """The low-level boundary, exercised through the SHIPPED guard.

        `real_guard=True` calls `apply_autovacuum_guard` itself. An
        earlier version reimplemented the refusal inside the fake and
        asserted against that, which proved only that the fake was
        written correctly. FakeConnection raises if a cursor is ever
        opened, so "refused before any cursor" is observed.
        """
        record = observe_setup(runner_module, lane_only(),
                               aliases={"default"},
                               prepared=(("default", LANE_DB, True),),
                               real_guard=True)
        # The property is "no cursor on an ordinary database, and the
        # run stops" -- NOT "the guard's message appears". Requiring
        # that message would reject a correct fix that validates the
        # routing BEFORE calling the guard, in which case the guard is
        # never reached. The low-level refusal itself is proven
        # separately and directly by C04.
        self.assertIsNotNone(
            record.failure,
            "an ordinary database was accepted as a guard target")
        self.assertNotIsInstance(
            record.failure, AssertionError,
            "a cursor was opened on an ordinary database before refusal")
        self.assertEqual(
            record.altered, [],
            "tables were altered on an ordinary database")


class ObservationIntegrity(SimpleTestCase):
    """Controls on the rows themselves."""

    def test_c01_an_unobserved_record_cannot_be_read_as_evidence(self):
        empty = LifecycleRecord()
        with self.assertRaises(NotObserved):
            require(empty, "failure")

    def test_c02_the_defect_set_is_computed_not_asserted(self):
        record = LifecycleRecord()
        record.setup_returned = [{"alias": "default"}]
        record.guard_calls = [{"alias": "default"}, {"alias": "archive"}]
        self.assertEqual(record.guarded_but_not_prepared(), {"archive"})

    def test_c03_the_guard_constant_is_unchanged(self):
        """DIET-643 scope must not widen to buy a RED row."""
        self.assertEqual(runner_module.GUARDED_TABLES,
                         ("dcim_modulebay", "dcim_module", "dcim_device"))

    def test_c04_the_shipped_guard_refuses_a_normal_database(self):
        """Direct refusal through `apply_autovacuum_guard` itself.

        An earlier version asserted only on the `_is_test_database`
        predicate, which is a different function from the one that
        protects the database.
        """
        from unittest import mock
        conns = FakeConnections({"default": FakeConnection("default", LANE_DB)})
        with mock.patch.object(runner_module, "connections", conns):
            with self.assertRaises(RuntimeError) as caught:
                runner_module.apply_autovacuum_guard("default")
        self.assertIn("refusing to apply", str(caught.exception))
        self.assertNotIsInstance(
            caught.exception, AssertionError,
            "the guard opened a cursor before refusing")

    def test_c05_a_configured_test_name_is_a_valid_disposable_target(self):
        """Not every disposable name begins with `test_`."""
        self.assertTrue(
            runner_module._is_test_database(
                FakeConnection("d", "diet_disposable",
                               test_name="diet_disposable")))
        self.assertFalse(
            runner_module._is_test_database(FakeConnection("d", LANE_DB)))
