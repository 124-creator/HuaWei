# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Run with the existing WSL Python: closeout.py prepare|evaluate ROOT OUT.

Only the eight missing fixed-plan L2 evaluations may be launched. No solver,
algorithm edits, score-driven selection, or historical file replacement.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from evidence import FrozenRun, cached_l2, digest, load_run, read_score, require


def freeze_runs(root: Path, out: Path) -> list[FrozenRun]:
    work = root / "work"
    folders = [work / "reproduce_B5_r12"]
    folders += [work / f"par{i}_{s}" for i in range(1, 7) for s in ("A", "B", "L2")]
    folders += [work / f"one{i}_B1L21" for i in range(1, 7)]
    chosen: dict[tuple[str, int, str], FrozenRun] = {}
    failures = []
    for folder in folders:
        for rp in sorted(folder.glob("case_*/report.json")):
            report = json.loads(rp.read_bytes())
            key = (report["scene"], report["cores"], report["case"])
            if report["status"] != "ok":
                failures.append({"key": key, "report": str(rp), "sha256": digest(rp),
                                 "status": report["status"], "budget": report["budget_seconds"]})
                continue
            require(key not in chosen, f"Duplicate primary run: {key}")
            chosen[key] = load_run(rp.parent)
    allowed = {("A", k, "case_087") for k in range(2, 6)}
    require({tuple(r["key"]) for r in failures} == allowed, "Unexpected primary failures")
    for name in ("retry087_A23", "retry087b_A45"):
        for rp in sorted((work / name).glob("case_*/report.json")):
            run = load_run(rp.parent)
            key = (run.scene, run.cores, run.case)
            require(key in allowed and key not in chosen, f"Unexpected retry: {key}")
            require(run.budget_seconds == 1800, f"Wrong retry budget: {rp}")
            chosen[key] = run
    expected = {(s, k, f"case_{i:03d}") for i in range(1, 101) for s in ("A", "B", "L2")
                for k in (range(2, 6) if s == "A" else range(1, 6))}
    require(set(chosen) == expected, "Selected grid is incomplete or contains extra keys")
    require(len({r.source_fingerprint for r in chosen.values()}) == 1, "Mixed source versions")
    with (out / "original_failures.json").open("x", encoding="utf-8") as stream:
        json.dump(failures, stream, indent=2)
    return [chosen[k] for k in sorted(chosen)]


def prepare(root: Path, out: Path) -> None:
    require(out.parent.is_dir() and not out.exists(), "Use a new output directory under an existing parent")
    out.mkdir()
    runs = freeze_runs(root, out)
    source_files = json.loads(Path(runs[0].report).read_bytes())["source_files"]
    inputs = {str(root / p): h for p, h in source_files.items()}
    inputs[str(root / "official/data/config.txt")] = runs[0].identity.config_sha256
    for run in runs:
        inputs[str(root / "official/data" / f"{run.case}.json")] = run.identity.graph_sha256
        inputs[run.report] = run.report_sha256
        inputs[run.driver] = run.driver_sha256
        inputs[run.protocol] = run.protocol_sha256
        inputs[run.plan] = run.identity.plan_sha256
        inputs[run.score.raw] = run.score.raw_sha256
    require(all(digest(Path(p)) == h for p, h in inputs.items()), "Frozen input hash mismatch")
    baseline_path = root / "stage4_reports/baselines.json"
    baselines = json.loads(baseline_path.read_bytes())
    local_csv = Path("/mnt/e/HWCupA2026/derived/formal_sources/official_1500_cells.csv")
    with local_csv.open(encoding="utf-8-sig", newline="") as stream:
        ref = {r["case_id"]: int(r["makespan_cycles"]) for r in csv.DictReader(stream)
               if r["problem"] == "REF" and r["status"] == "SUCCESS"}
    require(len(ref) == 100 and len(baselines) == 100, "Baseline coverage differs")
    require(all(ref[r["case"]] == r["makespan"] for r in baselines), "Baseline values differ")
    inputs[str(baseline_path)], inputs[str(local_csv)] = digest(baseline_path), digest(local_csv)
    config_hash = runs[0].identity.config_sha256
    code_hash = hashlib.sha256(json.dumps({p.name: digest(p) for p in sorted(
        (root / "official/code").glob("*.py"))}, sort_keys=True).encode()).hexdigest()
    require(all(r.identity.official_code_sha256 == code_hash for r in runs), "Official code differs")
    with (out / "selection.json").open("x", encoding="utf-8") as stream:
        json.dump({"policy": "Explicit primary dirs; replace only four failed case_087 A runs; no score selection",
                   "created_utc": datetime.now(timezone.utc).isoformat(), "root": str(root),
                   "baseline": ref, "config_sha256": config_hash, "official_code_sha256": code_hash,
                   "source_files": source_files, "inputs": inputs, "runs": [asdict(r) for r in runs]}, stream, indent=2)
    print(json.dumps({"frozen_runs": len(runs), "budget_counts": dict(Counter(
        r.budget_seconds for r in runs)), "input_bindings": len(inputs)}), flush=True)
    by_key = {(r.case, r.cores, r.scene): r for r in runs}
    pairs = []
    for case in sorted(ref):
        for cores in range(1, 6):
            b, l = by_key[(case, cores, "B")], by_key[(case, cores, "L2")]
            score = None
            metadata = None
            origin = "new_evaluation_required"
            if b.identity.plan_sha256 == l.identity.plan_sha256:
                score, origin = l.score, "identical_final_plan"
            else:
                for path in sorted(Path(l.report).parent.rglob("*.json")):
                    if path.name.endswith(".official.json") or path.stat().st_size > 65536:
                        continue
                    candidate = cached_l2(path, b.identity)
                    if candidate is not None:
                        score, metadata, origin = candidate, path, "existing_candidate"
                        break
            pairs.append({"case": case, "cores": cores, "identity": asdict(b.identity),
                          "b_plan": b.plan, "b_raw": b.score.raw, "l2_optimized_raw": l.score.raw,
                          "origin": origin, "score": asdict(score) if score else None,
                          "metadata": str(metadata) if metadata else None,
                          "metadata_sha256": digest(metadata) if metadata else None})
    with (out / "pairs.json").open("x", encoding="utf-8") as stream:
        json.dump({"scope": "500 same-B-plan L2 controls; not solver runs", "evaluation_timeout_seconds": 600,
                   "expected_pairs": 500, "pairs": pairs}, stream, indent=2)
    print(json.dumps({"pairs": len(pairs), "origins": dict(Counter(p["origin"] for p in pairs)),
                      "new": [[p["case"], p["cores"]] for p in pairs if p["score"] is None]}), flush=True)


