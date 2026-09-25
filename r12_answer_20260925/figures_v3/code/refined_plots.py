# /// script
# requires-python = ">=3.12"
# dependencies = ["matplotlib==3.11.1", "numpy"]
# ///
"""Four evidence-preserving readability revisions; run through build.py."""
from statistics import mean

import numpy as np
from matplotlib.colors import TwoSlopeNorm

from figlib import COLORS, DATA, PIPE_COLORS, PIPE_LABELS, frame, group, save, timeline
from helpers import clip_intervals, merge_busy
from v3_data import WINDOW, cache_marker


def f08() -> None:
    rows = [r for r in DATA["selected"] if r["scene"] == "A"]
    matrix = np.array([[np.log2(r["versus_C3"]) for r in sorted(group("A", k), key=lambda r: r["case"])] for k in range(2, 6)])
    limit = float(max(abs(matrix.min()), abs(matrix.max())))
    fig, ax = frame("F08", (2, 1), 157)
    image = ax[0].imshow(matrix, aspect="auto", cmap="BrBG", norm=TwoSlopeNorm(vmin=-limit, vcenter=0, vmax=limit),
                         interpolation="nearest", extent=(.5, 100.5, 5.5, 1.5))
    bad = sorted([r for r in rows if r["T"] > r["C3_T"]], key=lambda r: (r["k"], r["case"]))
    ax[0].scatter([int(r["case"].split("_")[-1]) for r in bad], [r["k"] for r in bad],
                  marker="s", facecolors="none", edgecolors=COLORS["bad"], s=35, linewidths=1.2)
    ax[0].set(xticks=[1, 20, 40, 60, 80, 100], yticks=[2, 3, 4, 5], xlabel="用例编号（001—100）", ylabel="核心数",
              title="(a) 全部400格；红框额外标记退化，不改变色标")
    ax[0].grid(False)
    fig.colorbar(image, ax=ax[0], shrink=.85, label="log2(T_C3 / T_R12)")
    y = np.arange(len(bad))
    slowdown = [100 * (r["T"] / r["C3_T"] - 1) for r in bad]
    ax[1].hlines(y, 0, slowdown, color="#D4B4B4", lw=1.5)
    ax[1].scatter(slowdown, y, color=COLORS["bad"], s=26)
    for i, value in enumerate(slowdown):
        ax[1].annotate(f"{value:.3f}%", (value, i), xytext=(5, 0), textcoords="offset points", va="center", fontsize=8)
    ax[1].set(yticks=y, yticklabels=[f"{r['case']} / {r['k']}核" for r in bad],
              ylim=(len(bad) - .3, -.7), xlim=(0, max(slowdown) * 1.28 + .02),
              xlabel="相对C3的耗时增加 / %", title=f"(b) 全部{len(bad)}个退化配置，逐项可定位")
    ax[1].grid(axis="y", visible=False)
    save(fig, "F08", rows)


def f18() -> None:
    rows = sorted(group("B", 5), key=lambda r: (-r["spill"], r["case"]))
    spill = np.array([r["spill"] for r in rows], dtype=float)
    positive = spill[spill > 0]
    fig, ax = frame("F18", (1, 2), 124)
    ax[0].plot(np.arange(1, len(positive) + 1), positive / 1048576, "o", color=COLORS["spill"], ms=4)
    ax[0].set(yscale="log", xlabel="非零用例排序（Spill降序）", ylabel="Spill新增COPY / MiB（log10）",
              title=f"(a) 非零{len(positive)}图；零值{100 - len(positive)}图")
    cumulative = np.r_[0, np.cumsum(spill) / spill.sum() * 100]
    ax[1].plot(np.arange(101), cumulative, color=COLORS["spill"], lw=1.6)
    ax[1].plot([0, 100], [0, 100], ls=":", color="#999999", label="等量贡献参考")
    ax[1].scatter([10], [cumulative[10]], s=28, color=COLORS["spill"])
    ax[1].annotate(f"前10图：{cumulative[10]:.2f}%", (10, cumulative[10]), xytext=(32, 77), fontsize=8.5,
                   arrowprops={"arrowstyle": "-", "color": COLORS["spill"], "lw": .8})
    ax[1].set(xlabel="累计用例数（含零值）", ylabel="累计Spill字节占比 / %", xlim=(0, 100), ylim=(0, 104),
              title="(b) 完整100图的累计贡献")
    ax[1].legend(loc="lower right")
    save(fig, "F18", rows)


