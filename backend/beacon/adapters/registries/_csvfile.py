"""One place for the CSV-reading contract shared by every registry ingester:
newline="" is the csv module's requirement, utf-8-sig drops a BOM if present."""

import csv
from collections.abc import Iterator
from pathlib import Path


def iter_rows(path: Path) -> Iterator[dict[str, str | None]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        yield from csv.DictReader(handle)


def iter_rows_below_banner(path: Path, *, header_column: str) -> Iterator[dict[str, str | None]]:
    """iter_rows for a publisher that prints a title banner above the header row — the CA
    LMIA export opens with a one-cell sentence naming the quarter, so DictReader would take
    that sentence as the header and every column name would be wrong.

    Rows are skipped until the one that carries header_column, which becomes the header. A
    file whose header never appears raises ValueError rather than quietly yielding rows keyed
    on junk: a registry snapshot we cannot read is a refresh that must fail loudly.
    """
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.reader(handle):
            names = [cell.strip() for cell in row]
            if header_column in names:
                yield from csv.DictReader(handle, fieldnames=names)
                return
    raise ValueError(f"no header row containing {header_column!r} in {path}")
