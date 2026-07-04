"""Protocols every external system implements. Adapters depend on this module, never vice versa."""

from collections.abc import Mapping
from datetime import datetime
from typing import Any, Protocol

from beacon.domain.company import Company
from beacon.domain.job import NormalizedJob

# A source-shaped payload exactly as the ATS returned it (one job posting).
type RawPosting = Mapping[str, Any]


class JobSource(Protocol):
    source_id: str

    async def fetch(self) -> list[RawPosting]: ...

    def normalize(self, raw: RawPosting) -> NormalizedJob: ...


class JobRepo(Protocol):
    def upsert(self, company_id: int, job: NormalizedJob, seen_at: datetime) -> None: ...


class CompanyRepo(Protocol):
    def upsert(self, company: Company) -> Company: ...

    def list_active(self) -> list[Company]: ...
