"""Cross-source dedup pass (SPEC §5). Runs after upsert: reads every persisted job,
assigns canonicals in the pure domain layer, and writes the links back. Idempotent."""

from collections import Counter
from dataclasses import dataclass

from beacon.application.ports import JobRepo
from beacon.domain.dedup import assign_canonicals


@dataclass(frozen=True, slots=True)
class DedupResult:
    groups: int  # canonical rows that gained at least one duplicate
    duplicates: int  # rows linked to a canonical


def dedupe_jobs(jobs: JobRepo) -> DedupResult:
    canonical = assign_canonicals(jobs.list_dedup_rows())
    jobs.set_canonical_links(
        {job_id: (None if root == job_id else root) for job_id, root in canonical.items()}
    )

    sizes = Counter(canonical.values())
    return DedupResult(
        groups=sum(1 for size in sizes.values() if size > 1),
        duplicates=sum(size - 1 for size in sizes.values() if size > 1),
    )
