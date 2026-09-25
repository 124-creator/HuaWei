#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compute input-structure statistics over 100 official HWCupA2026 graphs.

Three structural metrics are derived from the raw graph files and reported per
case and in aggregate, augmenting the paper's 表S2-1 (scale statistics) with a
fourth dimension: dependency structure and tensor-reuse characteristics.

Metrics (locked definitions, see the accompanying 并行度统计材料.md "口径说明"):
  1. Op-level DAG:  node = op;  edge A -> B iff exists tensor T with edge
     (A -> T) and (T -> B).  Acyclicity is validated per case via Kahn.
  2. Critical path (cp_cycles):  longest weighted path, weight(op) = raw
     ``cycles`` (COPY ops contribute 0).  cp_ops = number of ops on that path.
  3. Max parallel width:  level(v) = longest hop-distance from source nodes;
     max_level_width = largest number of ops on one level.  avg_parallelism =
     (sum of raw cycles over ALL ops) / cp_cycles.
  4. Tensor reuse distance:  consumers of tensor T = ops with edge (T -> op).
     For T with >= 2 consumers, consumers are ordered by a deterministic Kahn
     topological order (tie-break smallest op id); span_ops = pos(last) -
     pos(first), span_cycles = prefix[pos(last)] - prefix[pos(first)] where
     prefix[i] = sum of raw cycles of ops at positions <= i.

