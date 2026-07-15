"""SqliteResumeRepo against a real migrated DB (§11 12b): insert, lookup, active-singleton."""

import sqlite3
from datetime import UTC, datetime

from beacon.adapters.persistence.resumes import SqliteResumeRepo
from beacon.domain.resume import Resume, build_profile, resume_hash

NOW = datetime(2026, 7, 15, tzinfo=UTC)


def _resume(text: str, *, label: str = "CV", active: bool = False) -> Resume:
    return Resume(
        id=None,
        label=label,
        source_text=text,
        profile=build_profile(text),
        resume_hash=resume_hash(text),
        active=active,
        created_at=NOW,
    )


def test_insert_then_read_back_roundtrips_the_profile(db: sqlite3.Connection) -> None:
    repo = SqliteResumeRepo(db)

    stored = repo.insert(_resume("Senior iOS Engineer, Swift and SwiftUI"))

    assert stored.id is not None
    fetched = repo.get(stored.id)
    assert fetched is not None
    assert fetched.profile == stored.profile
    assert fetched.resume_hash == stored.resume_hash


def test_get_by_hash_finds_the_row(db: sqlite3.Connection) -> None:
    repo = SqliteResumeRepo(db)
    stored = repo.insert(_resume("Backend engineer, Django and Postgres"))

    assert repo.get_by_hash(stored.resume_hash) == stored
    assert repo.get_by_hash("nonexistent") is None


def test_set_active_keeps_exactly_one_active(db: sqlite3.Connection) -> None:
    repo = SqliteResumeRepo(db)
    first = repo.insert(_resume("iOS Swift", label="A"))
    second = repo.insert(_resume("React CSS", label="B"))

    repo.set_active(first.id)  # type: ignore[arg-type]  # persisted → has id
    repo.set_active(second.id)  # type: ignore[arg-type]

    active = repo.get_active()
    assert active is not None
    assert active.id == second.id
    assert [r.active for r in repo.list_all()] == [False, True]


def test_set_active_unknown_id_changes_nothing(db: sqlite3.Connection) -> None:
    repo = SqliteResumeRepo(db)
    only = repo.insert(_resume("iOS Swift"))
    repo.set_active(only.id)  # type: ignore[arg-type]

    assert repo.set_active(9999) is False
    active = repo.get_active()
    assert active is not None and active.id == only.id  # still the real one, not deactivated


def test_delete_removes_the_row(db: sqlite3.Connection) -> None:
    repo = SqliteResumeRepo(db)
    stored = repo.insert(_resume("iOS Swift"))

    assert repo.delete(stored.id) is True  # type: ignore[arg-type]
    assert repo.list_all() == []
    assert repo.delete(stored.id) is False  # type: ignore[arg-type]
