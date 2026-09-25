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


def main() -> None:
    root=Path(__file__).resolve().parents[1]
    checks=json.loads((root/"qa/checks.json").read_bytes())
    notes=json.loads((root/"qa/visual_notes.json").read_bytes())
    assert checks["status"]=="MACHINE_CHECKS_PASS_VISUAL_PENDING"
    assert set(notes["figures"])=={s.id for s in SPECS} and len(SPECS)==32
    reading=conclusions();assert set(reading)==set(notes["figures"])
    out=root/"delivery";out.mkdir(exist_ok=True)
    for name in ("figures","data","metadata"):(out/name).mkdir(exist_ok=True)
    catalogue=["# R12 三问图件说明", "", "共32张编号图：24张数据/日志证据图，8张标明性质的说明图。所有图片使用冻结R12数据或明确的规则示意，不新增求解与评分。", "",
        "- 先看 R12_32_figures.pdf 浏览全套，再从 figures/ 取单张文件。", "- 每张图均有矢量PDF、600dpi PNG与可编辑SVG；插入论文优先PDF。", "- 统一166 mm宽；普通标签至少7.8 pt，数学指数单独检查。不要把图缩到不可读。", "- 每张图的CSV为真实作图输入或明确的示意节点/关系；原始路径绑定留在内部审计，不随图包发送。", "- 这是图件交付与作者自检，不代表独立科学验收或正式提交批准。", "", "## 按论文板块选图", "", "共用F01—F04；Q1 F05—F12；Q2 F13—F21；Q3 F22—F30；综合F31—F32。", ""]
    review_rows=[]
    for spec in SPECS:
        key=spec.id;m=json.loads((root/"metadata"/f"{key}.json").read_bytes())
        checked=next(r for r in checks["records"] if r["id"]==key)
        assert m["files"]["pdf"]==checked["pdf_sha256"]==sha(root/"figures"/f"{key}.pdf")
        with Image.open(root/"figures"/f"{key}.png") as im:
            assert abs(im.info["dpi"][0]-600)<1 and abs(im.width-166/25.4*600)<2
        for extension in ("pdf","png","svg"):
            shutil.copyfile(root/"figures"/f"{key}.{extension}",out/"figures"/f"{key}.{extension}")
        shutil.copyfile(root/"data"/f"{key}.csv",out/"data"/f"{key}.csv")
        public={k:v for k,v in m.items() if k not in {"source_binding","plotted_lines"}}
        public.update(takeaway=reading[key],source_data=f"data/{key}.csv",visual_review="AUTHOR_INSPECTED",visual_note=notes["figures"][key])
        with (out/"metadata"/f"{key}.json").open("w",encoding="utf-8") as stream:json.dump(public,stream,ensure_ascii=False,indent=2)
        kind="真实数据/日志证据" if spec.kind=="evidence" else "机制说明（非实测）"
        catalogue += [f"## {key}　{spec.title}", "", f"**类别：**{kind}；**板块：**{spec.group}。", "", f"**读图问题：**{spec.question}", "", f"**可写结论：**{reading[key]}", "", f"**口径与限定：**{spec.note}", "", f"![{key}](figures/{key}.png)", "", f"[矢量PDF](figures/{key}.pdf) · [SVG](figures/{key}.svg) · [作图数据](data/{key}.csv)", ""]
        review_rows.append({"id":key,"pdf_sha256":m["files"]["pdf"],"note":notes["figures"][key]})
    catalogue += ["## 使用与披露", "", "数据来源为本队已完成的R12 full实验、官方原图与冻结时间线。C3对照不是等搜索预算消融；同方案L2配置比与分别选优比分开；COPY计账不等于命中后物理DDR净流量。", "", "图件由AI辅助整理，团队需理解、核查并按比赛规定披露。正式嵌入整篇论文后仍需检查字号、图号、题注和跨页排版。"]
    with (out/"图件说明.md").open("w",encoding="utf-8") as stream:stream.write("\n".join(catalogue)+"\n")
    shutil.copyfile(root/"R12_32_figures.pdf",out/"R12_32_figures.pdf")
    for filename in ("figure_requirements.json","visual_contract.json"):
        shutil.copyfile(root/filename,out/filename)
    with pymupdf.open(out/"R12_32_figures.pdf") as doc:assert len(doc)==32
    files=[p for p in sorted(out.rglob("*")) if p.is_file() and p.name!="MANIFEST.json"]
    forbidden=r"(?<![A-Za-z])[A-Za-z]:[\\/]|/(?:home|mnt|Users)/|Dreamboat|AGent员工"
    for path in files:
        if path.suffix in {".md",".json",".csv",".svg"}:
            assert not re.search(forbidden,path.read_text(encoding="utf-8-sig")),path.name
    hashes={p.relative_to(out).as_posix():sha(p) for p in files}
    with (out/"MANIFEST.json").open("w",encoding="utf-8") as stream:json.dump(hashes,stream,ensure_ascii=False,indent=2)
    archive=root/"R12_32_figures_share.zip"
    with zipfile.ZipFile(archive,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for path in files+[out/"MANIFEST.json"]:z.write(path,path.relative_to(out).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None and len(z.namelist())==len(hashes)+1
        import hashlib
        for name,expected in hashes.items():assert hashlib.sha256(z.read(name)).hexdigest()==expected,name
    receipt={"status":"32_FIGURES_DELIVERED_AUTHOR_CHECKED","figures":32,"evidence":24,"schematics":8,
        "files":len(hashes),"zip_bytes":archive.stat().st_size,"zip_sha256":sha(archive),"privacy_scan":"PASS",
        "independent_science_review":"NOT_PERFORMED","source_inputs_unchanged":checks["source_inputs_unchanged"],
        "visual_reviews":review_rows,"new_solver_calls":0,"new_official_scoring_calls":0}
    with (root/"DELIVERY_RECEIPT.json").open("w",encoding="utf-8") as stream:json.dump(receipt,stream,ensure_ascii=False,indent=2)
    print(json.dumps({k:v for k,v in receipt.items() if k!="visual_reviews"},ensure_ascii=False))


if __name__=="__main__":main()
