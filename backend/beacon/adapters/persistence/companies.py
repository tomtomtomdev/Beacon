import sqlite3

from beacon.domain.company import Company


class SqliteCompanyRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def upsert(self, company: Company) -> Company:
        """Insert by unique name, or refresh the seedable fields; returns the persisted row."""
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
            "SELECT id, name, ats_type, ats_slug, country_hq, priority"
            " FROM companies WHERE name = ?",
            (company.name,),
        ).fetchone()
        return _row_to_company(row)

    def list_active(self) -> list[Company]:
        rows = self._conn.execute(
            "SELECT id, name, ats_type, ats_slug, country_hq, priority"
            " FROM companies WHERE active = 1 ORDER BY priority, name"
        ).fetchall()
        return [_row_to_company(row) for row in rows]


def _row_to_company(row: sqlite3.Row) -> Company:
    return Company(
        name=row["name"],
        ats_type=row["ats_type"],
        ats_slug=row["ats_slug"],
        country_hq=row["country_hq"],
        priority=row["priority"],
        id=row["id"],
    )
