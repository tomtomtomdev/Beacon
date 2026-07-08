"""Backfill classification for jobs already in the DB (e.g. ingested before the classifier
existed). Same caching contract as the pipeline: only never-classified rows are touched."""

from beacon.application.ports import Classifier, JobRepo


def backfill_classifications(jobs: JobRepo, classifier: Classifier) -> int:
    """Classify every not-yet-classified job; return how many were classified."""
    pending = jobs.list_unclassified()
    for job_id, job in pending:
        jobs.set_classification(job_id, classifier.classify(job))
    return len(pending)
