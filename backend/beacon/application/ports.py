"""Protocols every external system implements. Adapters depend on this module, never vice versa."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from beacon.domain.company import Company
from beacon.domain.job import NormalizedJob
from beacon.domain.registry import Registry, RegistryCompany

# A source-shaped payload exactly as the ATS returned it (one job posting).
type RawPosting = Mapping[str, Any]


class JobSource(Protocol):
    source_id: str

    async def fetch(self) -> list[RawPosting]: ...

    def normalize(self, raw: RawPosting) -> NormalizedJob: ...


class RegistryIngester(Protocol):
    """A sponsor register. Reads a manually-refreshed snapshot (MVP) into the rows the
    matcher consumes. registry is the bit this ingester contributes to registry_flags."""

    registry: Registry

    def fetch(self) -> list[RegistryCompany]: ...


@dataclass(frozen=True, slots=True)
class JobFilters:
    """Query contract for job listings. Tier is deliberately absent from defaults —
    sponsorship never filters unless explicitly requested."""

    q: str | None = None
    countries: tuple[str, ...] = ()
    posted_since: datetime | None = None
    limit: int = 50
    offset: int = 0


@dataclass(frozen=True, slots=True)
class JobListing:
    """Read model for the job table: one row joined with its company."""

    id: int
    title: str
    company: str
    url: str
    location_raw: str
    country: str | None
    city: str | None
    posted_at: datetime | None
    sponsor_tier: str


@dataclass(frozen=True, slots=True)
class JobPage:
    jobs: list[JobListing]
    total: int


class JobRepo(Protocol):
    def upsert(self, company_id: int, job: NormalizedJob, seen_at: datetime) -> None: ...

    def search(self, filters: JobFilters) -> JobPage: ...

    def resolve_registry_tier(self, company_id: int, tier: str) -> None:
        """Set the registry-derived tier on a company's jobs, leaving explicit-text
        tiers untouched (they win on precedence)."""
        ...


class CompanyRepo(Protocol):
    def upsert(self, company: Company) -> Company: ...

    def list_active(self) -> list[Company]: ...

    def get_by_name(self, name: str) -> Company | None: ...

    def set_registry_match(
        self, company_id: int, flags: int, confidence: float | None, evidence: str | None
    ) -> None: ...
