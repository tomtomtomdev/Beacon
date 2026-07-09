"""Notification channel configuration as a pure value object.

TelegramConfig is the one representation of Telegram Bot API credentials, shared by
the SettingsRepo port, the notifier factory, and the config env-fallback. The bot
token is kept out of reprs (it travels through logs/tracebacks); it is a plain str,
not pydantic's SecretStr, so the domain stays framework-free."""

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class TelegramConfig:
    """Telegram credentials for the digest. Absent/partial → StdoutNotifier fallback."""

    bot_token: str | None = field(default=None, repr=False)  # never rendered in a repr/log
    chat_id: str | None = None

    @property
    def is_configured(self) -> bool:
        """Both credentials present — a real Telegram send is possible."""
        return bool(self.bot_token and self.chat_id)

    def merge(self, fallback: "TelegramConfig") -> "TelegramConfig":
        """This config's values win per field; fallback fills any blank. Used to layer
        UI-set creds (this) over the BEACON_TELEGRAM_* env creds (fallback), so a field
        the UI left empty still resolves from the environment."""
        return TelegramConfig(
            bot_token=self.bot_token or fallback.bot_token,
            chat_id=self.chat_id or fallback.chat_id,
        )
