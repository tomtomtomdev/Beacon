"""The only module that reads the environment. Everything else takes Settings."""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

_REPO_ROOT = Path(__file__).parents[2]
_REGISTRIES = _REPO_ROOT / "data" / "registries"


@dataclass(frozen=True, slots=True)
class Settings:
    db_path: Path
    seeds_path: Path
    # Manually-refreshed registry snapshots (MVP); drop real exports in data/registries/.
    uk_registry_path: Path = _REGISTRIES / "uk_sponsors.csv"
    ind_registry_path: Path = _REGISTRIES / "ind_sponsors.csv"
    h1b_registry_path: Path = _REGISTRIES / "h1b_lca.csv"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        source = os.environ if env is None else env
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
        )