def evaluate(root: Path, out: Path) -> None:
    declaration = json.loads((out / "pairs.json").read_bytes())
    selected = json.loads((out / "selection.json").read_bytes())
    require(all(digest(Path(p)) == h for p, h in selected["inputs"].items()), "Source evidence changed")
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    sys.path.insert(0, str(root / "round11_src"))
    from runtime import execute

    results = []
    for pair in declaration["pairs"]:
        if pair["score"] is not None:
            results.append(pair)
            continue
        case, cores = pair["case"], pair["cores"]
        folder = out / "new_scores" / f"{case}_n{cores}_Bplan_L2"
        require(not folder.exists(), f"Output already exists; do not overwrite: {folder}")
        folder.mkdir(parents=True)
        raw = folder / "official.json"
        cmd = [sys.executable, "-B", "-S", str(root / "official/code/multicore_cut_evaluate_problem_3.py"),
               str(root / "official/data" / f"{case}.json"), pair["b_plan"], "--config",
               str(root / "official/data/config.txt"), "-o", str(raw), "--trace-output",
               str(folder / "trace.json"), "--log-output", str(folder / "official.log")]
        process = execute(cmd, declaration["evaluation_timeout_seconds"], folder / "process.log")
        with (folder / "process.json").open("x", encoding="utf-8") as stream:
            json.dump({"identity": pair["identity"], "process": process,
                       "purpose": "Evaluate frozen B plan under L2; no optimization"}, stream, indent=2)
        require(process["status"] == "ok" and process["returncode"] == 0, f"Evaluation failed: {folder}")
        require(digest(Path(pair["b_plan"])) == pair["identity"]["plan_sha256"], "B plan changed")
        score = read_score(raw, "L2", cores)
        results.append({**pair, "origin": "new_official_evaluation", "score": asdict(score),
                        "metadata": str(folder / "process.json"),
                        "metadata_sha256": digest(folder / "process.json")})
        print(json.dumps({"case": case, "cores": cores, "makespan": score.makespan,
                          "wall_seconds": process["wall_seconds"], "status": "ok"}), flush=True)
    require(len(results) == 500, "Pair coverage is incomplete")
    with (out / "paired_results.json").open("x", encoding="utf-8") as stream:
        json.dump({"pairs_declaration_sha256": digest(out / "pairs.json"), "pairs": results}, stream, indent=2)
    print("PAIRED_RESULTS_COMPLETE: 500", flush=True)


if __name__ == "__main__":
    action, root_arg, out_arg = sys.argv[1:]
    actions = {"prepare": prepare, "evaluate": evaluate}
    require(action in actions, "Expected prepare or evaluate")
    actions[action](Path(root_arg).resolve(), Path(out_arg).resolve())
