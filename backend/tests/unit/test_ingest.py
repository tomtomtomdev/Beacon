from datetime import UTC, datetime

import pytest

from beacon.application.ingest import ingest_all, ingest_source
from beacon.application.ports import JobFilters, JobPage, RawPosting
from beacon.domain.company import Company
from beacon.domain.job import NormalizedJob

NOW = datetime(2026, 7, 4, 12, 0, tzinfo=UTC)


def make_job(external_id: str) -> NormalizedJob:
    return NormalizedJob(
        source_id="greenhouse",
        external_id=external_id,
        title=f"Engineer {external_id}",
        url=f"https://example.test/{external_id}",
        description="Build things.",
        location_raw="Dublin, Ireland",
        country="IE",
        city="Dublin",
        posted_at=None,
        content_hash="a" * 64,
    )


class FakeSource:
    """JobSource whose normalize blows up on any payload marked bad."""

    source_id = "greenhouse"

    def __init__(self, raws: list[RawPosting]) -> None:
        self._raws = raws

    async def fetch(self) -> list[RawPosting]:
        return self._raws

    def normalize(self, raw: RawPosting) -> NormalizedJob:
        if raw.get("bad"):
            raise KeyError("malformed posting")
        return make_job(str(raw["id"]))


class FakeJobRepo:
    def __init__(self) -> None:
        self.upserts: list[tuple[int, NormalizedJob, datetime]] = []

    def upsert(self, company_id: int, job: NormalizedJob, seen_at: datetime) -> None:
        self.upserts.append((company_id, job, seen_at))

    def search(self, filters: JobFilters) -> JobPage:
        raise NotImplementedError("ingest never searches")


COMPANY = Company(
    name="Tines", ats_type="greenhouse", ats_slug="tines", country_hq="IE", priority=2, id=7
)


async def test_ingest_source_upserts_every_fetched_posting() -> None:
    repo = FakeJobRepo()
    source = FakeSource([{"id": 1}, {"id": 2}, {"id": 3}])

    result = await ingest_source(source, COMPANY, repo, now=NOW)

    assert (result.fetched, result.upserted, result.errors) == (3, 3, 0)
    assert [(cid, job.external_id, seen) for cid, job, seen in repo.upserts] == [
        (7, "1", NOW),
        (7, "2", NOW),
        (7, "3", NOW),
    ]


async def test_one_bad_posting_never_blocks_the_poll() -> None:
    repo = FakeJobRepo()
    source = FakeSource([{"id": 1}, {"id": 2, "bad": True}, {"id": 3}])

    result = await ingest_source(source, COMPANY, repo, now=NOW)

    assert (result.fetched, result.upserted, result.errors) == (3, 2, 1)
    assert [job.external_id for _, job, _ in repo.upserts] == ["1", "3"]


async def test_ingest_requires_persisted_company() -> None:
    unsaved = Company(
        name="Tines", ats_type="greenhouse", ats_slug="tines", country_hq="IE", priority=2
    )

    with pytest.raises(ValueError, match="persisted"):
        await ingest_source(FakeSource([]), unsaved, FakeJobRepo(), now=NOW)


def make_company(name: str, ats_type: str, company_id: int) -> Company:
    return Company(
        name=name,
        ats_type=ats_type,
        ats_slug=name.lower(),
        country_hq="US",
        priority=1,
        id=company_id,
    )


async def test_ingest_all_skips_unsupported_ats() -> None:
    supported = make_company("Tines", "greenhouse", 1)
    dormant = make_company("Grab", "smartrecruiters", 2)
    repo = FakeJobRepo()
    fetch_calls: list[str] = []

    def source_for(company: Company) -> FakeSource | None:
        if company.ats_type != "greenhouse":
            return None
        source = FakeSource([{"id": 1}])
        original_fetch = source.fetch

        async def counting_fetch() -> list[RawPosting]:
            fetch_calls.append(company.name)
            return await original_fetch()

        source.fetch = counting_fetch  # type: ignore[method-assign]  # test spy
        return source

    results = await ingest_all([supported, dormant], repo, source_for, now=NOW)

    assert fetch_calls == ["Tines"]
    assert set(results) == {"Tines"}
    assert [cid for cid, _, _ in repo.upserts] == [1]


async def test_ingest_all_continues_when_one_company_fetch_fails() -> None:
    first = make_company("Aaa", "greenhouse", 1)
    second = make_company("Bbb", "greenhouse", 2)
    repo = FakeJobRepo()

    class ExplodingSource(FakeSource):
        async def fetch(self) -> list[RawPosting]:
            raise ConnectionError("board unreachable")

    def source_for(company: Company) -> FakeSource:
        return ExplodingSource([]) if company.name == "Aaa" else FakeSource([{"id": 9}])

    results = await ingest_all([first, second], repo, source_for, now=NOW)

    assert set(results) == {"Bbb"}
    assert [job.external_id for _, job, _ in repo.upserts] == ["9"]
