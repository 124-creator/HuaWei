# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Verify the working doc: idempotent rebuild, tag/table integrity, privacy, spot values."""
import csv
import hashlib
import json
import math
import re
import subprocess
import sys
from pathlib import Path

BASE = Path(r"E:/HWCupA2026/derived/r12_answer_20260925")
ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "公式与三线表工作稿.md"
CO = BASE / "publication/sources/closeout/results"


def sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main() -> None:
    before = sha(DOC)
    run = subprocess.run([sys.executable, "-X", "utf8", "-B", str(ROOT / "code/build_doc.py")],
                         capture_output=True, text=True, encoding="utf-8", check=False)
    assert run.returncode == 0, run.stdout + run.stderr
    assert sha(DOC) == before, "rebuild is not byte-identical (determinism violation)"
    text = DOC.read_text(encoding="utf-8")
    tags = re.findall(r"\\tag\{([^}]+)\}", text)
    expected = ([f"1-{i}" for i in range(1, 16)] + [f"2-{i}" for i in range(1, 13)] + [f"3-{i}" for i in range(1, 12)])
    assert tags == expected, (len(tags), set(expected) ^ set(tags))
    captions = re.findall(r"\*\*表([0-9]-[0-9]+)", text)
    assert captions == [f"1-{i}" for i in range(1, 5)] + [f"2-{i}" for i in range(1, 5)] + [f"3-{i}" for i in range(1, 6)], captions
    forbidden = r"(?<![A-Za-z])[A-Za-z]:\\(?=[A-Za-z0-9_])|/(?:home|mnt|Users)/|Dreamboat|AGent员工"
    assert not re.search(forbidden, text), "private path leaked into the document"
    sel = list(csv.DictReader((CO / "selected_per_case.csv").open(encoding="utf-8-sig")))
    a5 = [r for r in sel if r["scene"] == "A" and r["cores"] == "5"]
    a5mean = sum(float(r["speedup"]) for r in a5) / len(a5)
    walls = sorted(float(r["wall_seconds"]) for r in a5)
    spots = {f"{a5mean:.6f}": True, f"{walls[math.ceil(0.95*len(walls))-1]:.4f}": True,
             "3.743282": True, "4.131077": True, "1.016766": True, "1.027400": True,
             "4.187457": True, "4.218978": True, "23.4614%": True, "43.4760%": True}
    missing = [s for s in spots if s not in text]
    assert not missing, missing
    sources = json.loads((ROOT / "SOURCES.json").read_bytes())
    stale = []
    for name, digest in sources.items():
        path = (ROOT / name) if name.startswith("content/") else (BASE / name)
        if not path.is_file() or sha(path) != digest:
            stale.append(name)
    assert not stale, stale
    out = {"status": "WORKING_DOC_VERIFIED_MACHINE", "doc_sha256": sha(DOC), "equations": len(tags),
           "tables": len(captions), "privacy_scan": "PASS", "idempotent_rebuild": True,
           "spot_values_present": len(spots), "sources_tracked": len(sources),
           "independent_science_review": "NOT_PERFORMED", "solver_calls": 0}
    (ROOT / "RECEIPT.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
