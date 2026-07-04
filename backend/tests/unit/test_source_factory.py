import httpx

from beacon.adapters.sources.factory import make_source_factory
from beacon.domain.company import Company


def make_company(ats_type: str) -> Company:
    return Company(name="X", ats_type=ats_type, ats_slug="x", country_hq="US", priority=1, id=1)


def test_factory_builds_greenhouse_adapter() -> None:
    source_for = make_source_factory(httpx.AsyncClient())

    source = source_for(make_company("greenhouse"))

    assert source is not None
    assert source.source_id == "greenhouse"


def test_factory_returns_none_for_ats_without_adapter() -> None:
    source_for = make_source_factory(httpx.AsyncClient())

    assert source_for(make_company("smartrecruiters")) is None
