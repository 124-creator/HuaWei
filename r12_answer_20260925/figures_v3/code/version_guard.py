# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Existing interpreter: version_guard.py init | check. Never modify older versions."""
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT.parent / "figures_v2"


def sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def initialize() -> None:
    protected = json.loads((OLD / "PREVIOUS_VERSION.json").read_bytes())
    protected.update({str(p): sha(p) for p in OLD.rglob("*") if p.is_file()})
    for p in (ROOT.parent / "publication").rglob("*"):
        if p.is_file():
            protected[str(p)] = sha(p)
    with (ROOT / "PREVIOUS_VERSION.json").open("x", encoding="utf-8") as stream:
        json.dump(protected, stream, ensure_ascii=False, indent=2)
    for folder in ("figures", "data", "metadata"):
        shutil.copytree(OLD / folder, ROOT / folder)
    for p in (OLD / "code").glob("*.py"):
        if p.name != "version_guard.py":
            assert not (ROOT / "code" / p.name).exists()
            shutil.copyfile(p, ROOT / "code" / p.name)
    for name in ("dataset.json", "INPUTS.json", "figure_requirements.json", "visual_contract.json", "SKILL_REFERENCES.md"):
        assert not (ROOT / name).exists()
        shutil.copyfile(OLD / name, ROOT / name)
    print(f"INITIALIZED v3; protected {len(protected)} prior files")


def check() -> None:
    protected = json.loads((ROOT / "PREVIOUS_VERSION.json").read_bytes())
    for path, expected in protected.items():
        assert sha(Path(path)) == expected, path
    for name in ("dataset.json", "INPUTS.json"):
        assert sha(ROOT / name) == sha(OLD / name)
    print(f"UNCHANGED: {len(protected)} prior files; frozen dataset/bindings identical")


if __name__ == "__main__":
    {"init": initialize, "check": check}[sys.argv[1]]()
