"""Seed-file parsing. Schema pinned: name,ats_type,ats_slug,country_hq,priority."""

import csv
import io

from beacon.domain.company import Company


def parse_seed_csv(text: str) -> list[Company]:
    return [
        Company(
            name=row["name"],
            ats_type=row["ats_type"],
            ats_slug=row["ats_slug"],
            country_hq=row["country_hq"],
            priority=int(row["priority"]),
        )
        for row in csv.DictReader(io.StringIO(text))
    ]
