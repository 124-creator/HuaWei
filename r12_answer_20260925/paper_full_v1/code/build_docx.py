# 本程序及代码是在人工智能工具辅助下完成的。
# 人工智能工具名称、版本/型号、开发机构/公司、版本发布日期：【由参赛队按实际使用情况填写，见论文附录D】
"""把合稿中间件转成Word稿：按官方《论文格式规范》（附件2）与论文模板（附件3）排版。

封面与摘要页取自官方模板（template/附件3_论文模板_转docx.docx）；页码自摘要页起为1、位于页脚中部，无页眉；
题目三号黑体，一级标题四号黑体居中，其余汉字小四号宋体，单倍行距；另做三线表、公式右对齐编号、图题表题。
依赖：pypandoc-binary（pandoc 3.x）、python-docx、Pillow。输出 ../out/R12论文_v1.docx。
figures_v3 图片顶部带内部图号标题、底部带一行口径注记，这里裁掉这两条文字带后再嵌入（原图不改）；
口径注记的内容在正文相应段落中已有交代。
"""
from __future__ import annotations

import copy
import io
import re
import subprocess
from pathlib import Path

import pypandoc
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.text.paragraph import Paragraph
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.table import Table
from docx.shared import Cm, Pt
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = ROOT / "out"
FIGDIR = OUT / "fig"
M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
TITLE = "基于可证下界与结构化搜索的多核NPU切图调度"
# 封面信息表（模板第0页）；参赛队号为空时留空，由队员在正式提交前补填
SCHOOL = "郑州航空工业管理学院"
TEAM_NO = ""
MEMBERS = ["田中斐", "安镕基", "王玥"]
TEMPLATE = ROOT / "template" / "附件3_论文模板_转docx.docx"
TEXT_W = 16.5          # 版心宽度（cm）：A4宽21 cm减去模板左右边距各2.25 cm


