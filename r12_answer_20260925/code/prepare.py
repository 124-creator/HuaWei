# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Freeze publication inputs. Existing Python: prepare.py WORKSPACE R12_CODE_ROOT.

AI-assisted: OpenCode/Sisyphus, OpenAI. Public model version/release date not
independently verified. This prepares internal review material, not submission.
"""
import hashlib
import json
import shutil
import sys
from pathlib import Path


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main() -> None:
    workspace, core = map(Path, sys.argv[1:3])
    target = Path(__file__).resolve().parents[1]
    local = target.parents[1]
    closeout = workspace / "verification/R12_Q3_closeout_20260925"
    source_dir = target / "publication/sources"
    source_dir.mkdir(parents=True, exist_ok=False)
    protected = {}
    for name in ("PROBLEM_SPEC.md", "EXPERIMENT_PROTOCOL.yaml", "RUN_STATE.yaml", "RESULTS.json", "ISSUES.jsonl",
                 "coordination/index.json", "paper/chapters/Q1.json", "paper/chapters/Q2.json", "paper/chapters/Q3.json",
                 "solutions/Q1.md", "solutions/Q2.md", "solutions/Q3.md"):
        protected[str(local / name)] = digest(local / name)
    bindings = {}
    manifest = json.loads((closeout / "SHA256SUMS.json").read_bytes())
    for name, expected in manifest.items():
        source = closeout / name
        if digest(source) != expected:
            raise RuntimeError(f"Frozen closeout changed: {source}")
        destination = source_dir / "closeout" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        bindings[str(source)] = expected
    frozen = json.loads((source_dir / "closeout/results/selection.json").read_bytes())
    for name, expected in frozen["source_files"].items():
        source = core / name
        if digest(source) != expected:
            raise RuntimeError(f"R12 source mismatch: {source}")
        destination = target / "reproduction/NPU_R12" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        bindings[str(source)] = expected
    source_config = core / "official/data/config.txt"
    if digest(source_config) != frozen["config_sha256"]:
        raise RuntimeError("Fixed configuration changed")
    destination = target / "reproduction/NPU_R12/official/data/config.txt"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_config, destination)
    bindings[str(source_config)] = digest(source_config)
    named = {
        "original_problem.docx": local / "inputs/official/A题原题.docx",
        "C3_official_cells.csv": local / "derived/formal_sources/official_1500_cells.csv",
        "METHOD_R12.md": core / "METHOD_R12.md",
        "README_R12.md": core / "README_R12.md",
        "historical_method_R10.md": core / "answer/三问答案_完整版.md",
    }
    for name, source in named.items():
        shutil.copyfile(source, source_dir / name)
        bindings[str(source)] = digest(source)
    tools = workspace / "工作流/.agents/skills/mcm-paper-format/tools"
    for name in ("solution_doc.py", "plot_style.py", "publication_fonts.py"):
        protected[str(tools / name)] = digest(tools / name)
    for source in target.rglob("*.py"):
        if "reproduction" not in source.parts:
            compile(source.read_text(encoding="utf-8"), str(source), "exec")
    record = {"kind": "DERIVED_PUBLICATION_ONLY", "parent_instance": str(local),
              "user_authorization": "可以请开始", "solver_calls_allowed": 0,
              "protected": protected, "inputs": bindings, "workflow_tools": str(tools),
              "source_code_files": len(frozen["source_files"]),
              "independent_science_review": "NOT_PERFORMED", "D4": "NOT_GRANTED"}
    with (target / "SOURCE_MANIFEST.json").open("x", encoding="utf-8") as stream:
        json.dump(record, stream, ensure_ascii=False, indent=2)
    print(json.dumps({"status": "INPUTS_FROZEN", "files": len(bindings), "protected": len(protected)}))


if __name__ == "__main__":
    main()
