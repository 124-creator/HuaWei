#!/usr/bin/env python3
"""本程序及代码是在人工智能工具辅助下完成的。工具：ChatGPT，OpenAI；
具体版本/发布日期由参赛队核验。只核验成文产物，不运行求解器或评价器。
"""
from pathlib import Path
import hashlib, json, re, zipfile
from lxml import etree
import fitz
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'out'
NAME='R12论文_完整增强版_匿名'
NS={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','m':'http://schemas.openxmlformats.org/officeDocument/2006/math'}
def xml(path):
    with zipfile.ZipFile(path) as z:
        return etree.fromstring(z.read('word/document.xml'))
def matrix(t):
    return [[''.join(c.xpath('.//w:t/text()',namespaces=NS)) for c in r.xpath('./w:tc',namespaces=NS)] for r in t.xpath('./w:tr',namespaces=NS)]
def main():
    word=OUT/(NAME+'.docx'); pdf=OUT/(NAME+'.pdf')
    assert word.is_file() and pdf.is_file(), 'Missing Word or PDF'
    source=ROOT.parent/'paper_full_v1/out/R12论文_v1.docx'
    sx=xml(source); dx=xml(word)
    old=[matrix(t) for t in sx.xpath('./w:body/w:tbl',namespaces=NS) if len(t.xpath('./w:tr',namespaces=NS))==101]
    new=[matrix(t) for t in dx.xpath('./w:body/w:tbl',namespaces=NS) if len(t.xpath('./w:tr',namespaces=NS))==101]
    assert len(old)==len(new)==9
    checked=0
    for k,(a,b) in enumerate(zip(old,new)):
        assert len(a)==len(b)==101
        for i,(ar,br) in enumerate(zip(a[1:],b[1:]),1):
            expect=ar[:]; expect[0]=expect[0].replace('case_','')
            if k>=4: expect=[expect[j] for j in (0,3,4,5,6,7)]
            assert br==expect, ('Archival mismatch',k,i,br,expect)
            assert br[0]==f'{i:03d}'
            checked+=1
    equations=[]
    for t in dx.xpath('./w:body/w:tbl',namespaces=NS):
        mm=matrix(t)
        if len(mm)==1 and len(mm[0])==2 and re.fullmatch(r'\(\d+-\d+\)',mm[0][1]):
            equations.append(mm[0][1])
            assert t.xpath('.//m:oMath',namespaces=NS), 'Equation missing editable math'
    assert len(equations)==64 and len(set(equations))==64
    figures=len(dx.xpath('.//w:drawing',namespaces=NS))
    assert figures==37
    doc=fitz.open(pdf)
    assert 80<=len(doc)<=100, ('Page target not met',len(doc))
    text='\n'.join(p.get_text() for p in doc)
    for term in ['关键词','4.9','7.7','8.8','参考文献','900']:
        assert term in text, ('Required text missing',term)
    assert '1 问题重述' in doc[1].get_text(), 'Body must follow the abstract'
    for term in ['田中斐','安镕基','郑州航空工业管理学院','参赛队号']:
        assert term not in text, ('Identity leaked into anonymous paper',term)
    assert '\ufffd' not in text, 'Replacement characters in PDF text'
    warnings=[]
    for n,p in enumerate(doc,1):
        if len(p.get_text().strip())<80: warnings.append({'page':n,'warning':'sparse text; inspect figures visually'})
        feet=[w for w in p.get_text('words') if w[1]>p.rect.height-65 and w[4]==str(n)]
        assert feet, ('Missing continuous footer',n)
    report=json.loads((OUT/'校验记录.json').read_text())
    report.update(pdf_pages=len(doc),archival_rows_verified_after_export=checked,figures_after_export=figures,equations_after_export=len(equations),automated_checks='passed',visual_review='Local equivalent 100-page rendering reviewed separately; this script is not visual QA.',warnings=warnings)
    report['sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (word,pdf)}
    report['status']='generated and automatically verified; historical AI disclosure and formal font export still require team review'
    (OUT/'校验记录.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    (OUT/'SHA256SUMS.txt').write_text('\n'.join(v+'  '+k for k,v in report['sha256'].items())+'\n')
    print(json.dumps({k:report[k] for k in ['pdf_pages','archival_rows_verified_after_export','figures_after_export','equations_after_export','sha256']},ensure_ascii=False,indent=2))
if __name__=='__main__': main()
