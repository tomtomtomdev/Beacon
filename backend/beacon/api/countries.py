"""GET /countries — the visa reference cards (SPEC §4). Read-only; seeded at startup."""

from datetime import date

from fastapi import APIRouter
from pydantic import BaseModel

from beacon.api.deps import CountryRepoDep
from beacon.application.countries import list_countries
from beacon.domain.visa import CountryReference

router = APIRouter()


class CountryOut(BaseModel):
    code: str
    name: str
    visa_summary: str
    pr_summary: str
    citizenship_summary: str
    registry_name: str
    priority_tier: str
    verified_at: date
    source_url: str


@router.get("/countries")
def get_countries(repo: CountryRepoDep) -> list[CountryOut]:
    return [_to_dto(c) for c in list_countries(repo)]


def _to_dto(c: CountryReference) -> CountryOut:
    return CountryOut(
        code=c.code,
        name=c.name,
        visa_summary=c.visa_summary,
        pr_summary=c.pr_summary,
        citizenship_summary=c.citizenship_summary,
        registry_name=c.registry_name,
        priority_tier=c.priority_tier.value,
        verified_at=c.verified_at,
        source_url=c.source_url,
    )
