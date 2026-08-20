"""Manual demand spot-check — which role families are actually in demand, not just loud.

Ranking roles by raw posting count answers "which employer has the biggest org": in the
current corpus ten companies own ~60% of the postings, so a single employer hiring a whole
team outranks ten employers hiring one engineer each. This prints the company-normalized
view instead — every firm's contribution to a role is capped, breadth across employers
wins, and each row carries the concentration that produced it:

    cd backend && uv run python scripts/spot_check_demand.py
    cd backend && uv run python scripts/spot_check_demand.py --category ai-ml --cap 2

Reads the local beacon.db (no network). SCORE is the capped demand, FIRMS the distinct
employers, and TOP the largest single contributor — a row whose TOP share is high is a
fact about that employer, not about the market. Ranking logic is pure and lives in
domain/demand.py; this file is wiring only.
"""

import argparse
import sqlite3
from pathlib import Path

from beacon.adapters.persistence.db import connect
from beacon.config import Settings
from beacon.domain.demand import DemandRow, RolePosting, rank_roles

# Duplicates hang off their canonical via canonical_id — counting both would double-count
# the same opening, exactly as the /jobs list excludes them.
_SQL = """
    SELECT companies.name AS company, jobs.title AS title
    FROM jobs
    JOIN companies ON companies.id = jobs.company_id
    WHERE jobs.canonical_id IS NULL
"""
_CATEGORY_CLAUSE = " AND (',' || COALESCE(jobs.categories, '') || ',') LIKE ?"


def _postings(conn: sqlite3.Connection, category: str | None) -> list[RolePosting]:
    sql = _SQL + (_CATEGORY_CLAUSE if category else "")
    params = (f"%,{category},%",) if category else ()
    return [RolePosting(row["company"], row["title"]) for row in conn.execute(sql, params)]


def _render(rows: list[DemandRow], total: int, limit: int) -> None:
    print(f"{'#':>3}  {'Role family':38} {'Score':>5} {'Firms':>5} {'Posts':>5}  Top poster")
    print("-" * 96)
    for i, row in enumerate(rows[:limit], 1):
        top = f"{row.top_firm[:22]} ({row.top_firm_share:.0%})"
        print(f"{i:>3}  {row.role[:38]:38} {row.score:>5} {row.firms:>5} {row.postings:>5}  {top}")
    print("-" * 96)
    shown = min(limit, len(rows))
    print(f"showing {shown}/{len(rows)} role families over {total} canonical postings")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Company-normalized role-demand ranking over the local beacon.db."
    )
    parser.add_argument("--category", help="restrict to one category (e.g. ai-ml, backend, ios)")
    parser.add_argument(
        "--cap",
        type=int,
        default=3,
        help="max postings any one firm contributes to a role's score (default 3)",
    )
    parser.add_argument(
        "--min-firms",
        type=int,
        default=2,
        help="drop roles fewer than this many firms post (default 2)",
    )
    parser.add_argument("--limit", type=int, default=25, help="role families to show (default 25)")
    parser.add_argument("--db", type=Path, help="override the beacon.db path")
    args = parser.parse_args(argv)

    conn = connect(args.db or Settings.from_env().db_path)
    try:
        postings = _postings(conn, args.category)
    finally:
        conn.close()

    rows = rank_roles(postings, cap=args.cap, min_firms=args.min_firms)
    _render(rows, len(postings), args.limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
