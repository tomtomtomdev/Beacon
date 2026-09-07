"""probe_candidate — the evidence a seed row needs (slice 15b).

Slices 13 and 14 probed every candidate board by hand before writing an adapter, and those
probes are what killed The Muse and Breezy HR. This is that discipline as a use case: it runs
the real adapter through the real classifier and reports what Beacon would actually ingest,
which is the thing a curl of the board cannot answer.
"""

from beacon.adapters.classify.heuristic import HeuristicClassifier
from beacon.application.ports import RawPosting
from beacon.application.probe import probe_candidate
from beacon.domain.classification import Category
from beacon.domain.company import Company
from beacon.domain.descriptions import content_hash
from beacon.domain.job import NormalizedJob

CANDIDATE = Company(
    name="Mercari", ats_type="greenhouse", ats_slug="mercari", country_hq="JP", priority=2
)


def make_job(
    external_id: str, title: str, *, description: str = "Ship the app.", country: str | None = "JP"
) -> NormalizedJob:
    return NormalizedJob(
        source_id="greenhouse",
        external_id=external_id,
        title=title,
        url=f"https://example.test/{external_id}",
        description=description,
        location_raw=country or "",
        country=country,
        city=None,
        posted_at=None,
        content_hash=content_hash(description),
    )


class FakeBoard:
    """A JobSource over canned (raw -> NormalizedJob) pairs; a raw marked bad blows up."""

    source_id = "greenhouse"

    def __init__(self, jobs: list[NormalizedJob], *, bad: int = 0) -> None:
        self._jobs = {job.external_id: job for job in jobs}
        self._bad: list[RawPosting] = [{"id": f"bad-{i}", "bad": True} for i in range(bad)]

    async def fetch(self) -> list[RawPosting]:
        good: list[RawPosting] = [{"id": job_id} for job_id in self._jobs]
        return good + self._bad

    def normalize(self, raw: RawPosting) -> NormalizedJob:
        if raw.get("bad"):
            raise KeyError("malformed posting")
        return self._jobs[str(raw["id"])]


async def test_a_live_board_reports_the_density_of_the_focus_role() -> None:
    board = FakeBoard(
        [
            make_job("1", "Senior iOS Engineer"),
            make_job("2", "iOS Engineer, Payments"),
            make_job("3", "Staff Backend Engineer (Java)", country="SG"),
        ]
    )

    probe = await probe_candidate(CANDIDATE, lambda _: board, HeuristicClassifier())

    assert probe is not None
    assert (probe.fetched, probe.normalized, probe.errors) == (3, 3, 0)
    assert probe.categories[Category.IOS] == 2
    assert probe.categories[Category.BACKEND] == 1
    assert probe.countries == {"JP": 2, "SG": 1}
    # A count with no titles behind it cannot be sanity-checked — which is exactly how
    # Rippling's 376 postings read as reach until someone looked (slice 14).
    assert probe.focus_titles == ("Senior iOS Engineer", "iOS Engineer, Payments")


async def test_a_board_whose_rows_carry_no_ad_text_reports_zero_usable_postings() -> None:
    # Breezy HR's failure mode: 200 OK, rows with id/title/location and no ad text at all,
    # so every posting lands with no sponsorship tier and no resume score. Row count is not
    # reach, and the probe has to say so rather than counting the rows.
    board = FakeBoard([make_job(str(i), "iOS Engineer", description="") for i in range(3)])

    probe = await probe_candidate(CANDIDATE, lambda _: board, HeuristicClassifier())

    assert probe is not None
    assert probe.normalized == 3
    assert probe.with_text == 0


async def test_one_malformed_posting_never_kills_the_probe() -> None:
    board = FakeBoard([make_job("1", "iOS Engineer")], bad=2)

    probe = await probe_candidate(CANDIDATE, lambda _: board, HeuristicClassifier())

    assert probe is not None
    assert (probe.fetched, probe.normalized, probe.errors) == (3, 1, 2)


async def test_a_title_with_no_recognized_role_is_residue_not_a_category() -> None:
    board = FakeBoard([make_job("1", "Mobile Engineer"), make_job("2", "iOS Engineer")])

    probe = await probe_candidate(CANDIDATE, lambda _: board, HeuristicClassifier())

    assert probe is not None
    # The category comes from the title alone, so "Mobile Engineer" classifies as nothing —
    # the reason slice 15a left that phrasing out of ROLE_QUERIES.
    assert probe.unclassified == 1
    assert probe.categories[Category.IOS] == 1


async def test_a_candidate_whose_ats_type_has_no_adapter_probes_to_nothing() -> None:
    dormant = Company(
        name="Linktree", ats_type="gem", ats_slug="linktree", country_hq="AU", priority=3
    )

    assert await probe_candidate(dormant, lambda _: None, HeuristicClassifier()) is None
