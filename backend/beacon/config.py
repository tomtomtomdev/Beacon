"""The only module that reads the environment. Everything else takes Settings."""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic import SecretStr

from beacon.domain.notification import TelegramConfig

_REPO_ROOT = Path(__file__).parents[2]
_REGISTRIES = _REPO_ROOT / "data" / "registries"

# The one local-time zone for day/month boundaries (posted_since, digest, LLM budget month).
# Storage/comparison stay UTC; LOCAL_TZ is used only at these boundary edges (SPEC §9).
LOCAL_TZ = ZoneInfo("Asia/Jakarta")


@dataclass(frozen=True, slots=True)
class Settings:
    db_path: Path
    seeds_path: Path
    # Manually-refreshed registry snapshots (MVP); drop real exports in data/registries/.
    uk_registry_path: Path = _REGISTRIES / "uk_sponsors.csv"
    ind_registry_path: Path = _REGISTRIES / "ind_sponsors.csv"
    h1b_registry_path: Path = _REGISTRIES / "h1b_lca.csv"
    # Telegram Bot API credentials for the digest (slice 8). Absent → StdoutNotifier.
    # SecretStr keeps the token out of reprs/logs.
    telegram_bot_token: SecretStr | None = None
    telegram_chat_id: str | None = None

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        source = os.environ if env is None else env
        token = source.get("BEACON_TELEGRAM_BOT_TOKEN")
        return cls(
            db_path=Path(source.get("BEACON_DB_PATH", str(_REPO_ROOT / "beacon.db"))),
            seeds_path=Path(
                source.get("BEACON_SEEDS_PATH", str(_REPO_ROOT / "seeds" / "companies.csv"))
            ),
            uk_registry_path=Path(
                source.get("BEACON_UK_REGISTRY_PATH", str(_REGISTRIES / "uk_sponsors.csv"))
            ),
            ind_registry_path=Path(
                source.get("BEACON_IND_REGISTRY_PATH", str(_REGISTRIES / "ind_sponsors.csv"))
            ),
            h1b_registry_path=Path(
                source.get("BEACON_H1B_REGISTRY_PATH", str(_REGISTRIES / "h1b_lca.csv"))
            ),
            telegram_bot_token=SecretStr(token) if token else None,
            telegram_chat_id=source.get("BEACON_TELEGRAM_CHAT_ID"),
        )

    def telegram_config(self) -> TelegramConfig:
        """The env-provided Telegram creds as a domain value object — the fallback the
        DB-set creds layer over. Unwraps SecretStr here so it happens in one place."""
        return TelegramConfig(
            bot_token=(
                self.telegram_bot_token.get_secret_value() if self.telegram_bot_token else None
            ),
            chat_id=self.telegram_chat_id,
        )
