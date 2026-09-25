# /// script
# requires-python = ">=3.12"
# dependencies = ["pytest"]
# ///
"""Run: python -B -m pytest -p no:cacheprovider code/test_revision.py."""
import helpers
from graphlib import CycleError, TopologicalSorter

import pytest
from model_examples import AFTER, BEFORE, CYCLIC_QUEUES, FIFO_STATES, GROUPS, LEGAL_QUEUES, OP_EDGES, TASK_EDGES


def test_clip_intervals_preserves_real_overlaps() -> None:
    # Given two visible intervals and one outside the common zoom window.
    intervals = [(2, 15), (18, 30), (30, 40)]
    # When the timeline is restricted to an absolute-time window.
    result = helpers.clip_intervals(intervals, (10, 20))
    # Then only the actual intersections remain; no gap is filled.
    assert result == [(10, 15), (18, 20)]


def test_clip_intervals_excludes_zero_length_boundary_contacts() -> None:
    intervals = [(0, 10), (20, 30)]
    result = helpers.clip_intervals(intervals, (10, 20))
    assert result == []


def test_clip_intervals_keeps_the_source_unchanged() -> None:
    intervals = [(2, 15), (18, 30)]
    helpers.clip_intervals(intervals, (10, 20))
    assert intervals == [(2, 15), (18, 30)]


def test_conceptual_partition_preserves_each_original_operation_once() -> None:
    members = [op for group in GROUPS for op in group]
    assert sorted(members) == list(range(6))


def test_contracted_dependencies_match_the_original_example() -> None:
    mapping = {op: i for i, group in enumerate(GROUPS) for op in group}
    edges = {(mapping[a], mapping[b]) for a, b in OP_EDGES if mapping[a] != mapping[b]}
    assert edges == set(TASK_EDGES)


def test_legal_core_queues_keep_the_union_acyclic() -> None:
    graph = TopologicalSorter()
    for a, b in TASK_EDGES + tuple(edge for queue in LEGAL_QUEUES for edge in zip(queue, queue[1:])):
        graph.add(b, a)
    assert set(graph.static_order()) == {0, 1, 2, 3}


def test_reverse_core_queue_really_creates_a_cycle() -> None:
    graph = TopologicalSorter()
    for a, b in TASK_EDGES + tuple(edge for queue in CYCLIC_QUEUES for edge in zip(queue, queue[1:])):
        graph.add(b, a)
    with pytest.raises(CycleError):
        tuple(graph.static_order())


def test_microbatch_preserves_operations_and_original_dependencies() -> None:
    assert sorted(BEFORE) == sorted(AFTER)
    for order in (BEFORE, AFTER):
        assert all(order.index(f"A{i}") < order.index(f"B{i}") for i in range(1, 5))


def test_fifo_example_inserts_at_tail_without_refreshing_a_hit() -> None:
    initial, after_e, after_a = FIFO_STATES
    assert after_e == initial[1:] + ("E",)
    assert after_a == after_e[1:] + ("A",)
    assert all(len(set(state)) == 4 and len(state) * 262144 == 1048576 for state in FIFO_STATES)


def test_task_background_cannot_hide_internal_relationships() -> None:
    from figlib import plt
    from model_layout import Scene

    scene = Scene("F05")
    scene.box((0, 0, 100, 100), layer=0)
    scene.link([(10, 50), (90, 50)])
    background, relationship = scene.ax.patches
    assert background.get_zorder() < relationship.get_zorder()
    plt.close(scene.fig)
