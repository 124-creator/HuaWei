"""R12 flowchart redesign. AI-assisted code; no solver or manuscript execution.
Generate editable drawio, vector PDF/SVG, 600dpi PNG and geometry/font checks.
Release requires Liberation Serif and WenQuanYi Zen Hei. No font files are shipped.
"""
from __future__ import annotations
import argparse,json,math,re,subprocess,sys,warnings
from pathlib import Path
from html.parser import HTMLParser
from xml.etree import ElementTree as ET
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.textpath import TextToPath
from matplotlib.patches import FancyBboxPatch,Polygon
import fitz
from PIL import Image
from shapely.geometry import Polygon as SPolygon,LineString,box as SBox,Point
BASE='7cc49df7a561115f63b42753b99ebecf59f7b36e'
MMPT=72/25.4
PXMM=96/25.4
COL=dict(A='#3C5488',B='#007C83',L2='#B16D24',ink='#222222',grey='#555555',line='#555555')
FILL=dict(A='#EDF0F7',B='#E6F2F2',L2='#F7EFE6',neutral='#F3F4F7')
OUT=Path(__file__).resolve().parent
class Scene:
    def __init__(self,name,title,h):
        self.name,self.title,self.w,self.h=name,title,166.,h
        self.nodes,self.edges=[],[]
        self.text('title',5,2,156,9,title,12.2)
    def node(self,id,x,y,w,h,text='',fs=9.2,theme=None,shape='rect',role='node',color=None):
        d=dict(id=id,x=x,y=y,w=w,h=h,text=text,fs=fs,shape=shape,role=role,fill=FILL.get(theme,'#FFFFFF'),stroke=COL.get(theme,COL['line']),color=color or COL['ink'])
        self.nodes.append(d);return d
    def text(self,id,x,y,w,h,text,fs=9.2,color=None):return self.node(id,x,y,w,h,text,fs,shape='text',role='text',color=color)
    def panel(self,id,x,y,w,h,theme=None):return self.node(id,x,y,w,h,'',theme=theme,shape='panel',role='panel')
    def edge(self,id,source,target,points=None,sp=(.5,1),tp=(.5,0),dash=False,arrow=True):
        lu={n['id']:n for n in self.nodes};a,b=lu[source],lu[target]
        p0=(a['x']+a['w']*sp[0],a['y']+a['h']*sp[1]);p1=(b['x']+b['w']*tp[0],b['y']+b['h']*tp[1])
        pts=[p0]+(points or [])+[p1];pts=[p for i,p in enumerate(pts) if i==0 or p!=pts[i-1]]
        self.edges.append(dict(id=id,source=source,target=target,points=pts,sp=sp,tp=tp,dash=dash,arrow=arrow))
    def down(self,a,b):self.edge(a+'_'+b,a,b)
    def right(self,a,b):self.edge(a+'_'+b,a,b,sp=(1,.5),tp=(0,.5))
