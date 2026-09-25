# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Assemble chapter-7 upload files: Q3 formula/table slice, Q3 material copy, facts table."""
import csv
import hashlib
import json
import math
from pathlib import Path

BASE = Path(r"E:/HWCupA2026/derived/r12_answer_20260925")
KIT = BASE / "web_agent_kit_v1"
WORK = BASE / "formulas_tables_v1/公式与三线表工作稿.md"
ANSWERS = BASE / "figures_v3/answers/Q3.md"
CO = BASE / "publication/sources/closeout/results"
C3 = BASE / "publication/sources/C3_official_cells.csv"
OUT = KIT / "上传给网页agent/第7章"


def load(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(path.open(encoding="utf-8-sig")))


def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs)


def median(xs: list[float]) -> float:
    data = sorted(xs)
    return (data[49] + data[50]) / 2 if len(data) == 100 else data[len(data) // 2]


def p95(xs: list[float]) -> float:
    data = sorted(xs)
    return data[math.ceil(0.95 * len(data)) - 1]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    text = WORK.read_text(encoding="utf-8")
    slice_text = ("# 第7章_公式与表（节选自《公式与三线表工作稿》）\n\n"
                  "引用占位：公式【式(3-1)】、表【表3-1】；最终编号由团队统一重排。\n\n"
                  + text[text.index("## 问题三"):text.index("\n## 口径与限定")])
    (OUT / "第7章_公式与表.md").write_text(slice_text, encoding="utf-8")
    assert slice_text.count("\\tag{3-") == 11 and slice_text.count("**表3-") == 5
    (OUT / "第7章_内容材料_Q3.md").write_text(ANSWERS.read_text(encoding="utf-8"), encoding="utf-8")
    sel = load(CO / "selected_per_case.csv")
    pair = load(CO / "q3_paired_per_case.csv")
    cells = load(C3)
    ref = {r["case_id"]: float(r["makespan_cycles"]) for r in cells if r["problem"] == "REF"}
    lines = ["# 第7章_事实数值表（本章实验数值，以此为准）", "",
             "使用说明：本章正文引用的实验数值均以下表为准（原样引用，不得改动）；叙述需要表外数值时写 [需补数：说明]。使用要求与第5/6章相同（按上面要求执行）。", "",
             "口径：1 MiB=1048576 bytes；加速比为逐图比值算术平均；P95为经验最近秩；全部来自冻结closeout表。", "",
             "## 0. 题面固定参数（允许引用）", "",
             "- 只读L2：容量1 MiB=1048576 bytes、独立读带宽250 bytes/cycle；DDR带宽60 bytes/cycle；场景B跨核同步500 cycles；",
             "- 规模：100张图、核数1–5、单请求软预算600秒；L2容量与带宽本轮固定，未做参数扫描。", "",
             "## 1. L2逐核主结果（每格100图，L2独立选优方案）", "",
             "| 核数 | 平均加速比 | 中位加速比 | 最小加速比 | 均值新增COPY/MiB | 边界/MiB | Spill/MiB | 墙钟中位/s | 墙钟P95/s |",
             "|---|---|---|---|---|---|---|---|---|"]
    for k in ("1", "2", "3", "4", "5"):
        g = [r for r in sel if r["scene"] == "L2" and r["cores"] == k]
        sp = [float(r["speedup"]) for r in g]
        add = mean([float(r["added_copy_bytes"]) for r in g]) / 1048576
        part = mean([float(r["partition_added_copy_bytes"]) for r in g]) / 1048576
        spill = mean([float(r["spill_added_copy_bytes"]) for r in g]) / 1048576
        wall = [float(r["wall_seconds"]) for r in g]
        lines.append(f"| {k} | {mean(sp):.6f} | {median(sp):.6f} | {min(sp):.6f} | {add:.4f} | {part:.4f} | {spill:.4f} | {median(wall):.4f} | {p95(wall):.4f} |")
    lines += ["", "注：本表为L2配置下独立选优的结果；与“同一B方案开/关L2”的配置对照见§2，两者口径不同。", "",
              "## 2. 同方案配置比与分别选优比（每行100对）", "",
              "| 核数 | 同方案配置比均值 | 同方案配置比中位 | 分别选优比均值 | 改善/相同/退化 | 固定PB下L2相对REF均值 | 逐图命中字节率均值 | 最终方案不同对数 |",
              "|---|---|---|---|---|---|---|---|"]
    pair_sum = {r["cores"]: r for r in load(CO / "q3_paired_summary.csv")}
    for k in ("1", "2", "3", "4", "5"):
        g = [r for r in pair if r["cores"] == k]
        same = [float(r["same_plan_B_over_L2"]) for r in g]
        selr = [float(r["separate_selection_B_over_L2"]) for r in g]
        fix = [float(r["fixed_singlecore"]) / float(r["L2_same_B_plan_makespan"]) for r in g]
        hit = [float(r["L2_same_plan_hit_bytes"]) / (float(r["L2_same_plan_hit_bytes"]) + float(r["L2_same_plan_miss_bytes"])) for r in g]
        imp = sum(x > 1 for x in same)
        deg = sum(x < 1 for x in same)
        if k == "5":
            assert abs(mean(same) - 1.0167659521121053) < 1e-12 and abs(median(same) - 1.0005463808953121) < 1e-12
            assert abs(mean(selr) - 1.0273997188381554) < 1e-12 and abs(mean(fix) - 4.1874572049822465) < 1e-12
            assert abs(mean(hit) - 0.23461356517183732) < 1e-12 and int(pair_sum["5"]["different_final_plan_count"]) == 28
        lines.append(f"| {k} | {mean(same):.6f} | {median(same):.6f} | {mean(selr):.6f} | {imp} / {len(g)-imp-deg} / {deg} | {mean(fix):.6f} | {100*mean(hit):.4f}% | {pair_sum[k]['different_final_plan_count']} |")
    deg_rows = sorted([r for r in pair if float(r["same_plan_B_over_L2"]) < 1], key=lambda r: (int(r["cores"]), r["case"]))
    assert len(deg_rows) == 8
    lines += ["", "## 3. 全部同方案L2退化记录（8条）", "",
              "| 用例 | 核数 | 同方案配置比 | 同方案命中字节率 |", "|---|---|---|---|"]
    for r in deg_rows:
        hit = float(r["L2_same_plan_hit_bytes"]) / (float(r["L2_same_plan_hit_bytes"]) + float(r["L2_same_plan_miss_bytes"]))
        lines.append(f"| {r['case']} | {r['cores']} | {float(r['same_plan_B_over_L2']):.6f} | {100*hit:.4f}% |")
    g5 = [r for r in sel if r["scene"] == "L2" and r["cores"] == "5"]
    wall5 = sorted(float(r["wall_seconds"]) for r in g5)
    add5 = mean([float(r["added_copy_bytes"]) for r in g5]) / 1048576
    part5 = mean([float(r["partition_added_copy_bytes"]) for r in g5]) / 1048576
    spill5 = mean([float(r["spill_added_copy_bytes"]) for r in g5]) / 1048576
    assert abs(add5 - 9.4032) < 1e-3 and abs(part5 - 5.8467) < 1e-3 and abs(spill5 - 3.5565) < 1e-3
    lines += ["", "## 4. 五核L2独立选优的COPY与请求成本", "",
              f"- 平均新增COPY {add5:.4f} MiB（其中边界 {part5:.4f}、Spill {spill5:.4f}）；",
              f"- 请求墙钟：中位 {median(wall5):.4f} s、P95 {p95(wall5):.4f} s、最大 {wall5[-1]:.4f} s。", "",
              "## 5. 五核结果口径摘要", "",
              "| 口径 | 数值 |", "|---|---|",
              f"| 同方案配置比（均值 / 中位） | {1.0167659521121053:.6f} / {1.0005463808953121:.6f} |",
              f"| 分别选优比（均值） | 1.027400 |",
              f"| 固定PB，L2相对REF均值 | 4.187457 |",
              f"| L2独立选优相对REF均值 | 4.218978 |",
              f"| 逐图命中字节率均值 | 23.4614% |",
              f"| 五核不同最终方案对数 | 28 / 100 |", "",
              "注：两条性能口径分开读取；不能用均值曲线相除替代逐图比值平均。", "",
              "## 6. 案例（五核）", "",
              "| 用例 | 无L2 PB/cycles | 有L2同一PB/cycles | L2独立选优/cycles |", "|---|---|---|---|"]
    for case in ("case_073", "case_026"):
        r = next(x for x in pair if x["case"] == case and x["cores"] == "5")
        lines.append(f"| {case} | {r['B_makespan']} | {r['L2_same_B_plan_makespan']} | {r['L2_selected_makespan']} |")
    lines += ["", "## 7. L2最终方案相对C3的逐例对照（每格100图）", "",
              "| 核数 | 加速比均值 T_C3/T_L2 | 逐图降幅均值 | 更快/持平/更慢 | 更快但COPY更高 |",
              "|---|---|---|---|---|"]
    for k in ("1", "2", "3", "4", "5"):
        g = [r for r in sel if r["scene"] == "L2" and r["cores"] == k]
        c3 = {r["case_id"]: float(r["makespan_cycles"]) for r in cells if r["problem"] == "L2" and r["k"] == k}
        dm = {r["case_id"]: float(r["data_movement_bytes"]) for r in cells if r["problem"] == "L2" and r["k"] == k}
        rat = [c3[r["case"]] / float(r["makespan"]) for r in g]
        red = [1 - float(r["makespan"]) / c3[r["case"]] for r in g]
        w = sum(float(r["makespan"]) < c3[r["case"]] for r in g)
        tie = sum(float(r["makespan"]) == c3[r["case"]] for r in g)
        fmc = sum(float(r["makespan"]) < c3[r["case"]] and float(r["added_copy_bytes"]) > dm[r["case"]] for r in g)
        if k == "5":
            assert abs(100 * mean(red) - 31.4081) < 1e-3 and (w, tie, len(g) - w - tie, fmc) == (94, 5, 1, 7), (100 * mean(red), w, tie, fmc)
        lines.append(f"| {k} | {mean(rat):.6f} | {100*mean(red):.4f}% | {w} / {tie} / {len(g)-w-tie} | {fmc} |")
    lines += ["", "## 8. 跨场景五核对照（A / B / L2）", "",
              "| 场景 | 平均加速比 | 边界/MiB | Spill/MiB | 墙钟P95/s |", "|---|---|---|---|---|"]
    for scene in ("A", "B", "L2"):
        g = [r for r in sel if r["scene"] == scene and r["cores"] == "5"]
        sp = [float(r["speedup"]) for r in g]
        part = mean([float(r["partition_added_copy_bytes"]) for r in g]) / 1048576
        spill = mean([float(r["spill_added_copy_bytes"]) for r in g]) / 1048576
        wall = [float(r["wall_seconds"]) for r in g]
        if scene == "A":
            assert abs(mean(sp) - 3.7432824388023844) < 1e-12 and abs(part - 13.5574) < 1e-3 and abs(p95(wall) - 470.6481) < 1e-3
        if scene == "B":
            assert abs(mean(sp) - 4.131077430492359) < 1e-12
        if scene == "L2":
            assert abs(mean(sp) - 4.218977835070959) < 1e-12
        lines.append(f"| {scene} | {mean(sp):.6f} | {part:.4f} | {spill:.4f} | {p95(wall):.4f} |")
    lines += ["", "注：三场景搜索预算各不相同；C3对照为事后同评分口径，非等预算消融。"]
    (OUT / "第7章_事实数值表.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"files": sorted(p.name for p in OUT.iterdir()),
                      "slice_sha256": hashlib.sha256((OUT / "第7章_公式与表.md").read_bytes()).hexdigest(),
                      "facts_sha256": hashlib.sha256((OUT / "第7章_事实数值表.md").read_bytes()).hexdigest()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
