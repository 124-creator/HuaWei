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
