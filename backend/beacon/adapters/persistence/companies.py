import sqlite3

from beacon.domain.company import Company

_SELECT_COLUMNS = (
    "id, name, ats_type, ats_slug, country_hq, priority, registry_flags, match_confidence"
)


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
                priority = excluded.priority
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
