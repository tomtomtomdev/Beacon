"""Maps a company's ATS type to its adapter. New source = new entry in _ADAPTERS, nothing else.

SUPPORTED_ATS is derived from this table, so a company whose ats_type isn't here loads but
stays dormant (no adapter) until one is added.
"""

from collections.abc import Callable

from beacon.adapters.sources.ashby import AshbyAdapter
from beacon.adapters.sources.greenhouse import GreenhouseAdapter
from beacon.adapters.sources.himalayas import HimalayasAdapter
from beacon.adapters.sources.hn import HNAdapter
from beacon.adapters.sources.jobtech import JobTechAdapter
from beacon.adapters.sources.lever import LeverAdapter
from beacon.adapters.sources.mycareersfuture import MyCareersFutureAdapter
from beacon.adapters.sources.nav import NAVAdapter
from beacon.adapters.sources.recruitee import RecruiteeAdapter
from beacon.adapters.sources.remoteok import RemoteOKAdapter
from beacon.adapters.sources.rippling import RipplingAdapter
from beacon.adapters.sources.smartrecruiters import SmartRecruitersAdapter
from beacon.adapters.sources.teamtailor import TeamtailorAdapter
from beacon.adapters.sources.workable import WorkableAdapter
from beacon.adapters.sources.workday import WorkdayAdapter
from beacon.adapters.sources.wwr import WWRAdapter
from beacon.application.ingest import SourceFactory
from beacon.application.ports import Fetcher, JobSource
from beacon.domain.company import Company

type _BuildAdapter = Callable[[str, Fetcher], JobSource]

_ADAPTERS: dict[str, _BuildAdapter] = {
    "greenhouse": GreenhouseAdapter,
    "lever": LeverAdapter,
    "ashby": AshbyAdapter,
    "smartrecruiters": SmartRecruitersAdapter,
    "workable": WorkableAdapter,
    "workday": WorkdayAdapter,
    "teamtailor": TeamtailorAdapter,
    "recruitee": RecruiteeAdapter,
    "rippling": RipplingAdapter,
}

SUPPORTED_ATS = frozenset(_ADAPTERS)


def make_source_factory(fetcher: Fetcher) -> SourceFactory:
    def source_for(company: Company) -> JobSource | None:
        build = _ADAPTERS.get(company.ats_type)
        return build(company.ats_slug, fetcher) if build is not None else None

    return source_for


def make_companyless_sources(
    fetcher: Fetcher, *, nav_authenticated: bool = False
) -> list[JobSource]:
    """Sources not tied to a seed company; each yields jobs across many employers parsed
    from the postings (see ingest_companyless_source). Not part of the per-company factory.

    NAV is the one source that needs a credential, so it joins only when one is configured —
    an unauthenticated NAV poll is a guaranteed 401, not a source (the Telegram/LLM rule)."""
    sources: list[JobSource] = [
        HNAdapter(fetcher),
        JobTechAdapter(fetcher),
        RemoteOKAdapter(fetcher),
        WWRAdapter(fetcher),
        HimalayasAdapter(fetcher),
        MyCareersFutureAdapter(fetcher),
    ]
    if nav_authenticated:
        sources.append(NAVAdapter(fetcher))
    return sources
