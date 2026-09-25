# /// script
# requires-python = ">=3.12"
# dependencies = ["pytest", "matplotlib"]
# ///
"""Checks QA against the actual axis view, without changing chart data or limits."""
from figlib import frame, plt, visible_texts


def test_qa_does_not_count_ticks_outside_visible_view() -> None:
    fig, ax = plt.subplots()
    ax.set_yticks([0, 1, 2, 3, 4, 5])
    ax.set_ylim(0, 4.6)
    ax.set_xticks([])
    fig.canvas.draw()
    labels = [t.get_text() for t in visible_texts(fig)]
    assert "4" in labels and "5" not in labels
    plt.close(fig)


def test_qa_retains_real_annotation_outside_axes() -> None:
    fig, ax = plt.subplots()
    note = ax.text(1.5, 1.5, "outside", transform=ax.transAxes, clip_on=False)
    fig.canvas.draw()
    assert note in visible_texts(fig)
    plt.close(fig)


def test_figure_heading_is_separate_from_data_region() -> None:
    fig, axes = frame("F07")
    axes[0].plot([1, 2, 3], [1, 2, 3])
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    assert axes[0].get_window_extent(renderer).y1 < fig.texts[0].get_window_extent(renderer).y0
    plt.close(fig)
