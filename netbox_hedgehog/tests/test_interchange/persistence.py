"""Independent persistence observation for the atomicity rows (#673 I15-I16d).

Dev B's #674 review: counting through the production module's own accessors
lets a non-atomic implementation report zero from its own counters while having
written rows. The observation must therefore be independent of the code under
test.

This reads the DATABASE and the MEDIA tree directly, by introspection, so it
sees any table the plugin writes -- including ones a future implementation adds
without telling this suite.
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass

from django.conf import settings
from django.db import connection

#: Core changelog is included so a "success" ObjectChange cannot survive a
#: rolled-back import unnoticed.
_EXTRA_TABLES = ("core_objectchange",)


def _plugin_tables() -> list:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = current_schema() "
            "AND (table_name LIKE 'netbox_hedgehog%%' OR table_name = ANY(%s)) "
            "ORDER BY table_name",
            [list(_EXTRA_TABLES)],
        )
        return [row[0] for row in cursor.fetchall()]


def _media_files() -> frozenset:
    root = getattr(settings, "MEDIA_ROOT", None)
    if not root:
        return frozenset()
    base = pathlib.Path(root)
    if not base.is_dir():
        return frozenset()
    return frozenset(
        str(path.relative_to(base)) for path in base.rglob("*") if path.is_file())


@dataclass(frozen=True)
class PersistenceSnapshot:
    row_counts: dict
    media_files: frozenset

    @property
    def total_rows(self) -> int:
        return sum(self.row_counts.values())

    def diff(self, other: "PersistenceSnapshot") -> dict:
        """Tables whose counts changed, plus media files added or removed."""
        changed = {
            table: (self.row_counts.get(table, 0), other.row_counts.get(table, 0))
            for table in set(self.row_counts) | set(other.row_counts)
            if self.row_counts.get(table, 0) != other.row_counts.get(table, 0)
        }
        result = {"tables": changed}
        added = other.media_files - self.media_files
        removed = self.media_files - other.media_files
        if added:
            result["media_added"] = sorted(added)
        if removed:
            result["media_removed"] = sorted(removed)
        return result


def snapshot() -> PersistenceSnapshot:
    counts = {}
    with connection.cursor() as cursor:
        for table in _plugin_tables():
            cursor.execute(f'SELECT COUNT(*) FROM "{table}"')  # name from introspection
            counts[table] = cursor.fetchone()[0]
    return PersistenceSnapshot(counts, _media_files())
