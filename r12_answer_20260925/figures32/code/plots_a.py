# /// script
# requires-python = ">=3.12"
# dependencies = ["matplotlib==3.11.1", "numpy"]
# ///
"""Common evidence and scene-A figures. Existing data only."""
from statistics import mean
import numpy as np
from matplotlib.colors import TwoSlopeNorm
from figlib import DATA, COLORS, frame, save, boxes, timeline, group
from helpers import empirical_cdf


def f03() -> None:
    rows = DATA["graphs"]
    fig, ax = frame("F03", (1,2), 100)
    n = [r["noncopy_ops"] for r in rows]
    ax[0].scatter(n, [r["edges"] for r in rows], s=21, color=COLORS["A"], alpha=.75)
    ax[0].set(xscale="log", yscale="log", xlabel="非COPY操作数", ylabel="原始二部图边数")
    for field, name, color in (("M_work","M计算占比",COLORS["A"]),("V_work","V计算占比",COLORS["B"])):
        x,y=empirical_cdf([r[field]/(r["M_work"]+r["V_work"]) for r in rows])
        ax[1].step(x,y,where="post",label=name,color=color)
    ax[1].set(xlabel="静态计算工作量占比",ylabel="累计图比例",xlim=(-.02,1.02),ylim=(0,1.03));ax[1].legend(loc="lower right")
    save(fig,"F03",rows)


def f04() -> None:
    rows=DATA["graphs"];fig,ax=frame("F04",height=96)
    for field,name,color in (("L1_max_ratio","L1",COLORS["A"]),("UB_max_ratio","UB",COLORS["B"])):
        x,y=empirical_cdf([r[field] for r in rows]);ax[0].step(x,y,where="post",label=name,color=color)
    ax[0].axvline(1,color=COLORS["bad"],ls="--",lw=1,label="单张量等于容量")
    ax[0].set(xlabel="逐图最大单张量字节数 / 对应缓存容量",ylabel="累计图比例",xlim=(-.02,1.04),ylim=(0,1.03))
    ax[0].legend(loc="lower right");save(fig,"F04",rows)


def curve(scene: str, key: str) -> None:
    rows=[r for r in DATA["selected"] if r["scene"]==scene]
    fig,ax=frame(key,height=98);x=list(range(1,6))
    a=[1]+[mean(r["speedup"] for r in group(scene,k)) for k in range(2,6)]
    b=[1]+[mean(r["C3_speedup"] for r in group(scene,k)) for k in range(2,6)]
    ax[0].plot(x,a,"o-",color=COLORS[scene],label="R12 full")
    ax[0].plot(x,b,"s--",color=COLORS["C3"],label="C3 基线")
    ax[0].set(xticks=x,xlim=(.85,5.15),ylim=(.9,4.6),xlabel="核心数",ylabel="相对固定整图单核的平均加速比")
    ax[0].legend(loc="upper left");save(fig,key,rows)


def f08() -> None:
    rows=[r for r in DATA["selected"] if r["scene"]=="A"]
    matrix=np.array([[np.log2(r["versus_C3"]) for r in sorted(group("A",k),key=lambda r:r["case"])] for k in range(2,6)])
    limit=float(max(abs(matrix.min()),abs(matrix.max())))
    fig,ax=frame("F08",height=91)
    image=ax[0].imshow(matrix,aspect="auto",cmap="BrBG",norm=TwoSlopeNorm(vmin=-limit,vcenter=0,vmax=limit),interpolation="nearest",extent=(.5,100.5,5.5,1.5))
    ax[0].set(xticks=[1,20,40,60,80,100],yticks=[2,3,4,5],xlabel="用例编号（001—100）",ylabel="核心数")
    ax[0].grid(False);fig.colorbar(image,ax=ax[0],shrink=.85,label="log2(T_C3 / T_R12)")
    save(fig,"F08",rows)


def f09() -> None:
    rows=DATA["plansA"];fig,ax=frame("F09",(1,2),105)
    for axis,field,label in ((ax[0],"tasks","最终Task数量"),(ax[1],"median_ops","每Task操作数的图内中位数")):
        boxes(axis,[[r[field] for r in rows if r["k"]==k] for k in range(2,6)],[str(k) for k in range(2,6)])
        axis.set(yscale="log",xlabel="核心数",ylabel=label)
    save(fig,"F09",rows)


def traffic(scene: str, key: str) -> None:
    ks=range(2,6) if scene=="A" else range(1,6)
    rows=[r for r in DATA["selected"] if r["scene"]==scene]
    fig,ax=frame(key,(1,2),103)
    boundary=[mean(r["partition"] for r in group(scene,k))/1048576 for k in ks]
    spill=[mean(r["spill"] for r in group(scene,k))/1048576 for k in ks]
    ax[0].bar(list(ks),boundary,color=COLORS["partition"],label="边界新增")
    ax[0].bar(list(ks),spill,bottom=boundary,color=COLORS["spill"],label="Spill新增")
    ax[0].set(xticks=list(ks),xlabel="核心数",ylabel="平均新增COPY / MiB");ax[0].legend(loc="upper left",bbox_to_anchor=(0,1.22),ncol=2,fontsize=8.0)
    count=[sum(r["spill"]>0 for r in group(scene,k)) for k in ks]
    ax[1].bar(list(ks),count,color=COLORS["spill"],width=.62)
    ax[1].set(xticks=list(ks),ylim=(0,105),xlabel="核心数",ylabel="有Spill的图数 / 100")
    save(fig,key,rows)


def f11() -> None:
    rows=DATA["plansA"];fig,ax=frame("F11",height=102)
    boxes(ax[0],[[r["imbalance"] for r in rows if r["k"]==k] for k in range(2,6)],[str(k) for k in range(2,6)])
    ax[0].axhline(1,color="#555555",ls="--",lw=1,label="静态完全均衡")
    ax[0].set(xlabel="核心数",ylabel="最大核心工作量 / 核心平均工作量",ylim=(.95,max(r["imbalance"] for r in rows)*1.12));ax[0].legend(loc="upper left")
    save(fig,"F11",rows)


def f12() -> None:
    rows=DATA["timelineA"];fig,ax=frame("F12",height=153)
    timeline(ax[0],rows,"A / 5核 / case_087");ax[0].set_xlim(0,rows[0]["T"]/1e6*1.01)
    save(fig,"F12",rows)


DRAW={"F03":f03,"F04":f04,"F07":lambda:curve("A","F07"),"F08":f08,"F09":f09,
      "F10":lambda:traffic("A","F10"),"F11":f11,"F12":f12}
