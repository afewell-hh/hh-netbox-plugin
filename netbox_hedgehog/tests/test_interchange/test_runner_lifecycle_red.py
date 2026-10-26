"""DIET-715 Phase B: RED rows for the runner lifecycle contract.

Every row here states a property of `DietTestRunner`'s orchestration.
Rows marked RED fail against the current runner for the reason named in
their docstring; rows marked CONTROL pass now and must keep passing, so
a GREEN change cannot buy the RED rows by weakening the guard.

Nothing in `runner.py` or the guard is modified by this suite.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from django.test import SimpleTestCase

from netbox_hedgehog.tests import runner as runner_module
from .runner_lifecycle_support import (
    CASE_ALL_DATABASES, CASE_DB, CASE_SIMPLE, CASE_SIMPLE_WITH_DB,
    FakeConnection, FakeConnections, LifecycleRecord, NotObserved,
    observe_setup, require, run_supported_runner,
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


def tearDownModule():
    """Deterministic disposal of derived-identity child databases.

    Verified necessary: atexit alone left the database on the server.

    A failure here RAISES. Recording a failure and returning quietly
    reproduces the original defect in a new place: the run goes green,
    the database stays on the shared server, and nobody learns until
    someone lists pg_database by hand. An orphan is a real leak on
    shared infrastructure and must be loud.
    """
    from . import runner_lifecycle_support as support
    results = support.dispose_registered_children()
    failed = [name for name, ok in results if not ok]
    if failed or support.DISPOSAL_FAILURES:
        raise AssertionError(
            f"child database disposal failed: {failed}; "
            f"details={support.DISPOSAL_FAILURES}")


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


class SupportedRunnerSubprocess(SimpleTestCase):
    """Real subprocess execution of the runner the wrapper selects.

    Scope: these spawn `manage.py test <label>
    --testrunner=DietTestRunner`, which is the runner selection
    `run_diet_tests.sh` makes. They are NOT the full wrapper path,
    which adds compose exec and reaper-evidence preparation; that
    remains a declared gap.
    """

    def test_w01_database_free_selection_runs_bodies_through_the_runner(self):
        """RED. The availability defect, end to end.

        Measured against the current runner: rc=1, zero bodies, no test
        database created, guard refused. This is the observation rows'
        conclusion reproduced in a real subprocess with real bodies.
        """
        result = run_supported_runner([CASE_SIMPLE])
        self.assertEqual(
            result["returncode"], 0,
            f"a database-free selection failed: "
            f"{result['stderr'].strip().splitlines()[-1:] }")
        self.assertEqual(result["body_names"], ["database_free"],
                         "the body did not execute")
        self.assertFalse(result["created_test_database"],
                         "a test database was created for a selection "
                         "that needs none")
        self.assertFalse(result["guard_applied"],
                         "the guard ran for a selection with no database")

    def test_w00_the_child_uses_its_own_database_not_the_outer_one(self):
        """Isolation, observed from the child's own receipts.

        --keepdb previously made the child REUSE the outer run's
        disposable database. Asserting the harness writes a settings
        module would only prove the harness wrote a file; this reads
        the database name the child body actually connected to.
        """
        result = run_supported_runner([CASE_DB])
        self.assertEqual(result["returncode"], 0, result["stderr"][-400:])
        self.assertTrue(result["server_db_names"],
                        "no body reported a server-confirmed database")
        for names in result["server_db_names"]:
            observed = names.get("default")
            # SERVER-CONFIRMED via current_database(). The configured
            # settings value only records what was requested; it would
            # not notice a connection attached elsewhere.
            self.assertEqual(
                observed, result["child_test_database"],
                f"the child was attached to {observed!r}, not its own "
                f"{result['child_test_database']!r}")
            self.assertNotEqual(observed, LANE_DB)
            self.assertNotEqual(
                observed, TEST_DB,
                "the child borrowed the outer run's disposable database")

    def test_w00b_the_child_database_is_lane_scoped_and_retained(self):
        """Retention is deliberate, declared and lane-scoped.

        The child database is kept between rows on purpose -- reuse is
        what took this suite from a 20-minute timeout kill to minutes.
        A single global name would collide between concurrent lanes on
        a shared server, so the name carries the lane.
        """
        result = run_supported_runner([CASE_DB])
        self.assertEqual(result["returncode"], 0, result["stderr"][-400:])
        # Retention is a PROPERTY OF THE IDENTITY, not a constant. An
        # explicit lane is stable, so its database is reused and kept.
        # A derived container id changes every run, so keeping it would
        # orphan one database per run. Asserting True unconditionally
        # contradicted the CI fallback and would have failed the
        # required job.
        expected_retention = result["child_lane_source"] != "container-id"
        self.assertEqual(
            result["child_database_retained"], expected_retention,
            f"retention {result['child_database_retained']} does not "
            f"match identity source {result['child_lane_source']!r}")
        if not expected_retention:
            self.assertTrue(
                result["child_disposal_registered"],
                "a non-retained database declared non-retention but "
                "nothing was arranged to remove it")
        self.assertIn(
            "child_database_retained", result,
            "retention must be declared explicitly, not left implicit")
        self.assertTrue(
            result["child_test_database"].startswith("test_hh715_"),
            result["child_test_database"])
        self.assertIn(
            "".join(c if c.isalnum() else "_"
                    for c in result["child_lane"])[:24],
            result["child_test_database"],
            "the child database name is not lane-scoped, so two lanes "
            "on one server would collide")
        # A digest over the FULL lane, so two lanes agreeing in their
        # readable prefix still get different databases. Truncation
        # alone permitted exactly that collision.
        import hashlib as _h
        self.assertTrue(
            result["child_test_database"].endswith(
                _h.sha256(result["child_lane"].encode()).hexdigest()[:10]),
            f"no full-lane fingerprint in "
            f"{result['child_test_database']!r}; long lane names could "
            f"collide after truncation")
        self.assertNotIn(
            result["child_test_database"], (LANE_DB, TEST_DB),
            "the child target collides with a database it must not own")

    def test_w00c_missing_lane_identity_fails_closed(self):
        """No shared default, still -- but the reachable case changed.

        I wrote this row when identity came only from the environment.
        Adding the container-id fallback (required, or CI fails closed)
        made "no env vars" a RESOLVABLE case, so the old form asserted
        a refusal that can no longer happen. Left alone it would have
        been a permanently red row blamed on the runner. The genuine
        unidentified case is now: no env lane AND no container id.
        """
        from unittest import mock
        from . import runner_lifecycle_support as support
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("COMPOSE_PROJECT_NAME", None)
            os.environ.pop("HH715_LANE", None)
            with mock.patch.object(support.socket, "gethostname",
                                   return_value=""):
                lane, source, retained = support._resolve_lane()
                self.assertIsNone(
                    lane,
                    "with no env lane and no container id there is no "
                    "identity, and sharing one database is exactly "
                    "what must not happen")
                with self.assertRaises(RuntimeError) as caught:
                    support.run_supported_runner([CASE_DB])
        self.assertIn("no lane identity", str(caught.exception))

    def test_w00d_the_identity_chain_is_satisfiable_inside_ci(self):
        """REGRESSION CONTROL for a break I introduced.

        Making identity mandatory is right, but the required CI job runs
        these rows via `docker compose exec`, which passes neither the
        runner environment nor the Compose project into the container.
        Measured inside a CI-shaped container: COMPOSE_PROJECT_NAME,
        HH715_LANE and GITHUB_RUN_ID are ALL unset. An env-var-only
        requirement therefore fails the required job closed.
        """
        from .runner_lifecycle_support import _resolve_lane
        import os as _os
        from unittest import mock
        with mock.patch.dict(_os.environ, {}, clear=False):
            for var in ("COMPOSE_PROJECT_NAME", "HH715_LANE",
                        "GITHUB_RUN_ID"):
                _os.environ.pop(var, None)
            lane, source, retained = _resolve_lane()
        self.assertTrue(
            lane,
            "with no identity variables -- exactly the CI container -- "
            "the rows cannot resolve a lane and the required job fails")
        self.assertEqual(source, "container-id")
        self.assertFalse(
            retained,
            "a per-run derived identity must not retain its database, "
            "or CI orphans one database per run")

    def test_w00e_an_explicit_lane_is_still_preferred_and_retained(self):
        """The derived fallback must not mask an explicit lane."""
        from .runner_lifecycle_support import _resolve_lane
        import os as _os
        from unittest import mock
        with mock.patch.dict(_os.environ,
                             {"COMPOSE_PROJECT_NAME": "diet715devA"}):
            lane, source, retained = _resolve_lane()
        self.assertEqual((lane, source, retained),
                         ("diet715devA", "COMPOSE_PROJECT_NAME", True))

    def test_w00f_a_child_colliding_with_the_outer_target_is_refused(self):
        """PRE-SPAWN. The check must fire before anything is created:
        afterwards the damage -- dropping its own parent -- is done."""
        from .runner_lifecycle_support import (
            _assert_child_target_is_safe, _outer_server_database)
        outer = _outer_server_database()
        self.assertTrue(outer, "no server-confirmed outer database")
        with self.assertRaises(RuntimeError) as caught:
            _assert_child_target_is_safe(outer, "anylane")
        self.assertIn("its own parent", str(caught.exception))
        for reserved in ("netbox", "test_netbox"):
            with self.assertRaises(RuntimeError):
                _assert_child_target_is_safe(reserved, "anylane")

    def test_w00g_a_second_run_in_one_lane_is_refused_not_queued(self):
        """Same-lane exclusivity, enforced by the server.

        Queueing would hide the collision instead of reporting it, so
        the second holder must be REFUSED while the first still holds.
        """
        from .runner_lifecycle_support import _same_lane_exclusivity
        with _same_lane_exclusivity("lane-under-test"):
            with self.assertRaises(RuntimeError) as caught:
                with _same_lane_exclusivity("lane-under-test"):
                    pass
            self.assertIn("already running", str(caught.exception))
        # released: the same lane is usable again afterwards
        with _same_lane_exclusivity("lane-under-test"):
            pass

    def test_w00h_declared_non_retention_is_acted_on(self):
        """Declaring non-retention is not the same as doing it.

        The child runs with --keepdb so rows reuse one database rather
        than rebuilding per row. Under a derived identity that leaves
        the database behind every run, so the result said
        `retained: False` while the database survived -- a false
        declaration. Disposal must be really arranged.
        """
        from .runner_lifecycle_support import (
            _arrange_child_disposal, _DROP_REGISTERED, _resolve_lane,
            _admin_connection, child_database_absent, _database_ownership,
            child_database_exists,
            dispose_child_databases, DISPOSAL_FAILURES)
        # Registration is not removal. The earlier form asserted only
        # that a handler had been registered; measured on the server, a
        # registered handler still left the database behind. This
        # creates a real database and requires the server to confirm it
        # is gone.
        # Lane- AND pid-scoped. A global probe name is shared state:
        # two lanes running this row at once would drop each other's
        # probe, which is the collision class this file exists to
        # prevent, reintroduced by its own control.
        lane, _source, _retained = _resolve_lane()
        probe = (f"test_hh715_probe_"
                 f"{hashlib.sha256(lane.encode()).hexdigest()[:8]}_"
                 f"{os.getpid()}")
        # Created under the claim, so the probe cannot be made or
        # destroyed while another holder owns that name.
        # The probe takes the claim BEFORE touching the name and
        # refuses a pre-existing target rather than dropping it, so it
        # cannot delete someone else's database sharing that name.
        # create_probe_database, NOT owned_probe_database: the claim
        # must be RELEASED before the disposal below, because
        # _database_ownership opens a fresh session per call. Holding
        # it here made the row's own disposal decline as a non-owner.
        from .runner_lifecycle_support import create_probe_database
        before = set(_DROP_REGISTERED)
        create_probe_database(probe)
        try:
            self.assertFalse(child_database_absent(probe))
            # Dispose THIS probe explicitly. The registry-draining form
            # would clear pending real entries too, so genuine child
            # databases from actual spawns would never be disposed at
            # module teardown -- the control causing the leak.
            self.assertEqual(dispose_child_databases([probe]),
                             [(probe, True)])
            self.assertEqual(
                set(_DROP_REGISTERED), before,
                "the control mutated the real disposal registry")
        finally:
            # The obligation must survive an EARLY failure. If an
            # assertion above fails before disposal runs, the probe
            # database still exists and nothing has recorded it.
            # Dispose here, and leave any genuine failure RECORDED:
            # the previous blanket filter stripped every entry for
            # this name, so a real cleanup failure was erased and the
            # row could pass while leaving an orphan behind.
            if child_database_exists(probe):
                dispose_child_databases([probe])
        # Confirmed absence only: child_database_absent RAISES when the
        # server cannot be asked, so an unreachable server can no
        # longer read as a successfully removed database.
        self.assertTrue(
            child_database_absent(probe),
            f"{probe} survived disposal; a declared non-retention that "
            f"does not remove the database is a false declaration")
        self.assertEqual(
            [f for f in DISPOSAL_FAILURES if probe in f[0]], [],
            "disposal reported errors for the probe")
        # NOT atexit.unregister(_drop_child_database): that removes
        # EVERY registration of the function, including the real lane
        # disposal. Locally the lane is explicit and retained, so none
        # exists and the row passes; in CI the fallback registers a
        # real one and this control would have unregistered it --
        # causing the orphaned database it exists to prevent, in the
        # only environment that suffers it. The probe registration is
        # harmless: the drop is IF EXISTS on a name never created.
        # Lane- and pid-scoped, like the first probe. The global name
        # was registered into the SHARED registry and armed a backstop
        # for it, so two lanes running this row would register and
        # then drop each other's name.
        name = f"{probe}_reg"
        _DROP_REGISTERED.discard(name)
        self.assertTrue(
            _arrange_child_disposal(name, retained=False),
            "no disposal was arranged for a non-retained database")
        self.assertIn(name, _DROP_REGISTERED)
        # idempotent: one registration per name, not one per row
        self.assertFalse(_arrange_child_disposal(name, retained=False))
        _DROP_REGISTERED.discard(name)
        # an explicit lane keeps its database, so nothing is arranged
        self.assertFalse(
            _arrange_child_disposal("test_hh715_explicit", retained=True))

    def test_w00j_disposal_declines_a_database_it_does_not_own(self):
        """Cleanup without ownership is a cross-holder hazard.

        _drop_child_database runs pg_terminate_backend before DROP, so
        disposing a database another process is mid-run against would
        kill its sessions. A non-owner must DECLINE and record it,
        not act.
        """
        from .runner_lifecycle_support import (
            _admin_connection, _database_ownership, dispose_child_databases,
            child_database_exists, DISPOSAL_FAILURES, _resolve_lane,
            owned_probe_database)
        lane, _s, _r = _resolve_lane()
        name = (f"test_hh715_owned_"
                f"{hashlib.sha256(lane.encode()).hexdigest()[:8]}_"
                f"{os.getpid()}")
        # Created under its claim, and never over a pre-existing
        # database: owned_probe_database refuses rather than clearing
        # a name that already exists.
        try:
            with owned_probe_database(name):
                # The claim is held for the whole attempt, so the
                # disposal below is the non-owner.
                results = dispose_child_databases([name])
                self.assertEqual(results, [(name, False)],
                                 "disposal acted without holding the claim")
                self.assertTrue(
                    child_database_exists(name),
                    "a database owned by another holder was dropped")
                self.assertTrue(
                    any(name == n and "not owned" in why
                        for n, why in DISPOSAL_FAILURES),
                    "the declined disposal was not recorded")
        finally:
            # Remove ONLY the entry this row deliberately caused. The
            # blanket filter also erased unexpected failures, so a
            # genuine drop failure disappeared and the row passed with
            # an orphan on the server.
            expected = (name, "not owned by this process")
            if expected in DISPOSAL_FAILURES:
                DISPOSAL_FAILURES.remove(expected)
            unexpected = [f for f in DISPOSAL_FAILURES if f[0] == name]
            # Whatever happened, the probe must not survive.
            if child_database_exists(name):
                dispose_child_databases([name])
            self.assertEqual(
                unexpected, [],
                f"an unexpected cleanup failure for {name} was about "
                f"to be erased: {unexpected}")

    def test_w00k_running_and_disposing_take_the_same_claim(self):
        """Execution and disposal must INTERLOCK.

        They previously keyed on different things -- the lane for
        running, the database name for dropping -- so a disposal could
        take its own lock and drop the database while a child run held
        the lane lock and was actively using it. One key, or no
        protection at all.
        """
        from .runner_lifecycle_support import (
            _same_lane_exclusivity, _database_ownership, _child_db_name)
        lane = f"interlock-{os.getpid()}"
        name = _child_db_name(lane)
        # While a run holds the lane, the disposal claim is unavailable.
        with _same_lane_exclusivity(lane):
            with _database_ownership(name) as owned:
                self.assertFalse(
                    owned,
                    "disposal could claim the database while a child "
                    "run held the lane")
        # Released afterwards.
        with _database_ownership(name) as owned:
            self.assertTrue(owned)

    def test_w00l_the_atexit_backstop_is_owned_and_self_disarming(self):
        """The backstop registered _drop_child_database(name) per name:
        it bypassed ownership, and stayed armed after a successful
        disposal, so at exit it could drop a database a DIFFERENT
        process had since created under the same name."""
        from unittest import mock
        from . import runner_lifecycle_support as support
        name = (f"test_hh715_backstop_"
                f"{hashlib.sha256(str(os.getpid()).encode()).hexdigest()[:8]}")
        # ISOLATE, without draining. Under a derived identity the real
        # registry holds the live child database from actual spawns, so
        # asserting the backstop is a no-op against the SHARED registry
        # is only true when the lane is explicit and retained. Saving
        # and restoring keeps the real pending entries intact -- the
        # registry must not be drained by a control.
        saved = set(support._DROP_REGISTERED)
        try:
            support._DROP_REGISTERED.clear()
            # Created under the claim, which is then RELEASED: the
            # disposal below must acquire it itself, as a real one
            # would. Holding it here would make disposal decline as a
            # non-owner and the row would prove nothing.
            support.create_probe_database(name)
            support._arrange_child_disposal(name, retained=False)
            self.assertIn(name, support._DROP_REGISTERED)
            # Armed: a pending name goes through the OWNED path.
            with mock.patch.object(support,
                                   "dispose_child_databases") as disp:
                support._atexit_backstop()
                disp.assert_called_once_with([name])
            # DISARMED BY REAL DISPOSAL, not by a manual discard.
            # Clearing the entry by hand asserts the bookkeeping I
            # wrote rather than the behaviour: it would pass even if
            # disposal never cleared the registry at all.
            results = support.dispose_registered_children()
            self.assertEqual(results, [(name, True)])
            self.assertTrue(support.child_database_absent(name))
            self.assertNotIn(
                name, support._DROP_REGISTERED,
                "successful disposal did not clear the registry, so "
                "nothing disarms the backstop")
            with mock.patch.object(support,
                                   "dispose_child_databases") as disp:
                support._atexit_backstop()
                disp.assert_not_called()
        finally:
            # Restore the saved entries WITHOUT discarding anything
            # registered during the row. The previous form replaced the
            # registry with `saved` alone, so an early failure between
            # registration and disposal silently dropped the pending
            # obligation and orphaned its database.
            still_pending = set(support._DROP_REGISTERED)
            support._DROP_REGISTERED.clear()
            support._DROP_REGISTERED.update(saved | still_pending)
        self.assertEqual(
            support._DROP_REGISTERED, saved,
            "the control altered the real disposal registry")

    def test_w00m_an_early_failure_keeps_the_cleanup_obligation(self):
        """Failure paths, not just the happy path.

        Two ways a row can leave an orphan while reporting success:
        it loses the pending registration when it fails partway, or it
        erases a genuine cleanup failure along with an expected one.
        Both are simulated here against the real helpers.
        """
        from . import runner_lifecycle_support as support
        name = (f"test_hh715_oblig_"
                f"{hashlib.sha256(str(os.getpid()).encode()).hexdigest()[:8]}")
        saved = set(support._DROP_REGISTERED)
        try:
            support._DROP_REGISTERED.clear()
            support.create_probe_database(name)
            support._arrange_child_disposal(name, retained=False)
            # An early failure strikes HERE, before disposal runs.
            still_pending = set(support._DROP_REGISTERED)
            self.assertIn(
                name, still_pending,
                "the obligation was lost before disposal could run")
            # The restore must union, not replace: replacing with the
            # saved set alone discards this pending name.
            merged = saved | still_pending
            self.assertIn(name, merged,
                          "restoring the registry dropped a pending name")
            # And a genuine failure must not be strippable as though
            # it were the expected one.
            support.DISPOSAL_FAILURES.append((name, "disk on fire"))
            expected = (name, "not owned by this process")
            self.assertNotIn(
                expected, support.DISPOSAL_FAILURES,
                "the expected entry is not what was recorded")
            leftover = [f for f in support.DISPOSAL_FAILURES
                        if f[0] == name and f != expected]
            self.assertEqual(
                leftover, [(name, "disk on fire")],
                "a genuine cleanup failure would have been erased")
        finally:
            support.DISPOSAL_FAILURES[:] = [
                f for f in support.DISPOSAL_FAILURES
                if f != (name, "disk on fire")]
            if support.child_database_exists(name):
                support.dispose_child_databases([name])
            support._DROP_REGISTERED.clear()
            support._DROP_REGISTERED.update(saved)

    def test_w00i_an_unobservable_outer_database_refuses_to_spawn(self):
        """FAIL CLOSED. Returning None let the caller's `if outer and ...`
        skip the collision check and spawn anyway -- waving through the
        exact case where the check matters most."""
        from unittest import mock
        from . import runner_lifecycle_support as support
        with mock.patch.object(
                support, "_admin_connection",
                side_effect=OSError("server unreachable")):
            with self.assertRaises(support.OuterDatabaseUnobservable):
                support._outer_server_database(required=True)
            with self.assertRaises(support.OuterDatabaseUnobservable):
                support._assert_child_target_is_safe(
                    "test_hh715_anything", "anylane")
            self.assertIsNone(support._outer_server_database())

    def test_w02_database_backed_selection_still_works(self):
        """CONTROL. Must keep passing: the DIET-643 protection path."""
        result = run_supported_runner([CASE_DB])
        self.assertEqual(result["returncode"], 0, result["stderr"][-400:])
        self.assertEqual(result["body_names"], ["database_backed"])
        self.assertTrue(result["created_test_database"])
        self.assertTrue(result["guard_applied"],
                        "the guard did not run for a database-backed "
                        "selection; DIET-643 protection was lost")
        for names in result["db_names"]:
            self.assertNotEqual(
                names.get("default"), LANE_DB,
                "a body ran against the ordinary lane database")
            self.assertEqual(names.get("default"),
                             result["child_test_database"])

    def test_w03_a_simpletestcase_declaring_database_access(self):
        """A SimpleTestCase subclass may request a database explicitly.

        Class name is not the signal; `databases` is.
        """
        result = run_supported_runner([CASE_SIMPLE_WITH_DB])
        self.assertEqual(result["returncode"], 0, result["stderr"][-400:])
        self.assertEqual(result["body_names"], ["simple_declaring_db"])
        self.assertTrue(
            result["created_test_database"],
            "a SimpleTestCase declaring databases={'default'} did not "
            "get a disposable database")
        self.assertTrue(result["guard_applied"])

    def test_w04_databases_all(self):
        """`databases = "__all__"` must prepare and guard every alias."""
        result = run_supported_runner([CASE_ALL_DATABASES])
        self.assertEqual(result["returncode"], 0, result["stderr"][-400:])
        self.assertEqual(result["body_names"], ["all_databases"])
        self.assertTrue(result["created_test_database"])
        self.assertTrue(result["guard_applied"])

    def test_w05_mixed_selection_runs_every_body(self):
        """Mixed: one database-backed test is enough to prepare one."""
        result = run_supported_runner([CASE_SIMPLE, CASE_DB])
        self.assertEqual(result["returncode"], 0, result["stderr"][-400:])
        self.assertEqual(sorted(result["body_names"]),
                         ["database_backed", "database_free"])
        self.assertTrue(result["created_test_database"])

    def test_w06_keepdb_preserves_the_disposable_target(self):
        """--keepdb reuses a disposable database; it must still guard,
        and must never resolve to the ordinary one."""
        result = run_supported_runner([CASE_DB], extra_args=("--keepdb",))
        self.assertEqual(result["returncode"], 0, result["stderr"][-400:])
        self.assertEqual(result["body_names"], ["database_backed"])
        self.assertTrue(result["guard_applied"])
        for names in result["db_names"]:
            self.assertNotEqual(names.get("default"), LANE_DB)

    def test_w07_an_empty_selection_is_not_body_evidence(self):
        """An empty suite must not read as a successful run with bodies."""
        result = run_supported_runner([], label="hh715_disposable.tests")
        self.assertEqual(
            result["body_names"], [],
            "an empty selection produced body receipts")
        # Attribution: zero bodies must mean "nothing to run", not
        # "the run collapsed". An unrelated failure would otherwise
        # satisfy the row.
        self.assertEqual(
            result["returncode"], 0,
            f"the empty selection failed rather than running nothing: "
            f"{result['stderr'].strip().splitlines()[-1:]}")
        self.assertIn("Ran 0 test", result["stderr"] + result["stdout"])


class MirrorsAndPartialSetup(SimpleTestCase):
    """Mirror routing and multi-alias failure paths, observation level.

    This lane configures one alias, so these use constructed mappings
    and prove the runner's reconciliation logic. They are not live
    multi-alias measurements and are not offered as such.
    """

    def test_r17_a_dangling_mirror_fails_closed(self):
        """A mirror whose target was never prepared must not pass."""
        connections = FakeConnections({
            "default": FakeConnection("default", TEST_DB),
            "mirror": FakeConnection("mirror", LANE_DB, mirror="absent"),
        })
        record = observe_setup(runner_module, connections,
                               aliases={"default", "mirror"},
                               prepared=(("default", LANE_DB, True),))
        self.assertIsNotNone(
            record.failure,
            "a mirror pointing at an unprepared alias was accepted")
        # Attribution: any unrelated exception would otherwise satisfy
        # the row. It must name the dangling mirror alias.
        contract_type = reconciliation_error()
        self.assertIsNotNone(
            contract_type,
            "netbox_hedgehog.tests.runner defines no UnpreparedTarget")
        self.assertIsInstance(record.failure, contract_type)
        self.assertIn("mirror", record.failure.aliases)

    def test_r18_a_mirror_routed_to_an_ordinary_db_fails_closed(self):
        """Valid mirror declaration, ordinary routing: still refused."""
        connections = FakeConnections({
            "default": FakeConnection("default", TEST_DB),
            "mirror": FakeConnection("mirror", LANE_DB, mirror="default"),
        })
        record = observe_setup(runner_module, connections,
                               aliases={"default", "mirror"},
                               prepared=(("default", LANE_DB, True),))
        self.assertIsNotNone(
            record.failure,
            "a mirror still routed to the ordinary database was guarded")
        self.assertEqual(
            record.altered, [],
            "tables were altered before the mirror was validated")

    def test_r19_a_configured_test_name_target_is_accepted(self):
        """Not every disposable name starts with `test_`."""
        connections = FakeConnections({
            "default": FakeConnection("default", "diet_disposable",
                                      test_name="diet_disposable"),
        })
        record = observe_setup(runner_module, connections,
                               aliases={"default"},
                               prepared=(("default", LANE_DB, True),))
        self.assertIsNone(
            record.failure,
            f"a configured TEST.NAME target was rejected: {record.failure}")
        self.assertEqual(record.guarded_aliases(), {"default"})

    def test_r20_validation_precedes_every_alter(self):
        """A later invalid alias must not be discovered after earlier
        targets were already altered."""
        connections = FakeConnections({
            "aaa": FakeConnection("aaa", "test_aaa"),
            "zzz": FakeConnection("zzz", LANE_DB),
        })
        record = observe_setup(runner_module, connections,
                               aliases={"aaa", "zzz"},
                               prepared=(("aaa", "aaa", True),
                                         ("zzz", "zzz", True)))
        self.assertIsNotNone(record.failure)
        self.assertEqual(
            record.altered, [],
            "the full mapping was not validated before altering: "
            f"{record.altered}")

    def test_r21_a_setup_failure_is_preserved_and_guards_nothing(self):
        """Renamed. The old name promised cleanup it never observed.

        This row is only about the setup-exception path: the original
        error survives and the guard is never consulted. Cleanup is
        R22/R23.
        """
        original = OSError("database vanished")
        record = observe_setup(runner_module, lane_only(),
                               aliases={"default"}, prepared=(),
                               setup_raises=original)
        self.assertIs(record.failure, original)
        self.assertEqual(record.guard_calls, [])
        self.assertEqual(
            record.teardown_calls, [],
            "nothing was prepared, so there is nothing to tear down")

    def test_r22_a_post_setup_refusal_tears_down_prepared_targets(self):
        """RED. Django's run_suite teardown does NOT run when setup
        raises, so a refusal after preparation must dispose of what it
        prepared rather than leaving a database behind."""
        # The prepared target is a GENUINE disposable database; the
        # refusal comes from a SECOND required alias that was never
        # prepared. An earlier version pointed the only target at the
        # ordinary lane database, so the refusal and the thing to be
        # torn down were the same object and the row could not say
        # whether a legitimately prepared target gets disposed of.
        connections = FakeConnections({
            "default": FakeConnection("default", TEST_DB),
            "missing": FakeConnection("missing", "netbox_missing"),
        })
        record = observe_setup(runner_module, connections,
                               aliases={"default", "missing"},
                               prepared=(("default", LANE_DB, True),))
        self.assertIsNotNone(record.failure)
        # OBSERVED, not performed. An earlier version had the harness
        # call teardown from its own except branch, which proved the
        # harness cleans up rather than the runner.
        self.assertEqual(
            record.teardown_calls, [["default"]],
            "the RUNNER did not tear down the legitimately prepared "
            "target it had created before refusing over another alias")

    def test_r22b_teardown_is_never_asked_about_unprepared_aliases(self):
        """NEGATIVE control for the unsafe route.

        R22 shows that a refusal tears down what it prepared. This is
        the other half: the teardown must be scoped to prepared
        targets only. A cleanup that reached an alias Django never
        prepared would be acting on an ordinary database -- the exact
        thing the guard exists to prevent, arriving through the
        cleanup path instead.
        """
        connections = FakeConnections({
            "default": FakeConnection("default", TEST_DB),
            "ordinary": FakeConnection("ordinary", LANE_DB),
        })
        record = observe_setup(runner_module, connections,
                               aliases={"default", "ordinary"},
                               prepared=(("default", LANE_DB, True),))
        self.assertIsNotNone(record.failure)
        for call in record.teardown_calls:
            self.assertNotIn(
                "ordinary", call,
                "teardown was asked about an alias that was never "
                "prepared, i.e. an ordinary database")

    def test_r22d_a_returned_tuple_on_an_ordinary_db_is_not_destroyed(self):
        """The gap r22b does NOT cover.

        r22b covers an alias Django never prepared. This is the other
        shape: Django RETURNS the alias in its config, with destroy=True,
        but the connection is routed to an ordinary database. Django
        believes it owns a disposable target; it does not. Cleanup
        would then issue DROP DATABASE against production data, and the
        refusal path is what would trigger it.
        """
        connections = FakeConnections({
            "default": FakeConnection("default", TEST_DB),
            "claimed": FakeConnection("claimed", LANE_DB),
        })
        record = observe_setup(
            runner_module, connections,
            aliases={"default", "claimed"},
            # "claimed" comes back as prepared and destroyable while
            # still pointed at an ordinary database.
            prepared=(("default", LANE_DB, True), ("claimed", LANE_DB, True)))
        # NOT merely "something failed". Under current code the guard
        # refuses `claimed` as a non-test database before any target
        # validation runs, so assertIsNotNone(record.failure) passes on
        # a mechanism this row is not about -- a false green. The
        # refusal must come from TARGET VALIDATION and must name the
        # offending alias.
        self.assertEqual(
            type(record.failure).__name__, "UnpreparedTarget",
            f"the refusal came from {type(record.failure).__name__}, "
            f"not from validating the returned targets")
        self.assertIn("claimed", getattr(record.failure, "aliases", []))
        for call in record.teardown_calls:
            self.assertNotIn(
                "claimed", call,
                "cleanup was asked to destroy a database that is not a "
                "disposable test target")

    def test_r22c_a_successful_run_tears_nothing_down(self):
        """NEGATIVE control: cleanup belongs to the failure path.

        If teardown ran on success, Django's own run_suite teardown
        would destroy the target twice.
        """
        record = observe_setup(runner_module, prepared_default(),
                               aliases={"default"},
                               prepared=(("default", LANE_DB, True),))
        self.assertIsNone(record.failure, str(record.failure))
        self.assertEqual(
            record.teardown_calls, [],
            "a successful setup tore down its own target")

    def test_r23_a_cleanup_failure_does_not_replace_the_original(self):
        """RED. If teardown itself fails, the FIRST error is the one
        that must reach the caller."""
        original = RuntimeError("primary refusal")
        secondary = OSError("could not drop the test database")
        record = observe_setup(runner_module, prepared_default(),
                               aliases={"default"},
                               prepared=(("default", LANE_DB, True),),
                               guard_raises=original,
                               teardown_raises=secondary)
        self.assertIs(
            record.failure, original,
            "the cleanup failure replaced the original error")
        self.assertIs(record.teardown_failure, secondary)
        self.assertEqual(record.teardown_calls, [["default"]])


class ProtectedAdapterSelection(SimpleTestCase):
    """The wrapper-prepared adapter selection, on this branch.

    I previously reported this as impossible here because no
    `runner_contract` files exist. That was wrong: the protected
    selection is the REAPER ADAPTER, whose `HNP_REAPER_CONTAINER_EVIDENCE`
    prerequisite `run_diet_tests.sh` prepares for any
    `netbox_hedgehog.tests.test_interchange*` label. It is present on
    this branch, and importing frozen #711 source was never needed.
    """

    ADAPTER = ("netbox_hedgehog.tests.test_interchange."
               "test_reaper_adapter_red")

    def test_p01_the_protected_selection_is_discoverable_here(self):
        """The module and its prerequisite both exist on this branch."""
        from django.test.runner import DiscoverRunner
        suite = DiscoverRunner(verbosity=0, interactive=False).build_suite(
            [self.ADAPTER])
        self.assertGreater(
            suite.countTestCases(), 0,
            "the protected adapter selection discovered no tests")

    def test_p02_the_wrapper_prepares_the_adapter_prerequisite(self):
        """`run_diet_tests.sh` must prepare the evidence the adapter
        consumes, for any test_interchange selection.

        Source-level: the wrapper is a shell script, so this reads it.
        The paired runtime fact is P03.
        """
        wrapper = (Path(runner_module.__file__).parent.parent
                   / "scripts" / "run_diet_tests.sh")
        text = wrapper.read_text(encoding="utf-8")
        self.assertIn("netbox_hedgehog.tests.test_interchange", text)
        self.assertIn("prove_reaper_lane.py", text)
        self.assertIn("reaper-container-evidence.json", text)

    def test_p03_the_adapter_selection_runs_through_the_runner(self):
        """RED where the prerequisite is absent, and that is the point:
        a raw runner invocation without the wrapper's preparation must
        not silently report success for the protected selection."""
        result = run_supported_runner([], label=self.ADAPTER)
        prepared = "HNP_REAPER_CONTAINER_EVIDENCE" in os.environ
        if prepared:
            self.assertEqual(result["returncode"], 0,
                             result["stderr"][-400:])
        else:
            self.assertNotEqual(
                result["returncode"], 0,
                "the protected adapter selection reported success "
                "without the wrapper-prepared evidence")
            # Attribution, with the masking stated rather than hidden.
            #
            # MEASURED: today this selection fails on the DIET-715
            # guard refusal, because the adapter rows are
            # database-free and the runner aborts before any of them.
            # So the prerequisite scenario this row exists for is
            # currently UNREACHABLE -- the row is red, but masked by
            # the very defect this suite is about. Saying so is the
            # point; a row that merely asserted "it failed" would read
            # as evidence it had tested the prerequisite.
            output = result["stderr"] + result["stdout"]
            if "refusing to apply the DIET-643 autovacuum guard" in output:
                self.fail(
                    "P03 is BLOCKED by the DIET-715 defect: the protected "
                    "adapter selection is database-free, so the runner "
                    "refuses before any adapter row executes. The "
                    "missing-prerequisite behaviour cannot be exercised "
                    "until W01 passes. This row must not be read as "
                    "evidence about the prerequisite.")
            # MEASURED, and not what I first assumed. Without the
            # wrapper's evidence the adapter does NOT emit a message
            # naming HNP_REAPER_CONTAINER_EVIDENCE; it fails inside its
            # evidence-dependent contract rows (a15/a16/a17) with
            # "FAILED (failures=2, errors=2)". Asserting a prerequisite
            # message would have been asserting behaviour that does not
            # exist. Attribution therefore binds to two facts that do:
            # collection succeeded, so this is not a masking failure,
            # and the failures are in the evidence-dependent rows.
            self.assertIn(
                "Found 34 test(s)", output,
                "the selection did not even collect; this is a masking "
                "failure, not the prerequisite scenario")
            failing = [line for line in output.splitlines()
                       if line.startswith(("FAIL:", "ERROR:"))]
            self.assertTrue(failing, "no row reported a failure")
            # SCOPE LIMIT, measured twice and reported rather than
            # papered over: the adapter surfaces NO machine-checkable
            # "missing evidence" cause. Its evidence-dependent rows
            # simply error. So this row can show that the protected
            # selection does not succeed without the wrapper, and
            # WHICH rows fail -- it cannot show WHY from the output,
            # because the why is not emitted. Binding to exact row ids
            # is the strongest attribution available at this layer;
            # the missing cause is raised separately as an adapter
            # gap, not asserted here as though it existed.
            evidence_rows = {
                "test_a15_harness_emits_artifacts_and_observed_results",
                "test_a16_missing_or_contradictory_harness_evidence_fails",
            }
            named = {row for row in evidence_rows
                     if any(row in line for line in failing)}
            self.assertEqual(
                named, evidence_rows,
                f"the evidence-dependent rows did not fail; the refusal "
                f"is not attributable to the missing prerequisite. "
                f"failing={failing[:4]}")
