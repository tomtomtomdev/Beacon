"""registries_meta persistence: record/list a registry snapshot's freshness (upsert on
re-record). Consumed by the digest's staleness nag (SPEC §7)."""

import sqlite3
from datetime import UTC, datetime

from beacon.adapters.persistence.registries_meta import SqliteRegistriesMetaRepo

EARLY = datetime(2026, 5, 1, 9, 0, tzinfo=UTC)
LATER = datetime(2026, 7, 1, 9, 0, tzinfo=UTC)


def test_record_then_list_roundtrips(db: sqlite3.Connection) -> None:
    repo = SqliteRegistriesMetaRepo(db)

    repo.record("UK", EARLY, 142000)
    repo.record("NL", LATER, 12886)

    metas = {m.registry: m for m in repo.list_all()}
    assert metas["UK"].fetched_at == EARLY
    assert metas["UK"].row_count == 142000
    assert metas["NL"].fetched_at == LATER


def test_recording_the_same_registry_again_upserts(db: sqlite3.Connection) -> None:
    repo = SqliteRegistriesMetaRepo(db)
    repo.record("UK", EARLY, 100)

    repo.record("UK", LATER, 200)

    metas = repo.list_all()
    assert len(metas) == 1
    assert metas[0].fetched_at == LATER
    assert metas[0].row_count == 200
