import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime

from beacon.application.ports import JobRepo, JobSource
from beacon.domain.company import Company

logger = logging.getLogger(__name__)

# Wiring provides this: maps a company to its ATS adapter, or None when no adapter exists yet.
type SourceFactory = Callable[[Company], JobSource | None]


@dataclass(frozen=True, slots=True)
class IngestResult:
    fetched: int
    upserted: int
    errors: int


async def ingest_source(
    source: JobSource, company: Company, jobs: JobRepo, *, now: datetime
) -> IngestResult:
    """Fetch → normalize → upsert one company's board. One bad posting never kills the poll."""
    if company.id is None:
        raise ValueError(f"company {company.name!r} must be persisted before ingest")

    raw_postings = await source.fetch()
    upserted = errors = 0
    for raw in raw_postings:
        try:
            jobs.upsert(company.id, source.normalize(raw), seen_at=now)
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
    companies: Sequence[Company], jobs: JobRepo, source_for: SourceFactory, *, now: datetime
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
            results[company.name] = await ingest_source(source, company, jobs, now=now)
        except Exception:
            logger.exception("poll_failed source=%s company=%s", source.source_id, company.name)
    return results
