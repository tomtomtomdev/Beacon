"""Manual location-parse spot check — the data-correctness gate on the city table.

`CITY_TO_COUNTRY` is reference data in the same risk class as the company-name
normalizer, so it is read the same way: run this after ANY change to the table or to
`parse_location`, and eyeball the diff before the backfill keeps it.

    cd backend && uv run python scripts/spot_check_locations.py
    cd backend && uv run python scripts/spot_check_locations.py --limit 40

Reads the local beacon.db and writes nothing — the backfill is `beacon.relocate`. Three
sections, in the order they deserve attention:

  DISAGREEMENTS  the parser contradicts a country an adapter already stored. Must be
                 empty, or near it: an adapter that read a structured address field
                 outranks a re-parse of free text.
  HQ TIE-BREAK   the rows where a shared city name was settled by the employer's home
                 market. This is the only inference in the table; read every line.
  FILLED         rows that gain a country, grouped by the string that produced them.
"""

import argparse
import sqlite3
from collections import Counter
from pathlib import Path

from beacon.adapters.persistence.db import connect
from beacon.config import Settings
from beacon.domain.location import parse_location

_SQL = """
    SELECT jobs.location_raw AS raw, jobs.country AS stored, companies.country_hq AS hq,
           companies.name AS company
    FROM jobs
    JOIN companies ON companies.id = jobs.company_id
    WHERE jobs.canonical_id IS NULL AND jobs.closed_at IS NULL
"""


def _render(title: str, rows: Counter[tuple[str, ...]], limit: int) -> None:
    print(f"\n{title}  ({sum(rows.values())} jobs, {len(rows)} distinct)")
    print("-" * 96)
    for cells, n in rows.most_common(limit):
        print(f"{n:>5}  " + "  ".join(f"{c:<28}" for c in cells))
    if len(rows) > limit:
        print(f"       … {len(rows) - limit} more")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Re-parse every location in the local DB.")
    parser.add_argument("--limit", type=int, default=25, help="rows shown per section")
    parser.add_argument("--db", type=Path, help="override the database path")
    args = parser.parse_args(argv)

    settings = Settings.from_env()
    with connect(args.db or settings.db_path) as conn:
        conn.row_factory = sqlite3.Row
        jobs = conn.execute(_SQL).fetchall()

    filled: Counter[tuple[str, ...]] = Counter()
    tiebreak: Counter[tuple[str, ...]] = Counter()
    disagree: Counter[tuple[str, ...]] = Counter()
    uncountried = residue = 0
    for job in jobs:
        country, city = parse_location(job["raw"], job["hq"])
        if job["stored"] is None:
            uncountried += 1
        if country is None:
            residue += 1 if job["stored"] is None else 0
            continue
        if job["stored"] is None:
            filled[(job["raw"], country, city or "—")] += 1
            # Decided by the employer, not by the string: the same parse without an hq
            # yields nothing. That is the only inference in the table, so it is listed.
            if parse_location(job["raw"])[0] is None:
                tiebreak[(job["raw"], f"hq={job['hq']} → {country}", job["company"])] += 1
        elif job["stored"] != country:
            disagree[(job["raw"], f"stored={job['stored']} parsed={country}", job["company"])] += 1

    _render("DISAGREEMENTS — an adapter already said otherwise", disagree, args.limit)
    _render("HQ TIE-BREAK — the only inference in the table", tiebreak, args.limit)
    _render("FILLED — rows that gain a country", filled, args.limit)

    total = len(jobs)
    after = uncountried - sum(filled.values())
    print("-" * 96)
    print(f"canonical open jobs   {total}")
    print(f"uncountried before    {uncountried} ({uncountried / total:.1%})")
    print(f"uncountried after     {after} ({after / total:.1%})   filled {sum(filled.values())}")
    print(f"residue               {residue} rows that still name no country")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
