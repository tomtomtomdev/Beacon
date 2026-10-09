"""The shared reading of DOL's disclosure files (H-1B LCA, PERM): count certified filings per
employer, collect trade-name aliases, skip padding rows. Each register supplies its own
column names and status spellings as data, because DOL spells them differently per program.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field

from beacon.adapters.registries._evidence import counted
from beacon.domain.matching import split_trading_as
from beacon.domain.registry import RegistryCompany


@dataclass(frozen=True, slots=True)
class CertifiedFilingColumns:
    employer: str
    status: str
    trade_name: str
    certified_statuses: frozenset[str]
    evidence_noun: str  # "certified LCA filing" → "2 certified LCA filings"
    # Casefolded trade names that mean "none", never a brand (PERM's "N/A").
    placeholder_trade_names: frozenset[str] = frozenset()


@dataclass(slots=True)
class _Employer:
    certified: int = 0
    trade_names: set[str] = field(default_factory=set)


def certified_employers(
    rows: Iterable[dict[str, str | None]], columns: CertifiedFilingColumns
) -> list[RegistryCompany]:
    """One RegistryCompany per employer with at least one certified filing.

    Rows with an empty employer are the sheet's padding (openpyxl's max_row lies) and are
    skipped. Denied/Withdrawn rows contribute nothing. Filings are aggregated so a 3,000-filing
    Google reads differently from a 2-filing startup. The brand can hide in an embedded
    "dba X" in the employer name or in the trade-name column; both become aliases."""
    employers: dict[str, _Employer] = {}
    for row in rows:
        name = (row.get(columns.employer) or "").strip()
        if not name:
            continue  # padding row
        if (row.get(columns.status) or "").strip() not in columns.certified_statuses:
            continue  # Denied/Withdrawn is not sponsorship evidence
        employer = employers.setdefault(name, _Employer())
        employer.certified += 1
        trade = (row.get(columns.trade_name) or "").strip()
        if trade and trade.casefold() not in columns.placeholder_trade_names:
            employer.trade_names.add(trade)

    return [_to_company(name, employer, columns) for name, employer in employers.items()]


def _to_company(
    raw_name: str, employer: _Employer, columns: CertifiedFilingColumns
) -> RegistryCompany:
    legal, embedded = split_trading_as(raw_name)
    return RegistryCompany(
        name=legal,
        aliases=tuple(sorted({*embedded, *employer.trade_names})),
        evidence=counted(employer.certified, columns.evidence_noun),
    )
