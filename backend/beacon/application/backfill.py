"""Backfill classification for jobs already in the DB (e.g. ingested before the classifier
existed). Same caching contract as the pipeline: only never-classified rows are touched."""

from beacon.application.ports import Classifier, JobRepo


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
