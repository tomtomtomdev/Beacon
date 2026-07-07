"""NL IND register of recognised sponsors (public list, refreshed monthly).

Every legal entity is kept — multi-entity companies (Backbase ×3, Adyen ×2, …) match
at the company level, counted once by the matcher, not deduped here. The KvK number is
preserved as evidence: it becomes an exact-match key if seed rows ever gain one."""

from pathlib import Path

from beacon.adapters.registries._csvfile import iter_rows
from beacon.domain.registry import Registry, RegistryCompany

_NAME_COLUMN = "Organisation"
_KVK_COLUMN = "KvK number"


class INDRegistry:
    registry = Registry.NL

    def __init__(self, path: Path) -> None:
        self._path = path

    def fetch(self) -> list[RegistryCompany]:
        companies: list[RegistryCompany] = []
        for row in iter_rows(self._path):
            name = (row.get(_NAME_COLUMN) or "").strip()
            if not name:
                continue
            kvk = (row.get(_KVK_COLUMN) or "").strip()
            companies.append(RegistryCompany(name=name, evidence=f"KvK {kvk}" if kvk else ""))
        return companies
