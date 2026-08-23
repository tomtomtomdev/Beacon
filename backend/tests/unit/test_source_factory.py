import httpx
import pytest

from beacon.adapters.http.polite import PoliteClient
from beacon.adapters.sources.factory import (
    SUPPORTED_ATS,
    make_companyless_sources,
    make_source_factory,
)
from beacon.domain.company import Company


# Workday's slug carries tenant/instance/site; every other adapter takes a bare slug.
_SLUGS = {"workday": "acme/wd3/AcmeCareers"}


def make_company(ats_type: str) -> Company:
    return Company(
        name="X",
        ats_type=ats_type,
        ats_slug=_SLUGS.get(ats_type, "x"),
        country_hq="US",
        priority=1,
        id=1,
    )


def test_supported_ats_covers_every_seeded_ats_with_an_adapter() -> None:
    assert SUPPORTED_ATS == {
        "greenhouse",
        "lever",
        "ashby",
        "smartrecruiters",
        "workable",
        "workday",
        "teamtailor",
    }


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

    # gem is captcha-gated and bendingspoons has no public feed — both stay dormant seeds.
    assert source_for(make_company("gem")) is None


def test_companyless_sources_are_the_board_sources() -> None:
    sources = make_companyless_sources(PoliteClient(httpx.AsyncClient()))

    # Company-less sources aren't keyed by a seed company; the CLI ingests them separately.
    assert {source.source_id for source in sources} == {
        "hn",
        "jobtech",
        "remoteok",
        "weworkremotely",
        "himalayas",
        "mycareersfuture",
    }
    assert all(callable(s.fetch) and callable(s.normalize) for s in sources)
