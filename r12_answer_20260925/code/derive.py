# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Existing Python: derive.py. Derive publication tables, never solve or score.

AI-assisted: OpenCode/Sisyphus, OpenAI; public model version/release date not
independently verified. All source experiments remain immutable.
"""
import csv
import json
from collections import Counter
from pathlib import Path
from statistics import mean, median
from typing import Mapping, Sequence

from metrics import paired_stats, p95

type Cell = str | float | int


def table(path: Path, rows: Sequence[Mapping[str, Cell]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    target = Path(__file__).resolve().parents[1]
    root = target / "publication"
    source = root / "sources/closeout/results"
    with (source / "selected_per_case.csv").open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    with (source / "q3_paired_per_case.csv").open(encoding="utf-8-sig", newline="") as stream:
        pairs = list(csv.DictReader(stream))
    with (root / "sources/C3_official_cells.csv").open(encoding="utf-8-sig", newline="") as stream:
        old = {(r["case_id"], r["k"], r["problem"]): r for r in csv.DictReader(stream)}
    cases = {r["case"] for r in rows}
    expected = {(c, str(k), s) for c in cases for s in ("A", "B", "L2")
                for k in range(1, 6) if s != "A" or k > 1}
    if len(cases) != 100 or len(rows) != 1400 or {(r["case"], r["cores"], r["scene"]) for r in rows} != expected:
        raise RuntimeError("Selected-cell coverage differs from the frozen contract")
    if len(pairs) != 500 or len({(r["case"], r["cores"]) for r in pairs}) != 500:
        raise RuntimeError("Incomplete fixed-plan comparison")
    root.joinpath("tables").mkdir(exist_ok=True)
    values = {}
    summary = []
    comparisons = []
    for scene in ("A", "B", "L2"):
        for k in range(1, 6):
            group = [r for r in rows if r["scene"] == scene and int(r["cores"]) == k]
            if not group:
                continue
            times = [(int(r["fixed_singlecore"]), int(r["makespan"])) for r in group]
            ref = paired_stats(times, 100)
            ratios = [a / b for a, b in times]
            walls = [float(r["wall_seconds"]) for r in group]
            item = {"scene": scene, "cores": k, "count": len(group), "mean_speedup": ref.ratio,
                    "median_speedup": median(ratios), "min_speedup": min(ratios),
                    "mean_added_MiB": mean(int(r["added_copy_bytes"]) for r in group) / 1048576,
                    "mean_partition_MiB": mean(int(r["partition_added_copy_bytes"]) for r in group) / 1048576,
                    "mean_spill_MiB": mean(int(r["spill_added_copy_bytes"]) for r in group) / 1048576,
                    "wall_median_s": median(walls), "wall_p95_s": p95(walls), "wall_max_s": max(walls),
                    "wins_REF": ref.wins, "ties_REF": ref.ties, "losses_REF": ref.losses,
                    "extended_budget": sum(float(r["budget_seconds"]) > 600 for r in group)}
            summary.append(item)
            comp = paired_stats([(int(old[(r["case"], r["cores"], scene)]["makespan_cycles"]), int(r["makespan"])) for r in group], 100)
            compared = {"scene": scene, "cores": k, "ratio_mean": comp.ratio,
                        "time_reduction_percent": comp.reduction_percent, "wins": comp.wins,
                        "ties": comp.ties, "losses": comp.losses,
                        "faster_more_copy": sum(int(r["makespan"]) < int(old[(r["case"], r["cores"], scene)]["makespan_cycles"])
                            and int(r["added_copy_bytes"]) > int(old[(r["case"], r["cores"], scene)]["data_movement_bytes"]) for r in group)}
            comparisons.append(compared)
            for name, value in item.items():
                if isinstance(value, (int, float)):
                    values[f"{scene}.k{k}.{name}"] = value
            for name, value in compared.items():
                if isinstance(value, (int, float)):
                    values[f"C3.{scene}.k{k}.{name}"] = value
    with (source / "q3_paired_summary.csv").open(encoding="utf-8-sig", newline="") as stream:
        q3 = list(csv.DictReader(stream))
    for row in q3:
        k = int(row["cores"])
        group = [r for r in pairs if int(r["cores"]) == k]
        computed = paired_stats([(int(r["B_makespan"]), int(r["L2_same_B_plan_makespan"])) for r in group], 100)
        if abs(computed.ratio - float(row["same_plan_mean"])) > 1e-12:
            raise RuntimeError("Paired summary is inconsistent")
        for name, value in row.items():
            values[f"Q3.k{k}.{name}"] = int(value) if name in {"cores", "count", "improved", "ties", "degraded", "different_final_plan_count"} else float(value)
        values[f"Q3.k{k}.hit_percent"] = 100 * float(row["same_plan_mean_byte_hit_rate"])
    for row in rows:
        if row["cores"] == "5" and row["case"] in {"case_002", "case_005", "case_026", "case_062", "case_073"}:
            for name in ("makespan", "added_copy_bytes", "partition_added_copy_bytes", "spill_added_copy_bytes"):
                values[f"case.{row['case']}.{row['scene']}.{name}"] = int(row[name])
    for row in pairs:
        if row["cores"] == "5" and row["case"] in {"case_026", "case_062", "case_073"}:
            for name in ("B_makespan", "L2_same_B_plan_makespan", "L2_selected_makespan", "same_plan_B_over_L2", "L2_same_plan_byte_hit_rate"):
                values[f"paired.{row['case']}.{name}"] = int(row[name]) if name.endswith("makespan") else float(row[name])
    budgets = Counter(float(r["budget_seconds"]) for r in rows)
    if budgets != {600.0: 1396, 1800.0: 4}:
        raise RuntimeError("Budget disclosure no longer matches source")
    table(root / "tables/summary.csv", summary)
    table(root / "tables/comparison_C3.csv", comparisons)
    table(root / "tables/display_values.csv", [values])
    table(root / "tables/Q1_per_case.csv", [{k: r[k] for k in ("case", "cores", "makespan", "added_copy_bytes", "partition_added_copy_bytes", "spill_added_copy_bytes", "budget_seconds", "wall_seconds")} for r in rows if r["scene"] == "A"])
    table(root / "tables/Q2_per_case.csv", [{k: r[k] for k in ("case", "cores", "makespan", "added_copy_bytes", "partition_added_copy_bytes", "spill_added_copy_bytes", "budget_seconds", "wall_seconds")} for r in rows if r["scene"] == "B"])
    columns = ("case", "cores", "B_makespan", "L2_same_B_plan_makespan", "L2_selected_makespan", "B_added_copy_bytes", "L2_same_plan_added_copy_bytes", "L2_selected_added_copy_bytes", "L2_same_plan_byte_hit_rate", "L2_selected_byte_hit_rate", "same_plan_B_over_L2", "separate_selection_B_over_L2")
    table(root / "tables/Q3_per_case.csv", [{k: r[k] for k in columns} for r in pairs])
    table(root / "tables/Q3_degraded.csv", [{k: r[k] for k in columns} for r in pairs if int(r["L2_same_B_plan_makespan"]) > int(r["B_makespan"])])
    result = {"artifact_kind": "PUBLICATION_PROJECTION_NOT_NEW_EXPERIMENT", "parent_frozen_source": "sources/closeout/results/selection.json",
              "runs": [{"id": "R12_PUBLICATION", "outputs": ["tables/display_values.csv"]}],
              "paper_formats": {key: 6 if "same_plan" in key or "separate_selection" in key else 4 for key in values},
              "paper_values": {key: {"value": value, "source_run": "R12_PUBLICATION", "column": key, "agg": "first"} for key, value in values.items()}}
    with (root / "RESULTS.json").open("w", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps({"status": "DERIVED", "cells": len(rows), "pairs": len(pairs), "display_values": len(values)}))


if __name__ == "__main__":
    main()
