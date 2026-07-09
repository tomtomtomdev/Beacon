from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from beacon.application.errors import SourceUnavailable
from beacon.application.ingest import (
    ingest_all,
    ingest_companyless_source,
    ingest_source,
)
from beacon.application.ports import JobDetail, JobFilters, JobPage, JobSource, RawPosting
from beacon.domain.classification import Category, Classification, Level
from beacon.domain.company import Company
from beacon.domain.dedup import DedupRow
from beacon.domain.health import FailureKind, Health, SourceHealth
from beacon.domain.job import CLOSE_AFTER_MISSES, NormalizedJob
from beacon.domain.registry import Registry
from beacon.domain.sponsorship import SponsorSignal, SponsorTier

NOW = datetime(2026, 7, 4, 12, 0, tzinfo=UTC)
LATER = datetime(2026, 7, 5, 12, 0, tzinfo=UTC)


def make_job(
    external_id: str, content_hash: str = "a" * 64, description: str = "Build things."
) -> NormalizedJob:
    return NormalizedJob(
        source_id="greenhouse",
        external_id=external_id,
        title=f"Engineer {external_id}",
        url=f"https://example.test/{external_id}",
        description=description,
        location_raw="Dublin, Ireland",
        country="IE",
        city="Dublin",
        posted_at=None,
        content_hash=content_hash,
    )


