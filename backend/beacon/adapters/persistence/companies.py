import sqlite3
from datetime import datetime

from beacon.domain.company import Company
from beacon.domain.health import FailureKind, Health, SourceHealth

_SELECT_COLUMNS = (
    "id, name, ats_type, ats_slug, country_hq, priority, registry_flags, match_confidence"
)

# On re-seed, a changed ATS type/slug means the source moved and was fixed by hand — reset
# health so a quarantined board recovers on the next poll (SPEC §7: recovery is a data edit).
# Compares the stored row (unqualified/companies.*) against the incoming row (excluded.*).
_ATS_CHANGED = "companies.ats_type != excluded.ats_type OR companies.ats_slug != excluded.ats_slug"


class SqliteCompanyRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def upsert(self, company: Company) -> Company:
        """Insert by unique name, or refresh the seedable fields; returns the persisted row.

        Registry columns are deliberately untouched here — refresh owns them, so re-seeding
        never wipes a company's flags."""
        self._conn.execute(
            """
            INSERT INTO companies (name, ats_type, ats_slug, country_hq, priority)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (name) DO UPDATE SET
                ats_type = excluded.ats_type,
                ats_slug = excluded.ats_slug,
                country_hq = excluded.country_hq,
                priority = excluded.priority,
                health = CASE WHEN {changed} THEN 'ok' ELSE health END,
                consecutive_failures =
                    CASE WHEN {changed} THEN 0 ELSE consecutive_failures END,
                quarantine_reason = CASE WHEN {changed} THEN NULL ELSE quarantine_reason END,
                last_success_at =
                    CASE WHEN {changed} THEN NULL ELSE last_success_at END
            """.format(changed=_ATS_CHANGED),
            (
                company.name,
                company.ats_type,
                company.ats_slug,
                company.country_hq,
                company.priority,
            ),
        )
        self._conn.commit()
        row = self._conn.execute(
            f"SELECT {_SELECT_COLUMNS} FROM companies WHERE name = ?",
            (company.name,),
        ).fetchone()
        return _row_to_company(row)

    def get_or_create(self, company: Company) -> Company:
        """Insert only if the name is new; a name already present (a seed) is returned
        untouched, so its real ats_type/registry_flags survive a company-less poll."""
        self._conn.execute(
            """
            INSERT INTO companies (name, ats_type, ats_slug, country_hq, priority)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (name) DO NOTHING
            """,
            (
                company.name,
                company.ats_type,
                company.ats_slug,
                company.country_hq,
                company.priority,
            ),
        )
        self._conn.commit()
        row = self._conn.execute(
            f"SELECT {_SELECT_COLUMNS} FROM companies WHERE name = ?",
            (company.name,),
        ).fetchone()
        return _row_to_company(row)

    def list_active(self) -> list[Company]:
        rows = self._conn.execute(
            f"SELECT {_SELECT_COLUMNS} FROM companies WHERE active = 1 ORDER BY priority, name"
        ).fetchall()
        return [_row_to_company(row) for row in rows]

    def get_by_name(self, name: str) -> Company | None:
        row = self._conn.execute(
            f"SELECT {_SELECT_COLUMNS} FROM companies WHERE name = ?", (name,)
        ).fetchone()
        return _row_to_company(row) if row is not None else None

    def set_registry_match(
        self, company_id: int, flags: int, confidence: float | None, evidence: str | None
    ) -> None:
        self._conn.execute(
            "UPDATE companies SET registry_flags = ?, match_confidence = ?, match_evidence = ?"
            " WHERE id = ?",
            (flags, confidence, evidence, company_id),
        )
        self._conn.commit()

    def get_health(self, company_id: int) -> SourceHealth:
        row = self._conn.execute(
            "SELECT consecutive_failures, health, quarantine_reason, last_success_at"
            " FROM companies WHERE id = ?",
            (company_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"unknown company id={company_id}")
        return _row_to_health(row)

    def set_health(self, company_id: int, health: SourceHealth) -> None:
        self._conn.execute(
            "UPDATE companies SET consecutive_failures = ?, health = ?,"
            " quarantine_reason = ?, last_success_at = ? WHERE id = ?",
            (
                health.consecutive_failures,
                health.health.value,
                health.reason.value if health.reason else None,
                health.last_success_at.isoformat() if health.last_success_at else None,
                company_id,
            ),
        )
        self._conn.commit()

    def list_quarantined(self) -> list[Company]:
        """The quarantined seed companies — the weekly probe's retry list."""
        rows = self._conn.execute(
            f"SELECT {_SELECT_COLUMNS} FROM companies"
            " WHERE health = ? AND active = 1 ORDER BY priority, name",
            (Health.QUARANTINED.value,),
        ).fetchall()
        return [_row_to_company(row) for row in rows]


def _row_to_health(row: sqlite3.Row) -> SourceHealth:
    reason = row["quarantine_reason"]
    last_success = row["last_success_at"]
    return SourceHealth(
        consecutive_failures=row["consecutive_failures"],
        health=Health(row["health"]),
        reason=FailureKind(reason) if reason else None,
        last_success_at=datetime.fromisoformat(last_success) if last_success else None,
    )


def _row_to_company(row: sqlite3.Row) -> Company:
    return Company(
        name=row["name"],
        ats_type=row["ats_type"],
        ats_slug=row["ats_slug"],
        country_hq=row["country_hq"],
        priority=row["priority"],
        id=row["id"],
        registry_flags=row["registry_flags"],
        match_confidence=row["match_confidence"],
    )
