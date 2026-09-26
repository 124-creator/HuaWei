#!/usr/bin/env python3
# 本程序及代码是在人工智能工具辅助下完成的。
# ChatGPT，GPT-6 Astra Pro，OpenAI；Astra系列公告日期2026-09-03。
# 只修改原图文字和数值标注，保留数据曲线几何；不运行任何性能程序。
from __future__ import annotations
import ast, copy, hashlib, io, json, re
from pathlib import Path
from lxml import etree
from PIL import Image
import cairosvg

MAP={'F03':'2-1','F04':'2-2','F35':'2-3','F01':'4-1','F02':'4-2','F06':'5-1','F33':'5-2','F34':'5-3','F38':'5-4','F07':'5-5','F08':'5-6','F10':'5-7','F12':'5-8','F05':'6-1','F13':'6-2','F14':'6-3','F39':'6-4','F15':'6-5','F16':'6-6','F17':'6-7','F18':'6-8','F19':'6-9','F21':'6-10','F20':'6-11','F22':'7-1','F40':'7-2','F24':'7-3','F25':'7-4','F26':'7-5','F30':'7-6','F29':'7-7','F27':'7-8','F28':'7-9','F09':'8-1','F11':'8-2','F31':'8-3','F32':'8-4'}
NS={'s':'http://www.w3.org/2000/svg'}

def translate(s):
    s=re.sub(r'\bC([0-4])\s+(M|V|IN|OUT)\b',lambda m:'核'+m[1]+' '+m[2],s)
    s=s.replace('R12 full','LBSS').replace('R12','LBSS').replace('C3','SCB')
    s=s.replace('F28','图7-9').replace('F27','图7-8').replace('T_L2','T_L')
    s=s.replace('PB','P_B').replace('PL','P_L').replace('Q3','问题三')
    s=re.sub(r'\bL2([1-5])\b',lambda m:'L2-'+m[1],s)
    s=s.replace('A087','case_087（场景A）')
    for a,b in [('认代价','代价分析'),('造候选','候选构造'),('设下界','下界筛选'),('凭评测','评价择优'),('写不出闭式表达式','采用官方确定性评价'),('忽略搬运时已NP难','计算调度抽象为NP难'),('跳过其余改进阶段','跳过受控阶段'),('核归属不变 ⇒ 边界搬运不变','核归属不变 ⇒ Spill前边界不变'),('不改变色标',''),('开发诊断案例','设计阶段的诊断案例')]:s=s.replace(a,b)
    return s.replace('，；','；').rstrip('，')

def geometry_hash(root):
    values=[]
    for x in root.iter():
        name=etree.QName(x).localname
        if name in ('path','rect','circle','polygon','polyline','image','use'):
            values.append((name,sorted((k,v) for k,v in x.attrib.items() if k not in ('id','style'))))
    return hashlib.sha256(json.dumps(values,ensure_ascii=False).encode()).hexdigest()

def point_labels(root,metadata,key):
    lines=[x for x in metadata.get('plotted_lines',[]) if len(x.get('x',[]))==5]
    groups=[]
    for g in root.xpath('//s:g[starts-with(@id,"line2d_")]',namespaces=NS):
        uses=g.xpath('./s:g/s:use',namespaces=NS)
        if len(uses)==5 and all('x' in x.attrib and 'y' in x.attrib for x in uses):groups.append(uses)
    if len(groups)!=len(lines):return {'annotated':False,'reason':'marker count differs; exact source curves retained'}
    font='font-size: 7.5px; font-family: Liberation Serif; text-anchor: middle; fill: #202020'
    count=0
    for j,(g,data) in enumerate(zip(groups,lines)):
        for i,(use,val) in enumerate(zip(g,data['y'])):
            if key in ('F07','F15'):
                if i==0 and j==1:continue
                dy=-8 if j==0 else 12
            else:
                # Label the independently-selected curve and the two ratio curves;
                # the two near-overlapping fixed-plan curves retain exact five-core legend labels.
                if j<2:continue
                dy=(-9 if j in (2,4) else 11)
                if j==3 and i==0:dy=14
            t=etree.Element('{'+NS['s']+'}text',x=use.get('x'),y=str(float(use.get('y'))+dy),style=font)
            t.text=f'{val:.3f}' if key!='F24' or j==2 else f'{val:.4f}'
            root.append(t);count+=1
    return {'annotated':True,'labels_added':count,'values_source':'original figure metadata.plotted_lines; no geometry modified','near_coincident_series':'F24 fixed-plan values remain in legend and main table'}

def crop_helpers(base):
    tree=ast.parse((base/'paper_full_v1/code/build_docx.py').read_text())
    selected=[x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name in ('crop_title_band','crop_note_band')]
    env={'Path':Path,'Image':Image}
    exec(compile(ast.Module(body=selected,type_ignores=[]),'<document-crop-functions>','exec'),env)
    return env['crop_title_band']