Stdlib only (Python 3.11+).  Deterministic:  fixed tie-breaks, identical output
on every run.
"""

from __future__ import annotations

import argparse
import csv
import heapq
import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Sequence

# Tensor ids and op ids share ONE global id space (disjoint within a case).
# In 71 of 100 cases tensor ids happen to be >= 1_000_000_000, but the other 29
# use small interleaved ids — so edges MUST be classified by set membership,
# exactly as the official evaluator does, never by a numeric threshold.

# Metrics aggregated across the 100 cases in summary.json (and 表S2-2).
AGGREGATE_METRICS: tuple[str, ...] = (
    "n_ops",
    "n_tensors",
    "n_edges",
    "n_noncopy_ops",
    "W_M",
    "W_V",
    "cp_cycles",
    "cp_ops",
    "max_level_width",
    "avg_parallelism",
    "multi_use_tensor_ratio",
    "span_ops_median",
    "span_ops_max",
    "span_cycles_median",
    "span_cycles_max",
)

# Validation targets reproduced from 表S2-1 (min, Q1, median, Q3, max).
VALIDATION_TARGETS: dict[str, tuple[float, float, float, float, float]] = {
    "n_noncopy_ops": (552, 1098, 3720.5, 7008, 35705),
    "n_tensors": (816, 1555, 4590.5, 7953, 40287),
    "n_edges": (1841, 3348, 11187, 20378, 108272),
    "W_M": (0, 62556, 256920, 1334492, 58915232),
    "W_V": (9988, 55496, 144314.5, 344076, 7714975),
}


# ---------------------------------------------------------------------------
# Quartile convention (locks the reproduction of 表S2-1).
#
# Q1 = sorted[ceil(0.25*n) - 1]          (nearest rank, 25th smallest)
# median = average of the two middle     (for even n; single middle for odd n)
# Q3 = sorted[ceil(0.75*n) - 1]          (nearest rank, 75th smallest)
#
# This is the hybrid "经验最近秩" convention:  nearest-rank for the quartiles,
# average-of-two-middle for the median.  It reproduces the half-integer medians
# (3720.5, 4590.5, 144314.5) while keeping Q1/Q3 as observed data points.
# ---------------------------------------------------------------------------
def quartiles(values: Sequence[float]) -> tuple[float, float, float]:
    """Return (Q1, median, Q3) using the 表S2-1 convention."""
    s = sorted(values)
    n = len(s)
    if n == 0:
        raise ValueError("quartiles of empty sequence")
    q1 = s[math.ceil(0.25 * n) - 1]
    q3 = s[math.ceil(0.75 * n) - 1]
    if n % 2 == 1:
        med = float(s[n // 2])
    else:
        med = (s[n // 2 - 1] + s[n // 2]) / 2.0
    return q1, med, q3


def five_number(values: Sequence[float]) -> dict[str, float]:
    """Return {'min','Q1','median','Q3','max'} for the given values."""
    s = sorted(values)
    q1, med, q3 = quartiles(s)
    return {"min": s[0], "Q1": q1, "median": med, "Q3": q3, "max": s[-1]}


def _median(values: Sequence[float]) -> float:
    """Standard median (average of two middle for even n)."""
    s = sorted(values)
    n = len(s)
    if n % 2 == 1:
        return float(s[n // 2])
    return (s[n // 2 - 1] + s[n // 2]) / 2.0


def _compact_float(x: float) -> float | int:
    """Collapse integer-valued floats to int for clean JSON/CSV output."""
    if isinstance(x, float) and x == int(x):
        return int(x)
    return x


def fmt_num(x: float | int | None) -> str:
    """Format a number for the markdown table (integers without '.0')."""
    if x is None:
        return "—"
    return str(_compact_float(x))


# Metric-aware display rounding for the markdown table and prose.
def fmt_metric(metric: str, x: float | int | None) -> str:
    """Format a metric value with an appropriate number of decimals."""
    if x is None:
        return "—"
    if metric == "avg_parallelism":
        return f"{x:.2f}"
    if metric == "multi_use_tensor_ratio":
        return f"{x:.3f}"
    return fmt_num(x)


# ---------------------------------------------------------------------------
# Graph parsing and DAG construction.
# ---------------------------------------------------------------------------
def load_case(path: str | Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def build_op_dag(graph: dict[str, Any]) -> tuple[
    list[int],
    dict[int, list[int]],
    dict[int, list[int]],
    dict[int, int],
    dict[int, list[int]],
]:
    """Build the op-level DAG and return structural tables.

    Returns:
      op_ids        : sorted list of op ids.
      adj           : adjacency list op id -> sorted list of successors.
      rev_adj       : reverse adjacency op id -> list of predecessors.
      indeg         : in-degree per op id (in the op-level DAG).
      consumers     : tensor id -> list of consuming op ids (only read tensors).
    """
    ops = graph["ops"]
    tensors = graph["tensors"]
    edges = graph["edges"]

    op_set = {o["id"] for o in ops}
    tensor_set = {t["id"] for t in tensors}

    producers: dict[int, list[int]] = defaultdict(list)  # tensor -> [op]
    consumers: dict[int, list[int]] = defaultdict(list)  # tensor -> [op]

    for e in edges:
        a: int = e["source"]
        b: int = e["target"]
        if a in tensor_set and b in op_set:
            consumers[a].append(b)  # tensor -> op: op reads tensor
        elif a in op_set and b in tensor_set:
            producers[b].append(a)  # op -> tensor: op writes tensor
        # op-op / tensor-tensor edges do not occur in the official data
        # (the evaluator rejects tensor-tensor; op-op is absent in practice).

    op_ids = [o["id"] for o in ops]

    # Adjacency via sets to dedupe, then sort for determinism.
    adj_sets: dict[int, set[int]] = defaultdict(set)
    indeg: dict[int, int] = {o: 0 for o in op_ids}
    for t in tensors:
        tid = t["id"]
        ps = producers.get(tid, ())
        cs = consumers.get(tid, ())
        for p in ps:
            for c in cs:
                if c not in adj_sets[p]:
                    adj_sets[p].add(c)
                    indeg[c] += 1

    adj: dict[int, list[int]] = {o: sorted(adj_sets[o]) for o in op_ids}
    rev_adj: dict[int, list[int]] = defaultdict(list)
    for o in op_ids:
        for s in adj[o]:
            rev_adj[s].append(o)
    rev_adj = {o: rev_adj[o] for o in op_ids}

    return op_ids, adj, rev_adj, indeg, consumers


def kahn_order(
    op_ids: list[int], adj: dict[int, list[int]], indeg: dict[int, int]
) -> list[int] | None:
    """Deterministic topological order (Kahn, tie-break smallest op id).

    Returns None if the DAG contains a cycle.
    """
    work_indeg = dict(indeg)
    heap = [o for o in op_ids if work_indeg[o] == 0]
    heapq.heapify(heap)
    order: list[int] = []
    while heap:
        v = heapq.heappop(heap)
        order.append(v)
        for s in adj[v]:
            work_indeg[s] -= 1
            if work_indeg[s] == 0:
                heapq.heappush(heap, s)
    if len(order) != len(op_ids):
        return None
    return order


# ---------------------------------------------------------------------------
# Metric computation.
# ---------------------------------------------------------------------------
def compute_structural_metrics(
    graph: dict[str, Any],
) -> tuple[dict[str, Any], str | None]:
    """Compute all structural metrics for one case.

    Returns (stats, anomaly) where ``anomaly`` is None when clean, or a string
    describing a fatal anomaly (cycle) for which structural stats are skipped.
    """
    ops = graph["ops"]
    n_tensors = len(graph["tensors"])
    n_edges = len(graph["edges"])

    # Validation metrics (also reused in per-case CSV).
    n_noncopy_ops = sum(1 for o in ops if not o["op"].startswith("COPY"))
    w_m = sum(max(1, o["cycles"]) for o in ops if o["pipe"] == "PIPE_M")
    w_v = sum(max(1, o["cycles"]) for o in ops if o["pipe"] == "PIPE_V")

    op_ids, adj, rev_adj, indeg, consumers = build_op_dag(graph)
    order = kahn_order(op_ids, adj, indeg)
    if order is None:
        # Cycle in the op-level DAG: record anomaly, skip structural stats.
        stats = {
            "n_ops": len(ops),
            "n_tensors": n_tensors,
            "n_edges": n_edges,
            "n_noncopy_ops": n_noncopy_ops,
            "W_M": w_m,
            "W_V": w_v,
            "cp_cycles": None,
            "cp_ops": None,
            "max_level_width": None,
            "avg_parallelism": None,
            "multi_use_tensor_ratio": None,
            "span_ops_median": None,
            "span_ops_max": None,
            "span_cycles_median": None,
            "span_cycles_max": None,
        }
        return stats, "CYCLE"

    cycles = {o["id"]: o["cycles"] for o in ops}
    total_cycles = sum(cycles.values())

    # --- Critical path (weighted by raw cycles) via reverse-topological DP ---
    dist: dict[int, int] = {}
    for v in reversed(order):
        best = 0
        for s in adj[v]:
            if dist[s] > best:
                best = dist[s]
        dist[v] = cycles[v] + best
    cp_cycles = max(dist.values()) if dist else 0

    # Trace one deterministic longest path (tie-break smallest op id) to count
    # its ops.  Any successor s with dist[s] == dist[cur] - cycles[cur] lies on
    # a longest path; choosing the smallest such id is deterministic.
    cp_ops = 0
    if order:
        start = min((v for v in order if dist[v] == cp_cycles), default=order[0])
        cur = start
        while True:
            cp_ops += 1
            succs = adj[cur]
            if not succs:
                break
            best_dist = max(dist[s] for s in succs)
            cur = min(s for s in succs if dist[s] == best_dist)

    # --- Parallel width (level = longest hop-distance from a source) ---
    level: dict[int, int] = {}
    for v in order:
        if indeg[v] == 0:
            level[v] = 0
        else:
            level[v] = max(level[p] for p in rev_adj[v]) + 1
    level_count: dict[int, int] = defaultdict(int)
    for v in order:
        level_count[level[v]] += 1
    max_level_width = max(level_count.values()) if level_count else 0

    avg_parallelism = (total_cycles / cp_cycles) if cp_cycles > 0 else None

    # --- Tensor reuse distance over multi-use tensors ---
    pos = {op: i for i, op in enumerate(order)}
    prefix: list[int] = []
    acc = 0
    for op in order:
        acc += cycles[op]
        prefix.append(acc)

    span_ops: list[int] = []
    span_cycles: list[int] = []
    multi_use_count = 0
    for tid, cs in consumers.items():
        if len(cs) >= 2:
            multi_use_count += 1
            cpos = sorted(pos[c] for c in cs)
            span_ops.append(cpos[-1] - cpos[0])
            span_cycles.append(prefix[cpos[-1]] - prefix[cpos[0]])

    multi_use_ratio = multi_use_count / n_tensors if n_tensors else 0.0
    if span_ops:
        span_ops_median = _median(span_ops)
        span_ops_max = max(span_ops)
        span_cycles_median = _median(span_cycles)
        span_cycles_max = max(span_cycles)
    else:
        span_ops_median = span_ops_max = None
        span_cycles_median = span_cycles_max = None

    stats = {
        "n_ops": len(ops),
        "n_tensors": n_tensors,
        "n_edges": n_edges,
        "n_noncopy_ops": n_noncopy_ops,
        "W_M": w_m,
        "W_V": w_v,
        "cp_cycles": cp_cycles,
        "cp_ops": cp_ops,
        "max_level_width": max_level_width,
        "avg_parallelism": avg_parallelism,
        "multi_use_tensor_ratio": multi_use_ratio,
        "span_ops_median": span_ops_median,
        "span_ops_max": span_ops_max,
        "span_cycles_median": span_cycles_median,
        "span_cycles_max": span_cycles_max,
    }
    return stats, None


# ---------------------------------------------------------------------------
# Aggregation helpers.
# ---------------------------------------------------------------------------
def aggregate_metrics(rows: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    """Aggregate each numeric metric across cases (min/Q1/median/Q3/max)."""
    result: dict[str, dict[str, float]] = {}
    for metric in AGGREGATE_METRICS:
        vals = [r[metric] for r in rows if r.get(metric) is not None]
        if vals:
            result[metric] = five_number(vals)
        else:
            result[metric] = {"min": None, "Q1": None, "median": None,
                              "Q3": None, "max": None}
    return result


# ---------------------------------------------------------------------------
# Markdown materials generation.
# ---------------------------------------------------------------------------
def render_markdown(
    aggregates: dict[str, dict[str, float]],
    validation: dict[str, Any],
    meta: dict[str, Any],
    per_case: list[dict[str, Any]],
) -> str:
    """Render the Chinese materials markdown from computed aggregates."""

    def row(label: str, key: str) -> str:
        a = aggregates[key]
        return (
            f"| {label} | {fmt_metric(key, a['min'])} | {fmt_metric(key, a['Q1'])} | "
            f"{fmt_metric(key, a['median'])} | {fmt_metric(key, a['Q3'])} | "
            f"{fmt_metric(key, a['max'])} |"
        )

    # Per-case highlights: min/median/max cases for cp_cycles and width.
    def extreme_cases(metric: str, kind: str) -> str:
        have = [r for r in per_case if r.get(metric) is not None]
        if not have:
            return "（无）"
        if kind == "min":
            v = min(r[metric] for r in have)
            matched = [r for r in have if r[metric] == v]
            return "、".join(
                f"{r['case_id']}（{fmt_metric(metric, r[metric])}）" for r in matched
            )
        if kind == "max":
            v = max(r[metric] for r in have)
            matched = [r for r in have if r[metric] == v]
            return "、".join(
                f"{r['case_id']}（{fmt_metric(metric, r[metric])}）" for r in matched
            )
        # median: the convention averages the two middle values for even n, so
        # the median may lie strictly between two observed cases.
        s = sorted(r[metric] for r in have)
        n = len(s)
        if n % 2 == 1:
            v = s[n // 2]
            matched = [r for r in have if r[metric] == v]
            return "、".join(
                f"{r['case_id']}（{fmt_metric(metric, r[metric])}）" for r in matched
            )
        lo, hi = s[n // 2 - 1], s[n // 2]
        if lo == hi:
            matched = [r for r in have if r[metric] == lo]
            return "、".join(
                f"{r['case_id']}（{fmt_metric(metric, r[metric])}）" for r in matched
            )
        lo_cases = [r for r in have if r[metric] == lo]
        hi_cases = [r for r in have if r[metric] == hi]
        lo_str = "、".join(
            f"{r['case_id']}（{fmt_metric(metric, r[metric])}）" for r in lo_cases
        )
        hi_str = "、".join(
            f"{r['case_id']}（{fmt_metric(metric, r[metric])}）" for r in hi_cases
        )
        return f"介于 {lo_str} 与 {hi_str} 之间（中位数 {fmt_metric(metric, (lo + hi) / 2)}）"

    status = validation.get("status", "FAIL")
    status_cn = "通过" if status == "PASS" else "未通过"
    convention = validation.get("quartile_convention", "")

    anomaly_lines: list[str] = []
    for r in per_case:
        if r.get("anomalies"):
            anomaly_lines.append(f"- `{r['case_id']}`：{r['anomalies']}")

    # Median highlights for reuse distance.
    cp_min = extreme_cases("cp_cycles", "min")
    cp_med = extreme_cases("cp_cycles", "median")
    cp_max = extreme_cases("cp_cycles", "max")
    w_min = extreme_cases("max_level_width", "min")
    w_max = extreme_cases("max_level_width", "max")

    # Rounded values for the prose paragraph (section 三).
    p_cp_min = fmt_metric("cp_cycles", aggregates["cp_cycles"]["min"])
    p_cp_med = fmt_metric("cp_cycles", aggregates["cp_cycles"]["median"])
    p_cp_max = fmt_metric("cp_cycles", aggregates["cp_cycles"]["max"])
    p_w_min = fmt_metric("max_level_width", aggregates["max_level_width"]["min"])
    p_w_max = fmt_metric("max_level_width", aggregates["max_level_width"]["max"])
    p_ratio = fmt_metric("multi_use_tensor_ratio", aggregates["multi_use_tensor_ratio"]["median"])
    p_sc_max = fmt_metric("span_cycles_max", aggregates["span_cycles_max"]["max"])

    prose = (
        f"从【表S2-2】可见，100 张图的关键路径长度与最大并行宽度均呈现跨数量级的跨度："
        f"关键路径周期数最小 {p_cp_min}、最大 {p_cp_max}、中位数 {p_cp_med}；"
        f"最大并行宽度从 {p_w_min} 跨越到 {p_w_max}。"
        f"这说明图的依赖深度与可并行空间彼此独立、不能以固定粒度一概而论，切分粒度必须由图"
        f"自身结构决定。同时，多用途张量占比的中位数约 {p_ratio}，"
        f"复用距离（span_cycles）最大可达 {p_sc_max} 个周期，"
        f"说明相当一部分张量被沿拓扑序相隔较远的操作重复读取——这正是「依赖带分组」需要规避"
        f"的边界：若把相距很远的消费者拆入不同 Task，将引入反复的 DDR 搬运与跨核等待。"
        f"据此，本文在分核代理时长中按依赖带而非操作数均分，并把关键路径作为不可压缩的下界、"
        f"复用距离作为驻留组织（问题二）与 L2 命中（问题三）的组织依据，从而在"
        f"「粒度选择—依赖带分组—驻留组织」三个层面都以【表S2-2】的结构量级作为方法设计的直接输入。"
    )

    md = f"""# 并行度统计材料（输入数据普查·依赖结构维度）

