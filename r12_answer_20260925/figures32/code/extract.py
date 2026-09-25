# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Existing Python: extract.py. Read frozen files, never solve or score.

AI-assisted: OpenCode/Sisyphus, OpenAI; public model release date unverified.
"""
import csv
import hashlib
import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from statistics import median

from specs import SPECS


def sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def native(posix_path: str) -> Path:
    return Path("//wsl.localhost/Ubuntu-24.04") / posix_path.lstrip("/")


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    project = root.parent
    raw_root = project.parents[1] / "data/raw/official"
    source = project / "publication/sources/closeout/results"
    manifest = json.loads((project / "SOURCE_MANIFEST.json").read_bytes())
    bindings = {**manifest["protected"], **manifest["inputs"]}
    for name, expected in bindings.items():
        assert sha(Path(name)) == expected, name
    for path in (project / "publication/solutions").glob("*.md"):
        bindings[str(path)] = sha(path)
    frozen = json.loads((source / "selection.json").read_bytes())
    with (source / "selected_per_case.csv").open(encoding="utf-8-sig", newline="") as stream:
        selected = list(csv.DictReader(stream))
    with (source / "q3_paired_per_case.csv").open(encoding="utf-8-sig", newline="") as stream:
        pair_rows = list(csv.DictReader(stream))
    with (project / "publication/sources/C3_official_cells.csv").open(encoding="utf-8-sig", newline="") as stream:
        old = {(r["case_id"], int(r["k"]), r["problem"]): r for r in csv.DictReader(stream)}
    assert len(selected) == 1400 and len(pair_rows) == 500
    result = {"selected": [], "pairs": [], "graphs": [], "plansA": [], "stages": [], "timelineA": [], "timelineB": [], "timelineL2": [], "cache": []}
    runs = {(r["case"], r["cores"], r["scene"]): r for r in frozen["runs"]}
    for r in selected:
        case, k, scene = r["case"], int(r["cores"]), r["scene"]
        before = old[(case, k, scene)]
        t, ref, c3 = int(r["makespan"]), int(r["fixed_singlecore"]), int(before["makespan_cycles"])
        assert ref == int(old[(case, 1, "REF")]["makespan_cycles"])
        result["selected"].append({"case": case, "k": k, "scene": scene, "T": t, "REF": ref,
            "copy": int(r["added_copy_bytes"]), "partition": int(r["partition_added_copy_bytes"]), "spill": int(r["spill_added_copy_bytes"]),
            "wall": float(r["wall_seconds"]), "budget": float(r["budget_seconds"]), "C3_T": c3,
            "C3_copy": int(before["data_movement_bytes"]), "speedup": ref/t, "C3_speedup": ref/c3,
            "versus_C3": c3/t, "reduction_pct": 100*(1-t/c3)})
    for r in pair_rows:
        b, fixed, best = int(r["B_makespan"]), int(r["L2_same_B_plan_makespan"]), int(r["L2_selected_makespan"])
        result["pairs"].append({"case": r["case"], "k": int(r["cores"]), "B": b, "L2_fixed": fixed, "L2_best": best,
            "REF": int(r["fixed_singlecore"]), "hardware": b/fixed, "selected": b/best, "reselection": fixed/best,
            "hit": float(r["L2_same_plan_byte_hit_rate"]), "different": r["B_plan_sha256"] != r["L2_selected_plan_sha256"]})
    for case in sorted(frozen["baseline"]):
        graph_file = raw_root / "data" / f"{case}.json"
        expected = runs[(case, 2, "A")]["identity"]["graph_sha256"]
        assert sha(graph_file) == expected, graph_file
        bindings[str(graph_file)] = expected
        graph = json.loads(graph_file.read_bytes())
        ops = {str(op["id"]): op for op in graph["ops"] if op["op"] not in {"COPY_IN", "COPY_OUT"}}
        m = sum(max(1, op["cycles"]) for op in ops.values() if op["pipe"] == "PIPE_M")
        v = sum(max(1, op["cycles"]) for op in ops.values() if op["pipe"] == "PIPE_V")
        g = {"case": case, "noncopy_ops": len(ops), "tensors": len(graph["tensors"]), "edges": len(graph["edges"]), "M_work": m, "V_work": v}
        for pos, capacity in (("L1", 524288), ("UB", 131072)):
            sizes = [t["size"] for t in graph["tensors"] if t["pos"] == pos]
            g[f"{pos}_max_ratio"] = max(sizes, default=0) / capacity
        result["graphs"].append(g)
        for k in range(2, 6):
            run = runs[(case, k, "A")]
            path = native(run["plan"])
            expected = run["identity"]["plan_sha256"]
            assert sha(path) == expected, path
            bindings[str(path)] = expected
            plan = json.loads(path.read_bytes())
            groups = Counter(plan["node_to_subgraph"].values())
            core_of = {sg: core for core, queue in enumerate(plan["core_schedules"]) for sg in queue}
            load = [0] * k
            for op_id, sg in plan["node_to_subgraph"].items():
                load[core_of[sg]] += max(1, ops[op_id]["cycles"])
            assert set(plan["node_to_subgraph"]) == set(ops) and sum(load) == m+v
            result["plansA"].append({"case": case, "k": k, "tasks": len(groups), "median_ops": median(groups.values()),
                "max_ops": max(groups.values()), "imbalance": k*max(load)/sum(load), "active_cores": sum(x>0 for x in load)})
        run = runs[(case, 5, "B")]
        path = native(run["report"])
        assert sha(path) == run["report_sha256"]
        bindings[str(path)] = run["report_sha256"]
        report = json.loads(path.read_bytes())
        stages = [report[key]["makespan"] for key in ("control", "indexed_selected", "selected")]
        assert stages[0] >= stages[1] >= stages[2] == run["score"]["makespan"]
        result["stages"].append({"case": case, "REF": frozen["baseline"][case], "control": stages[0], "indexed": stages[1], "full": stages[2]})
    chosen = [("timelineA", "case_087", runs[("case_087",5,"A")]["score"]),
              ("timelineB", "case_073", runs[("case_073",5,"B")]["score"])]
    controls = json.loads((source / "paired_results.json").read_bytes())
    control = next(p for p in controls["pairs"] if p["identity"]["case"] == "case_073" and p["identity"]["cores"] == 5)
    chosen.append(("timelineL2", "case_073", control["score"]))
    for key, case, score in chosen:
        path = native(score["raw"])
        assert sha(path) == score["raw_sha256"], path
        bindings[str(path)] = score["raw_sha256"]
        raw = json.loads(path.read_bytes())
        assert raw["makespan"] == score["makespan"]
        for core in raw["per_core_timeline"]:
            for op in core["ops"]:
                assert 0 <= op["start"] <= op["end"] <= raw["makespan"]
                result[key].append({"case": case, "core": core["core_id"], "pipe": op["pipe"], "op_id": op["op_id"],
                    "op": op["op"], "start": op["start"], "end": op["end"], "T": raw["makespan"]})
        if key == "timelineL2":
            hit = miss = used = 0
            for i, event in enumerate(raw["cache_events"]):
                kind = event["event"]
                if kind == "hit": hit += event["size_bytes"]
                if kind == "miss": miss += event["size_bytes"]
                if kind == "insert": used = event["used_bytes"]
                assert 0 <= used <= 1048576
                result["cache"].append({"index": i, "time": event["time"], "event": kind, "bytes": event["size_bytes"],
                    "used": used, "hit_bytes": hit, "miss_bytes": miss, "cumulative_hit": hit/(hit+miss) if hit+miss else 0,
                    "T": raw["makespan"]})
            assert hit == raw["cache_stats"]["hit_bytes"] and miss == raw["cache_stats"]["miss_bytes"]
    for name, expected in bindings.items():
        assert sha(Path(name)) == expected, name
    for name, content in (("dataset.json", result), ("INPUTS.json", bindings), ("figure_requirements.json", [asdict(s) for s in SPECS])):
        with (root / name).open("x", encoding="utf-8") as stream:
            json.dump(content, stream, ensure_ascii=False, indent=2)
    print(json.dumps({"status": "EXTRACTED", "counts": {k:len(v) for k,v in result.items()}, "bound_inputs": len(bindings)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
