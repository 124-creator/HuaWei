# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Create the fixed 45+4+5 input inventory. Run with the existing Python."""
import hashlib
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = Path("D:/AGent员工/Agent02-数学建模工作流的打造")
TEMP = Path("C:/Users/DREAMB~1/AppData/Local/Temp/opencode")


def sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main() -> None:
    records = []
    for year, expected in ((2024, 24), (2025, 21)):
        folder = WORKSPACE / "题目/优秀论文" / f"{year}年研究生数学建模竞赛优秀论文选"
        files = sorted(folder.rglob("*.pdf"))
        assert len(files) == expected
        counters = defaultdict(int)
        for path in files:
            topic = path.name[0]
            counters[topic] += 1
            records.append({"id": f"C{str(year)[2:]}_{topic}{counters[topic]:02d}", "group": "competition",
                            "year": year, "topic": topic, "title": path.stem, "path": str(path), "columns": 1,
                            "version": "local competition reference PDF; award identity not individually verified", "url": "local corpus"})
    journals = [
        ("J_PIMCOMP", 2025, "journal_research", "PIMCOMP: An End-to-End DNN Compiler for Processing-In-Memory Accelerators", "PIMCOMP_author_v1.pdf", 2, "IEEE TCAD 44(5):1745-1759", "10.1109/TCAD.2024.3496847", "https://arxiv.org/pdf/2411.09159v1", "author version arXiv v1, 2024; journal identity verified by Crossref"),
        ("J_DNNVM", 2020, "journal_research", "DNNVM: End-to-End Compiler Leveraging Heterogeneous Optimizations on FPGA-Based CNN Accelerators", "DNNVM_author_v2.pdf", 1, "IEEE TCAD 39(10):2668-2681", "10.1109/TCAD.2019.2930577", "https://arxiv.org/pdf/1902.07463v2", "accepted author manuscript v2, 2019; not publisher pagination"),
        ("J_EYERISS", 2017, "journal_research", "Eyeriss: An Energy-Efficient Reconfigurable Accelerator for Deep Convolutional Neural Networks", "Eyeriss_JSSC.pdf", 2, "IEEE JSSC 52(1):127-138", "10.1109/JSSC.2016.2616357", "https://courses.cs.washington.edu/courses/cse550/21au/papers/CSE550.Eyeriss.pdf", "journal-layout PDF hosted by university course"),
        ("J_SURVEY", 2017, "journal_survey", "Efficient Processing of Deep Neural Networks: A Tutorial and Survey", "Sze_ProcIEEE_survey_author_v2.pdf", 2, "Proceedings of the IEEE 105(12):2295-2329", "10.1109/JPROC.2017.2761740", "https://arxiv.org/pdf/1703.09039v2", "author version v2; tutorial/survey, separate group"),
    ]
    for pid, year, group, title, name, columns, venue, doi, url, version in journals:
        records.append(dict(id=pid, year=year, group=group, topic="accelerator", title=title, path=str(ROOT / "refs" / name), columns=columns, venue=venue, doi=doi, url=url, version=version))
    for label, year, filename, title in (("alpa", 2022, "osdi22-zheng-lianmin", "Alpa"), ("welder", 2023, "osdi23-shi", "Welder"), ("ladder", 2024, "osdi24-wang-lei", "Ladder"), ("mirage", 2025, "osdi25-wu-mengdi", "Mirage"), ("syncopate", 2026, "osdi26-qiang", "Syncopate")):
        records.append(dict(id="T_" + label.upper(), year=year, group="conference", topic="scheduling", title=title,
                            path=str(TEMP / f"r12_review_{label}_20260925.pdf"), columns=2, venue=f"OSDI {year}",
                            url=f"https://www.usenix.org/system/files/{filename}.pdf", version="official USENIX proceedings PDF; includes cover"))
    for item in records:
        path = Path(item["path"])
        assert path.is_file(), path
        item["sha256"] = sha(path)
        item["bytes"] = path.stat().st_size
    assert len(records) == 54
    with (ROOT / "INPUTS.json").open("x", encoding="utf-8") as stream:
        json.dump(records, stream, ensure_ascii=False, indent=2)
    protected = {}
    for name in ("figures_v3/R12_figures_v3_share.zip", "publication/solutions/Q1.md", "publication/solutions/Q2.md", "publication/solutions/Q3.md"):
        p = ROOT.parent / name
        protected[str(p)] = sha(p)
    with (ROOT / "PROTECTED.json").open("x", encoding="utf-8") as stream:
        json.dump(protected, stream, ensure_ascii=False, indent=2)
    print(json.dumps({"papers": len(records), "input_bytes": sum(x["bytes"] for x in records), "protected_R12_files": len(protected)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
