# /// script
# requires-python = ">=3.12"
# dependencies = ["pytest"]
# ///
"""Run: existing-python -B -m pytest -p no:cacheprovider code/test_metrics.py."""
import pytest
from metrics import paired_stats, p95


def test_ratio_mean_preserves_equal_case_weights() -> None:
    pairs = [(2, 1), (9, 9)]
    result = paired_stats(pairs, 2)
    assert result.ratio == 1.5


def test_time_reduction_is_not_inverse_of_average_ratio() -> None:
    pairs = [(2, 1), (9, 9)]
    result = paired_stats(pairs, 2)
    assert result.reduction_percent == 25.0


def test_win_tie_loss_uses_integer_times() -> None:
    pairs = [(10, 8), (10, 10), (10, 12)]
    result = paired_stats(pairs, 3)
    assert (result.wins, result.ties, result.losses) == (1, 1, 1)


def test_incomplete_group_is_rejected() -> None:
    pairs = [(10, 8)]
    with pytest.raises(ValueError):
        paired_stats(pairs, 100)


def test_invalid_time_is_rejected() -> None:
    pairs = [(10, 0)]
    with pytest.raises(ValueError):
        paired_stats(pairs, 1)


def test_p95_is_empirical_nearest_rank() -> None:
    values = [float(i) for i in range(1, 101)]
    result = p95(values)
    assert result == 95.0
