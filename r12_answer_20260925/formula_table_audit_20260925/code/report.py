# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Compose the audit report + delivery zip from frozen outputs. Run once."""
import csv
import hashlib
import json
import statistics
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERIFIED = [
    ("C24_B04", "p10, p29 渲染目视", "连字符公式号 (3-1)…(3-8)、(4-1)…(4-13) 确认；脚本26条与缓存逐条一致"),
    ("C25_B01", "p11 渲染目视", "“(1)(2)(3)”为列表序号而非公式；0公式结论成立"),
    ("C25_A04", "p28 渲染目视", "表内 O(1.39)/O(3.30) 为数值；脚本识别30条 (3-1)…(5-8) 真公式号"),
    ("C25_A01", "p20 渲染目视", "公式内联书写、无右缘编号；0公式结论成立"),
    ("C25_D01", "p18 缓存文本核验", "展示公式无编号；渲染触发MuPDF堆崩溃故改用文本；结论一致"),
    ("T_WELDER", "p5/p6 渲染目视", "数学内联于正文，无编号展示公式"),
    ("T_LADDER", "p5/p6 渲染目视", "“(1)”为图轴批量参数(ResNet (1))，非公式号；0结论成立"),
    ("T_SYNCOPATE", "p5/p8 渲染目视", "图为动机实验与代码清单；无编号展示公式"),
    ("J_PIMCOMP", "p6/p7 渲染目视", "内联数学(HWP=IOK²)，无编号展示公式；“(4)”为列表项"),
]


def sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main() -> None:
    rows = list(csv.DictReader((ROOT / "out/per_paper.csv").open(encoding="utf-8-sig")))
    summary = json.loads((ROOT / "out/SUMMARY.json").read_bytes())
    protected = json.loads((ROOT / "PROTECTED.json").read_bytes())
    for path, expected in protected.items():
        assert sha(Path(path)) == expected, path
    comp = [r for r in rows if r["group"] == "competition"]
    zero = [r["id"] for r in comp if int(r["eq_main"]) == 0]
    eq_all = sorted(int(r["eq_main"]) for r in comp)
    tab_all = sorted(int(r["tables_main"]) for r in comp)
    lines = ["# 公式与表格统计报告（2026-09-25）", "",
             "统计对象：2024/2025竞赛参考库45篇 + 期刊研究3篇 + 期刊综述1篇 + OSDI顶会5篇，共54份PDF（3847页）。",
             "主指标：正文唯一编号公式单元（多行同号计1）；表格按唯一表号（续表去重）。行内公式与未编号展示公式不计数。", ""]
    lines += ["## 一、分组统计（正文）", "",
              "| 组 | n | 公式 min/q1/中位/q3/max | 表中位(min–max) | 公式密度中位（每10正文页） |",
              "|---|---|---|---|---|"]
    for key, name in (("competition_2024", "竞赛2024"), ("competition_2025", "竞赛2025"),
                      ("all_competition", "竞赛合并"), ("journal_research", "期刊研究"),
                      ("journal_survey", "期刊综述"), ("conference", "OSD顶会")):
        item = summary["summary"][key]
        eq = item["eq_main"]
        quant = f"{eq['min']}/{eq.get('q1', '-')}/{eq['median']}/{eq.get('q3', '-')}/{eq['max']}"
        table = item["tables_main"]
        density = item.get("eq_per_10_body_pages", {})
        lines.append(f"| {name} | {item['n']} | {quant} | {table['median']}（{table['min']}–{table['max']}） | {density.get('median', '-')} |")
    lines += ["", f"45篇竞赛论文正文编号公式中位数 **{statistics.median(eq_all):.0f}**（min {eq_all[0]}、max {eq_all[-1]}）；"
              f"表中位数 **{statistics.median(tab_all):.0f}**（min {tab_all[0]}、max {tab_all[-1]}）。", "",
              f"7篇竞赛论文正文编号公式为0（{', '.join(zero)}）；目视确认其公式以内联或未编号展示方式书写，属于真实风格差异而非漏检。", "",
              "## 二、与顶刊/顶会的对比观察", "",
              "- 系统与体系结构方向的期刊/顶会论文几乎不使用编号展示公式（中位0–3条），数学以行内、伪代码、图内标注表达；",
              "- 竞赛优秀论文（尤其2025年F题、A题）编号公式中位可达67，密度约9–10条/10页，是竞赛文体的显著特征；",
              "- 两类载体不可互相套用数量；竞赛稿应参照竞赛分布，同时保留公式与推导的实现对应关系。", "",
              "## 三、人工核验记录", ""]
    for pid, where, note in VERIFIED:
        lines.append(f"- **{pid}**（{where}）：{note}")
    lines += ["", "## 四、口径、限定与告警", "",
              "- 计数规则：右缘独立标签（严格）＋行尾连字符标签（粘连）；`(1990-2005)`式年份、`O(1.39)`式表值、图内`ResNet (1)`式参数一律排除；",
              "- 未统计：行内公式、无编号展示公式、图片化公式；因此本统计是编号公式下界而非全部数学表达；",
              "- 边界：按“目录+3页”防护后的首个“参考文献/附录”切分；T_WELDER、T_SYNCOPATE未检出参考文献标题，按全文计数；",
              "- 表格重复号：14篇存在跨页续表或重号（如C25_F02的4.8–4.12），已按唯一表号去重；",
              "- 英语两列论文出现少量疑似图内“(1)(2)”误报（3篇、每篇1–2条），已在报告中标注，不进入竞赛统计；",
              "- 本报告为单会话作者侧统计，不是独立审稿；参考库获奖身份未逐篇认证。", "",
              "## 五、R12三问的公式/表格规划建议（不改变主解，仅指导成文）", "",
              "竞赛合并中位≈52条正文编号公式、11张表。结合R12现有20个展示公式块（Q1 7、Q2 5、Q3 8）与真实模型职责，建议：", "",
              "| 问 | 编号公式建议 | 候选清单（来源=冻结解答） | 表格建议 |",
              "|---|---|---|---|",
              "| Q1 | 14–18 | 方案变量P=(g,a,π)；目标与字典序；释放时刻r_s复现；容量约束；成本分解C_solve；逐例比值均值定义；边界≤(r+1)b；Treap插入不等式；下界剪枝条件；复杂度说明 | 4–5（主结果、COPY分解、预算例外、逐例附录截取） |",
              "| Q2 | 10–14 | T_B目标；B同步不等式；边界COPY计数；核心归属不变式；partition不变等式；微批窗口/候选上限；阶段均值定义；预算表 | 3–4（主结果、阶段配对、Spill集中度、案例） |",
              "| Q3 | 10–14 | FIFO容量H(t)；命中率h_i；带宽池约束；理想延迟；R_hw与R_select定义及分解等式；均值定义；退化清单 | 4–5（配置比表、选优比表、逐例附录、退化表） |",
              "| 合计 | **34–46** | 每问先给1–2条“回答题目的核心式”，推导细节放正文或附录，避免无编号公式堆叠 | **11–14** |", "",
              "落地要求（按现行工作流）：公式用原生OMML/LaTeX并连续编号、符号首现定义、矩阵维度与单位清楚、正斜体统一、长式aligned分行；表格原生三线表（顶底1.5pt、表头0.5pt、无竖线、无底纹）、表题在上、注明n/单位/误差/缺失含义。", "",
              "## 六、产出文件", "",
              "| 文件 | 内容 |", "|---|---|",
              "| out/per_paper.csv | 54篇逐篇：页数、正文边界、公式数、表数、异常标记 |",
              "| out/candidates.csv | 全部公式/表号候选（页码、x位置、原文片段） |",
              "| out/SUMMARY.json | 分组统计与告警明细 |",
              "| code/pdf_rules.py、test_pdf_rules.py | 计数规则与12项单元测试 |",
              "| code/inventory.py、extract.py、count.py | 输入清单、缓存提取、精化计数 |",
              "| refs/、INPUTS.json | 外部原文与逐份SHA256（版权归原出版方） |", "",
              "统计脚本与缓存不构成科学验收；引用外部论文时按各自出版方要求标注。"]
    report = ROOT / "REPORT.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    files = [ROOT / "REPORT.md", ROOT / "PLAN.md", ROOT / "INPUTS.json",
             ROOT / "out/per_paper.csv", ROOT / "out/candidates.csv", ROOT / "out/SUMMARY.json"]
    files += sorted((ROOT / "code").glob("*.py"))
    archive = ROOT / "formula_table_stats_20260925.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for path in files:
            z.write(path, path.relative_to(ROOT).as_posix())
    hashes = {p.relative_to(ROOT).as_posix(): sha(p) for p in files}
    receipt = {"status": "FORMULA_TABLE_STATS_DELIVERED_AUTHOR_CHECKED",
               "papers": len(rows), "pages_extracted": 3847, "zero_equation_competition_papers": zero,
               "zip_sha256": sha(archive), "files": hashes,
               "protected_r12_files_unchanged": len(protected), "independent_review": "NOT_PERFORMED"}
    (ROOT / "RECEIPT.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in receipt.items() if k != "files"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
