# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Interval and distribution operations for figure QA; existing Python + pytest.

AI-assisted: OpenCode/Sisyphus, OpenAI; public model release date unverified.
"""
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class InvalidFigureData(ValueError):
    reason: str

    def __str__(self) -> str:
        return self.reason


def merge_busy(intervals: Sequence[tuple[float, float]]) -> list[tuple[float, float]]:
    if any(end < start or start < 0 for start, end in intervals):
        raise InvalidFigureData("Invalid execution interval")
    merged: list[tuple[float, float]] = []
    for start, end in sorted(intervals):
        if start == end:
            continue
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged


def empirical_cdf(values: Sequence[float]) -> tuple[list[float], list[float]]:
    if not values:
        raise InvalidFigureData("Empty distribution")
    return sorted(values), [(i + 1) / len(values) for i in range(len(values))]


def clip_intervals(intervals: Sequence[tuple[float, float]], window: tuple[float, float]) -> list[tuple[float, float]]:
    """Intersect busy intervals with a shared absolute-time display window."""
    lo, hi = window
    return [(max(a, lo), min(b, hi)) for a, b in intervals if max(a, lo) < min(b, hi)]


def first_fitting_gap(gaps: Sequence[tuple[float, float]], request: tuple[float, float, float]) -> float | None:
    """Evaluate the documented fit inequality for an explicitly conceptual calendar."""
    ready, duration, guard = request
    for low, high in gaps:
        start = max(ready, low)
        if start + duration + guard <= high:
            return start
    return None


def cdf_at(values: Sequence[float], threshold: float) -> float:
    """Keep the full frozen sample as denominator, even for a zoomed display."""
    return sum(value <= threshold for value in values) / len(values)