def designs():
    ss=[]
    s=Scene('00_R12_总体技术路线','多核 NPU 切图调度：总体技术路线',159)
    for id,x,txt in [('graphs',6,'原始计算图 <i>G</i><br>结构、依赖与张量复用'),('config',60,'固定硬件配置 <i>θ</i><br>容量、共享带宽与同步'),('ref',114,'官方评价与单核 REF<br>统一执行和统计口径')]:s.node(id,x,17,46,17,txt,9.0,theme='neutral')
    s.node('model',6,45,154,19,'联合决策 <i>P</i> = (<i>g</i>, <i>a</i>, <i>π</i>)：划分、核心归属、核上顺序<br>满足执行约束；先比较 Makespan，再比较新增 COPY',9.4)
    for id in ['graphs','config','ref']:
        n=next(n for n in s.nodes if n['id']==id);cx=n['x']+23;s.edge(id+'_model',id,'model',tp=((cx-6)/154,0))
    for id,x,txt in [('gen',6,'结构化<br>候选生成'),('screen',46,'结构检查与<br>有效下界筛选'),('evaluate',86,'官方完整<br>事件评价'),('keep',126,'字典序保留<br>已得可行解')]:s.node(id,x,75,34,17,txt,9.2,theme='neutral')
    for a,b in [('gen','screen'),('screen','evaluate'),('evaluate','keep')]:s.right(a,b)
    s.edge('model_gen','model','gen',points=[(23,69)],sp=(17/154,1))
    for id,x,title,txt in [('a',6,'问题一 · 场景 A','每子图一个 Task<br>依赖带与反馈重排<br>Task 粒度与并行权衡'),('b',60,'问题二 · 场景 B','每核心一个 Task<br>活动核与驻留组织<br>真实 Spill 引导微批'),('l2',114,'问题三 · 共享 L2','沿用 B 的 Task 结构<br>L2 评价下独立选解<br>同方案配置对照')]:
        th={'a':'A','b':'B','l2':'L2'}[id];s.node(id,x,110,46,29,title+'<br>'+txt,9.0,theme=th)
        s.edge('shared_'+id,'keep',id,points=[(143,102),(x+23,102)]);s.edges[-1]['bus']='shared_pipeline_fanout'
    s.node('deliver',6,146,154,11,'验证与交付：逐核曲线、逐例表、失败与预算记录、可复现程序',9.1,theme='neutral')
    for id in ['a','b','l2']:
        n=next(n for n in s.nodes if n['id']==id);s.edge(id+'_deliver',id,'deliver',tp=((n['x']+23-6)/154,0))
    ss.append(s)
    s=Scene('01_R12_问题一_候选与评价','问题一：Task 粒度与候选评价',190)
    s.node('rule',7,16,152,16,'每子图一个 Task；跨 Task 数据经 DDR 中转<br>同核前一 Task 后等 100 cycles；跨核前驱后等 1000 cycles',9.1,theme='A')
    s.node('start',7,41,152,15,'原图、固定配置与核数 → 构造并评价控制解<br>保存成功当前解 <i>P</i>*，各阶段共用同一软预算',9.2,theme='neutral')
    s.panel('early',7,66,94,70,'A');s.text('early_head',10,68,88,8,'01  早期扩展：按以下顺序尝试',9.4,color=COL['A'])
    for id,y,txt in [('activity',80,'减少活动核心  →  补齐空核心队列'),('bands',92,'依赖带  <i>w</i> = 4 / 8 / 2 / 16  →  追加式分核'),('feedback',104,'固定划分 <i>g</i>  →  用真实 Task 时长反馈重排'),('family',116,'完整分量家族  →  补充不同活动核与排序')]:s.text(id,10,y,88,8,txt,9.1)
    s.text('gate',10,127,88,7,'本组逐阶段检查 3% 近优门控',9.0,color=COL['A'])
    s.node('insert',7,146,94,21,'02  区间索引插入<br>Treap 加速同一空隙判定<br>仍按剩余预算构造与评价',9.2)
    s.text('eval_head',114,61,45,8,'每份候选的共用过程',9.0,color=COL['grey'])
    s.node('check',115,74,44,24,'覆盖与联合无环<br>方案去重<br>有效下界筛选',9.2)
    s.node('eval',115,110,44,18,'官方 A 完整评价<br>核内展开＋事件模拟',9.0)
    s.node('retain',115,140,44,26,'成功且字典序更优<br>才替换 <i>P</i>*<br>否则保留当前解',9.2,theme='A')
    s.node('output',7,178,152,10,'全部阶段结束：输出成功方案；无成功解则返回失败并保留原因',9.0,theme='neutral')
    s.edge('start_early','start','early',sp=(47/152,1));s.down('early','insert')
    s.edge('early_check','early','check',sp=(1,20/70),tp=(0,.5))
    s.edge('insert_check','insert','check',sp=(1,.5),tp=(0,.75),points=[(108,156.5),(108,92)])
    s.down('check','eval');s.down('eval','retain');s.edge('retain_output','retain','output',tp=(130/152,0));ss.append(s)
    s=Scene('02_R12_问题二_Spill微批','问题二：驻留组织与 Spill 引导微批',195)
    s.node('rule',7,16,152,16,'同核全部子图合成一个 Task；跨核仍生成 COPY 对<br>单生产者的 <i>b</i> 字节非最终输出张量：<i>r</i> 个远端消费核产生 2<i>rb</i> 边界量',9.1,theme='B')
    s.node('early',7,43,78,23,'可行控制解 → 早期扩展<br>活动核、关键链移动、分量／驻留<br>近优门控按阶段生效',9.0,theme='neutral')
    s.node('insert',96,43,63,23,'区间索引插入<br>不被早期近优门控一并跳过<br>每份候选都经官方评价',9.0);s.right('early','insert')
    s.node('spill',37,77,92,23,'成功当前解存在实测 Spill<br>且诊断预算充足？',9.3,theme='B',shape='diamond')
    s.edge('insert_spill','insert','spill',points=[(127.5,71),(83,71)]);s.text('yes',86,100.5,14,7,'是',9.0,color=COL['B'])
    s.panel('micro',7,111,141,44,'B');s.text('micro_title',10,112,135,8,'至多两份固定窗口候选：细化顺序，不迁移核心',9.3,color=COL['B'])
    for id,x,txt in [('diagnose',11,'观察原版 Step 2<br>筛选真实大张量事件'),('window',59,'窗口宽 4 或 8<br>至多 16 个不重叠窗'),('reorder',107,'每窗 ≤128 原操作<br>稳定拓扑与输入复用')]:s.text(id,x,122,37,16,txt,9.0)
    s.right('diagnose','window');s.right('window','reorder');s.text('invariant',10,143,135,9,'核归属与窗口外顺序不变，因此 Spill 前边界 COPY 不变',9.0)
    s.edge('yes_micro','spill','micro',tp=(76/141,0))
    s.node('evaluate',7,165,141,12,'结构检查与官方 B 完整评价；成功且字典序更优才更新当前解',9.0)
    s.node('output',7,184,152,9,'保留成功方案并输出；没有成功方案则返回失败，不补零',9.0,theme='neutral');s.down('micro','evaluate')
    s.edge('evaluate_output','evaluate','output',tp=(70.5/152,0));s.edge('no_output','spill','output',sp=(1,.5),tp=(1,.5),points=[(163,88.5),(163,188.5)])
    s.text('no',139,80,17,7,'否',9.0,color=COL['grey']);ss.append(s)
    s=Scene('03_R12_问题三_配置与选解','问题三：分开衡量配置效应与选解效应',189)
    s.text('solve_head',7,15,152,7,'01  分别求解：所有候选均在本次请求预算内生成',9.4,color=COL['grey'])
    s.node('pb',7,28,71,33,'场景 B 独立求解<br>原图、固定配置与相同核数<br>按 B 配置评价并选出<br><i>P</i><sub>B</sub>',9.3,theme='B')
    s.node('pl',88,28,71,33,'L2 配置下独立求解<br>本场景候选＋重新生成 B 类候选<br>先按 L2 重评，再插入与微批<br><i>P</i><sub>L</sub>',9.3,theme='L2')
    s.node('freeze_b',7,70,71,12,'02  冻结方案 <i>P</i><sub>B</sub>',9.4,theme='neutral');s.node('freeze_l',88,70,71,12,'02  冻结方案 <i>P</i><sub>L</sub>',9.4,theme='neutral');s.down('pb','freeze_b');s.down('pl','freeze_l')
    s.node('tb',7,92,46,23,'[1]  无 L2<br><i>T</i><sub>B</sub>(<i>P</i><sub>B</sub>)<br>共同分子',9.6,theme='B')
    s.node('tlb',60,92,46,23,'[2]  有 L2 · 同方案<br><i>T</i><sub>L</sub>(<i>P</i><sub>B</sub>)<br>仅评价配置改变',9.4,theme='B')
    s.node('tll',113,92,46,23,'[3]  有 L2 · 另选方案<br><i>T</i><sub>L</sub>(<i>P</i><sub>L</sub>)<br>包含方案变化',9.4,theme='L2')
    s.edge('pb_tb','freeze_b','tb',sp=(23/71,1));s.edge('pb_tlb','freeze_b','tlb',sp=(.8,1),points=[(63.8,87),(83,87)]);s.edge('pl_tll','freeze_l','tll',sp=(48/71,1))
    s.text('measure',7,120,152,7,'03  对照不反馈选解；逐图求比，再取 100 图算术均值',9.3,color=COL['grey'])
    s.node('rhw',7,133,71,23,'[1] / [2]  同方案配置比<br><i>R</i><sub>hw</sub> = <i>T</i><sub>B</sub>(<i>P</i><sub>B</sub>) / <i>T</i><sub>L</sub>(<i>P</i><sub>B</sub>)<br>方案固定，识别配置联合净效应',9.3,theme='B')
    s.node('rsel',88,133,71,23,'[1] / [3]  分别选优综合比<br><i>R</i><sub>select</sub> = <i>T</i><sub>B</sub>(<i>P</i><sub>B</sub>) / <i>T</i><sub>L</sub>(<i>P</i><sub>L</sub>)<br>配置与选解效应同时存在',9.3,theme='L2')
    s.node('cache',7,166,152,20,'只读 FIFO：发射查询；COPY_IN 完成后尝试插入；命中不刷新次序<br>L2 读池：1 MiB、250 bytes/cycle；DDR：全核共享 60 bytes/cycle<br>命中字节率与 COPY 计账另报，不代替 Makespan',9.0,theme='neutral');ss.append(s)
    return ss
