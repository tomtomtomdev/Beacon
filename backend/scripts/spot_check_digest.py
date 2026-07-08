"""Manual saved-search digest spot-check — the slice-8 acceptance gate.

Builds a throwaway DB, seeds a job matching the acceptance search ("senior iOS,
SE+NL+IE, tier>=registry_inferred") plus a non-matching control, creates that search,
and runs match_saved_searches. If BEACON_TELEGRAM_BOT_TOKEN + BEACON_TELEGRAM_CHAT_ID
are set it sends the real Telegram message (live network — manual only); otherwise it
prints the digest via StdoutNotifier. Runs twice to prove the seen-matches dedup.

    cd backend && uv run python scripts/spot_check_digest.py
    # live Telegram:
    BEACON_TELEGRAM_BOT_TOKEN=... BEACON_TELEGRAM_CHAT_ID=... \
        uv run python scripts/spot_check_digest.py

Acceptance (PLAN slice 8): the matching job produces exactly one Telegram message; a
re-run notifies nothing.
"""

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import httpx

from beacon.adapters.notify.stdout import StdoutNotifier
from beacon.adapters.notify.telegram import TelegramNotifier
from beacon.adapters.persistence.companies import SqliteCompanyRepo
from beacon.adapters.persistence.db import MIGRATIONS_DIR, connect, run_migrations
from beacon.adapters.persistence.jobs import SqliteJobRepo
from beacon.adapters.persistence.searches import SqliteSearchRepo
from beacon.application.notify import match_saved_searches
from beacon.application.ports import Notifier
from beacon.config import Settings
from beacon.domain.classification import Category, Classification, Level
from beacon.domain.company import Company
from beacon.domain.job import NormalizedJob
from beacon.domain.saved_search import SavedSearch, SearchFilters
from beacon.domain.sponsorship import SponsorSignal, SponsorTier

NOW = datetime(2026, 7, 8, 6, 0, tzinfo=UTC)


def _job(ext: str, country: str) -> NormalizedJob:
    return NormalizedJob(
        source_id="lever",
        external_id=ext,
        title=f"Senior iOS Engineer ({country})",
        url=f"https://boards.example/{ext}",
        description="Build the iOS app.",
        location_raw=country,
        country=country,
        city=None,
        posted_at=None,
        content_hash=f"h-{ext}",
    )


def _notifier(settings: Settings, client: httpx.AsyncClient) -> tuple[Notifier, str]:
    token = settings.telegram_bot_token
    if token is not None and settings.telegram_chat_id is not None:
        notifier = TelegramNotifier(
            client, bot_token=token.get_secret_value(), chat_id=settings.telegram_chat_id
        )
        return notifier, f"Telegram (chat {settings.telegram_chat_id})"
    return StdoutNotifier(), "Stdout (no BEACON_TELEGRAM_* set)"


async def _run() -> int:
    settings = Settings.from_env()
    with TemporaryDirectory() as tmp:
        conn = connect(Path(tmp) / "beacon.db")
        run_migrations(conn, MIGRATIONS_DIR)
        companies, jobs, searches = (
            SqliteCompanyRepo(conn),
            SqliteJobRepo(conn),
            SqliteSearchRepo(conn),
        )
        spotify = companies.upsert(
            Company(
                name="Spotify", ats_type="lever", ats_slug="spotify", country_hq="SE", priority=1
            )
        )
        assert spotify.id is not None  # noqa: S101 — freshly inserted
        ios = Classification(categories=frozenset({Category.IOS}), level=Level.SENIOR)
        backend = Classification(categories=frozenset({Category.BACKEND}), level=Level.SENIOR)
        inferred = SponsorSignal(SponsorTier.REGISTRY_INFERRED)
        jobs.upsert(
            spotify.id, _job("1", "SE"), seen_at=NOW, classification=ios, sponsorship=inferred
        )
        jobs.upsert(
            spotify.id, _job("2", "NL"), seen_at=NOW, classification=ios, sponsorship=inferred
        )
        # Control: right category profile but US + backend + unknown tier → must not match.
        jobs.upsert(
            spotify.id,
            NormalizedJob(
                source_id="lever",
                external_id="3",
                title="Backend Engineer",
                url="https://boards.example/3",
                description="Build APIs.",
                location_raw="US",
                country="US",
                city=None,
                posted_at=None,
                content_hash="h-3",
            ),
            seen_at=NOW,
            classification=backend,
        )
        searches.create(
            SavedSearch(
                name="senior iOS, SE+NL+IE, tier>=registry_inferred",
                filters=SearchFilters(
                    countries=("SE", "NL", "IE"),
                    categories=("ios",),
                    levels=("senior",),
                    tiers=("registry_inferred", "explicit_yes"),
                ),
            )
        )

        async with httpx.AsyncClient(timeout=15.0) as client:
            notifier, label = _notifier(settings, client)
            print(f"notifier: {label}\n")

            print("=== FIRST RUN (expect the matching iOS jobs; US backend excluded) ===")
            first = await match_saved_searches(searches, jobs, notifier, now=NOW)
            print(f"-> searches={first.searches_run} new_matches={first.new_matches}\n")

            print("=== SECOND RUN (expect nothing — seen-matches dedup) ===")
            second = await match_saved_searches(searches, jobs, notifier, now=NOW)
            print(f"-> searches={second.searches_run} new_matches={second.new_matches}")

        ok = first.new_matches == 2 and second.new_matches == 0
        print("\nACCEPTANCE", "OK" if ok else "FAILED")
        return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_run()))
