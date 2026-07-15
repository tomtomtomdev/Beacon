"""Tier-1 scoring use case (§11 12c): cache-gated heuristic scoring of a resume against the
current /jobs page.

The cache policy lives in the use case (the repo stays dumb), so these pin it against an
in-memory FakeMatchScoreRepo and a spy on score_match: an unchanged (resume_hash, content_hash)
reuses the stored score; a changed content_hash recomputes only that job.
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import pytest

from beacon.application.ports import CachedScore, JobListing
from beacon.application.scoring import ScorableJob, job_facts_from_listing, score_jobs_for_resume
from beacon.domain.classification import Category, Level
from beacon.domain.resume import JobFacts, MatchScore, Resume, ResumeProfile
from beacon.domain.sponsorship import SponsorTier

NOW = datetime(2026, 7, 15, tzinfo=UTC)


def make_resume() -> Resume:
    profile = ResumeProfile(
        skills=frozenset({"swift", "swiftui"}),
        categories=frozenset({Category.IOS}),
        level=Level.SENIOR,
        years=8,
        target_countries=frozenset(),
    )
    return Resume(
        id=1,
        label="CV",
        source_text="Senior iOS Engineer, 8 years Swift and SwiftUI",
        profile=profile,
        resume_hash="resume-abc",
        active=True,
        created_at=NOW,
    )


def make_facts(skills: frozenset[str]) -> JobFacts:
    return JobFacts(
        skills=skills,
        categories=frozenset({Category.IOS}),
        level=Level.SENIOR,
        country="SE",
        sponsor_tier=SponsorTier.UNKNOWN,
    )


class FakeMatchScoreRepo:
    """In-memory MatchScoreRepo implementing the real protocol (fakes over mocks)."""

    def __init__(self) -> None:
        self._rows: dict[tuple[str, int], CachedScore] = {}
        self.upserts = 0

    def get_cached(self, resume_hash: str, job_ids: Sequence[int]) -> dict[int, CachedScore]:
        return {
            job_id: self._rows[(resume_hash, job_id)]
            for job_id in job_ids
            if (resume_hash, job_id) in self._rows
        }

    def upsert(
        self,
        resume_hash: str,
        job_id: int,
        content_hash: str,
        score: MatchScore,
        computed_at: datetime,
    ) -> None:
        self._rows[(resume_hash, job_id)] = CachedScore(score=score, content_hash=content_hash)
        self.upserts += 1


def _spy_score_match(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Wrap the score_match the scoring module calls, to count computes without changing them."""
    from beacon.domain.resume import score_match as real

    calls: list[int] = []

    def counting(profile: ResumeProfile, job: JobFacts) -> MatchScore:
        calls.append(1)
        return real(profile, job)

    monkeypatch.setattr("beacon.application.scoring.score_match", counting)
    return calls


def test_score_jobs_for_resume_caches(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = FakeMatchScoreRepo()
    resume = make_resume()
    calls = _spy_score_match(monkeypatch)
    jobs = [
        ScorableJob(id=1, content_hash="h1", facts=make_facts(frozenset({"swift"}))),
        ScorableJob(id=2, content_hash="h2", facts=make_facts(frozenset({"kotlin"}))),
    ]

    first = score_jobs_for_resume(repo, resume, jobs, now=NOW)
    second = score_jobs_for_resume(repo, resume, jobs, now=NOW)

    assert set(first) == {1, 2}
    assert first == second  # identical scores on the cached pass
    assert len(calls) == 2  # computed once per job; the second pass was all cache hits


def test_changed_content_hash_recomputes_only_that_job(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = FakeMatchScoreRepo()
    resume = make_resume()
    calls = _spy_score_match(monkeypatch)
    jobs = [
        ScorableJob(id=1, content_hash="h1", facts=make_facts(frozenset({"swift"}))),
        ScorableJob(id=2, content_hash="h2", facts=make_facts(frozenset({"kotlin"}))),
    ]
    score_jobs_for_resume(repo, resume, jobs, now=NOW)  # warms the cache (2 computes)

    edited = [
        ScorableJob(id=1, content_hash="h1-new", facts=make_facts(frozenset({"swift"}))),
        ScorableJob(id=2, content_hash="h2", facts=make_facts(frozenset({"kotlin"}))),
    ]
    score_jobs_for_resume(repo, resume, edited, now=NOW)

    assert len(calls) == 3  # only job 1 (new content_hash) recomputed; job 2 stayed cached


def test_job_facts_from_listing_assembles_from_read_model_row() -> None:
    listing = JobListing(
        id=7,
        title="Senior iOS Engineer",
        company="Acme",
        url="https://example.test/7",
        location_raw="Stockholm",
        country="SE",
        city="Stockholm",
        categories=("ios",),
        level="senior",
        posted_at=NOW,
        sponsor_tier="registry_inferred",
        user_status="new",
    )

    facts = job_facts_from_listing(listing, description="We build with Swift and SwiftUI.")

    assert facts == JobFacts(
        skills=frozenset({"swift", "swiftui"}),
        categories=frozenset({Category.IOS}),
        level=Level.SENIOR,
        country="SE",
        sponsor_tier=SponsorTier.REGISTRY_INFERRED,
    )
