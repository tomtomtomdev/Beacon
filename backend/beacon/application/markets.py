"""Market coverage: which countries hold open jobs, split against the SPEC §4 reference.

The corpus holds open jobs in 45 countries §4 has never assessed, and until this view existed
there was no way to ask for any of them — /jobs already accepted an arbitrary ?country=, so the
gap was never filtering, only discovery.
"""

from beacon.application.ports import JobRepo
from beacon.domain.visa import MarketCoverage, partition_markets


def get_market_coverage(jobs: JobRepo) -> MarketCoverage:
    return partition_markets(jobs.count_open_by_country())