def crop_title_band(src: Path, dst: Path) -> None:
    """裁掉图片顶部的标题行：找到第一段非白行及其后的空白间隔，从间隔处开始保留。"""
    im = Image.open(src).convert("RGB")
    w, h = im.size
    gray = im.convert("L")
    px = gray.load()
    step = max(1, w // 400)
    def dark(y):
        return any(px[x, y] < 200 for x in range(0, w, step))
    y = 0
    while y < h * 0.12 and not dark(y):
        y += 1
    top_text = y
    while y < h * 0.15 and dark(y):
        y += 1
    if top_text < h * 0.12 and y < h * 0.15:
        gap_start = y
        while y < h * 0.2 and not dark(y):
            y += 1
        cut = max(gap_start, y - int(0.01 * h))
        im = im.crop((0, cut, w, h))
    im = crop_note_band(im, h)
    dst.parent.mkdir(parents=True, exist_ok=True)
    im.save(dst, dpi=(600, 600))


def crop_note_band(im, h0):
    """裁掉图片底部的一行口径注记：自下而上找到最后一段文字带（允许标点下沿的细小断开）及其上方的空白间隔。
    文字带高度不超过原图高度的4.5%、上方空白不少于0.4%时才裁，否则原样返回。"""
    w, h = im.size
    px = im.convert("L").load()
    step = max(1, w // 400)
    def dark(y):
        return any(px[x, y] < 200 for x in range(0, w, step))
    min_gap = 0.004 * h0
    y = h - 1
    while y > h * 0.8 and not dark(y):
        y -= 1
    band_bottom = top = y
    gap = 0
    while y > h * 0.8:
        if dark(y):
            top = y; y -= 1; continue
        run_start = y
        while y > h * 0.75 and not dark(y):
            y -= 1
        gap = run_start - y
        if gap >= min_gap:
            break
    if band_bottom - top <= 0.045 * h0 and gap >= min_gap:
        keep = y + 1 + int(min(gap, 0.02 * h0) * 0.6)
        return im.crop((0, 0, w, keep))
    return im


def word_compat(m: str) -> str:
    """公式兼容改写（只用于docx）：保证Word与LibreOffice/WPS的OMML渲染一致。
    源稿保留标准LaTeX（Typora/MathJax可直接渲染），这里只替换几种OMML导入易出错的写法。"""
    m = m.replace("\\setminus", "\\smallsetminus")
    m = re.sub(r"\^\{?\\ast\}?|\^\{\*\}|\^\*", r"^{\\text{*}}", m)
    m = re.sub(r"([_^])\{([+\-])\}", lambda g: g.group(1) + "{\\text{" + ("+" if g.group(2) == "+" else "−") + "}}", m)
    m = m.replace("\\lvert", "\\left|").replace("\\rvert", "\\right|")
    m = m.replace("\\left|", "\x00L").replace("\\right|", "\x00R")
    m = re.sub(r"\|([^|\x00]+?)\|", lambda g: "\\left|" + g.group(1) + "\\right|", m)
    m = m.replace("\x00L", "\\left|").replace("\x00R", "\\right|")
    m = re.sub(r"\\#\s*(\\left\\\{.*?\\right\\\}|\\\{.*?\\\})", lambda g: "\\left|" + g.group(1) + "\\right|", m)
    m = re.sub(r"\\text\{([^{}]*)\}", lambda g: "\\text{" + g.group(1).replace("(", "（").replace(")", "）") + "}", m)
    return m


def compat_math(text: str) -> str:
    parts = re.split(r"(```.*?```)", text, flags=re.S)
    out = []
    for part in parts:
        if part.startswith("```"):
            out.append(part); continue
        part = re.sub(r"\$\$(.+?)\$\$", lambda g: "$$" + word_compat(g.group(1)) + "$$", part, flags=re.S)
        part = re.sub(r"(?<![\$\\])\$([^$\n]+?)\$(?!\$)", lambda g: "$" + word_compat(g.group(1)) + "$", part)
        out.append(part)
    return "".join(out)


def prepare_markdown() -> Path:
    text = compat_math((OUT / "_pandoc_input.md").read_text(encoding="utf-8"))
    def repl(m):
        src = Path(m.group(1))
        dst = FIGDIR / src.name
        if "figures_v3" in src.as_posix():
            crop_title_band(src, dst)
        else:
            Image.open(src).save(dst, dpi=(600, 600))
        return f"![]({dst.as_posix()}){{width=15.5cm}}"
    text = re.sub(r"!\[\]\(([^)]+)\)\{width=15\.5cm\}", repl, text)
    # Word中多字母\mathrm按字母拆分，统一改为\text以保持正体整词
    text = re.sub(r"\\mathrm\{([A-Za-z][A-Za-z ]+)\}", r"\\text{\1}", text)
    text = text.replace("{width=15.5cm}", "{width=14cm}")
    path = OUT / "_pandoc_ready.md"
    path.write_text(text, encoding="utf-8")
    return path


def set_run_fonts(style, east="宋体", west="Times New Roman", size=None, bold=None):
    style.font.name = west
    rpr = style.element.get_or_add_rPr()
    fonts = rpr.get_or_add_rFonts()
    for attr in ("w:ascii", "w:hAnsi", "w:cs"):
        fonts.set(qn(attr), west)
    fonts.set(qn("w:eastAsia"), east)
    if size:
        style.font.size = Pt(size)
    if bold is not None:
        style.font.bold = bold


def reference_doc() -> Path:
    ref = OUT / "_reference.docx"
    data = subprocess.run([pypandoc.get_pandoc_path(), "--print-default-data-file", "reference.docx"],
                          capture_output=True, check=True).stdout
    ref.write_bytes(data)
    doc = Document(ref)
    st = doc.styles
    # 附件2：其余汉字一律小四号（12 pt）宋体，单倍行距
    for name in ("Normal", "Body Text", "First Paragraph", "Compact", "Block Text"):
        if name in [s.name for s in st]:
            set_run_fonts(st[name], size=12)
            pf = st[name].paragraph_format
            pf.line_spacing = 1.0; pf.space_before = Pt(0); pf.space_after = Pt(0)
    # 附件2：一级标题四号（14 pt）黑体并居中；二、三级标题按“其余汉字”取小四号宋体，加粗以示层级
    for lvl, size, east, bold in ((1, 14, "黑体", False), (2, 12, "宋体", True), (3, 12, "宋体", True), (4, 12, "宋体", True)):
        s = st[f"Heading {lvl}"]
        set_run_fonts(s, east=east, west="Times New Roman", size=size, bold=bold)
        s.font.color.rgb = None
        s.font.italic = False
        s.paragraph_format.line_spacing = 1.0
        s.paragraph_format.space_before = Pt(12 if lvl == 1 else 6)
        s.paragraph_format.space_after = Pt(6 if lvl == 1 else 3)
        if lvl == 1:
            s.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for name in ("Title", "Subtitle"):
        if name in [s.name for s in st]:
            set_run_fonts(st[name], east="黑体", size=18, bold=True)
    doc.save(ref)
    return ref


def number_equations(doc) -> int:
    body = doc.element.body
    n = 0
    for p in list(body.iter(qn("w:p"))):
        text = "".join(t.text or "" for t in p.iter(qn("w:t")))
        m = re.fullmatch(r"EQNO\(([^)]+)\)", text.strip())
        if not m:
            continue
        prev = p.getprevious()
        para = prev.find(f"{{{M_NS}}}oMathPara") if prev is not None else None
        if prev is None or para is None:
            raise SystemExit(f"公式编号 {m.group(1)} 前没有展示公式")
        omath = para.find(f"{{{M_NS}}}oMath")
        prev.remove(para)
        pf = Paragraph(prev, doc._body).paragraph_format
        pf.tab_stops.add_tab_stop(Cm(TEXT_W / 2), WD_TAB_ALIGNMENT.CENTER)
        pf.tab_stops.add_tab_stop(Cm(TEXT_W), WD_TAB_ALIGNMENT.RIGHT)
        pf.first_line_indent = Cm(0)
        def run_tab():
            r = OxmlElement("w:r"); r.append(OxmlElement("w:tab")); return r
        prev.append(run_tab())
        prev.append(omath)
        r = run_tab()
        t = OxmlElement("w:t"); t.text = f"({m.group(1)})"; r.append(t)
        prev.append(r)
        p.getparent().remove(p)
        n += 1
    return n


def border(tag, sz):
    b = OxmlElement(f"w:{tag}")
    b.set(qn("w:val"), "single" if sz else "nil"); b.set(qn("w:sz"), str(sz)); b.set(qn("w:space"), "0"); b.set(qn("w:color"), "000000")
    return b


def text_em(s: str) -> float:
    """估计一段文字的排版宽度（以字号为1个em）：汉字与全角标点1 em，Times New Roman数字0.5 em、字母约0.55 em。"""
    def w(ch):
        if ord(ch) >= 0x2E80:
            return 1.0
        if ch.isspace():
            return 0.25
        return 0.5 if ch.isdigit() or ch in ".,:;%+-()−/" else 0.55
    return sum(w(ch) for ch in s)


def fit_columns(table, size_pt: float) -> None:
    """按单元格内容分配列宽并铺满版心：各列取所需宽度（长文字列封顶16 em，允许折行），
    放不下时优先压缩长文字列；数字、西文词、公式与不超过5个字宽的短单元格不折行；
    表头在空格处折行。pandoc给的列宽按源稿横线长度，不可靠。"""
    tbl = table._tbl
    grid = tbl.find(qn("w:tblGrid"))
    ncol = len(grid.findall(qn("w:gridCol")))
    rows = tbl.findall(qn("w:tr"))
    def cell_text(tc):
        return "".join(x.text or "" for x in tc.iter() if x.tag in (qn("w:t"), f"{{{M_NS}}}t")).strip()
    need, fb, fh = [0.0] * ncol, [0.0] * ncol, [0.0] * ncol     # 所需宽度；表体下限；表头下限
    for i, tr in enumerate(rows):
        for j, tc in enumerate(tr.findall(qn("w:tc"))[:ncol]):
            t = cell_text(tc)
            w = text_em(t)
            need[j] = max(need[j], min(w, 16.0))
            # 不可断开的单位：数字、西文词连同紧贴的全角括号与标点（LibreOffice会在其内部硬断）
            words = re.findall(r"[（(]?[A-Za-z0-9_.,%+\-−=()/]+[）)，、；。]?", t)
            fb[j] = max(fb[j], min(max((text_em(x) for x in words), default=0.0), 10.0))
            if i == 0:                                  # 表头：不超过5个字宽不折行；更长的在空格处折行，否则至少留4个字宽
                segs = t.split()
                fh[j] = w if w <= 5.0 else min(max(text_em(x) for x in segs), 6.0) if len(segs) > 1 else 4.0
            elif w <= 5.0:
                fb[j] = max(fb[j], w)
    em = size_pt * 20                                  # 1 em对应的twips
    pad = 1.0                                          # 左右单元格边距各108 twips（约0.9 em），另留0.1 em余量
    avail = 11906 - 1276 - 1274                        # 版心宽度（twips）
    floor = [(max(b, h) + pad) * em for b, h in zip(fb, fh)]
    if sum(floor) > avail:                             # 放不下时按同一比例压缩表头下限（表头多折行），保住表体不折行
        lo, hi = 0.0, 1.0
        for _ in range(30):
            a = (lo + hi) / 2
            if sum((max(b, a * h) + pad) * em for b, h in zip(fb, fh)) > avail:
                hi = a
            else:
                lo = a
        floor = [(max(b, lo * h) + pad) * em for b, h in zip(fb, fh)]
    need = [max(n + pad, 0) * em for n in need]
    need = [max(n, f) for n, f in zip(need, floor)]
    total, fl = sum(need), sum(floor)
    if total <= avail:
        widths = [n * avail / total for n in need]
    elif fl >= avail:
        widths = [f * avail / fl for f in floor]
    else:
        widths = [f + (n - f) * (avail - fl) / (total - fl) for n, f in zip(need, floor)]
    widths = [int(w) for w in widths]
    tblpr = tbl.tblPr
    for tag in ("w:tblW", "w:tblLayout"):
        for old in tblpr.findall(qn(tag)):
            tblpr.remove(old)
    tw = OxmlElement("w:tblW"); tw.set(qn("w:w"), str(sum(widths))); tw.set(qn("w:type"), "dxa"); tblpr.append(tw)
    lay = OxmlElement("w:tblLayout"); lay.set(qn("w:type"), "fixed"); tblpr.append(lay)
    for gc, w in zip(grid.findall(qn("w:gridCol")), widths):
        gc.set(qn("w:w"), str(w))
    for i, tr in enumerate(rows):
        for tc, w in zip(tr.findall(qn("w:tc")), widths):
            tcpr = tc.get_or_add_tcPr()
            for old in tcpr.findall(qn("w:tcW")):
                tcpr.remove(old)
            cw = OxmlElement("w:tcW"); cw.set(qn("w:w"), str(w)); cw.set(qn("w:type"), "dxa"); tcpr.insert(0, cw)
            if i == 0 and (text_em(cell_text(tc)) + pad) * em > w:
                for t in tc.iter(qn("w:t")):            # 放不下的表头在第一个空格处换行（pandoc常把空格单独成一段文字）
                    if t.text and not t.text.strip():
                        t.addnext(OxmlElement("w:br")); t.text = ""
                        break
                    if t.text and " " in t.text.strip():
                        a, b = t.text.strip().split(" ", 1)
                        t.text = a
                        br = OxmlElement("w:br"); t.addnext(br)
                        t2 = OxmlElement("w:t"); t2.text = b; t2.set(qn("xml:space"), "preserve"); br.addnext(t2)
                        break


def keep_table(table, long_table: bool) -> None:
    """短表整表不跨页（除末行外各行段落“与下段同页”）；长表允许跨页，表头行在每页重复。行内一律不断开。"""
    rows = table._tbl.findall(qn("w:tr"))
    for i, tr in enumerate(rows):
        trpr = tr.find(qn("w:trPr"))
        if trpr is None:
            trpr = OxmlElement("w:trPr"); tr.insert(0, trpr)
        if trpr.find(qn("w:cantSplit")) is None:
            trpr.append(OxmlElement("w:cantSplit"))
        if i == 0 and long_table and trpr.find(qn("w:tblHeader")) is None:
            trpr.append(OxmlElement("w:tblHeader"))
        if not long_table and i < len(rows) - 1:
            for p in tr.iter(qn("w:p")):
                Paragraph(p, table._parent).paragraph_format.keep_with_next = True


def three_line(table, small=False) -> None:
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    tblpr = table._tbl.tblPr
    for old in tblpr.findall(qn("w:tblBorders")):
        tblpr.remove(old)
    borders = OxmlElement("w:tblBorders")
    for tag, sz in (("top", 12), ("left", 0), ("bottom", 12), ("right", 0), ("insideH", 0), ("insideV", 0)):
        borders.append(border(tag, sz))
    tblpr.append(borders)
    jc = tblpr.find(qn("w:jc"))
    if jc is None:
        jc = OxmlElement("w:jc"); tblpr.append(jc)
    jc.set(qn("w:val"), "center")
    header = table.rows[0]
    for cell in header.cells:
        tcpr = cell._tc.get_or_add_tcPr()
        for old in tcpr.findall(qn("w:tcBorders")):
            tcpr.remove(old)
        tb = OxmlElement("w:tcBorders"); tb.append(border("bottom", 4)); tcpr.append(tb)
    size = Pt(10.5 if small else 12)       # 正文表格小四号；附录逐例长表取五号，见README说明
    for row in table.rows:
        for cell in row.cells:
            for par in cell.paragraphs:
                par.paragraph_format.first_line_indent = Cm(0)
                par.paragraph_format.line_spacing = 1.0
                par.alignment = WD_ALIGN_PARAGRAPH.CENTER
                for run in par.runs:
                    run.font.size = size
    for cell in header.cells:
        for par in cell.paragraphs:
            for run in par.runs:
                run.font.bold = True
    fit_columns(table, 10.5 if small else 12)
    keep_table(table, long_table=len(table.rows) > 25)


def algorithm_boxes(doc) -> int:
    """算法块排成三线框：标题行上粗线、下细线，块末粗线；标题与算法体同页，算法体不拆行。"""
    pars = doc.paragraphs
    n = 0
    for i, par in enumerate(pars):
        if not re.match(r"^算法\d+-\d+\s", par.text.strip()):
            continue
        j = i + 1
        while j < len(pars) and pars[j].style.name == "Block Text":
            j += 1
        block = pars[i + 1:j]
        if not block:
            continue
        def rule(p, top=None, bottom=None):
            ppr = p._element.get_or_add_pPr()
            bdr = OxmlElement("w:pBdr")
            if top: bdr.append(border("top", top))
            if bottom: bdr.append(border("bottom", bottom))
            for b in bdr:
                b.set(qn("w:space"), "1")
            ppr.append(bdr)
        rule(par, top=12, bottom=4)
        rule(block[-1], bottom=12)
        par.paragraph_format.first_line_indent = Cm(0)
        par.paragraph_format.keep_with_next = True
        par.paragraph_format.space_before = Pt(6)
        for k, p in enumerate(block):
            pf = p.paragraph_format
            pf.left_indent = Cm(0); pf.right_indent = Cm(0); pf.first_line_indent = Cm(0)
            pf.space_before = Pt(0); pf.space_after = Pt(0)
            pf.keep_together = True
            if k < len(block) - 1:
                pf.keep_with_next = True
        block[-1].paragraph_format.space_after = Pt(6)
        n += 1
    return n


def style_paragraphs(doc) -> None:
    for par in doc.paragraphs:
        name = par.style.name
        txt = par.text.strip()
        if name in ("表题", "图题"):
            par.alignment = WD_ALIGN_PARAGRAPH.CENTER
            par.paragraph_format.first_line_indent = Cm(0)
            if name == "表题":                      # 表题与表格同页
                par.paragraph_format.keep_with_next = True
            par.paragraph_format.space_before = Pt(3 if name == "表题" else 0)
            par.paragraph_format.space_after = Pt(3 if name == "表题" else 6)
            for run in par.runs:
                run.font.size = Pt(12); run.font.bold = True
                rf = run._element.get_or_add_rPr().get_or_add_rFonts()
                rf.set(qn("w:eastAsia"), "宋体")
            continue
        has_img = bool(par._element.findall(".//" + qn("w:drawing")))
        if has_img:
            par.alignment = WD_ALIGN_PARAGRAPH.CENTER
            par.paragraph_format.first_line_indent = Cm(0)
            par.paragraph_format.keep_with_next = True   # 图与图题同页
            continue
        if name.startswith("Heading"):
            if txt in ("1 问题重述", "参考文献", "附录"):
                par.paragraph_format.page_break_before = True
            continue
        if not txt:
            continue
        if par._element.find(f".//{{{M_NS}}}oMath") is not None and par._element.find(qn("w:pPr") + "/" + qn("w:tabs")) is not None:
            continue
        if re.match(r"^\[\d+\] ", txt):          # 参考文献条目：悬挂缩进
            par.paragraph_format.left_indent = Cm(0.9)
            par.paragraph_format.first_line_indent = Cm(-0.9)
            continue
        if name in ("Body Text", "First Paragraph", "Normal"):
            par.paragraph_format.first_line_indent = Cm(0.85)


ORDER = {
    "pPr": ["pStyle", "keepNext", "keepLines", "pageBreakBefore", "framePr", "widowControl", "numPr", "suppressLineNumbers",
            "pBdr", "shd", "tabs", "suppressAutoHyphens", "kinsoku", "wordWrap", "overflowPunct", "topLinePunct", "autoSpaceDE",
            "autoSpaceDN", "bidi", "adjustRightInd", "snapToGrid", "spacing", "ind", "contextualSpacing", "mirrorIndents",
            "suppressOverlap", "jc", "textDirection", "textAlignment", "textboxTightWrap", "outlineLvl", "divId", "cnfStyle",
            "rPr", "sectPr", "pPrChange"],
    "rPr": ["rStyle", "rFonts", "b", "bCs", "i", "iCs", "caps", "smallCaps", "strike", "dstrike", "outline", "shadow", "emboss",
            "imprint", "noProof", "snapToGrid", "vanish", "webHidden", "color", "spacing", "w", "kern", "position", "sz", "szCs",
            "highlight", "u", "effect", "bdr", "shd", "fitText", "vertAlign", "rtl", "cs", "em", "lang", "eastAsianLayout",
            "specVanish", "oMath"],
    "tblPr": ["tblStyle", "tblpPr", "tblOverlap", "bidiVisual", "tblStyleRowBandSize", "tblStyleColBandSize", "tblW", "jc",
              "tblCellSpacing", "tblInd", "tblBorders", "shd", "tblLayout", "tblCellMar", "tblLook", "tblCaption", "tblDescription"],
    "trPr": ["cnfStyle", "divId", "gridBefore", "gridAfter", "wBefore", "wAfter", "cantSplit", "trHeight", "tblHeader",
             "tblCellSpacing", "jc", "hidden", "ins", "del", "trPrChange"],
    "tcPr": ["cnfStyle", "tcW", "gridSpan", "hMerge", "vMerge", "tcBorders", "shd", "noWrap", "tcMar", "textDirection",
             "tcFitText", "vAlign", "hideMark"],
}


def reorder_children(doc) -> None:
    """按OOXML架构顺序重排属性节点的子元素，避免Word报“文件已损坏”。"""
    W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    roots = [doc.element, doc.styles.element]
    for root in roots:
        for tag, order in ORDER.items():
            rank = {W + name: i for i, name in enumerate(order)}
            for el in root.iter(W + tag):
                kids = list(el)
                known = [k for k in kids if k.tag in rank]
                if [k.tag for k in known] == sorted((k.tag for k in known), key=rank.get):
                    continue
                for k in kids:
                    el.remove(k)
                for k in sorted(kids, key=lambda k: rank.get(k.tag, len(order))):
                    el.append(k)


def el_text(el) -> str:
    return "".join(x.text or "" for x in el.iter(qn("w:t"))).strip()


def normalize_ooxml(el) -> None:
    """模板经LibreOffice转存后有两类写法Word不认：字体名写成“宋体;SimSun”式回退列表，
    对齐与缩进用start/end。这里统一改回字体首名与left/right，并去掉书签（避免与正文书签编号冲突）。"""
    for rf in el.iter(qn("w:rFonts")):
        for attr, v in list(rf.attrib.items()):
            if ";" in v:
                rf.set(attr, v.split(";")[0])
    for jc in el.iter(qn("w:jc")):
        v = jc.get(qn("w:val"))
        if v in ("start", "end"):
            jc.set(qn("w:val"), "left" if v == "start" else "right")
    for ind in el.iter(qn("w:ind")):
        for old, new in (("w:start", "w:left"), ("w:end", "w:right")):
            if ind.get(qn(old)) is not None:
                ind.set(qn(new), ind.get(qn(old))); del ind.attrib[qn(old)]
    for tag in ("w:tblCellMar", "w:tcBorders", "w:tblBorders"):
        for box in el.iter(qn(tag)):
            for kid in box:
                if kid.tag == qn("w:start"):
                    kid.tag = qn("w:left")
                elif kid.tag == qn("w:end"):
                    kid.tag = qn("w:right")
    for tag in ("w:bookmarkStart", "w:bookmarkEnd"):
        for bm in list(el.iter(qn(tag))):
            bm.getparent().remove(bm)


def fill_cover(table) -> None:
    """按SCHOOL、TEAM_NO、MEMBERS填写封面信息表，字体字号沿用模板单元格（加粗小二号）；
    学校与队号的内容与左侧标签同样靠下对齐，队员姓名接在“1.”“2.”“3.”之后。"""
    cells = [tr.findall(qn("w:tc")) for tr in table.findall(qn("w:tr"))]
    assert el_text(cells[0][0]).replace(" ", "") == "学校" and el_text(cells[1][0]) == "参赛队号" \
        and el_text(cells[2][0]) == "队员姓名" and len(cells) == 2 + len(MEMBERS), "模板封面信息表结构与预期不符"
    def write(tc, text, bottom=False):
        if bottom:
            tcpr = tc.get_or_add_tcPr()
            va = tcpr.find(qn("w:vAlign"))
            if va is None:
                va = OxmlElement("w:vAlign"); tcpr.append(va)
            va.set(qn("w:val"), "bottom")
        p = tc.findall(qn("w:p"))[-1]
        runs = p.findall(qn("w:r"))
        if not runs:
            runs = [OxmlElement("w:r")]; p.append(runs[0])
        t = runs[-1].find(qn("w:t"))
        if t is None:
            t = OxmlElement("w:t"); runs[-1].append(t)
        t.text = (t.text or "") + text
        t.set(qn("xml:space"), "preserve")
    write(cells[0][1], SCHOOL, bottom=True)
    if TEAM_NO:
        write(cells[1][1], TEAM_NO, bottom=True)
    for k, name in enumerate(MEMBERS):
        assert el_text(cells[2 + k][1]) == f"{k + 1}.", "模板队员行应为“1.”“2.”“3.”"
        write(cells[2 + k][1], " " + name)


def front_matter(doc) -> None:
    """封面（模板第0页）与摘要页（第1页）取自官方模板：封面信息表按SCHOOL、TEAM_NO、MEMBERS填写；
    摘要页依次为赛事名称、“题 目：”＋三号黑体题目、“摘 要：”、摘要正文、“关键词：”＋关键词。"""
    tpl = Document(TEMPLATE)
    tk = list(tpl.element.body.iterchildren())
    assert el_text(tk[2]) == "中国研究生创新实践系列大赛" and tk[6].tag == qn("w:tbl"), "模板封面结构与预期不符"
    assert el_text(tk[18]).startswith("题 目：") and el_text(tk[20]) == "摘 要：" and el_text(tk[24]) == "关键词：", "模板摘要页结构与预期不符"
    body = doc.element.body
    kids = [el for el in body.iterchildren() if el.tag in (qn("w:p"), qn("w:tbl"))]   # 跳过pandoc放在正文层的书签
    assert el_text(kids[0]) == "摘要", "合稿首个元素应为“摘要”一级标题"
    end = next(i for i, el in enumerate(kids) if el_text(el).startswith("关键词："))
    abstract = kids[1:end]
    keywords = el_text(kids[end]).split("：", 1)[1].strip()
    for el in (kids[0], kids[end]):
        body.remove(el)

    def clone(i):
        el = copy.deepcopy(tk[i]); normalize_ooxml(el); return el
    cover = [clone(i) for i in range(0, 7)]          # 徽标、赛事名称三行、空行、学校/参赛队号/队员姓名表
    A = "http://schemas.openxmlformats.org/drawingml/2006/main"
    R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    for j, blip in enumerate(cover[0].iter(f"{{{A}}}blip")):
        blob = tpl.part.related_parts[blip.get(f"{{{R}}}embed")].blob
        rid, _ = doc.part.get_or_add_image(io.BytesIO(blob))
        blip.set(f"{{{R}}}embed", rid)
    for j, dp in enumerate(cover[0].iter(qn("wp:docPr"))):
        dp.set("id", str(10001 + j))
    fill_cover(cover[6])
    head = [clone(i) for i in range(14, 21)]         # 赛事名称三行、空行、“题 目：”、空行、“摘 要：”
    Paragraph(head[0], doc._body).paragraph_format.page_break_before = True
    title = head[4]
    runs = title.findall(qn("w:r"))
    for r in runs[1:]:
        title.remove(r)
    tp = Paragraph(title, doc._body)
    for text, size in (("  ", 16), (TITLE, 16)):
        run = tp.add_run(text)
        run.font.size = Pt(size); run.font.name = "Times New Roman"
        rf = run._element.get_or_add_rPr().get_or_add_rFonts()
        rf.set(qn("w:eastAsia"), "黑体"); rf.set(qn("w:ascii"), "黑体"); rf.set(qn("w:hAnsi"), "黑体")
    kw = clone(24)
    kp = Paragraph(kw, doc._body)
    kp.paragraph_format.space_before = Pt(6)
    run = kp.add_run(keywords)
    run.font.size = Pt(12); run.font.name = "Times New Roman"
    run._element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), "宋体")
    first = body[0]
    for el in cover + head + abstract + [kw]:
        first.addprevious(el)


