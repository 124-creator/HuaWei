# 本程序及代码是在人工智能工具辅助下完成的。
# 人工智能工具名称、版本/型号、开发机构/公司、版本发布日期：【由参赛队按实际使用情况填写，见论文附录D】
"""论文新增图件的生成入口。

F35 技术路线、F38/F39/F40 三问求解流程：见 flowcharts.py（由队伍流程图初稿优化与适配而来）。
原F37“统一求解流程”已由三问各自的流程图取代，不再生成；f36()为已随原8.2节删除的下界间隙分布图，保留代码备查。
输出到 ../figures/：PNG(600dpi)、PDF、SVG。
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

HERE = Path(__file__).resolve().parent
R12 = HERE.parents[1]
OUT = HERE.parent / "figures"
COLORS = {"A": "#3C5488", "B": "#007C83", "L2": "#B16D24", "grey": "#555555", "light": "#F3F4F7"}
plt.rcParams.update({
    "font.family": ["Liberation Serif", "WenQuanYi Zen Hei", "DejaVu Serif"], "font.size": 9, "axes.unicode_minus": False,
    "svg.hashsalt": "R12-paper", "pdf.fonttype": 42, "axes.spines.top": False, "axes.spines.right": False,
})
MM = 1 / 25.4


def save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "pdf", "svg"):
        kw = {"dpi": 600} if ext == "png" else {}
        fig.savefig(OUT / f"{name}.{ext}", bbox_inches="tight", pad_inches=0.04, metadata=None if ext != "pdf" else {"CreationDate": None}, **kw)
    plt.close(fig)


def box(ax, x, y, w, h, text, fc="white", ec=COLORS["grey"], fs=8.6, weight="normal", lw=0.9):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.006,rounding_size=0.012",
                                fc=fc, ec=ec, lw=lw))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, weight=weight, linespacing=1.45)


def arrow(ax, x0, y0, x1, y1, text=None, color=COLORS["grey"], rad=0.0):
    ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>", mutation_scale=9, lw=0.9,
                                 color=color, connectionstyle=f"arc3,rad={rad}"))
    if text:
        ax.text((x0 + x1) / 2 + 0.01, (y0 + y1) / 2, text, fontsize=7.6, color=color, ha="left", va="center")


def f36():
    ver = json.loads((R12 / "publication/sources/closeout/results/verification.json").read_text(encoding="utf-8"))
    groups = [("A", k) for k in (2, 3, 4, 5)] + [("B", k) for k in range(1, 6)] + [("L2", k) for k in range(1, 6)]
    data = {g: [] for g in groups}
    rows = []
    for c in ver["checks"]:
        if c["kind"] != "selected":
            continue
        g = (c["scene"], c["cores"])
        data[g].append(c["compute_gap_upper_bound"] * 100)
        rows.append({"scene": c["scene"], "cores": c["cores"], "case": c["case"],
                     "lower_bound": c["global_compute_lower_bound"], "gap_upper_bound_pct": c["compute_gap_upper_bound"] * 100})
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "F36.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(sorted(rows, key=lambda r: (r["scene"], r["cores"], r["case"])))
    fig, axes = plt.subplots(1, 2, figsize=(166 * MM, 78 * MM), gridspec_kw={"width_ratios": [1.35, 1]})
    ax = axes[0]
    pos = []; p = 0
    for i, g in enumerate(groups):
        if i and g[0] != groups[i - 1][0]:
            p += 0.8
        pos.append(p); p += 1
    floor = 0.01
    vals = [[max(v, floor) for v in data[g]] for g in groups]
    bp = ax.boxplot(vals, positions=pos, widths=0.62, patch_artist=True, showfliers=True,
                    flierprops=dict(marker="o", markersize=1.8, alpha=.55, markeredgewidth=0),
                    medianprops=dict(color="black", lw=1.0), whiskerprops=dict(lw=.8), capprops=dict(lw=.8))
    for patch, g in zip(bp["boxes"], groups):
        patch.set_facecolor(COLORS[g[0]]); patch.set_alpha(.35); patch.set_edgecolor(COLORS[g[0]])
    for fl, g in zip(bp["fliers"], groups):
        fl.set_markerfacecolor(COLORS[g[0]])
    ax.set_yscale("log"); ax.set_ylim(0.008, 900)
    ax.set_yticks([0.01, 0.1, 1, 10, 100], ["0.01", "0.1", "1", "10", "100"])
    ax.yaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    ax.axhline(3, color="#B55252", ls="--", lw=.9)
    ax.text(pos[-1] + .45, 3, "3%\n近优认证线", color="#B55252", fontsize=7.2, va="center", ha="left")
    ax.set_xticks(pos, [f"{s}-{k}" if s == "L2" else f"{s}{k}" for s, k in groups], fontsize=7.2, rotation=0)
    ax.set_ylabel("间隙上界 γ /%（对数轴）")
    ax.set_title("(a) 各场景、各核数的间隙上界分布", fontsize=9)
    ax = axes[1]
    bins = [(0, 3, "≤3%"), (3, 10, "3%–10%"), (10, 50, "10%–50%"), (50, math.inf, ">50%")]
    shades = ["#267F74", "#8FBFB7", "#D9C58F", "#C98B77"]
    labels = [f"{s}-{k}" if s == "L2" else f"{s}{k}" for s, k in groups]
    left = [0] * len(groups)
    for (lo, hi, name), col in zip(bins, shades):
        cnt = [sum(lo < v <= hi if lo > 0 else v <= hi for v in data[g]) for g in groups]
        ax.barh(range(len(groups)), cnt, left=left, color=col, edgecolor="white", lw=.4, label=name, height=.72)
        left = [a + b for a, b in zip(left, cnt)]
    ax.set_yticks(range(len(groups)), labels, fontsize=7.4); ax.invert_yaxis()
    ax.set_xlim(0, 100); ax.set_xlabel("图数（每组100张）")
    ax.set_title("(b) 间隙上界的分档计数", fontsize=9)
    ax.legend(ncols=4, fontsize=7.2, loc="upper center", bbox_to_anchor=(0.45, -0.16), frameon=False, handlelength=1.2, columnspacing=.8)
    fig.tight_layout(w_pad=1.2)
    save(fig, "F36")




if __name__ == "__main__":
    import flowcharts
    flowcharts.roadmap(OUT); flowcharts.q1_flow(OUT); flowcharts.q2_flow(OUT); flowcharts.q3_flow(OUT)
    print("figures ->", OUT)
