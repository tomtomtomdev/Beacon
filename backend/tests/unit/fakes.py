"""In-memory port stubs shared by the rollup use-case tests.

These are stubs, not working stores: every method the use case under test does not read
raises, so a new caller can never quietly lean on a fake that silently returns nothing.
The stateful `FakeCompanyRepo` in test_ingest.py is a different animal — it models real
get_or_create/shadow behavior — and stays there.
"""

from datetime import datetime

from beacon.application.ports import CompanyHealth
from beacon.domain.company import Company
from beacon.domain.health import SourceHealth
from beacon.domain.registry import RegistryMeta


class StubCompanyRepo:
    """Serves the two reads the source-health and registry-coverage rollups make."""

    def __init__(
        self,
        *,
        health: list[CompanyHealth] | None = None,
        registry_flag_counts: dict[int, int] | None = None,
    ) -> None:
        self._health = health or []
        self._registry_flag_counts = registry_flag_counts or {}

    def list_health(self) -> list[CompanyHealth]:
        return self._health

    def count_by_registry_flags(self) -> dict[int, int]:
        return self._registry_flag_counts

    def upsert(self, company: Company) -> Company:
        raise NotImplementedError("a rollup never writes")

    def get_or_create(self, company: Company) -> Company:
        raise NotImplementedError("a rollup never writes")

    def list_active(self) -> list[Company]:
        raise NotImplementedError("a rollup reads the aggregate, not the company rows")

    def get_by_name(self, name: str) -> Company | None:
        raise NotImplementedError("a rollup never looks one company up")

    def set_registry_match(
        self, company_id: int, flags: int, confidence: float | None, evidence: str | None
    ) -> None:
        raise NotImplementedError("a rollup never writes")

    def get_health(self, company_id: int) -> SourceHealth:
        raise NotImplementedError("a rollup reads every company at once")

    def set_health(self, company_id: int, health: SourceHealth) -> None:
        raise NotImplementedError("a rollup never writes")

    def list_quarantined(self) -> list[Company]:
        raise NotImplementedError("a rollup counts quarantined rows itself")


class StubRegistriesMetaRepo:
    def __init__(self, metas: list[RegistryMeta] | None = None) -> None:
        self._metas = metas or []

    def list_all(self) -> list[RegistryMeta]:
        return self._metas

    def record(self, registry: str, fetched_at: datetime, row_count: int) -> None:
        raise NotImplementedError("coverage reads snapshots; refresh_registries writes them")
