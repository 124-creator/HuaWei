#!/usr/bin/env python3
# 本程序及代码是在人工智能工具辅助下完成的。
# ChatGPT / GPT-6 Astra Pro / OpenAI；Astra系列公告2026-09-03。
# 仅对文稿构建脚本应用已通过局部预检的修正，不运行求解器或评估器。
from pathlib import Path
import hashlib
HERE=Path(__file__).resolve().parent
MARK='# LBSS_PREFLIGHT_COMPAT_V1'

def apply(name,fn):
    p=HERE/name;s=p.read_text(encoding='utf-8')
    if MARK in s:return
    s=fn(s);p.write_text(s+'\n'+MARK+'\n',encoding='utf-8')
    print(name,hashlib.sha256(p.read_bytes()).hexdigest())

def build(s):
    s=s.replace("r'\\bL2([1-5])\\b'","r'(?<![A-Za-z0-9])L2([1-5])(?![0-9])'")
    s=s.replace('\\mathrm{','\\text{')
    s=s.replace(r'\begin{aligned}\text{span}+\varepsilon&<\text{need}\quad\lor\\\text{rightmost}+\varepsilon&<\text{ready}+\text{need}.\end{aligned}',r'\begin{gathered}\text{span}+\varepsilon<\text{need}\quad\lor\\\text{rightmost}+\varepsilon<\text{ready}+\text{need}.\end{gathered}')
    s=s.replace('def math_blocks():',"EQ.pop('4-6')  # Preserve the source low-limit operator.\nEQ['4-1']=r'P=(g,a,\\pi),\\quad g:U\\to S,\\quad a:S\\to\\{0,\\ldots,k-1\\}'\n\ndef math_blocks():")
    s=s.replace("el.xpath('.//m:t')","el.xpath('.//*[local-name()=\"t\"]')")
    s=s.replace("m.xpath('.//m:r')","m.xpath('.//*[local-name()=\"r\"]')")
    s=s.replace("run.xpath('.//m:t/text()')","run.xpath('.//*[local-name()=\"t\"]/text()')")
    s=s.replace("['REF','题目规定的整图单核参考']","['REF','题目规定的整图单核参考'],['Makespan','所有操作完成时刻的最大值，即总体执行时间']")
    anchor='    # Reconcile prose anchors against the pinned document before applying edits.'
    s=s.replace(anchor,"""    edits[51]='数据分析工具说明：本节沿用归档统计，相关文稿的历史提交记录标注Claude（Claude Opus 5.5，Anthropic；模型发布日期2026年9月22日）。本次统计核对使用ChatGPT（GPT-6 Astra Pro，OpenAI；Astra系列公告日期2026年9月3日）。本文区分文稿提交记录与统计脚本的历史版本记录，详细范围见附录D。'
    edits[633]='本章按合法性、下界间隙、性能分布、配对比较和时间成本检验算法。相关文稿历史提交记录标注Claude（Claude Opus 5.5，Anthropic；模型发布日期2026年9月22日）；本次冻结表只读复算与核对使用ChatGPT（GPT-6 Astra Pro，OpenAI；Astra系列公告日期2026年9月3日）。新增统计仅由已有结果计算，历史记录范围见附录D。'
"""+anchor)
    anchor='    # Shared public terminology, chapter cross-references and math subscripts.'
    s=s.replace(anchor,"""    fill(ps[647], '各核负载W_c为该核全部非COPY操作的max(1, cycles)之和。η=1表示静态计算负载相同；场景A的η中位数为1.013至1.079，最大为2.727，五核时7张图使用少于5个核心（图8-2）。该指标度量静态工作量，区别于含搬运与等待的运行利用率。')
    for t in ts:
        if len(t.rows)==1 and len(t.columns)==2 and t.cell(0,1).text=='(8-4)':patch_text(t.cell(0,0)._tc,r'd(?=i|ᵢ|>)','ℓ')
"""+anchor)
    s=s.replace("patch_text(d.element.body,r'\\bround12\\b','算法实现')","patch_text(d.element.body,r'\\bround12\\b','算法实现')\n    patch_text(d.element.body,'Static Construction Baseline','Static Constructive Baseline')")
    anchor='    # Update table numbers by first occurrence'
    s=s.replace(anchor,"""    for run in d.element.body.xpath('.//m:r'):
        wr=run.find(qn('w:rPr'))
        if wr is None:wr=OxmlElement('w:rPr');run.append(wr)
        rf=wr.find(qn('w:rFonts'))
        if rf is None:rf=OxmlElement('w:rFonts');wr.insert(0,rf)
        for key in ('ascii','hAnsi'):rf.set(qn('w:'+key),'Cambria Math')
        rf.set(qn('w:eastAsia'),'宋体')
        for key in ('sz','szCs'):
            x=wr.find(qn('w:'+key))
            if x is None:x=OxmlElement('w:'+key);wr.append(x)
            x.set(qn('w:val'),'24')
"""+anchor)
    s=s.replace('text=alltext(d.element.body)',"text='\\n'.join(alltext(p) for p in d.element.body.xpath('.//w:p'))")
    return s

def figures(s):
    s=s.replace('def translate(s):',"def translate(s):\n    if re.fullmatch(r'C[0-7]',s):return 'C'+s[-1].translate(str.maketrans('01234567','₀₁₂₃₄₅₆₇'))")
    s=s.replace("s=s.replace('R12 full','LBSS')","s=s.replace('统一建模','LBSS建模').replace('R12 full','LBSS')")
    s=s.replace('for x in root.iter():\n        name=','for x in root.iter():\n        if not isinstance(x.tag,str):continue\n        name=')
    s=s.replace("['Liberation Serif','Noto Sans CJK SC','DejaVu Serif']","['Liberation Serif','Noto Sans CJK JP','DejaVu Serif']")
    s=s.replace("node.set('style',st)","if re.search(r'[\\u3400-\\u9fff]',''.join(text.itertext())):st=re.sub(r'font-family:[^;]+',\"font-family: 'Noto Serif CJK SC'\",st)\n                    node.set('style',st)")
    return s

def checker(s):
    s=s.replace('body=text(doc.element.body)',"body='\\n'.join(text(p) for p in doc.element.body.xpath('.//w:p'))")
    s=s.replace('        for row in t.rows[1:]:\n            for cell in row.cells:',"        has_case_id='最差用例' in ''.join(x.text for x in t.rows[0].cells)\n        for row in t.rows[1:]:\n            for cell in (row.cells[:-1] if has_case_id else row.cells):")
    return s

apply('build_submission.py',build)
apply('figures.py',figures)
apply('verify_delivery.py',checker)
