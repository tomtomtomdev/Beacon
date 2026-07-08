import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime

from beacon.application.ports import Classifier, JobRepo, JobSource
from beacon.domain.company import Company
from beacon.domain.job import NormalizedJob
from beacon.domain.sponsorship import SponsorSignal, detect_sponsorship, resolve_tier

logger = logging.getLogger(__name__)

# Wiring provides this: maps a company to its ATS adapter, or None when no adapter exists yet.
type SourceFactory = Callable[[Company], JobSource | None]


@dataclass(frozen=True, slots=True)
class IngestResult:
    fetched: int
    upserted: int
    errors: int


def _resolve_sponsorship(job: NormalizedJob, company: Company) -> SponsorSignal:
    """Combine the posting's explicit-text signal with the company's registry flags via
    the one precedence function: explicit text > registry > unknown. Explicit tiers keep
    their evidence sentence; registry/unknown carry none."""
    detected = detect_sponsorship(job.description)
    text_tier = detected.tier if detected else None
    return SponsorSignal(
        tier=resolve_tier(text_tier, company.registry_flags),
        evidence=detected.evidence if detected else None,
    )


async def ingest_source(
    source: JobSource, company: Company, jobs: JobRepo, classifier: Classifier, *, now: datetime
) -> IngestResult:
    """Fetch → normalize → classify → upsert one board. One bad posting never kills the poll.

    Classification is cached by content_hash: a posting is (re)classified only when its
    content_hash is new or changed, so unchanged re-polls never re-run the classifier."""
    if company.id is None:
        raise ValueError(f"company {company.name!r} must be persisted before ingest")

    raw_postings = await source.fetch()
    upserted = errors = 0
    for raw in raw_postings:
        try:
            job = source.normalize(raw)
            previous_hash = jobs.content_hash_for(job.source_id, job.external_id)
            if previous_hash == job.content_hash:
                # Unchanged content: skip re-classify and re-detect; the stored
                # classification and sponsor tier/evidence carry over untouched.
                classification = None
                sponsorship = None
            else:
                classification = classifier.classify(job)
                sponsorship = _resolve_sponsorship(job, company)
            jobs.upsert(
                company.id, job, seen_at=now, classification=classification, sponsorship=sponsorship
            )
            upserted += 1
        except Exception:
            errors += 1
            logger.exception(
                "posting_failed source=%s company=%s external_id=%s",
                source.source_id,
                company.name,
                raw.get("id", "?"),
            )

    logger.info(
        "poll source=%s company=%s fetched=%d upserted=%d errors=%d",
        source.source_id,
        company.name,
        len(raw_postings),
        upserted,
        errors,
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
