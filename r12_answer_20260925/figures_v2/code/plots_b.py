# /// script
# requires-python = ">=3.12"
# dependencies = ["matplotlib==3.11.1", "numpy"]
# ///
"""Scene-B evidence: all observations and disclosed stage comparisons."""
from statistics import mean
import numpy as np
from figlib import DATA, COLORS, frame, save, timeline, group
from plots_a import curve, traffic


def f16() -> None:
    rows=sorted(group("B",1),key=lambda r:(r["speedup"],r["case"]))
    fig,ax=frame("F16",height=99)
    y=[100*(r["speedup"]-1) for r in rows]
    ax[0].bar(np.arange(1,101),y,color=COLORS["B"],width=.9)
    ax[0].axhline(0,color="#555555",lw=.8)
    ax[0].text(.06,.82,f"改善 {sum(r['speedup']>1 for r in rows)} 图\n持平 {sum(r['speedup']==1 for r in rows)} 图",transform=ax[0].transAxes,fontsize=9.3,linespacing=1.6)
    ax[0].set(xlim=(.5,100.5),xlabel="用例排序（按优化B1收益升序）",ylabel="加速比超出1的幅度 / %")
    save(fig,"F16",rows)


def f18() -> None:
    rows=sorted(group("B",5),key=lambda r:(-r["spill"],r["case"]))
    fig,ax=frame("F18",(1,2),105);x=np.arange(1,101)
    spill=np.array([r["spill"] for r in rows],dtype=float)
    ax[0].bar(x,spill/1048576,color=COLORS["spill"],width=.9)
    ax[0].set(yscale="symlog",xlabel="用例排序（Spill降序）",ylabel="Spill新增COPY / MiB",xlim=(0,101))
    ax[1].plot(np.r_[0,x],np.r_[0,np.cumsum(spill)/spill.sum()*100],color=COLORS["spill"])
    ax[1].plot([0,100],[0,100],ls=":",color="#999999",label="等量贡献参考")
    ax[1].set(xlabel="累计用例数",ylabel="累计Spill字节占比 / %",xlim=(0,100),ylim=(0,103));ax[1].legend(loc="lower right")
    save(fig,"F18",rows)


def f19() -> None:
    rows=DATA["stages"];fig,ax=frame("F19",(1,2),104)
    keys=["control","indexed","full"]
    y=[mean(r["REF"]/r[k] for r in rows) for k in keys]
    ax[0].plot(range(3),y,"o-",color=COLORS["B"])
    ax[0].set(xticks=range(3),xticklabels=["控制","插入后","微批后"],ylabel="相对REF平均加速比",xlabel="同次请求阶段")
    ax[0].set_ylim(min(y)*.994,max(y)*1.006)
    counts=[sum(r["indexed"]<r["control"] for r in rows),sum(r["full"]<r["indexed"] for r in rows)]
    ax[1].bar([0,1],counts,color=[COLORS["A"],COLORS["B"]],width=.55)
    ax[1].set(xticks=[0,1],xticklabels=["插入阶段","微批阶段"],ylabel="较前阶段严格改善的图数",xlabel="未改善含相同、未触发或未完成")
    ax[1].set_ylim(0,max(counts)*1.3+1)
    for i,n in enumerate(counts):ax[1].text(i,n+.25,str(n),ha="center",va="bottom",fontsize=9)
    save(fig,"F19",rows)


def f20() -> None:
    rows=group("B",5);fig,ax=frame("F20",height=110)
    for sign,label,color in ((True,"R12更快",COLORS["good"]),(False,"相同或更慢",COLORS["bad"])):
        part=[r for r in rows if (r["T"]<r["C3_T"])==sign]
        ax[0].scatter([(r["copy"]-r["C3_copy"])/1048576 for r in part],[r["reduction_pct"] for r in part],s=25,alpha=.8,color=color,label=label)
    ax[0].axvline(0,color="#777777",lw=.8);ax[0].axhline(0,color="#777777",lw=.8)
    ax[0].set(xscale="symlog",xlabel="R12−C3 新增COPY变化 / MiB（对称对数轴）",ylabel="逐图执行时间降低 / %")
    ax[0].legend(loc="upper right");save(fig,"F20",rows)


def f21() -> None:
    rows=DATA["timelineB"];fig,ax=frame("F21",height=153)
    timeline(ax[0],rows,"B / 5核 / case_073");ax[0].set_xlim(0,rows[0]["T"]/1e6*1.01)
    save(fig,"F21",rows)


DRAW={"F15":lambda:curve("B","F15"),"F16":f16,"F17":lambda:traffic("B","F17"),
      "F18":f18,"F19":f19,"F20":f20,"F21":f21}
