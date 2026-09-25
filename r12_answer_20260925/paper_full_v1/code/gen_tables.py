"""由冻结数据直接生成第8章统计表与附录逐例结果表（Markdown），避免手抄。

输出到 ../chapters/_gen/*.md，由 merge.py 通过 <!-- include: _gen/xxx.md --> 展开。
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
R12 = HERE.parents[1]
GEN = HERE.parent / "chapters/_gen"
F = json.loads((HERE.parent / "qa/facts.json").read_text(encoding="utf-8"))
GROUPS = [("A", k) for k in (2, 3, 4, 5)] + [("B", k) for k in range(1, 6)] + [("L2", k) for k in range(1, 6)]
NAME = {"A": "A", "B": "B", "L2": "L2"}


def label(sc, k):
    return f"{sc}{k}" if sc != "L2" else f"L2-{k}"


def rows(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write(name, text):
    GEN.mkdir(parents=True, exist_ok=True)
    (GEN / f"{name}.md").write_text(text.rstrip() + "\n", encoding="utf-8")


def gap_table():
    out = ["| 场景-核数 | 间隙上界中位/% | 间隙上界P90/% | ≤1% | ≤3% | ≤5% | ≤10% | 下界由M/V/CP决定 |",
           "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for sc, k in GROUPS:
        key = f"{sc}{k}.gap"
        out.append(f"| {label(sc, k)} | {F[key+'.median_pct']:.2f} | {F[key+'.p90_pct']:.2f} | {F[key+'.le1pct']} | "
                   f"{F[key+'.le3pct']} | {F[key+'.le5pct']} | {F[key+'.le10pct']} | "
                   f"{F[key+'.bind_M']}/{F[key+'.bind_V']}/{F[key+'.bind_CP']} |")
    out.append(f"| REF（整图单核） | {F['REF.gap.median_pct']:.2f} | — | {F['REF.gap.le1pct']} | {F['REF.gap.le3pct']} | "
               f"{F['REF.gap.le5pct']} | {F['REF.gap.le10pct']} | 同B1 |")
    write("S8_gap", "\n".join(out))


def speed_table():
    out = ["| 场景-核数 | 平均加速比 | 并行效率 $\\overline S_k/k$ | 最小（用例） | 最大（用例） | 加速比超过核数的图数 |",
           "|---|---:|---:|---:|---:|---:|"]
    for sc, k in GROUPS:
        key = f"{sc}{k}"
        eff = "—" if k == 1 else f"{F[key+'.efficiency']:.4f}"
        out.append(f"| {label(sc, k)} | {F[key+'.mean_speedup']:.4f} | {eff} | {F[key+'.min_speedup']:.4f}（{F[key+'.min_case']}） | "
                   f"{F[key+'.max_speedup']:.4f}（{F[key+'.max_case']}） | {F[key+'.superlinear_count']} |")
    write("S8_speed", "\n".join(out))


def sign_table():
    out = ["| 场景-核数 | 更快/持平/更慢 | 符号检验 $\\log_{10}p$ | Wilcoxon $z$ | 有效配对数 |",
           "|---|---:|---:|---:|---:|"]
    for sc, k in GROUPS:
        key = f"{sc}{k}"
        out.append(f"| {label(sc, k)} | {F[key+'.C3.wins']}/{F[key+'.C3.ties']}/{F[key+'.C3.losses']} | "
                   f"{F[key+'.sign_log10p']:.2f} | {F[key+'.wilcoxon_z']:.2f} | {F[key+'.wilcoxon_n']} |")
    write("S8_sign", "\n".join(out))


def rank_table():
    out = ["| 场景-核数 | 规模与加速比的Spearman $r_s$ | 规模与求解墙钟的Spearman $r_s$ |", "|---|---:|---:|"]
    for sc, k in (("A", 2), ("A", 5), ("B", 2), ("B", 5), ("L2", 5)):
        key = f"{sc}{k}"
        out.append(f"| {label(sc, k)} | {F[key+'.spearman_size_speedup']:.3f} | {F[key+'.spearman_size_wall']:.3f} |")
    write("S8_rank", "\n".join(out))


def summary_table():
    out = ["| 核数 | 问题一 场景A | 问题二 场景B | 问题三 无L2（$P_B$） | 问题三 只读Cache（$P_L$） | 同方案配置比 $\\overline R_{\\mathrm{hw}}$ | 分别选优比 $\\overline R_{\\mathrm{select}}$ |",
           "|---|---:|---:|---:|---:|---:|---:|"]
    for k in range(1, 6):
        a = "1（定义）" if k == 1 else f"{F[f'A{k}.mean_speedup']:.4f}"
        b = "1（定义）" if k == 1 else f"{F[f'B{k}.mean_speedup']:.4f}"
        out.append(f"| {k} | {a} | {b} | {F[f'B{k}.mean_speedup']:.4f} | {F[f'L2{k}.mean_speedup']:.4f} | "
                   f"{F[f'Q3.k{k}.same_plan_mean']:.6f} | {F[f'Q3.k{k}.separate_selection_mean']:.6f} |")
    write("S10_summary", "\n".join(out))


def appendix():
    cells = {(r["case"], int(r["k"]), r["scene"]): r for r in rows(R12 / "figures_v3/delivery/data/F31.csv")}
    cases = sorted({c for c, _, _ in cells})
    q3 = {(r["case"], int(r["cores"])): r for r in rows(R12 / "publication/tables/Q3_per_case.csv")}
    q1 = {(r["case"], int(r["cores"])): r for r in rows(R12 / "publication/tables/Q1_per_case.csv")}
    q2 = {(r["case"], int(r["cores"])): r for r in rows(R12 / "publication/tables/Q2_per_case.csv")}
    # 交叉核对：F31 与冻结附录CSV逐项一致
    for (c, k), r in q1.items():
        assert int(cells[(c, k, "A")]["T"]) == int(r["makespan"]) and int(cells[(c, k, "A")]["copy"]) == int(r["added_copy_bytes"])
    for (c, k), r in q2.items():
        assert int(cells[(c, k, "B")]["T"]) == int(r["makespan"]) and int(cells[(c, k, "B")]["copy"]) == int(r["added_copy_bytes"])
    for (c, k), r in q3.items():
        assert int(cells[(c, k, "L2")]["T"]) == int(r["L2_selected_makespan"])
        assert int(cells[(c, k, "B")]["T"]) == int(r["B_makespan"])
    t = ["| 用例 | REF单核 | 2核 | 3核 | 4核 | 5核 |", "|---|---:|---:|---:|---:|---:|"]
    for c in cases:
        t.append(f"| {c} | {cells[(c, 2, 'A')]['REF']} | " + " | ".join(q1[(c, k)]["makespan"] for k in (2, 3, 4, 5)) + " |")
    write("A_q1_makespan", "\n".join(t))
    t = ["| 用例 | 2核 | 3核 | 4核 | 5核 |", "|---|---:|---:|---:|---:|"]
    for c in cases:
        t.append(f"| {c} | " + " | ".join(q1[(c, k)]["added_copy_bytes"] for k in (2, 3, 4, 5)) + " |")
    write("A_q1_copy", "\n".join(t))
    t = ["| 用例 | 1核 | 2核 | 3核 | 4核 | 5核 |", "|---|---:|---:|---:|---:|---:|"]
    for c in cases:
        t.append(f"| {c} | " + " | ".join(q2[(c, k)]["makespan"] for k in range(1, 6)) + " |")
    write("A_q2_makespan", "\n".join(t))
    t = ["| 用例 | 1核 | 2核 | 3核 | 4核 | 5核 |", "|---|---:|---:|---:|---:|---:|"]
    for c in cases:
        t.append(f"| {c} | " + " | ".join(q2[(c, k)]["added_copy_bytes"] for k in range(1, 6)) + " |")
    write("A_q2_copy", "\n".join(t))
    for k in range(1, 6):
        t = ["| 用例 | 无L2 Makespan | 无L2 新增COPY | 只读Cache Makespan | 只读Cache 新增COPY | 只读Cache 命中率/% | 同方案开L2 Makespan | 同方案命中率/% |",
             "|---|---:|---:|---:|---:|---:|---:|---:|"]
        for c in cases:
            r = q3[(c, k)]
            t.append(f"| {c} | {r['B_makespan']} | {r['B_added_copy_bytes']} | {r['L2_selected_makespan']} | "
                     f"{r['L2_selected_added_copy_bytes']} | {float(r['L2_selected_byte_hit_rate'])*100:.4f} | "
                     f"{r['L2_same_B_plan_makespan']} | {float(r['L2_same_plan_byte_hit_rate'])*100:.4f} |")
        write(f"A_q3_k{k}", "\n".join(t))


if __name__ == "__main__":
    speed_table(); sign_table(); rank_table(); summary_table(); appendix()
    print("tables ->", GEN)
