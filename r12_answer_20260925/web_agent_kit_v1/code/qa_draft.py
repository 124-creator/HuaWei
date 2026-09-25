# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""QA a web-agent chapter draft against its facts table.

Usage: python qa_draft.py <draft_path> <facts_path> <prefix> [out_dir]
Machine check only; not scientific acceptance.
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

KIT = Path(r"E:/HWCupA2026/derived/r12_answer_20260925/web_agent_kit_v1")
TOKEN = re.compile(r"\d+(?:\.\d+)?(?:%|倍)?")
BANNED = ["生长子图", "强连通", "向上秩", "列表调度", "启发式投影", "簇足迹", "双上界", "预实验对照"]
TEMPLATE_NUMS = ["0.852", "1.3148", "1.7174", "2.0001", "1.7839", "2.4406", "2.9806", "3.53", "10.6%", "12.691", "66.9%", "397/400", "99.25%", "1.5718"]


def main() -> None:
    draft = Path(sys.argv[1])
    facts = Path(sys.argv[2])
    prefix = sys.argv[3]
    out = Path(sys.argv[4]) if len(sys.argv) > 4 else (KIT / "初稿")
    text = draft.read_text(encoding="utf-8")
    allowed = set(TOKEN.findall(facts.read_text(encoding="utf-8")))
    tokens = TOKEN.findall(text)
    unknown = []
    for token in sorted(set(tokens)):
        if token in allowed:
            continue
        index = text.index(token)
        unknown.append({"token": token, "count": tokens.count(token),
                        "context": text[max(0, index - 40):index + 30].replace("\n", " ")})
    sections = {name: (name in text) for name in ("自检清单", "优化建议", "AI", "需补数")}
    report = {"chapter": prefix, "draft_chars": len(text), "unique_tokens": len(set(tokens)),
              "unknown_tokens": unknown, "sections_present": sections,
              "banned_term_hits": {w: text.count(w) for w in BANNED if w in text},
              "template_number_hits": {n: text.count(n) for n in TEMPLATE_NUMS if n in text},
              "reference_placeholders": dict(Counter(re.findall(r"【(图F\d+|表\d-\d+|式\(\d-\d+\))】", text))),
              "figure_ids": sorted({m for m in re.findall(r"【图(F\d+)】", text)})}
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{prefix}_初稿_网页agent.md").write_text(text, encoding="utf-8")
    (out / f"{prefix}_机器核对.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "unknown_tokens"}, ensure_ascii=False, indent=1))
    print("unknown_sample", json.dumps(unknown[:22], ensure_ascii=False))


if __name__ == "__main__":
    main()
