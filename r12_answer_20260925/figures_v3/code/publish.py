# /// script
# requires-python = ">=3.12"
# dependencies = ["pymupdf", "Pillow"]
# ///
"""Existing Python: publish.py. Package only reviewed, path-free figure assets."""
import json
import re
import shutil
import zipfile
from pathlib import Path

import pymupdf
from PIL import Image
from captions import conclusions
from specs import SPECS
from verify import sha
from version_guard import check as check_previous_version
from answers import verify_answers


def main() -> None:
    root=Path(__file__).resolve().parents[1]
    check_previous_version()
    verify_answers()
    checks=json.loads((root/"qa/checks.json").read_bytes())
    notes=json.loads((root/"qa/visual_notes.json").read_bytes())
    assert checks["status"]=="MACHINE_CHECKS_PASS_VISUAL_PENDING"
    assert set(notes["figures"])=={s.id for s in SPECS} and len(SPECS)==34
    reading=conclusions();assert set(reading)==set(notes["figures"])
    out=root/"delivery";out.mkdir(exist_ok=True)
    for name in ("figures","data","metadata"):(out/name).mkdir(exist_ok=True)
    catalogue=["# R12 三问图件说明 v3", "", "共34张编号图：24张数据/日志证据图，10张结构/机制说明图。本轮新增2张方法图、更新5张证据图，其余27张逐字节沿用v2。没有新增算法控制流程图。", "",
        "- 先读 README.md 和 answers/ 下三问图文版；23张图接入正文，11张作为补充证据。", "- 重点优化7图.pdf 汇总本轮变化，R12_figures_v3.pdf 提供完整图册。", "- 每图提供PDF、600dpi PNG、SVG与CSV；插入论文优先PDF。", "- 统一166 mm宽，普通标签至少7.8 pt；数学上下标单独检查，最终排版不可缩到不可读。", "- 原始路径绑定留在内部，不随共享包发送。", "- 参考与改动说明.md 说明文献借鉴，SKILL_REFERENCES.md保留高星技能核验记录。", "- 作者自检不等于独立科学验收或正式提交批准。", "", "## 按论文板块选图", "", "共用F01—F04；Q1 F05—F12及F33—F34；Q2 F13—F21；Q3 F22—F30；综合F31—F32。", ""]
    review_rows=[]
    for spec in SPECS:
        key=spec.id;m=json.loads((root/"metadata"/f"{key}.json").read_bytes())
        checked=next(r for r in checks["records"] if r["id"]==key)
        assert m["files"]["pdf"]==checked["pdf_sha256"]==sha(root/"figures"/f"{key}.pdf")
        assert notes["pdf_hashes"][key]==m["files"]["pdf"], (key,"stale visual review")
        with Image.open(root/"figures"/f"{key}.png") as im:
            assert abs(im.info["dpi"][0]-600)<1 and abs(im.width-166/25.4*600)<2
        for extension in ("pdf","png","svg"):
            shutil.copyfile(root/"figures"/f"{key}.{extension}",out/"figures"/f"{key}.{extension}")
        shutil.copyfile(root/"data"/f"{key}.csv",out/"data"/f"{key}.csv")
        public={k:v for k,v in m.items() if k not in {"source_binding","plotted_lines","plotted_images","plotted_scatter","axis_views"}}
        public.update(takeaway=reading[key],source_data=f"data/{key}.csv",visual_review="AUTHOR_INSPECTED",visual_note=notes["figures"][key])
        with (out/"metadata"/f"{key}.json").open("w",encoding="utf-8") as stream:json.dump(public,stream,ensure_ascii=False,indent=2)
        kind="真实数据/日志证据" if spec.kind=="evidence" else "机制说明（非实测）"
        catalogue += [f"## {key}　{spec.title}", "", f"**类别：**{kind}；**板块：**{spec.group}。", "", f"**读图问题：**{spec.question}", "", f"**可写结论：**{reading[key]}", "", f"**口径与限定：**{spec.note}", "", f"![{key}](figures/{key}.png)", "", f"[矢量PDF](figures/{key}.pdf) · [SVG](figures/{key}.svg) · [作图数据](data/{key}.csv)", ""]
        review_rows.append({"id":key,"pdf_sha256":m["files"]["pdf"],"note":notes["figures"][key]})
    catalogue += ["## 使用与披露", "", "数据来源为本队已完成的R12 full实验、官方原图与冻结时间线。C3对照不是等搜索预算消融；同方案L2配置比与分别选优比分开；COPY计账不等于命中后物理DDR净流量。", "", "图件由AI辅助整理，团队需理解、核查并按比赛规定披露。正式嵌入整篇论文后仍需检查字号、图号、题注和跨页排版。"]
    with (out/"图件说明.md").open("w",encoding="utf-8") as stream:stream.write("\n".join(catalogue)+"\n")
    shutil.copyfile(out/"图件说明.md",root/"图件说明.md")
    shutil.copyfile(root/"R12_figures_v3.pdf",out/"R12_figures_v3.pdf")
    with pymupdf.open() as focus:
        for key in notes["freshly_reviewed"]:
            with pymupdf.open(root/"figures"/f"{key}.pdf") as source:
                focus.insert_pdf(source)
        focus.save(out/"重点优化7图.pdf",garbage=4,deflate=True)
    for name in ("SKILL_REFERENCES.md","README.md","参考与改动说明.md","图文映射.md"):
        shutil.copyfile(root/name,out/name)
    for folder in ("answers","tables"):
        shutil.copytree(root/folder,out/folder,dirs_exist_ok=True)
    for filename in ("figure_requirements.json","visual_contract.json"):
        shutil.copyfile(root/filename,out/filename)
    with pymupdf.open(out/"R12_figures_v3.pdf") as doc:assert len(doc)==34
    with pymupdf.open(out/"重点优化7图.pdf") as doc:assert len(doc)==7
    files=[p for p in sorted(out.rglob("*")) if p.is_file() and p.name!="MANIFEST.json"]
    forbidden=r"(?<![A-Za-z])[A-Za-z]:[\\/]|/(?:home|mnt|Users)/|Dreamboat|AGent员工"
    for path in files:
        if path.suffix in {".md",".json",".csv",".svg"}:
            assert not re.search(forbidden,path.read_text(encoding="utf-8-sig")),path.name
        if path.suffix==".md":
            for target in re.findall(r"!?\[[^\]]*\]\(([^)]+)\)",path.read_text(encoding="utf-8")):
                if target.startswith(("https://","http://","#")):continue
                destination=(path.parent/target.split("#")[0]).resolve()
                assert destination.is_relative_to(out) and destination.is_file(),(path.name,target)
    hashes={p.relative_to(out).as_posix():sha(p) for p in files}
    with (out/"MANIFEST.json").open("w",encoding="utf-8") as stream:json.dump(hashes,stream,ensure_ascii=False,indent=2)
    archive=root/"R12_figures_v3_share.zip"
    with zipfile.ZipFile(archive,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for path in files+[out/"MANIFEST.json"]:z.write(path,path.relative_to(out).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None and len(z.namelist())==len(hashes)+1
        import hashlib
        for name,expected in hashes.items():assert hashlib.sha256(z.read(name)).hexdigest()==expected,name
    receipt={"status":"V3_FIGURES_AND_ANSWERS_DELIVERED_AUTHOR_CHECKED","figures":34,"evidence":24,"schematics":10,
        "files":len(hashes),"zip_bytes":archive.stat().st_size,"zip_sha256":sha(archive),"privacy_scan":"PASS",
        "independent_science_review":"NOT_PERFORMED","source_inputs_unchanged":checks["source_inputs_unchanged"],
        "visual_reviews":review_rows,"revised_figures":notes["freshly_reviewed"],"unchanged_figures":notes["inherited_review"],
        "answer_integration":json.loads((root/"qa/answer_check.json").read_bytes()),
        "new_solver_calls":0,"new_official_scoring_calls":0,"github_references":"SKILL_REFERENCES.md"}
    with (root/"DELIVERY_RECEIPT.json").open("w",encoding="utf-8") as stream:json.dump(receipt,stream,ensure_ascii=False,indent=2)
    print(json.dumps({k:v for k,v in receipt.items() if k!="visual_reviews"},ensure_ascii=False))


if __name__=="__main__":main()
