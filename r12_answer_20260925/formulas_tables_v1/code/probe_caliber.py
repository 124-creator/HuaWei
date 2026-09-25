# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Caliber probe: confirm frozen estimator conventions before building tables."""
import csv
import json
import math
from pathlib import Path

BASE = Path(r"E:/HWCupA2026/derived/r12_answer_20260925")
CO = BASE / "publication/sources/closeout/results"
C3 = BASE / "publication/sources/C3_official_cells.csv"


def main() -> None:
    sel = list(csv.DictReader((CO / "selected_per_case.csv").open(encoding="utf-8-sig")))
    a5 = [r for r in sel if r["scene"] == "A" and r["cores"] == "5"]
    walls = sorted(float(r["wall_seconds"]) for r in a5)
    print("A5 p95 nearest-rank:", walls[math.ceil(0.95 * len(walls)) - 1])
    cells = list(csv.DictReader(C3.open(encoding="utf-8-sig")))
    c3a5 = {r["case_id"]: float(r["makespan_cycles"]) for r in cells if r["problem"] == "A" and r["k"] == "5"}
    c3dm5 = {r["case_id"]: float(r["data_movement_bytes"]) for r in cells if r["problem"] == "A" and r["k"] == "5"}
    rat = [c3a5[r["case"]] / float(r["makespan"]) for r in a5]
    red = [1 - float(r["makespan"]) / c3a5[r["case"]] for r in a5]
    w = sum(float(r["makespan"]) < c3a5[r["case"]] for r in a5)
    t = sum(float(r["makespan"]) == c3a5[r["case"]] for r in a5)
    fmc = sum(float(r["makespan"]) < c3a5[r["case"]] and float(r["added_copy_bytes"]) > c3dm5[r["case"]] for r in a5)
    print("A5 ratio:", sum(rat) / len(rat), "red%:", 100 * sum(red) / len(red), "w/t/l:", w, t, len(a5) - w - t, "fmc:", fmc)
    pair = list(csv.DictReader((CO / "q3_paired_per_case.csv").open(encoding="utf-8-sig")))
    p5 = [r for r in pair if r["cores"] == "5"]
    spm = sum(float(r["same_plan_B_over_L2"]) for r in p5) / len(p5)
    ssm = sum(float(r["separate_selection_B_over_L2"]) for r in p5) / len(p5)
    fix = sum(float(r["fixed_singlecore"]) / float(r["L2_same_B_plan_makespan"]) for r in p5) / len(p5)
    hr = sum(float(r["L2_same_plan_hit_bytes"]) / (float(r["L2_same_plan_hit_bytes"]) + float(r["L2_same_plan_miss_bytes"])) for r in p5) / len(p5)
    l2sel = [r for r in sel if r["scene"] == "L2" and r["cores"] == "5"]
    selmean = sum(float(r["speedup"]) for r in l2sel) / len(l2sel)
    print("q3k5 same:", spm, "select:", ssm, "fixL2vsREF:", fix, "hit:", hr, "L2sel:", selmean)
    ds = json.loads((BASE / "figures_v3/dataset.json").read_bytes())["stages"]
    print("stage means:", sum(r["REF"] / r["control"] for r in ds) / 100,
          sum(r["REF"] / r["indexed"] for r in ds) / 100, sum(r["REF"] / r["full"] for r in ds) / 100)
    print("counts:", sum(r["indexed"] < r["control"] for r in ds), sum(r["full"] < r["indexed"] for r in ds))
    extra = list(csv.DictReader((CO / "budget_exceptions.csv").open(encoding="utf-8-sig")))
    print("budget exceptions:", [(r["case"], r["cores"], r["budget_seconds"]) for r in extra])


if __name__ == "__main__":
    main()
