# /// script
# requires-python = ">=3.12"
# dependencies = ["pytest"]
# ///
"""Presentation regression tests. Run with existing Python and pytest."""
import math
import pytest

import helpers


def test_virtual_gap_uses_ready_duration_and_guard() -> None:
    gaps = [(0, 2), (4, 7), (9, 11), (14, 22), (25, math.inf)]
    start = helpers.first_fitting_gap(gaps, (5, 5, 1))
    assert start == 14


def test_virtual_gap_accepts_an_exact_fit() -> None:
    start = helpers.first_fitting_gap([(4, 10)], (5, 4, 1))
    assert start == 5


def test_virtual_gap_has_no_fabricated_fit() -> None:
    assert helpers.first_fitting_gap([(0, 2), (4, 7)], (5, 5, 1)) is None


def test_cdf_keeps_full_denominator_under_a_zoom() -> None:
    assert helpers.cdf_at([.99, 1, 1, 1.2], 1) == .75


def test_cdf_distinguishes_ties_and_tail() -> None:
    assert helpers.cdf_at([.99, 1, 1, 1.2], .98) == 0
    assert helpers.cdf_at([.99, 1, 1, 1.2], 1.3) == 1


def test_band_example_covers_original_operations_once() -> None:
    from method_figures import BAND_GROUPS, CHAINS
    assert sorted(op for group in BAND_GROUPS for chain in group for op in CHAINS[chain]) == list(range(10))


def test_band_example_respects_depth_and_component_boundaries() -> None:
    from method_figures import BAND_GROUPS, DEPTHS, EDGES
    for v, depth in enumerate(DEPTHS):
        assert depth == 1 + max((DEPTHS[u] for u, w in EDGES if w == v), default=-1)
    owner = {c: group for group, chains in enumerate(BAND_GROUPS) for c in chains}
    for a, b in EDGES:
        if owner[a] != owner[b]:
            assert DEPTHS[a] // 2 < DEPTHS[b] // 2


def test_cache_annotation_is_a_real_frozen_event_not_a_pipe_claim() -> None:
    from v3_data import cache_marker
    m = cache_marker()
    assert (m.index, m.time, m.before, m.after, m.net_drop) == (2428, 1143536, 986880, 762624, 224256)


def test_rendered_ecdf_preserves_all_tied_unit_ratios(monkeypatch: pytest.MonkeyPatch) -> None:
    from collections.abc import Mapping, Sequence
    from matplotlib.figure import Figure
    from figlib import Cell, plt
    import v3_plots

    captured: list[Figure] = []

    def capture(fig: Figure, key: str, rows: Sequence[Mapping[str, Cell]]) -> None:
        captured.append(fig)

    monkeypatch.setattr(v3_plots, "save", capture)
    v3_plots.f25()
    fig = captured[0]
    curve = fig.axes[1].lines[0]
    at_one = [float(y) for x, y in zip(curve.get_xdata(), curve.get_ydata()) if x == 1.0]
    plt.close(fig)
    assert at_one[-1] == .39


def test_only_the_declared_safe_edges_are_contractible() -> None:
    from collections import Counter
    from method_figures import CHAINS, EDGES
    original = [(a, b) for chain in CHAINS for a, b in zip(chain, chain[1:])]
    original += [(CHAINS[a][-1], CHAINS[b][0]) for a, b in EDGES]
    outgoing = Counter(a for a, _ in original)
    incoming = Counter(b for _, b in original)
    assert {(a, b) for a, b in original if outgoing[a] == 1 and incoming[b] == 1} == {(0, 1), (6, 7)}
