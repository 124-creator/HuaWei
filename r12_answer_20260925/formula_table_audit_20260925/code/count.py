# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Refined counting from the frozen cache. Primary metric: unique numbered units."""
import csv
import gzip
import json
import re
import statistics
from pathlib import Path

from pdf_rules import equation_unit, glued_equation_tag

ROOT = Path(__file__).resolve().parents[1]


def load(pid: str) -> dict:
    with gzip.open(ROOT / "cache" / f"{pid}.json.gz", "rt", encoding="utf-8") as stream:
        return json.load(stream)


def boundaries(data: dict, group: str) -> tuple[int, int, bool, bool]:
    body = 3 if group == "competition" else 1
    toc_pages = [page["page"] for page in data["pages"] if any(h["kind"] == "toc" for h in page["headings"])]
    guard = (max(toc_pages) + 3) if toc_pages else 0
    for page in data["pages"]:
        if any(h["kind"] == "body_start" for h in page["headings"]):
            body = page["page"]
            break
    frontier = data["total_pages"] + 1
    for page in data["pages"]:
        if page["page"] <= guard:
            continue
        kinds = {h["kind"] for h in page["headings"]}
        if kinds & {"references", "appendix"}:
            frontier = min(frontier, page["page"])
    saw_ref = any(h["kind"] == "references" for p in data["pages"] for h in p["headings"] if p["page"] > guard)
    saw_app = any(h["kind"] == "appendix" for p in data["pages"] for h in p["headings"] if p["page"] > guard)
    return body, frontier, saw_ref, saw_app


def plates(pid: str, data: dict, group: str) -> dict:
    body, frontier, saw_ref, saw_app = boundaries(data, group)
    eq_main: dict[str, int] = {}
    eq_app: dict[str, int] = {}
    glued_new: dict[str, int] = {}
    eq_pages: dict[str, set[int]] = {}
    tab_main: dict[str, bool] = {}
    tab_app: dict[str, bool] = {}
    tab_dup: list[str] = []
    for page in data["pages"]:
        in_main = body <= page["page"] < frontier
        for hit in page["hits"]:
            if hit["kind"] == "equation":
                tag = hit["tag"]
                if re.match(r"^0[.]", tag):
                    continue
                unit = equation_unit(tag)
                target = eq_main if in_main else eq_app
                target.setdefault(unit, 0)
                eq_pages.setdefault(unit, set()).add(page["page"])
            elif hit["kind"] == "table":
                target = tab_main if in_main else tab_app
                if hit["tag"] in target:
                    if hit["tag"] not in tab_dup:
                        tab_dup.append(hit["tag"])
                target[hit["tag"]] = bool(hit.get("continued"))
        for line in page["lines"]:
            tag = glued_equation_tag(line["text"])
            if tag and line["box"][2] > .62 * page["width"]:
                if in_main and equation_unit(tag) not in eq_main:
                    glued_new[tag] = page["page"]
    repeat = {u: sorted(p) for u, p in eq_pages.items() if len(p) > 2}
    return {"id": pid, "group": group, "pages_total": data["total_pages"], "body_start": body,
            "frontier": frontier, "saw_references": saw_ref, "saw_appendix": saw_app,
            "body_pages": max(0, frontier - body),
            "eq_main": len(eq_main), "eq_appendix": len(eq_app), "eq_glued_extra": len(glued_new),
            "eq_multi_page": len(repeat), "tables_main": len(tab_main), "tables_appendix": len(tab_app),
            "table_duplicate_ids": len(tab_dup), "table_continues": sum(tab_main.values()),
            "_glued": glued_new, "_repeat": {k: v for k, v in list(repeat.items())[:4]}}


def main() -> None:
    inputs = json.loads((ROOT / "INPUTS.json").read_bytes())
    out = ROOT / "out"
    out.mkdir(exist_ok=True)
    records, candidates = [], []
    for item in inputs:
        data = load(item["id"])
        record = plates(item["id"], data, item["group"])
        record["year"] = item["year"]
        record["title"] = item["title"]
        records.append(record)
        for page in data["pages"]:
            for hit in page["hits"]:
                candidates.append({"id": item["id"], "kind": hit["kind"], "tag": hit["tag"], "page": hit["page"],
                                   "x0_w": round(hit["box"][0] / page["width"], 3), "text": hit["text"][:70]})
    fields = [k for k in records[0] if not k.startswith("_")]
    with (out / "per_paper.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for record in records:
            writer.writerow({k: v for k, v in record.items() if k in fields})
    with (out / "candidates.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["id", "kind", "tag", "page", "x0_w", "text"])
        writer.writeheader()
        writer.writerows(candidates)
    groups: dict[str, list[dict]] = {}
    for record in records:
        key = record["group"] if record["group"] != "competition" else f"competition_{record['year']}"
        groups.setdefault(key, []).append(record)
    summary = {}
    for key, rows in groups.items():
        eq = sorted(r["eq_main"] + r["eq_glued_extra"] for r in rows)
        tables = sorted(r["tables_main"] for r in rows)
        rate = sorted(10 * (r["eq_main"] + r["eq_glued_extra"]) / max(1, r["body_pages"]) for r in rows)
        summary[key] = {"n": len(rows), "eq_main": {"min": eq[0], "q1": statistics.quantiles(eq, n=4)[0] if len(eq) > 3 else eq[0],
                         "median": statistics.median(eq), "q3": statistics.quantiles(eq, n=4)[2] if len(eq) > 3 else eq[-1], "max": eq[-1]},
                        "tables_main": {"min": tables[0], "median": statistics.median(tables), "max": tables[-1]},
                        "eq_per_10_body_pages": {"min": round(rate[0], 2), "median": round(statistics.median(rate), 2), "max": round(rate[-1], 2)}}
    summary["all_competition"] = {}
    comp = [r for r in records if r["group"] == "competition"]
    eqc = sorted(r["eq_main"] + r["eq_glued_extra"] for r in comp)
    tabc = sorted(r["tables_main"] for r in comp)
    summary["all_competition"] = {"n": len(comp), "eq_main": {"min": eqc[0], "median": statistics.median(eqc), "max": eqc[-1]},
                                  "tables_main": {"min": tabc[0], "median": statistics.median(tabc), "max": tabc[-1]}}
    flagged = {"missing_boundaries": [r["id"] for r in records if not r["saw_references"]],
               "duplicate_table_ids": {r["id"]: r["table_duplicate_ids"] for r in records if r["table_duplicate_ids"]},
               "glued_samples": {r["id"]: r["_glued"] for r in records if r["_glued"]},
               "multi_page_equation_tags": {r["id"]: r["_repeat"] for r in records if r["_repeat"]}}
    (out / "SUMMARY.json").write_text(json.dumps({"summary": summary, "flags": flagged}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print("FLAGS", json.dumps({k: (len(v) if isinstance(v, (list, dict)) else v) for k, v in flagged.items()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
