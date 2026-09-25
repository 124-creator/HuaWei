# /// script
# requires-python = ">=3.12"
# dependencies = ["matplotlib==3.11.1", "numpy"]
# ///
"""Fixed-plan L2 comparisons and synthesis; never reinterpret selected plans."""
from statistics import mean
import numpy as np
from figlib import DATA, COLORS, frame, save, boxes, timeline, group


def f24() -> None:
    rows=DATA["pairs"];fig,ax=frame("F24",(1,2),107);ks=list(range(1,6))
    gs=[[r for r in rows if r["k"]==k] for k in ks]
    b=[mean(r["REF"]/r["B"] for r in g) for g in gs];l=[mean(r["REF"]/r["L2_fixed"] for r in g) for g in gs]
    ax[0].plot(ks,b,"o-",color=COLORS["B"],label="无L2 / 固定PB")
    ax[0].plot(ks,l,"s--",color=COLORS["L2"],label="有L2 / 同一PB")
    ax[0].set(xlabel="核心数",ylabel="相对REF的平均加速比",xticks=ks,ylim=(.9,4.5));ax[0].legend(loc="upper left",fontsize=8)
    ax[1].plot(ks,[mean(r["hardware"] for r in g) for g in gs],"o-",color=COLORS["L2"],label="同方案配置比")
    ax[1].plot(ks,[mean(r["selected"] for r in g) for g in gs],"^--",color="#756580",label="分别选优比")
    ax[1].axhline(1,color="#777777",lw=.7,ls=":")
    ax[1].set(xlabel="核心数",ylabel="逐图耗时比的算术均值",xticks=ks,ylim=(.999,1.034));ax[1].legend(loc="upper left",fontsize=8)
    save(fig,"F24",rows)


def f25() -> None:
    rows=DATA["pairs"];fig,ax=frame("F25",height=107)
    boxes(ax[0],[[r["hardware"] for r in rows if r["k"]==k] for k in range(1,6)],[str(k) for k in range(1,6)])
    ax[0].axhline(1,color="#555555",ls="--",lw=.8)
    ax[0].set(xlabel="核心数",ylabel="同方案配置比 T_B / T_L2",ylim=(.98,max(r["hardware"] for r in rows)*1.025))
    save(fig,"F25",rows)


def f26() -> None:
    rows=[r for r in DATA["pairs"] if r["k"]==5];fig,ax=frame("F26",height=107)
    ax[0].scatter([100*r["hit"] for r in rows],[r["hardware"] for r in rows],s=28,alpha=.72,color=COLORS["L2"])
    ax[0].axhline(1,color="#777777",ls="--",lw=.9)
    for case in ("case_073","case_026"):
        r=next(x for x in rows if x["case"]==case)
        offset=(8,8) if case=="case_073" else (36,.989)
        coordinates="offset points" if case=="case_073" else "data"
        ax[0].annotate(case,(100*r["hit"],r["hardware"]),xytext=offset,textcoords=coordinates,fontsize=8.3,va="center",
                       arrowprops={"arrowstyle":"-","color":"#666666","lw":.6})
    ax[0].set(xlabel="逐图命中字节率 / %",ylabel="同方案配置比 T_B / T_L2",xlim=(-2,102),ylim=(.985,1.15))
    save(fig,"F26",rows)


def f27() -> None:
    rows=DATA["cache"];fig,ax=frame("F27",(2,1),135)
    x=[r["time"]/1e6 for r in rows]
    assert all(b>=a for a,b in zip(x,x[1:]))
    ax[0].step(x,[r["used"]/1048576 for r in rows],where="post",color=COLORS["L2"])
    ax[0].axhline(1,color="#555555",ls="--",lw=.8,label="L2容量")
    ax[0].set(ylabel="FIFO缓存占用 / MiB",ylim=(-.02,1.08));ax[0].legend(loc="lower right")
    ax[1].step(x,[100*r["cumulative_hit"] for r in rows],where="post",color=COLORS["B"])
    ax[1].set(ylabel="累计命中字节率 / %",xlabel="执行时间 / 百万 cycles",ylim=(0,102))
    for a in ax:a.set_xlim(0,rows[0]["T"]/1e6)
    save(fig,"F27",rows)


def f28() -> None:
    fig,ax=frame("F28",(2,1),202)
    b,l=DATA["timelineB"],DATA["timelineL2"]
    timeline(ax[0],b,"(a) 无L2：固定B方案")
    timeline(ax[1],l,"(b) 有L2：同一B方案")
    for axis in ax:axis.set_xlim(0,b[0]["T"]/1e6*1.01)
    rows=[{"configuration":"B",**r} for r in b]+[{"configuration":"L2_same_B",**r} for r in l]
    save(fig,"F28",rows)


