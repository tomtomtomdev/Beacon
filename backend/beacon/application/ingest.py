import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime

from beacon.application.ports import Classifier, CompanyRepo, JobRepo, JobSource
from beacon.domain.company import Company
from beacon.domain.job import CLOSE_AFTER_MISSES, NormalizedJob
from beacon.domain.sponsorship import SponsorSignal, detect_sponsorship, resolve_tier

# ats_type a company-less source stamps on employers it shadows; no adapter polls it.
SHADOW_ATS_TYPE = "none"

logger = logging.getLogger(__name__)

# Wiring provides this: maps a company to its ATS adapter, or None when no adapter exists yet.
type SourceFactory = Callable[[Company], JobSource | None]


@dataclass(frozen=True, slots=True)
class IngestResult:
    fetched: int
    upserted: int
    errors: int


def _resolve_sponsorship(job: NormalizedJob, registry_flags: int) -> SponsorSignal:
    """Combine the posting's explicit-text signal with the company's registry flags via
    the one precedence function: explicit text > registry > unknown. Explicit tiers keep
    their evidence sentence; registry/unknown carry none."""
    detected = detect_sponsorship(job.description)
    text_tier = detected.tier if detected else None
    return SponsorSignal(
        tier=resolve_tier(text_tier, registry_flags),
        evidence=detected.evidence if detected else None,
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


async def ingest_source(
    source: JobSource, company: Company, jobs: JobRepo, classifier: Classifier, *, now: datetime
) -> IngestResult:
    """Fetch → normalize → classify → upsert one board. One bad posting never kills the poll."""
    if company.id is None:
        raise ValueError(f"company {company.name!r} must be persisted before ingest")

    raw_postings = await source.fetch()
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

    # This poll succeeded (fetch returned) — sweep the company's postings on this source for
    # closures. Scoped to (source_id, company_id) since many companies share an ATS source_id.
    closed = jobs.sweep_absent_jobs(
        source.source_id, company.id, seen, now, threshold=CLOSE_AFTER_MISSES
    )
    logger.info(
        "poll source=%s company=%s fetched=%d upserted=%d errors=%d closed=%d",
        source.source_id,
        company.name,
        len(raw_postings),
        upserted,
        errors,
        closed,
    )
    return IngestResult(fetched=len(raw_postings), upserted=upserted, errors=errors)


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
) -> IngestResult:
    """Ingest a source whose postings each name their own employer (HN, JobTech).

    One source yields jobs across many companies; each posting resolves-or-creates its
    employer (a known seed is reused, so its registry flags carry through). One bad posting
    never kills the poll."""
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
    logger.info(
        "poll source=%s fetched=%d upserted=%d errors=%d closed=%d",
        source.source_id,
        len(raw_postings),
        upserted,
        errors,
        closed,
    )
    return IngestResult(fetched=len(raw_postings), upserted=upserted, errors=errors)


async def ingest_all(
    companies: Sequence[Company],
    jobs: JobRepo,
    source_for: SourceFactory,
    classifier: Classifier,
    *,
    now: datetime,
) -> dict[str, IngestResult]:
    """Poll every company that has an adapter. One dead board never stops the run."""
    results: dict[str, IngestResult] = {}
    for company in companies:
        source = source_for(company)
        if source is None:
            logger.info(
                "skip company=%s ats_type=%s reason=no_adapter", company.name, company.ats_type
            )
            continue
        try:
            results[company.name] = await ingest_source(source, company, jobs, classifier, now=now)
        except Exception:
            logger.exception("poll_failed source=%s company=%s", source.source_id, company.name)
    return results
