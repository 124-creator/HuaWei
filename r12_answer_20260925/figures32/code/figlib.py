# /// script
# requires-python = ">=3.12"
# dependencies = ["matplotlib==3.11.1", "numpy"]
# ///
"""Shared publication style and evidence-preserving exports.

AI-assisted: OpenCode/Sisyphus, OpenAI; public model release date unverified.
"""
import csv
import hashlib
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.figure import Figure
from matplotlib.text import Text

from helpers import merge_busy
from specs import INDEX

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "dataset.json").read_bytes())
CONFIG = json.loads((ROOT.parent / "SOURCE_MANIFEST.json").read_bytes())
sys.path.insert(0, CONFIG["workflow_tools"])
import plot_style as ps

ps.setup()
plt.rcParams.update({"font.size": 9.5, "xtick.labelsize": 8.5, "ytick.labelsize": 8.5,
                    "legend.fontsize": 8.3, "axes.titlesize": 9.5, "svg.hashsalt": "R12-32"})
COLORS = {"A": "#3C5488", "B": "#007C83", "L2": "#B16D24", "C3": "#858585",
          "partition": "#3C5488", "spill": "#B66A4D", "good": "#267F74", "bad": "#B55252"}
PIPE_COLORS = {"PIPE_M": "#3C5488", "PIPE_V": "#007C83", "PIPE_MTE2": "#C18A35", "PIPE_MTE3": "#A66055"}
PIPE_LABELS = {"PIPE_M": "M", "PIPE_V": "V", "PIPE_MTE2": "IN", "PIPE_MTE3": "OUT"}
type Cell = str | int | float | bool


def visible_texts(fig: Figure) -> list[Text]:
    # Axis objects retain ticks outside the view interval; those labels are not drawn.
    excluded = set()
    for ax in fig.axes:
        for axis in (ax.xaxis, ax.yaxis):
            lo, hi = sorted(axis.get_view_interval())
            for tick in axis.get_major_ticks() + axis.get_minor_ticks():
                if not lo <= tick.get_loc() <= hi:
                    excluded.update((id(tick.label1), id(tick.label2)))
    return [t for t in fig.findobj(Text) if t.get_visible() and t.get_text().strip() and id(t) not in excluded]


def frame(key: str, shape: tuple[int, int] = (1, 1), height: float = 100) -> tuple[Figure, np.ndarray]:
    fig, axes = ps.new_fig(width_in=166/25.4, height_in=height/25.4, nrows=shape[0], ncols=shape[1], squeeze=False)
    fig.get_layout_engine().set(rect=(0, 0.075, 1, 0.84))
    spec = INDEX[key]
    fig.suptitle(f"{key}  {spec.title}", fontsize=10.5, y=0.99)
    fig.text(0.5, 0.018, spec.note, ha="center", va="bottom", fontsize=8.2, color="#404040")
    return fig, axes.ravel()


def save(fig: Figure, key: str, rows: Sequence[Mapping[str, Cell]]) -> None:
    assert rows
    for folder in ("figures", "data", "metadata"):
        (ROOT / folder).mkdir(exist_ok=True)
    ps.assert_no_overlap(fig)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    bounds = fig.bbox
    texts = visible_texts(fig)
    title = fig.texts[0]
    title_box = title.get_window_extent(renderer)
    assert all(ax.get_window_extent(renderer).y1 + 2 < title_box.y0 for ax in fig.axes), (key, "title enters plot")
    assert not any(t is not title and title_box.overlaps(t.get_window_extent(renderer)) for t in texts), (key, "title overlaps text")
    clipped = []
    for t in texts:
        box = t.get_window_extent(renderer)
        if box.x0 < bounds.x0-2 or box.y0 < bounds.y0-2 or box.x1 > bounds.x1+2 or box.y1 > bounds.y1+2:
            clipped.append(t.get_text())
    assert not clipped, (key, clipped)
    assert min(t.get_fontsize() for t in texts) >= 7.8
    with (ROOT / "data" / f"{key}.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        fields = list(dict.fromkeys(k for row in rows for k in row))
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)
    files = {}
    for suffix in ("pdf", "png", "svg"):
        path = ROOT / "figures" / f"{key}.{suffix}"
        fig.savefig(path, dpi=600, metadata={"Creator": "R12 evidence figures"} if suffix == "pdf" else None)
        files[suffix] = hashlib.sha256(path.read_bytes()).hexdigest()
    spec = INDEX[key]
    lines = [{"axis": i, "label": line.get_label(), "x": [float(x) for x in line.get_xdata()],
              "y": [float(y) for y in line.get_ydata()]} for i, ax in enumerate(fig.axes) for line in ax.lines]
    record = {"id": key, "kind": spec.kind, "title": spec.title, "reading_question": spec.question,
              "caveat": spec.note, "sources": spec.sources.split(","), "data_rows": len(rows),
              "data_sha256": hashlib.sha256((ROOT/"data"/f"{key}.csv").read_bytes()).hexdigest(),
              "files": files, "width_mm": 166, "height_mm": fig.get_figheight()*25.4,
              "minimum_source_font_pt": min(t.get_fontsize() for t in texts), "clipped_text": clipped,
              "plotted_lines": lines, "source_binding": "INPUTS.json (private audit record)",
              "scientific_acceptance": "NOT_GRANTED_BY_RENDERER"}
    with (ROOT/"metadata"/f"{key}.json").open("w", encoding="utf-8") as stream:
        json.dump(record, stream, ensure_ascii=False, indent=2)
    plt.close(fig)
    print(f"RENDERED {key}: {len(rows)} source rows", flush=True)


def timeline(ax, rows: Sequence[Mapping[str, Cell]], title: str) -> None:
    ymax = 20
    for core in range(5):
        for offset, pipe in enumerate(PIPE_COLORS):
            selected = [(r["start"], r["end"]) for r in rows if r["core"] == core and r["pipe"] == pipe]
            merged = merge_busy(selected)
            assert sum(b-a for a, b in merged) <= rows[0]["T"]
            spans = [(a/1e6, (b-a)/1e6) for a, b in merged]
            ax.broken_barh(spans, (core*4+offset-0.34, 0.68), facecolors=PIPE_COLORS[pipe], edgecolors="none")
    labels = [f"C{c}  {PIPE_LABELS[p]}" for c in range(5) for p in PIPE_COLORS]
    ax.set(yticks=np.arange(ymax), yticklabels=labels, ylim=(19.7, -0.7), xlabel="执行时间 / 百万 cycles", title=title)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="y", visible=False)


def boxes(ax, arrays: Sequence[Sequence[float]], labels: Sequence[str]) -> None:
    ax.boxplot(arrays, tick_labels=labels, showfliers=True, patch_artist=True,
               boxprops={"facecolor": "#DAE7EA", "edgecolor": "#426572"},
               medianprops={"color": "#222222", "linewidth": 1.4},
               flierprops={"marker": ".", "markersize": 3, "markerfacecolor": "#426572", "markeredgecolor": "#426572"})


def group(scene: str, k: int) -> list:
    return [r for r in DATA["selected"] if r["scene"] == scene and r["k"] == k]
