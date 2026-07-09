"""build_health_alerts translates quarantined companies + stale registry snapshots into the
digest's health section (SPEC §7). Healthy state contributes nothing."""

import sqlite3
from datetime import UTC, datetime, timedelta

from beacon.adapters.persistence.companies import SqliteCompanyRepo
from beacon.adapters.persistence.registries_meta import SqliteRegistriesMetaRepo
from beacon.application.health_report import build_health_alerts
from beacon.domain.company import Company
from beacon.domain.health import FailureKind, Health, SourceHealth
from beacon.domain.registry import REGISTRY_STALE_AFTER_DAYS

NOW = datetime(2026, 7, 9, 6, 0, tzinfo=UTC)
LAST_OK = datetime(2026, 6, 1, 6, 0, tzinfo=UTC)


def seed(db: sqlite3.Connection, name: str, slug: str) -> int:
    company = SqliteCompanyRepo(db).upsert(
        Company(name=name, ats_type="greenhouse", ats_slug=slug, country_hq="IE", priority=2)
    )
    assert company.id is not None
    return company.id


def test_quarantined_company_becomes_a_health_alert_with_reason_and_since(
    db: sqlite3.Connection,
) -> None:
    repo = SqliteCompanyRepo(db)
    healthy = seed(db, "Healthy", "healthy")  # noqa: F841 - present but must not alert
    sick = seed(db, "Crypto", "crypto")
    repo.set_health(
        sick,
        SourceHealth(
            consecutive_failures=3,
            health=Health.QUARANTINED,
            reason=FailureKind.GONE,
            last_success_at=LAST_OK,
        ),
    )

    alerts, stale = build_health_alerts(repo, SqliteRegistriesMetaRepo(db), now=NOW)

    assert stale == ()
    assert [(a.company, a.reason, a.since) for a in alerts] == [("Crypto", "gone", "2026-06-01")]


def test_quarantined_never_polled_reports_since_never(db: sqlite3.Connection) -> None:
    repo = SqliteCompanyRepo(db)
    sick = seed(db, "Crypto", "crypto")
    repo.set_health(
        sick,
        SourceHealth(consecutive_failures=3, health=Health.QUARANTINED, reason=FailureKind.GONE),
    )

    alerts, _ = build_health_alerts(repo, SqliteRegistriesMetaRepo(db), now=NOW)

    assert alerts[0].since == "never"


def test_stale_registry_snapshot_becomes_a_warning(db: sqlite3.Connection) -> None:
    repo = SqliteCompanyRepo(db)
    meta_repo = SqliteRegistriesMetaRepo(db)
    fresh_at = NOW - timedelta(days=10)
    stale_at = NOW - timedelta(days=REGISTRY_STALE_AFTER_DAYS + 5)
    meta_repo.record("NL", fresh_at, 100)
    meta_repo.record("UK", stale_at, 200)

    _, stale = build_health_alerts(repo, meta_repo, now=NOW)

    assert [(s.registry, s.fetched_at) for s in stale] == [("UK", stale_at.date().isoformat())]


def test_all_healthy_produces_no_alerts(db: sqlite3.Connection) -> None:
    repo = SqliteCompanyRepo(db)
    seed(db, "Healthy", "healthy")

    assert build_health_alerts(repo, SqliteRegistriesMetaRepo(db), now=NOW) == ((), ())
