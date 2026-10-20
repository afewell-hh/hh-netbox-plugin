"""Observation helpers for the DIET-715 runner-lifecycle contract.

These do not patch the runner. They observe what it does, so a row can
state a fact about behaviour rather than about source text.

Why an observer rather than assertions on `runner.py`: the defect is
orchestration -- which aliases the guard is asked about, in what order,
relative to Django's actual preparation. That is only visible by
watching the calls, and a source-shaped assertion would pass against a
rewrite that preserved the shape and lost the property.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field


UNKNOWN = "unknown"


@dataclass
class AliasFacts:
    """What is true of one alias at the moment the guard is consulted.

    `prepared` means Django's setup returned a teardown record naming
    this connection. It is NOT the same as "the name looks like a test
    database": Dev B's third blocker is explicit that a setup tuple or a
    `test_`-looking name alone is not proof of preparation, so both are
    recorded separately and never collapsed.
    """

    alias: str
    name: str | None = None
    requested: bool = False
    prepared: bool = False
    destroy: bool | None = None
    mirror_of: str | None = None
    looks_like_test_name: bool = False


@dataclass
class LifecycleRecord:
    """Everything a row needs to judge one runner invocation."""

    #: aliases Django was asked to set up, exactly as passed.
    #: `None` records "omitted", which Django treats as its default
    #: behaviour and which must never be conflated with `{}`.
    requested_aliases: object = None
    requested_was_omitted: bool = False
    #: teardown records returned by the superclass setup.
    setup_returned: list = field(default_factory=list)
    #: aliases the guard was actually invoked for, in call order.
    guard_calls: list = field(default_factory=list)
    #: tables ALTERed, per alias, in call order.
    altered: list = field(default_factory=list)
    #: SQL statements issued against each alias by the guard.
    sql: list = field(default_factory=list)
    #: the exception that ended the run, if any.
    failure: BaseException | None = None
    #: teardown invocations observed after a post-setup refusal, and
    #: any exception teardown itself raised. Populated by
    #: `observe_setup`; an earlier draft declared a field nothing
    #: wrote, which is why R21 could claim to test cleanup while
    #: testing only the exception identity.
    teardown_calls: list = field(default_factory=list)
    teardown_failure: BaseException | None = None

    # Deliberately ABSENT: body-execution and teardown observations.
    # Earlier drafts declared `bodies` and `teardown_calls` that nothing
    # ever populated, so a row could read an always-empty list as
    # evidence that no body ran and no teardown was skipped. They are
    # removed rather than left empty; the wrapper-subprocess rows that
    # would populate them honestly are not yet implemented and are
    # reported as an open gap, not as a passing row.

    def guarded_aliases(self) -> set:
        return {call["alias"] for call in self.guard_calls}

    def prepared_aliases(self) -> set:
        return {entry["alias"] for entry in self.setup_returned}

    def guarded_but_not_prepared(self) -> set:
        """The defect, stated as a set.

        Non-empty means the guard was consulted about a connection
        Django did not prepare -- which is how a lane database reaches
        a guard built only for disposable ones.
        """
        return self.guarded_aliases() - self.prepared_aliases()


# NOTE: the reconciliation failure type is deliberately NOT defined
# here. An earlier draft owned it in this test package, so a correct
# fix raising its own runner-side type would have left the rows red --
# the suite would have rejected the change it exists to require. The
# rows now ask `netbox_hedgehog.tests.runner` for it; its absence is
# the RED cause and defining it is part of GREEN.


class NotObserved(AssertionError):
    """A row asked for evidence this record does not carry.

    Raised rather than returning a default, so a row can never pass by
    reading an absent observation as a benign value.
    """


def require(record: LifecycleRecord, field_name: str):
    value = getattr(record, field_name, None)
    if value is None:
        raise NotObserved(
            f"{field_name} was never observed in this record; a row must "
            f"not treat an unobserved value as evidence")
    return value


@contextlib.contextmanager
def nothing_observed():
    """A record that deliberately observed nothing.

    Used by controls that must fail when a row would accept an empty
    record as proof of good behaviour.
    """
    yield LifecycleRecord()


# ----------------------------------------------------------------------
# Driving the REAL runner.
#
# These helpers invoke `DietTestRunner.setup_databases` itself and record
# what it does. Nothing in `runner.py` is patched: the superclass setup
# and the guard are replaced only at the seams the runner calls OUT to,
# so the runner's own orchestration -- which is the thing under test --
# executes unmodified.
# ----------------------------------------------------------------------

class FakeConnection:
    """A connection with a name and routing, and no database behind it."""

    def __init__(self, alias, name, test_name=None, mirror=None):
        self.alias = alias
        self.settings_dict = {"NAME": name, "TEST": {}}
        if test_name is not None:
            self.settings_dict["TEST"]["NAME"] = test_name
        if mirror is not None:
            self.settings_dict["TEST"]["MIRROR"] = mirror
        self.cursor_calls = []

    def cursor(self):
        raise AssertionError(
            f"the guard opened a cursor on {self.alias} ({self.settings_dict['NAME']!r}); "
            f"a row must observe refusal BEFORE any cursor is opened")


class FakeConnections:
    """Stands in for django.db.connections for observation rows.

    Iterating yields alias names, indexing yields the connection, which
    is the surface `DietTestRunner.setup_databases` uses.
    """

    def __init__(self, mapping):
        self._mapping = dict(mapping)

    def __iter__(self):
        return iter(self._mapping)

    def __getitem__(self, alias):
        return self._mapping[alias]

    def keys(self):
        return self._mapping.keys()


def observe_setup(runner_module, connections, *, aliases, omit_aliases=False,
                  prepared=(), setup_raises=None, guard_raises=None,
                  guard_sql_raises=None, real_guard=False,
                  teardown_raises=None):
    """Run the real `DietTestRunner.setup_databases` and record it.

    `prepared` is what Django's superclass setup reports having created,
    as (alias, old_name, destroy) -- a teardown record, not an oracle.
    """
    from unittest import mock

    record = LifecycleRecord()
    record.requested_aliases = None if omit_aliases else aliases
    record.requested_was_omitted = omit_aliases

    runner = runner_module.DietTestRunner(verbosity=0, interactive=False)

    def fake_super_setup(**kwargs):
        record.requested_aliases = kwargs.get("aliases")
        record.requested_was_omitted = "aliases" not in kwargs
        if setup_raises is not None:
            raise setup_raises
        config = []
        for alias, old_name, destroy in prepared:
            record.setup_returned.append(
                {"alias": alias, "old_name": old_name, "destroy": destroy})
            config.append((connections[alias], old_name, destroy))
        return config

    def recording_real_guard(alias="default"):
        """The REAL `apply_autovacuum_guard`, merely recorded.

        A row that asserts the refusal must exercise the shipped guard.
        An earlier version reimplemented the refusal inside the fake and
        then asserted against it, which proved only that the fake was
        written correctly.
        """
        record.guard_calls.append(
            {"alias": alias,
             "name": connections[alias].settings_dict.get("NAME") or ""})
        return real_apply(alias)

    def fake_guard(alias="default"):
        conn = connections[alias]
        name = conn.settings_dict.get("NAME") or ""
        test_name = (conn.settings_dict.get("TEST") or {}).get("NAME")
        record.guard_calls.append({"alias": alias, "name": name})
        if guard_raises is not None:
            raise guard_raises
        # The real refusal, reproduced exactly: a non-test database is
        # rejected BEFORE any cursor is opened.
        is_test = (test_name and name == test_name) or name.startswith("test_")
        if not is_test:
            raise RuntimeError(
                f"refusing to apply the DIET-643 autovacuum guard to non-test "
                f"database {name!r}; this guard is for disposable test "
                f"databases only")
        if guard_sql_raises is not None:
            raise guard_sql_raises
        altered = list(runner_module.GUARDED_TABLES)
        record.altered.append({"alias": alias, "tables": altered})
        record.sql.append({"alias": alias, "statements": [
            f'ALTER TABLE "{t}" SET (autovacuum_enabled = false)'
            for t in altered]})
        return altered

    def recording_teardown(old_config, verbosity=1, **kwargs):
        """Records a teardown the RUNNER performs.

        The harness must never call this itself. An earlier version
        invoked `teardown_databases` from the except branch, so R22/R23
        proved the harness cleans up -- not the runner. Observing is
        the only honest option: if the runner never calls it, the rows
        stay red until it does.
        """
        record.teardown_calls.append(
            [c.alias for c, _old, _destroy in (old_config or [])])
        if teardown_raises is not None:
            record.teardown_failure = teardown_raises
            raise teardown_raises

    real_apply = runner_module.apply_autovacuum_guard
    guard = recording_real_guard if real_guard else fake_guard
    call = {} if omit_aliases else {"aliases": aliases}
    with mock.patch.object(runner_module, "connections", connections), \
            mock.patch.object(runner_module, "apply_autovacuum_guard",
                              guard), \
            mock.patch.object(
                runner_module.DiscoverRunner, "setup_databases",
                staticmethod(fake_super_setup)), \
            mock.patch.object(
                runner_module.DiscoverRunner, "teardown_databases",
                staticmethod(recording_teardown)):
        try:
            runner.setup_databases(**call)
        except BaseException as exc:          # recorded, never swallowed
            record.failure = exc
    return record


# ----------------------------------------------------------------------
# Real subprocess execution of the supported runner.
#
# These rows spawn `manage.py test <label> --testrunner=DietTestRunner`
# -- the exact runner selection `run_diet_tests.sh` makes -- against a
# DISPOSABLE module written to a temporary package.
#
# The module is disposable and named nothing this suite contains, for
# the reason #711 discovered the hard way: a selection that re-discovers
# the running suite respawns it, several levels deep, against one
# --keepdb database.
#
# Scope limit, stated rather than implied: this exercises the runner and
# real test bodies in a real subprocess. It is NOT the full
# `run_diet_tests.sh` path, which additionally performs compose exec and
# reaper-evidence preparation. Rows below say which of the two they
# speak for.
# ----------------------------------------------------------------------

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

RUNNER_LABEL = "netbox_hedgehog.tests.runner.DietTestRunner"

#: Written by each disposable body, so "the body ran" is a fact on disk
#: rather than a count parsed from runner output.
RECEIPT_VARIABLE = "HH715_BODY_RECEIPTS"

_BODY = '''
import json, os
from django.test import SimpleTestCase, TestCase
from django.db import connections

def _receipt(name, extra=None):
    path = os.environ.get("{receipt}")
    if not path:
        return
    # Configured name AND the name the SERVER reports. A settings
    # value only says what was asked for; current_database() says
    # what the connection is actually attached to.
    server = {{}}
    for alias in connections:
        try:
            with connections[alias].cursor() as cursor:
                cursor.execute("SELECT current_database()")
                server[alias] = cursor.fetchone()[0]
        except Exception as exc:
            server[alias] = f"unavailable: {{type(exc).__name__}}"
    record = {{"body": name, "server_db_names": server, "db_names": {{
        alias: connections[alias].settings_dict.get("NAME")
        for alias in connections}}}}
    if extra:
        record.update(extra)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\\n")

{cases}
'''

CASE_SIMPLE = '''
class DatabaseFree(SimpleTestCase):
    def test_body_runs_without_a_database(self):
        _receipt("database_free")
'''

CASE_DB = '''
class DatabaseBacked(TestCase):
    def test_body_runs_with_a_database(self):
        _receipt("database_backed")
'''

CASE_SIMPLE_WITH_DB = '''
class SimpleButDeclaresDatabase(SimpleTestCase):
    databases = {"default"}

    def test_body_declares_database_access(self):
        _receipt("simple_declaring_db")
'''

CASE_ALL_DATABASES = '''
class DeclaresAllDatabases(SimpleTestCase):
    databases = "__all__"

    def test_body_declares_all_databases(self):
        _receipt("all_databases")
'''


def run_supported_runner(cases, *, label=None, extra_args=(), timeout=600):
    """Spawn the real runner on a disposable module and report facts."""
    workspace = tempfile.mkdtemp(prefix="hh715-")
    package = Path(workspace) / "hh715_disposable"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "tests.py").write_text(
        _BODY.format(receipt=RECEIPT_VARIABLE,
                     cases=textwrap.dedent("".join(cases))),
        encoding="utf-8")
    receipts = Path(workspace) / "receipts.jsonl"

    # CHILD DATABASE ISOLATION.
    #
    # --keepdb alone does not isolate: it makes the child REUSE the same
    # disposable database the outer run is using, so a row could not
    # tell "the child got its own target" from "the child borrowed
    # ours", and a destructive child would act on the outer database.
    # A generated settings module gives the child its own TEST NAME.
    # The child's database name is STABLE, not per-invocation. A name
    # derived from the temporary workspace changed every run, so
    # --keepdb could never reuse it and every row rebuilt the whole
    # migration set: measured at roughly two minutes per subprocess
    # row, which is not viable in the interchange job. A fixed name is
    # still isolated from the outer run's `test_netbox` -- isolation
    # comes from the name differing, not from it being unique.
    # One owned child database PER LANE, reused across rows.
    #
    # A single global name would collide between concurrent lanes on a
    # shared server. The lane is taken from the Compose project when
    # present, so two lanes never share a child target, and the name is
    # recorded in the result for the retention check below.
    lane = (os.environ.get("COMPOSE_PROJECT_NAME")
            or os.environ.get("HH715_LANE"))
    if not lane:
        # FAIL CLOSED. Defaulting to a shared name such as "local"
        # meant every unidentified environment wrote to ONE database on
        # a shared server, which is a collision dressed as a default.
        raise RuntimeError(
            "no lane identity: set COMPOSE_PROJECT_NAME or HH715_LANE. "
            "These rows create an owned child database and must not "
            "share one with an unidentified environment.")
    # Truncation alone could collide: two lanes agreeing in their first
    # 24 characters would map to the same database. The digest is taken
    # over the FULL lane, so distinct lanes cannot collide even when
    # their readable prefixes match.
    readable = "".join(c if c.isalnum() else "_" for c in lane)[:24]
    fingerprint = hashlib.sha256(lane.encode("utf-8")).hexdigest()[:10]
    settings_name = f"hh715_settings_{os.getpid()}"
    child_test_db = f"test_hh715_{readable}_{fingerprint}"
    (Path(workspace) / (settings_name + ".py")).write_text(
        "from netbox.settings import *  # noqa: F401,F403\n"
        "DATABASES['default'].setdefault('TEST', {})\n"
        f"DATABASES['default']['TEST']['NAME'] = {child_test_db!r}\n",
        encoding="utf-8")

    environment = dict(os.environ)
    environment["PYTHONPATH"] = workspace + os.pathsep + environment.get(
        "PYTHONPATH", "")
    environment["DJANGO_SETTINGS_MODULE"] = settings_name
    environment[RECEIPT_VARIABLE] = str(receipts)

    # --noinput: an existing disposable database otherwise makes Django
    #   prompt, and the subprocess EOFs on stdin.
    # --keepdb: so the subprocess REUSES that database instead of
    #   dropping and recreating one the outer run may be using. Without
    #   it a row here could destroy the database the suite runs on.
    # --noinput so an existing target does not prompt. --keepdb so the
    # child REUSES ITS OWN stable database across rows instead of
    # rebuilding migrations each time; it cannot touch the outer run's
    # database, which has a different name. W00 verifies that from the
    # child's own connection rather than from this comment.
    base = ["--noinput", "--keepdb"]
    merged = [a for a in base if a not in extra_args] + list(extra_args)
    argv = [sys.executable, "manage.py", "test",
            label or "hh715_disposable.tests",
            f"--testrunner={RUNNER_LABEL}", "-v", "1", *merged]
    completed = subprocess.run(
        argv, capture_output=True, text=True, timeout=timeout,
        env=environment, cwd="/opt/netbox/netbox")

    bodies = []
    if receipts.exists():
        for line in receipts.read_text(encoding="utf-8").splitlines():
            if line.strip():
                bodies.append(json.loads(line))
    return {
        "argv": argv,
        "child_test_database": child_test_db,
        "child_lane": lane,
        # RETAINED ON PURPOSE: reuse is what keeps the subprocess rows
        # affordable. Declared here so a row can assert the retention
        # is deliberate and lane-scoped rather than accidental.
        "child_database_retained": True,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "bodies": bodies,
        "body_names": [b["body"] for b in bodies],
        "server_db_names": [b.get("server_db_names", {}) for b in bodies],
        "db_names": [b.get("db_names", {}) for b in bodies],
        # With --keepdb Django reports reuse rather than creation; both
        # mean "a disposable target was prepared for this run".
        "created_test_database": any(
            marker in (completed.stderr + completed.stdout)
            for marker in ("Creating test database",
                           "Using existing test database")),
        "guard_applied": "DIET-643: autovacuum disabled" in (
            completed.stdout + completed.stderr),
    }