class Rich(HTMLParser):
    def __init__(self):
        super().__init__();self.rows=[[]];self.stack=[];self.bold=False;self.italic=False;self.script=''
    def handle_starttag(self,tag,attrs):
        if tag=='br':self.rows.append([]);return
        self.stack.append((tag,self.bold,self.italic,self.script))
        if tag in ('b','strong'):self.bold=True
        if tag in ('i','em'):self.italic=True
        if tag in ('sub','sup'):self.script=tag
    def handle_endtag(self,tag):
        if self.stack:_,self.bold,self.italic,self.script=self.stack.pop()
    def handle_data(self,data):
        for chunk in re.findall(r'[\u2e80-\uffff]+|[^\u2e80-\uffff]+',data):self.rows[-1].append((chunk,self.bold,self.italic,self.script))
def font_paths(prototype):
    en=fm.findfont('Liberation Serif',fallback_to_default=False)
    try:zh=fm.findfont('WenQuanYi Zen Hei',fallback_to_default=False)
    except ValueError:
        if not prototype:raise RuntimeError('Install fonts-wqy-zenhei; silent font substitution is forbidden')
        zh='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
    return en,zh

def write_drawio(s,path):
    mx=ET.Element('mxfile',host='app.diagrams.net',agent='R12-flowchart-redesign',version='24.7.17');dg=ET.SubElement(mx,'diagram',id=s.name,name=s.title)
    mo=ET.SubElement(dg,'mxGraphModel',page='1',pageScale='1',pageWidth=str(s.w*PXMM),pageHeight=str(s.h*PXMM),grid='0',math='0',shadow='0')
    root=ET.SubElement(mo,'root');ET.SubElement(root,'mxCell',id='0');ET.SubElement(root,'mxCell',id='1',parent='0')
    for n in s.nodes:
        sh=n['shape'];radius='rounded=1;arcSize=7;' if sh not in ('text','diamond') else '';shp='shape=rhombus;' if sh=='diamond' else ('text;' if sh=='text' else '')
        fill='none' if sh=='text' else n['fill'];stroke='none' if sh=='text' else n['stroke']
        style=f'{shp}{radius}html=1;whiteSpace=wrap;align=center;verticalAlign=middle;fontFamily=WenQuanYi Zen Hei;fontSize={n["fs"]*4/3};fontColor={n["color"]};fillColor={fill};strokeColor={stroke};strokeWidth=1.2;spacing=5;'
        val=f'<div style="font-family:\'Liberation Serif\',\'WenQuanYi Zen Hei\';line-height:1.48;">{n["text"]}</div>' if n['text'] else ''
        c=ET.SubElement(root,'mxCell',id=n['id'],parent='1',vertex='1',value=val,style=style);c.set('r12Role',n['role'])
        ET.SubElement(c,'mxGeometry',x=str(n['x']*PXMM),y=str(n['y']*PXMM),width=str(n['w']*PXMM),height=str(n['h']*PXMM),attrib={'as':'geometry'})
    for e in s.edges:
        style=f'edgeStyle=none;rounded=0;html=1;strokeColor={COL["line"]};strokeWidth=1.15;endArrow={"block" if e["arrow"] else "none"};endFill=1;endSize=6;exitX={e["sp"][0]};exitY={e["sp"][1]};entryX={e["tp"][0]};entryY={e["tp"][1]};exitPerimeter=0;entryPerimeter=0;'
        if e['dash']:style+='dashed=1;dashPattern=4 3;'
        c=ET.SubElement(root,'mxCell',id=e['id'],parent='1',edge='1',source=e['source'],target=e['target'],style=style);c.set('r12Bus',e.get('bus',''))
        g=ET.SubElement(c,'mxGeometry',relative='1',attrib={'as':'geometry'});arr=ET.SubElement(g,'Array',attrib={'as':'points'})
        for x,y in e['points'][1:-1]:ET.SubElement(arr,'mxPoint',x=str(x*PXMM),y=str(y*PXMM))
    ET.indent(mx);ET.ElementTree(mx).write(path,encoding='utf-8',xml_declaration=True)

