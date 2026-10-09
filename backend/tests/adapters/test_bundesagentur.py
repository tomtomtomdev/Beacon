"""Bundesagentur für Arbeit Jobsuche as a company-less JobSource — recorded live 2026-10-07.

`jobs_ios_entwickler.json` is the v6 list for `was=iOS Entwickler` (page 1, size 25),
`ergebnisliste` trimmed to three of its 21 rows (single place, single place, ten places with a
padded `firma`) plus one OESTERREICH row from a `was=Softwareentwickler&wo=Österreich` page;
`facetten` dropped. The two `jobdetail_*.json` files are the v4 details of the first two rows.
"""

from base64 import b64encode
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, cast

import httpx
import pytest

from beacon.adapters.http.polite import PoliteClient
from beacon.adapters.sources.bundesagentur import BundesagenturAdapter
from beacon.domain.descriptions import content_hash, normalize_description

_LIST = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v6/jobs"
_DETAIL = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobdetails/"
_PETAFUEL = "10001-1003456610-S"
_STAMPAY = "13644-123163-S"
_AUSTRIA = "11949-17378531-S"


@pytest.fixture
def listing(load_fixture: Callable[[str], Any]) -> dict[str, Any]:
    return cast(dict[str, Any], load_fixture("bundesagentur/jobs_ios_entwickler.json"))


@pytest.fixture
def details(load_fixture: Callable[[str], Any]) -> dict[str, dict[str, Any]]:
    return {
        refnr: cast(dict[str, Any], load_fixture(f"bundesagentur/jobdetail_{refnr}.json"))
        for refnr in (_PETAFUEL, _STAMPAY)
    }


def make_adapter(
    handler: Callable[[httpx.Request], httpx.Response] | None = None,
    *,
    queries: tuple[str, ...] = ("iOS Entwickler",),
    page_size: int = 25,
    max_pages: int = 2,
) -> BundesagenturAdapter:
    transport = httpx.MockTransport(handler) if handler else None
    client = httpx.AsyncClient(transport=transport)
    return BundesagenturAdapter(
        PoliteClient(client, min_interval=0.0),
        queries=queries,
        page_size=page_size,
        max_pages=max_pages,
    )


def row(listing: dict[str, Any], refnr: str) -> dict[str, Any]:
    return next(r for r in listing["ergebnisliste"] if r["referenznummer"] == refnr)


def test_bundesagentur_normalizes_a_recorded_posting(
    details: dict[str, dict[str, Any]],
) -> None:
    detail = details[_PETAFUEL]

    normalized = make_adapter().normalize(detail)

    assert normalized.source_id == "bundesagentur"
    assert normalized.external_id == _PETAFUEL
    assert normalized.title == "iOS-Entwickler (m/w/d)"
    assert normalized.company_name == "petaFuel GmbH"
    assert normalized.url == f"https://www.arbeitsagentur.de/jobsuche/jobdetail/{_PETAFUEL}"
    assert normalized.country == "DE"
    assert normalized.city == "Freising"  # `ort` reads "Freising, Oberbayern": the town first
    assert normalized.location_raw == "Freising, Oberbayern, DEUTSCHLAND"
    # Date-only field (slice 13 rule): midnight UTC, never a fabricated time of day.
    assert normalized.posted_at == datetime(2026, 7, 28, tzinfo=UTC)
    expected = normalize_description(detail["stellenangebotsBeschreibung"])
    assert normalized.description == expected
    assert normalized.content_hash == content_hash(expected)


@pytest.mark.parametrize(
    ("refnr", "country", "city"),
    [
        (_STAMPAY, "DE", "Augsburg"),
        # Ten German places: the first one names the city, DEUTSCHLAND names the country.
        ("10001-1001883604-S", "DE", "Frankfurt am Main"),
        # The register also lists Austrian ads: DE is never defaulted, the town text decides.
        (_AUSTRIA, "AT", "Wien"),
    ],
    ids=["single-place", "many-places", "oesterreich"],
)
def test_bundesagentur_reads_country_only_from_deutschland(
    listing: dict[str, Any], refnr: str, country: str | None, city: str | None
) -> None:
    normalized = make_adapter().normalize(row(listing, refnr))

    assert (normalized.country, normalized.city) == (country, city)


def test_bundesagentur_strips_the_padded_firma(listing: dict[str, Any]) -> None:
    normalized = make_adapter().normalize(row(listing, "10001-1001883604-S"))

    assert normalized.company_name == "zollsoft GmbH"


