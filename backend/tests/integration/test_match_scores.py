"""SqliteMatchScoreRepo against a real migrated DB (§11 12c): the Tier-1 score cache — the
upsert/get_cached roundtrip, the stored content_hash the use case gates staleness on, and
the replace-on-conflict behavior for a re-scored pair."""

import sqlite3
from datetime import UTC, datetime

from beacon.adapters.persistence.companies import SqliteCompanyRepo
from beacon.adapters.persistence.jobs import SqliteJobRepo
from beacon.adapters.persistence.match_scores import SqliteMatchScoreRepo
from beacon.domain.company import Company
from beacon.domain.job import NormalizedJob
from beacon.domain.resume import MatchScore

NOW = datetime(2026, 7, 16, tzinfo=UTC)
RESUME_HASH = "resume-abc"


def _score(overall: int = 90) -> MatchScore:
    return MatchScore(
        overall=overall,
        skills_score=100,
        level_score=100,
        sponsor_score=38,
        matched_skills=frozenset({"swift"}),
        missing_skills=frozenset({"kotlin"}),
    )


def _seed_job(conn: sqlite3.Connection, content_hash: str) -> int:
    company = SqliteCompanyRepo(conn).upsert(
        Company(name="Spotify", ats_type="lever", ats_slug="spotify", country_hq="SE", priority=1)
    )
    assert company.id is not None
    SqliteJobRepo(conn).upsert(
        company.id,
        NormalizedJob(
            source_id="lever",
            external_id="1",
            title="Senior iOS Engineer",
            url="https://example.test/1",
            description="Swift and SwiftUI.",
            location_raw="Stockholm",
            country="SE",
            city="Stockholm",
            posted_at=NOW,
            content_hash=content_hash,
        ),
        seen_at=NOW,
    )
    return int(conn.execute("SELECT id FROM jobs").fetchone()["id"])


def test_get_cached_is_empty_until_a_score_is_stored(db: sqlite3.Connection) -> None:
    repo = SqliteMatchScoreRepo(db)
    job_id = _seed_job(db, "h1")

    assert repo.get_cached(RESUME_HASH, [job_id]) == {}
    assert repo.get_cached(RESUME_HASH, []) == {}  # no ids — no query, no rows


def test_upsert_then_get_cached_roundtrips_with_the_content_hash(
    db: sqlite3.Connection,
) -> None:
    repo = SqliteMatchScoreRepo(db)
    job_id = _seed_job(db, "h1")

    repo.upsert(RESUME_HASH, job_id, "h1", _score(), NOW)

    cached = repo.get_cached(RESUME_HASH, [job_id])[job_id]
    assert cached.score == _score()
    assert cached.content_hash == "h1"  # the staleness gate the scoring use case reads


def test_rescoring_a_pair_replaces_its_row(db: sqlite3.Connection) -> None:
    repo = SqliteMatchScoreRepo(db)
    job_id = _seed_job(db, "h1")
    repo.upsert(RESUME_HASH, job_id, "h1", _score(overall=90), NOW)

    # The posting's content changed → the use case re-scores under the new content_hash.
    repo.upsert(RESUME_HASH, job_id, "h2", _score(overall=40), NOW)

    cached = repo.get_cached(RESUME_HASH, [job_id])[job_id]
    assert cached.score.overall == 40
    assert cached.content_hash == "h2"
