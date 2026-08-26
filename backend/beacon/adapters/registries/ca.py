"""CA TFWP positive-LMIA employers list (quarterly XLSX → CSV, open.canada.ca).

Structural twin of H1BLCARegistry: one row per (program stream, occupation), so filings
are aggregated per employer and a ten-LMIA sponsor never reads like a one-filing shop.
Approved positions are counted alongside approved LMIAs because a single LMIA can cover
many positions (a fruit grower's 13 LMIAs cover 751 harvest positions).

Publisher caveat, stated in the file's own footnotes and not hidden here: the list
EXCLUDES all personal names and business names built on personal names, so it is not a
complete register — absence from it is not evidence of non-sponsorship.

Real-file hazards handled: a one-cell title banner above the header row, a trailing
"Notes:" block whose lines carry no employer, and province/stream values padded with
trailing spaces.
"""

from dataclasses import dataclass
from pathlib import Path

from beacon.adapters.registries._csvfile import iter_rows_below_banner
from beacon.adapters.registries._evidence import counted
from beacon.domain.registry import Registry, RegistryCompany

_NAME_COLUMN = "Employer"
_LMIA_COLUMN = "Approved LMIAs"
_POSITIONS_COLUMN = "Approved Positions"


@dataclass(slots=True)
class _Employer:
    lmias: int = 0
    positions: int = 0


def _count(raw: str | None) -> int:
    return int((raw or "0").strip() or 0)


class CALMIARegistry:
    registry = Registry.CA

    def __init__(self, path: Path) -> None:
        self._path = path

    def fetch(self) -> list[RegistryCompany]:
        employers: dict[str, _Employer] = {}
        for row in iter_rows_below_banner(self._path, header_column=_NAME_COLUMN):
            name = (row.get(_NAME_COLUMN) or "").strip()
            if not name:
                continue  # the footnotes block, and any padding row
            employer = employers.setdefault(name, _Employer())
            employer.lmias += _count(row.get(_LMIA_COLUMN))
            employer.positions += _count(row.get(_POSITIONS_COLUMN))

        return [
            RegistryCompany(name=name, evidence=self._evidence(employer))
            for name, employer in employers.items()
        ]

    @staticmethod
    def _evidence(employer: _Employer) -> str:
        lmias = counted(employer.lmias, "positive LMIA")
        return f"{lmias} ({counted(employer.positions, 'position')})"
