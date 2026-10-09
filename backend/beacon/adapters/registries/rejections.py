"""The reviewed rejection table (slice 25c): matches a person looked at and refused.

seeds/registry_rejections.csv — company,registry,entry,reason,reviewed_at. `company` and
`entry` are written exactly as `scripts/spot_check_registry.py` prints them, so a line from
its review set becomes a row here by adding a reason. The reason is required: a rejection
nobody can explain is a guess, and the table exists to hold judgements.
"""

import csv
import io

from beacon.domain.matching import RegistryRejection
from beacon.domain.registry import Registry


def parse_rejections_csv(text: str) -> frozenset[RegistryRejection]:
    rejections: set[RegistryRejection] = set()
    for line, row in enumerate(csv.DictReader(io.StringIO(text)), start=2):
        registry_name = (row.get("registry") or "").strip()
        if registry_name not in Registry.__members__:
            raise ValueError(f"line {line}: unknown registry {registry_name!r}")
        if not (row.get("reason") or "").strip():
            raise ValueError(f"line {line}: a rejection needs a reason")
        rejections.add(
            RegistryRejection(
                company=(row.get("company") or "").strip(),
                registry=Registry[registry_name],
                entry=(row.get("entry") or "").strip(),
            )
        )
    return frozenset(rejections)