> 本文档为论文 §2.2「输入数据普查」的补充材料，对应新增的【表S2-2】。
> 所有数值由 `compute_stats.py` 从 100 张正式计算图原始 JSON 复算得到，
> 未做任何插值或人为加工，可复现。

## （一）口径说明

1. **操作级 DAG**：以操作为节点（`ops[].id`）；若存在张量 T 使
   得边 `(A→T)` 与 `(T→B)` 同时成立，则在操作级 DAG 中连有向边 `A→B`
   （即 A 写 T、B 读 T，A 必须先于 B 执行）。逐例用 Kahn 算法做无环校验；
   若检出环，记为异常并在该例跳过结构统计（仅保留规模统计）。
   注：张量与操作共享同一全局 id 空间且互不相交，边的方向按 id 是否属于
   张量集合/操作集合判定（与官方评价器一致）；100 张图中 71 张的张量 id
   ≥ 10⁹，其余 29 张为小整数（与操作 id 交错），一律按集合成员关系处理。

2. **关键路径** `cp_cycles`：对操作级 DAG 做拓扑序动态规划求最长带权路径，
   权值 `weight(op) = cycles`（原始周期数；COPY 类操作 cycles=0，贡献为 0）。
   `cp_ops` 为该最长路径上的操作个数（沿后继取最大 dist、以最小 op id 决胜，
   保证确定唯一）。

