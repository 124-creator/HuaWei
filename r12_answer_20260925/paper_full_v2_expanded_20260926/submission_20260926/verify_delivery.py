#!/usr/bin/env python3
# 本程序及代码是在人工智能工具辅助下完成的。
# ChatGPT，GPT-6 Astra Pro，OpenAI；Astra系列公告日期2026-09-03。
# 文稿和归档数据校验，不运行求解器或评估器。
from pathlib import Path
from collections import Counter
from copy import deepcopy
import hashlib, json, re, zipfile
import fitz
from docx import Document

HERE=Path(__file__).resolve().parent;OUT=HERE/'out';NAME='多核NPU切图调度论文'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def text(e):return ''.join(e.xpath('.//w:t/text()|.//m:t/text()'))

src=Document(HERE.parent/'out/R12论文_完整增强版_匿名.docx')
doc=Document(OUT/(NAME+'.docx'));pdfpath=OUT/(NAME+'.pdf')
report=json.loads((OUT/'新校验记录.json').read_text())
old=[t for t in src.tables if len(t.rows)==101];new=[t for t in doc.tables if len(t.rows)==101]
assert len(old)==len(new)==9
assert [[[c.text for c in r.cells] for r in t.rows] for t in old]==[[[c.text for c in r.cells] for r in t.rows] for t in new]
# Audit all unchanged, standalone numeric data cells (not mathematical display tables).
numeric=re.compile(r'^[+−-]?(?:\d[\d.,]*(?:e[+−-]?\d+)?%?)(?:\s*/\s*[+−-]?\d[\d.,]*%?)*$')
def numeric_cells(d):
    c=Counter()
    for t in d.tables:
        if len(t.rows)==1 and len(t.columns)==2:continue
        for row in t.rows[1:]:
            for cell in row.cells:
                s=cell.text.strip()
                if numeric.fullmatch(s):c[s]+=1
    return c
before=numeric_cells(src);after=numeric_cells(doc)
# Additional tables introduce numbers; display NA changes are logged rather than rewriting original data.
missing={k:v-after[k] for k,v in before.items() if v>after[k]}
assert set(missing).issubset({'0','0.0','0.0000','0.000000'}),missing
body=text(doc.element.body)
internal=re.findall(r'R12|C3|R6|R7|R10|round12|F27|F28|A087|\bL2[1-5]\b|/home/|/mnt/data/',body)
assert not internal,internal
assert len(doc.inline_shapes)==37
assert not doc.element.body.xpath('.//w:ins|.//w:del|.//w:commentRangeStart')
assert not doc.element.body.xpath('.//m:t[text()="&"]')
assert not any(p.text.strip() for s in doc.sections for p in s.header.paragraphs)
# Strip only PDF document metadata. Do not reflow or alter content streams.
f=fitz.open(pdfpath)
m=f.metadata;m.update(author='',subject='多核调度、结构化搜索与缓存分析',title='基于可证下界与结构化搜索的多核NPU切图调度',keywords='LBSS; SCB; NPU')
f.set_metadata(m);tmp=OUT/'_metadata.pdf';f.save(tmp);f.close();tmp.replace(pdfpath)
f=fitz.open(pdfpath);texts=[p.get_text() for p in f];joined='\n'.join(texts)
assert len(f)>0
assert all(len(t.strip())>8 for t in texts),'Blank page detected'
for term in ('LBSS','SCB','263','18.8','90.5','模拟审稿意见'):
    assert term in joined,term
errors=re.findall(r'Error:|<?>\s*\n|Syntax Error|undefined control sequence',joined,flags=re.I)
errors=[x for x in errors if x.strip() not in ('>','')]
assert not errors,errors
footers=[]
for i,p in enumerate(f):
    nums=[w for w in p.get_text('words') if w[1]>p.rect.height-60 and w[4]==str(i+1)]
    footers.append(bool(nums))
