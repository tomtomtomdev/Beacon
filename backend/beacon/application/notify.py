"""The `match_saved_searches` pipeline step: after ingest+dedup, find each saved
search's new matches, notify once, and remember them so they never re-fire."""

import logging
from dataclasses import dataclass
from datetime import datetime

from beacon.application.ports import JobListing, JobRepo, Notifier, SearchRepo
from beacon.application.searches import to_job_filters
from beacon.domain.digest import Digest, DigestGroup, DigestLine, HealthAlert, RegistryStale
from beacon.domain.saved_search import SearchFilters, match_reason

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class MatchResult:
    searches_run: int
    new_matches: int


def _digest_line(filters: SearchFilters, job: JobListing) -> DigestLine:
    reason = match_reason(
        filters,
        categories=job.categories,
        country=job.country,
        level=job.level,
        tier=job.sponsor_tier,
    )
    return DigestLine(
        title=job.title,
        company=job.company,
        country=job.country,
        tier=job.sponsor_tier,
        url=job.url,
        reason=reason,
    )


async def match_saved_searches(
    searches: SearchRepo,
    jobs: JobRepo,
    notifier: Notifier,
    *,
    now: datetime,
    health_alerts: tuple[HealthAlert, ...] = (),
    stale_registries: tuple[RegistryStale, ...] = (),
) -> MatchResult:
    """Notify (once) about every saved search's not-yet-seen matches.

    Sends a single grouped digest, then records the notified matches — send *before*
    record, so a notifier failure leaves the matches un-recorded and they retry next run.
    Source-health alerts (quarantines, stale registries) ride the same digest and make it
    send even with no new matches — silent decay is the failure mode this guards against."""
    all_searches = searches.list_all()
    groups: list[DigestGroup] = []
    pending: list[tuple[int, list[tuple[int, str]]]] = []

    for search in all_searches:
        if search.id is None:  # list_all only yields persisted rows; guard narrows the type
            continue
        page = jobs.search(to_job_filters(search.filters))
        seen = searches.seen_job_ids(search.id)
        new = [job for job in page.jobs if job.id not in seen]
        if not new:
            continue
        lines = tuple(_digest_line(search.filters, job) for job in new)
        groups.append(DigestGroup(search.name, lines))
        pending.append(
            (search.id, [(job.id, line.reason) for job, line in zip(new, lines, strict=True)])
        )

    digest = Digest(
        groups=tuple(groups), health_alerts=health_alerts, stale_registries=stale_registries
    )
    new_matches = sum(len(group.lines) for group in groups)

    if not digest.is_empty():
        await notifier.send(digest)
        for search_id, matches in pending:
            searches.record_matches(search_id, matches, notified_at=now)

    for search in all_searches:
        if search.id is not None:
            searches.touch_last_run(search.id, now)

    logger.info("match_saved_searches searches=%d new_matches=%d", len(all_searches), new_matches)
    return MatchResult(searches_run=len(all_searches), new_matches=new_matches)
