# /// script
# requires-python = ">=3.12"
# dependencies = ["pytest"]
# ///
"""Exact content preservation tests for document integration, not prompt wording."""
import pytest

from answers import insert_block, restore_source, wrap_block


def test_figure_insertion_is_exactly_reversible() -> None:
    source = "# Title\n\nA source paragraph.\n\n$$\nx^2+y^2=z^2\n$$\n\nEnd.\n"
    integrated = insert_block(source, "A source", wrap_block("test", "![F02](../figures/F02.png)"))
    assert restore_source("Q1", integrated) == source


def test_missing_anchor_stops_instead_of_silently_dropping_content() -> None:
    with pytest.raises(AssertionError):
        insert_block("# Title\n\nOriginal.\n", "Missing.", wrap_block("test", "image"))


def test_ambiguous_anchor_stops_instead_of_inserting_twice() -> None:
    with pytest.raises(AssertionError):
        insert_block("Same one\n\nSame two\n", "Same", wrap_block("test", "image"))
