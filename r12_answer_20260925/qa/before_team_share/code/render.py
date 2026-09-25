# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Existing Python: render.py Q1 (or Q2/Q3).

Prepare a derived chapter, then call the unchanged workflow solution-doc CLI.
This is a publication projection, not a new instance or an accepted chapter.
AI-assisted: OpenCode/Sisyphus, OpenAI; public model release date unverified.
"""
import json
import subprocess
import sys
from pathlib import Path

from prepare import digest


def main() -> None:
    qid = sys.argv[1]
    if qid not in {"Q1", "Q2", "Q3"}:
        raise RuntimeError("Expected Q1, Q2 or Q3")
    target = Path(__file__).resolve().parents[1]
    root = target / "publication"
    task = target / "TASK.md"
    draft = target / "drafts" / f"{qid}.json"
    chapter = json.loads(draft.read_bytes())
    names = ["RESULTS.json", "tables/display_values.csv", "tables/summary.csv", "tables/comparison_C3.csv",
             "sources/original_problem.docx", "sources/METHOD_R12.md", "sources/closeout/results/selection.json",
             "sources/closeout/results/verification.json", f"../drafts/{qid}.json", "../code/derive.py",
             "../reproduction/NPU_R12/round12_src/solve_round12.py",
             "../reproduction/NPU_R12/round12_src/residency_bands.py",
             "../reproduction/NPU_R12/official/code/multicore_cut_evaluate_problem_3.py"]
    figure_name = {"Q1": "q1_curve", "Q2": "q2_curve", "Q3": "q3_configuration"}[qid]
    names += [f"figures/{figure_name}.pdf", f"figures/{figure_name}.png", f"tables/{qid}_per_case.csv"]
    chapter.update(schema="manuscript-craft-v1", question_id=qid, plan_signature=digest(task),
                   source_bindings={name: digest(root / name) for name in names},
                   open_gaps=["队员实质性科学审阅、工具信息及引用核实尚待完成；本稿不是正式提交件。"],
                   mathematical_preflight={"status": "AUTHOR_SELF_CHECK_ONLY", "external_review": "NOT_PERFORMED",
                                           "scope": "source-bound internal draft; not formal acceptance"})
    for section in chapter["sections"]:
        for index, block in enumerate(section["blocks"], 1):
            block["id"] = f"{section['section_id']}_b{index}"
            block["evidence_ids"] = ["original_problem", "R12_source", "frozen_results"]
    chapters = root / "paper/chapters"
    chapters.mkdir(parents=True, exist_ok=True)
    with (chapters / f"{qid}.json").open("w", encoding="utf-8") as stream:
        json.dump(chapter, stream, ensure_ascii=False, indent=2)
    manifest = json.loads((target / "SOURCE_MANIFEST.json").read_bytes())
    workflow = Path(manifest["workflow_tools"]).parents[3]
    command = [sys.executable, "-X", "utf8", "-B", str(workflow / "mmwf.py"), "solution-doc",
               "--root", str(root), "--question", qid]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", check=False)
    log = {"command": command, "returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
    with (target / f"RENDER_{qid}.json").open("w", encoding="utf-8") as stream:
        json.dump(log, stream, ensure_ascii=False, indent=2)
    print(result.stdout)
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout)


if __name__ == "__main__":
    main()
