"""IE DETE register of employment permits issued to companies (monthly XLSX → CSV).

Ireland publishes the permits it actually *issued*, not a licensed-sponsor list: an
employer appearing here has sponsored someone this year, which is stronger evidence than
eligibility. One row per employer, with the publisher's own monthly columns and a grand
total, so there is nothing to aggregate — the count goes straight into the evidence line.

Real-file hazards handled: leading whitespace in published names, "T/A <brand>" trading-as
segments (Irish registers use the abbreviation, not the word), and the empty trailing row
an Excel export leaves behind.
"""

from pathlib import Path

from beacon.adapters.registries._csvfile import iter_rows
from beacon.adapters.registries._evidence import counted
from beacon.domain.matching import split_trading_as
from beacon.domain.registry import Registry, RegistryCompany

_NAME_COLUMN = "Employer Name"
_TOTAL_COLUMN = "Permits Issued Grand Total"


class IEPermitsRegistry:
    registry = Registry.IE

    def __init__(self, path: Path) -> None:
        self._path = path

    def fetch(self) -> list[RegistryCompany]:
        companies: list[RegistryCompany] = []
        for row in iter_rows(self._path):
            raw = (row.get(_NAME_COLUMN) or "").strip()
            if not raw:
                continue  # export padding
            legal, aliases = split_trading_as(raw)
            permits = int((row.get(_TOTAL_COLUMN) or "0").strip() or 0)
            companies.append(
                RegistryCompany(
                    name=legal,
                    aliases=aliases,
                    evidence=f"{counted(permits, 'employment permit')} issued",
                )
            )
        return companies
