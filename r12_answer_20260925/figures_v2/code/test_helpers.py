# /// script
# requires-python = ">=3.12"
# dependencies = ["pytest"]
# ///
"""Run existing-python -B -m pytest -p no:cacheprovider code/test_helpers.py."""
import pytest
from helpers import empirical_cdf, merge_busy


def test_merge_retains_idle_gap() -> None:
    observed = [(0, 3), (3, 5), (7, 9)]
    assert merge_busy(observed) == [(0, 5), (7, 9)]


def test_overlap_is_union_not_double_count() -> None:
    assert merge_busy([(3, 8), (0, 4), (10, 10)]) == [(0, 8)]


def test_negative_duration_is_rejected() -> None:
    with pytest.raises(ValueError):
        merge_busy([(2, 1)])


def test_empty_timeline_is_valid_idle_pipe() -> None:
    assert merge_busy([]) == []


def test_ecdf_preserves_ties_and_all_cases() -> None:
    x, y = empirical_cdf([2, 1, 1, 3])
    assert x == [1, 1, 2, 3]
    assert y == [0.25, 0.5, 0.75, 1.0]


def test_ecdf_empty_group_is_not_success() -> None:
    with pytest.raises(ValueError):
        empirical_cdf([])
