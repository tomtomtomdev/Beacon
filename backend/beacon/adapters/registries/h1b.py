"""US H-1B LCA disclosure file (quarterly XLSX exported to CSV).

Only Certified / Certified-Withdrawn rows are sponsorship evidence; Denied/Withdrawn
contribute nothing. Rows with an empty employer are the sheet's padding (openpyxl's
max_row lies) and are skipped. Filings are aggregated per employer so a 3,000-filing
Google reads differently from a 2-filing startup. The brand can hide in an embedded
"dba X" in EMPLOYER_NAME or in the separate TRADE_NAME_DBA column — both become aliases.
"""

from pathlib import Path

from beacon.adapters.registries._certified import CertifiedFilingColumns, certified_employers
from beacon.adapters.registries._csvfile import iter_rows
from beacon.domain.registry import Registry, RegistryCompany

_COLUMNS = CertifiedFilingColumns(
    employer="EMPLOYER_NAME",
    status="CASE_STATUS",
    trade_name="TRADE_NAME_DBA",
    certified_statuses=frozenset({"Certified", "Certified - Withdrawn"}),
    evidence_noun="certified LCA filing",
)


class H1BLCARegistry:
    registry = Registry.US

    def __init__(self, path: Path) -> None:
        self._path = path

    def fetch(self) -> list[RegistryCompany]:
        return certified_employers(iter_rows(self._path), _COLUMNS)
