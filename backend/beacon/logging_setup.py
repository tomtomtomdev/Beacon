"""The one place CLI entrypoints configure logging, so every one of them hides the same
secrets. Wiring only — imported by the `python -m beacon.*` composition roots."""

import logging

LOG_FORMAT = "%(levelname)s %(name)s %(message)s"


def configure_cli_logging() -> None:
    """Beacon's key=value INFO lines on; httpx's request log off.

    httpx logs each request at INFO with its full URL. Telegram's sendMessage URL embeds the
    bot token, so leaving httpx at INFO writes that secret into .ingest.log / .digest.log on
    every digest. WARNING keeps the failures worth seeing without the URLs.
    """
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
    # basicConfig is a no-op once the root logger has a handler, so set the level outright —
    # otherwise anything that logs before main() silently swallows every INFO line.
    logging.getLogger().setLevel(logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