def parse_drawio(path):
    root=ET.parse(path).getroot();dg=root.find('diagram');mo=dg.find('mxGraphModel');s=object.__new__(Scene)
    s.name=path.stem;s.title=dg.get('name');s.w=float(mo.get('pageWidth'))/PXMM;s.h=float(mo.get('pageHeight'))/PXMM;s.nodes=[];s.edges=[]
    cells=mo.find('root').findall('mxCell');ids=[c.get('id') for c in cells];assert len(ids)==len(set(ids))
    for c in cells:
        if c.get('vertex')!='1':continue
        st=dict(p.split('=',1) for p in c.get('style').split(';') if '=' in p);g=c.find('mxGeometry')
        sh='diamond' if st.get('shape')=='rhombus' else 'text' if c.get('style').startswith('text;') else 'panel' if c.get('r12Role')=='panel' else 'rect'
        val=re.sub(r'^<div[^>]*>|</div>$','',c.get('value',''))
        s.nodes.append(dict(id=c.get('id'),x=float(g.get('x'))/PXMM,y=float(g.get('y'))/PXMM,w=float(g.get('width'))/PXMM,h=float(g.get('height'))/PXMM,text=val,fs=float(st['fontSize'])*.75,shape=sh,role=c.get('r12Role','node'),fill=st.get('fillColor','#FFFFFF'),stroke=st.get('strokeColor','#555555'),color=st.get('fontColor','#222222')))
    lu={n['id']:n for n in s.nodes}
    for c in cells:
        if c.get('edge')!='1':continue
        st=dict(p.split('=',1) for p in c.get('style').split(';') if '=' in p);a,b=lu[c.get('source')],lu[c.get('target')];sp=(float(st['exitX']),float(st['exitY']));tp=(float(st['entryX']),float(st['entryY']))
        pts=[(a['x']+a['w']*sp[0],a['y']+a['h']*sp[1])]+[(float(p.get('x'))/PXMM,float(p.get('y'))/PXMM) for p in c.findall('./mxGeometry/Array/mxPoint')]+[(b['x']+b['w']*tp[0],b['y']+b['h']*tp[1])]
        s.edges.append(dict(id=c.get('id'),source=c.get('source'),target=c.get('target'),points=pts,sp=sp,tp=tp,dash=st.get('dashed')=='1',arrow=st['endArrow']!='none',bus=c.get('r12Bus','')))
    return s

