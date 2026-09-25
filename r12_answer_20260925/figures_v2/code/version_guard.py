# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Run with the existing interpreter: version_guard.py init | check."""
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT.parent / "figures32"


def sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def initialize() -> None:
    protected = {str(p): sha(p) for p in sorted(OLD.rglob("*")) if p.is_file()}
    for name in ("R12_team_share.zip", "R12_answers_candidate.zip"):
        p = ROOT.parent / name
        protected[str(p)] = sha(p)
    for p in (ROOT.parent / "publication" / "solutions").glob("*.md"):
        protected[str(p)] = sha(p)
    with (ROOT / "PREVIOUS_VERSION.json").open("x", encoding="utf-8") as stream:
        json.dump(protected, stream, ensure_ascii=False, indent=2)
    for folder in ("figures", "data", "metadata"):
        shutil.copytree(OLD / folder, ROOT / folder)
    for p in (OLD / "code").glob("*.py"):
        if p.name != "extract.py":
            assert not (ROOT / "code" / p.name).exists()
            shutil.copyfile(p, ROOT / "code" / p.name)
    for name in ("dataset.json", "INPUTS.json", "figure_requirements.json", "visual_contract.json"):
        assert not (ROOT / name).exists()
        shutil.copyfile(OLD / name, ROOT / name)
    print(f"INITIALIZED v2; protected {len(protected)} previous files")


def check() -> None:
    protected = json.loads((ROOT / "PREVIOUS_VERSION.json").read_bytes())
    for path, expected in protected.items():
        assert sha(Path(path)) == expected, path
    assert sha(ROOT / "dataset.json") == sha(OLD / "dataset.json")
    assert sha(ROOT / "INPUTS.json") == sha(OLD / "INPUTS.json")
    print(f"UNCHANGED: {len(protected)} previous files; dataset and input bindings identical")


if __name__ == "__main__":
    {"init": initialize, "check": check}[sys.argv[1]]()
