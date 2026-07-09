import sqlite3

from beacon.adapters.persistence.settings import SqliteSettingsRepo
from beacon.domain.notification import TelegramConfig


def test_get_returns_empty_config_when_nothing_stored(db: sqlite3.Connection) -> None:
    assert SqliteSettingsRepo(db).get_telegram_config() == TelegramConfig()


def test_set_then_get_roundtrips_the_config(db: sqlite3.Connection) -> None:
    repo = SqliteSettingsRepo(db)

    repo.set_telegram_config(TelegramConfig(bot_token="123:secret", chat_id="4242"))

    assert repo.get_telegram_config() == TelegramConfig(bot_token="123:secret", chat_id="4242")


def test_set_overwrites_the_previous_values(db: sqlite3.Connection) -> None:
    repo = SqliteSettingsRepo(db)
    repo.set_telegram_config(TelegramConfig(bot_token="old", chat_id="1"))

    repo.set_telegram_config(TelegramConfig(bot_token="new", chat_id="2"))

    assert repo.get_telegram_config() == TelegramConfig(bot_token="new", chat_id="2")


def test_a_none_field_clears_the_stored_value(db: sqlite3.Connection) -> None:
    repo = SqliteSettingsRepo(db)
    repo.set_telegram_config(TelegramConfig(bot_token="tok", chat_id="42"))

    repo.set_telegram_config(TelegramConfig(bot_token=None, chat_id="42"))

    assert repo.get_telegram_config() == TelegramConfig(bot_token=None, chat_id="42")