class CountingClassifier:
    """Classifier port that records which postings it was actually asked to classify."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def classify(self, job: NormalizedJob) -> Classification:
        self.calls.append(job.external_id)
        return Classification(categories=frozenset({Category.BACKEND}), level=Level.SENIOR)


class FakeSource:
    """JobSource whose normalize blows up on any payload marked bad."""

    source_id = "greenhouse"

    def __init__(self, raws: list[RawPosting]) -> None:
        self._raws = raws

    async def fetch(self) -> list[RawPosting]:
        return self._raws

    def normalize(self, raw: RawPosting) -> NormalizedJob:
        if raw.get("bad"):
            raise KeyError("malformed posting")
        return make_job(str(raw["id"]))


class FakeJobRepo:
    def __init__(self) -> None:
        self.upserts: list[tuple[int, NormalizedJob, datetime, Classification | None]] = []
        self.sponsorships: list[SponsorSignal | None] = []
        self.sweeps: list[tuple[str, int | None, set[str], datetime, int]] = []
        self._hashes: dict[tuple[str, str], str] = {}

    def upsert(
        self,
        company_id: int,
        job: NormalizedJob,
        seen_at: datetime,
        classification: Classification | None = None,
        sponsorship: SponsorSignal | None = None,
    ) -> None:
        self.upserts.append((company_id, job, seen_at, classification))
        self.sponsorships.append(sponsorship)
        self._hashes[(job.source_id, job.external_id)] = job.content_hash

    def content_hash_for(self, source_id: str, external_id: str) -> str | None:
        return self._hashes.get((source_id, external_id))

    def sweep_absent_jobs(
        self,
        source_id: str,
        company_id: int | None,
        seen_external_ids: set[str],
        now: datetime,
        *,
        threshold: int,
    ) -> int:
        self.sweeps.append((source_id, company_id, seen_external_ids, now, threshold))
        return 0

    def list_unclassified(self) -> list[tuple[int, NormalizedJob]]:
        raise NotImplementedError("ingest never backfills")

    def list_ambiguous(self) -> list[tuple[int, NormalizedJob]]:
        raise NotImplementedError("ingest never backfills")

    def set_classification(self, job_id: int, classification: Classification) -> None:
        raise NotImplementedError("ingest never backfills")

    def list_dedup_rows(self) -> list[DedupRow]:
        raise NotImplementedError("ingest never dedupes")

    def set_canonical_links(self, links: Mapping[int, int | None]) -> None:
        raise NotImplementedError("ingest never dedupes")

    def get_job_detail(self, job_id: int) -> JobDetail | None:
        raise NotImplementedError("ingest never reads detail")

    def set_user_status(self, job_id: int, status: str) -> int | None:
        raise NotImplementedError("ingest never sets status")

    def search(self, filters: JobFilters) -> JobPage:
        raise NotImplementedError("ingest never searches")

    def resolve_registry_tier(self, company_id: int, tier: str) -> None:
        raise NotImplementedError("ingest never re-resolves tiers")


COMPANY = Company(
    name="Tines", ats_type="greenhouse", ats_slug="tines", country_hq="IE", priority=2, id=7
)


async def test_ingest_source_upserts_every_fetched_posting() -> None:
    repo = FakeJobRepo()
    source = FakeSource([{"id": 1}, {"id": 2}, {"id": 3}])

    result = await ingest_source(source, COMPANY, repo, CountingClassifier(), now=NOW)

    assert (result.fetched, result.upserted, result.errors) == (3, 3, 0)
    assert [(cid, job.external_id, seen) for cid, job, seen, _ in repo.upserts] == [
        (7, "1", NOW),
        (7, "2", NOW),
        (7, "3", NOW),
    ]


async def test_one_bad_posting_never_blocks_the_poll() -> None:
    repo = FakeJobRepo()
    source = FakeSource([{"id": 1}, {"id": 2, "bad": True}, {"id": 3}])

    result = await ingest_source(source, COMPANY, repo, CountingClassifier(), now=NOW)

    assert (result.fetched, result.upserted, result.errors) == (3, 2, 1)
    assert [job.external_id for _, job, _, _ in repo.upserts] == ["1", "3"]


async def test_new_posting_is_classified_on_ingest() -> None:
    repo = FakeJobRepo()
    classifier = CountingClassifier()
    source = FakeSource([{"id": 1}])

    await ingest_source(source, COMPANY, repo, classifier, now=NOW)

    assert classifier.calls == ["1"]
    assert repo.upserts[0][3] == Classification(frozenset({Category.BACKEND}), Level.SENIOR)


async def test_classification_cached_by_content_hash() -> None:
    repo = FakeJobRepo()
    classifier = CountingClassifier()
    source = FakeSource([{"id": 1}])

    await ingest_source(source, COMPANY, repo, classifier, now=NOW)
    await ingest_source(source, COMPANY, repo, classifier, now=LATER)  # same content_hash

    assert classifier.calls == ["1"]  # classified exactly once, not on the re-poll
    assert repo.upserts[1][3] is None  # unchanged posting upserts without reclassifying


async def test_changed_content_hash_reclassifies() -> None:
    repo = FakeJobRepo()
    classifier = CountingClassifier()

    class MutatingSource(FakeSource):
        def normalize(self, raw: RawPosting) -> NormalizedJob:
            return make_job("1", content_hash=str(raw["hash"]))

    await ingest_source(MutatingSource([{"hash": "old"}]), COMPANY, repo, classifier, now=NOW)
    await ingest_source(MutatingSource([{"hash": "new"}]), COMPANY, repo, classifier, now=LATER)

    assert classifier.calls == ["1", "1"]  # content changed → classified again
    assert repo.upserts[1][3] is not None


class DescribedSource(FakeSource):
    """Fetches one posting whose description carries the given sponsorship text."""

    def __init__(self, description: str) -> None:
        super().__init__([{"id": 1}])
        self._description = description

    def normalize(self, raw: RawPosting) -> NormalizedJob:
        return make_job(str(raw["id"]), description=self._description)


async def test_explicit_text_tier_wins_over_registry_on_ingest() -> None:
    # A flagged company would infer registry_inferred, but explicit "no" text beats it.
    flagged = replace(COMPANY, registry_flags=int(Registry.UK))
    repo = FakeJobRepo()
    source = DescribedSource("No visa sponsorship is available for this role.")

    await ingest_source(source, flagged, repo, CountingClassifier(), now=NOW)

    assert repo.sponsorships[0] == SponsorSignal(
        SponsorTier.EXPLICIT_NO, "No visa sponsorship is available for this role."
    )


async def test_silent_text_falls_back_to_registry_tier_on_ingest() -> None:
    flagged = replace(COMPANY, registry_flags=int(Registry.NL))
    repo = FakeJobRepo()

    await ingest_source(
        DescribedSource("Build great products."), flagged, repo, CountingClassifier(), now=NOW
    )

    assert repo.sponsorships[0] == SponsorSignal(SponsorTier.REGISTRY_INFERRED, None)


async def test_silent_text_unflagged_company_is_unknown_on_ingest() -> None:
    repo = FakeJobRepo()  # COMPANY has no registry flags

    await ingest_source(
        DescribedSource("Build great products."), COMPANY, repo, CountingClassifier(), now=NOW
    )

    assert repo.sponsorships[0] == SponsorSignal(SponsorTier.UNKNOWN, None)


async def test_sponsorship_not_recomputed_on_unchanged_repoll() -> None:
    repo = FakeJobRepo()
    source = DescribedSource("Visa sponsorship available.")

    await ingest_source(source, COMPANY, repo, CountingClassifier(), now=NOW)
    await ingest_source(source, COMPANY, repo, CountingClassifier(), now=LATER)

    assert repo.sponsorships[0] == SponsorSignal(
        SponsorTier.EXPLICIT_YES, "Visa sponsorship available."
    )
    assert repo.sponsorships[1] is None  # unchanged content → tier left intact


async def test_ingest_requires_persisted_company() -> None:
    unsaved = Company(
        name="Tines", ats_type="greenhouse", ats_slug="tines", country_hq="IE", priority=2
    )

    with pytest.raises(ValueError, match="persisted"):
        await ingest_source(FakeSource([]), unsaved, FakeJobRepo(), CountingClassifier(), now=NOW)


def make_company(name: str, ats_type: str, company_id: int) -> Company:
    return Company(
        name=name,
        ats_type=ats_type,
        ats_slug=name.lower(),
        country_hq="US",
        priority=1,
        id=company_id,
    )


async def test_ingest_all_skips_unsupported_ats() -> None:
    supported = make_company("Tines", "greenhouse", 1)
    dormant = make_company("Grab", "smartrecruiters", 2)
    repo = FakeJobRepo()
    fetch_calls: list[str] = []

    def source_for(company: Company) -> FakeSource | None:
        if company.ats_type != "greenhouse":
            return None
        source = FakeSource([{"id": 1}])
        original_fetch = source.fetch

        async def counting_fetch() -> list[RawPosting]:
            fetch_calls.append(company.name)
            return await original_fetch()

        source.fetch = counting_fetch  # type: ignore[method-assign]  # test spy
        return source

    company_repo = FakeCompanyRepo(existing=[supported, dormant])
    results = await ingest_all(
        [supported, dormant], repo, source_for, CountingClassifier(), company_repo, now=NOW
    )

    assert fetch_calls == ["Tines"]
    assert set(results) == {"Tines"}
    assert [cid for cid, _, _, _ in repo.upserts] == [1]


async def test_successful_poll_runs_the_closed_sweep_with_the_seen_ids() -> None:
    repo = FakeJobRepo()
    source = FakeSource([{"id": 1}, {"id": 2}])

    await ingest_source(source, COMPANY, repo, CountingClassifier(), now=NOW)

    # Swept, scoped to (source_id, company_id), with exactly the ids present this poll.
    assert repo.sweeps == [("greenhouse", 7, {"1", "2"}, NOW, CLOSE_AFTER_MISSES)]


async def test_failed_poll_never_closes_jobs() -> None:
    # A poll whose fetch fails (404 / unreachable) must never run the closed-sweep — absence
    # only ever accrues from successful polls, so a dead board can't mass-close its jobs.
    repo = FakeJobRepo()
    company_repo = FakeCompanyRepo(existing=[COMPANY])
    gone = UnavailableSource(FailureKind.GONE)

    for _ in range(5):  # five consecutive failing cycles
        await ingest_all(
            [COMPANY], repo, lambda _c: gone, CountingClassifier(), company_repo, now=NOW
        )

    assert repo.sweeps == []  # never swept → nothing can close
    assert company_repo.get_health(7).health is Health.QUARANTINED  # gone after 3 (SPEC §7)


async def test_ingest_all_continues_when_one_company_fetch_fails() -> None:
    first = make_company("Aaa", "greenhouse", 1)
    second = make_company("Bbb", "greenhouse", 2)
    repo = FakeJobRepo()
    company_repo = FakeCompanyRepo(existing=[first, second])

    def source_for(company: Company) -> JobSource:
        return (
            UnavailableSource(FailureKind.UNREACHABLE)
            if company.name == "Aaa"
            else FakeSource([{"id": 9}])
        )

    results = await ingest_all(
        [first, second], repo, source_for, CountingClassifier(), company_repo, now=NOW
    )

    # Both polls are reported; Aaa's carries its failure, Bbb upserted its one job.
    assert results["Aaa"].failure is FailureKind.UNREACHABLE
    assert results["Bbb"].upserted == 1
    assert [job.external_id for _, job, _, _ in repo.upserts] == ["9"]


# --- source health: failure taxonomy, quarantine, freeze (slice 11) ---


class UnavailableSource:
    """A JobSource whose fetch fails at the HTTP/transport level with a given health kind."""

    source_id = "greenhouse"

    def __init__(self, kind: FailureKind) -> None:
        self._kind = kind

    async def fetch(self) -> list[RawPosting]:
        raise SourceUnavailable(self._kind)

    def normalize(self, raw: RawPosting) -> NormalizedJob:  # pragma: no cover - never reached
        raise AssertionError("unavailable source never normalizes")


class AllBadSource(FakeSource):
    """A non-empty response where every posting fails to normalize (a shape change)."""

    async def fetch(self) -> list[RawPosting]:
        return [{"id": 1, "bad": True}, {"id": 2, "bad": True}]


async def test_gone_fetch_records_the_kind_and_never_sweeps() -> None:
    repo = FakeJobRepo()

    result = await ingest_source(
        UnavailableSource(FailureKind.GONE), COMPANY, repo, CountingClassifier(), now=NOW
    )

    assert result.failure is FailureKind.GONE
    assert repo.sweeps == []  # a failed poll never runs the closed-sweep


async def test_all_postings_failing_to_normalize_is_schema_drift_without_a_sweep() -> None:
    # A non-empty response nothing could parse → the API changed shape; its empty seen-set
    # must NOT reach the sweep (that would mark every job absent and eventually close them).
    repo = FakeJobRepo()

    result = await ingest_source(AllBadSource([]), COMPANY, repo, CountingClassifier(), now=NOW)

    assert (result.fetched, result.upserted, result.failure) == (2, 0, FailureKind.SCHEMA_DRIFT)
    assert repo.sweeps == []


async def test_empty_board_is_a_successful_poll_that_still_sweeps() -> None:
    # Zero postings is a legitimate empty board (a successful poll), not schema drift.
    repo = FakeJobRepo()

    result = await ingest_source(FakeSource([]), COMPANY, repo, CountingClassifier(), now=NOW)

    assert result.failure is None
    assert repo.sweeps == [("greenhouse", 7, set(), NOW, CLOSE_AFTER_MISSES)]


async def test_ingest_all_quarantines_after_three_gone_polls() -> None:
    repo = FakeJobRepo()
    company_repo = FakeCompanyRepo(existing=[COMPANY])
    gone = UnavailableSource(FailureKind.GONE)

    for _ in range(2):
        await ingest_all(
            [COMPANY], repo, lambda _c: gone, CountingClassifier(), company_repo, now=NOW
        )
        assert company_repo.get_health(7).health is Health.DEGRADED  # under threshold

    await ingest_all([COMPANY], repo, lambda _c: gone, CountingClassifier(), company_repo, now=NOW)

    quarantined = company_repo.get_health(7)
    assert quarantined.health is Health.QUARANTINED
    assert quarantined.reason is FailureKind.GONE
    assert quarantined.consecutive_failures == 3


async def test_ingest_all_skips_a_quarantined_company_entirely() -> None:
    # Quarantined → not polled (no fetch, no log spam) and its jobs are frozen (never swept).
    repo = FakeJobRepo()
    company_repo = FakeCompanyRepo(existing=[COMPANY])
    company_repo.set_health(
        7, SourceHealth(consecutive_failures=3, health=Health.QUARANTINED, reason=FailureKind.GONE)
    )
    fetched: list[str] = []

    class WatchedSource(FakeSource):
        async def fetch(self) -> list[RawPosting]:
            fetched.append(self.source_id)
            return await super().fetch()

    await ingest_all(
        [COMPANY],
        repo,
        lambda _c: WatchedSource([{"id": 1}]),
        CountingClassifier(),
        company_repo,
        now=NOW,
    )

    assert fetched == []  # never polled
    assert repo.sweeps == []  # jobs frozen — the closed-sweep never touches them


async def test_success_after_a_failure_restores_health() -> None:
    repo = FakeJobRepo()
    company_repo = FakeCompanyRepo(existing=[COMPANY])

    await ingest_all(
        [COMPANY],
        repo,
        lambda _c: UnavailableSource(FailureKind.UNREACHABLE),
        CountingClassifier(),
        company_repo,
        now=NOW,
    )
    assert company_repo.get_health(7).consecutive_failures == 1

    await ingest_all(
        [COMPANY],
        repo,
        lambda _c: FakeSource([{"id": 1}]),
        CountingClassifier(),
        company_repo,
        now=LATER,
    )

    restored = company_repo.get_health(7)
    assert restored.health is Health.OK
    assert restored.consecutive_failures == 0
    assert restored.last_success_at == LATER


# --- company-less sources (HN / JobTech): one source, many companies parsed per posting ---


def companyless_job(
    external_id: str, company_name: str | None, description: str = "Build things."
) -> NormalizedJob:
    return NormalizedJob(
        source_id="hn",
        external_id=external_id,
        title="Engineer",
        url=f"https://news.ycombinator.com/item?id={external_id}",
        description=description,
        location_raw="",
        country=None,
        city=None,
        posted_at=None,
        content_hash="h" * 64,
        company_name=company_name,
    )


class CompanylessSource:
    """A JobSource whose postings each name their own company. A None slot blows up."""

    source_id = "hn"

    def __init__(self, jobs: list[NormalizedJob | None]) -> None:
        self._jobs = jobs

    async def fetch(self) -> list[RawPosting]:
        return [{"i": i} for i in range(len(self._jobs))]

    def normalize(self, raw: RawPosting) -> NormalizedJob:
        job = self._jobs[raw["i"]]
        if job is None:
            raise ValueError("malformed posting")
        return job


class FakeCompanyRepo:
    def __init__(self, existing: list[Company] | None = None) -> None:
        self._by_name: dict[str, Company] = {c.name: c for c in existing or []}
        self._next_id = max((c.id or 0 for c in self._by_name.values()), default=0) + 1
        self.created: list[str] = []
        self._health: dict[int, SourceHealth] = {}

    def get_or_create(self, company: Company) -> Company:
        found = self._by_name.get(company.name)
        if found is not None:
            return found
        stored = replace(company, id=self._next_id)
        self._next_id += 1
        self._by_name[company.name] = stored
        self.created.append(company.name)
        return stored

    def get_by_name(self, name: str) -> Company | None:
        return self._by_name.get(name)

    def upsert(self, company: Company) -> Company:
        raise NotImplementedError("company-less ingest never re-seeds")

    def list_active(self) -> list[Company]:
        raise NotImplementedError("company-less ingest never lists")

    def set_registry_match(
        self, company_id: int, flags: int, confidence: float | None, evidence: str | None
    ) -> None:
        raise NotImplementedError("company-less ingest never matches registries")

    def get_health(self, company_id: int) -> SourceHealth:
        return self._health.get(company_id, SourceHealth())

    def set_health(self, company_id: int, health: SourceHealth) -> None:
        self._health[company_id] = health

    def list_quarantined(self) -> list[Company]:
        quarantined = {cid for cid, h in self._health.items() if h.health is Health.QUARANTINED}
        return [c for c in self._by_name.values() if c.id in quarantined]


ANTHROPIC = Company(
    name="Anthropic",
    ats_type="greenhouse",
    ats_slug="anthropic",
    country_hq="US",
    priority=1,
    id=1,
    registry_flags=int(Registry.UK),
)


async def test_companyless_creates_shadow_company_for_a_new_name() -> None:
    jobs = FakeJobRepo()
    companies = FakeCompanyRepo()
    source = CompanylessSource([companyless_job("1", "BrandNewCo")])

    result = await ingest_companyless_source(source, jobs, companies, CountingClassifier(), now=NOW)

    assert (result.fetched, result.upserted, result.errors) == (1, 1, 0)
    assert companies.created == ["BrandNewCo"]
    shadow = companies.get_by_name("BrandNewCo")
    assert shadow is not None and shadow.ats_type == "none"
    assert jobs.upserts[0][0] == shadow.id  # posting attached to the shadow company's id


async def test_companyless_posting_attaches_to_existing_company_untouched() -> None:
    # A known name (already a seed) is reused, not shadowed — so the posting inherits its
    # registry flags: silent text at a UK-flagged company resolves to registry_inferred.
    jobs = FakeJobRepo()
    companies = FakeCompanyRepo(existing=[ANTHROPIC])
    source = CompanylessSource([companyless_job("1", "Anthropic")])

    await ingest_companyless_source(source, jobs, companies, CountingClassifier(), now=NOW)

    assert companies.created == []
    assert jobs.upserts[0][0] == 1
    assert jobs.sponsorships[0] == SponsorSignal(SponsorTier.REGISTRY_INFERRED, None)


async def test_companyless_one_bad_posting_never_blocks_the_poll() -> None:
    jobs = FakeJobRepo()
    companies = FakeCompanyRepo()
    source = CompanylessSource([companyless_job("1", "A"), None, companyless_job("3", "C")])

    result = await ingest_companyless_source(source, jobs, companies, CountingClassifier(), now=NOW)

    assert (result.fetched, result.upserted, result.errors) == (3, 2, 1)
    assert [job.external_id for _, job, _, _ in jobs.upserts] == ["1", "3"]


async def test_companyless_posting_without_company_name_is_an_error() -> None:
    jobs = FakeJobRepo()
    companies = FakeCompanyRepo()
    source = CompanylessSource([companyless_job("1", None)])

    result = await ingest_companyless_source(source, jobs, companies, CountingClassifier(), now=NOW)

    assert (result.fetched, result.upserted, result.errors) == (1, 0, 1)
    assert jobs.upserts == []
    assert companies.created == []


async def test_companyless_poll_sweeps_by_source_across_all_companies() -> None:
    # Company-less source spans many employers → sweep scope is the source_id, company_id None.
    jobs = FakeJobRepo()
    companies = FakeCompanyRepo()
    source = CompanylessSource([companyless_job("1", "A"), companyless_job("2", "B")])

    await ingest_companyless_source(source, jobs, companies, CountingClassifier(), now=NOW)

    assert jobs.sweeps == [("hn", None, {"1", "2"}, NOW, CLOSE_AFTER_MISSES)]
