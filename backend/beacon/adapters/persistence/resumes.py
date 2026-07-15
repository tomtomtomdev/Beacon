"""SqliteResumeRepo — persists uploaded resumes (§11 12b).

Dumb repo (the dedup/active policy lives in ingest_resume). The one invariant it owns is the
active-singleton: set_active flips the chosen row on and every other off in a single UPDATE.
"""

import sqlite3
from datetime import UTC, datetime

from beacon.domain.resume import Resume, profile_from_json, profile_to_json

_SELECT_COLUMNS = "id, label, source_text, profile_json, resume_hash, active, created_at"


class SqliteResumeRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def insert(self, resume: Resume) -> Resume:
        created_at = resume.created_at or datetime.now(UTC)  # caller normally passes it
        cursor = self._conn.execute(
            "INSERT INTO resumes (label, source_text, profile_json, resume_hash, active,"
            " created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                resume.label,
                resume.source_text,
                profile_to_json(resume.profile),
                resume.resume_hash,
                1 if resume.active else 0,
                created_at.isoformat(),
            ),
        )
        self._conn.commit()
        stored = self.get(int(cursor.lastrowid or 0))
        assert stored is not None  # noqa: S101 — the row we just inserted always exists
        return stored

    def get(self, resume_id: int) -> Resume | None:
        row = self._conn.execute(
            f"SELECT {_SELECT_COLUMNS} FROM resumes WHERE id = ?", (resume_id,)
        ).fetchone()
        return _row_to_resume(row) if row is not None else None

    def get_by_hash(self, resume_hash: str) -> Resume | None:
        row = self._conn.execute(
            f"SELECT {_SELECT_COLUMNS} FROM resumes WHERE resume_hash = ?", (resume_hash,)
        ).fetchone()
        return _row_to_resume(row) if row is not None else None

    def get_active(self) -> Resume | None:
        row = self._conn.execute(
            f"SELECT {_SELECT_COLUMNS} FROM resumes WHERE active = 1"
        ).fetchone()
        return _row_to_resume(row) if row is not None else None

    def list_all(self) -> list[Resume]:
        rows = self._conn.execute(f"SELECT {_SELECT_COLUMNS} FROM resumes ORDER BY id").fetchall()
        return [_row_to_resume(row) for row in rows]

    def set_active(self, resume_id: int) -> bool:
        if (
            self._conn.execute("SELECT 1 FROM resumes WHERE id = ?", (resume_id,)).fetchone()
            is None
        ):
            return False
        self._conn.execute(
            "UPDATE resumes SET active = CASE WHEN id = ? THEN 1 ELSE 0 END", (resume_id,)
        )
        self._conn.commit()
        return True

    def delete(self, resume_id: int) -> bool:
        cursor = self._conn.execute("DELETE FROM resumes WHERE id = ?", (resume_id,))
        self._conn.commit()
        return cursor.rowcount > 0


def _row_to_resume(row: sqlite3.Row) -> Resume:
    return Resume(
        id=row["id"],
        label=row["label"],
        source_text=row["source_text"],
        profile=profile_from_json(row["profile_json"]),
        resume_hash=row["resume_hash"],
        active=bool(row["active"]),
        created_at=datetime.fromisoformat(row["created_at"]),
    )
