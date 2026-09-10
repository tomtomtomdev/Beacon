"""CLI composition root: python -m beacon.notify.

Sends the current digest without polling. run.sh dispatches it at launch and again on
close, so a report lands even when the background poll is cut short by Ctrl-C — the poll
itself still sends its own digest when it finishes (see beacon.ingest). No new matches
means no message: the send gate is Digest.has_matches().

Wiring only — connects settings, DB, repos and the notify use case.
"""

import argparse
import asyncio
import sqlite3
from datetime import UTC, datetime

import httpx

from beacon.adapters.notify.factory import make_notifier
from beacon.adapters.persistence.companies import SqliteCompanyRepo
from beacon.adapters.persistence.db import MIGRATIONS_DIR, connect, run_migrations
from beacon.adapters.persistence.jobs import SqliteJobRepo
from beacon.adapters.persistence.registries_meta import SqliteRegistriesMetaRepo
from beacon.adapters.persistence.searches import SqliteSearchRepo
from beacon.adapters.persistence.settings import SqliteSettingsRepo
from beacon.application.health_report import build_health_alerts
from beacon.application.notify import MatchResult, match_saved_searches
from beacon.application.settings import effective_telegram_config
from beacon.config import Settings
from beacon.logging_setup import configure_cli_logging


async def send_digest(
    conn: sqlite3.Connection,
    settings: Settings,
    client: httpx.AsyncClient,
    *,
    now: datetime,
) -> MatchResult:
    """The pipeline's notify tail, shared by the poll (beacon.ingest) and the standalone
    dispatches here so both resolve creds and assemble the digest identically.

    Creds set via the Settings UI (DB) win, falling back to BEACON_TELEGRAM_* env.
    Source-health (SPEC §7) is attached to every digest, but only rides one that has matches
    to report — a run that found no jobs sends nothing at all.
    """
    telegram = effective_telegram_config(SqliteSettingsRepo(conn), settings.telegram_config())
    health_alerts, stale = build_health_alerts(
        SqliteCompanyRepo(conn), SqliteRegistriesMetaRepo(conn), now=now
    )
    return await match_saved_searches(
        SqliteSearchRepo(conn),
        SqliteJobRepo(conn),
        make_notifier(telegram, client),
        now=now,
        health_alerts=health_alerts,
        stale_registries=stale,
    )


async def dispatch_digest(settings: Settings, *, now: datetime) -> MatchResult:
    """One standalone digest send: open the DB, assemble, deliver. No polling, so it costs
    a few reads and — only when something matched — one Telegram POST."""
    conn = connect(settings.db_path)
    run_migrations(conn, MIGRATIONS_DIR)
    async with httpx.AsyncClient(timeout=15.0) as client:
        return await send_digest(conn, settings, client, now=now)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Send the pending saved-search digest without polling."
    )
    parser.parse_args(argv)

    configure_cli_logging()
    result = asyncio.run(dispatch_digest(Settings.from_env(), now=datetime.now(UTC)))
    print(f"searches={result.searches_run} new_matches={result.new_matches}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