def serving(
    listing: dict[str, Any],
    details: dict[str, dict[str, Any]],
    calls: list[httpx.URL],
    *,
    fail: frozenset[str] = frozenset(),
) -> Callable[[httpx.Request], httpx.Response]:
    """The recorded list for every query and page; details by base64 key — the recorded two,
    an empty-but-valid one for the rest, and a 404 for any refnr in `fail`."""
    by_key = {b64(r["referenznummer"]): r["referenznummer"] for r in listing["ergebnisliste"]}

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url)
        url = str(request.url.copy_with(query=None))
        if url == _LIST:
            return httpx.Response(200, json=listing)
        refnr = by_key[url.removeprefix(_DETAIL)]
        if refnr in fail:
            return httpx.Response(404, json={})
        return httpx.Response(200, json=details.get(refnr, {"referenznummer": refnr}))

    return handler


def b64(refnr: str) -> str:
    return b64encode(refnr.encode()).decode()


def detail_calls(calls: list[httpx.URL]) -> list[str]:
    return [str(u) for u in calls if str(u).startswith(_DETAIL)]


async def test_bundesagentur_fetches_detail_by_base64_refnr(
    listing: dict[str, Any], details: dict[str, dict[str, Any]]
) -> None:
    calls: list[httpx.URL] = []

    raw_postings = await make_adapter(serving(listing, details, calls)).fetch()

    assert f"{_DETAIL}MTAwMDEtMTAwMzQ1NjYxMC1T" in detail_calls(calls)  # the probed key
    petafuel = next(r for r in raw_postings if r["referenznummer"] == _PETAFUEL)
    assert petafuel["stellenangebotsBeschreibung"]


async def test_bundesagentur_dedups_by_refnr_before_the_detail_spend(
    listing: dict[str, Any], details: dict[str, dict[str, Any]]
) -> None:
    calls: list[httpx.URL] = []
    adapter = make_adapter(
        serving(listing, details, calls), queries=("iOS Entwickler", "iOS Developer")
    )

    raw_postings = await adapter.fetch()

    # Both queries return the same four refnrs: four detail calls, not eight.
    assert len(detail_calls(calls)) == len(listing["ergebnisliste"])
    assert len(raw_postings) == len(listing["ergebnisliste"])


async def test_bundesagentur_skips_a_failed_detail_and_continues(
    listing: dict[str, Any], details: dict[str, dict[str, Any]], caplog: pytest.LogCaptureFixture
) -> None:
    calls: list[httpx.URL] = []
    handler = serving(listing, details, calls, fail=frozenset({_STAMPAY}))

    with caplog.at_level("INFO"):
        raw_postings = await make_adapter(handler).fetch()

    refnrs = {r["referenznummer"] for r in raw_postings}
    assert _STAMPAY not in refnrs
    assert len(refnrs) == len(listing["ergebnisliste"]) - 1
    assert f"bundesagentur_detail_skipped refnr={_STAMPAY}" in caplog.text


async def test_bundesagentur_stops_at_the_page_cap_and_logs_it(
    listing: dict[str, Any], caplog: pytest.LogCaptureFixture
) -> None:
    pages: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url.copy_with(query=None)) != _LIST:
            return httpx.Response(200, json={})
        page = request.url.params["page"]
        pages.append(page)
        rows = [
            {**r, "referenznummer": f"{r['referenznummer']}-p{page}"}
            for r in listing["ergebnisliste"]
        ]
        return httpx.Response(200, json={**listing, "ergebnisliste": rows, "maxErgebnisse": 99})

    with caplog.at_level("INFO"):
        await make_adapter(handler, page_size=4, max_pages=2).fetch()

    assert pages == ["1", "2"]
    assert "bundesagentur_page_cap query=iOS Entwickler fetched=8 total=99" in caplog.text


async def test_bundesagentur_stops_paging_at_a_short_page(
    listing: dict[str, Any], details: dict[str, dict[str, Any]], caplog: pytest.LogCaptureFixture
) -> None:
    calls: list[httpx.URL] = []

    with caplog.at_level("INFO"):
        await make_adapter(serving(listing, details, calls), page_size=25, max_pages=3).fetch()

    assert [u.params["page"] for u in calls if "page" in u.params] == ["1"]
    assert "bundesagentur_page_cap" not in caplog.text