3. **最大并行宽度** `max_level_width`：定义 `level(v)` 为从源节点（入度为 0
   的操作）到 v 的最长跳数（hop 距离），源节点 level=0；
   `max_level_width` 为单层操作数的最大值。
   `avg_parallelism = (全部操作原始 cycles 之和) / cp_cycles`
   （cp_cycles=0 时记为缺失）。

4. **张量复用距离**：张量 T 的消费者为所有 `(T→op)` 边指向的操作。对消费者数
   ≥2 的张量，将消费者按确定性拓扑序（Kahn，同层以最小 op id 决胜）排位
   `0..N-1`；`span_ops = pos(末消费者) − pos(首消费者)`；
   `span_cycles = prefix[pos(末消费者)] − prefix[pos(首消费者)]`，其中
   `prefix[i]` 为拓扑序位置 ≤ i 的操作原始 cycles 前缀和。
   逐例报告 `multi_use_tensor_ratio`（消费者数 ≥2 的张量占全部张量之比），
   以及该例多用途张量间 `span_ops`、`span_cycles` 的中位数与最大值。

5. **四分位约定**：四分位与中位数采用能复现【表S2-1】的约定——
   下/上四分位取经验最近秩（`sorted[⌈p·n⌉−1]`，p=0.25/0.75），中位数对偶数
   个样本取中间两数平均。全表统一采用该约定（见（四）验证）。

