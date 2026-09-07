"""Two probes that ask a source a question without trusting its answer.

`probe_quarantined` is the weekly restore probe (SPEC §7). `probe_candidate` is the
seed-row evidence gate (slice 15b): what a *candidate* board would actually contribute if
it were seeded, measured by running its real adapter through the real classifier.

The weekly restore probe (SPEC §7).

Quarantined sources are skipped by the regular poll, so without a probe they'd never recover
from a temporary outage or DNS blip. Once a week this retries each quarantined source exactly
once: a clean poll restores it to ok (and resumes upserting), a failed probe leaves it
quarantined with its counters untouched — a probe never pushes a source deeper."""

import logging
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

from beacon.application.ingest import SourceFactory, ingest_source
from beacon.application.ports import Classifier, CompanyRepo, JobRepo
from beacon.domain.classification import Category
from beacon.domain.company import Company
from beacon.domain.health import record_success

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ProbeResult:
    probed: int
    restored: int


async def probe_quarantined(
    company_repo: CompanyRepo,
    jobs: JobRepo,
    source_for: SourceFactory,
    classifier: Classifier,
    *,
    now: datetime,
) -> ProbeResult:
    quarantined = company_repo.list_quarantined()
    restored = 0
    for company in quarantined:
        source = source_for(company)
        if source is None or company.id is None:
            continue
        result = await ingest_source(source, company, jobs, classifier, now=now)
        if result.failure is None:
            state = company_repo.get_health(company.id)
            company_repo.set_health(company.id, record_success(state, now=now))
            restored += 1
            logger.info("probe_restored company=%s", company.name)
        else:
            # Still down — leave the quarantine and its counters exactly as they were.
            logger.info("probe_still_down company=%s kind=%s", company.name, result.failure)
    return ProbeResult(probed=len(quarantined), restored=restored)


@dataclass(frozen=True, slots=True)
class CandidateProbe:
    """What one candidate board would contribute if it were seeded.

    `fetched`, `normalized` and `with_text` are deliberately three numbers rather than one:
    a board can answer 200 with hundreds of rows that carry no ad text at all, which is reach
    that does not exist — no content_hash, no sponsorship tier, no resume score (Breezy HR,
    slice 14). `categories` / `unclassified` are the classifier's own verdict on the titles,
    so the counts are what `/jobs` would later show rather than a hopeful reading of the
    board, and `focus_titles` is what makes them checkable by eye."""

    company: str
    ats_type: str
    ats_slug: str
    fetched: int
    normalized: int
    with_text: int
    errors: int
    categories: Mapping[str, int]
    unclassified: int
    countries: Mapping[str, int]
    focus_titles: tuple[str, ...]


async def probe_candidate(
    company: Company,
    source_for: SourceFactory,
    classifier: Classifier,
    *,
    focus: Category = Category.IOS,
) -> CandidateProbe | None:
    """Report what a candidate board would ingest — the evidence a seed row needs (slice 15b).

    Nothing is persisted and no company id is required, so this runs against a candidate that
    is not in the DB (and must not be until it passes). None means the company's `ats_type`
    has no adapter, i.e. it would load dormant — a normal answer, not a failure.

    A fetch failure is *not* swallowed: a 404 slug or an unreachable host is the answer to the
    question being asked, so it propagates to the caller. One malformed posting, on the other
    hand, never kills the probe (rule 6)."""
    source = source_for(company)
    if source is None:
        return None

    raw_postings = await source.fetch()
    categories: Counter[str] = Counter()
    countries: Counter[str] = Counter()
    focus_titles: list[str] = []
    normalized = with_text = unclassified = errors = 0

    for raw in raw_postings:
        try:
            job = source.normalize(raw)
        except Exception:
            errors += 1
            logger.exception(
                "probe_posting_failed company=%s external_id=%s", company.name, raw.get("id", "?")
            )
            continue
        normalized += 1
        if job.description:
            with_text += 1
        if job.country:
            countries[job.country] += 1
        classified = classifier.classify(job)
        if not classified.categories:
            unclassified += 1
        for category in classified.categories:
            categories[category] += 1
        if focus in classified.categories:
            focus_titles.append(job.title)

    return CandidateProbe(
        company=company.name,
        ats_type=company.ats_type,
        ats_slug=company.ats_slug,
        fetched=len(raw_postings),
        normalized=normalized,
        with_text=with_text,
        errors=errors,
        categories=dict(categories),
        unclassified=unclassified,
        countries=dict(countries),
        focus_titles=tuple(focus_titles),
    )
