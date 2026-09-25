# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Publication arithmetic only. Run tests with the existing Python and pytest.

AI-assisted code: OpenCode/Sisyphus; provider OpenAI; exact public model version
and release date unverified. Human review is required before contest submission.
"""
from dataclasses import dataclass
from math import ceil
from statistics import mean
from typing import Sequence


@dataclass(frozen=True, slots=True)
class PairStats:
    ratio: float
    reduction_percent: float
    wins: int
    ties: int
    losses: int


@dataclass(frozen=True, slots=True)
class InvalidSample(ValueError):
    reason: str

    def __str__(self) -> str:
        return self.reason


def paired_stats(pairs: Sequence[tuple[int, int]], expected: int) -> PairStats:
    if len(pairs) != expected or expected <= 0:
        raise InvalidSample("Incomplete paired group")
    if any(a <= 0 or b <= 0 for a, b in pairs):
        raise InvalidSample("Makespan must be positive")
    return PairStats(mean(a / b for a, b in pairs),
                     100 * mean(1 - b / a for a, b in pairs),
                     sum(b < a for a, b in pairs),
                     sum(b == a for a, b in pairs),
                     sum(b > a for a, b in pairs))


def p95(values: Sequence[float]) -> float:
    if not values:
        raise InvalidSample("Empty percentile sample")
    return sorted(values)[ceil(0.95 * len(values)) - 1]
