"""US PERM labor certification disclosure file (quarterly XLSX exported to CSV), slice 24.

A certified PERM labor certification is the first step of an employment-based green card,
so it is different evidence from an H-1B LCA and carries its own bit (Registry.PERM).

Read against the live FY2026 Q3 file, not the record layout: the expired status is spelled
"Certified - Expired" there (the layout says "Certified-Expired"), and an expired
certification still was a sponsorship. Denied/Withdrawn contribute nothing. 812,880 of the
sheet's 925,430 rows are padding with an empty employer. EMP_TRADE_NAME becomes an alias,
except for the placeholders filers type when there is none ("N/A" alone on 11,441 rows).
"""

from pathlib import Path

from beacon.adapters.registries._certified import CertifiedFilingColumns, certified_employers
from beacon.adapters.registries._csvfile import iter_rows
from beacon.domain.registry import Registry, RegistryCompany

_COLUMNS = CertifiedFilingColumns(
    employer="EMP_BUSINESS_NAME",
    status="CASE_STATUS",
    trade_name="EMP_TRADE_NAME",
    certified_statuses=frozenset({"Certified", "Certified - Expired"}),
    evidence_noun="certified PERM filing",
    # Every spelling seen at least five times in the FY2026 Q3 file, compared casefolded.
    placeholder_trade_names=frozenset({"n/a", "na", "none", "not applicable"}),
)


class PERMRegistry:
    registry = Registry.PERM

    def __init__(self, path: Path) -> None:
        self._path = path

    def fetch(self) -> list[RegistryCompany]:
        return certified_employers(iter_rows(self._path), _COLUMNS)
