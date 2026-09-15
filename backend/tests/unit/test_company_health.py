"""The source-health rollup (`get_company_health`) as the globe widget consumes it (DESIGN §1):
summary counts, and the latest successful poll across every seed company.

The per-company rows and the pending/shadow rules are covered end-to-end in tests/api/
test_companies.py; what lives here is the rollup arithmetic, which needs no DB."""

from datetime import UTC, datetime

from beacon.application.company_health import get_company_health
from beacon.application.ports import CompanyHealth, CompanyRepo
from beacon.domain.health import Health
from tests.unit.fakes import StubCompanyRepo

SUPPORTED = frozenset({"greenhouse", "lever"})

EARLY = datetime(2026, 9, 15, 1, 0, tzinfo=UTC)
LATE = datetime(2026, 9, 15, 5, 0, tzinfo=UTC)


def company(
    name: str, *, ats_type: str = "greenhouse", last_success_at: datetime | None = None
) -> CompanyHealth:
    return CompanyHealth(
        name=name,
        ats_type=ats_type,
        ats_slug=name.lower(),
        country_hq="IE",
        health=Health.OK.value,
        reason=None,
        last_success_at=last_success_at,
        consecutive_failures=0,
    )


def test_summary_carries_the_latest_successful_poll() -> None:
    repo: CompanyRepo = StubCompanyRepo(
        health=[
            company("Early", last_success_at=EARLY),
            company("Late", ats_type="lever", last_success_at=LATE),
            company("NeverPolled"),
        ]
    )

    view = get_company_health(repo, SUPPORTED)

    assert view.summary.last_poll_at == LATE


def test_last_poll_at_is_none_when_nothing_has_ever_polled() -> None:
    # A box that has never run a poll must render no time at all — not epoch, not "now".
    repo: CompanyRepo = StubCompanyRepo(health=[company("Fresh"), company("AlsoFresh")])

    view = get_company_health(repo, SUPPORTED)

    assert view.summary.last_poll_at is None
