"""Maps a company's ATS type to its adapter. New source = new entry here, nothing else."""

from beacon.adapters.sources.greenhouse import GreenhouseAdapter
from beacon.application.ingest import SourceFactory
from beacon.application.ports import Fetcher, JobSource
from beacon.domain.company import Company


def make_source_factory(fetcher: Fetcher) -> SourceFactory:
    def source_for(company: Company) -> JobSource | None:
        if company.ats_type == "greenhouse":
            return GreenhouseAdapter(slug=company.ats_slug, fetcher=fetcher)
        return None  # lever/ashby arrive later this slice; other ATS types stay dormant

    return source_for