def render(s,out,en,zh,prototype=False):
    plt.rcParams.update({'pdf.fonttype':42,'ps.fonttype':42,'svg.fonttype':'path','svg.hashsalt':'r12-flowchart-20260926','font.family':['Liberation Serif',fm.FontProperties(fname=zh).get_name()]})
    fig=plt.figure(figsize=(s.w/25.4,s.h/25.4),dpi=150);ax=fig.add_axes([0,0,1,1]);ax.set(xlim=(0,s.w),ylim=(s.h,0));ax.axis('off');items=[];t2p=TextToPath()
    def prop(chunk,bold=False,italic=False,size=9.2):
        if any(ord(c)>=0x2e80 for c in chunk):return fm.FontProperties(fname=zh,size=size)
        return fm.FontProperties(family='Liberation Serif',weight='bold' if bold else 'normal',style='italic' if italic else 'normal',size=size)
    def rich(n):
        p=Rich();p.feed(n['text']);rows=p.rows;step=n['fs']/MMPT*1.48
        for j,runs in enumerate(rows):
            widths=[];props=[]
            for chunk,bold,italic,sc in runs:
                fp=prop(chunk,bold,italic,n['fs']*(.75 if sc else 1));props.append(fp);widths.append(t2p.get_text_width_height_descent(chunk,fp,False)[0]/MMPT)
            x=n['x']+(n['w']-sum(widths))/2;y=n['y']+n['h']/2+(j-(len(rows)-1)/2)*step+n['fs']/MMPT*.32
            for (chunk,bold,italic,sc),wi,fp in zip(runs,widths,props):
                dy=n['fs']/MMPT*(.25 if sc=='sub' else -.37 if sc=='sup' else 0)
                art=ax.text(x,y+dy,chunk,fontproperties=fp,ha='left',va='baseline',color=n['color'],zorder=4);items.append((art,n['id'],sc,chunk));x+=wi
    for n in s.nodes:
        if n['role']=='panel':ax.add_patch(FancyBboxPatch((n['x'],n['y']),n['w'],n['h'],boxstyle='round,pad=0,rounding_size=1.3',facecolor=n['fill'],edgecolor=n['stroke'],lw=.9,zorder=0))
    for e in s.edges:
        pts=e['points'];xx,yy=zip(*pts);ax.plot(xx,yy,color=COL['line'],lw=.85,ls=(0,(4,3)) if e['dash'] else '-',solid_capstyle='butt',solid_joinstyle='miter',zorder=1)
        if e['arrow']:
            p,q=pts[-2:];dx,dy=q[0]-p[0],q[1]-p[1];ll=math.hypot(dx,dy);ux,uy=dx/ll,dy/ll
            tri=[q,(q[0]-1.8*ux+.62*uy,q[1]-1.8*uy-.62*ux),(q[0]-1.8*ux-.62*uy,q[1]-1.8*uy+.62*ux)];ax.add_patch(Polygon(tri,closed=True,fc=COL['line'],ec='none',zorder=2))
    shapes={}
    for n in s.nodes:
        x,y,w,h=n['x'],n['y'],n['w'],n['h']
        if n['shape']=='diamond':
            v=[(x+w/2,y),(x+w,y+h/2),(x+w/2,y+h),(x,y+h/2)];ax.add_patch(Polygon(v,closed=True,facecolor=n['fill'],edgecolor=n['stroke'],lw=.9,zorder=2));shapes[n['id']]=SPolygon(v)
        elif n['shape']=='rect':ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0,rounding_size=1.3',facecolor=n['fill'],edgecolor=n['stroke'],lw=.9,zorder=2));shapes[n['id']]=SBox(x,y,x+w,y+h)
        if n['text']:rich(n)
    errors=[];fig.canvas.draw();renderer=fig.canvas.get_renderer();lu={n['id']:n for n in s.nodes};rects=[]
    for art,id,sc,txt in items:
        bb=art.get_window_extent(renderer).transformed(ax.transData.inverted());x0,x1=sorted([bb.x0,bb.x1]);y0,y1=sorted([bb.y0,bb.y1]);n=lu[id];pad=.5 if n['shape']=='text' else 1.6
        if x0<n['x']+pad-.2 or x1>n['x']+n['w']-pad+.2 or y0<n['y']+.3 or y1>n['y']+n['h']-.3:errors.append(['text_outside',id,txt,[round(z,2) for z in [x0,y0,x1,y1]]])
        rects.append((id,SBox(x0,y0,x1,y1),txt))
    for i,(id,a,txt) in enumerate(rects):
        for jd,b,tx2 in rects[i+1:]:
            if id!=jd and a.intersection(b).area>.03:errors.append(['text_overlap',id,jd])
    for e in s.edges:
        line=LineString(e['points'])
        for p,q in zip(e['points'],e['points'][1:]):
            if abs(p[0]-q[0])>.02 and abs(p[1]-q[1])>.02:errors.append(['non_orthogonal',e['id'],p,q])
        for id,shape in shapes.items():
            if id not in (e['source'],e['target']) and line.intersects(shape.buffer(-.2)):errors.append(['edge_hits_node',e['id'],id])
        for id,bb,txt in rects:
            if id not in (e['source'],e['target']) and line.intersects(bb.buffer(.5)):errors.append(['edge_near_text',e['id'],id,txt])
    for i,(id,a) in enumerate(shapes.items()):
        for jd,b in list(shapes.items())[i+1:]:
            if a.intersection(b).area>.03:errors.append(['node_overlap',id,jd])
    for i,e in enumerate(s.edges):
        for f in s.edges[i+1:]:
            if e.get('bus') and e.get('bus')==f.get('bus'):continue
            inter=LineString(e['points']).intersection(LineString(f['points']))
            if not inter.is_empty:
                ends=[Point(e['points'][0]),Point(e['points'][-1]),Point(f['points'][0]),Point(f['points'][-1])]
                if inter.length>.03 or not any(inter.distance(p)<.03 for p in ends):errors.append(['unintended_edge_crossing',e['id'],f['id']])
    for n in s.nodes:
        if n['x']<1 or n['y']<1 or n['x']+n['w']>s.w-1 or n['y']+n['h']>s.h-1:errors.append(['outside_canvas',n['id']])
    out.mkdir(exist_ok=True,parents=True)
    for ext in ('pdf','svg','png'):
        meta={'Creator':'R12 asset-only native vector renderer','CreationDate':None,'ModDate':None} if ext=='pdf' else {'Date':None} if ext=='svg' else None
        with warnings.catch_warnings(record=True) as ws:
            warnings.simplefilter('always');fig.savefig(out/(s.name+'.'+ext),dpi=600,metadata=meta,facecolor='white',edgecolor='none')
            for w in ws:
                if 'Glyph' in str(w.message):errors.append(['missing_glyph',str(w.message)])
    fig.savefig(out/(s.name+'_screen.png'),dpi=180,facecolor='white');plt.close(fig)
    doc=fitz.open(out/(s.name+'.pdf'));pg=doc[0];pg.get_pixmap(matrix=fitz.Matrix(180/72,180/72),alpha=False).save(out/(s.name+'_pdfcheck.png'))
    fonts=subprocess.check_output(['pdffonts',str(out/(s.name+'.pdf'))],text=True)
    for line in fonts.splitlines()[2:]:
        flags=re.search(r'\s(yes|no)\s+(yes|no)\s+(yes|no)\s+\d',line)
        if not flags or flags.group(1)!='yes' or flags.group(2)!='yes':errors.append(['font_not_embedded_or_subset',line])
        if 'Type 3' in line:errors.append(['type3_font',line])
    if pg.get_images():errors.append(['pdf_contains_raster'])
    svg=(out/(s.name+'.svg')).read_text()
    if re.search(r'<(?:text|image)\b',svg):errors.append(['svg_not_outlined_or_raster'])
    png=Image.open(out/(s.name+'.png'));dpi=png.info.get('dpi',(0,0))
    if min(dpi)<599:errors.append(['dpi_low',dpi])
    return dict(figure=s.name,width_mm=s.w,height_mm=s.h,body_font_min_pt=min(n['fs'] for n in s.nodes if n['text'] and n['id']!='title'),title_font_pt=12.2,fonts=fonts,png_size=png.size,png_dpi=dpi,pdf_raster_images=len(pg.get_images()),svg_text_outlined=True,vertices=len(s.nodes),edges=len(s.edges),errors=errors,prototype_font=prototype)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--prototype',action='store_true');ap.add_argument('--from-drawio',action='store_true');args=ap.parse_args();en,zh=font_paths(args.prototype)
    for d in ('drawio','exports','qa'):(OUT/d).mkdir(exist_ok=True)
    if not args.from_drawio:
        for s in designs():write_drawio(s,OUT/'drawio'/(s.name+'.drawio'))
    reports=[]
    for path in sorted((OUT/'drawio').glob('*.drawio')):
        s=parse_drawio(path);r=render(s,OUT/'exports',en,zh,args.prototype);reports.append(r)
        for suffix in ('_screen.png','_pdfcheck.png'):(OUT/'exports'/(s.name+suffix)).replace(OUT/'qa'/(s.name+suffix))
    qa=dict(base_commit=BASE,fonts={'latin':fm.FontProperties(fname=en).get_name(),'chinese':fm.FontProperties(fname=zh).get_name()},scope='new flowchart assets only; no manuscript/solver execution',figures=reports,error_count=sum(len(r['errors']) for r in reports))
    (OUT/'qa'/'geometry_and_fonts.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2),encoding='utf-8')
    for r in reports:print(r['figure'],r['errors'])
    print('TOTAL_ERRORS',qa['error_count'])
    if qa['error_count']:sys.exit(2)
if __name__=='__main__':main()
