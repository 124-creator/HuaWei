# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Build 公式与三线表工作稿.md from frozen closeout data. Deterministic; no solver calls."""
import csv
import hashlib
import json
import math
import re
import sys
from pathlib import Path

BASE = Path(r"E:/HWCupA2026/derived/r12_answer_20260925")
ROOT = Path(__file__).resolve().parents[1]
CO = BASE / "publication/sources/closeout/results"
C3 = BASE / "publication/sources/C3_official_cells.csv"
DATASET = BASE / "figures_v3/dataset.json"
DOC = ROOT / "公式与三线表工作稿.md"


def sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(path.open(encoding="utf-8-sig")))


def f6(x: float) -> str:
    return f"{x:.6f}"


def f4(x: float) -> str:
    return f"{x:.4f}"


def pct4(x: float) -> str:
    return f"{x * 100:.4f}%"


def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs)


def median(xs: list[float]) -> float:
    data = sorted(xs)
    mid = len(data) // 2
    return data[mid] if len(data) % 2 else (data[mid - 1] + data[mid]) / 2


def p95(xs: list[float]) -> float:
    data = sorted(xs)
    return data[math.ceil(0.95 * len(data)) - 1]


def table(header: list[str], rows: list[list[str]], caption: str, note: str) -> str:
    spec = "|" + "|".join(["---"] + ["---:"] * (len(header) - 1)) + "|"
    body = "\n".join("| " + " | ".join([r[0], *r[1:]]) + " |" for r in rows)
    return f"**{caption}**\n\n| " + " | ".join(header) + " |\n" + spec + "\n" + body + f"\n\n*注：{note}*\n"


def scene_rows(sel: list[dict[str, str]], scene: str, cores: str) -> list[dict[str, str]]:
    return [r for r in sel if r["scene"] == scene and r["cores"] == cores]


