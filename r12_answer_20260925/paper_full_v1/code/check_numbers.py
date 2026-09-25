"""全文数字溯源核对：正文每个数字都要能对上 冻结事实 / 逐例原始值 / 题面与算法常数 / 可复算的派生值。

输出 ../qa/数字溯源报告.md 与 ../qa/数字溯源.json。未匹配项逐条列出，供人工复核后修正或登记派生公式。
这是机器核对，不等于科学验收。
"""
from __future__ import annotations

import csv
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
R12 = ROOT.parent
F = json.loads((ROOT / "qa/facts.json").read_text(encoding="utf-8"))

# 题面、配置与算法源码中的常数（出处见右侧注释）
CONSTANTS = {
    524288, 131072, 60, 250, 1048576, 100, 1000, 500,      # 配置（题面附录B.4）
    2048, 128, 16, 512, 4, 8, 2, 6, 30, 40, 45, 120, 180,  # 算法参数（solve_round12/10/7/6、residency_bands）
    600, 1800, 1400, 400, 1470, 70, 62, 430, 1024, 1.03,   # 预算、配置格数与对照构成（verification.json）
    2026, 256, 320, 576, 1.001, 10000,                      # 年份、概念例（F13、F22）与普查阈值
}
SMALL_INT = 100         # 不超过此值的整数多为图数、配置数等计数，易与事实表误配，只统计不报警（已在会话中逐项人工核对）
SKIP_PATTERNS = [
    r"case_\d+", r"e\d{3,5}(?=（)", r"[图表式]\(?[A-Z]?\d+-\d+\)?", r"\d+\.\d+(?:\.\d+)*节", r"第\d+(?:\.\d+)*[章节]",
    r"^#{1,4} .*$", r"\[\d+(?:,\d+)*\]", r"F\d\d", r"L2-\d", r"[ABL]\d(?=\b|[^0-9.])", r"R12", r"C3", r"MTE[23]", r"L[12]\b",
    r"Python \d+\.\d+(?:\.\d+)?", r"Ubuntu \d+\.\d+", r"arXiv:\d+\.\d+", r"OSDI \d+", r"\d{4}, \d+\(\d+(?:-\d+)?\): \d+-\d+",
    r"\d+\(\d+(?:-\d+)?\)", r"\b(?:19|20)\d\d\b(?=[,.:：，年])", r"SHA256", r"sha256", r"Step[123]", r"step[123]", r"x\d",
    r"`[^`]*`", r"\\tag\{[^}]*\}", r"\d+ ?mm", r"600 ?dpi", r"(?<![0-9.])\d\.\d(?:\.\d)?(?=[、，节 |）)])",
    r"(?<=[A-Za-z_])\d+", r"\\mathrm\{[^}]*\}",
]
NUM = re.compile(r"(?<![0-9A-Za-z_.])[-−]?[1-9]\d{0,2}(?:,\d{3})+(?!\d)(?:\.\d+)?|(?<![0-9A-Za-z_.])[-−]?\d+(?:\.\d+)?")