def page_setup(doc) -> None:
    """版心与页码按模板：A4，左右边距各22.5 mm，上30.0 mm，下18.5 mm，页脚距17.5 mm；
    封面为第0页且不显示页码，摘要页起为1、页脚居中，全文无页眉。"""
    sec = doc.sections[-1]
    sec.page_width, sec.page_height = Cm(21), Cm(29.7)
    tw = lambda v: Pt(v / 20)
    sec.left_margin, sec.right_margin = tw(1276), tw(1274)
    sec.top_margin, sec.bottom_margin = tw(1702), tw(1048)
    sec.header_distance, sec.footer_distance = tw(0), tw(992)
    sec.different_first_page_header_footer = True
    sec.first_page_footer.is_linked_to_previous = False
    for p in sec.first_page_footer.paragraphs:
        for r in list(p.runs):
            r._element.getparent().remove(r._element)
    sec.footer.is_linked_to_previous = False
    par = sec.footer.paragraphs[0]
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    par.paragraph_format.first_line_indent = Cm(0)
    for kind, text in (("begin", None), (None, " PAGE "), ("separate", None), (None, "1"), ("end", None)):
        run = par.add_run()
        run.font.size = Pt(10.5); run.font.name = "Times New Roman"
        if kind:
            fc = OxmlElement("w:fldChar"); fc.set(qn("w:fldCharType"), kind); run._element.append(fc)
        elif text.strip() == "PAGE":
            it = OxmlElement("w:instrText"); it.set(qn("xml:space"), "preserve"); it.text = text; run._element.append(it)
        else:
            run._element.append(OxmlElement("w:t")); run._element[-1].text = text
    sp = sec._sectPr
    for old in sp.findall(qn("w:pgNumType")):
        sp.remove(old)
    pg = OxmlElement("w:pgNumType"); pg.set(qn("w:start"), "0"); pg.set(qn("w:fmt"), "decimal")
    later = ("w:cols", "w:formProt", "w:vAlign", "w:noEndnote", "w:titlePg", "w:textDirection", "w:bidi", "w:rtlGutter", "w:docGrid")
    anchor = next((sp.find(qn(t)) for t in later if sp.find(qn(t)) is not None), None)
    if anchor is not None:                       # sectPr子元素有架构顺序：pgNumType在cols、titlePg之前
        anchor.addprevious(pg)
    else:
        sp.append(pg)
    assert not any(h for h in sp.findall(qn("w:headerReference"))), "论文不能有页眉"


