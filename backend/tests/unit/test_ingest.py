from datetime import UTC, datetime

import pytest

from beacon.application.ingest import ingest_source
from beacon.application.ports import RawPosting
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
