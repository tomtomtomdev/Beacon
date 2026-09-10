"""CLI logging config: Beacon's own INFO lines stay, httpx's do not.

httpx logs every request at INFO with its full URL, and Telegram's sendMessage URL embeds
the bot token — so an unmuted httpx writes that secret into .ingest.log / .digest.log."""

import logging
from collections.abc import Iterator

import pytest

from beacon.logging_setup import configure_cli_logging


@pytest.fixture(autouse=True)
def restore_logging() -> Iterator[None]:
    """configure_cli_logging mutates process-wide loggers; put them back afterwards."""
    root, httpx_logger = logging.getLogger(), logging.getLogger("httpx")
    root_level, httpx_level = root.level, httpx_logger.level
    handlers = list(root.handlers)

    yield

    root.setLevel(root_level)
    root.handlers = handlers
    httpx_logger.setLevel(httpx_level)


def test_beacon_info_lines_are_logged() -> None:
    configure_cli_logging()

    assert logging.getLogger("beacon.application.notify").isEnabledFor(logging.INFO)


def test_httpx_info_is_silenced_so_a_bot_token_url_never_reaches_a_log() -> None:
    configure_cli_logging()

    assert not logging.getLogger("httpx").isEnabledFor(logging.INFO)
