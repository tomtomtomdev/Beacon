"""UK Home Office register of licensed sponsors (CSV download, refreshed monthly).

Real-register hazards handled: leading/trailing whitespace, one row per visa route
(deduped by name), trading-as segments, CRLF line endings, and junk county values."""

from pathlib import Path

from beacon.adapters.registries._csvfile import iter_rows
from beacon.domain.matching import split_trading_as
from beacon.domain.registry import Registry, RegistryCompany

_NAME_COLUMN = "Organisation Name"
_ROUTE_COLUMN = "Route"


class UKSponsorRegistry:
    registry = Registry.UK

    def __init__(self, path: Path) -> None:
        self._path = path

    def fetch(self) -> list[RegistryCompany]:
        deduped: dict[str, RegistryCompany] = {}
        for row in iter_rows(self._path):
            raw = (row.get(_NAME_COLUMN) or "").strip()
            if not raw or raw.casefold() in deduped:
                continue
            legal, aliases = split_trading_as(raw)
            deduped[raw.casefold()] = RegistryCompany(
                name=legal,
                aliases=aliases,
                evidence=(row.get(_ROUTE_COLUMN) or "").strip(),
            )
        return list(deduped.values())
