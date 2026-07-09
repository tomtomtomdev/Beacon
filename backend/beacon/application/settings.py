"""Settings use cases: read/update the Telegram config and fire a test digest.

The repo persists creds verbatim; the partial-update rule (keep the stored token when
the UI doesn't re-send it) lives here so it is the one place that policy exists."""

from beacon.application.ports import Notifier, SettingsRepo
from beacon.domain.digest import Digest, DigestGroup, DigestLine
from beacon.domain.notification import TelegramConfig

# A one-line digest that exercises the exact render + send path a real digest takes,
# so a successful test proves the credentials and the whole pipeline work.
_TEST_DIGEST = Digest(
    groups=(
        DigestGroup(
            search_name="Beacon test",
            lines=(
                DigestLine(
                    title="Telegram is connected ✅",
                    company="Beacon",
                    country=None,
                    tier="—",
                    url="(test message from Settings)",
                    reason="settings test",
                ),
            ),
        ),
    )
)


def effective_telegram_config(repo: SettingsRepo, env: TelegramConfig) -> TelegramConfig:
    """The creds actually used to send: UI-set values layered over the env fallback."""
    return repo.get_telegram_config().merge(env)


def update_telegram_config(
    repo: SettingsRepo, *, chat_id: str | None, bot_token: str | None
) -> TelegramConfig:
    """Persist a Settings edit. bot_token None → keep the stored token (the UI does not
    re-send the secret on an unrelated save); "" → clear it; a value → set it. chat_id is
    stored as given ("" / None clears it)."""
    stored = repo.get_telegram_config()
    new_token = stored.bot_token if bot_token is None else (bot_token or None)
    updated = TelegramConfig(bot_token=new_token, chat_id=chat_id or None)
    repo.set_telegram_config(updated)
    return updated


async def send_test_message(notifier: Notifier) -> None:
    """Send the fixed test digest through whatever notifier was wired (Telegram or Stdout)."""
    await notifier.send(_TEST_DIGEST)
