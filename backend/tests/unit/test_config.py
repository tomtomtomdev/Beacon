from pathlib import Path

from beacon.config import Settings


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
