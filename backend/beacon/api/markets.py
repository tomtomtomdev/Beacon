"""GET /markets — open-job counts per country, split into the markets SPEC §4 assessed and the
ones it never did (DESIGN §2, the country menu's second group).

Its own endpoint rather than a field on /countries: that resource is the §4 visa reference,
seeded at startup, and hanging a live job count off it would make a reference resource change
every poll. Read-only.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from beacon.api.deps import JobRepoDep
from beacon.application.markets import get_market_coverage
from beacon.domain.visa import MarketCount, MarketCoverage

router = APIRouter()


class MarketCountOut(BaseModel):
    """Code only, no name: §4 names come from /countries, and the markets outside it have no
    name source in this repo — the frontend renders those through Intl.DisplayNames."""

    code: str
    open_jobs: int


class MarketCoverageOut(BaseModel):
    target_markets: list[MarketCountOut]
    other_markets: list[MarketCountOut]


@router.get("/markets")
def get_markets(repo: JobRepoDep) -> MarketCoverageOut:
    return _to_out(get_market_coverage(repo))


def _count_out(market: MarketCount) -> MarketCountOut:
    return MarketCountOut(code=market.code, open_jobs=market.open_jobs)


def _to_out(coverage: MarketCoverage) -> MarketCoverageOut:
    return MarketCoverageOut(
        target_markets=[_count_out(market) for market in coverage.target_markets],
        other_markets=[_count_out(market) for market in coverage.other_markets],
    )
