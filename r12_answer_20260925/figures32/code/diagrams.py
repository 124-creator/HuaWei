# /// script
# requires-python = ">=3.12"
# dependencies = ["matplotlib==3.11.1"]
# ///
"""Eight native-vector explanatory diagrams, never represented as measured data."""
from dataclasses import asdict, dataclass
from matplotlib.patches import FancyArrowPatch, Rectangle
from figlib import frame, save


@dataclass(frozen=True, slots=True)
class Node:
    id: str
    label: str
    x: float
    y: float
    width: float = 2.65
    height: float = 1.05
    color: str = "#F0F4F6"
    border: bool = True


@dataclass(frozen=True, slots=True)
class Edge:
    source: str
    target: str
    label: str = ""
    both: bool = False


def draw(key: str, nodes: list[Node], edges: list[Edge]) -> None:
    fig, axes = frame(key, height=124)
    ax=axes[0];ax.set(xlim=(0,10),ylim=(0,6));ax.axis("off")
    lookup={n.id:n for n in nodes}
    for node in nodes:
        ax.add_patch(Rectangle((node.x-node.width/2,node.y-node.height/2),node.width,node.height,
                               facecolor=node.color,edgecolor="#62737D" if node.border else "none",linewidth=1,zorder=2))
        ax.text(node.x,node.y,node.label,ha="center",va="center",fontsize=9.3,zorder=3,linespacing=1.55)
    for edge in edges:
        a,b=lookup[edge.source],lookup[edge.target]
        dx,dy=b.x-a.x,b.y-a.y
        ta=min(a.width/(2*abs(dx)) if dx else float("inf"),a.height/(2*abs(dy)) if dy else float("inf"))
        tb=min(b.width/(2*abs(dx)) if dx else float("inf"),b.height/(2*abs(dy)) if dy else float("inf"))
        assert ta+tb<1, (key,a.id,b.id)
        start=(a.x+ta*dx,a.y+ta*dy);end=(b.x-tb*dx,b.y-tb*dy)
        ax.add_patch(FancyArrowPatch(start,end,arrowstyle="<|-|>" if edge.both else "-|>",
                                    mutation_scale=11,linewidth=1.1,color="#516773",zorder=1))
        if edge.label:
            ax.text((start[0]+end[0])/2,(start[1]+end[1])/2+.16,edge.label,ha="center",va="center",fontsize=8.2,
                    bbox={"facecolor":"white","edgecolor":"none","pad":1},zorder=4)
    rows=[{"record":"node",**asdict(n)} for n in nodes]+[{"record":"edge",**asdict(e)} for e in edges]
    save(fig,key,rows)


def f01() -> None:
    nodes=[Node("ddr","共享DDR：60 bytes/cycle",5,5.2,6,.7,"#F8F2E7"),
           Node("c0","核心0\nM / V / IN / OUT\nL1 512 KiB\nUB 128 KiB",1.6,3,2.7,1.6),
           Node("c1","核心1\nM / V / IN / OUT\nL1 512 KiB\nUB 128 KiB",5,3,2.7,1.6),
           Node("cn","核心k−1\nM / V / IN / OUT\nL1 512 KiB\nUB 128 KiB",8.4,3,2.7,1.6),
           Node("l2","仅Q3：共享只读L2，1 MiB\n独立读带宽250 bytes/cycle",5,.85,6,1,"#EDF5F1")]
    edges=[Edge("ddr",c,both=True) for c in ("c0","c1","cn")]+[Edge("l2",c) for c in ("c0","c1","cn")]
    draw("F01",nodes,edges)


def f02() -> None:
    nodes=[Node("in","原始DAG\n固定配置与核数",1.6,5),Node("gen","依赖与张量索引\n预定候选构造",5,5),
           Node("check","覆盖与联合无环\n去重及下界剪枝",8.4,5),Node("eval","官方完整评价\n记录失败与超时",8.4,3),
           Node("compare","比较Makespan\n相同时比较COPY",5,3),Node("keep","保留成功当前解\n只接受真实改进",1.6,3),
           Node("out","输出切图与核序\n记录版本与预算",1.6,1)]
    draw("F02",nodes,[Edge("in","gen"),Edge("gen","check"),Edge("check","eval"),Edge("eval","compare"),Edge("compare","keep"),Edge("keep","out")])