def load_raw_values() -> set[int]:
    vals: set[int] = set()
    def add_csv(path, cols=None):
        with path.open(encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                for k, v in r.items():
                    if cols and k not in cols:
                        continue
                    try:
                        x = float(v)
                    except (TypeError, ValueError):
                        continue
                    if x.is_integer():
                        vals.add(int(x))
    add_csv(R12 / "figures_v3/delivery/data/F31.csv", {"T", "REF", "copy", "partition", "spill", "C3_T", "C3_copy"})
    add_csv(R12 / "publication/tables/Q3_per_case.csv")
    add_csv(R12 / "figures_v3/delivery/data/F19.csv")
    add_csv(R12 / "figures_v3/delivery/data/F27.csv")
    add_csv(R12 / "figures_v3/delivery/data/F09.csv", {"tasks", "max_ops"})
    add_csv(R12 / "figures_v3/delivery/data/F03.csv")
    add_csv(R12 / "publication/sources/closeout/results/budget_exceptions.csv", {"makespan"})
    return vals


def derived_values() -> dict[str, float]:
    """人工确认过口径、由事实表可复算的派生值（名称 → 数值）。"""
    d = {
        "L2读带宽/DDR带宽 250/60": 250 / 60,
        "最大/最小操作数": F["graphs.ops_span_ratio"],
        "1800秒/场景A五核墙钟中位": F["case_087.budget_ratio_vs_A5_median"],
        "场景A边际增量 2→3": F["A3.mean_speedup"] - F["A2.mean_speedup"],
        "场景A边际增量 3→4": F["A4.mean_speedup"] - F["A3.mean_speedup"],
        "场景A边际增量 4→5": F["A5.mean_speedup"] - F["A4.mean_speedup"],
        "五核配置比减1（%）": (F["Q3.k5.same_plan_mean"] - 1) * 100,
        "case_062 A2/A4新增COPY之比": F["case_062.A2_A4_copy_ratio"],
        "五核L2 hw>1.04 的图数": F["Q3.k5.hw_gt_1_04"],
        "case_073 e2428 占用净降 KiB": (986880 - 762624) / 1024,
        "case_073 e2428 占用净降 bytes": 986880 - 762624,
        "控制链占最终值比例（%）": F["B5.stage.control_share_pct"],
        "插入与微批合计（%）": 100 - F["B5.stage.control_share_pct"],
        "C3五核A加速比": F["A5.C3_speedup_mean"],
        "case_062最忙核心Task数(2核)": -(-F["case_062.A2.tasks"] // 2),
        "场景B→A五核边界降幅（%）": (1 - F["B5.mean_partition_MiB"] / F["A5.mean_partition_MiB"]) * 100,
        "五核L2配置比中位与1之差": F["Q3.k5.same_plan_median"] - 1,
    }
    for k in range(1, 6):
        d[f"选优比-配置比 k{k}"] = F[f"Q3.k{k}.sel_minus_hw"]
    return d


def displayed_match(token: str, value: float) -> bool:
    if "." in token:
        dec = len(token.split(".")[1])
        return abs(round(value, dec) - float(token)) < 10 ** (-dec) / 2 + 1e-12 or f"{value:.{dec}f}" == token
    return abs(value - float(token)) < 0.5 and float(token) == round(value)


def main() -> None:
    text = (ROOT / "全文_R12论文_v1.md").read_text(encoding="utf-8")
    body = text.split("# 参考文献")[0]           # 参考文献与附录逐例表单独处理
    appendix = text.split("# 附录", 1)[1] if "# 附录" in text else ""
    floats = [(k, float(v)) for k, v in F.items() if isinstance(v, (int, float)) and not isinstance(v, bool)]
    raw = load_raw_values()
    derived = derived_values()
    report = defaultdict(list)
    counts = Counter()
    chapter = "摘要"
    for line in body.split("\n"):
        if line.startswith("# "):
            chapter = line[2:].strip()
            continue
        work = line
        for pat in SKIP_PATTERNS:
            work = re.sub(pat, " ", work, flags=re.M)
        for m in NUM.finditer(work):
            tok = m.group(0).replace("−", "-")
            plain = tok.replace(",", "")
            after = work[m.end():m.end() + 1]
            pct = after == "%"
            try:
                val = float(plain)
            except ValueError:
                continue
            counts["tokens"] += 1
            if val.is_integer() and abs(val) <= SMALL_INT and "." not in plain:
                counts["small_int"] += 1
                continue
            if val in CONSTANTS and not pct:
                counts["constant"] += 1
                continue
            hit = None
            for k, v in floats:
                if displayed_match(plain, v) or (pct and displayed_match(plain, v * 100)) or (pct and displayed_match(plain, v)):
                    hit = k
                    break
            if hit is None and "." not in plain and int(val) in raw:
                hit = "逐例原始值"
            if hit is None:
                for k, v in derived.items():
                    if displayed_match(plain, v):
                        hit = "派生:" + k
                        break
            if hit is None:
                report[chapter].append({"token": tok + ("%" if pct else ""), "context": line.strip()[:160]})
                counts["unmatched"] += 1
            elif hit.startswith("派生"):
                counts["derived"] += 1
            elif hit == "逐例原始值":
                counts["raw"] += 1
            else:
                counts["fact"] += 1
    # 附录逐例表：逐格回查冻结CSV（gen_tables.py 已断言与冻结CSV一致，这里只统计行数）
    counts["appendix_rows"] = sum(1 for l in appendix.split("\n") if l.startswith("| case_"))
    out = {"counts": dict(counts), "unmatched": report}
    (ROOT / "qa/数字溯源.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    lines = ["# 全文数字溯源报告（check_numbers.py 自动生成）", "",
             "对象：`全文_R12论文_v1.md` 正文（摘要至第10章）。附录逐例表由 `gen_tables.py` 生成并已逐格断言与冻结CSV一致。", "",
             "| 类别 | 个数 |", "|---|---:|"]
    names = {"tokens": "数字总数", "fact": "对上事实表（冻结数据重算）", "raw": "对上逐例原始值", "derived": "对上可复算派生值",
             "constant": "题面/配置/算法常数与概念例数值", "small_int": "≤100的计数类整数（未逐条报警）", "unmatched": "未匹配（需人工复核）",
             "appendix_rows": "附录逐例表行数"}
    for k in ("tokens", "fact", "raw", "derived", "constant", "small_int", "unmatched", "appendix_rows"):
        lines.append(f"| {names[k]} | {counts.get(k, 0)} |")
    lines += ["", "## 可复算派生值（已登记口径）", "", "| 派生值 | 数值 |", "|---|---:|"]
    lines += [f"| {k} | {v:.6g} |" for k, v in derived.items()]
    lines += ["", "## 未匹配项", ""]
    if not report:
        lines.append("无。")
    for ch, items in report.items():
        lines.append(f"### {ch}")
        lines += [f"- `{it['token']}` —— {it['context']}" for it in items]
        lines.append("")
    (ROOT / "qa/数字溯源报告.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(dict(counts), ensure_ascii=False))
    for ch, items in report.items():
        for it in items:
            print(ch[:12], it["token"], "|", it["context"][:110])


if __name__ == "__main__":
    main()
