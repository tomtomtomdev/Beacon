import asyncio
import logging
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime

from beacon.application.errors import SourceUnavailable
from beacon.application.ports import Classifier, CompanyRepo, JobRepo, JobSource
from beacon.domain.company import SHADOW_ATS_TYPE, Company
from beacon.domain.health import FailureKind, record_failure, record_success, should_poll
from beacon.domain.job import CLOSE_AFTER_MISSES, NormalizedJob
from beacon.domain.sponsorship import SponsorSignal, detect_sponsorship, resolve_tier

logger = logging.getLogger(__name__)

# Wiring provides this: maps a company to its ATS adapter, or None when no adapter exists yet.
type SourceFactory = Callable[[Company], JobSource | None]
# Seconds from an arbitrary origin, monotonic. Injected so tests can step it (slice 25a).
type Clock = Callable[[], float]

# How many sources poll at once (slice 25b). Politeness does not depend on it: PoliteClient
# serialises same-host requests behind a per-host lock at 1 rps, so the bound only caps open
# connections and memory. Sources on one host (every Greenhouse board) still queue.
POLL_CONCURRENCY = 16


@dataclass(frozen=True, slots=True)
class IngestResult:
    fetched: int
    upserted: int
    errors: int
    # None on a successful poll; the health FailureKind when the poll failed. A failed poll
    # is fed to record_failure and — crucially — never runs the closed-sweep (SPEC §7).
    failure: FailureKind | None = None
    # Wall time of this one poll, failures included: a host timing out three times is exactly
    # the source that costs minutes (slice 25a — the poll had no per-source timing at all).
    secs: float = 0.0


def _resolve_sponsorship(job: NormalizedJob, registry_flags: int) -> SponsorSignal:
    """Combine the posting's location, its explicit-text signal and the company's registry
    flags via the one precedence function: home market > explicit text > registry > unknown.
    Explicit tiers keep their evidence sentence; home/registry/unknown carry none.

    The country passed is the JOB's (SPEC §5.1), which is what makes a Jakarta req from a
    Singapore-HQ seed resolve as home market rather than following its employer."""
    detected = detect_sponsorship(job.description)
    text_tier = detected.tier if detected else None
    tier = resolve_tier(text_tier, registry_flags, job.country)
    return SponsorSignal(
        tier=tier,
        evidence=detected.evidence if detected and tier is text_tier else None,
    )


def _upsert_posting(
    job: NormalizedJob,
    company_id: int,
    registry_flags: int,
    jobs: JobRepo,
    classifier: Classifier,
    now: datetime,
) -> None:
    """Classify + resolve sponsorship (gated by content_hash) and upsert one posting.

    Classification and sponsorship are (re)computed only when the posting's content_hash is
    new or changed; an unchanged re-poll upserts with both None so the stored values survive."""
    previous_hash = jobs.content_hash_for(job.source_id, job.external_id)
    if previous_hash == job.content_hash:
        classification = None
        sponsorship = None
    else:
        classification = classifier.classify(job)
        sponsorship = _resolve_sponsorship(job, registry_flags)
    jobs.upsert(
        company_id, job, seen_at=now, classification=classification, sponsorship=sponsorship
    )


def _stopwatch(clock: Clock) -> Callable[[], float]:
    started = clock()
    return lambda: round(clock() - started, 1)


