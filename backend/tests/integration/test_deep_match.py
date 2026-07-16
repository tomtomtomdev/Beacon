"""deep_match_job use case (§11 12e) — the Tier-2 orchestration, against real repos with only
the LLM boundary and the budget faked. Mirrors the tiered classifier's discipline: the heuristic
score is always returned; the LLM only *upgrades* it with a rationale, only for the one job asked
about, only under budget, and any failure degrades silently to the heuristic. Cached by
(resume_hash, content_hash) — a repeat is free, a changed posting recomputes."""

import sqlite3
from datetime import UTC, datetime

from beacon.adapters.persistence.companies import SqliteCompanyRepo
from beacon.adapters.persistence.jobs import SqliteJobRepo
from beacon.adapters.persistence.match_scores import SqliteMatchScoreRepo
from beacon.application.deep_match import deep_match_job
from beacon.domain.classification import Category, Level
from beacon.domain.company import Company
from beacon.domain.job import NormalizedJob
from beacon.domain.resume import DeepMatchJob, MatchRationale, Resume, ResumeProfile

NOW = datetime(2026, 7, 16, tzinfo=UTC)

RATIONALE = MatchRationale(
    summary="Strong iOS fit.",
    strengths=("8 years Swift",),
    gaps=("No Kotlin",),
    verdict="Worth applying.",
    sponsor_note="Registry-inferred in a target country.",
)


class FakeMatcher:
    """Canned stand-in for LLMMatcher — records the jobs it was asked about, never hits the net."""

    def __init__(self, rationale: MatchRationale, *, error: Exception | None = None) -> None:
        self._rationale = rationale
        self._error = error
        self.calls: list[DeepMatchJob] = []

    def deep_match(self, resume: Resume, job: DeepMatchJob) -> MatchRationale:
        self.calls.append(job)
        if self._error is not None:
            raise self._error
        return self._rationale


class FakeBudget:
    def __init__(self, *, allow: bool = True) -> None:
        self._allow = allow
        self.reserves = 0

    def try_reserve(self) -> bool:
        self.reserves += 1
        return self._allow


def _resume() -> Resume:
    profile = ResumeProfile(
        skills=frozenset({"swift", "swiftui"}),
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


def _seed_job(conn: sqlite3.Connection, *, content_hash: str = "h1") -> int:
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
            description="Build the iOS app with Swift and SwiftUI. Kotlin a plus.",
            location_raw="Stockholm",
            country="SE",
            city="Stockholm",
            posted_at=NOW,
            content_hash=content_hash,
        ),
        seen_at=NOW,
    )
    return int(conn.execute("SELECT id FROM jobs").fetchone()["id"])


def test_returns_and_caches_a_rationale_under_budget(db: sqlite3.Connection) -> None:
    job_id = _seed_job(db)
    matcher = FakeMatcher(RATIONALE)
    budget = FakeBudget()

    result = deep_match_job(
        SqliteJobRepo(db), SqliteMatchScoreRepo(db), matcher, budget, _resume(), job_id, now=NOW
    )

    assert result is not None
    assert result.rationale == RATIONALE
    assert result.score.overall > 0  # the heuristic score rides along
    assert len(matcher.calls) == 1 and budget.reserves == 1
    # It was persisted — a second call is a free cache hit (no LLM, no budget).
    again = deep_match_job(
        SqliteJobRepo(db), SqliteMatchScoreRepo(db), matcher, budget, _resume(), job_id, now=NOW
    )
    assert again is not None and again.rationale == RATIONALE
    assert len(matcher.calls) == 1  # not called again
    assert budget.reserves == 1  # not reserved again


def test_budget_exhausted_degrades_to_heuristic(db: sqlite3.Connection) -> None:
    job_id = _seed_job(db)
    matcher = FakeMatcher(RATIONALE)
    budget = FakeBudget(allow=False)

    result = deep_match_job(
        SqliteJobRepo(db), SqliteMatchScoreRepo(db), matcher, budget, _resume(), job_id, now=NOW
    )

    assert result is not None
    assert result.rationale is None  # degraded
    assert result.score.overall > 0  # ...but the heuristic score is intact
    assert budget.reserves == 1  # budget was consulted
    assert matcher.calls == []  # ...and refused, so no call


def test_no_matcher_configured_degrades_to_heuristic(db: sqlite3.Connection) -> None:
    job_id = _seed_job(db)
    budget = FakeBudget()

    result = deep_match_job(
        SqliteJobRepo(db), SqliteMatchScoreRepo(db), None, budget, _resume(), job_id, now=NOW
    )

    assert result is not None
    assert result.rationale is None
    assert result.score.overall > 0
    assert budget.reserves == 0  # without a matcher the budget is never touched


def test_llm_failure_degrades_to_heuristic(db: sqlite3.Connection) -> None:
    job_id = _seed_job(db)
    matcher = FakeMatcher(RATIONALE, error=ValueError("LLM response is not valid JSON"))
    budget = FakeBudget()

    result = deep_match_job(
        SqliteJobRepo(db), SqliteMatchScoreRepo(db), matcher, budget, _resume(), job_id, now=NOW
    )

    assert result is not None
    assert result.rationale is None  # the error was swallowed
    assert result.score.overall > 0  # heuristic preserved, pipeline never crashed
    assert len(matcher.calls) == 1  # it was tried once


def test_unknown_job_returns_none(db: sqlite3.Connection) -> None:
    result = deep_match_job(
        SqliteJobRepo(db),
        SqliteMatchScoreRepo(db),
        FakeMatcher(RATIONALE),
        FakeBudget(),
        _resume(),
        9999,
        now=NOW,
    )

    assert result is None


def test_scores_exactly_one_job(db: sqlite3.Connection) -> None:
    job_id = _seed_job(db)
    matcher = FakeMatcher(RATIONALE)

    deep_match_job(
        SqliteJobRepo(db),
        SqliteMatchScoreRepo(db),
        matcher,
        FakeBudget(),
        _resume(),
        job_id,
        now=NOW,
    )

    # Exactly one job was ever handed to the LLM — there is no whole-DB fan-out path.
    assert len(matcher.calls) == 1
    assert matcher.calls[0].title == "Senior iOS Engineer"


def test_changed_posting_recomputes_the_rationale(db: sqlite3.Connection) -> None:
    job_id = _seed_job(db, content_hash="h1")
    matcher = FakeMatcher(RATIONALE)
    deep_match_job(
        SqliteJobRepo(db),
        SqliteMatchScoreRepo(db),
        matcher,
        FakeBudget(),
        _resume(),
        job_id,
        now=NOW,
    )

    # The posting is re-polled with materially changed content (new content_hash).
    _seed_job(db, content_hash="h2")
    deep_match_job(
        SqliteJobRepo(db),
        SqliteMatchScoreRepo(db),
        matcher,
        FakeBudget(),
        _resume(),
        job_id,
        now=NOW,
    )

    assert len(matcher.calls) == 2  # the stale h1 rationale was not reused for h2
