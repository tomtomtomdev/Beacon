"""SqliteSettingsRepo — persists user-editable runtime config in the app_settings
key/value table. Today that is only the Telegram credentials (set via the Settings UI)."""

import sqlite3

from beacon.domain.notification import TelegramConfig

_TOKEN_KEY = "telegram_bot_token"
_CHAT_KEY = "telegram_chat_id"


class SqliteSettingsRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get_telegram_config(self) -> TelegramConfig:
        stored = {
            row["key"]: row["value"]
            for row in self._conn.execute("SELECT key, value FROM app_settings")
        }
        return TelegramConfig(bot_token=stored.get(_TOKEN_KEY), chat_id=stored.get(_CHAT_KEY))

    def set_telegram_config(self, config: TelegramConfig) -> None:
        """Persist exactly this config: a value upserts its key, a None deletes it.
        Partial-update semantics (keep the stored token) live in the use case, not here."""
        self._put(_TOKEN_KEY, config.bot_token)
        self._put(_CHAT_KEY, config.chat_id)
        self._conn.commit()

    def _put(self, key: str, value: str | None) -> None:
        if value is None:
            self._conn.execute("DELETE FROM app_settings WHERE key = ?", (key,))
        else:
            self._conn.execute(
                "INSERT INTO app_settings (key, value) VALUES (?, ?)"
                " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
