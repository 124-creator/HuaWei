# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""QA the web-agent chapter 5 draft against the facts table. Machine check only."""
import json
import re
from collections import Counter
from pathlib import Path

KIT = Path(r"E:/HWCupA2026/derived/r12_answer_20260925/web_agent_kit_v1")
DRAFT = Path(r"D:/默认下载/第5章_场景A下的多核切图与调度.md")
FACTS = KIT / "上传给网页agent/第5章/第5章_事实数值表.md"
OUT = KIT / "初稿"
TOKEN = re.compile(r"\d+(?:\.\d+)?(?:%|倍)?")
BANNED = ["生长子图", "强连通", "向上秩", "列表调度", "启发式投影", "簇足迹", "双上界", "预实验对照"]
TEMPLATE_NUMS = ["0.852", "1.3148", "1.7174", "2.0001", "1.7839", "2.4406", "2.9806", "3.53", "10.6%", "12.691", "66.9%", "397/400", "99.25%", "1.5718"]


def main() -> None:
    text = DRAFT.read_text(encoding="utf-8")
    facts = FACTS.read_text(encoding="utf-8")
    allowed = set(TOKEN.findall(facts))
    tokens = TOKEN.findall(text)
    unknown = []
    for token in sorted(set(tokens)):
        if token in allowed:
            continue
        index = text.index(token)
        unknown.append({"token": token, "count": tokens.count(token),
                        "context": text[max(0, index - 40):index + 30].replace("\n", " ")})
    sections = {name: (name in text) for name in ("自检清单", "优化建议", "质量评估", "AI", "需补数")}
    banned_hits = {word: text.count(word) for word in BANNED if word in text}
    template_hits = {num: text.count(num) for num in TEMPLATE_NUMS if num in text}
    refs = Counter(re.findall(r"【(图F\d+|表\d-\d+|式\(\d-\d+\))】", text))
    report = {"draft_chars": len(text), "unique_tokens": len(set(tokens)),
              "unknown_tokens": unknown, "sections_present": sections,
              "banned_term_hits": banned_hits, "template_number_hits": template_hits,
              "reference_placeholders": dict(refs), "figure_ids": sorted({m for m in re.findall(r"【图(F\d+)】", text)})}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "第5章_初稿_网页agent.md").write_text(text, encoding="utf-8")
    (OUT / "第5章_机器核对.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "unknown_tokens"}, ensure_ascii=False, indent=1))
    print("unknown_sample", json.dumps(unknown[:20], ensure_ascii=False))


if __name__ == "__main__":
    main()
