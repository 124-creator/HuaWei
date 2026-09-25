# /// script
# requires-python = ">=3.12"
# dependencies = ["python-docx"]
# ///
"""Inventory every numeric token in the teammate template for classification."""
import csv
import json
import re
from collections import defaultdict
from pathlib import Path

from docx import Document

SRC = Path(r"C:\Users\Dreamboat\OneDrive\文档\WeChat Files\wxid_tnssm99dpsea22\FileStorage\Temp\Copy\2026华为杯A题_本人部分P0候选_v0.6.docx")
OUT = Path(__file__).resolve().parents[1] / "out"
TOKEN = re.compile(r"\d+(?:\.\d+)?(?:%|倍)?")


def main() -> None:
    doc = Document(SRC)
    entries: list[tuple[str, str]] = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            entries.append(("p", text))
    for ti, table in enumerate(doc.tables):
        for row in table.rows:
            entries.append((f"t{ti}", " | ".join(cell.text.strip() for cell in row.cells)))
    index: dict[str, list[str]] = defaultdict(list)
    for where, text in entries:
        for match in TOKEN.finditer(text):
            token = match.group(0)
            if len(token) == 1 and token.isdigit():
                continue
            start = max(0, match.start() - 30)
            index[token].append(f"[{where}] …{text[start:match.end()+24]}…")
    OUT.mkdir(exist_ok=True)
    rows = []
    for token, samples in sorted(index.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        rows.append({"token": token, "count": len(samples), "first_context": samples[0][:110]})
    with (OUT / "template_number_inventory.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["token", "count", "first_context"])
        writer.writeheader()
        writer.writerows(rows)
    result_like = [r for r in rows if re.match(r"^[0-3]\.\d{2,}|^\d+\.\d+%?$", r["token"])]
    print(json.dumps({"unique_tokens": len(rows), "rows": len(rows),
                      "result_like_sample": result_like[:25],
                      "file": str(OUT / "template_number_inventory.csv")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
