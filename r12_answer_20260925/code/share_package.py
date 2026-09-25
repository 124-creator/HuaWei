# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Existing Python: share_package.py. Export an explicit, path-free reading set.

AI-assisted: OpenCode/Sisyphus, OpenAI; public model release date unverified.
"""
import hashlib
import json
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

from prepare import digest


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    publication = root / "publication"
    before = root / "qa/before_team_share"
    prior = json.loads((before / "SHA256SUMS.json").read_bytes())
    immutable = [name for name in prior if name.startswith(("publication/tables/", "publication/figures/", "publication/sources/", "reproduction/"))]
    for name in immutable:
        assert digest(root / name) == prior[name], name
    assert digest(root / "publication/RESULTS.json") == prior["publication/RESULTS.json"]
    used = {}
    formula_counts = {}
    for qid in ("Q1", "Q2", "Q3"):
        old = (before / "drafts" / f"{qid}.json").read_text(encoding="utf-8")
        new = (root / "drafts" / f"{qid}.json").read_text(encoding="utf-8")
        pattern = r"\{\{value:([^}]+)\}\}"
        old_keys, new_keys = set(re.findall(pattern, old)), set(re.findall(pattern, new))
        assert old_keys == new_keys, qid
        used[qid] = len(new_keys)
        original = (root / "qa/share_renderer" / f"{qid}.md").read_text(encoding="utf-8")
        body = original[original.index("## 1. "):original.index("## 附录 A")]
        body = re.sub(r"^<sub>.*$|^<!-- evidence:.*$", "", body, flags=re.MULTILINE)
        document = (publication / "solutions" / f"{qid}.md").read_text(encoding="utf-8")
        content = document[document.index("## 1. "):]
        number = r"\b\d+(?:\.\d+)?(?:e[+-]?\d+)?"
        assert re.findall(number, body) == re.findall(number, content), qid
        assert "```latex" not in document and "<sub>" not in document and "<!-- evidence:" not in document
        formula_counts[qid] = len(re.findall(r"^\$\$$", document, flags=re.MULTILINE)) // 2
    checks = subprocess.run([sys.executable, "-X", "utf8", "-B", str(root / "code/check_delivery.py")], capture_output=True, text=True, encoding="utf-8", check=False)
    assert checks.returncode == 0, checks.stdout + checks.stderr
    tests = subprocess.run([sys.executable, "-X", "utf8", "-B", "-m", "pytest", "-p", "no:cacheprovider", str(root / "code/test_metrics.py"), str(root / "code/test_reader_view.py"), "-q"], capture_output=True, text=True, encoding="utf-8", check=False)
    assert tests.returncode == 0, tests.stdout + tests.stderr
    members = [f"solutions/Q{i}.md" for i in range(1, 4)] + ["阅读说明.md"]
    members += [f"figures/{stem}.{suffix}" for stem in ("q1_curve", "q2_curve", "q3_configuration") for suffix in ("png", "pdf")]
    members += [f"tables/{name}.csv" for name in ("Q1_per_case", "Q2_per_case", "Q3_per_case", "Q3_degraded", "summary", "comparison_C3")]
    share = root / "team_share"
    share.mkdir(exist_ok=True)
    extras = {p.relative_to(share).as_posix() for p in share.rglob("*") if p.is_file()} - set(members) - {"MANIFEST.json"}
    assert not extras, extras
    forbidden = r"(?<![A-Za-z])[A-Za-z]:[\\/]|/(?:home|mnt|Users)/|Dreamboat|AGent员工|source_bindings|plan_signature"
    hashes = {}
    for name in members:
        source, destination = publication / name, share / name
        if source.suffix in {".md", ".csv"}:
            assert re.search(forbidden, source.read_text(encoding="utf-8-sig")) is None, name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        hashes[name] = digest(destination)
    for name in [n for n in members if n.endswith(".md")]:
        path = share / name
        for link in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
            assert (path.parent / link).is_file(), (name, link)
            assert (path.parent / link).resolve().is_relative_to(share.resolve()), (name, link)
    with (share / "MANIFEST.json").open("w", encoding="utf-8") as stream:
        json.dump({"version": "R12 full", "files": hashes}, stream, ensure_ascii=False, indent=2)
    bundle = root / "R12_team_share.zip"
    with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in members + ["MANIFEST.json"]:
            archive.write(share / name, name)
    with zipfile.ZipFile(bundle) as archive:
        assert archive.testzip() is None
        assert set(archive.namelist()) == set(members) | {"MANIFEST.json"}
        for name, expected in hashes.items():
            assert hashlib.sha256(archive.read(name)).hexdigest() == expected
    old_receipt = json.loads((before / "PACKAGE_RECEIPT.json").read_bytes())
    assert digest(root / old_receipt["file"]) == old_receipt["sha256"]
    receipt = {"status": "CHECKED_READING_COPY", "immutable_files": len(immutable), "source_values_unchanged": True,
               "referenced_keys": used, "numeric_tokens_preserved": True, "display_math_counts": formula_counts,
               "tests": tests.stdout, "privacy_scan": "PASS_EXPLICIT_READING_SET", "relative_links": "PASS",
               "files": len(hashes), "zip_bytes": bundle.stat().st_size, "zip_sha256": digest(bundle),
               "old_zip_unchanged": True, "independent_science_review": "NOT_PERFORMED"}
    with (root / "qa/SHARE_CHECK.json").open("w", encoding="utf-8") as stream:
        json.dump(receipt, stream, ensure_ascii=False, indent=2)
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == "__main__":
    main()
