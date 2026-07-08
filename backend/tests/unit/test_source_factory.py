import httpx
import pytest

from beacon.adapters.http.polite import PoliteClient
from beacon.adapters.sources.factory import (
    SUPPORTED_ATS,
    make_companyless_sources,
    make_source_factory,
)
from beacon.domain.company import Company


def make_company(ats_type: str) -> Company:
    return Company(name="X", ats_type=ats_type, ats_slug="x", country_hq="US", priority=1, id=1)


def test_supported_ats_is_greenhouse_lever_ashby() -> None:
    assert SUPPORTED_ATS == {"greenhouse", "lever", "ashby"}


@pytest.mark.parametrize("ats_type", sorted(SUPPORTED_ATS))
def test_all_adapters_satisfy_the_jobsource_protocol(ats_type: str) -> None:
    source_for = make_source_factory(PoliteClient(httpx.AsyncClient()))

    source = source_for(make_company(ats_type))

    # Structural JobSource contract: an id plus fetch/normalize.
    assert source is not None
    assert source.source_id == ats_type
    assert callable(source.fetch) and callable(source.normalize)


def test_factory_returns_none_for_ats_without_adapter() -> None:
    source_for = make_source_factory(PoliteClient(httpx.AsyncClient()))

    assert source_for(make_company("smartrecruiters")) is None


def test_companyless_sources_are_hn_and_jobtech() -> None:
    sources = make_companyless_sources(PoliteClient(httpx.AsyncClient()))

    # Company-less sources aren't keyed by a seed company; the CLI ingests them separately.
    assert {source.source_id for source in sources} == {"hn", "jobtech"}
    assert all(callable(s.fetch) and callable(s.normalize) for s in sources)
