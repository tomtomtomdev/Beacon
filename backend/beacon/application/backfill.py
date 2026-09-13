"""Backfills over jobs already in the DB: classification for rows ingested before the
classifier existed, and the sponsorship tier for rows ingested before the home market did.
Same caching contract as the pipeline — only rows that actually need it are touched."""

from dataclasses import dataclass

from beacon.application.ports import Classifier, JobRepo
from beacon.domain.location import parse_location
from beacon.domain.sponsorship import HOME_COUNTRY, resolve_tier


def backfill_classifications(jobs: JobRepo, classifier: Classifier) -> int:
    """Classify every not-yet-classified job; return how many were classified."""
    pending = jobs.list_unclassified()
    for job_id, job in pending:
        jobs.set_classification(job_id, classifier.classify(job))
    return len(pending)


def upgrade_ambiguous_classifications(jobs: JobRepo, classifier: Classifier) -> int:
    """Re-run the (LLM-backed) classifier over the empty-category residue and rewrite only
    the rows it actually improved (a now-non-empty category set); return that improved count.

    This is the slice-9 catch-up for the pre-LLM backlog — rows classified '' by the earlier
    heuristic-only ingests. Distinct from backfill_classifications (which handles NULL, i.e.
    never-classified rows) so slice 3's '' = "classified, nothing matched" contract holds for
    the plain backfill. Rows the classifier still can't resolve are left '' (they cost one
    budgeted call and may be retried on a later run); cost is capped by the classifier's
    monthly LLM budget."""
    improved = 0
    for job_id, job in jobs.list_ambiguous():
        result = classifier.classify(job)
        if result.categories:
            jobs.set_classification(job_id, result)
            improved += 1
    return improved


def backfill_home_market(jobs: JobRepo) -> int:
    """Retier every stored home-market posting; return how many rows moved.

    The tier is asked of resolve_tier rather than named here, so the rule that the home
    market outranks the text/registry chain has exactly one statement in the codebase. Its
    first two arguments are immaterial by construction — that is the property
    test_not_required_sits_outside_the_text_chain pins over every combination of them.

    No re-classification: this is a location predicate over the country column, so nothing
    it touches can change a content_hash or spend an LLM call. Idempotent, so re-running it
    is free.
    """
    return jobs.set_tier_for_country(
        HOME_COUNTRY, resolve_tier(text_tier=None, registry_flags=0, country=HOME_COUNTRY)
    )


@dataclass(frozen=True, slots=True)
class LocationBackfill:
    """What one re-parse pass moved. `residue` is the honest remainder — rows whose string
    still names no country — and is reported rather than hidden, because a parser that
    silently filled everything would be guessing."""

    filled: int
    residue: int
    retiered: int


def backfill_locations(jobs: JobRepo) -> LocationBackfill:
    """Re-read the location string of every job that has no country; return what moved.

    Needs no network, no classifier and no key: the raw string was kept on the row for
    exactly this ("a better parser can re-parse without re-fetching"), so nothing here can
    move a content_hash or spend an LLM call. Idempotent — a filled row is no longer
    uncountried, so a second run moves zero.

    **Fills only where country IS NULL.** Several adapters establish a country without
    parse_location — jobtech and teamtailor read Swedish country names, MyCareersFuture
    reads a structured address block — so a blind re-parse would delete 543 correct
    countries in the real DB. Re-parsing fills gaps; it does not outrank an adapter.

    The company's home market is passed through because a shared city name (Geneva,
    Cambridge, San Jose) resolves no country without it. Retiering is not optional and is
    therefore not left to the caller: `not_required` is a location predicate, so a row that
    gains the home country must move onto that tier in the same pass.
    """
    filled = 0
    pending = jobs.list_uncountried()
    for job in pending:
        country, city = parse_location(job.location_raw, job.country_hq)
        if country is None:
            continue
        jobs.set_location(job.id, country, city)
        filled += 1
    return LocationBackfill(
        filled=filled, residue=len(pending) - filled, retiered=backfill_home_market(jobs)
    )
