# /// script
# requires-python = ">=3.12"
# dependencies = ["pymupdf==1.28.2", "pytest==9.1.1"]
# ///
"""Existing Python: check_delivery.py. Read-only checks plus own QA outputs.

AI-assisted: OpenCode/Sisyphus, OpenAI; public model release date unverified.
This is author QA, never an independent scientific acceptance certificate.
"""
import csv
import json
import re
import subprocess
import sys
from decimal import Decimal, getcontext
from pathlib import Path
from statistics import median

import pymupdf

from prepare import digest


def main() -> None:
    target = Path(__file__).resolve().parents[1]
    root = target / "publication"
    qa = target / "qa"
    qa.mkdir(exist_ok=True)
    manifest = json.loads((target / "SOURCE_MANIFEST.json").read_bytes())
    for path, expected in {**manifest["inputs"], **manifest["protected"]}.items():
        if digest(Path(path)) != expected:
            raise RuntimeError(f"Protected input changed: {path}")
    frozen = json.loads((root / "sources/closeout/results/selection.json").read_bytes())
    for path, expected in frozen["source_files"].items():
        if digest(target / "reproduction/NPU_R12" / path) != expected:
            raise RuntimeError(f"Copied solver changed: {path}")
    getcontext().prec = 60
    with (root / "sources/closeout/results/selected_per_case.csv").open(encoding="utf-8-sig", newline="") as stream:
        selected = list(csv.DictReader(stream))
    with (root / "sources/closeout/results/q3_paired_per_case.csv").open(encoding="utf-8-sig", newline="") as stream:
        pairs = list(csv.DictReader(stream))
    with (root / "sources/C3_official_cells.csv").open(encoding="utf-8-sig", newline="") as stream:
        c3 = {(r["case_id"], r["k"], r["problem"]): r for r in csv.DictReader(stream)}
    result = json.loads((root / "RESULTS.json").read_bytes())
    with (root / "tables/display_values.csv").open(encoding="utf-8-sig", newline="") as stream:
        wide = next(csv.DictReader(stream))
    for key, item in result["paper_values"].items():
        assert Decimal(str(item["value"])) == Decimal(wide[key]), key
    for scene in ("A", "B", "L2"):
        for k in range(1, 6):
            group = [r for r in selected if r["scene"] == scene and int(r["cores"]) == k]
            if not group:
                assert scene == "A" and k == 1
                continue
            assert len(group) == 100
            exact = sum(Decimal(r["fixed_singlecore"]) / Decimal(r["makespan"]) for r in group) / 100
            assert abs(exact - Decimal(wide[f"{scene}.k{k}.mean_speedup"])) < Decimal("1e-12")
            wall = sorted(Decimal(r["wall_seconds"]) for r in group)
            independent = {"wall_median_s": median(wall), "wall_p95_s": wall[94], "wall_max_s": wall[-1]}
            for label, column in (("mean_added_MiB", "added_copy_bytes"), ("mean_partition_MiB", "partition_added_copy_bytes"), ("mean_spill_MiB", "spill_added_copy_bytes")):
                independent[label] = sum(Decimal(r[column]) for r in group) / 100 / 1048576
            for label, exact_value in independent.items():
                assert abs(exact_value - Decimal(wide[f"{scene}.k{k}.{label}"])) < Decimal("1e-12")
            old_times = [Decimal(c3[(r["case"], r["cores"], scene)]["makespan_cycles"]) for r in group]
            new_times = [Decimal(r["makespan"]) for r in group]
            reduction = sum(1 - b / a for a, b in zip(old_times, new_times))
            assert abs(reduction - Decimal(wide[f"C3.{scene}.k{k}.time_reduction_percent"])) < Decimal("1e-12")
            assert sum(b < a for a, b in zip(old_times, new_times)) == int(wide[f"C3.{scene}.k{k}.wins"])
            assert sum(b == a for a, b in zip(old_times, new_times)) == int(wide[f"C3.{scene}.k{k}.ties"])
            assert sum(b > a for a, b in zip(old_times, new_times)) == int(wide[f"C3.{scene}.k{k}.losses"])
            faster_more = sum(int(r["makespan"]) < int(c3[(r["case"], r["cores"], scene)]["makespan_cycles"])
                              and int(r["added_copy_bytes"]) > int(c3[(r["case"], r["cores"], scene)]["data_movement_bytes"]) for r in group)
            assert faster_more == int(wide[f"C3.{scene}.k{k}.faster_more_copy"])
    for k in range(1, 6):
        group = [r for r in pairs if int(r["cores"]) == k]
        assert len(group) == 100
        for key, denominator in (("same_plan_mean", "L2_same_B_plan_makespan"), ("separate_selection_mean", "L2_selected_makespan")):
            exact = sum(Decimal(r["B_makespan"]) / Decimal(r[denominator]) for r in group) / 100
            assert abs(exact - Decimal(wide[f"Q3.k{k}.{key}"])) < Decimal("1e-12")
    appendix_counts = {}
    for qid, expected in (("Q1", 400), ("Q2", 500), ("Q3", 500)):
        with (root / "tables" / f"{qid}_per_case.csv").open(encoding="utf-8-sig", newline="") as stream:
            appendix = list(csv.DictReader(stream))
        assert len(appendix) == expected
        assert len({(r["case"], r["cores"]) for r in appendix}) == expected
        appendix_counts[qid] = expected
        document = root / "solutions" / f"{qid}.md"
        text = document.read_text(encoding="utf-8")
        assert "{{value:" not in text and "UNHANDLED_BLOCK" not in text and "‹未解析:" not in text
        for link in re.findall(r"\]\(([^)]+)\)", text):
            assert (document.parent / link).is_file(), (qid, link)
        chapter = json.loads((root / "paper/chapters" / f"{qid}.json").read_bytes())
        for name, expected_sha in chapter["source_bindings"].items():
            assert digest(root / name) == expected_sha, name
        for section in chapter["sections"]:
            for block in section["blocks"]:
                if block.get("type") == "raw_math":
                    assert not any(ord(c) < 32 and c not in "\n\r" for c in block["tex"])
    with (root / "tables/Q3_degraded.csv").open(encoding="utf-8-sig", newline="") as stream:
        assert len(list(csv.DictReader(stream))) == 8
    plots = json.loads((root / "figures/plot_data.json").read_bytes())
    for plot in plots[:2]:
        scene = {"q1_curve": "A", "q2_curve": "B"}[plot["figure"]]
        expected = [1.0] + [float(wide[f"{scene}.k{k}.mean_speedup"]) for k in range(2, 6)]
        assert plot["x"] == [1, 2, 3, 4, 5] and plot["R12"] == expected
    assert plots[2]["hardware_ratio"] == [float(wide[f"Q3.k{k}.same_plan_mean"]) for k in range(1, 6)]
    pdf_records = []
    for name in ("q1_curve", "q2_curve", "q3_configuration"):
        pdf = root / "figures" / f"{name}.pdf"
        with pymupdf.open(pdf) as doc:
            assert len(doc) == 1
            page = doc[0]
            text = page.get_text()
            assert "\ufffd" not in text and any("\u4e00" <= c <= "\u9fff" for c in text)
            image = qa / f"{name}_from_pdf.png"
            page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False).save(image)
            pdf_records.append({"pdf": str(pdf.relative_to(target)), "sha256": digest(pdf),
                                "image": str(image.relative_to(target)), "width_pt": page.rect.width,
                                "height_pt": page.rect.height, "text_chars": len(text)})
    tests = subprocess.run([sys.executable, "-B", "-m", "pytest", "-p", "no:cacheprovider", str(target / "code/test_metrics.py"), "-q"], capture_output=True, text=True, check=False)
    assert tests.returncode == 0, tests.stdout + tests.stderr
    pure_lines = {}
    for source in (target / "code").glob("*.py"):
        content = source.read_text(encoding="utf-8")
        compile(content, str(source), "exec")
        pure_lines[source.name] = sum(bool(line.strip()) and not line.lstrip().startswith("#") for line in content.splitlines())
        assert pure_lines[source.name] <= 250
    receipt = {"status": "AUTHOR_MECHANICAL_CHECKS_PASS", "independent_science_review": "NOT_PERFORMED",
               "protected_unchanged": len(manifest["protected"]), "input_bindings_unchanged": len(manifest["inputs"]),
               "copied_source_files": len(frozen["source_files"]), "appendix_counts": appendix_counts,
               "display_values_checked": len(wide), "arithmetic_tolerance": "1e-12",
               "tests": {"returncode": tests.returncode, "stdout": tests.stdout, "stderr": tests.stderr},
               "source_pure_lines": pure_lines, "pdf_renders": pdf_records,
               "visual_review": "REQUIRES_DIRECT_IMAGE_INSPECTION", "lsp": "Unavailable; no install performed",
               "new_solver_calls": 0, "new_official_scoring_calls": 0}
    with (target / "CHECK_RECEIPT.json").open("w", encoding="utf-8") as stream:
        json.dump(receipt, stream, ensure_ascii=False, indent=2)
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == "__main__":
    main()
