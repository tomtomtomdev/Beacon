"""SqliteMatchScoreRepo against a real migrated DB (§11 12e): the Tier-2 rationale cache and
its content_hash invalidation. The Tier-1 score cache is exercised via the use case; here we
pin the deep-match additions — get_rationale / set_rationale and the staleness rule that a
re-scored posting (new content_hash) drops a stale rationale."""

import sqlite3
from datetime import UTC, datetime

from beacon.adapters.persistence.companies import SqliteCompanyRepo
from beacon.adapters.persistence.jobs import SqliteJobRepo
from beacon.adapters.persistence.match_scores import SqliteMatchScoreRepo
from beacon.domain.company import Company
from beacon.domain.job import NormalizedJob
from beacon.domain.resume import MatchRationale, MatchScore

NOW = datetime(2026, 7, 16, tzinfo=UTC)
RESUME_HASH = "resume-abc"


def _score() -> MatchScore:
    return MatchScore(
        overall=90,
        skills_score=100,
        level_score=100,
        sponsor_score=38,
        matched_skills=frozenset({"swift"}),
        missing_skills=frozenset({"kotlin"}),
    )


def _rationale() -> MatchRationale:
    return MatchRationale(
        summary="Strong iOS fit.",
        strengths=("8 years Swift",),
        gaps=("No Kotlin",),
        verdict="Worth applying.",
        sponsor_note="Registry-inferred in a target country.",
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


def test_get_rationale_is_none_until_one_is_stored(db: sqlite3.Connection) -> None:
    repo = SqliteMatchScoreRepo(db)
    job_id = _seed_job(db, "h1")
    repo.upsert(RESUME_HASH, job_id, "h1", _score(), NOW)  # a Tier-1 score, no rationale yet

    assert repo.get_rationale(RESUME_HASH, job_id) is None


def test_set_then_get_rationale_roundtrips(db: sqlite3.Connection) -> None:
    repo = SqliteMatchScoreRepo(db)
    job_id = _seed_job(db, "h1")
    repo.upsert(RESUME_HASH, job_id, "h1", _score(), NOW)

    repo.set_rationale(RESUME_HASH, job_id, "h1", _rationale(), NOW)

    cached = repo.get_rationale(RESUME_HASH, job_id)
    assert cached is not None
    assert cached.rationale == _rationale()
    assert cached.content_hash == "h1"
    # The Tier-1 score row is untouched by the rationale write.
    assert repo.get_cached(RESUME_HASH, [job_id])[job_id].score == _score()


def test_rescoring_a_changed_posting_drops_the_stale_rationale(db: sqlite3.Connection) -> None:
    repo = SqliteMatchScoreRepo(db)
    job_id = _seed_job(db, "h1")
    repo.upsert(RESUME_HASH, job_id, "h1", _score(), NOW)
    repo.set_rationale(RESUME_HASH, job_id, "h1", _rationale(), NOW)

    # The posting's content changed → Tier-1 re-scores with a new content_hash.
    repo.upsert(RESUME_HASH, job_id, "h2", _score(), NOW)

    # The old rationale was for h1; it must not survive as if it were for h2.
    assert repo.get_rationale(RESUME_HASH, job_id) is None


def test_rescoring_an_unchanged_posting_keeps_the_rationale(db: sqlite3.Connection) -> None:
    repo = SqliteMatchScoreRepo(db)
    job_id = _seed_job(db, "h1")
    repo.upsert(RESUME_HASH, job_id, "h1", _score(), NOW)
    repo.set_rationale(RESUME_HASH, job_id, "h1", _rationale(), NOW)

    repo.upsert(RESUME_HASH, job_id, "h1", _score(), NOW)  # same content_hash — a plain re-score

    cached = repo.get_rationale(RESUME_HASH, job_id)
    assert cached is not None and cached.rationale == _rationale()
