"""Maps a company's ATS type to its adapter. New source = new entry here, nothing else."""

import httpx

from beacon.adapters.sources.greenhouse import GreenhouseAdapter
from beacon.application.ingest import SourceFactory
from beacon.application.ports import JobSource
from beacon.domain.company import Company


def make_source_factory(client: httpx.AsyncClient) -> SourceFactory:
    def source_for(company: Company) -> JobSource | None:
        if company.ats_type == "greenhouse":
            return GreenhouseAdapter(slug=company.ats_slug, client=client)
        return None  # lever/ashby arrive in slice 4; other ATS types stay dormant

    return source_for
