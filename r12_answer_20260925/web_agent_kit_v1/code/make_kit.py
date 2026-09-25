# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Assemble chapter-5 upload files: formula/table slice, Q1 material copy, number whitelist."""
import csv
import hashlib
import json
import math
from pathlib import Path

BASE = Path(r"E:/HWCupA2026/derived/r12_answer_20260925")
KIT = BASE / "web_agent_kit_v1"
WORK = BASE / "formulas_tables_v1/公式与三线表工作稿.md"
ANSWERS = BASE / "figures_v3/answers/Q1.md"
CO = BASE / "publication/sources/closeout/results"
C3 = BASE / "publication/sources/C3_official_cells.csv"
OUT = KIT / "上传给网页agent"


def load(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(path.open(encoding="utf-8-sig")))


def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs)


def p95(xs: list[float]) -> float:
    data = sorted(xs)
    return data[math.ceil(0.95 * len(data)) - 1]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    text = WORK.read_text(encoding="utf-8")
    start = text.index("## 问题一")
    stop = text.index("\n## 问题二")
    slice_text = "# 第5章_公式与表（节选自《公式与三线表工作稿》）\n\n引用占位：公式【式(1-1)】、表【表1-1】；最终编号由团队统一重排。\n\n" + text[start:stop]
    (OUT / "第5章_公式与表.md").write_text(slice_text, encoding="utf-8")
    assert slice_text.count("\\tag{1-") == 15 and slice_text.count("**表1-") == 4
    (OUT / "第5章_内容材料_Q1.md").write_text(ANSWERS.read_text(encoding="utf-8"), encoding="utf-8")
    sel = load(CO / "selected_per_case.csv")
    cells = load(C3)
    ref = {r["case_id"]: float(r["makespan_cycles"]) for r in cells if r["problem"] == "REF"}
    lines = ["# 第5章_事实数值表（本章实验数值，以此为准）", "",
             "使用说明：本章正文引用的实验数值均以下表为准（原样引用，不得改动或四舍五入改数）；若叙述需要表外数值，写 [需补数：说明]。题面固定参数与算法参数可直接引用（见§0）。", "",
             "口径：1 MiB=1048576 bytes；加速比为逐图比值算术平均；P95为经验最近秩；全部来自冻结closeout表。", "",
             "## 0. 题面固定参数与算法参数（来自原题与冻结解答，允许引用）", "",
             "- 硬件：L1=524288 bytes、UB=131072 bytes、DDR带宽=60 bytes/cycle；场景A等待：同核切换100 cycles、跨核前驱1000 cycles；场景B跨核同步500 cycles；只读L2：1 MiB、250 bytes/cycle（仅问题三）。",
             "- 规模：100张官方计算图、核数1–5、单请求软预算600秒（问题一为2–5核）。",
             "- 算法参数：依赖带宽度取4/8/2/16；软目标2048操作；快速插入候选构造上限30秒；单次完整评价上限120秒；整体受剩余预算约束。", "",
             "## 1. 场景A逐核主结果（每格100图）", "",
             "| 核数 | 平均加速比 | 中位加速比 | 最小加速比 | 均值新增COPY/MiB | 边界/MiB | Spill/MiB | 墙钟中位/s | 墙钟P95/s |",
             "|---|---|---|---|---|---|---|---|---|"]
    for k in ("2", "3", "4", "5"):
        g = [r for r in sel if r["scene"] == "A" and r["cores"] == k]
        sp = [float(r["speedup"]) for r in g]
        add = mean([float(r["added_copy_bytes"]) for r in g]) / 1048576
        part = mean([float(r["partition_added_copy_bytes"]) for r in g]) / 1048576
        spill = mean([float(r["spill_added_copy_bytes"]) for r in g]) / 1048576
        wall = [float(r["wall_seconds"]) for r in g]
        lines.append(f"| {k} | {mean(sp):.6f} | {sorted(sp)[len(sp)//2-1:len(sp)//2+1] and (sorted(sp)[49]+sorted(sp)[50])/2:.6f} | {min(sp):.6f} | {add:.4f} | {part:.4f} | {spill:.4f} | {(sorted(wall)[49]+sorted(wall)[50])/2:.4f} | {p95(wall):.4f} |")
    lines += ["", "## 2. 相对C3的逐例对照（每格100图）", "",
              "| 核数 | 加速比均值 T_C3/T_R12 | 逐图降幅均值 | 更快/持平/更慢 | 更快但COPY更高 | C3平均加速比 REF/T_C3 |",
              "|---|---|---|---|---|---|"]
    deg_all = []
    for k in ("2", "3", "4", "5"):
        g = [r for r in sel if r["scene"] == "A" and r["cores"] == k]
        c3 = {r["case_id"]: float(r["makespan_cycles"]) for r in cells if r["problem"] == "A" and r["k"] == k}
        dm = {r["case_id"]: float(r["data_movement_bytes"]) for r in cells if r["problem"] == "A" and r["k"] == k}
        rat = [c3[r["case"]] / float(r["makespan"]) for r in g]
        red = [1 - float(r["makespan"]) / c3[r["case"]] for r in g]
        w = sum(float(r["makespan"]) < c3[r["case"]] for r in g)
        tie = sum(float(r["makespan"]) == c3[r["case"]] for r in g)
        fmc = sum(float(r["makespan"]) < c3[r["case"]] and float(r["added_copy_bytes"]) > dm[r["case"]] for r in g)
        c3sp = mean([ref[r["case"]] / c3[r["case"]] for r in g])
        if k == "5":
            assert abs(c3sp - 2.036883) < 1e-4, c3sp
        for r in g:
            if float(r["makespan"]) > c3[r["case"]]:
                deg_all.append((r["case"], k, 100 * (float(r["makespan"]) / c3[r["case"]] - 1)))
        lines.append(f"| {k} | {mean(rat):.6f} | {100*mean(red):.4f}% | {w} / {tie} / {len(g)-w-tie} | {fmc} | {c3sp:.6f} |")
    assert len(deg_all) == 9
    lines += ["", "## 3. 全部退化配置（相对C3耗时增加%）", ""]
    for case, k, slow in sorted(deg_all, key=lambda x: (int(x[1]), x[0])):
        lines.append(f"- {case} / {k}核：+{slow:.3f}%")
    ex = load(CO / "budget_exceptions.csv")
    lines += ["", "## 4. 预算例外（case_087）", "",
              "| 场景/核数 | 首次600s | 补跑预算 | 补跑墙钟/s | Makespan/cycles |", "|---|---|---|---|---|"]
    for r in ex:
        lines.append(f"| A{r['cores']} | 无顶层成功 | {int(float(r['budget_seconds']))} s | {float(r['wall_seconds']):.4f} | {r['makespan']} |")
    a5 = {r["case"]: r for r in sel if r["scene"] == "A" and r["cores"] == "5"}
    lines += ["", "## 5. 权衡案例（A5）", "",
              "| 用例 | Makespan/cycles | 新增COPY/bytes |", "|---|---|---|"]
    for case in ("case_002", "case_005"):
        lines.append(f"| {case} | {a5[case]['makespan']} | {a5[case]['added_copy_bytes']} |")
    lines += ["", "## 6. 其他允许出现的数值", "",
              "- 图F07：A五核平均REF加速比 3.743282，C3对照 2.036883（不同搜索成本的最终方案比较）；",
              "- 规模：100张图、400个A场景格、4个1800秒补跑、9个退化配置；",
              "- A五核请求墙钟：中位21.4839 s、P95 470.6481 s、最大1036.1133 s（含构造、评价与I/O，受机器负载影响）；",
              "- 五核最小加速比 1.2023（见上表min列，原样引用）。"]
    (OUT / "第5章_事实数值表.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    legacy = OUT / "第5章_数字白名单.md"
    if legacy.exists():
        legacy.unlink()
    report = {"files": sorted(p.name for p in OUT.iterdir()),
              "slice_sha256": hashlib.sha256((OUT / "第5章_公式与表.md").read_bytes()).hexdigest(),
              "facts_sha256": hashlib.sha256((OUT / "第5章_事实数值表.md").read_bytes()).hexdigest()}
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
