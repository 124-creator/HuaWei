# /// script
# requires-python = ">=3.12"
# dependencies = ["matplotlib==3.11.1"]
# ///
"""Native-vector scene primitives; used by build.py with existing Python."""
from collections.abc import Sequence
from typing import Final

from matplotlib.patches import Ellipse, FancyArrowPatch, Rectangle

from figlib import Cell, frame, save

INK: Final = "#253845"
BLUE: Final = "#365D87"
TEAL: Final = "#087F83"
AMBER: Final = "#A66B20"
RED: Final = "#AB4949"
PALE_BLUE: Final = "#E9F0F7"
PALE_TEAL: Final = "#E5F2EF"
PALE_AMBER: Final = "#F8F0E2"
GRAY: Final = "#697781"


class Scene:
    """Mutable artist builder that records conceptual geometry, never measured data."""

    def __init__(self, key: str, height: float = 136) -> None:
        self.key = key
        self.fig, axes = frame(key, height=height)
        self.ax = axes[0]
        self.ax.set(xlim=(0, 100), ylim=(0, 100))
        self.ax.axis("off")
        self.rows: list[dict[str, Cell]] = []

    def label(self, at: tuple[float, float], text: str, *, size: float = 9.0,
              color: str = INK, align: str = "center", bold: bool = False) -> None:
        self.ax.text(*at, text, ha=align, va="center", fontsize=size, color=color,
                     weight="bold" if bold else "normal", linespacing=1.5, zorder=5)
        self.rows.append({"record": "label", "x": at[0], "y": at[1], "text": text})

    def box(self, rect: tuple[float, float, float, float], text: str = "", *,
            fill: str = "white", stroke: str = BLUE, dashed: bool = False,
            size: float = 9.0, hatch: str = "", layer: float = 2) -> None:
        x, y, w, h = rect
        self.ax.add_patch(Rectangle((x, y), w, h, facecolor=fill, edgecolor=stroke,
                                   linewidth=1.1, linestyle="--" if dashed else "-",
                                   hatch=hatch, zorder=layer))
        self.rows.append({"record": "region", "x": x, "y": y, "w": w, "h": h,
                          "text": text, "fill": fill, "hatch": hatch, "layer": layer})
        if text:
            self.label((x + w / 2, y + h / 2), text, size=size)

    def tensor(self, at: tuple[float, float], name: str) -> None:
        self.ax.add_patch(Ellipse(at, 4.9, 5.3, facecolor=PALE_AMBER,
                                 edgecolor=AMBER, linewidth=1.1, zorder=3))
        self.label(at, name, size=8.5)
        self.rows.append({"record": "tensor", "x": at[0], "y": at[1], "text": name})

    def link(self, points: Sequence[tuple[float, float]], *, color: str = GRAY,
             dashed: bool = False, arrow: bool = True, both: bool = False) -> None:
        style = "--" if dashed else "-"
        if len(points) > 2:
            self.ax.plot([p[0] for p in points[:-1]], [p[1] for p in points[:-1]],
                         color=color, lw=1.05, ls=style, zorder=1)
        heads = "<|-|>" if both else ("-|>" if arrow else "-")
        self.ax.add_patch(FancyArrowPatch(points[-2], points[-1], arrowstyle=heads,
                                         mutation_scale=9, linewidth=1.05, linestyle=style,
                                         color=color, shrinkA=0, shrinkB=0, zorder=1))
        for i, (a, b) in enumerate(zip(points, points[1:])):
            self.rows.append({"record": "relationship", "segment": i, "x": a[0], "y": a[1],
                              "end_x": b[0], "end_y": b[1], "dashed": dashed, "color": color})

    def panel(self, at: tuple[float, float], title: str) -> None:
        self.label(at, title, size=9.7, bold=True, align="left")

    def finish(self) -> None:
        save(self.fig, self.key, self.rows)
