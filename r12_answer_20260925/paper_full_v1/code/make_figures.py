"""新增两张图：F35 全文技术路线（结构示意），F36 最优性间隙上界分布（冻结校验数据）。

输出到 ../figures/：PNG(600dpi)、PDF、SVG，以及F36作图数据CSV。
只读 publication/sources/closeout/results/verification.json 与 figures_v3/delivery/data/F31.csv。
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
    "font.family": ["WenQuanYi Zen Hei", "DejaVu Sans"], "font.size": 9, "axes.unicode_minus": False,
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


def f35():
    fig = plt.figure(figsize=(166 * MM, 150 * MM))
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    box(ax, 0.03, 0.925, 0.94, 0.058,
        "输入：100张操作—张量计算图 ＋ 固定硬件配置 θ（L1/UB容量、60 bytes/cycle共享DDR、等待常数）",
        fc=COLORS["light"], fs=8.2)
    box(ax, 0.03, 0.775, 0.94, 0.118,
        "第4章 统一建模：方案 P=(g, a, π)；覆盖、唯一排布与联合无环；字典序目标 (T, D_added)\n"
        "评价语义约束：数据依赖、Pipe串行、Task释放、活跃集合容量、带宽公平共享\n"
        "复杂性与下界：命题4.1（NP难）；与方案无关的计算下界 LB_k 与窗口下界",
        fc="white", fs=8.2)
    cols = [("A", "第5章 问题一 · 场景A\n代价：Task边界搬运与启动等待",
             "安全链收缩\n依赖带弱连通分组（w=4,8,2,16）\n尾长优先的追加式分核\n划分不变的反馈重排\nTreap区间索引插入候选"),
            ("B", "第6章 问题二 · 场景B\n代价：核内驻留与容量溢出",
             "共用部件（安全链、基础构造、插入）\n＋活动核数与驻留组织候选\n＋关键链局部移动\n＋Spill触发的局部微批\n核归属不变 ⇒ 边界COPY不变"),
            ("L2", "第7章 问题三 · 共享只读L2\n代价：命中、逐出与双带宽池",
             "沿用场景B的全部部件\n＋同一请求内跨配置重评价\nFIFO：发射时命中、完成时插入\n同方案配置比 R_hw\n分别选优比 R_select 与分解恒等式")]
    x0, w, gap = 0.03, 0.30, 0.02
    for i, (key, head, body) in enumerate(cols):
        x = x0 + i * (w + gap)
        box(ax, x, 0.635, w, 0.085, head, fc=COLORS[key], ec=COLORS[key], fs=8.2, weight="bold")
        ax.texts[-1].set_color("white")
        box(ax, x, 0.425, w, 0.2, body, fc="white", ec=COLORS[key], fs=8.0, lw=1.1)
        arrow(ax, 0.5, 0.775, x + w / 2, 0.722)
        arrow(ax, x + w / 2, 0.425, x + w / 2, 0.382)
    box(ax, 0.03, 0.262, 0.94, 0.118,
        "评价择优闭环：候选生成 → 覆盖/联合无环检查与哈希去重 → 下界剪枝 → 官方评价器（黑箱目标）→ 字典序择优\n"
        "官方时间线反馈 → 反馈重排、关键链移动与Spill诊断\n"
        "停止准则：预算用尽／候选枚举完毕／当前解 T ≤ 1.03·LB（近优认证）",
        fc=COLORS["light"], fs=8.2)
    arrow(ax, 0.5, 0.262, 0.5, 0.212)
    box(ax, 0.03, 0.125, 0.94, 0.085,
        "第8章 模型检验：可证下界与间隙上界 ｜ 相对C3的配对检验\n核数与图规模的稳健性 ｜ 预算敏感性与求解成本",
        fc="white", fs=8.2)
    arrow(ax, 0.5, 0.125, 0.5, 0.083)
    box(ax, 0.03, 0.012, 0.94, 0.07,
        "输出：1至5核平均加速比曲线；L2两配置对比曲线与配置比\n逐例Makespan、新增COPY与命中率；可复现Python程序",
        fc=COLORS["light"], fs=8.2)
    save(fig, "F35")


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
    f35(); f36(); print("figures ->", OUT)
