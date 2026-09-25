# /// script
# requires-python = ">=3.12"
# dependencies = ["python-docx"]
# ///
"""Extract full outline + tail of the teammate docx to scope the user's part."""
import json
import re
from pathlib import Path

from docx import Document

SRC = Path(r"C:\Users\Dreamboat\OneDrive\文档\WeChat Files\wxid_tnssm99dpsea22\FileStorage\Temp\Copy\2026华为杯A题_本人部分P0候选_v0.6.docx")
HEADING = re.compile(r"^(\d+(\.\d+){0,3})[ 　]?(\S.{0,60})$|^(附录[A-Z]?|参考文献|摘\s*要|关键词)")


def main() -> None:
    doc = Document(SRC)
    outline, tail = [], []
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        match = HEADING.match(text)
        outline.append({"t": text[:80]}) if match and len(text) <= 84 else None
        tail.append(text[:100])
    table_captions = [t[:70] for t in tail if re.match(r"^表\s*\d", t)]
    figure_captions = [t[:70] for t in tail if re.match(r"^图\s*\d", t)]
    print(json.dumps({"outline": outline, "tables": table_captions, "figures": figure_captions,
                      "tail_last12": tail[-12:]}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
