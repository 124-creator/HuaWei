# /// script
# requires-python = ">=3.12"
# dependencies = ["matplotlib==3.11.1", "numpy"]
# ///
"""Existing-data Q2 case comparison and Q3 interpretation. Run through build.py."""
from statistics import mean, median

from figlib import COLORS, DATA, boxes, frame, save
from helpers import cdf_at
from v3_data import WINDOW, cache_marker


def f21() -> None:
    rows = DATA["stages"]
    cases = [r for r in rows if r["full"] < r["indexed"]]
    assert [r["case"] for r in cases] == ["case_067", "case_073"]
    fig, axes = frame("F21", (1, 2), 119)
    total_gain = sum(r["REF"] / r["full"] - r["REF"] / r["indexed"] for r in cases)
    for axis, row, color in zip(axes, cases, (COLORS["A"], COLORS["B"])):
        times = [row[k] for k in ("control", "indexed", "full")]
        normalized = [t / times[0] for t in times]
        axis.plot(range(3), normalized, "o-", color=color)
        for i, (value, raw) in enumerate(zip(normalized, times)):
            axis.annotate(f"{raw:,}", (i, value), xytext=(0, 10), textcoords="offset points",
                          fontsize=8, ha="center")
        reduction = 100 * (1 - row["full"] / row["indexed"])
        contribution = 100 * (row["REF"] / row["full"] - row["REF"] / row["indexed"]) / total_gain
        axis.set(xticks=range(3), xticklabels=["控制", "插入后", "微批后"], xlim=(-.3, 2.3),
                 ylim=(.57, 1.08), ylabel="该例阶段Makespan / 控制阶段Makespan", title=row["case"],
                 xlabel="标注为原始cycles；两图共用相对尺度")
        axis.text(.04, .12, f"插入后至微批后耗时降低 {reduction:.2f}%\n该阶段加速比增量贡献 {contribution:.2f}%",
                  transform=axis.transAxes, fontsize=8.1, linespacing=1.6)
    save(fig, "F21", rows)


def f24() -> None:
    rows = DATA["pairs"]
    fig, axes = frame("F24", (1, 2), 121)
    ks = list(range(1, 6))
    groups = [[r for r in rows if r["k"] == k] for k in ks]
    options = (("B", "无L2 / PB", COLORS["B"], "o-"),
               ("L2_fixed", "有L2 / 同一PB", COLORS["L2"], "s--"),
               ("L2_best", "有L2 / 另选PL", "#756580", "^:"))
    for field, label, color, style in options:
        values = [mean(r["REF"] / r[field] for r in group) for group in groups]
        axes[0].plot(ks, values, style, color=color, label=f"{label}  {values[-1]:.4f}")
    axes[0].set(xlabel="核心数", ylabel="相对REF的平均加速比", xticks=ks, ylim=(.9, 4.6),
                title="(a) 三类真实方案；图例末列为五核值")
    axes[0].legend(loc="upper left", fontsize=8.0)
    for field, label, color, style in (("hardware", "同方案配置比", COLORS["L2"], "o-"),
                                        ("selected", "分别选优比", "#756580", "^--")):
        axes[1].plot(ks, [mean(r[field] for r in group) for group in groups], style, color=color, label=label)
    axes[1].axhline(1, color="#777777", lw=.7, ls=":")
    axes[1].set(xlabel="核心数", ylabel="逐图耗时比的算术均值", xticks=ks, ylim=(.999, 1.034),
                title="(b) 两种比值；纵轴局部放大")
    axes[1].legend(loc="upper left", fontsize=8)
    save(fig, "F24", rows)


def f25() -> None:
    rows = DATA["pairs"]
    fig, axes = frame("F25", (1, 2), 127)
    boxes(axes[0], [[r["hardware"] for r in rows if r["k"] == k] for k in range(1, 6)], [str(k) for k in range(1, 6)])
    axes[0].axhline(1, color="#555555", ls="--", lw=.8)
    axes[0].set(xlabel="核心数", ylabel="同方案配置比 T_B / T_L", title="(a) 全部500对：长尾和退化均保留",
                ylim=(.985, max(r["hardware"] for r in rows) * 1.025))
    values = [r["hardware"] for r in rows if r["k"] == 5]
    unique = sorted(set(values))
    axes[1].step([unique[0], *unique], [0, *(cdf_at(values, x) for x in unique)],
                 where="post", color=COLORS["B"], label="五核ECDF / n=100")
    axes[1].axvline(median(values), color=COLORS["B"], ls="--", lw=1, label="中位数")
    axes[1].axvline(mean(values), color=COLORS["L2"], ls=":", lw=1.2, label="均值")
    axes[1].set(xlim=(.992, 1.04), ylim=(0, 1.02), xlabel="同方案配置比（局部视窗）",
                ylabel="完整100图的累计比例", title="(b) 五核：典型值与均值分开读")
    axes[1].legend(loc="upper left", fontsize=8, frameon=True, facecolor="white", edgecolor="none", framealpha=1)
    inside = round(100 * cdf_at(values, 1.04))
    axes[1].text(.98, .08, f"中位数 {median(values):.6f}\n均值 {mean(values):.6f}\n右侧视窗外仍有 {100-inside} 图",
                 transform=axes[1].transAxes, ha="right", fontsize=8.3, linespacing=1.6)
    save(fig, "F25", rows)


def f27() -> None:
    rows = DATA["cache"]
    marker = cache_marker()
    fig, axes = frame("F27", (2, 1), 157)
    x = [r["time"] / 1e6 for r in rows]
    axes[0].step(x, [r["used"] / 1048576 for r in rows], where="post", color=COLORS["L2"])
    axes[0].axhline(1, color="#555555", ls="--", lw=.8, label="L2容量")
    axes[0].set(ylabel="FIFO占用 / MiB", ylim=(-.02, 1.08), title="(a) 真实占用；阴影与F28使用同一窗口")
    axes[0].legend(loc="lower right")
    axes[0].annotate(f"e{marker.index}：insert\n占用净降 {marker.net_drop/1024:.0f} KiB",
                     (marker.time / 1e6, marker.after / 1048576), xytext=(.52, .37), fontsize=8.5,
                     arrowprops={"arrowstyle": "->", "color": COLORS["bad"], "lw": .8})
    axes[1].step(x, [100 * r["cumulative_hit"] for r in rows], where="post", color=COLORS["B"])
    axes[1].set(ylabel="累计命中字节率 / %", xlabel="绝对执行时间 / 百万 cycles", ylim=(0, 102),
                title=f"(b) 同一事件定位：t={marker.time:,} cycles")
    for axis in axes:
        axis.set_xlim(0, rows[0]["T"] / 1e6)
        axis.axvspan(WINDOW[0] / 1e6, WINDOW[1] / 1e6, facecolor="#E1C988", alpha=.22, zorder=0)
        axis.axvline(marker.time / 1e6, color=COLORS["bad"], lw=.8, ls=":", label="cache_event")
    save(fig, "F27", rows)


DRAW = {"F21": f21, "F24": f24, "F25": f25, "F27": f27}
