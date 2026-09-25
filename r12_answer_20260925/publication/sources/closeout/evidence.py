# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Read-only evidence checks for R12 closeout. Uses the supplied stdlib environment."""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Sequence


class AuditError(RuntimeError):
    """Evidence violates the declared closeout contract."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AuditError(message)


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def ratio_mean(pairs: Sequence[tuple[int, int]], expected: int = 100) -> float:
    require(len(pairs) == expected, f"Expected {expected} pairs, got {len(pairs)}")
    require(all(a > 0 and b > 0 for a, b in pairs), "Non-positive Makespan")
    return mean(a / b for a, b in pairs)


@dataclass(frozen=True, slots=True)
class Identity:
    case: str
    cores: int
    graph_sha256: str
    config_sha256: str
    official_code_sha256: str
    plan_sha256: str


@dataclass(frozen=True, slots=True)
class Score:
    raw: str
    raw_sha256: str
    makespan: int
    added_copy_bytes: int
    partition_added_copy_bytes: int
    spill_added_copy_bytes: int
    hit_bytes: int | None
    miss_bytes: int | None
    hit_rate: float | None


def read_score(path: Path, scene: str, cores: int) -> Score:
    data = json.loads(path.read_bytes())
    require(data["num_cores"] == cores, f"Wrong core count: {path}")
    require(data["bandwidth_bytes_per_cycle"] == 60, f"Wrong DDR bandwidth: {path}")
    require(data["makespan"] > 0, f"Invalid Makespan: {path}")
    movement = data["data_movement_bytes"]
    added = movement["added_copy_bytes"]
    require(movement["scheduled_copy_bytes"] - movement["original_graph_copy_bytes"] == added,
            f"COPY subtraction mismatch: {path}")
    require(movement["partition_added_copy_bytes"] + movement["spill_added_copy_bytes"] == added,
            f"COPY decomposition mismatch: {path}")
    hit = miss = rate = None
    if scene == "L2":
        require(data.get("problem") == 3 and data.get("cache_mode") == "read_only",
                f"Not a read-only L2 result: {path}")
        require(data["cache_capacity_bytes"] == 1048576 and
                data["cache_bandwidth_bytes_per_cycle"] == 250, f"Wrong L2 config: {path}")
        stats = data["cache_stats"]
        hit, miss, rate = stats["hit_bytes"], stats["miss_bytes"], stats["hit_rate"]
        expected_rate = hit / (hit + miss) if hit + miss else 0.0
        require(math.isclose(rate, expected_rate, rel_tol=1e-12, abs_tol=1e-12),
                f"Byte-weighted hit rate mismatch: {path}")
    else:
        require(data["scene"] == scene and "cache_stats" not in data,
                f"Wrong evaluator scene: {path}")
    return Score(str(path), digest(path), data["makespan"], added,
                 movement["partition_added_copy_bytes"], movement["spill_added_copy_bytes"],
                 hit, miss, rate)


def cached_l2(path: Path, identity: Identity) -> Score | None:
    """Only accept an exact plan/input/evaluator match with a verified raw digest."""
    meta = json.loads(path.read_bytes())
    if not isinstance(meta, dict):
        return None
    fields = {
        "status": "ok", "mode": "L2", "case": identity.case,
        "graph_sha256": identity.graph_sha256, "config_sha256": identity.config_sha256,
        "official_code_sha256": identity.official_code_sha256,
        "plan_sha256": identity.plan_sha256,
    }
    if any(meta.get(key) != value for key, value in fields.items()):
        return None
    raw = path.parent / meta["official_result_file"]
    require(raw.is_file() and digest(raw) == meta["official_result_sha256"],
            f"Stale cached raw: {path}")
    score = read_score(raw, "L2", identity.cores)
    require(meta.get("makespan", score.makespan) == score.makespan, f"Stale cached metric: {path}")
    return score


@dataclass(frozen=True, slots=True)
class FrozenRun:
    case: str
    cores: int
    scene: str
    report: str
    report_sha256: str
    driver: str
    driver_sha256: str
    protocol: str
    protocol_sha256: str
    plan: str
    identity: Identity
    score: Score
    budget_seconds: float
    wall_seconds: float
    source_fingerprint: str


def load_run(folder: Path) -> FrozenRun:
    report, driver_path, protocol = folder / "report.json", folder / "driver.json", folder.parent / "protocol.json"
    r = json.loads(report.read_bytes())
    driver = json.loads(driver_path.read_bytes())
    require(r["status"] == driver["status"] == "ok", f"Unsuccessful selected run: {folder}")
    require(driver["process"]["returncode"] == 0, f"Driver process failed: {folder}")
    require(driver["signature"]["protocol_sha256"] == digest(protocol), f"Stale protocol: {folder}")
    plan, raw = folder / "selected_plan.json", folder / r["selected"]["raw"]
    require(digest(plan) == r["selected_plan_sha256"] == driver["plan_sha256"], f"Plan changed: {folder}")
    require(digest(raw) == r["selected_raw_sha256"] == driver["raw_sha256"], f"Raw changed: {folder}")
    parsed_plan = json.loads(plan.read_bytes())
    require(set(parsed_plan) == {"node_to_subgraph", "core_schedules"}, f"Unexpected output fields: {folder}")
    require(len(parsed_plan["core_schedules"]) == r["cores"], f"Plan core count mismatch: {folder}")
    score = read_score(raw, r["scene"], r["cores"])
    require(score.makespan == r["selected"]["makespan"] == driver["makespan"], f"Metric mismatch: {folder}")
    identity = Identity(r["case"], r["cores"], r["graph_sha256"], r["config_sha256"],
                        r["official_source_sha256"], r["selected_plan_sha256"])
    source_fp = hashlib.sha256(json.dumps(r["source_files"], sort_keys=True).encode()).hexdigest()
    return FrozenRun(r["case"], r["cores"], r["scene"], str(report), digest(report),
                     str(driver_path), digest(driver_path), str(protocol), digest(protocol),
                     str(plan), identity, score, r["budget_seconds"], r["wall_seconds"], source_fp)
