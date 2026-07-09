"""Protocols every external system implements. Adapters depend on this module, never vice versa."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from beacon.domain.classification import Classification
from beacon.domain.company import Company
from beacon.domain.dedup import DedupRow
from beacon.domain.digest import Digest
from beacon.domain.health import SourceHealth
from beacon.domain.job import NormalizedJob
from beacon.domain.notification import TelegramConfig
from beacon.domain.registry import Registry, RegistryCompany, RegistryMeta
from beacon.domain.saved_search import SavedSearch
from beacon.domain.sponsorship import SponsorSignal
from beacon.domain.visa import CountryReference

# A source-shaped payload exactly as the ATS returned it (one job posting).
type RawPosting = Mapping[str, Any]


class Fetcher(Protocol):
    """The single HTTP door every adapter fetches through. The implementation owns
    politeness (1 rps/host, conditional GET, backoff); adapters just ask for JSON."""

    async def get_json(self, url: str, *, params: Mapping[str, str] | None = None) -> Any: ...

    async def get_text(self, url: str, *, params: Mapping[str, str] | None = None) -> str: ...


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


class LLMBudget(Protocol):
    """The hard monthly cap on LLM classifier calls (cost control, SPEC §9). try_reserve
    counts one call against the current month and reports whether it was under budget —
    the tiered classifier only calls the LLM when it returns True."""

    def try_reserve(self) -> bool:
        """Reserve one LLM call for this month. True (and the call is now counted) when
        under the monthly cap; False when the cap is reached. Counts the attempt, so a
        failing/retrying call can never blow the budget."""
        ...


class Notifier(Protocol):
    """Delivers a new-match digest. TelegramNotifier is the MVP; the digest is channel-
    agnostic so each notifier owns its own formatting/size limits. Never called for an
    empty digest (the use case guards that)."""

    async def send(self, digest: Digest) -> None: ...


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
    sponsor_evidence: str | None
    # Company-level registry signal behind a registry_inferred tier: which registers the
    # company matched (e.g. ("UK", "NL")) and the fuzzy-match confidence. The drawer lists
    # them; empty/None when the company matched no register.
    registries: tuple[str, ...]
    match_confidence: float | None
    user_status: str
    duplicate_sources: tuple[DuplicateSource, ...]


class JobRepo(Protocol):
    def upsert(
        self,
        company_id: int,
        job: NormalizedJob,
        seen_at: datetime,
        classification: Classification | None = None,
        sponsorship: SponsorSignal | None = None,
    ) -> None:
        """Persist a posting. classification writes categories/level; None leaves the
        stored values intact (an unchanged re-poll keeps its earlier classification).
        sponsorship writes sponsor_tier/sponsor_evidence; None leaves them intact (so a
        registry-derived tier survives an unchanged re-poll)."""
        ...

    def content_hash_for(self, source_id: str, external_id: str) -> str | None:
        """The content_hash currently stored for this posting, or None if unseen.
        Lets the pipeline classify only when content changed."""
        ...

    def list_unclassified(self) -> list[tuple[int, NormalizedJob]]:
        """Persisted jobs never classified (categories IS NULL), each as (job_id, job).
        An empty-string categories value means 'classified, nothing matched' and is skipped."""
        ...

    def list_ambiguous(self) -> list[tuple[int, NormalizedJob]]:
        """Persisted jobs classified but with no category (categories = ''), each as
        (job_id, job) — the empty residue the LLM upgrader revisits. Distinct from
        list_unclassified (NULL = never classified)."""
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

    def sweep_absent_jobs(
        self,
        source_id: str,
        company_id: int | None,
        seen_external_ids: set[str],
        now: datetime,
        *,
        threshold: int,
    ) -> int:
        """After a *successful* poll, advance the closed-posting sweep for the jobs in scope
        (source_id, and company_id when the source is per-company — None for company-less
        sources spanning many employers). Jobs present in seen_external_ids reset to zero
        misses and reopen; absent jobs increment their miss counter and get closed_at set once
        they reach `threshold` consecutive misses. Returns the count newly closed. Never called
        on a failed poll, so absence only ever accrues from successful polls (SPEC §7)."""
        ...

    def search(self, filters: JobFilters) -> JobPage: ...

    def resolve_registry_tier(self, company_id: int, tier: str) -> None:
        """Set the registry-derived tier on a company's jobs, leaving explicit-text
        tiers untouched (they win on precedence)."""
        ...


@dataclass(frozen=True, slots=True)
class CompanyHealth:
    """Read model for the source-health view (DESIGN §3) and the digest's quarantine lines.
    `health` is ok/degraded/quarantined; `reason` is the current failure kind (None when ok)."""

    name: str
    ats_type: str
    ats_slug: str
    country_hq: str
    health: str
    reason: str | None
    last_success_at: datetime | None
    consecutive_failures: int


class CompanyRepo(Protocol):
    def upsert(self, company: Company) -> Company: ...

    def get_or_create(self, company: Company) -> Company:
        """Return the existing company with this name untouched, or insert this one and
        return it persisted. Used by company-less sources to shadow employers parsed from
        postings without ever overwriting a real seed row's ats_type/registry flags."""
        ...

    def list_active(self) -> list[Company]: ...

    def get_by_name(self, name: str) -> Company | None: ...

    def set_registry_match(
        self, company_id: int, flags: int, confidence: float | None, evidence: str | None
    ) -> None: ...

    def get_health(self, company_id: int) -> SourceHealth:
        """The company's current polling health (SPEC §7). Fresh rows read back as OK."""
        ...

    def set_health(self, company_id: int, health: SourceHealth) -> None:
        """Persist a health transition (after a poll, or a probe restore)."""
        ...

    def list_quarantined(self) -> list[Company]:
        """The quarantined seed companies — the weekly probe's retry list."""
        ...

    def list_health(self) -> list[CompanyHealth]:
        """Every pollable seed company with its health, for the source-health view and digest.
        Shadow employers (ats_type='none') are excluded — they aren't pollable sources."""
        ...


