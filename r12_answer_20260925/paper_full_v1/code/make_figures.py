"""新增图：F35 全文技术路线、F37 R12求解流程（均为结构示意，不含实验数据）。

输出到 ../figures/：PNG(600dpi)、PDF、SVG。字体与队伍图件（figures_v3）一致：
西文用Times系衬线体（Liberation Serif），中文用黑体（WenQuanYi Zen Hei）。
f36()为已随原8.2节删除的下界间隙分布图，保留代码备查，不再调用。
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


def f35():
    fig = plt.figure(figsize=(166 * MM, 150 * MM))
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    box(ax, 0.03, 0.925, 0.94, 0.058,
        "输入：100张操作—张量计算图 ＋ 固定硬件配置 θ（L1/UB容量、60 bytes/cycle共享DDR、等待常数）",
        fc=COLORS["light"], fs=8.2)
    box(ax, 0.03, 0.775, 0.94, 0.118,
        "第4章 统一建模：方案 P=(g, a, π)；覆盖、唯一排布与联合无环；字典序目标（Makespan，新增搬运量）\n"
        "评价语义约束：数据依赖、Pipe串行、Task释放、活跃集合容量、带宽公平共享\n"
        "复杂性与下界：命题4.1（NP难）；与方案无关的计算下界 LB 与窗口下界",
        fc="white", fs=8.2)
    cols = [("A", "第5章 问题一 · 场景A\n代价：Task边界搬运与启动等待",
             "安全链收缩\n依赖带弱连通分组（w=4,8,2,16）\n尾长优先的追加式分核\n划分不变的反馈重排\nTreap区间索引插入候选"),
            ("B", "第6章 问题二 · 场景B\n代价：核内驻留与容量溢出",
             "共用部件（安全链、基础构造、插入）\n＋活动核数与驻留组织候选\n＋关键链局部移动\n＋Spill触发的局部微批\n核归属不变 ⇒ 边界COPY不变"),
            ("L2", "第7章 问题三 · 共享只读L2\n代价：命中、逐出与双带宽池",
             "沿用场景B的全部部件\n＋同一请求内跨配置重评价\nFIFO：发射时命中、完成时插入\n同方案配置比与分别选优比\n逐例分解恒等式")]
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
        "第8章 模型检验：证据矩阵 ｜ 加速比分布与并行效率 ｜ 相对C3的配对检验\n稳健性分析：核数与图规模 ｜ 白盒统计：最终方案来源 ｜ 灵敏度分析：求解预算",
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


# ---------------------------------------------------------------- F37 求解流程
H37 = 221.0          # 图高（mm），坐标系以mm为单位、原点在左下


def _y(top):
    return H37 - top


def node(ax, cx, top, w, h, text, ec, fc="white", fs=8.2, lw=1.0, round_=1.6, weight="normal", color="black"):
    ax.add_patch(FancyBboxPatch((cx - w / 2, _y(top + h)), w, h, boxstyle=f"round,pad=0,rounding_size={round_}",
                                fc=fc, ec=ec, lw=lw))
    ax.text(cx, _y(top + h / 2), text, ha="center", va="center", fontsize=fs, linespacing=1.35,
            weight=weight, color=color)
    return {"l": cx - w / 2, "r": cx + w / 2, "t": top, "b": top + h, "cx": cx, "cy": top + h / 2}


def diamond(ax, cx, top, w, h, text, ec, fc="white", fs=8.2):
    from matplotlib.patches import Polygon
    cy = top + h / 2
    ax.add_patch(Polygon([(cx, _y(top)), (cx + w / 2, _y(cy)), (cx, _y(top + h)), (cx - w / 2, _y(cy))],
                         closed=True, fc=fc, ec=ec, lw=1.0))
    ax.text(cx, _y(cy), text, ha="center", va="center", fontsize=fs)
    return {"l": cx - w / 2, "r": cx + w / 2, "t": top, "b": top + h, "cx": cx, "cy": cy}


def path(ax, pts, label=None, at=0, dx=1.2, dy=-2.2, color=COLORS["grey"], ls="-", ha="left"):
    """折线箭头：pts为(x, top)序列，箭头画在最后一段；label标在第at段起点附近。"""
    xy = [(x, _y(t)) for x, t in pts]
    for (x0, y0), (x1, y1) in zip(xy[:-2], xy[1:-1]):
        ax.plot([x0, x1], [y0, y1], color=color, lw=0.9, ls=ls, solid_capstyle="butt")
    ax.add_patch(FancyArrowPatch(xy[-2], xy[-1], arrowstyle="-|>", mutation_scale=8, lw=0.9, color=color,
                                 linestyle=ls, shrinkA=0, shrinkB=0))
    if label:
        x, y = xy[at]
        ax.text(x + dx, y + dy, label, fontsize=7.8, color=color, ha=ha, va="center")


def f37():
    fig = plt.figure(figsize=(166 * MM, H37 * MM))
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 166); ax.set_ylim(0, H37); ax.axis("off")
    grey, red, cA, cB, cL = COLORS["grey"], "#B55252", COLORS["A"], COLORS["B"], COLORS["L2"]
    fcA, fcB, fcL, fcR = "#EDF0F7", "#E6F2F2", "#F7EFE6", "#FBEFEF"
    cx, W = 58, 92
    s = node(ax, cx, 3, 86, 10, "开始：计算图 G、核数 k、场景 s ∈ {A, B, L2}、软预算 600 s", ec=grey, fc=COLORS["light"], round_=5)
    lb = node(ax, cx, 18, W, 10, "计算与方案无关的下界 LB（计算下界与窗口下界）", ec=grey)
    b1 = node(ax, cx, 33, W, 13, "① 基础构造：分量、链波、分量批次（B/L2另加块迁移）\n逐个评价，得到首个可行解 P*", ec=grey)
    g = diamond(ax, cx, 51, 62, 15, "近优认证 T(P*) ≤ 1.03·LB？", ec=red, fc=fcR)
    c2 = node(ax, cx, 71, W, 9, "② 减少活动核心的候选（至多6个）", ec=grey)
    dA = diamond(ax, cx, 85, 44, 13, "场景A？", ec=grey, fc=COLORS["light"])
    a3 = node(ax, 34, 104, 44, 14, "③ 依赖带候选 w ∈ {4, 8, 2, 16}\n安全链收缩→弱连通分组\n→尾长优先的追加式分核", ec=cA, fc=fcA, fs=7.9)
    a4 = node(ax, 34, 122, 44, 11, "④ 反馈重排：划分 g 不变，\n按实测Task时长重新分核", ec=cA, fc=fcA, fs=7.9)
    b3 = node(ax, 82, 104, 44, 14, "③′ 关键链局部移动\n（至多4个；仅用于不超过\n10000个操作的图）", ec=cB, fc=fcB, fs=7.9)
    f5 = node(ax, cx, 139, W, 10, "⑤ 分量家族：m ≤ k，target ∈ {0, 512, 2048}，至多评价6个", ec=grey)
    dL = diamond(ax, cx, 154, 44, 13, "场景L2？", ec=grey, fc=COLORS["light"])
    l6 = node(ax, 72, 171, 64, 11, "⑥ 跨配置重评价：独立求解一个B方案\n（至多180 s）后按L2配置评价（至多40 s）", ec=cL, fc=fcL, fs=7.9)
    i7 = node(ax, cx, 186, W, 11, "⑦ 插入式候选：HEFT式优先级＋Treap区间索引\n生成≤30 s，评价≤120 s", ec=grey, fs=7.9)
    dS = diamond(ax, 42, 201, 48, 13, "B/L2 且 Spill > 0？", ec=grey, fc=COLORS["light"], fs=7.9)
    m8 = node(ax, 96, 201, 48, 13, "⑧ Spill触发的局部微批：\n诊断≤40 s，至多2个候选，\n每个评价≤45 s", ec=cB, fc=fcB, fs=7.9)
    out = node(ax, 145, 202.5, 32, 10, "输出 P*\n与官方评价结果", ec=grey, fc=COLORS["light"], round_=5, fs=7.9)
    # 主干
    path(ax, [(cx, s["b"]), (cx, lb["t"])])
    path(ax, [(cx, lb["b"]), (cx, b1["t"])])
    path(ax, [(cx, b1["b"]), (cx, g["t"])])
    path(ax, [(cx, g["b"]), (cx, c2["t"])], label="否", at=0, dy=-2.4)
    path(ax, [(cx, c2["b"]), (cx, dA["t"])])
    path(ax, [(dA["l"], dA["cy"]), (a3["cx"], dA["cy"]), (a3["cx"], a3["t"])], label="是", at=0, dx=-5, dy=1.6)
    path(ax, [(dA["r"], dA["cy"]), (b3["cx"], dA["cy"]), (b3["cx"], b3["t"])], label="否", at=0, dx=2.5, dy=1.6)
    path(ax, [(a3["cx"], a3["b"]), (a3["cx"], a4["t"])])
    path(ax, [(a4["cx"], a4["b"]), (a4["cx"], f5["t"])])
    path(ax, [(b3["cx"], b3["b"]), (b3["cx"], f5["t"])])
    path(ax, [(cx, f5["b"]), (cx, dL["t"])])
    path(ax, [(dL["r"], dL["cy"]), (l6["cx"] + 18, dL["cy"]), (l6["cx"] + 18, l6["t"])], label="是", at=0, dx=2.5, dy=1.6)
    path(ax, [(dL["l"], dL["cy"]), (22, dL["cy"]), (22, i7["t"])], label="否", at=0, dx=-5, dy=1.6)
    path(ax, [(l6["cx"] - 10, l6["b"]), (l6["cx"] - 10, i7["t"])])
    path(ax, [(dS["cx"], i7["b"]), (dS["cx"], dS["t"])])
    path(ax, [(dS["r"], dS["cy"]), (m8["l"], dS["cy"])], label="是", at=0, dx=1.2, dy=1.8)
    path(ax, [(m8["r"], m8["cy"]), (out["l"], m8["cy"])])
    path(ax, [(dS["cx"], dS["b"]), (dS["cx"], H37 - 2.5), (out["cx"], H37 - 2.5), (out["cx"], out["b"])],
         label="否", at=0, dx=1.2, dy=-1.9)
    # 近优认证：成立则跳过②—⑥，直接到⑦
    path(ax, [(g["r"], g["cy"]), (112, g["cy"]), (112, i7["cy"]), (i7["r"], i7["cy"])], label="是：跳过②—⑥", at=0,
         dx=1.2, dy=2.0, color=red)
    ax.text(91.5, _y(65), "各阶段开始前\n均重复此检查", fontsize=7.8, color=red, ha="left", va="center", linespacing=1.3)
    # 右侧：每个候选的统一处理
    x0, x1, top = 120, 164, 18
    xm = (x0 + x1) / 2
    steps = ["覆盖与联合无环检查", "方案哈希去重", "候选下界 > T(P*)\n则剪枝", "剩余预算不足则跳过",
             "官方评价器\n（黑箱目标）", "(T, 新增COPY, 名称)\n字典序严格更优\n则 P* ← 该候选"]
    hs = [9, 9, 12, 9, 12, 16]
    bot = top + 16 + sum(hs) + 3.5 * (len(hs) - 1) + 5
    ax.add_patch(FancyBboxPatch((x0, _y(bot)), x1 - x0, bot - top, boxstyle="round,pad=0,rounding_size=1.6",
                                fc="white", ec=grey, lw=0.9, ls=(0, (3, 2))))
    ax.text(xm, _y(top + 7), "每个候选的统一处理\n（①—⑧产生的候选）", ha="center", va="center", fontsize=8.2,
            weight="bold", linespacing=1.35)
    t = top + 16
    for i, (txt, h) in enumerate(zip(steps, hs)):
        fc = fcR if i == 5 else (COLORS["light"] if i == 4 else "white")
        node(ax, xm, t, 36, h, txt, ec=grey, fc=fc, fs=7.9, round_=1.2)
        if i < len(steps) - 1:
            path(ax, [(xm, t + h), (xm, t + h + 3.5)])
        t += h + 3.5
    # 图例
    lx, ly = x0 + 2, bot + 8
    for i, (name, ec, fc) in enumerate([("三个场景共用", grey, "white"), ("仅场景A", cA, fcA),
                                         ("场景B与L2", cB, fcB), ("仅L2场景", cL, fcL)]):
        yy = ly + i * 6.2
        ax.add_patch(FancyBboxPatch((lx, _y(yy + 4)), 7, 4, boxstyle="round,pad=0,rounding_size=0.8", fc=fc, ec=ec, lw=1.0))
        ax.text(lx + 9, _y(yy + 2), name, fontsize=7.8, va="center", ha="left")
    save(fig, "F37")


if __name__ == "__main__":
    f35(); f37(); print("figures ->", OUT)