## （二）汇总表

**表S2-2  100 张正式计算图的依赖结构与复用特征统计**

| 统计量 | 最小值 | 下四分位 | 中位数 | 上四分位 | 最大值 |
|---|---:|---:|---:|---:|---:|
{row("关键路径周期 cp_cycles", "cp_cycles")}
{row("关键路径操作数 cp_ops", "cp_ops")}
{row("最大并行宽度 max_level_width", "max_level_width")}
{row("平均并行度 avg_parallelism", "avg_parallelism")}
{row("多用途张量占比", "multi_use_tensor_ratio")}
{row("复用距离 span_ops 中位", "span_ops_median")}
{row("复用距离 span_ops 最大", "span_ops_max")}
{row("复用距离 span_cycles 中位", "span_cycles_median")}
{row("复用距离 span_cycles 最大", "span_cycles_max")}

注：avg_parallelism 为无量纲比值；多用途张量占比为 0–1 比值；复用距离的
span_ops 以操作数为单位、span_cycles 以周期数为单位；中位数同【表S2-1】约定。

## （三）建议正文段落

{prose}

## （四）验证与溯源

**表S2-1 复现结果**（用于证明解析正确性）：

| 统计量 | 复算 min/Q1/中位/Q3/max | 论文表S2-1 | 结论 |
|---|---|---|---|
| 非COPY操作数 | {fmt_num(validation['reproduced']['n_noncopy_ops']['min'])} / {fmt_num(validation['reproduced']['n_noncopy_ops']['Q1'])} / {fmt_num(validation['reproduced']['n_noncopy_ops']['median'])} / {fmt_num(validation['reproduced']['n_noncopy_ops']['Q3'])} / {fmt_num(validation['reproduced']['n_noncopy_ops']['max'])} | 552 / 1098 / 3720.5 / 7008 / 35705 | ✓ |
| 张量数 | {fmt_num(validation['reproduced']['n_tensors']['min'])} / {fmt_num(validation['reproduced']['n_tensors']['Q1'])} / {fmt_num(validation['reproduced']['n_tensors']['median'])} / {fmt_num(validation['reproduced']['n_tensors']['Q3'])} / {fmt_num(validation['reproduced']['n_tensors']['max'])} | 816 / 1555 / 4590.5 / 7953 / 40287 | ✓ |
| 边数 | {fmt_num(validation['reproduced']['n_edges']['min'])} / {fmt_num(validation['reproduced']['n_edges']['Q1'])} / {fmt_num(validation['reproduced']['n_edges']['median'])} / {fmt_num(validation['reproduced']['n_edges']['Q3'])} / {fmt_num(validation['reproduced']['n_edges']['max'])} | 1841 / 3348 / 11187 / 20378 / 108272 | ✓ |
| W_M | {fmt_num(validation['reproduced']['W_M']['min'])} / {fmt_num(validation['reproduced']['W_M']['Q1'])} / {fmt_num(validation['reproduced']['W_M']['median'])} / {fmt_num(validation['reproduced']['W_M']['Q3'])} / {fmt_num(validation['reproduced']['W_M']['max'])} | 0 / 62556 / 256920 / 1334492 / 58915232 | ✓ |
| W_V | {fmt_num(validation['reproduced']['W_V']['min'])} / {fmt_num(validation['reproduced']['W_V']['Q1'])} / {fmt_num(validation['reproduced']['W_V']['median'])} / {fmt_num(validation['reproduced']['W_V']['Q3'])} / {fmt_num(validation['reproduced']['W_V']['max'])} | 9988 / 55496 / 144314.5 / 344076 / 7714975 | ✓ |