async def ingest_source(
    source: JobSource,
    company: Company,
    jobs: JobRepo,
    classifier: Classifier,
    *,
    now: datetime,
    clock: Clock = time.monotonic,
) -> IngestResult:
    """Fetch → normalize → classify → upsert one board. One bad posting never kills the poll.

    A fetch failure is classified into a health FailureKind (gone/unreachable via
    SourceUnavailable; a shape error building the posting list → schema_drift) and returned,
    not raised. A failed poll — including a response where *every* posting fails to normalize
    (the API changed shape) — never runs the closed-sweep, so a broken source can't mass-close
    its jobs (SPEC §7)."""
    if company.id is None:
        raise ValueError(f"company {company.name!r} must be persisted before ingest")

    elapsed = _stopwatch(clock)
    try:
        raw_postings = await source.fetch()
    except SourceUnavailable as exc:
        secs = elapsed()
        logger.warning(
            "poll_failed source=%s company=%s kind=%s secs=%.1f",
            source.source_id,
            company.name,
            exc.kind,
            secs,
        )
        return IngestResult(fetched=0, upserted=0, errors=1, failure=exc.kind, secs=secs)
    except Exception:
        # Fetched bytes but couldn't even build the posting list → the response shape changed.
        secs = elapsed()
        logger.exception(
            "poll_schema_drift source=%s company=%s secs=%.1f", source.source_id, company.name, secs
        )
        return IngestResult(
            fetched=0, upserted=0, errors=1, failure=FailureKind.SCHEMA_DRIFT, secs=secs
        )

    upserted = errors = 0
    seen: set[str] = set()
    for raw in raw_postings:
        try:
            job = source.normalize(raw)
            seen.add(job.external_id)
            _upsert_posting(job, company.id, company.registry_flags, jobs, classifier, now)
            upserted += 1
        except Exception:
            errors += 1
            logger.exception(
                "posting_failed source=%s company=%s external_id=%s",
                source.source_id,
                company.name,
                raw.get("id", "?"),
            )

    # A non-empty response where nothing normalized is a shape change, not a poll — and its
    # empty `seen` set must NOT reach the sweep (an empty board is fine; all-failed is not).
    if raw_postings and upserted == 0:
        logger.warning(
            "poll_schema_drift source=%s company=%s fetched=%d",
            source.source_id,
            company.name,
            len(raw_postings),
        )
        return IngestResult(
            fetched=len(raw_postings),
            upserted=0,
            errors=errors,
            failure=FailureKind.SCHEMA_DRIFT,
            secs=elapsed(),
        )

    # Genuine success (fetch returned and at least one posting normalized, or the board is
    # legitimately empty) — sweep the company's postings on this source for closures. Scoped to
    # (source_id, company_id) since many companies share an ATS source_id.
    closed = jobs.sweep_absent_jobs(
        source.source_id, company.id, seen, now, threshold=CLOSE_AFTER_MISSES
    )
    secs = elapsed()
    logger.info(
        "poll source=%s company=%s fetched=%d upserted=%d errors=%d closed=%d secs=%.1f",
        source.source_id,
        company.name,
        len(raw_postings),
        upserted,
        errors,
        closed,
        secs,
    )
    return IngestResult(fetched=len(raw_postings), upserted=upserted, errors=errors, secs=secs)


def _shadow_company(job: NormalizedJob) -> Company:
    """A minimal employer row for a company named only inside a company-less posting.
    ats_type='none' means no adapter ever polls it; get_or_create leaves a real seed intact."""
    if not job.company_name:
        raise ValueError(f"company-less posting {job.external_id!r} has no company_name")
    return Company(
        name=job.company_name,
        ats_type=SHADOW_ATS_TYPE,
        ats_slug="",
        country_hq=job.country or "",
        priority=5,
    )


