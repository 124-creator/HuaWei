# /// script
# requires-python = ">=3.12"
# dependencies = ["pymupdf==1.28.2"]
# ///
"""Stream PDFs pagewise and cache small text/geometry records. No input changes."""
import gzip
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

import pymupdf

from inventory import sha
from pdf_rules import Hit, equation_tag, heading_kind, normalized, right_label, table_tag

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    started = time.perf_counter()
    records = json.loads((ROOT / "INPUTS.json").read_bytes())
    cache = ROOT / "cache"
    cache.mkdir(exist_ok=True)
    pages_processed = 0
    for item in records:
        if sys.argv[1:] and item["id"] not in sys.argv[1:]:
            continue
        dest = cache / (item["id"] + ".json.gz")
        if dest.exists():
            continue
        path = Path(item["path"])
        assert sha(path) == item["sha256"]
        pages = []
        with pymupdf.open(path) as doc:
            for pnum, page in enumerate(doc, 1):
                flags = pymupdf.TEXTFLAGS_DICT & ~pymupdf.TEXT_PRESERVE_IMAGES
                tp = page.get_textpage(flags=flags)
                lines = []
                spans = []
                for block in page.get_text("dict", textpage=tp)["blocks"]:
                    for line in block.get("lines", []):
                        text = "".join(span["text"] for span in line["spans"])
                        lines.append({"text": text, "box": line["bbox"], "size": max((s["size"] for s in line["spans"]), default=0)})
                        spans += [{"text": s["text"], "box": s["bbox"], "size": s["size"]} for s in line["spans"]]
                words = page.get_text("words", textpage=tp)
                sources = lines + spans + [{"text": w[4], "box": w[:4], "size": 0} for w in words]
                hits = []
                seen = set()
                for source in sources:
                    tag = equation_tag(source["text"])
                    box = tuple(source["box"])
                    if tag and right_label(box, (page.rect.width, page.rect.height), item["columns"]):
                        if tag.isdigit() and int(tag) > 1000:
                            continue
                        identity = ("equation", tag, round(box[1] / 8))
                        if identity not in seen:
                            hits.append(asdict(Hit("equation", tag, pnum, box, source["text"])))
                            seen.add(identity)
                marks = []
                for line in lines:
                    text = normalized(line["text"])
                    box = tuple(line["box"])
                    label = table_tag(text)
                    if label and .04 * page.rect.height < box[1] < .94 * page.rect.height:
                        identity = ("table", label[0], round(box[1] / 8))
                        if identity not in seen:
                            hits.append(asdict(Hit("table", label[0], pnum, box, text, label[1])))
                            seen.add(identity)
                    kind = heading_kind(text)
                    if kind:
                        marks.append({"kind": kind, "page": pnum, "y": box[1], "text": text, "size": line["size"]})
                pages.append({"page": pnum, "width": page.rect.width, "height": page.rect.height,
                              "lines": lines, "hits": hits, "headings": marks, "text_chars": sum(len(x["text"]) for x in lines)})
                pages_processed += 1
            payload = {"id": item["id"], "source_sha256": item["sha256"], "total_pages": len(doc), "pages": pages}
        with gzip.open(dest, "wt", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False)
        eqs = {h["tag"] for p in pages for h in p["hits"] if h["kind"] == "equation"}
        tables = {h["tag"] for p in pages for h in p["hits"] if h["kind"] == "table"}
        print(f"{item['id']}: pages={len(pages)} eq_tags_full={len(eqs)} table_tags_full={len(tables)}", flush=True)
    print(json.dumps({"pages_processed": pages_processed, "elapsed_s": round(time.perf_counter()-started, 2)}))


if __name__ == "__main__":
    main()
