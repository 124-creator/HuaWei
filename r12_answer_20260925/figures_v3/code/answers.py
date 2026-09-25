# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Build losslessly traceable Markdown answer copies with figures. Run: answers.py."""
import hashlib
import json
import re
import shutil
from pathlib import Path

from answer_map import PLACEMENTS, PRIMARY
from captions import conclusions
from specs import INDEX, SPECS
from version_guard import check

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT.parent / "publication"
OLD_Q3_CAPTION = "左图是同一P_B在两配置下相对REF的平均性能；"
NEW_Q3_CAPTION = "左图区分无L2的P_B、有L2的同一P_B和有L2另选P_L，三条曲线均相对同一REF；"


def insert_block(text: str, prefix: str, block: str) -> str:
    matches = [line for line in text.splitlines() if line.startswith(prefix)]
    assert len(matches) == 1, (prefix, len(matches))
    return text.replace(matches[0], matches[0] + "\n\n" + block, 1)


def wrap_block(key: str, body: str) -> str:
    return f"<!-- V3_FIGURE_BEGIN {key} -->\n{body}\n<!-- V3_FIGURE_END -->"


def restore_source(q: str, text: str) -> str:
    text = re.sub(r"\n\n<!-- V3_FIGURE_BEGIN [^>]+ -->\n.*?\n<!-- V3_FIGURE_END -->", "", text, flags=re.S)
    old = {"Q1": "q1_curve", "Q2": "q2_curve", "Q3": "q3_configuration"}[q]
    text = text.replace(f"../figures/{PRIMARY[q]}.", f"../figures/{old}.")
    text = text.replace("../README.md", "../阅读说明.md")
    return text.replace(NEW_Q3_CAPTION, OLD_Q3_CAPTION)


def verify_answers() -> None:
    records = []
    for q in PRIMARY:
        source_path = SOURCE / "solutions" / f"{q}.md"
        source = source_path.read_text(encoding="utf-8")
        output = ROOT / "answers" / f"{q}.md"
        text = output.read_text(encoding="utf-8")
        assert restore_source(q, text) == source, (q, "source content lost or changed")
        assert re.findall(r"\$\$(.*?)\$\$", text, re.S) == re.findall(r"\$\$(.*?)\$\$", source, re.S)
        linked = re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", text)
        for target in linked:
            if target.startswith(("https://", "http://", "#")):
                continue
            dest = (output.parent / target.split("#")[0]).resolve()
            assert dest.is_relative_to(ROOT) and dest.is_file(), (q, target)
        ids = re.findall(r"!\[[^\]]*\]\(../figures/(F\d+)\.png\)", text)
        expected = [PRIMARY[q]] + [key for item in PLACEMENTS if item[0] == q for key in item[2]]
        assert sorted(ids) == sorted(expected) and len(ids) == len(set(ids))
        records.append({"question": q, "original_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
                        "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(), "main_figures": ids,
                        "original_text_reversible": True, "display_equations_unchanged": True, "links_checked": len(linked)})
    (ROOT / "qa").mkdir(exist_ok=True)
    with (ROOT / "qa/answer_check.json").open("w", encoding="utf-8") as stream:
        json.dump({"status": "TEXT_AND_LINK_CHECKS_PASS", "records": records,
                   "scope": "Markdown integration only; not final full-paper typesetting"}, stream, ensure_ascii=False, indent=2)
    print(json.dumps(records, ensure_ascii=False))


def main() -> None:
    check()
    (ROOT / "answers").mkdir(exist_ok=True)
    (ROOT / "tables").mkdir(exist_ok=True)
    for path in (SOURCE / "tables").glob("*.csv"):
        shutil.copyfile(path, ROOT / "tables" / path.name)
    reading = conclusions()
    mapping = []
    for q in PRIMARY:
        text = (SOURCE / "solutions" / f"{q}.md").read_text(encoding="utf-8")
        old = {"Q1": "q1_curve", "Q2": "q2_curve", "Q3": "q3_configuration"}[q]
        text = text.replace(f"../figures/{old}.", f"../figures/{PRIMARY[q]}.")
        text = text.replace("../阅读说明.md", "../README.md")
        if q == "Q3":
            assert text.count(OLD_Q3_CAPTION) == 1
            text = text.replace(OLD_Q3_CAPTION, NEW_Q3_CAPTION)
        intro = "图文整合版v3。原模型、公式、算法、数值与局限完整保留；这里只更新图引用并补充图解。图中概念例与真实实验明确区分，算法流程仍由文字步骤表达。"
        text = insert_block(text, "# ", wrap_block(f"{q}_intro", intro))
        for i, (question, anchor, keys, note) in enumerate(PLACEMENTS):
            if question != q:
                continue
            blocks = [note]
            for key in keys:
                spec = INDEX[key]
                kind = "结构示意，非实测" if spec.kind == "schematic" else "冻结数据证据"
                blocks += [f"![{key} {spec.title}](../figures/{key}.png)",
                           f"**图{key}｜{spec.title}（{kind}）**", reading[key],
                           f"[矢量PDF](../figures/{key}.pdf) · [作图数据](../data/{key}.csv)"]
                mapping.append((key, q, anchor))
            text = insert_block(text, anchor, wrap_block(f"{q}_{i}", "\n\n".join(blocks)))
        with (ROOT / "answers" / f"{q}.md").open("w", encoding="utf-8") as stream:
            stream.write(text)
        mapping.append((PRIMARY[q], q, "原主结果曲线位置"))
    placed = {key: (q, anchor) for key, q, anchor in mapping}
    lines = ["# 图文对应索引", "", "正文使用23张图；其余11张为补充证据，不为凑数重复塞入正文。", "",
             "| 图号 | 内容 | 阅读位置 |", "|---|---|---|"]
    for spec in SPECS:
        location = f"[{placed[spec.id][0]}图文版](answers/{placed[spec.id][0]}.md)，{placed[spec.id][1]}" if spec.id in placed else "[完整图件说明](图件说明.md)中的补充图"
        lines.append(f"| {spec.id} | {spec.title} | {location} |")
    with (ROOT / "图文映射.md").open("w", encoding="utf-8") as stream:
        stream.write("\n".join(lines) + "\n")
    verify_answers()


if __name__ == "__main__":
    main()
