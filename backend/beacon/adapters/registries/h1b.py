"""US H-1B LCA disclosure file (quarterly XLSX exported to CSV).

Only Certified / Certified-Withdrawn rows are sponsorship evidence; Denied/Withdrawn
contribute nothing. Rows with an empty employer are the sheet's padding (openpyxl's
max_row lies) and are skipped. Filings are aggregated per employer so a 3,000-filing
Google reads differently from a 2-filing startup. The brand can hide in an embedded
"dba X" in EMPLOYER_NAME or in the separate TRADE_NAME_DBA column — both become aliases.
"""

from dataclasses import dataclass, field
from pathlib import Path

from beacon.adapters.registries._csvfile import iter_rows
from beacon.domain.matching import split_trading_as
from beacon.domain.registry import Registry, RegistryCompany

_CERTIFIED_STATUSES = frozenset({"Certified", "Certified - Withdrawn"})
_NAME_COLUMN = "EMPLOYER_NAME"
_STATUS_COLUMN = "CASE_STATUS"
_DBA_COLUMN = "TRADE_NAME_DBA"


@dataclass(slots=True)
class _Employer:
    certified: int = 0
    dba_aliases: set[str] = field(default_factory=set)


class H1BLCARegistry:
    registry = Registry.US

    def __init__(self, path: Path) -> None:
        self._path = path

    def fetch(self) -> list[RegistryCompany]:
        employers: dict[str, _Employer] = {}
        for row in iter_rows(self._path):
            name = (row.get(_NAME_COLUMN) or "").strip()
            if not name:
                continue  # padding row
            if (row.get(_STATUS_COLUMN) or "").strip() not in _CERTIFIED_STATUSES:
                continue  # Denied/Withdrawn is not sponsorship evidence
            employer = employers.setdefault(name, _Employer())
            employer.certified += 1
            dba = (row.get(_DBA_COLUMN) or "").strip()
            if dba:
                employer.dba_aliases.add(dba)

        return [self._to_company(raw_name, employer) for raw_name, employer in employers.items()]

    @staticmethod
    def _to_company(raw_name: str, employer: _Employer) -> RegistryCompany:
        legal, embedded = split_trading_as(raw_name)
        aliases = tuple(sorted({*embedded, *employer.dba_aliases}))
        plural = "" if employer.certified == 1 else "s"
        return RegistryCompany(
            name=legal,
            aliases=aliases,
            evidence=f"{employer.certified} certified LCA filing{plural}",
        )
