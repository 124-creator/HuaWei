# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Assemble chapter-6 upload files: Q2 formula/table slice, Q2 material copy, facts table."""
import csv
import hashlib
import json
import math
from pathlib import Path

BASE = Path(r"E:/HWCupA2026/derived/r12_answer_20260925")
KIT = BASE / "web_agent_kit_v1"
WORK = BASE / "formulas_tables_v1/公式与三线表工作稿.md"
ANSWERS = BASE / "figures_v3/answers/Q2.md"
CO = BASE / "publication/sources/closeout/results"
C3 = BASE / "publication/sources/C3_official_cells.csv"
OUT = KIT / "上传给网页agent/第6章"


def load(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(path.open(encoding="utf-8-sig")))


def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs)


def median(xs: list[float]) -> float:
    data = sorted(xs)
    return data[49:51] and (data[49] + data[50]) / 2


def p95(xs: list[float]) -> float:
    data = sorted(xs)
    return data[math.ceil(0.95 * len(data)) - 1]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    text = WORK.read_text(encoding="utf-8")
    start = text.index("## 问题二")
    stop = text.index("\n## 问题三")
    slice_text = ("# 第6章_公式与表（节选自《公式与三线表工作稿》）\n\n"
                  "引用占位：公式【式(2-1)】、表【表2-1】；最终编号由团队统一重排。\n\n" + text[start:stop])
    (OUT / "第6章_公式与表.md").write_text(slice_text, encoding="utf-8")
    assert slice_text.count("\\tag{2-") == 12 and slice_text.count("**表2-") == 4
    (OUT / "第6章_内容材料_Q2.md").write_text(ANSWERS.read_text(encoding="utf-8"), encoding="utf-8")
    sel = load(CO / "selected_per_case.csv")
    cells = load(C3)
    ref = {r["case_id"]: float(r["makespan_cycles"]) for r in cells if r["problem"] == "REF"}
    stages = json.loads((BASE / "figures_v3/dataset.json").read_bytes())["stages"]
    lines = ["# 第6章_事实数值表（本章实验数值，以此为准）", "",
             "使用说明：本章正文引用的实验数值均以下表为准（原样引用，不得改动）；叙述需要表外数值时写 [需补数：说明]。使用要求与第5章相同（按上面要求执行）。", "",
             "口径：1 MiB=1048576 bytes；加速比为逐图比值算术平均；P95为经验最近秩；全部来自冻结closeout表。", "",
             "## 0. 题面固定参数与算法参数（允许引用）", "",
             "- 硬件：L1=524288 bytes、UB=131072 bytes、DDR=60 bytes/cycle；场景B跨核同步500 cycles；只读L2：1 MiB、250 bytes/cycle（仅问题三）。",
             "- 规模：100张官方计算图、核数1–5、单请求软预算600秒。",
             "- 算法参数：活动核数m≤k；驻留组织target∈{0,512,2048}；Spill触发：张量≥容量/4且前后使用子图距离≤8；微批窗口∈{4,8}、每候选≤16窗口、每窗口≤128操作；快速插入构造≤30秒；单次评价≤120秒；Spill诊断40秒；每个微批候选评分45秒。", "",
             "## 1. 场景B逐核主结果（每格100图）", "",
             "| 核数 | 平均加速比 | 中位加速比 | 最小加速比 | 均值新增COPY/MiB | 边界/MiB | Spill/MiB | 墙钟中位/s | 墙钟P95/s |",
             "|---|---|---|---|---|---|---|---|---|"]
    for k in ("1", "2", "3", "4", "5"):
        g = [r for r in sel if r["scene"] == "B" and r["cores"] == k]
        sp = [float(r["speedup"]) for r in g]
        add = mean([float(r["added_copy_bytes"]) for r in g]) / 1048576
        part = mean([float(r["partition_added_copy_bytes"]) for r in g]) / 1048576
        spill = mean([float(r["spill_added_copy_bytes"]) for r in g]) / 1048576
        wall = [float(r["wall_seconds"]) for r in g]
        lines.append(f"| {k} | {mean(sp):.6f} | {median(sp):.6f} | {min(sp):.6f} | {add:.4f} | {part:.4f} | {spill:.4f} | {median(wall):.4f} | {p95(wall):.4f} |")
    lines += ["", "注：一核行为优化B1实测均值；标准参考曲线的一核参考点按原题定义为1，两者不可混用。", "",
              "## 2. 相对C3的逐例对照（每格100图）", "",
              "| 核数 | 加速比均值 T_C3/T_R12 | 逐图降幅均值 | 更快/持平/更慢 | 更快但COPY更高 | C3平均加速比 REF/T_C3 |",
              "|---|---|---|---|---|---|"]
    deg = []
    for k in ("1", "2", "3", "4", "5"):
        g = [r for r in sel if r["scene"] == "B" and r["cores"] == k]
        c3 = {r["case_id"]: float(r["makespan_cycles"]) for r in cells if r["problem"] == "B" and r["k"] == k}
        dm = {r["case_id"]: float(r["data_movement_bytes"]) for r in cells if r["problem"] == "B" and r["k"] == k}
        rat = [c3[r["case"]] / float(r["makespan"]) for r in g]
        red = [1 - float(r["makespan"]) / c3[r["case"]] for r in g]
        w = sum(float(r["makespan"]) < c3[r["case"]] for r in g)
        tie = sum(float(r["makespan"]) == c3[r["case"]] for r in g)
        fmc = sum(float(r["makespan"]) < c3[r["case"]] and float(r["added_copy_bytes"]) > dm[r["case"]] for r in g)
        c3sp = mean([ref[r["case"]] / c3[r["case"]] for r in g])
        if k == "5":
            assert abs(mean(red) - 0.344910) < 1e-5 and (w, tie, len(g) - w - tie, fmc) == (94, 5, 1, 4), (mean(red), w, tie, fmc)
        if k == "1":
            assert abs(mean(sp := [float(r["speedup"]) for r in g]) - 1.061366) < 1e-5
        for r in g:
            if float(r["makespan"]) > c3[r["case"]]:
                deg.append((r["case"], k, 100 * (float(r["makespan"]) / c3[r["case"]] - 1)))
        lines.append(f"| {k} | {mean(rat):.6f} | {100*mean(red):.4f}% | {w} / {tie} / {len(g)-w-tie} | {fmc} | {c3sp:.6f} |")
    lines += ["", "## 3. 全部退化配置（B场景，相对C3耗时增加%）", ""]
    for case, k, slow in sorted(deg, key=lambda x: (int(x[1]), x[0])):
        lines.append(f"- {case} / {k}核：+{slow:.3f}%")
    g5 = [r for r in sel if r["scene"] == "B" and r["cores"] == "5"]
    spill5 = sorted([float(r["spill_added_copy_bytes"]) for r in g5], reverse=True)
    pos = sum(x > 0 for x in spill5)
    top10 = 100 * sum(spill5[:10]) / sum(spill5)
    lines += ["", "## 4. 五核B的Spill集中度", "",
              f"- 有Spill的图数：{pos} / 100（零Spill {100-pos} 图）；",
              f"- 前10图贡献全部Spill字节的 {top10:.2f}%。"]
    assert pos == 22 and abs(top10 - 93.84) < 0.01, (pos, top10)
    b1 = [r for r in sel if r["scene"] == "B" and r["cores"] == "1"]
    improve = sum(float(r["T"]) < float(r["REF"]) for r in b1) if "T" in b1[0] else None
    lines += ["", "## 5. 优化B1", "",
              "- 优化B1平均REF加速比 1.061366；55图改善、45图相同（按逐例比值统计）。", ""]
    means = [mean([r["REF"] / r[st] for r in stages]) for st in ("control", "indexed", "full")]
    count = [sum(r["indexed"] < r["control"] for r in stages), sum(r["full"] < r["indexed"] for r in stages)]
    assert abs(means[2] - 4.131077) < 1e-5 and count == [12, 2]
    lines += ["## 6. 同次请求三阶段（五核B，100请求）", "",
              "| 阶段 | 相对REF平均加速比 | 较前阶段严格改善 |", "|---|---|---|",
              f"| 控制 | {means[0]:.6f} | （基准） |", f"| 插入后 | {means[1]:.6f} | {count[0]} / 100 |",
              f"| 微批后 | {means[2]:.6f} | {count[1]} / 100 |"]
    change = [r for r in stages if r["full"] < r["indexed"]]
    delta_sum = sum(r["REF"] / r["full"] - r["REF"] / r["indexed"] for r in change)
    lines += ["", "两个进一步改善实例（原始cycles，控制→插入后→微批后）："]
    for r in change:
        c = r["REF"] / r["full"] - r["REF"] / r["indexed"]
        lines.append(f"- {r['case']}：{r['control']:,} → {r['indexed']:,} → {r['full']:,}；该阶段加速比增量贡献 {100*c/delta_sum:.2f}%")
    c73 = next(r for r in g5 if r["case"] == "case_073")
    lines += ["", "## 7. case_073（B五核）", "",
              f"- Makespan {c73['makespan']} cycles；边界新增 {c73['partition_added_copy_bytes']} bytes；Spill新增 {c73['spill_added_copy_bytes']} bytes。",
              "", "注：全部数值来自冻结closeout表与冻结阶段数据；同次请求三阶段共享预算，不是等预算独立消融。"]
    (OUT / "第6章_事实数值表.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    report = {"files": sorted(p.name for p in OUT.iterdir()),
              "slice_sha256": hashlib.sha256((OUT / "第6章_公式与表.md").read_bytes()).hexdigest(),
              "facts_sha256": hashlib.sha256((OUT / "第6章_事实数值表.md").read_bytes()).hexdigest(),
              "degradations": len(deg)}
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
