from pathlib import Path

from beacon.config import Settings

DEFAULT_LLM_MODEL = "claude-haiku-4-5-20251001"


def test_settings_defaults_resolve_inside_the_repo() -> None:
    settings = Settings.from_env({})

    assert settings.db_path.name == "beacon.db"
    assert settings.seeds_path.name == "companies.csv"
    assert settings.seeds_path.parent.name == "seeds"


def test_settings_env_overrides_win() -> None:
    settings = Settings.from_env(
        {"BEACON_DB_PATH": "/data/x.db", "BEACON_SEEDS_PATH": "/data/seeds.csv"}
    )

    assert settings.db_path == Path("/data/x.db")
    assert settings.seeds_path == Path("/data/seeds.csv")


def test_telegram_settings_absent_by_default() -> None:
    settings = Settings.from_env({})

    assert settings.telegram_bot_token is None
    assert settings.telegram_chat_id is None


def test_telegram_settings_from_env_keep_the_token_secret() -> None:
    settings = Settings.from_env(
        {"BEACON_TELEGRAM_BOT_TOKEN": "12345:secret", "BEACON_TELEGRAM_CHAT_ID": "4242"}
    )

    assert settings.telegram_bot_token is not None
    # SecretStr so the token never leaks into a repr/log line.
    assert repr(settings.telegram_bot_token) == "SecretStr('**********')"
    assert settings.telegram_bot_token.get_secret_value() == "12345:secret"
    assert settings.telegram_chat_id == "4242"


def test_llm_settings_default_when_absent() -> None:
    settings = Settings.from_env({})

    assert settings.anthropic_api_key is None
    assert settings.llm_model == DEFAULT_LLM_MODEL
    assert settings.llm_monthly_budget == 500


def test_llm_settings_from_env_override_and_keep_the_key_secret() -> None:
    settings = Settings.from_env(
        {
            "BEACON_ANTHROPIC_API_KEY": "sk-ant-secret",
            "BEACON_LLM_MODEL": "claude-something-newer",
            "BEACON_LLM_MONTHLY_BUDGET": "1200",
        }
    )

    assert settings.anthropic_api_key is not None
    assert repr(settings.anthropic_api_key) == "SecretStr('**********')"
    assert settings.anthropic_api_key.get_secret_value() == "sk-ant-secret"
    assert settings.llm_model == "claude-something-newer"
    assert settings.llm_monthly_budget == 1200
