"""SqliteMatchScoreRepo against a real migrated DB (§11 12c): the Tier-1 score cache — the
upsert/get_cached roundtrip, the stored content_hash and scoring_version the use case gates
staleness on, and the replace-on-conflict behavior for a re-scored pair."""

import sqlite3
from datetime import UTC, datetime

from beacon.adapters.persistence.companies import SqliteCompanyRepo
from beacon.adapters.persistence.jobs import SqliteJobRepo
from beacon.application.ports import JobFilters
from beacon.adapters.persistence.match_scores import SqliteMatchScoreRepo
from beacon.domain.company import Company
from beacon.domain.job import NormalizedJob
from beacon.domain.resume import SCORING_VERSION, MatchScore

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

    repo.upsert(RESUME_HASH, job_id, "h1", SCORING_VERSION, _score(), NOW)

    cached = repo.get_cached(RESUME_HASH, [job_id])[job_id]
    assert cached.score == _score()
    # the two staleness gates the scoring use case reads
    assert cached.content_hash == "h1"
    assert cached.scoring_version == SCORING_VERSION


def test_rescoring_a_pair_replaces_its_row(db: sqlite3.Connection) -> None:
    repo = SqliteMatchScoreRepo(db)
    job_id = _seed_job(db, "h1")
    repo.upsert(RESUME_HASH, job_id, "h1", SCORING_VERSION, _score(overall=90), NOW)

    # The posting's content changed → the use case re-scores under the new content_hash.
    repo.upsert(RESUME_HASH, job_id, "h2", SCORING_VERSION, _score(overall=40), NOW)

    cached = repo.get_cached(RESUME_HASH, [job_id])[job_id]
    assert cached.score.overall == 40
    assert cached.content_hash == "h2"


def test_rows_written_before_versioning_read_back_as_version_zero(
    db: sqlite3.Connection,
) -> None:
    """Migration 010's DEFAULT 0 is what retires the pre-versioning cache: every row warmed
    before the column existed reads back at a version no SCORING_VERSION can equal, so the
    use case rescores it instead of trusting it."""
    repo = SqliteMatchScoreRepo(db)
    job_id = _seed_job(db, "h1")
    db.execute(
        """
        INSERT INTO job_match_scores (
            resume_hash, job_canonical_id, overall, skills_score, level_score, sponsor_score,
            matched_skills, missing_skills, content_hash, computed_at
        ) VALUES (?, ?, 90, 100, 100, 38, '[]', '[]', 'h1', ?)
        """,
        (RESUME_HASH, job_id, NOW.isoformat()),
    )

    cached = repo.get_cached(RESUME_HASH, [job_id])[job_id]

    assert cached.scoring_version == 0
    assert cached.scoring_version != SCORING_VERSION


def _seed_second_job(conn: sqlite3.Connection, external_id: str) -> int:
    company_id = int(conn.execute("SELECT id FROM companies").fetchone()["id"])
    SqliteJobRepo(conn).upsert(
        company_id,
        NormalizedJob(
            source_id="lever",
            external_id=external_id,
            title="iOS Engineer",
            url=f"https://example.test/{external_id}",
            description="Swift and SwiftUI.",
            location_raw="Stockholm",
            country="SE",
            city="Stockholm",
            posted_at=NOW,
            content_hash="h2",
        ),
        seen_at=NOW,
    )
    return int(
        conn.execute("SELECT id FROM jobs WHERE external_id = ?", (external_id,)).fetchone()["id"]
    )


def test_sort_by_match_ignores_scores_left_by_older_scoring_code(
    db: sqlite3.Connection,
) -> None:
    """sort=match picks the window the application then rescores, so a stale-version row must
    not win a slot: if it did, the SWIFT false positives would fill page 1 and the real iOS
    roles would never reach the window to be corrected."""
    repo = SqliteMatchScoreRepo(db)
    stale_job = _seed_job(db, "h1")
    fresh_job = _seed_second_job(db, "2")
    repo.upsert(RESUME_HASH, stale_job, "h1", SCORING_VERSION - 1, _score(overall=99), NOW)
    repo.upsert(RESUME_HASH, fresh_job, "h2", SCORING_VERSION, _score(overall=10), NOW)

    page = SqliteJobRepo(db).search(JobFilters(sort="match", resume_hash=RESUME_HASH, limit=10))

    assert [job.id for job in page.jobs] == [fresh_job, stale_job]