def f05() -> None:
    nodes=[Node("a","核心0 / Task s1\n完成并写出",1.6,4.6),Node("d1","DDR中转\n缓存不跨Task保留",5,4.6),Node("b","核心0 / Task s2\n前Task后等待100",8.4,4.6),
           Node("c","核心0 / Task s1\n跨核前驱完成",1.6,1.7),Node("d2","DDR中转\n所有边界需搬运",5,1.7),Node("e","核心1 / Task s2\n跨核等待1000",8.4,1.7)]
    draw("F05",nodes,[Edge("a","d1"),Edge("d1","b"),Edge("c","d2"),Edge("d2","e")])


def f06() -> None:
    nodes=[Node("s0","依赖带0 / S0\nu0 → u1",1.6,3.5),
           Node("s1","依赖带1 / S1\nu2",5,4.85,2.65,1.05,"#EDF5F1"),
           Node("s2","依赖带1 / S2\nu3",5,2.1,2.65,1.05,"#EDF5F1"),
           Node("s3","依赖带2 / S3\nu4 → u5",8.4,3.5,2.65,1.05,"#F8F2E7"),
           Node("q0","核心0：S0 → S1 → S3",3,.65,5,.7,"#FFFFFF",False),
           Node("q1","核心1：S2",8,.65,3,.7,"#FFFFFF",False)]
    draw("F06",nodes,[Edge("s0","s1"),Edge("s0","s2"),Edge("s1","s3"),Edge("s2","s3")])


def f13() -> None:
    nodes=[Node("s1","核心0 / 子图s1",1.6,4.8),Node("local","私有L1 / UB\n允许驻留复用",5,4.8,2.65,1.05,"#EDF5F1"),
           Node("s2","核心0 / 子图s2\n仍属同一Task",8.4,4.8),Node("spill","容量不足\n换出与再换入",1.6,1.8,2.65,1.05,"#F8F2E7"),
           Node("ddr","DDR\n跨核源COPY_OUT",5,1.8,2.65,1.05,"#F8F2E7"),Node("remote","核心1 / COPY_IN\n源OUT完成后＋500",8.4,1.8)]
    draw("F13",nodes,[Edge("s1","local"),Edge("local","s2"),Edge("local","ddr","跨核时"),Edge("local","spill","容量不足"),Edge("spill","ddr",both=True),Edge("ddr","remote")])


def f14() -> None:
    nodes=[Node("heading0","重排前：交替使用输入A与B",5,5.35,8,.55,"#FFFFFF",False),
           Node("heading1","重排后：同核窗口内成组复用",5,2.65,8,.55,"#FFFFFF",False)];edges=[]
    before=["A1","B1","A2","B2","A3","B3","A4","B4"]
    after=["A1","A2","A3","A4","B1","B2","B3","B4"]
    for row,order,y in (("before",before,4.4),("after",after,1.7)):
        for i,label in enumerate(order):
            key=f"{row}{i}";nodes.append(Node(key,label,.7+i*1.23,y,1.0,.85,"#E3EFF0" if label[0]=="A" else "#F4EADC"))
            if i:edges.append(Edge(f"{row}{i-1}",key))
    draw("F14",nodes,edges)


def f22() -> None:
    nodes=[Node("in","COPY_IN发射\n查询逻辑张量键",5,5.15),Node("lookup","此刻键是否在FIFO？\n命中不刷新次序",5,3.75),
           Node("hit","命中：L2读池\n250 bytes/cycle",2,2.2),Node("miss","未命中：DDR池\n60 bytes/cycle",8,2.2),
           Node("end","完成时尝试插入\n不存在且可容纳才插入\n不足则FIFO逐出",5,.65,3.5,1.15)]
    draw("F22",nodes,[Edge("in","lookup"),Edge("lookup","hit"),Edge("lookup","miss"),Edge("hit","end"),Edge("miss","end")])


def f23() -> None:
    nodes=[Node("pb","冻结B方案 PB",1.6,4.8),Node("b","B配置评分\nB耗时(PB)",5,5),Node("l","L2配置评分\nL2耗时(PB)",5,3),
           Node("hw","配置效应\nB(PB) ÷ L2(PB)",8.4,4),Node("pl","L2另选方案 PL",1.6,1),
           Node("ls","L2配置评分\nL2耗时(PL)",5,1),Node("sel","共用B(PB)分子\n综合选优比\nB(PB) ÷ L2(PL)",8.4,1,2.65,1.35)]
    draw("F23",nodes,[Edge("pb","b"),Edge("pb","l"),Edge("b","hw"),Edge("l","hw"),Edge("pl","ls"),Edge("ls","sel")])


DRAW={"F01":f01,"F02":f02,"F05":f05,"F06":f06,"F13":f13,"F14":f14,"F22":f22,"F23":f23}