def diagram_sources(base,temp):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    source=(base/'paper_full_v1/code/flowcharts.py').read_text()
    env={'__name__':'diagram_functions'};exec(compile(source,'<figure-functions>','exec'),env)
    plt.rcParams.update({'font.family':['Liberation Serif','Noto Sans CJK SC','DejaVu Serif'],'svg.fonttype':'none','svg.hashsalt':'LBSS-paper'})
    old=env['Canvas'].lines
    def words(self,cx,cy,text,**kw):return old(self,cx,cy,translate(text),**kw)
    env['Canvas'].lines=words
    for name in ('roadmap','q1_flow','q2_flow','q3_flow'):env[name](temp)


def generate(base,dest):
    dest.mkdir(parents=True,exist_ok=True);temp=dest/'_diagram_sources';temp.mkdir(exist_ok=True)
    diagram_sources(base,temp);crop=crop_helpers(base);records=[]
    for key,num in MAP.items():
        source=(temp if key in ('F35','F38','F39','F40') else base/'figures_v3/figures')/(key+'.svg')
        root=etree.parse(str(source)).getroot();geo=geometry_hash(root)
        removed=[]
        for text in root.xpath('//s:text',namespaces=NS):
            val=''.join(text.itertext())
            if any(v in val for v in ('不代表容量足够或不会Spill','不推断实测Spill字节数','不指定替换策略')):
                removed.append(val);text.getparent().remove(text);continue
            # SVG text is either one text node or a sequence of math tspans.
            for node in text.iter():
                if node.text:node.text=translate(node.text)
                if node.tail:node.tail=translate(node.tail)
                if 'style' in node.attrib:
                    st=node.get('style').replace("'Microsoft YaHei'","'Noto Sans CJK SC'").replace("'Times New Roman'","'Liberation Serif'")
                    node.set('style',st)
            if key=='F32' and 'case_087' in ''.join(text.itertext()):
                text.clear();text.set('style','font-size: 7.4px; font-family: Noto Sans CJK SC; text-anchor: end; fill: #ab4949')
                for k,line in enumerate(['case_087（场景A）','补跑预算1800 s']):
                    span=etree.SubElement(text,'{'+NS['s']+'}tspan',x='466',y=str(28+10*k));span.text=line
        for x in root.xpath('//s:metadata',namespaces=NS):x.getparent().remove(x)
        assert geometry_hash(root)==geo,key+' data geometry changed'
        annotation={}
        if key in ('F07','F15','F24'):
            md=json.loads((base/'figures_v3/metadata'/f'{key}.json').read_text());annotation=point_labels(root,md,key)
        svg=dest/('图'+num+'.svg');svg.write_bytes(etree.tostring(root,xml_declaration=True,encoding='UTF-8'))
        rawpng=dest/('_'+key+'.png');cairosvg.svg2png(bytestring=svg.read_bytes(),write_to=str(rawpng),output_width=2400)
        png=dest/('图'+num+'.png')
        if key not in ('F35','F38','F39','F40'):crop(rawpng,png)
        else:Image.open(rawpng).save(png)
        rawpng.unlink()
        # Remove image ancillary metadata without modifying pixels.
        im=Image.open(png).convert('RGB');im.save(png,optimize=True,dpi=(450,450))
        records.append({'source_id':key,'paper_figure':'图'+num,'nontext_geometry_sha256':geo,'geometry_preserved':True,'removed_defensive_notes':removed,'point_annotation':annotation,'sha256_png':hashlib.sha256(png.read_bytes()).hexdigest()})
    return records

def replace_figures(d,base,dest):
    if not all((dest/('图'+num+'.png')).exists() for num in MAP.values()):records=generate(base,dest)
    else:records=json.loads((dest/'figure_checks.json').read_text())
    paragraphs=list(d.paragraphs);count=0
    for i,p in enumerate(paragraphs):
        blips=p._p.xpath('.//a:blip')
        if not blips:continue
        following=next((q.text for q in paragraphs[i+1:i+4] if re.match(r'图\s*\d+-\d+',q.text)),None)
        assert following,(i,'missing caption')
        num=re.match(r'图\s*(\d+-\d+)',following)[1]
        file=dest/('图'+num+'.png');assert file.exists(),num
        for b in blips:
            rid=b.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
            d.part.related_parts[rid]._blob=file.read_bytes();count+=1
    assert count==37,count
    return {'figures_replaced':count,'records':records}

if __name__=='__main__':
    here=Path(__file__).resolve().parent
    r=generate(here.parent.parent,here/'assets')
    (here/'assets/figure_checks.json').write_text(json.dumps(r,ensure_ascii=False,indent=2))
    print('Prepared figure assets only; complete paper not rebuilt:',len(r))
