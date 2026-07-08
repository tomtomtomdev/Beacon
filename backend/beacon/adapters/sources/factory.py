"""Maps a company's ATS type to its adapter. New source = new entry in _ADAPTERS, nothing else.

SUPPORTED_ATS is derived from this table, so a company whose ats_type isn't here loads but
stays dormant (no adapter) until one is added.
"""

from collections.abc import Callable

from beacon.adapters.sources.ashby import AshbyAdapter
from beacon.adapters.sources.greenhouse import GreenhouseAdapter
from beacon.adapters.sources.hn import HNAdapter
from beacon.adapters.sources.jobtech import JobTechAdapter
from beacon.adapters.sources.lever import LeverAdapter
from beacon.application.ingest import SourceFactory
from beacon.application.ports import Fetcher, JobSource
from beacon.domain.company import Company

type _BuildAdapter = Callable[[str, Fetcher], JobSource]

_ADAPTERS: dict[str, _BuildAdapter] = {
    "greenhouse": GreenhouseAdapter,
    "lever": LeverAdapter,
    "ashby": AshbyAdapter,
}

SUPPORTED_ATS = frozenset(_ADAPTERS)


def make_source_factory(fetcher: Fetcher) -> SourceFactory:
    def source_for(company: Company) -> JobSource | None:
        build = _ADAPTERS.get(company.ats_type)
        return build(company.ats_slug, fetcher) if build is not None else None

    return source_for


def make_companyless_sources(fetcher: Fetcher) -> list[JobSource]:
    """Sources not tied to a seed company; each yields jobs across many employers parsed
    from the postings (see ingest_companyless_source). Not part of the per-company factory."""
    return [HNAdapter(fetcher), JobTechAdapter(fetcher)]
