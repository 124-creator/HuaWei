# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Usage: existing WSL python -B -S summarize.py OUT.

Export separate fixed-plan hardware and independently-selected performance results.
The supplied execution checker is reused, not claimed as a new independent simulator.
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path
from statistics import mean, median

from evidence import digest, ratio_mean, read_score, require

type Cell = str | int | float | bool | None


def write_table(path: Path, rows: list[dict[str, Cell]]) -> None:
    require(bool(rows), f"Empty table: {path}")
    with path.open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main(out: Path) -> None:
    frozen = json.loads((out / "selection.json").read_bytes())
    paired = json.loads((out / "paired_results.json").read_bytes())
    root = Path(frozen["root"])
    require(paired["pairs_declaration_sha256"] == digest(out / "pairs.json"), "Pair declaration changed")
    require(all(digest(Path(p)) == h for p, h in frozen["inputs"].items()), "Frozen evidence changed")
    runs = {(r["case"], r["cores"], r["scene"]): r for r in frozen["runs"]}
    controls = {(r["case"], r["cores"]): r for r in paired["pairs"]}
    require(len(runs) == 1400 and len(controls) == 500, "Coverage mismatch")
    sys.path[:0] = [str(root / "stage4_src"), str(root / "src"), str(root / "official/code")]
    from validate_selected_execution import graph_view, verify_one

    audit = []
    seen = set()
    control_rows = []
    for case in sorted(frozen["baseline"]):
        graph = json.loads((root / "official/data" / f"{case}.json").read_bytes())
        view = graph_view(graph)
        for run in (r for key, r in runs.items() if key[0] == case):
            score = run["score"]
            key = (run["identity"]["graph_sha256"], run["identity"]["plan_sha256"], score["raw_sha256"])
            plan = json.loads(Path(run["plan"]).read_bytes())
            raw = json.loads(Path(score["raw"]).read_bytes())
            checked = verify_one(graph, view, plan, raw, run["scene"])
            require(max(op["end"] for core in raw["per_core_timeline"] for op in core["ops"]) == score["makespan"],
                    f"Timeline end mismatch: {key}")
            require(all(0 <= peak[tier] <= cap for peak in raw["memory_peak_by_core"].values()
                        for tier, cap in (("L1", 524288), ("UB", 131072))), "Reported capacity peak exceeded")
            audit.append({"case": case, "cores": run["cores"], "scene": run["scene"], "kind": "selected",
                          "plan_sha256": key[1], "raw_sha256": key[2], **checked})
            seen.add(key)
        for k in range(1, 6):
            pair = controls[(case, k)]
            b, optimized = runs[(case, k, "B")], runs[(case, k, "L2")]
            require(pair["identity"] == b["identity"], "Control identity does not match frozen B plan")
            if pair["metadata"]:
                require(digest(Path(pair["metadata"])) == pair["metadata_sha256"], "Reuse metadata changed")
            score = read_score(Path(pair["score"]["raw"]), "L2", k)
            require(score.raw_sha256 == pair["score"]["raw_sha256"], "Controlled L2 raw changed")
            require(score.partition_added_copy_bytes == b["score"]["partition_added_copy_bytes"] and
                    score.spill_added_copy_bytes == b["score"]["spill_added_copy_bytes"],
                    "Fixed-plan B/L2 pre-simulation COPY changed")
            key = (b["identity"]["graph_sha256"], b["identity"]["plan_sha256"], score.raw_sha256)
            if key not in seen:
                checked = verify_one(graph, view, json.loads(Path(b["plan"]).read_bytes()),
                                     json.loads(Path(score.raw).read_bytes()), "L2")
                audit.append({"case": case, "cores": k, "scene": "L2", "kind": "fixed_B_plan",
                              "plan_sha256": key[1], "raw_sha256": key[2], **checked})
                seen.add(key)
            tb, tl = b["score"]["makespan"], optimized["score"]["makespan"]
            control_rows.append({"case": case, "cores": k, "fixed_singlecore": frozen["baseline"][case],
                "B_makespan": tb, "L2_same_B_plan_makespan": score.makespan, "L2_selected_makespan": tl,
                "same_plan_B_over_L2": tb / score.makespan, "separate_selection_B_over_L2": tb / tl,
                "L2_reselection_gain": score.makespan / tl,
                "B_added_copy_bytes": b["score"]["added_copy_bytes"],
                "L2_same_plan_added_copy_bytes": score.added_copy_bytes,
                "L2_selected_added_copy_bytes": optimized["score"]["added_copy_bytes"],
                "L2_same_plan_hit_bytes": score.hit_bytes, "L2_same_plan_miss_bytes": score.miss_bytes,
                "L2_same_plan_byte_hit_rate": score.hit_rate,
                "L2_selected_byte_hit_rate": optimized["score"]["hit_rate"],
                "B_plan": b["plan"], "B_plan_sha256": b["identity"]["plan_sha256"],
                "L2_selected_plan_sha256": optimized["identity"]["plan_sha256"],
                "B_raw": b["score"]["raw"], "L2_same_plan_raw": score.raw,
                "L2_same_plan_raw_sha256": score.raw_sha256, "origin": pair["origin"]})
        print(f"VERIFIED {case}: selected outputs and fixed-plan controls", flush=True)
    require(all(digest(Path(p)) == h for p, h in frozen["inputs"].items()), "Inputs changed during audit")
    selected_rows = []
    for run in frozen["runs"]:
        row = {k: run[k] for k in ("case", "cores", "scene", "budget_seconds", "wall_seconds", "plan", "report")}
        row.update(run["score"])
        row.update(plan_sha256=run["identity"]["plan_sha256"], fixed_singlecore=frozen["baseline"][run["case"]],
                   speedup=frozen["baseline"][run["case"]] / run["score"]["makespan"])
        selected_rows.append(row)
    main_summary = []
    standard_curve = []
    for scene in ("A", "B", "L2"):
        for k in (range(2, 6) if scene == "A" else range(1, 6)):
            group = [r for r in selected_rows if r["scene"] == scene and r["cores"] == k]
            value = ratio_mean([(r["fixed_singlecore"], r["makespan"]) for r in group])
            main_summary.append({"scene": scene, "cores": k, "count": len(group), "mean_speedup": value,
                                 "budget_exceptions": sum(r["budget_seconds"] != 600 for r in group)})
            if scene in ("A", "B") and k >= 2:
                standard_curve.append({"scene": scene, "cores": k, "mean_speedup": value,
                                       "basis": "fixed_REF_over_selected"})
    for scene in ("A", "B"):
        standard_curve.append({"scene": scene, "cores": 1, "mean_speedup": 1.0, "basis": "defined_REF_over_REF"})
    q3_summary = []
    for k in range(1, 6):
        group = [r for r in control_rows if r["cores"] == k]
        hw = [r["same_plan_B_over_L2"] for r in group]
        q3_summary.append({"cores": k, "count": len(group),
            "same_plan_mean": ratio_mean([(r["B_makespan"], r["L2_same_B_plan_makespan"]) for r in group]),
            "same_plan_median": median(hw), "same_plan_min": min(hw), "same_plan_max": max(hw),
            "improved": sum(r["B_makespan"] > r["L2_same_B_plan_makespan"] for r in group),
            "ties": sum(r["B_makespan"] == r["L2_same_B_plan_makespan"] for r in group),
            "degraded": sum(r["B_makespan"] < r["L2_same_B_plan_makespan"] for r in group),
            "separate_selection_mean": ratio_mean([(r["B_makespan"], r["L2_selected_makespan"]) for r in group]),
            "REF_over_L2_same_plan": ratio_mean([(r["fixed_singlecore"], r["L2_same_B_plan_makespan"]) for r in group]),
            "same_plan_mean_byte_hit_rate": mean(r["L2_same_plan_byte_hit_rate"] for r in group),
            "different_final_plan_count": sum(r["B_plan_sha256"] != r["L2_selected_plan_sha256"] for r in group)})
    write_table(out / "selected_per_case.csv", selected_rows)
    write_table(out / "selected_summary.csv", main_summary)
    write_table(out / "q1_q2_standard_curve.csv", sorted(standard_curve, key=lambda r: (r["scene"], r["cores"])))
    write_table(out / "q3_paired_per_case.csv", control_rows)
    write_table(out / "q3_paired_summary.csv", q3_summary)
    write_table(out / "budget_exceptions.csv", [r for r in selected_rows if r["budget_seconds"] != 600])
    verification = {"status": "PASS_WITH_DISCLOSED_LIMITS", "selected_cells": len(runs), "same_plan_pairs": 500,
        "origin_counts": dict(Counter(r["origin"] for r in control_rows)), "checks": audit,
        "selected_and_control_checks": len(audit), "original_inputs_unchanged": True,
        "first_attempt_failures": 4, "extended_budget_successes": 4,
        "scope": "Hashes, arithmetic, supplied graph/work/Pipe/precedence/COPY checker; not a second bandwidth simulator or D4",
        "source_selection_sha256": digest(out / "selection.json"), "paired_results_sha256": digest(out / "paired_results.json")}
    with (out / "verification.json").open("x", encoding="utf-8") as stream:
        json.dump(verification, stream, indent=2)
    print(json.dumps({"checks": len(audit), "selected_cells": len(runs), "same_plan_pairs": 500,
                      "q3_summary": q3_summary}), flush=True)


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve())
