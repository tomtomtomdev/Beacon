"""One place for the CSV-reading contract shared by every registry ingester:
newline="" is the csv module's requirement, utf-8-sig drops a BOM if present."""

import csv
from collections.abc import Iterator
from pathlib import Path


def iter_rows(path: Path) -> Iterator[dict[str, str | None]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        yield from csv.DictReader(handle)
