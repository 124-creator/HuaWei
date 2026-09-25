# /// script
# requires-python = ">=3.12"
# dependencies = ["matplotlib==3.11.1"]
# ///
"""Existing Python: charts.py. Reuses the unchanged workflow plotting style.

AI-assisted: OpenCode/Sisyphus, OpenAI; model release information unverified.
Charts use frozen measured data, never image generation or synthetic results.
"""
import csv
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.figure import Figure


def save_chart(fig: Figure, path: Path) -> None:
    """Native PDF export avoids an unavailable system Cairo DLL; inspect the PDF."""
    fig.savefig(path.with_suffix(".pdf"), metadata={"Creator": "Matplotlib; R12 internal review"})
    fig.savefig(path.with_suffix(".png"), dpi=600)
    fig.savefig(path.with_suffix(".svg"), metadata={"Date": None})


def main() -> None:
    target = Path(__file__).resolve().parents[1]
    root = target / "publication"
    manifest = json.loads((target / "SOURCE_MANIFEST.json").read_bytes())
    sys.path.insert(0, manifest["workflow_tools"])
    import plot_style as ps

    ps.setup()
    with (root / "sources/closeout/results/q1_q2_standard_curve.csv").open(encoding="utf-8-sig", newline="") as stream:
        curves = list(csv.DictReader(stream))
    with (root / "sources/C3_official_cells.csv").open(encoding="utf-8-sig", newline="") as stream:
        old = list(csv.DictReader(stream))
    with (root / "sources/closeout/results/q3_paired_summary.csv").open(encoding="utf-8-sig", newline="") as stream:
        q3 = list(csv.DictReader(stream))
    with (root / "sources/closeout/results/selected_summary.csv").open(encoding="utf-8-sig", newline="") as stream:
        summary = list(csv.DictReader(stream))
    baseline = {r["case_id"]: int(r["makespan_cycles"]) for r in old if r["problem"] == "REF"}
    output = root / "figures"
    output.mkdir(exist_ok=True)
    plot_data = []
    colors = {"A": "#3C5488", "B": "#007C83"}
    names = {"A": "q1_curve", "B": "q2_curve"}
    x = list(range(1, 6))
    for scene in ("A", "B"):
        y = [float(r["mean_speedup"]) for r in curves if r["scene"] == scene]
        c3 = [1.0] + [sum(baseline[r["case_id"]] / int(r["makespan_cycles"]) for r in old if r["problem"] == scene and int(r["k"]) == k) / 100 for k in range(2, 6)]
        fig, ax = ps.new_fig(width_in=6.53, height_in=3.35)
        main_line, = ax.plot(x, y, "o-", color=colors[scene], label=f"R12 场景 {scene}")
        ax.plot(x, c3, "s--", color="#777777", label="C3 对照（非等搜索预算）")
        ax.set(xlabel="核心数", ylabel="相对固定整图单核的平均加速比", xticks=x, xlim=(0.85, 5.15), ylim=(0.9, 4.5))
        ax.legend(loc="upper left")
        ps.assert_no_overlap(fig)
        assert list(main_line.get_ydata()) == y
        save_chart(fig, output / names[scene])
        plot_data.append({"figure": names[scene], "x": x, "R12": y, "C3": c3, "reference_k1": "defined_as_one"})
        plt.close(fig)
    fig, axes = ps.new_fig(width_in=6.53, height_in=3.4, ncols=2)
    b = [float(r["mean_speedup"]) for r in summary if r["scene"] == "B"]
    fixed = [float(r["REF_over_L2_same_plan"]) for r in q3]
    hardware = [float(r["same_plan_mean"]) for r in q3]
    selected = [float(r["separate_selection_mean"]) for r in q3]
    axes[0].plot(x, b, "o-", color=colors["B"], label="无 L2：固定 B 方案")
    axes[0].plot(x, fixed, "s--", color="#3C5488", label="有 L2：同一 B 方案")
    axes[0].set(title="(a) 同方案性能", ylabel="相对 REF 的平均加速比", ylim=(0.9, 4.5))
    axes[0].legend(loc="upper left", fontsize=7.9)
    axes[1].plot(x, hardware, "o-", color="#3C5488", label="同方案配置比")
    axes[1].plot(x, selected, "^--", color="#B36B00", label="分别选优综合比")
    axes[1].axhline(1, color="#777777", linewidth=0.7, linestyle=":")
    axes[1].set(title="(b) 两种比较口径", ylabel="逐图 B/L2 耗时比的均值", ylim=(0.999, 1.034))
    axes[1].legend(loc="upper left", fontsize=7.9)
    for ax in axes:
        ax.set(xlabel="核心数", xticks=x, xlim=(0.85, 5.15))
    ps.assert_no_overlap(fig)
    save_chart(fig, output / "q3_configuration")
    plot_data.append({"figure": "q3_configuration", "x": x, "B_REF": b, "L2_fixed_REF": fixed,
                      "hardware_ratio": hardware, "selected_ratio": selected,
                      "right_axis": "enlarged_ratio_axis_not_zero_based"})
    plt.close(fig)
    with (output / "plot_data.json").open("w", encoding="utf-8") as stream:
        json.dump(plot_data, stream, ensure_ascii=False, indent=2)
    print(json.dumps({"status": "CHARTS_GENERATED", "figures": len(plot_data), "visual_review": "PENDING"}))


if __name__ == "__main__":
    main()
