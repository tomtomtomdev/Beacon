"""Protocols every external system implements. Adapters depend on this module, never vice versa."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from beacon.domain.classification import Classification
from beacon.domain.company import Company
from beacon.domain.dedup import DedupRow
from beacon.domain.job import NormalizedJob
from beacon.domain.registry import Registry, RegistryCompany

# A source-shaped payload exactly as the ATS returned it (one job posting).
type RawPosting = Mapping[str, Any]


class Fetcher(Protocol):
    """The single HTTP door every adapter fetches through. The implementation owns
    politeness (1 rps/host, conditional GET, backoff); adapters just ask for JSON."""

    async def get_json(self, url: str, *, params: Mapping[str, str] | None = None) -> Any: ...


class JobSource(Protocol):
    source_id: str

    async def fetch(self) -> list[RawPosting]: ...

    def normalize(self, raw: RawPosting) -> NormalizedJob: ...


class RegistryIngester(Protocol):
    """A sponsor register. Reads a manually-refreshed snapshot (MVP) into the rows the
    matcher consumes. registry is the bit this ingester contributes to registry_flags."""

    registry: Registry

    def fetch(self) -> list[RegistryCompany]: ...


class Classifier(Protocol):
    """Produces a job's category/level. Heuristic today; the LLM classifier (slice 9)
    shares this port and only upgrades the ambiguous residue."""

    def classify(self, job: NormalizedJob) -> Classification: ...


@dataclass(frozen=True, slots=True)
class JobFilters:
    """Query contract for job listings. sponsor_tiers is deliberately empty by default —
    sponsorship drives the sort but never filters unless explicitly requested.

    sort: "tier" (default, sort_rank DESC then posted_at DESC) or "date" (posted_at DESC).
    """

    q: str | None = None
    countries: tuple[str, ...] = ()
    categories: tuple[str, ...] = ()
    levels: tuple[str, ...] = ()
    posted_since: datetime | None = None
    sponsor_tiers: tuple[str, ...] = ()
    # None → default view (everything except 'hidden'); "all" → no status filter;
    # a specific status → only that status (e.g. "new" for the morning scan).
    status: str | None = None
    sort: str = "tier"
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
    categories: tuple[str, ...]
    level: str | None
    posted_at: datetime | None
    sponsor_tier: str
    user_status: str


@dataclass(frozen=True, slots=True)
class JobPage:
    jobs: list[JobListing]
    total: int


@dataclass(frozen=True, slots=True)
class DuplicateSource:
    """One underlying posting behind a canonical job — where the same role was found."""

    source: str
    company: str
    url: str


@dataclass(frozen=True, slots=True)
class JobDetail:
    """Read model for the detail view: the canonical job plus every source it was
    found on (its own posting and any cross-source duplicates)."""

    id: int
    title: str
    company: str
    url: str
    description: str
    location_raw: str
    country: str | None
    city: str | None
    categories: tuple[str, ...]
    level: str | None
    posted_at: datetime | None
    sponsor_tier: str
    user_status: str
    duplicate_sources: tuple[DuplicateSource, ...]


class JobRepo(Protocol):
    def upsert(
        self,
        company_id: int,
        job: NormalizedJob,
        seen_at: datetime,
        classification: Classification | None = None,
    ) -> None:
        """Persist a posting. classification writes categories/level; None leaves the
        stored values intact (an unchanged re-poll keeps its earlier classification)."""
        ...

    def content_hash_for(self, source_id: str, external_id: str) -> str | None:
        """The content_hash currently stored for this posting, or None if unseen.
        Lets the pipeline classify only when content changed."""
        ...

    def list_unclassified(self) -> list[tuple[int, NormalizedJob]]:
        """Persisted jobs never classified (categories IS NULL), each as (job_id, job).
        An empty-string categories value means 'classified, nothing matched' and is skipped."""
        ...

    def set_classification(self, job_id: int, classification: Classification) -> None: ...

    def list_dedup_rows(self) -> list[DedupRow]:
        """Every persisted job reduced to the fields the canonicalizer compares."""
        ...

    def set_canonical_links(self, links: Mapping[int, int | None]) -> None:
        """Apply the dedup assignment: canonical_id = the canonical row's id for a
        duplicate, or None for a canonical row. Applied in one transaction."""
        ...

    def get_job_detail(self, job_id: int) -> JobDetail | None:
        """The canonical job for this id (resolving through canonical_id if a
        duplicate id is given), with every underlying source listed. None if unknown."""
        ...

    def set_user_status(self, job_id: int, status: str) -> int | None:
        """Set the user status on the canonical row for this id (resolving through
        canonical_id if a duplicate id is given). Returns the updated canonical id,
        or None if the id is unknown."""
        ...

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
