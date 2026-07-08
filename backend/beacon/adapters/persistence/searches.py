import sqlite3
from collections.abc import Sequence
from datetime import datetime

from beacon.domain.saved_search import (
    SavedSearch,
    filters_from_json,
    filters_to_json,
)

_SELECT_COLUMNS = "id, name, filters_json, notify_channel, last_run_at"


class SqliteSearchRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def create(self, search: SavedSearch) -> SavedSearch:
        cursor = self._conn.execute(
            "INSERT INTO saved_searches (name, filters_json, notify_channel, last_run_at)"
            " VALUES (?, ?, ?, ?)",
            (
                search.name,
                filters_to_json(search.filters),
                search.notify_channel,
                search.last_run_at.isoformat() if search.last_run_at else None,
            ),
        )
        self._conn.commit()
        created = self.get(int(cursor.lastrowid or 0))
        assert created is not None  # noqa: S101 — the row we just inserted always exists
        return created

    def list_all(self) -> list[SavedSearch]:
        rows = self._conn.execute(
            f"SELECT {_SELECT_COLUMNS} FROM saved_searches ORDER BY id"
        ).fetchall()
        return [_row_to_search(row) for row in rows]

    def get(self, search_id: int) -> SavedSearch | None:
        row = self._conn.execute(
            f"SELECT {_SELECT_COLUMNS} FROM saved_searches WHERE id = ?", (search_id,)
        ).fetchone()
        return _row_to_search(row) if row is not None else None

    def delete(self, search_id: int) -> bool:
        cursor = self._conn.execute("DELETE FROM saved_searches WHERE id = ?", (search_id,))
        self._conn.commit()
        return cursor.rowcount > 0

    def seen_job_ids(self, search_id: int) -> set[int]:
        rows = self._conn.execute(
            "SELECT job_canonical_id FROM seen_matches WHERE search_id = ?", (search_id,)
        ).fetchall()
        return {row["job_canonical_id"] for row in rows}

    def record_matches(
        self, search_id: int, matches: Sequence[tuple[int, str]], notified_at: datetime
    ) -> None:
        """Mark (job, reason) pairs as notified for this search. INSERT OR IGNORE keeps the
        first notification intact, so re-running a poll never resends or rewrites a match."""
        self._conn.executemany(
            "INSERT OR IGNORE INTO seen_matches"
            " (search_id, job_canonical_id, notified_at, match_reason) VALUES (?, ?, ?, ?)",
            [(search_id, job_id, notified_at.isoformat(), reason) for job_id, reason in matches],
        )
        self._conn.commit()

    def touch_last_run(self, search_id: int, at: datetime) -> None:
        self._conn.execute(
            "UPDATE saved_searches SET last_run_at = ? WHERE id = ?", (at.isoformat(), search_id)
        )
        self._conn.commit()


def _row_to_search(row: sqlite3.Row) -> SavedSearch:
    last_run_at = row["last_run_at"]
    return SavedSearch(
        id=row["id"],
        name=row["name"],
        filters=filters_from_json(row["filters_json"]),
        notify_channel=row["notify_channel"],
        last_run_at=datetime.fromisoformat(last_run_at) if last_run_at else None,
    )
