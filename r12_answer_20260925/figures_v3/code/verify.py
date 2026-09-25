# /// script
# requires-python = ">=3.12"
# dependencies = ["pymupdf==1.28.2", "pytest"]
# ///
"""Existing Python: verify.py. Render every PDF and validate source-bound data.

AI-assisted: OpenCode/Sisyphus, OpenAI; no independent science acceptance claim.
"""
import csv
import hashlib
import io
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from statistics import mean, median
from v3_data import cache_marker
from answers import verify_answers

import pymupdf
from specs import SPECS
from version_guard import check as check_previous_version


def sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream,"sha256").hexdigest()


def main() -> None:
    root=Path(__file__).resolve().parents[1];qa=root/"qa";qa.mkdir(exist_ok=True)
    check_previous_version()
    d=json.loads((root/"dataset.json").read_bytes())
    protected=json.loads((root/"INPUTS.json").read_bytes())
    for path,expected in protected.items():assert sha(Path(path))==expected,path
    expected_rows={"F03":d["graphs"],"F04":d["graphs"],"F09":d["plansA"],"F11":d["plansA"],"F12":d["timelineA"],
                   "F19":d["stages"],"F21":d["stages"],"F24":d["pairs"],"F25":d["pairs"],"F27":d["cache"],
                   "F31":d["selected"],"F32":d["selected"]}
    a=[r for r in d["selected"] if r["scene"]=="A"];b=[r for r in d["selected"] if r["scene"]=="B"]
    b5=[r for r in b if r["k"]==5]
    for key in ("F07","F08","F10"):expected_rows[key]=a
    for key in ("F15","F17"):expected_rows[key]=b
    expected_rows.update({"F16":sorted([r for r in b if r["k"]==1],key=lambda r:(r["speedup"],r["case"])),
        "F18":sorted(b5,key=lambda r:(-r["spill"],r["case"])),"F20":b5,
        "F26":[r for r in d["pairs"] if r["k"]==5],
        "F28":[{"configuration":"B",**r} for r in d["timelineB"]]+[{"configuration":"L2_same_B",**r} for r in d["timelineL2"]],
        "F29":sorted([r for r in d["pairs"] if r["k"]==5 and r["different"]],key=lambda r:r["case"]),
        "F30":sorted([r for r in d["pairs"] if r["hardware"]<1],key=lambda r:(r["k"],r["case"]))})
    combined=pymupdf.open();records=[]
    for spec in SPECS:
        key=spec.id;m=json.loads((root/"metadata"/f"{key}.json").read_bytes())
        assert m["kind"]==spec.kind and m["minimum_source_font_pt"]>=7.8 and not m["clipped_text"]
        data_path=root/"data"/f"{key}.csv";assert sha(data_path)==m["data_sha256"]
        if key in expected_rows:
            rows=expected_rows[key];text=io.StringIO(newline="")
            fields=list(dict.fromkeys(k for r in rows for k in r))
            writer=csv.DictWriter(text,fieldnames=fields);writer.writeheader();writer.writerows(rows)
            assert hashlib.sha256(text.getvalue().encode("utf-8-sig")).hexdigest()==m["data_sha256"],key
        for ext,value in m["files"].items():assert sha(root/"figures"/f"{key}.{ext}")==value
        for curve_key,scene in (("F07","A"),("F15","B")):
            if key==curve_key:
                expected=[1]+[mean(r["speedup"] for r in d["selected"] if r["scene"]==scene and r["k"]==k) for k in range(2,6)]
                assert m["plotted_lines"][0]["y"]==expected
        if key=="F24":
            actual=[line for line in m["plotted_lines"] if line["label"]=="同方案配置比"][0]["y"]
            expected=[mean(r["hardware"] for r in d["pairs"] if r["k"]==k) for k in range(1,6)]
            assert actual==expected
            curves=[line for line in m["plotted_lines"] if line["axis"]==0]
            for line,field in zip(curves,("B","L2_fixed","L2_best")):
                assert line["y"]==[mean(r["REF"]/r[field] for r in d["pairs"] if r["k"]==k) for k in range(1,6)]
            assert len(curves)==3
        if key=="F21":
            changed=[r for r in d["stages"] if r["full"]<r["indexed"]]
            assert len(changed)==2 and len(m["plotted_lines"])==2
            for curve,row in zip(m["plotted_lines"],changed):
                assert curve["y"]==[row[k]/row["control"] for k in ("control","indexed","full")]
        if key=="F25":
            values=[r["hardware"] for r in d["pairs"] if r["k"]==5]
            curves=[line for line in m["plotted_lines"] if line["axis"]==1]
            ecdf=curves[0]
            assert ecdf["y"][0]==0 and ecdf["y"][-1]==1
            for x,y in zip(ecdf["x"][1:],ecdf["y"][1:]):
                assert abs(y-sum(v<=x for v in values)/100)<1e-12
            assert next(line for line in curves if line["label"]=="中位数")["x"]==[median(values)]*2
            assert next(line for line in curves if line["label"]=="均值")["x"]==[mean(values)]*2
        if key=="F19":
            expected=[mean(r["REF"]/r[stage] for r in d["stages"]) for stage in ("control","indexed","full")]
            assert m["plotted_lines"][0]["y"]==expected
        if key=="F08":
            import numpy as np
            expected=np.array([[np.log2(r["versus_C3"]) for r in sorted([r for r in a if r["k"]==k],key=lambda r:r["case"])] for k in range(2,6)])
            assert np.array_equal(m["plotted_images"][0]["values"],expected)
            negative={(int(r["case"].split("_")[-1]),r["k"]) for r in a if r["T"]>r["C3_T"]}
            assert {tuple(point) for point in m["plotted_scatter"][0]["xy"]}==negative
        if key=="F18":
            import numpy as np
            spill=np.array(sorted([r["spill"] for r in b5],reverse=True),dtype=float)
            assert m["plotted_lines"][0]["y"]==(spill[spill>0]/1048576).tolist()
            assert m["plotted_lines"][1]["y"]==np.r_[0,np.cumsum(spill)/spill.sum()*100].tolist()
        if key=="F28":
            views=m["axis_views"]
            assert len(views)==4 and views[0]["xlim"]==views[1]["xlim"]
            assert views[2]["xlim"]==views[3]["xlim"]==[.9,1.2]
        if key=="F27":
            assert m["plotted_lines"][0]["y"]==[r["used"]/1048576 for r in d["cache"]]
            cumulative=[line for line in m["plotted_lines"] if line["axis"]==1][0]
            assert cumulative["y"]==[100*r["cumulative_hit"] for r in d["cache"]]
        if key in {"F27","F28"}:
            marked=[line for line in m["plotted_lines"] if line["label"]=="cache_event"]
            assert len(marked)==2
            assert all(line["x"]==[cache_marker().time/1e6]*2 for line in marked)
        with pymupdf.open(root/"figures"/f"{key}.pdf") as doc:
            assert len(doc)==1 and abs(doc[0].rect.width/72*25.4-166)<.05
            page=doc[0];content=page.get_text();assert "\ufffd" not in content and key in content
            page.get_pixmap(matrix=pymupdf.Matrix(2,2),alpha=False).save(qa/f"{key}.png")
            combined.insert_pdf(doc)
            small=[{"text":s["text"],"size":s["size"]} for block in page.get_text("dict")["blocks"] if "lines" in block for line in block["lines"] for s in line["spans"] if s["text"].strip() and s["size"]<7.79]
            records.append({"id":key,"pdf_sha256":m["files"]["pdf"],"source_font_min":m["minimum_source_font_pt"],
                            "small_pdf_spans_for_math_review":small,"capture":f"qa/{key}.png"})
    combined.save(root/"R12_figures_v3.pdf",garbage=4,deflate=True);combined.close()
    tests=subprocess.run([sys.executable,"-X","utf8","-B","-m","pytest","-p","no:cacheprovider",str(root/"code"),"-q"],capture_output=True,text=True,encoding="utf-8",check=False)
    assert tests.returncode==0,tests.stdout+tests.stderr
    for p in (root/"code").glob("*.py"):
        code=p.read_text(encoding="utf-8");compile(code,str(p),"exec")
        assert sum(bool(x.strip()) and not x.lstrip().startswith("#") for x in code.splitlines())<=250,p
    verify_answers()
    out={"status":"MACHINE_CHECKS_PASS_VISUAL_PENDING","figures":len(records),"kinds":dict(Counter(s.kind for s in SPECS)),
         "source_inputs_unchanged":len(protected),"evidence_CSV_exact_checks":len(expected_rows),"tests":tests.stdout,
         "records":records,"scientific_review":"NOT_INDEPENDENTLY_PERFORMED","solver_calls":0,"official_scoring_calls":0,
         "lsp":"Not installed; no installation performed"}
    with (qa/"checks.json").open("w",encoding="utf-8") as stream:json.dump(out,stream,ensure_ascii=False,indent=2)
    print(json.dumps({k:v for k,v in out.items() if k!="records"},ensure_ascii=False))
    print("PDF_SPANS_BELOW_7_8",json.dumps({r["id"]:r["small_pdf_spans_for_math_review"] for r in records if r["small_pdf_spans_for_math_review"]},ensure_ascii=False))


if __name__=="__main__":main()
