# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Existing Python: package_delivery.py. Package internal drafts; never upload.

AI-assisted: OpenCode/Sisyphus, OpenAI; public model release date unverified.
"""
import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path

from prepare import digest


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    check = json.loads((root / "CHECK_RECEIPT.json").read_bytes())
    assert check["status"] == "AUTHOR_MECHANICAL_CHECKS_PASS"
    assert (root / "VISUAL_REVIEW.md").is_file()
    smoke = []
    for script in ("solve_round12.py", "run_matrix.py"):
        command = [sys.executable, "-B", "-S", str(root / "reproduction/NPU_R12/round12_src" / script), "--help"]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        assert result.returncode == 0, result.stderr
        smoke.append({"script": script, "returncode": result.returncode, "stdout": result.stdout,
                      "scope": "argument/import smoke only; not a solver run"})
    with (root / "ENTRYPOINT_SMOKE.json").open("w", encoding="utf-8") as stream:
        json.dump(smoke, stream, ensure_ascii=False, indent=2)
    omitted = {"SHA256SUMS.json", "PACKAGE_RECEIPT.json"}
    files = [p for p in sorted(root.rglob("*")) if p.is_file() and p.suffix != ".zip"
             and p.name not in omitted and "__pycache__" not in p.parts and ".pytest_cache" not in p.parts]
    manifest = {p.relative_to(root).as_posix(): digest(p) for p in files}
    with (root / "SHA256SUMS.json").open("w", encoding="utf-8") as stream:
        json.dump(manifest, stream, ensure_ascii=False, indent=2)
    bundle = root / "R12_answers_candidate.zip"
    with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files + [root / "SHA256SUMS.json"]:
            archive.write(path, path.relative_to(root).as_posix())
    with zipfile.ZipFile(bundle) as archive:
        assert archive.testzip() is None
        assert len(archive.namelist()) == len(manifest) + 1
        for name, expected in manifest.items():
            assert hashlib.sha256(archive.read(name)).hexdigest() == expected, name
    receipt = {"status": "INTERNAL_BUNDLE_VERIFIED", "file": bundle.name, "bytes": bundle.stat().st_size,
               "sha256": digest(bundle), "verified_files": len(manifest), "crc_check": "PASS",
               "contents": "three drafts, three charts, per-case tables, 68 frozen source files, config, provenance",
               "omitted": "100 original graph files and bulk raw timelines; obtain originals by frozen hashes",
               "submission_approved": False}
    with (root / "PACKAGE_RECEIPT.json").open("w", encoding="utf-8") as stream:
        json.dump(receipt, stream, ensure_ascii=False, indent=2)
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
