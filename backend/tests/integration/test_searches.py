import sqlite3
from datetime import UTC, datetime

from beacon.adapters.persistence.searches import SqliteSearchRepo
from beacon.domain.saved_search import SavedSearch, SearchFilters

RUN_AT = datetime(2026, 7, 8, 6, 0, tzinfo=UTC)


def _seed_jobs(db: sqlite3.Connection, *job_ids: int) -> None:
    """Minimal company + canonical jobs so seen_matches' FK to jobs(id) is satisfiable."""
    db.execute(
        "INSERT INTO companies (id, name, ats_type, ats_slug, country_hq)"
        " VALUES (1, 'Spotify', 'lever', 'spotify', 'SE')"
    )
    db.executemany(
        "INSERT INTO jobs (id, company_id, source_id, external_id, title, description, url,"
        " content_hash, first_seen_at, last_seen_at)"
        " VALUES (?, 1, 'lever', ?, 'iOS Engineer', 'x', 'https://e.test', 'h', ?, ?)",
        [(job_id, str(job_id), RUN_AT.isoformat(), RUN_AT.isoformat()) for job_id in job_ids],
    )
    db.commit()


def _search(name: str = "Senior iOS") -> SavedSearch:
    return SavedSearch(
        name=name,
        filters=SearchFilters(
            countries=("SE", "NL", "IE"), categories=("ios",), levels=("senior",)
        ),
        notify_channel="telegram",
    )


def test_create_assigns_id_and_get_roundtrips_the_search(db: sqlite3.Connection) -> None:
    repo = SqliteSearchRepo(db)

    created = repo.create(_search())

    assert created.id is not None
    fetched = repo.get(created.id)
    assert fetched == created
    # Filters survive the JSON column round-trip.
    assert fetched is not None and fetched.filters == _search().filters


def test_list_all_returns_every_created_search(db: sqlite3.Connection) -> None:
    repo = SqliteSearchRepo(db)
    repo.create(_search("A"))
    repo.create(_search("B"))

    names = [s.name for s in repo.list_all()]

    assert names == ["A", "B"]


def test_delete_removes_the_search(db: sqlite3.Connection) -> None:
    repo = SqliteSearchRepo(db)
    created = repo.create(_search())
    assert created.id is not None

    assert repo.delete(created.id) is True
    assert repo.get(created.id) is None
    assert repo.delete(created.id) is False


def test_record_matches_then_seen_job_ids_reads_them_back(db: sqlite3.Connection) -> None:
    repo = SqliteSearchRepo(db)
    _seed_jobs(db, 10, 11)
    created = repo.create(_search())
    assert created.id is not None

    repo.record_matches(created.id, [(10, "ios · SE"), (11, "ios · NL")], notified_at=RUN_AT)

    assert repo.seen_job_ids(created.id) == {10, 11}
    reason = db.execute(
        "SELECT match_reason FROM seen_matches WHERE search_id = ? AND job_canonical_id = 10",
        (created.id,),
    ).fetchone()["match_reason"]
    assert reason == "ios · SE"


def test_recording_the_same_match_again_is_idempotent(db: sqlite3.Connection) -> None:
    repo = SqliteSearchRepo(db)
    _seed_jobs(db, 10)
    created = repo.create(_search())
    assert created.id is not None

    repo.record_matches(created.id, [(10, "first")], notified_at=RUN_AT)
    repo.record_matches(created.id, [(10, "second")], notified_at=RUN_AT)

    assert repo.seen_job_ids(created.id) == {10}
    reason = db.execute(
        "SELECT match_reason FROM seen_matches WHERE job_canonical_id = 10"
    ).fetchone()["match_reason"]
    assert reason == "first"  # the original notification is preserved


def test_touch_last_run_records_the_timestamp(db: sqlite3.Connection) -> None:
    repo = SqliteSearchRepo(db)
    created = repo.create(_search())
    assert created.id is not None

    repo.touch_last_run(created.id, RUN_AT)

    fetched = repo.get(created.id)
    assert fetched is not None and fetched.last_run_at == RUN_AT