assert all(footers),[(i+1,v) for i,v in enumerate(footers) if not v]
headings={}
for label in ('1 问题重述','4.8','4.9','7.6','7.7','8.7','8.8','参考文献','附录 A','附录A','附录D'):
    headings[label]=[i+1 for i,t in enumerate(texts) if label in t]
fonts=sorted(set(font[3] for p in f for font in p.get_fonts()))
report.update(pdf_pages=len(f),serialized_archive_rows_verified=900,figures_verified=37,equations_verified=64,standalone_numeric_cell_multiset_missing=missing,numeric_display_exception='Zero-regression rows display NA for the worst-regression statistic; original values remain in raw tables and reviewer-response record',pdf_page_numbers_continuous=True,blank_pages=0,math_error_markers=0,pdf_fonts=fonts,formal_word_font_export='NOT_COMPLETED: rendered with LibreOffice and fallback fonts; Word export helper supplied',visual_review='PENDING: all-page inspection after downloading the one-build artifact',status='AUTOMATED_CHECKS_PASSED; formal font export and historical disclosure remain open',sha256={NAME+'.docx':sha(OUT/(NAME+'.docx')),NAME+'.pdf':sha(pdfpath)})
(OUT/'新校验记录.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
(OUT/'SHA256SUMS.txt').write_text('\n'.join(v+'  '+k for k,v in report['sha256'].items())+'\n')
# Formula/source inventory: all displays keep their numbered identity and source class.
formula=[]
for t in doc.tables:
    if len(t.rows)==1 and len(t.columns)==2 and re.fullmatch(r'\(\d+-\d+\)',t.cell(0,1).text):
        k=t.cell(0,1).text
        if k.startswith('(4-'):kind='题面规则、本文定义或正文给出的资源松弛推导；4.5复杂性归约引用[14]'
        elif k.startswith('(5-'):kind='本文候选规则、无环证明与复杂度说明；插入规则和Treap出处见[6][15]'
        elif k.startswith('(6-'):kind='官方Task/边界规则及本文微批定义和不变量推导'
        elif k.startswith('(7-'):kind='官方FIFO/带宽语义、比值定义与代数恒等式推导'
        else:kind='指标定义与配对统计；符号秩来源[19]、相关性来源[20]'
        formula.append({'equation':k,'text':text(t.cell(0,0)._tc),'source_class':kind})
assert len(formula)==64
(OUT/'公式来源与等价排版核对.json').write_text(json.dumps(formula,ensure_ascii=False,indent=2))
# Response matrix is versioned separately from the paper and does not assert nonexistent formal compliance.
changes=(HERE/'review_response.md').read_text(encoding='utf-8')
changes=changes.replace('{{PAGES}}',str(len(f))).replace('{{BEFORE_NEG}}',str(report['negative_expression_token_count']['before'])).replace('{{AFTER_NEG}}',str(report['negative_expression_token_count']['after']))
(OUT/'逐条改动清单与未采纳说明.md').write_text(changes,encoding='utf-8')
(OUT/'工具信息来源.md').write_text('''# 工具信息与来源边界

本次工具：ChatGPT / GPT-6 Astra Pro / OpenAI。GPT-6 Astra系列公告及安全概览日期2026-09-03；未把系列公告日期虚构为另有独立Pro型号发布日期。

- https://openai.com/index/gpt-6-astra/
- https://openai.com/index/safety-overview-gpt-6-astra/

历史仓库提交9dd614f等记录Claude Opus 5.5共同参与；模拟审稿意见开头明确为Claude Code / Anthropic生成。Claude Opus 5.5模型公告日期2026-09-22。

- https://www.anthropic.com/claude-opus-5-5

模型日期与客户端版本不是同一事项。历史ChatGPT后台型号、部分早期开发工具和Claude Code客户端版本未完整留存，附录D如实披露，未替用户编造。完成正式提交前应由参赛队从真实账户界面与日志补核。
''',encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k not in ('figure_relabelling','table8_6_before')},ensure_ascii=False,indent=2))