def main() -> None:
    sel = load(CO / "selected_per_case.csv")
    pair = load(CO / "q3_paired_per_case.csv")
    pair_sum = {r["cores"]: r for r in load(CO / "q3_paired_summary.csv")}
    budget = load(CO / "budget_exceptions.csv")
    c3cells = load(C3)
    stages = json.loads(DATASET.read_bytes())["stages"]
    t: dict[str, str] = {}

    def main_rows(scene: str, ks: list[str]) -> tuple[list[list[str]], dict[str, float]]:
        rows, checks = [], {}
        for k in ks:
            g = scene_rows(sel, scene, k)
            sp = [float(r["speedup"]) for r in g]
            add = mean([float(r["added_copy_bytes"]) for r in g]) / 1048576
            part = mean([float(r["partition_added_copy_bytes"]) for r in g]) / 1048576
            spill = mean([float(r["spill_added_copy_bytes"]) for r in g]) / 1048576
            wall = [float(r["wall_seconds"]) for r in g]
            checks[k] = mean(sp)
            rows.append([k, f6(mean(sp)), f6(median(sp)), f6(min(sp)), f4(add), f4(part), f4(spill), f4(median(wall)), f4(p95(wall))])
        return rows, checks

    header_main = ["核数", "平均加速比", "中位加速比", "最小加速比", "均值新增COPY/MiB", "其中边界/MiB", "其中Spill/MiB", "墙钟中位/s", "墙钟P95/s"]
    arows, achk = main_rows("A", ["2", "3", "4", "5"])
    assert abs(achk["5"] - 3.7432824388023844) < 1e-12
    t["q1_main"] = table(header_main, arows, "表1-1 场景A逐核主结果（每格100图）",
                         "加速比为逐图比值算术平均；P95为经验最近秩；C3对照不是等搜索预算消融。")
    rows = []
    for k in ["2", "3", "4", "5"]:
        g = scene_rows(sel, "A", k)
        c3 = {r["case_id"]: r for r in c3cells if r["problem"] == "A" and r["k"] == k}
        rat = [float(c3[r["case"]]["makespan_cycles"]) / float(r["makespan"]) for r in g]
        red = [1 - float(r["makespan"]) / float(c3[r["case"]]["makespan_cycles"]) for r in g]
        w = sum(float(r["makespan"]) < float(c3[r["case"]]["makespan_cycles"]) for r in g)
        tie = sum(float(r["makespan"]) == float(c3[r["case"]]["makespan_cycles"]) for r in g)
        fmc = sum(float(r["makespan"]) < float(c3[r["case"]]["makespan_cycles"]) and float(r["added_copy_bytes"]) > float(c3[r["case"]]["data_movement_bytes"]) for r in g)
        if k == "5":
            assert abs(mean(rat) - 2.053092817570483) < 1e-12 and abs(mean(red) - 0.4347602292388654) < 1e-12 and (w, tie, len(g) - w - tie, fmc) == (93, 5, 2, 2)
        rows.append([k, f6(mean(rat)), pct4(mean(red)), f"{w} / {tie} / {len(g) - w - tie}", str(fmc)])
    t["q1_c3"] = table(["核数", "加速比均值 T_C3/T_R12", "逐图降幅均值", "更快 / 持平 / 更慢", "更快但COPY更高"], rows,
                       "表1-2 场景A相对C3的逐例对照（每格100图）",
                       "C3为同输入、同评分口径的事后对照；时间为官方cycles，非求解墙钟。")
    rows = []
    for r in sorted(budget, key=lambda x: x["cores"]):
        assert r["case"] == "case_087" and float(r["budget_seconds"]) == 1800.0
        rows.append([r["case"], f"A{r['cores']}", "600 s 首次无成功", f"{int(float(r['budget_seconds']))} s", f4(float(r["wall_seconds"])), r["makespan"]])
    t["q1_budget"] = table(["用例", "场景/核数", "首次预算", "补跑预算", "补跑墙钟/s", "Makespan/cycles"], rows,
                           "表1-3 预算例外完整记录",
                           "首次600秒失败结果保留；仅本组使用1800秒补跑；不称历史零失败。")
    a5 = {r["case"]: r for r in scene_rows(sel, "A", "5")}
    rows = [[c, a5[c]["makespan"], a5[c]["added_copy_bytes"]] for c in ("case_002", "case_005")]
    assert rows == [["case_002", "58180", "82944"], ["case_005", "69060", "2483610"]]
    t["q1_tradeoff"] = table(["用例（A5）", "Makespan/cycles", "新增COPY/bytes"], rows,
                             "表1-4 并行—搬运权衡案例",
                             "展示终点值差异；两例均比C3更快且COPY更高，不构成单因素消融。")
    brows, bchk = main_rows("B", ["1", "2", "3", "4", "5"])
    assert abs(bchk["1"] - 1.0613657846081295) < 1e-12 and abs(bchk["5"] - 4.131077430492359) < 1e-12
    t["q2_main"] = table(header_main, brows, "表2-1 场景B逐核主结果（每格100图）",
                         "一核行为优化B1实测；标准参考曲线一核按定义取1，二者不可混用；其余口径同表1-1。")
    g5 = scene_rows(sel, "B", "5")
    rows = [["平均新增COPY/MiB", f4(mean([float(r["added_copy_bytes"]) for r in g5]) / 1048576)],
            ["其中边界/MiB", f4(mean([float(r["partition_added_copy_bytes"]) for r in g5]) / 1048576)],
            ["其中Spill/MiB", f4(mean([float(r["spill_added_copy_bytes"]) for r in g5]) / 1048576)],
            ["请求墙钟中位/s", f4(median([float(r["wall_seconds"]) for r in g5]))],
            ["请求墙钟P95/s", f4(p95([float(r["wall_seconds"]) for r in g5]))],
            ["请求墙钟最大/s", f4(max(float(r["wall_seconds"]) for r in g5))]]
    assert rows[0][1] == "8.2173" and rows[2][1] == "2.7062"
    t["q2_copy5"] = table(["五核B指标", "数值"], rows, "表2-2 五核B的COPY分解与请求成本",
                          "官方模拟前COPY计账；墙钟含构造、评价与I/O，不是硬实时承诺。")
    means = [mean([r["REF"] / r[st] for r in stages]) for st in ("control", "indexed", "full")]
    assert abs(means[0] - 4.073197919292522) < 1e-12 and abs(means[2] - 4.131077430492359) < 1e-12
    count = [sum(r["indexed"] < r["control"] for r in stages), sum(r["full"] < r["indexed"] for r in stages)]
    assert count == [12, 2]
    rows = [[st, f6(m), f"{c} / 100"] for st, m, c in zip(("控制", "插入后", "微批后"), means, [None, count[0], count[1]])]
    rows[0][2] = "（基准）"
    rows[0][1] = f6(means[0])
    for r in stages:
        if r["case"] in ("case_067", "case_073") and r["full"] < r["indexed"]:
            rows.append([f"{r['case']}（明细）", f"{r['control']:,} → {r['indexed']:,} → {r['full']:,}", "—"])
    t["q2_stages"] = table(["阶段", "相对REF平均加速比 / 原始cycles", "较前阶段严格改善"], rows,
                           "表2-3 五核B同次请求的三阶段结果",
                           "阶段共享同一总软预算，不是等预算独立消融；未改善含相同、未触发或未完成。")
    c73 = next(r for r in g5 if r["case"] == "case_073")
    rows = [["Makespan/cycles", c73["makespan"]], ["边界新增/bytes", c73["partition_added_copy_bytes"]], ["Spill新增/bytes", c73["spill_added_copy_bytes"]]]
    assert rows[0][1] == "2034983" and rows[1][1] == "21712384" and rows[2][1] == "15489024"
    t["q2_case073"] = table(["case_073（B5）", "数值"], rows, "表2-4 开发诊断案例终点值",
                            "仅作机制动机展示，不单独证明微批因果收益。")
    if len(sys.argv) > 1 and sys.argv[1] == "tables-only":
        print(json.dumps(sorted(t), ensure_ascii=False))
        return
    p5 = [r for r in pair if r["cores"] == "5"]
    same = [float(r["same_plan_B_over_L2"]) for r in p5]
    assert abs(mean(same) - 1.0167659521121053) < 1e-12 and abs(median(same) - float(pair_sum["5"]["same_plan_median"])) < 1e-12
    rows = []
    for k in ["1", "2", "3", "4", "5"]:
        g = [r for r in pair if r["cores"] == k]
        s = [float(r["same_plan_B_over_L2"]) for r in g]
        sel_ = [float(r["separate_selection_B_over_L2"]) for r in g]
        imp = sum(x > 1 for x in s)
        deg = sum(x < 1 for x in s)
        rows.append([k, f6(mean(s)), f6(median(s)), f6(mean(sel_)), f"{imp} / {len(g) - imp - deg} / {deg}"])
    assert rows[4][1] == "1.016766" and rows[4][3] == "1.027400"
    t["q3_ratios"] = table(["核数", "同方案配置比均值", "同方案配置比中位", "分别选优比均值", "改善 / 相同 / 退化"], rows,
                           "表3-1 同核数L2配置比与选优比（每行100图）",
                           "配置比与选优比口径不同，不可互换；一核配置比为实测值。")
    rows = []
    for case, k in (("case_073", "5"), ("case_026", "5")):
        r = next(x for x in pair if x["case"] == case and x["cores"] == k)
        rows.append([f"{case}（{k}核）", r["B_makespan"], r["L2_same_B_plan_makespan"], r["L2_selected_makespan"]])
    assert rows[0][1:] == ["2034983", "1806253", "1805392"] and rows[1][1:] == ["33518", "33721", "33721"]
    t["q3_cases"] = table(["用例", "无L2 P_B/cycles", "有L2 同一P_B/cycles", "L2独立选优/cycles"], rows,
                          "表3-2 五核异质性案例",
                          "case_026为同方案配置比最小的五核用例；案例不代替全100图。")
    deg = sorted([r for r in pair if float(r["same_plan_B_over_L2"]) < 1], key=lambda r: (int(r["cores"]), r["case"]))
    assert len(deg) == 8
    rows = []
    for r in deg:
        hit = float(r["L2_same_plan_hit_bytes"]) / (float(r["L2_same_plan_hit_bytes"]) + float(r["L2_same_plan_miss_bytes"]))
        rows.append([r["case"], r["cores"], f6(float(r["same_plan_B_over_L2"])), pct4(hit)])
    t["q3_degraded"] = table(["用例", "核数", "同方案配置比", "同方案命中字节率"], rows,
                             "表3-3 全部同方案L2退化记录（8条）",
                             "低于1表示退化；只确认事实，不把未经核实的机制写成原因。")
    g = scene_rows(sel, "L2", "5")
    wall = sorted(float(r["wall_seconds"]) for r in g)
    rows = [["平均新增COPY/MiB", f4(mean([float(r["added_copy_bytes"]) for r in g]) / 1048576)],
            ["其中边界/MiB", f4(mean([float(r["partition_added_copy_bytes"]) for r in g]) / 1048576)],
            ["其中Spill/MiB", f4(mean([float(r["spill_added_copy_bytes"]) for r in g]) / 1048576)],
            ["请求墙钟中位/s", f4(median(wall))], ["请求墙钟P95/s", f4(p95(wall))], ["请求墙钟最大/s", f4(wall[-1])]]
    assert rows[0][1] == "9.4032" and rows[2][1] == "3.5565"
    t["q3_cost5"] = table(["五核L2独立选优指标", "数值"], rows, "表3-4 五核L2独立选优的COPY与请求成本",
                          "更早完成的COPY会改变后续发射与FIFO状态；COPY计账不等于命中后物理DDR净流量。")
    hit5 = [float(r["L2_same_plan_hit_bytes"]) / (float(r["L2_same_plan_hit_bytes"]) + float(r["L2_same_plan_miss_bytes"])) for r in p5]
    rows = [["同方案配置比（均值 / 中位）", f"{f6(mean(same))} / {f6(median(same))}"],
            ["分别选优比（均值）", f6(mean([float(r['separate_selection_B_over_L2']) for r in p5]))],
            ["固定P_B，L2相对REF均值", f6(mean([float(r['fixed_singlecore']) / float(r['L2_same_B_plan_makespan']) for r in p5]))],
            ["L2独立选优相对REF均值", f6(mean([float(r['speedup']) for r in scene_rows(sel, 'L2', '5')]))],
            ["逐图命中字节率均值", pct4(mean(hit5))],
            ["五核不同最终方案对数", pair_sum["5"]["different_final_plan_count"] + " / 100"]]
    assert rows[3][1] == "4.218978" and rows[4][1] == "23.4614%"
    t["q3_summary"] = table(["五核口径", "数值"], rows, "表3-5 五核结果口径摘要",
                            "两条性能口径分开读取；不能用均值曲线相除替代逐图比值平均。")
    parts = []
    for name in ("equations_q1.md", "equations_q2.md", "equations_q3.md"):
        chunk = (ROOT / "content" / name).read_text(encoding="utf-8")
        chunk = re.sub(r"^# (问题)", r"## \1", chunk, count=1, flags=re.M)
        chunk = re.sub(r"^## (三线表)", r"### \1", chunk, count=1, flags=re.M)
        parts.append(chunk)
    text = "\n\n".join(parts)
    for key, block in t.items():
        text = text.replace("{{TABLE:" + key + "}}", block)
    assert "{{TABLE:" not in text
    head = ["# R12 三问公式与三线表工作稿（v1）", "",
            "用户口径：所有公式来自冻结解答与真实代码，所有数值由冻结CSV重算生成；本稿独立成文，融合时按终稿模板重排编号。",
            "共38条编号公式与13张三线表。表格以Markdown给出，融合到Word/LaTeX时改为三线表（顶底1.5pt、表头0.5pt、无竖线、无底纹），表题在表上。", ""]
    tail = ["", "## 口径与限定", "",
            "- 生成方式：`code/build_doc.py` 从closeout冻结表重算；P95为经验最近秩；1 MiB=1048576 bytes。",
            "- 来源哈希见 `SOURCES.json`；本稿不是科学验收，融合后仍需按工作流检查OMML、三线表线宽与逐页版式。"]
    doc = "\n".join(head) + text + "\n".join(tail)
    DOC.write_text(doc, encoding="utf-8")
    sources = {}
    for p in (CO / "selected_per_case.csv", CO / "q3_paired_per_case.csv", CO / "q3_paired_summary.csv",
              CO / "budget_exceptions.csv", C3, DATASET):
        sources[p.relative_to(BASE).as_posix()] = sha(p)
    for p in sorted((ROOT / "content").glob("*.md")):
        sources[f"content/{p.name}"] = sha(p)
    (ROOT / "SOURCES.json").write_text(json.dumps(sources, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"doc": str(DOC), "tables": len(t), "source_files": len(sources), "doc_sha256": sha(DOC)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
