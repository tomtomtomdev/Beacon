"""Backfills over jobs already in the DB: classification for rows ingested before the
classifier existed, and the sponsorship tier for rows ingested before the home market did.
Same caching contract as the pipeline — only rows that actually need it are touched."""

from beacon.application.ports import Classifier, JobRepo
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