def f19() -> None:
    rows = DATA["stages"]
    fig, ax = frame("F19", (1, 2), 126)
    values = [mean(r["REF"] / r[k] for r in rows) for k in ("control", "indexed", "full")]
    ax[0].plot(range(3), values, "o-", color=COLORS["B"])
    ax[0].set(xticks=range(3), xticklabels=["控制", "插入后", "微批后"],
              ylabel="相对REF平均加速比", xlabel="同次请求阶段", title="(a) 纵轴局部放大；标明实际增量")
    ax[0].set_ylim(min(values) - .025, max(values) + .025)
    ax[0].set_xlim(-.25, 2.35)
    for i, value in enumerate(values):
        ax[0].annotate(f"{value:.6f}", (i, value), xytext=(0, 10), textcoords="offset points", ha="center", fontsize=8.2)
    for i in range(2):
        ax[0].text(i + .5, values[i] - .008,
                    f"Δ +{values[i + 1] - values[i]:.6f}", ha="center", fontsize=8, color=COLORS["B"])
    counts = [sum(r["indexed"] < r["control"] for r in rows), sum(r["full"] < r["indexed"] for r in rows)]
    ax[1].bar([0, 1], counts, color=[COLORS["A"], COLORS["B"]], width=.55)
    ax[1].set(xticks=[0, 1], xticklabels=["插入阶段", "微批阶段"], ylabel="较前阶段严格改善的图数",
              xlabel="其余含相同、未触发或未完成", ylim=(0, max(counts) * 1.45), title="(b) 全部100个请求为分母")
    for i, count in enumerate(counts):
        ax[1].text(i, count + .35, f"{count} / 100", ha="center", fontsize=8.8)
    save(fig, "F19", rows)


def f28() -> None:
    fig, old_axes = frame("F28", (2, 1), 235)
    for axis in old_axes:
        fig.delaxes(axis)
    grid = fig.add_gridspec(3, 2, height_ratios=[2, 2, 1.1])
    top = [fig.add_subplot(grid[0, :]), fig.add_subplot(grid[1, :])]
    detail = [fig.add_subplot(grid[2, 0]), fig.add_subplot(grid[2, 1])]
    b, l = DATA["timelineB"], DATA["timelineL2"]
    window = WINDOW
    for axis, rows, title in zip(top, (b, l), ("(a) 无L2：固定PB", "(b) 有L2：同一PB")):
        timeline(axis, rows, f"{title}；T = {rows[0]['T']:,} cycles")
        axis.set_xlim(0, b[0]["T"] / 1e6 * 1.01)
        axis.axvspan(window[0] / 1e6, window[1] / 1e6, facecolor="#E1C988", alpha=.25, zorder=0)
    for axis, rows, title in zip(detail, (b, l), ("(c) 无L2 / 核心0 / 局部", "(d) 有L2 / 核心0 / 局部")):
        for offset, pipe in enumerate(PIPE_COLORS):
            intervals = [(r["start"], r["end"]) for r in rows if r["core"] == 0 and r["pipe"] == pipe]
            clipped = clip_intervals(merge_busy(intervals), window)
            axis.broken_barh([(a / 1e6, (b - a) / 1e6) for a, b in clipped], (offset - .3, .6),
                             facecolors=PIPE_COLORS[pipe], edgecolors="none")
        axis.set(yticks=range(4), yticklabels=list(PIPE_LABELS.values()), ylim=(3.6, -.6),
                 xlim=(window[0] / 1e6, window[1] / 1e6), xlabel="绝对时间 / 百万 cycles", title=title)
        axis.grid(axis="y", visible=False)
    marker = cache_marker()
    for axis in (top[1], detail[1]):
        axis.axvline(marker.time / 1e6, color=COLORS["bad"], ls=":", lw=.8, label="cache_event")
    detail[1].set_title(f"(d) L2 / 核心0；红线e{marker.index}见F27", fontsize=8.5)
    rows = [{"configuration": "B", **r} for r in b] + [{"configuration": "L2_same_B", **r} for r in l]
    save(fig, "F28", rows)
