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
                  guard_sql_raises=None, real_guard=False):
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

    real_apply = runner_module.apply_autovacuum_guard
    guard = recording_real_guard if real_guard else fake_guard
    call = {} if omit_aliases else {"aliases": aliases}
    with mock.patch.object(runner_module, "connections", connections), \
            mock.patch.object(runner_module, "apply_autovacuum_guard",
                              guard), \
            mock.patch.object(
                runner_module.DiscoverRunner, "setup_databases",
                staticmethod(fake_super_setup)):
        try:
            runner.setup_databases(**call)
        except BaseException as exc:          # recorded, never swallowed
            record.failure = exc
    return record