def main() -> None:
    FIGDIR.mkdir(parents=True, exist_ok=True)
    md = prepare_markdown()
    ref = reference_doc()
    out = OUT / "R12论文_v1.docx"
    pypandoc.convert_file(str(md), "docx", outputfile=str(out), format="markdown+pipe_tables+tex_math_dollars+fenced_divs+link_attributes",
                          extra_args=[f"--reference-doc={ref}", "--resource-path", str(ROOT)])
    doc = Document(out)
    n = number_equations(doc)
    seen_appendix = False
    for el in list(doc.element.body.iterchildren()):
        if el.tag == qn("w:p") and el_text(el) == "附录":
            seen_appendix = True
        if el.tag == qn("w:tbl"):
            three_line(Table(el, doc), small=seen_appendix)
    style_paragraphs(doc)
    algos = algorithm_boxes(doc)
    front_matter(doc)
    page_setup(doc)
    doc.core_properties.title = TITLE
    reorder_children(doc)
    doc.save(out)
    print(f"docx -> {out}  (numbered equations: {n}, tables: {len(doc.tables)}, algorithms: {algos})")
    todo = re.findall(r"【[^】]*(?:参赛队|填写)[^】]*】", (ROOT / "全文_R12论文_v1.md").read_text(encoding="utf-8"))
    if todo:                                   # 提交前须清零：附录D与AI标注中的待填项
        print(f"提醒：全文仍有{len(todo)}处待参赛队填写的【】占位（附录D与人工智能工具标注），提交前须逐一填写。")


if __name__ == "__main__":
    main()
