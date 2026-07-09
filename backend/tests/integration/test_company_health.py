"""Company health persistence (SPEC §7): the SqliteCompanyRepo reads/writes the health
columns, lists quarantined sources for the probe, and — crucially — a slug/ATS change on
re-seed resets health so recovery from a moved board is a pure data edit (no code)."""

import sqlite3
from datetime import UTC, datetime

from beacon.adapters.persistence.companies import SqliteCompanyRepo
from beacon.domain.company import Company
from beacon.domain.health import FailureKind, Health, SourceHealth

NOW = datetime(2026, 7, 9, 6, 0, tzinfo=UTC)


def seed(db: sqlite3.Connection, name: str = "Tines", slug: str = "tines") -> int:
    company = SqliteCompanyRepo(db).upsert(
        Company(name=name, ats_type="greenhouse", ats_slug=slug, country_hq="IE", priority=2)
    )
    assert company.id is not None
    return company.id


def quarantine(repo: SqliteCompanyRepo, company_id: int) -> None:
    repo.set_health(
        company_id,
        SourceHealth(
            consecutive_failures=3,
            health=Health.QUARANTINED,
            reason=FailureKind.GONE,
            last_success_at=NOW,
        ),
    )


def test_fresh_company_health_defaults_to_ok(db: sqlite3.Connection) -> None:
    repo = SqliteCompanyRepo(db)
    company_id = seed(db)

    assert repo.get_health(company_id) == SourceHealth()


def test_set_and_get_health_roundtrips(db: sqlite3.Connection) -> None:
    repo = SqliteCompanyRepo(db)
    company_id = seed(db)
    state = SourceHealth(
        consecutive_failures=2,
        health=Health.DEGRADED,
        reason=FailureKind.UNREACHABLE,
        last_success_at=NOW,
    )

    repo.set_health(company_id, state)

    assert repo.get_health(company_id) == state


def test_list_quarantined_returns_only_quarantined_companies(db: sqlite3.Connection) -> None:
    repo = SqliteCompanyRepo(db)
    healthy = seed(db, "Healthy", "healthy")
    sick = seed(db, "Sick", "sick")
    quarantine(repo, sick)

    quarantined = repo.list_quarantined()

    assert [c.name for c in quarantined] == ["Sick"]
    assert healthy not in [c.id for c in quarantined]


def test_reslug_on_reseed_resets_health(db: sqlite3.Connection) -> None:
    # Recovery from a moved board: fix the slug in the CSV, next re-seed clears quarantine.
    repo = SqliteCompanyRepo(db)
    company_id = seed(db)
    quarantine(repo, company_id)

    repo.upsert(
        Company(
            name="Tines", ats_type="greenhouse", ats_slug="tines-new", country_hq="IE", priority=2
        )
    )

    assert repo.get_health(company_id) == SourceHealth()


def test_unchanged_reseed_preserves_health(db: sqlite3.Connection) -> None:
    # A routine re-seed (same slug) must NOT un-quarantine — every run re-seeds from the CSV.
    repo = SqliteCompanyRepo(db)
    company_id = seed(db)
    quarantine(repo, company_id)

    repo.upsert(
        Company(name="Tines", ats_type="greenhouse", ats_slug="tines", country_hq="IE", priority=2)
    )

    assert repo.get_health(company_id).health is Health.QUARANTINED