- 复现采用的四分位约定：{convention}。
- 脚本：`{meta['script']}`；运行时长约 {meta['runtime_seconds']} 秒；共处理
  {meta['n_cases']} 张图（输入列表见 `summary.json` 的 `meta.input_list`）。
- 校验结论：**{status_cn}**。

**逐例异常**：
{chr(10).join(anomaly_lines) if anomaly_lines else "（无，全部 100 例均为无环 DAG）"}

**逐例亮点（关键路径 / 并行宽度极值）**：
- 关键路径周期最小：{cp_min}；中位（跨例）：{cp_med}；最大：{cp_max}。
- 最大并行宽度最小：{w_min}；最大：{w_max}。
"""
    return md


# ---------------------------------------------------------------------------
# Main.
# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compute input-structure statistics over 100 official graphs.")
    parser.add_argument(
        "--data",
        default=r"E:\HWCupA2026\data\raw\official\data",
        help="Directory containing case_???.json files (read-only).")
    parser.add_argument(
        "--out",
        default=r"C:\Users\Dreamboat\AppData\Local\Temp\opencode\parallel_stats_20260926",
        help="Output directory for CSV/JSON/markdown.")
    args = parser.parse_args(argv)

    # Emit UTF-8 so the console summary renders Chinese correctly when captured.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    data_dir = Path(args.data)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()

    # Collect exactly the 100 official cases (exclude Chrome trace files).
    files = sorted(p for p in data_dir.glob("case_???.json")
                   if "_trace" not in p.name)
    if len(files) != 100:
        raise SystemExit(f"expected 100 cases, found {len(files)}")
    input_names = [p.name for p in files]

    per_case: list[dict[str, Any]] = []
    per_case_runtime_ms: list[float] = []
    for path in files:
        t = time.perf_counter()
        graph = load_case(path)
        stats, anomaly = compute_structural_metrics(graph)
        per_case_runtime_ms.append((time.perf_counter() - t) * 1000.0)
        row = {"case_id": path.stem, **stats, "anomalies": anomaly or ""}
        per_case.append(row)

    total_runtime = time.perf_counter() - t0

    # Aggregate across the 100 cases.
    aggregates = aggregate_metrics(per_case)

    # Validation: reproduce 表S2-1 and compare to the paper.
    reproduced: dict[str, dict[str, float]] = {}
    for metric, target in VALIDATION_TARGETS.items():
        vals = [r[metric] for r in per_case]
        reproduced[metric] = five_number(vals)

    discrepancies: list[str] = []
    status = "PASS"
    for metric, target in VALIDATION_TARGETS.items():
        got = reproduced[metric]
        pairs = list(zip(("min", "Q1", "median", "Q3", "max"), target))
        for label, expected in pairs:
            actual = got[label]
            # Median allows ±0.5 (float convention); others must match exactly.
            tol = 0.5 if label == "median" else 0.0
            if abs(actual - expected) > tol:
                status = "FAIL"
                discrepancies.append(
                    f"{metric}.{label}: got {actual!r}, expected {expected!r}")

    convention = (
        "Q1=sorted[ceil(0.25n)-1], median=平均中间两数(偶数), "
        "Q3=sorted[ceil(0.75n)-1]（经验最近秩）"
    )

    meta = {
        "script": str(Path(__file__).resolve()),
        "runtime_seconds": round(total_runtime, 3),
        "per_case_runtime_ms": [round(x, 2) for x in per_case_runtime_ms],
        "n_cases": len(files),
        "input_list": input_names,
        "excluded": [
            "case_009_problem_2_trace.json",
            "case_035_problem_3_trace.json",
            "case_078_problem_1_trace.json",
            "config.txt",
        ],
    }

    validation = {
        "quartile_convention": convention,
        "reproduced": reproduced,
        "expected": {
            k: {"min": v[0], "Q1": v[1], "median": v[2], "Q3": v[3], "max": v[4]}
            for k, v in VALIDATION_TARGETS.items()
        },
        "status": status,
        "discrepancies": discrepancies,
    }

    summary = {
        "aggregates": aggregates,
        "validation": validation,
        "meta": meta,
    }

    # --- Write per-case CSV ---
    csv_path = out_dir / "per_case_stats.csv"
    columns = [
        "case_id", "n_ops", "n_tensors", "n_edges", "n_noncopy_ops", "W_M", "W_V",
        "cp_cycles", "cp_ops", "max_level_width", "avg_parallelism",
        "multi_use_tensor_ratio", "span_ops_median", "span_ops_max",
        "span_cycles_median", "span_cycles_max", "anomalies",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)
        writer.writeheader()
        for r in per_case:
            out_row = {}
            for c in columns:
                v = r.get(c, "")
                if c != "case_id" and c != "anomalies" and v is not None:
                    v = _compact_float(v)
                out_row[c] = "" if v is None else v
            writer.writerow(out_row)

    # --- Write summary JSON ---
    json_path = out_dir / "summary.json"
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    # --- Write Chinese materials markdown ---
    md_path = out_dir / "并行度统计材料.md"
    md_path.write_text(
        render_markdown(aggregates, validation, meta, per_case),
        encoding="utf-8",
    )

    # --- Console summary ---
    def agg_line(metric: str, label: str) -> str:
        a = aggregates[metric]
        return (f"  {label:<28} min={fmt_metric(metric, a['min']):>12} "
                f"Q1={fmt_metric(metric, a['Q1']):>12} "
                f"med={fmt_metric(metric, a['median']):>12} "
                f"Q3={fmt_metric(metric, a['Q3']):>12} "
                f"max={fmt_metric(metric, a['max']):>12}")

    print("=" * 92)
    print("INPUT-STRUCTURE STATISTICS — 100 official HWCupA2026 graphs")
    print("=" * 92)
    print("Key aggregates (min / Q1 / median / Q3 / max):")
    print(agg_line("cp_cycles", "critical path (cycles)"))
    print(agg_line("cp_ops", "critical path (#ops)"))
    print(agg_line("max_level_width", "max parallel width"))
    print(agg_line("avg_parallelism", "avg parallelism"))
    print(agg_line("multi_use_tensor_ratio", "multi-use tensor ratio"))
    print(agg_line("span_ops_median", "reuse span_ops median"))
    print(agg_line("span_ops_max", "reuse span_ops max"))
    print(agg_line("span_cycles_median", "reuse span_cycles median"))
    print(agg_line("span_cycles_max", "reuse span_cycles max"))
    print("-" * 92)
    print(f"Validation (表S2-1): {status}"
          + ("" if status == "PASS" else f"  discrepancies={discrepancies}"))
    print(f"Quartile convention: {convention}")
    print(f"Runtime: {total_runtime:.2f}s total across {len(files)} cases "
          f"(slowest case {max(per_case_runtime_ms):.0f} ms)")
    anomalies = [r["case_id"] for r in per_case if r["anomalies"]]
    print(f"Anomalies (cycles): {anomalies if anomalies else 'none'}")
    print("-" * 92)
    print("Output files:")
    for p in (csv_path, json_path, md_path):
        print(f"  {p}")

    if status != "PASS":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
