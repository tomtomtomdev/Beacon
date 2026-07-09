from beacon.domain.notification import TelegramConfig


def test_empty_config_is_not_configured() -> None:
    assert TelegramConfig().is_configured is False


def test_needs_both_token_and_chat_id_to_be_configured() -> None:
    assert TelegramConfig(bot_token="t", chat_id=None).is_configured is False
    assert TelegramConfig(bot_token=None, chat_id="42").is_configured is False
    assert TelegramConfig(bot_token="t", chat_id="42").is_configured is True


def test_repr_never_leaks_the_token() -> None:
    # The token flows through logs/tracebacks; it must never appear in a repr.
    assert "SECRET" not in repr(TelegramConfig(bot_token="SECRET", chat_id="42"))


def test_merge_lets_this_config_win_per_field_and_fallback_fills_blanks() -> None:
    db = TelegramConfig(bot_token="db-token", chat_id=None)
    env = TelegramConfig(bot_token="env-token", chat_id="env-chat")

    merged = db.merge(env)

    # DB-set token wins; the chat_id the UI left blank falls back to env.
    assert merged.bot_token == "db-token"
    assert merged.chat_id == "env-chat"
