"""deep_match_job use case (§11 12e) — the deterministic Tier-2, against real repos.

The heuristic score is computed fresh and build_rationale words the SAME facts, so a
rationale always comes back (no key, no budget, no degrade path), identical calls word
identically, and a changed posting re-derives with no cache to go stale.
"""

import sqlite3
from datetime import UTC, datetime

from beacon.adapters.persistence.companies import SqliteCompanyRepo
from beacon.adapters.persistence.jobs import SqliteJobRepo
from beacon.application.deep_match import deep_match_job
from beacon.domain.classification import Category, Level
from beacon.domain.company import Company
from beacon.domain.job import NormalizedJob
from beacon.domain.resume import Resume, ResumeProfile

NOW = datetime(2026, 7, 16, tzinfo=UTC)


def _resume() -> Resume:
    profile = ResumeProfile(
        skills=frozenset({"ios", "swift", "swiftui"}),
        categories=frozenset({Category.IOS}),
        level=Level.SENIOR,
        years=8,
        target_countries=frozenset({"SE"}),
    )
    return Resume(
        id=1,
        label="CV",
        source_text="Senior iOS Engineer, 8 years Swift and SwiftUI.",
        profile=profile,
        resume_hash="resume-abc",
        active=True,
        created_at=NOW,
    )


def _seed_job(
    conn: sqlite3.Connection,
    *,
    description: str = "Build the iOS app with Swift and SwiftUI. Kotlin a plus.",
    content_hash: str = "h1",
) -> int:
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
            description=description,
            location_raw="Stockholm",
            country="SE",
            city="Stockholm",
            posted_at=NOW,
            content_hash=content_hash,
        ),
        seen_at=NOW,
    )
    return int(conn.execute("SELECT id FROM jobs").fetchone()["id"])


def test_returns_the_score_with_a_rationale_over_the_same_facts(db: sqlite3.Connection) -> None:
    job_id = _seed_job(db)

    result = deep_match_job(SqliteJobRepo(db), _resume(), job_id)

    assert result is not None
    assert result.score.overall > 0  # the heuristic score rides along
    # The rationale words the scored facts: kotlin is the one skill the posting names
    # that the resume lacks, and SE is in the resume's relocation strategy.
    assert any("kotlin" in line for line in result.rationale.gaps)
    assert result.rationale.sponsor_note.endswith("SE is in your relocation strategy.")
    assert result.rationale.verdict  # never empty — there is no degrade path


def test_is_deterministic_across_calls(db: sqlite3.Connection) -> None:
    job_id = _seed_job(db)

    first = deep_match_job(SqliteJobRepo(db), _resume(), job_id)
    second = deep_match_job(SqliteJobRepo(db), _resume(), job_id)

    assert first is not None and second is not None
    assert first.rationale == second.rationale
    assert first.score == second.score


def test_changed_posting_re_derives_the_rationale(db: sqlite3.Connection) -> None:
    job_id = _seed_job(db, content_hash="h1")
    before = deep_match_job(SqliteJobRepo(db), _resume(), job_id)

    # The posting is re-polled with materially changed content: Kotlin is gone.
    _seed_job(db, description="Build the iOS app with Swift and SwiftUI.", content_hash="h2")
    after = deep_match_job(SqliteJobRepo(db), _resume(), job_id)

    assert before is not None and after is not None
    assert any("kotlin" in line for line in before.rationale.gaps)
    assert not any("kotlin" in line for line in after.rationale.gaps)  # nothing stale survives


def test_unknown_job_returns_none(db: sqlite3.Connection) -> None:
    result = deep_match_job(SqliteJobRepo(db), _resume(), 9999)

    assert result is None