class SearchRepo(Protocol):
    def create(self, search: SavedSearch) -> SavedSearch:
        """Persist a new saved search; returns it with its assigned id."""
        ...

    def list_all(self) -> list[SavedSearch]: ...

    def get(self, search_id: int) -> SavedSearch | None: ...

    def delete(self, search_id: int) -> bool:
        """Remove a saved search (and its seen_matches, via cascade). False if unknown."""
        ...

    def seen_job_ids(self, search_id: int) -> set[int]:
        """Canonical job ids already notified for this search — the notify-once ledger."""
        ...

    def record_matches(
        self, search_id: int, matches: Sequence[tuple[int, str]], notified_at: datetime
    ) -> None:
        """Mark (canonical job id, match_reason) pairs as notified; idempotent per pair."""
        ...

    def touch_last_run(self, search_id: int, at: datetime) -> None: ...


class CountryRepo(Protocol):
    """The visa reference table (SPEC §4) — a seeded projection of the COUNTRY_REFERENCE
    domain constant. Read-only to the API; the seed keeps the table in sync at startup."""

    def get_all(self) -> list[CountryReference]:
        """Every reference row, primary-tier countries before nice-to-have."""
        ...

    def seed(self, countries: Sequence[CountryReference]) -> None:
        """Idempotently upsert the reference rows (keyed on code); re-seeding updates."""
        ...


class RegistriesMetaRepo(Protocol):
    """Freshness bookkeeping for the sponsor-registry snapshots (registries_meta). The refresh
    records each snapshot's fetched_at/row_count; the digest reads it to nag when one is stale."""

    def record(self, registry: str, fetched_at: datetime, row_count: int) -> None:
        """Upsert one registry's snapshot freshness, keyed on the registry name."""
        ...

    def list_all(self) -> list[RegistryMeta]:
        """Every recorded registry snapshot."""
        ...


class SettingsRepo(Protocol):
    """User-editable runtime config (Telegram creds set via the Settings UI)."""

    def get_telegram_config(self) -> TelegramConfig:
        """The stored Telegram creds, or an empty TelegramConfig if none set."""
        ...

    def set_telegram_config(self, config: TelegramConfig) -> None:
        """Persist the config verbatim — a None field clears that stored value."""
        ...
