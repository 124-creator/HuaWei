# 本程序及代码是在人工智能工具辅助下完成的。
# 人工智能工具名称、版本/型号、开发机构/公司、版本发布日期：【由参赛队按实际使用情况填写，见论文附录D】
"""R12论文全文事实底座：只读冻结CSV/JSON，确定性地计算正文所需全部数值。

输出 ../qa/facts.json（扁平键值，供数字核对）与 ../qa/事实总表.md（人读版）。
不运行求解器、不调用评价器、不修改任何冻结文件；新增的只是读表统计。
"""
from __future__ import annotations

import csv
import json
import math
import re
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
R12 = HERE.parents[1]                      # r12_answer_20260925/
QA = HERE.parent / "qa"
TAB = R12 / "publication/tables"
RES = R12 / "publication/sources/closeout/results"
FIG = R12 / "figures_v3/delivery/data"
SCENES = ("A", "B", "L2")
CORES = {"A": (2, 3, 4, 5), "B": (1, 2, 3, 4, 5), "L2": (1, 2, 3, 4, 5)}


def rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def nearest_rank(xs, p):
    xs = sorted(xs)
    return xs[max(0, math.ceil(p * len(xs)) - 1)]


def ranks(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for t in range(i, j + 1):
            r[order[t]] = (i + j) / 2 + 1
        i = j + 1
    return r


def spearman(x, y):
    rx, ry = ranks(x), ranks(y)
    mx, my = st.mean(rx), st.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return num / den


def sign_test_two_sided(wins, losses):
    """Exact two-sided binomial sign test, ties excluded; returns log10(p)."""
    n = wins + losses
    m = min(wins, losses)
    tail = sum(math.comb(n, i) for i in range(m + 1)) / 2 ** n
    p = min(1.0, 2 * tail)
    return math.log10(p) if p > 0 else -math.inf


def wilcoxon_z(diffs):
    """Wilcoxon signed-rank, zeros dropped, average ranks, tie-corrected normal z."""
    d = [x for x in diffs if x != 0]
    n = len(d)
    r = ranks([abs(x) for x in d])
    w_plus = sum(ri for ri, x in zip(r, d) if x > 0)
    mean = n * (n + 1) / 4
    ties = Counter(abs(x) for x in d)
    var = n * (n + 1) * (2 * n + 1) / 24 - sum(t ** 3 - t for t in ties.values()) / 48
    return n, w_plus, (w_plus - mean) / math.sqrt(var)


def main() -> None:
    F: dict[str, object] = {}

    # ---- 1. 冻结汇总表（不重算，原样登记） ----
    for r in rows(TAB / "summary.csv"):
        key = f"{r['scene']}{r['cores']}"
        for c in ("mean_speedup", "median_speedup", "min_speedup", "mean_added_MiB", "mean_partition_MiB",
                  "mean_spill_MiB", "wall_median_s", "wall_p95_s", "wall_max_s"):
            F[f"{key}.{c}"] = float(r[c])
        for c in ("wins_REF", "ties_REF", "losses_REF", "extended_budget"):
            F[f"{key}.{c}"] = int(r[c])
    for r in rows(TAB / "comparison_C3.csv"):
        key = f"{r['scene']}{r['cores']}.C3"
        F[f"{key}.ratio_mean"] = float(r["ratio_mean"])
        F[f"{key}.reduction_pct"] = float(r["time_reduction_percent"])
        for c in ("wins", "ties", "losses", "faster_more_copy"):
            F[f"{key}.{c}"] = int(r[c])
    for r in rows(RES / "q3_paired_summary.csv"):
        key = f"Q3.k{r['cores']}"
        for c in ("same_plan_mean", "same_plan_median", "same_plan_min", "same_plan_max",
                  "separate_selection_mean", "REF_over_L2_same_plan", "same_plan_mean_byte_hit_rate"):
            F[f"{key}.{c}"] = float(r[c])
        for c in ("improved", "ties", "degraded", "different_final_plan_count"):
            F[f"{key}.{c}"] = int(r[c])

    # ---- 2. 逐例总表（含REF与C3） ----
    cells = rows(FIG / "F31.csv")
    D = {(r["case"], int(r["k"]), r["scene"]): r for r in cells}
    F["cells.total"] = len(cells)
    for sc in SCENES:
        for k in CORES[sc]:
            cc = [r for r in cells if r["scene"] == sc and int(r["k"]) == k]
            sp = [float(r["speedup"]) for r in cc]
            key = f"{sc}{k}"
            lo = min(cc, key=lambda r: float(r["speedup"]))
            hi = max(cc, key=lambda r: float(r["speedup"]))
            F[f"{key}.min_case"] = lo["case"]
            F[f"{key}.max_case"] = hi["case"]
            F[f"{key}.max_speedup"] = float(hi["speedup"])
            F[f"{key}.superlinear_count"] = sum(x > k for x in sp)
            F[f"{key}.efficiency"] = st.mean(sp) / k
            F[f"{key}.C3_speedup_mean"] = st.mean(float(r["C3_speedup"]) for r in cc)
            F[f"{key}.spill_graphs"] = sum(int(r["spill"]) > 0 for r in cc)
            F[f"{key}.wall_over600"] = sum(float(r["wall"]) > 600 for r in cc)
            wmax = max(cc, key=lambda r: float(r["wall"]))
            F[f"{key}.wall_max_case"] = wmax["case"]
            # 相对C3的配对检验（仅作描述性支持；每格100张不同图）
            wins = sum(int(r["T"]) < int(r["C3_T"]) for r in cc)
            losses = sum(int(r["T"]) > int(r["C3_T"]) for r in cc)
            F[f"{key}.sign_log10p"] = sign_test_two_sided(wins, losses)
            n, wplus, z = wilcoxon_z([math.log(int(r["C3_T"]) / int(r["T"])) for r in cc])
            F[f"{key}.wilcoxon_n"] = n
            F[f"{key}.wilcoxon_z"] = z
            # 退化（相对C3更慢）的逐项幅度
            for r in cc:
                if int(r["T"]) > int(r["C3_T"]):
                    F[f"{key}.slower.{r['case']}_pct"] = (int(r["T"]) / int(r["C3_T"]) - 1) * 100
    F["A.slower_total"] = sum(1 for k in CORES["A"] for key in [f"A{k}"] for f in F if f.startswith(key + ".slower."))
    F["B.slower_total"] = sum(1 for k in CORES["B"] for f in F if f.startswith(f"B{k}.slower."))

    # 规模相关性（Spearman）
    graphs = {r["case"]: r for r in rows(FIG / "F03.csv")}
    size = {c: int(g["noncopy_ops"]) for c, g in graphs.items()}
    for sc, k in (("A", 5), ("B", 5), ("L2", 5), ("A", 2), ("B", 2)):
        cs = sorted(size)
        F[f"{sc}{k}.spearman_size_speedup"] = spearman([size[c] for c in cs], [float(D[(c, k, sc)]["speedup"]) for c in cs])
        F[f"{sc}{k}.spearman_size_wall"] = spearman([size[c] for c in cs], [float(D[(c, k, sc)]["wall"]) for c in cs])

    # ---- 3. 输入图普查 ----
    ops = [int(g["noncopy_ops"]) for g in graphs.values()]
    F["graphs.count"] = len(graphs)
    F["graphs.ops_min"], F["graphs.ops_max"], F["graphs.ops_median"] = min(ops), max(ops), st.median(ops)
    F["graphs.ops_q1"], F["graphs.ops_q3"] = nearest_rank(ops, .25), nearest_rank(ops, .75)
    F["graphs.ops_span_ratio"] = max(ops) / min(ops)
    for col in ("tensors", "edges", "M_work", "V_work"):
        xs = [int(g[col]) for g in graphs.values()]
        F[f"graphs.{col}_min"], F[f"graphs.{col}_max"] = min(xs), max(xs)
        F[f"graphs.{col}_median"] = st.median(xs)
        F[f"graphs.{col}_q1"], F[f"graphs.{col}_q3"] = nearest_rank(xs, .25), nearest_rank(xs, .75)
    F["graphs.M_zero"] = sum(int(g["M_work"]) == 0 for g in graphs.values())
    F["graphs.V_zero"] = sum(int(g["V_work"]) == 0 for g in graphs.values())
    order = sorted(size, key=lambda c: -size[c])
    for i, c in enumerate(order, 1):
        F[f"graphs.size.{c}"] = size[c]
        F[f"graphs.size_rank.{c}"] = i
    F["graphs.ops_le_1000"] = sum(x <= 1000 for x in ops)
    F["graphs.ops_ge_10000"] = sum(x >= 10000 for x in ops)
    mshare = [int(g["M_work"]) / (int(g["M_work"]) + int(g["V_work"])) for g in graphs.values()]
    F["graphs.M_share_min"], F["graphs.M_share_max"], F["graphs.M_share_median"] = min(mshare), max(mshare), st.median(mshare)
    F["graphs.M_dominant"] = sum(int(g["M_work"]) > int(g["V_work"]) for g in graphs.values())
    F["graphs.V_dominant"] = sum(int(g["M_work"]) < int(g["V_work"]) for g in graphs.values())
    ratio = [max(float(g["L1_max_ratio"]), float(g["UB_max_ratio"])) for g in graphs.values()]
    F["graphs.max_tensor_ratio_max"] = max(ratio)
    F["graphs.max_tensor_ratio_lt_0_1"] = sum(x < .1 for x in ratio)

    # ---- 4. 下界与最优性间隙上界（verification.json，冻结校验字段） ----
    ver = json.loads((RES / "verification.json").read_text(encoding="utf-8"))
    F["verify.selected_cells"] = ver["selected_cells"]
    F["verify.same_plan_pairs"] = ver["same_plan_pairs"]
    F["verify.checks_total"] = ver["selected_and_control_checks"]
    for k, v in ver["origin_counts"].items():
        F[f"verify.origin.{k}"] = v
    F["verify.control_checks"] = sum(1 for c in ver["checks"] if c["kind"] == "fixed_B_plan")
    F["verify.first_attempt_failures"] = ver["first_attempt_failures"]
    F["verify.extended_budget_successes"] = ver["extended_budget_successes"]
    sel = [c for c in ver["checks"] if c["kind"] == "selected"]
    below = 0
    for c in sel:
        T = int(D[(c["case"], c["cores"], c["scene"])]["T"])
        k = c["cores"]
        lb = max(-(-c["matrix_work"] // k), -(-c["vector_work"] // k), c["critical_path_compute_only"])
        assert lb == c["global_compute_lower_bound"], c
        below += T < lb
        assert abs((T - lb) / lb - c["compute_gap_upper_bound"]) < 1e-12
    F["lb.violations"] = below
    for sc in SCENES:
        for k in CORES[sc]:
            g = [c["compute_gap_upper_bound"] for c in sel if c["scene"] == sc and c["cores"] == k]
            key = f"{sc}{k}.gap"
            F[f"{key}.median_pct"] = st.median(g) * 100
            F[f"{key}.mean_pct"] = st.mean(g) * 100
            F[f"{key}.p90_pct"] = nearest_rank(g, .9) * 100
            for t in (1, 3, 5, 10):
                F[f"{key}.le{t}pct"] = sum(x <= t / 100 for x in g)
            bind = Counter()
            for c in sel:
                if c["scene"] == sc and c["cores"] == k:
                    m, v = -(-c["matrix_work"] // k), -(-c["vector_work"] // k)
                    bind["M" if c["global_compute_lower_bound"] == m else ("V" if c["global_compute_lower_bound"] == v else "CP")] += 1
            for b in ("M", "V", "CP"):
                F[f"{key}.bind_{b}"] = bind[b]
    lb1 = {c["case"]: c["global_compute_lower_bound"] for c in sel if c["scene"] == "B" and c["cores"] == 1}
    ref = {c: int(D[(c, 1, "B")]["REF"]) for c in lb1}
    rg = [ref[c] / lb1[c] - 1 for c in lb1]
    F["REF.gap.median_pct"], F["REF.gap.mean_pct"] = st.median(rg) * 100, st.mean(rg) * 100
    for t in (1, 3, 5, 10):
        F[f"REF.gap.le{t}pct"] = sum(x <= t / 100 for x in rg)
    # 同图：五核较两核的间隙增量（间隙随核数变松的程度）
    F["gap.growth_note"] = "compute-only bound ignores DDR, sync waits and boundary COPY"

    # ---- 5. 第6章阶段增量与Spill集中度 ----
    stages = rows(FIG / "F19.csv")
    for col in ("control", "indexed", "full"):
        F[f"B5.stage.{col}"] = st.mean(int(r["REF"]) / int(r[col]) for r in stages)
    F["B5.stage.control_share_pct"] = F["B5.stage.control"] / F["B5.stage.full"] * 100
    F["B5.stage.inc_indexed"] = F["B5.stage.indexed"] - F["B5.stage.control"]
    F["B5.stage.inc_full"] = F["B5.stage.full"] - F["B5.stage.indexed"]
    F["B5.stage.improved_indexed"] = sum(int(r["indexed"]) < int(r["control"]) for r in stages)
    F["B5.stage.improved_full"] = sum(int(r["full"]) < int(r["indexed"]) for r in stages)
    for r in stages:
        if int(r["full"]) < int(r["indexed"]):
            d = (int(r["REF"]) / int(r["full"]) - int(r["REF"]) / int(r["indexed"])) / 100
            F[f"B5.stage.{r['case']}.reduction_pct"] = (1 - int(r["full"]) / int(r["indexed"])) * 100
            F[f"B5.stage.{r['case']}.share_pct"] = d / F["B5.stage.inc_full"] * 100
    spill5 = sorted((int(D[(c, 5, "B")]["spill"]) for c in graphs), reverse=True)
    nz = [x for x in spill5 if x > 0]
    F["B5.spill_nonzero"] = len(nz)
    F["B5.spill_top10_share_pct"] = sum(nz[:10]) / sum(nz) * 100
    b1 = [float(D[(c, 1, "B")]["speedup"]) for c in graphs]
    F["B1.improved"] = sum(x > 1 for x in b1)
    F["B1.same"] = sum(x == 1 for x in b1)
    F["B1.worse"] = sum(x < 1 for x in b1)

    # ---- 6. 第7章：配置比分布、选解效应、缓存事件 ----
    pairs = rows(FIG / "F25.csv")
    for k in range(1, 6):
        pk = [r for r in pairs if int(r["k"]) == k]
        hw = [float(r["hardware"]) for r in pk]
        F[f"Q3.k{k}.hw_lt_1_001"] = sum(x < 1.001 for x in hw)
        F[f"Q3.k{k}.hw_gt_1_04"] = sum(x > 1.04 for x in hw)
        F[f"Q3.k{k}.hw_gt_1_1"] = sum(x > 1.1 for x in hw)
        diff = [r for r in pk if r["different"] == "True"]
        F[f"Q3.k{k}.diff_faster"] = sum(float(r["reselection"]) > 1 for r in diff)
        F[f"Q3.k{k}.diff_equal"] = sum(float(r["reselection"]) == 1 for r in diff)
        F[f"Q3.k{k}.diff_slower"] = sum(float(r["reselection"]) < 1 for r in diff)
        F[f"Q3.k{k}.sel_minus_hw"] = F[f"Q3.k{k}.separate_selection_mean"] - F[f"Q3.k{k}.same_plan_mean"]
    for r in rows(TAB / "Q3_degraded.csv"):
        key = f"Q3.degraded.{r['case']}.k{r['cores']}"
        F[f"{key}.same_plan_ratio"] = float(r["same_plan_B_over_L2"])
        F[f"{key}.hit_rate_pct"] = float(r["L2_same_plan_byte_hit_rate"]) * 100
        F[f"{key}.separate_ratio"] = float(r["separate_selection_B_over_L2"])
    cache = rows(FIG / "F27.csv")
    F["case_073.cache_events"] = len(cache)
    F["hw.ddr_over_l2_ratio"] = 250 / 60

    # ---- 7. case_062 与 case_064 专项 ----
    tasks = {(r["case"], int(r["k"])): r for r in rows(FIG / "F09.csv")}
    for k in (2, 3, 4, 5):
        r, t = D[("case_062", k, "A")], tasks[("case_062", k)]
        key = f"case_062.A{k}"
        F[f"{key}.T"], F[f"{key}.C3_T"] = int(r["T"]), int(r["C3_T"])
        F[f"{key}.copy"], F[f"{key}.C3_copy"] = int(r["copy"]), int(r["C3_copy"])
        F[f"{key}.tasks"], F[f"{key}.median_ops"] = int(t["tasks"]), float(t["median_ops"])
        F[f"{key}.max_ops"] = int(t["max_ops"])
        # 同核Task切换等待下界：最忙核心至少有 ceil(tasks/k) 个Task，其间至少 (n-1)*100 cycles
        n_busiest = -(-int(t["tasks"]) // k)
        F[f"{key}.switch_wait_lb"] = (n_busiest - 1) * 100
        F[f"{key}.switch_wait_lb_share_pct"] = (n_busiest - 1) * 100 / int(r["T"]) * 100
    F["case_062.A2_A4_copy_ratio"] = F["case_062.A2.copy"] / F["case_062.A4.copy"]
    for k in (2, 3, 4, 5):
        F[f"case_062.A{k}.reduction_pct"] = (1 - F[f"case_062.A{k}.T"] / F[f"case_062.A{k}.C3_T"]) * 100
    for k in (2, 3, 4, 5):
        tk = [r for r in tasks.values() if int(r["k"]) == k]
        F[f"A{k}.tasks_median"] = st.median(int(r["tasks"]) for r in tk)
        F[f"A{k}.tasks_min"] = min(int(r["tasks"]) for r in tk)
        F[f"A{k}.tasks_max"] = max(int(r["tasks"]) for r in tk)
        F[f"A{k}.imbalance_median"] = st.median(float(r["imbalance"]) for r in tk)
        F[f"A{k}.imbalance_max"] = max(float(r["imbalance"]) for r in tk)
        F[f"A{k}.full_active"] = sum(int(r["active_cores"]) == k for r in tk)
        F[f"A{k}.fewer_active"] = sum(int(r["active_cores"]) < k for r in tk)
    F["gap.le3_total"] = sum(F[f"{sc}{k}.gap.le3pct"] for sc in SCENES for k in CORES[sc])
    F["gap.le1_total"] = sum(F[f"{sc}{k}.gap.le1pct"] for sc in SCENES for k in CORES[sc])
    F["sign.max_log10p"] = max(F[f"{sc}{k}.sign_log10p"] for sc in SCENES for k in CORES[sc])
    F["wilcoxon.min_z"] = min(F[f"{sc}{k}.wilcoxon_z"] for sc in SCENES for k in CORES[sc])
    F["wilcoxon.max_z"] = max(F[f"{sc}{k}.wilcoxon_z"] for sc in SCENES for k in CORES[sc])
    for k in (1, 2, 3, 4, 5):
        r = D[("case_062", k, "B")]
        F[f"case_062.B{k}.vsC3_pct"] = (int(r["T"]) / int(r["C3_T"]) - 1) * 100
    hard = Counter(F[f"{sc}{k}.min_case"] for sc in SCENES for k in CORES[sc] if k > 1)
    F["case_064.min_cells"] = hard["case_064"]
    F["multi_core_min_groups"] = sum(hard.values())

    # ---- 8. 预算例外 ----
    for r in rows(RES / "budget_exceptions.csv"):
        key = f"case_087.A{r['cores']}"
        F[f"{key}.wall"], F[f"{key}.T"], F[f"{key}.speedup"] = float(r["wall_seconds"]), int(r["makespan"]), float(r["speedup"])
    F["case_087.budget_ratio_vs_A5_median"] = 1800 / F["A5.wall_median_s"]

    # ---- 9. 最终方案由哪个组件产生（selected_per_case.csv 中选中方案官方结果文件的相对路径） ----
    def origin(raw: str) -> str:
        rel = re.search(r"/case_\d+_n\d_(?:A|B|L2)/(.*)$", raw).group(1)
        if rel.startswith("indexed_insertion/"):
            return "insertion"
        if rel.startswith("local_microbatch/"):
            return "microbatch"
        if rel.startswith("control/extra/B_plan_evaluated_in_L2"):
            return "cross_config"
        if rel.startswith("control/extra/"):
            return "family"
        if "/control_work/" in rel:
            return "base"
        if "/control_r6/core/" in rel:
            return "core"
        if "/control_r6/critical/" in rel or rel.startswith("control/r7/reassign/"):
            return "feedback"
        if rel.startswith("control/r7/bands/"):
            return "bands"
        raise ValueError(f"未登记的方案来源: {rel}")
    sel_rows = rows(RES / "selected_per_case.csv")
    assert len(sel_rows) == 1400
    oc = Counter((r["scene"], int(r["cores"]), origin(r["raw"])) for r in sel_rows)
    ORIGINS = ("base", "core", "bands", "feedback", "family", "cross_config", "insertion", "microbatch")
    for sc in SCENES:
        for o in ORIGINS:
            F[f"{sc}.origin.{o}"] = sum(oc[(sc, k, o)] for k in CORES[sc])
            for k in CORES[sc]:
                F[f"{sc}{k}.origin.{o}"] = oc[(sc, k, o)]
        F[f"{sc}.origin.improved_stage"] = sum(F[f"{sc}.origin.{o}"] for o in ORIGINS if o != "base")
        F[f"{sc}.origin.improved_stage_pct"] = F[f"{sc}.origin.improved_stage"] / (100 * len(CORES[sc])) * 100
    # 参数层面：场景A依赖带宽度、反馈重排时长口径各自产生的最终方案数
    for w in (2, 4, 8, 16):
        F[f"A.origin.band_w{w}"] = sum(1 for r in sel_rows if r["scene"] == "A" and f"/bands/band{w}_result" in r["raw"])
    for mode in ("local", "observed"):
        F[f"A.origin.reassign_{mode}"] = sum(1 for r in sel_rows if r["scene"] == "A" and f"/reassign/reassign_{mode}_result" in r["raw"])
    assert sum(F[f"A.origin.band_w{w}"] for w in (2, 4, 8, 16)) == F["A.origin.bands"]
    assert F["A.origin.reassign_local"] + F["A.origin.reassign_observed"] == F["A.origin.feedback"]
    # 与五核B同请求阶段记录（F19）交叉核对：最终方案来自插入或微批的图，恰是R12阶段相对控制链有改善的图
    late = {r["case"] for r in sel_rows if r["scene"] == "B" and int(r["cores"]) == 5
            and origin(r["raw"]) in ("insertion", "microbatch")}
    assert late == {r["case"] for r in stages if int(r["full"]) < int(r["control"])}, late

    # ---- 10. 依赖结构与复用特征（队伍增补材料：并行度统计_20260926，表S2-2） ----
    par = rows(HERE.parent / "并行度统计_20260926" / "per_case_stats.csv")
    assert len(par) == 100 and all(not r["anomalies"] for r in par)
    for r in par:     # 与存档数据交叉核对：规模列与F03一致，关键路径与校验记录的计算关键路径一致
        g = graphs[r["case_id"]]
        assert int(r["n_noncopy_ops"]) == int(g["noncopy_ops"]) and int(r["n_edges"]) == int(g["edges"])
    cp_ver = {c["case"]: c["critical_path_compute_only"] for c in sel}
    assert all(int(float(r["cp_cycles"])) == cp_ver[r["case_id"]] for r in par)
    for col in ("cp_cycles", "cp_ops", "max_level_width", "avg_parallelism", "multi_use_tensor_ratio",
                "span_ops_median", "span_ops_max", "span_cycles_median", "span_cycles_max"):
        xs = [float(r[col]) for r in par]
        F[f"s22.{col}.min"], F[f"s22.{col}.max"], F[f"s22.{col}.median"] = min(xs), max(xs), st.median(xs)
        F[f"s22.{col}.q1"], F[f"s22.{col}.q3"] = nearest_rank(xs, .25), nearest_rank(xs, .75)
    pb = {r["case_id"]: r for r in par}
    for c in ("case_048", "case_064"):            # 正文点名的两张图
        F[f"s22.avg_parallelism.{c}"] = float(pb[c]["avg_parallelism"])
        F[f"s22.max_level_width.{c}"] = int(pb[c]["max_level_width"])
    F["s22.avg_parallelism.lt5"] = sum(float(r["avg_parallelism"]) < 5 for r in par)
    F["s22.avg_parallelism.lt10"] = sum(float(r["avg_parallelism"]) < 10 for r in par)
    # 平均并行度与加速比的秩相关（与第8.4节规模相关性同组、同口径）
    for sc, k in (("A", 5), ("B", 5), ("L2", 5), ("A", 2), ("B", 2)):
        cs = sorted(pb)
        F[f"{sc}{k}.spearman_par_speedup"] = spearman([float(pb[c]["avg_parallelism"]) for c in cs],
                                                       [float(D[(c, k, sc)]["speedup"]) for c in cs])
    low = [c for c in pb if float(pb[c]["avg_parallelism"]) < 10]
    for sc in SCENES:
        F[f"{sc}5.speedup_mean.par_lt10"] = st.mean(float(D[(c, 5, sc)]["speedup"]) for c in low)
        F[f"{sc}5.speedup_mean.par_ge10"] = st.mean(float(D[(c, 5, sc)]["speedup"]) for c in pb if c not in low)

    QA.mkdir(parents=True, exist_ok=True)
    (QA / "facts.json").write_text(json.dumps(F, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    lines = ["# 事实总表（facts.py 自动生成，勿手改）", "",
             "来源：publication/tables、closeout/results、figures_v3/delivery/data 的冻结文件；只做读表统计。", "",
             "| 键 | 值 |", "|---|---|"]
    for k in sorted(F):
        v = F[k]
        lines.append(f"| `{k}` | {v:.6g} |" if isinstance(v, float) else f"| `{k}` | {v} |")
    (QA / "事实总表.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"facts: {len(F)} keys -> {QA/'facts.json'}")


if __name__ == "__main__":
    main()