async def ingest_companyless_source(
    source: JobSource,
    jobs: JobRepo,
    companies: CompanyRepo,
    classifier: Classifier,
    *,
    now: datetime,
    clock: Clock = time.monotonic,
) -> IngestResult:
    """Ingest a source whose postings each name their own employer (HN, JobTech).

    One source yields jobs across many companies; each posting resolves-or-creates its
    employer (a known seed is reused, so its registry flags carry through). One bad posting
    never kills the poll."""
    elapsed = _stopwatch(clock)
    raw_postings = await source.fetch()
    upserted = errors = 0
    seen: set[str] = set()
    for raw in raw_postings:
        try:
            job = source.normalize(raw)
            seen.add(job.external_id)
            company = companies.get_or_create(_shadow_company(job))
            if company.id is None:  # get_or_create always persists; guard narrows the type
                raise ValueError(f"company {company.name!r} was not persisted")
            _upsert_posting(job, company.id, company.registry_flags, jobs, classifier, now)
            upserted += 1
        except Exception:
            errors += 1
            logger.exception(
                "posting_failed source=%s external_id=%s", source.source_id, raw.get("id", "?")
            )

    # Successful poll → sweep this source's postings across every employer it spans
    # (company_id=None: a company-less source isn't scoped to one company).
    closed = jobs.sweep_absent_jobs(source.source_id, None, seen, now, threshold=CLOSE_AFTER_MISSES)
    secs = elapsed()
    logger.info(
        "poll source=%s fetched=%d upserted=%d errors=%d closed=%d secs=%.1f",
        source.source_id,
        len(raw_postings),
        upserted,
        errors,
        closed,
        secs,
    )
    return IngestResult(fetched=len(raw_postings), upserted=upserted, errors=errors, secs=secs)


async def ingest_all(
    companies: Sequence[Company],
    jobs: JobRepo,
    source_for: SourceFactory,
    classifier: Classifier,
    company_repo: CompanyRepo,
    *,
    now: datetime,
    concurrency: int = POLL_CONCURRENCY,
) -> dict[str, IngestResult]:
    """Poll every company that has an adapter and isn't quarantined, recording each poll's
    health outcome. One dead board never stops the run; a quarantined source is skipped
    entirely (no fetch, no sweep — its jobs stay frozen), only the weekly probe retries it.

    Polls overlap, at most `concurrency` at a time (slice 25b: run sequentially, the poll's
    wall time was the sum of 60+ boards and reached 2989s of a 3000s watchdog). Results come
    back in company order whatever finishes first."""
    gate = asyncio.Semaphore(concurrency)

    async def poll(company: Company) -> IngestResult | None:
        source = source_for(company)
        if source is None:
            logger.info(
                "skip company=%s ats_type=%s reason=no_adapter", company.name, company.ats_type
            )
            return None
        if company.id is None:
            return None  # seed rows are always persisted; guard narrows the type
        state = company_repo.get_health(company.id)
        if not should_poll(state):
            logger.info(
                "skip company=%s reason=quarantined since=%s", company.name, state.last_success_at
            )
            return None
        try:
            async with gate:
                result = await ingest_source(source, company, jobs, classifier, now=now)
        except Exception:
            logger.exception("poll_crashed source=%s company=%s", source.source_id, company.name)
            return None
        updated = (
            record_success(state, now=now)
            if result.failure is None
            else record_failure(state, result.failure)
        )
        company_repo.set_health(company.id, updated)
        return result

    outcomes = await asyncio.gather(*(poll(company) for company in companies))
    return {
        company.name: result
        for company, result in zip(companies, outcomes, strict=True)
        if result is not None
    }


async def ingest_companyless_all(
    sources: Sequence[JobSource],
    jobs: JobRepo,
    companies: CompanyRepo,
    classifier: Classifier,
    *,
    now: datetime,
    concurrency: int = POLL_CONCURRENCY,
    clock: Clock = time.monotonic,
) -> dict[str, IngestResult]:
    """Poll every company-less source, overlapping like ingest_all. A source that crashes is
    logged with its time and skipped (rule 6): company-less sources have no per-company health
    to record. Results come back in source order."""
    gate = asyncio.Semaphore(concurrency)

    async def poll(source: JobSource) -> IngestResult | None:
        async with gate:
            elapsed = _stopwatch(clock)
            try:
                return await ingest_companyless_source(
                    source, jobs, companies, classifier, now=now, clock=clock
                )
            except Exception:
                logger.exception(
                    "companyless_poll_failed source=%s secs=%.1f", source.source_id, elapsed()
                )
                return None

    outcomes = await asyncio.gather(*(poll(source) for source in sources))
    return {
        source.source_id: result
        for source, result in zip(sources, outcomes, strict=True)
        if result is not None
    }