def f29() -> None:
    rows=sorted([r for r in DATA["pairs"] if r["k"]==5 and r["different"]],key=lambda r:r["case"])
    assert len(rows)==28
    fig,ax=frame("F29",height=171);y=np.arange(len(rows));v=[r["reselection"] for r in rows]
    ax[0].hlines(y,np.minimum(1,v),np.maximum(1,v),color="#AAB6BD",lw=1.3)
    ax[0].scatter(v,y,c=[COLORS["good"] if x>=1 else COLORS["bad"] for x in v],s=28)
    ax[0].axvline(1,color="#777777",ls="--",lw=.8)
    ax[0].set(yticks=y,yticklabels=[r["case"] for r in rows],ylim=(len(rows)-.3,-.8),
              xlabel="同一L2配置：T_L2(PB) / T_L2(PL)")
    ax[0].grid(axis="y",visible=False);ax[0].tick_params(axis="y",length=0)
    save(fig,"F29",rows)


def f30() -> None:
    rows=sorted([r for r in DATA["pairs"] if r["hardware"]<1],key=lambda r:(r["k"],r["case"]))
    assert len(rows)==8
    fig,ax=frame("F30",height=109);y=np.arange(8);v=[r["hardware"] for r in rows]
    ax[0].hlines(y,v,1,color="#C8A2A2",lw=1.4)
    ax[0].scatter(v,y,color=COLORS["bad"],s=35)
    ax[0].axvline(1,color="#777777",ls="--",lw=.8)
    for i,value in enumerate(v):ax[0].text(1.0003,i,f"{value:.6f}",fontsize=8.4,va="center")
    ax[0].set(yticks=y,yticklabels=[f"{r['case']} / {r['k']}核" for r in rows],ylim=(7.7,-.7),
              xlim=(min(v)-.0008,1.0023),xlabel="同方案配置比 T_B / T_L2（放大区间）")
    ax[0].grid(axis="y",visible=False);save(fig,"F30",rows)


def f31() -> None:
    rows=DATA["selected"];fig,ax=frame("F31",height=151)
    groups=[(s,k) for s in ("A","B","L2") for k in range(1,6) if s!="A" or k>1]
    wins=[];ties=[];loss=[]
    for s,k in groups:
        g=group(s,k);wins.append(sum(r["T"]<r["C3_T"] for r in g));ties.append(sum(r["T"]==r["C3_T"] for r in g));loss.append(sum(r["T"]>r["C3_T"] for r in g))
    y=np.arange(len(groups))
    ax[0].barh(y,wins,color=COLORS["good"],label="R12更快")
    ax[0].barh(y,ties,left=wins,color="#C8CED2",label="相同")
    ax[0].barh(y,loss,left=np.array(wins)+ties,color=COLORS["bad"],label="R12更慢")
    for i,(w,t,l) in enumerate(zip(wins,ties,loss)):ax[0].text(102,i,f"{w} / {t} / {l}",fontsize=8.4,va="center")
    ax[0].set(yticks=y,yticklabels=[f"{s} / {k}核" for s,k in groups],ylim=(len(groups)-.3,-.8),xlim=(0,122),
              xticks=[0,20,40,60,80,100],xlabel="用例数（右侧为更快 / 相同 / 更慢）")
    ax[0].legend(loc="lower left",bbox_to_anchor=(0,1.01),ncol=3);ax[0].grid(axis="y",visible=False)
    save(fig,"F31",rows)


def f32() -> None:
    rows=DATA["selected"];fig,ax=frame("F32",height=119)
    groups=[(s,k) for s in ("A","B","L2") for k in range(1,6) if s!="A" or k>1]
    boxes(ax[0],[[r["wall"] for r in group(s,k)] for s,k in groups],[f"{s}{k}" for s,k in groups])
    for i,(s,k) in enumerate(groups,1):
        for r in group(s,k):
            if r["budget"]>600:ax[0].scatter(i,r["wall"],marker="D",s=45,facecolor="none",edgecolor=COLORS["bad"],zorder=5)
    ax[0].axhline(600,color="#777777",ls="--",lw=.8,label="常规软预算600 s")
    ax[0].axhline(1800,color=COLORS["bad"],ls=":",lw=.9,label="A087补跑预算1800 s")
    ax[0].set(yscale="log",ylim=(min(r["wall"] for r in rows)*.7,2600),xlabel="场景与核心数",ylabel="完整请求墙钟 / s（对数轴）")
    ax[0].legend(loc="lower right",bbox_to_anchor=(1,1.01),ncol=2,fontsize=8.1);save(fig,"F32",rows)


DRAW={"F24":f24,"F25":f25,"F26":f26,"F27":f27,"F28":f28,"F29":f29,"F30":f30,"F31":f31,"F32":f32}
