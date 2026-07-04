"""The only module that reads the environment. Everything else takes Settings."""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

_REPO_ROOT = Path(__file__).parents[2]


@dataclass(frozen=True, slots=True)
class Settings:
    db_path: Path
    seeds_path: Path

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        source = os.environ if env is None else env
        return cls(
            db_path=Path(source.get("BEACON_DB_PATH", str(_REPO_ROOT / "beacon.db"))),
            seeds_path=Path(
                source.get("BEACON_SEEDS_PATH", str(_REPO_ROOT / "seeds" / "companies.csv"))
            ),
        )
