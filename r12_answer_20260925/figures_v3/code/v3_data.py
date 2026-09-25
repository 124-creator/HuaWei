# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""One deterministic annotation shared by existing-data views, not a new experiment."""
from dataclasses import dataclass
from typing import Final

from figlib import DATA

WINDOW: Final = (900000, 1200000)


@dataclass(frozen=True, slots=True)
class CacheMarker:
    index: int
    time: int
    before: int
    after: int
    inserted_bytes: int

    @property
    def net_drop(self) -> int:
        return self.before - self.after


def cache_marker() -> CacheMarker:
    rows = DATA["cache"]
    changes = [(a, b) for a, b in zip(rows, rows[1:])
               if WINDOW[0] <= b["time"] <= WINDOW[1] and b["used"] < a["used"]]
    a, b = max(changes, key=lambda pair: pair[0]["used"] - pair[1]["used"])
    return CacheMarker(b["index"], b["time"], a["used"], b["used"], b["bytes"])
