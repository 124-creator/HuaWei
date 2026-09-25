# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Data-linked takeaways for the figure catalogue; no invented experiment claims."""
import json
from pathlib import Path
from statistics import mean, median
from v3_data import cache_marker


def conclusions() -> dict[str, str]:
    d=json.loads((Path(__file__).resolve().parents[1]/"dataset.json").read_bytes())
    a=[r for r in d["selected"] if r["scene"]=="A" and r["k"]==5]
    b=[r for r in d["selected"] if r["scene"]=="B" and r["k"]==5]
    b1=[r for r in d["selected"] if r["scene"]=="B" and r["k"]==1]
    p=[r for r in d["pairs"] if r["k"]==5]
    stages=d["stages"]
    changed=[r for r in p if r["different"]]
    spill=sorted((r["spill"] for r in b),reverse=True)
    improved=[r for r in stages if r["full"]<r["indexed"]]
    delta_sum=sum(r["REF"]/r["full"]-r["REF"]/r["indexed"] for r in improved)
    case073=next(r for r in improved if r["case"]=="case_073")
    share073=(case073["REF"]/case073["full"]-case073["REF"]/case073["indexed"])/delta_sum
    marker=cache_marker()
    return {
      "F01":"三种场景共用固定DDR与私有缓存；只有Q3增加独立只读L2。画出的核心仅为代表，不表示固定只有三个核心。",
      "F02":"同一概念DAG在操作—张量、子图划分和核心队列视图中保持对象对应，分别解释g、a、π；输出不含自由指定的开始时刻。",
      "F03":f"100张图的非COPY操作数范围为{min(r['noncopy_ops'] for r in d['graphs'])}至{max(r['noncopy_ops'] for r in d['graphs'])}；M/V计算组成有明显差异。",
      "F04":"单张量相对容量的大小仅描述输入尺度；多个张量生命周期重叠仍可能引起Spill，不能从本图推断运行时峰值。",
      "F05":"单生产者、单消费者且非最终输出的b字节张量，在A的同核Task边界需写出和读入共2b；B中同核合并Task且无Spill时可省去该边界量。",
      "F06":"原DAG无环不够：核心队列增加的顺序边也必须参与检查。反例S3先于S0使S0→S1→S3→S0成环。",
      "F07":f"A五核平均REF加速比为{mean(r['speedup'] for r in a):.6f}，对照为{mean(r['C3_speedup'] for r in a):.6f}。这是不同搜索成本的最终方案比较。",
      "F08":"全部400格同时显示；负色保留较C3更慢的配置，平均优势不代表逐例必胜。色标使用对称log2比值且未截断观测。",
      "F09":"Task数量和每Task粒度在用例间差异较大，算法并非固定把图均分成k块；箱体只描述样本分布。",
      "F10":"边界新增与Spill新增合计为官方added_copy_bytes；右侧统计有Spill的图数，避免把少数大值误解为全部用例的典型情况。",
      "F11":"不平衡度为最大核心M+V工作量除以核心均值，1表示静态完全均衡；此量忽略通信、双Pipe重叠和等待，不是实际利用率。",
      "F12":f"这是case_087的A五核补跑结果，Makespan为{d['timelineA'][0]['T']} cycles；画面中的空白保留真实空闲，不自动解释其唯一原因。",
      "F13":"概念例的320 KiB与256 KiB张量均可单独放入512 KiB L1，但不能同时常驻。逻辑活期重叠不能直接当作实测占用或Spill量。",
      "F14":"四条A_i→B_i依赖和所有原操作核心归属不变；共享大型输入可从交替使用改成成组使用。中间张量活期及完整执行代价仍可能增加，不能单凭此图认定收益。",
      "F15":f"B五核平均REF加速比为{mean(r['speedup'] for r in b):.6f}；一核参考点按定义取1，不混入优化后B1。",
      "F16":f"优化B1平均REF加速比为{mean(r['speedup'] for r in b1):.6f}；{sum(r['T']<r['REF'] for r in b1)}图改善、{sum(r['T']==r['REF'] for r in b1)}图相同。纵轴是加速比超出1的幅度，不是耗时降低率。",
      "F17":"B的跨核边界开销与核内Spill可随核数呈不同变化；按字节分开报告，不用单个总量掩盖机制差异。",
      "F18":f"按Spill降序的前10图贡献五核B总Spill字节的{100*sum(spill[:10])/sum(spill):.2f}%；这是一种集中度描述，不是统计推断。",
      "F19":f"控制、插入后、微批后的平均REF加速比分别为{mean(r['REF']/r['control'] for r in stages):.6f}、{mean(r['REF']/r['indexed'] for r in stages):.6f}、{mean(r['REF']/r['full'] for r in stages):.6f}。同次请求阶段共享预算，不冒称独立等预算消融。",
      "F20":f"五核B有{sum(r['T']<r['C3_T'] and r['copy']>r['C3_copy'] for r in b)}图比C3更快但新增COPY更高；主次目标确有权衡，不是每例双目标支配。",
      "F21":f"B5的100请求中，case_067和case_073在微批阶段进一步改善；case_073贡献该阶段平均加速比增量的{100*share073:.2f}%。这不是整体R12收益占比，也不是触发率或等预算独立消融。",
      "F22":"命中在发射时决定带宽池，插入在完成时发生；命中读取完成时若键已被逐出，也可能重新插入。无键或超容量不插入。",
      "F23":"同方案PB在B/L2下比较描述配置效应；PB与PL分别评分的比值包含选解变化，二者不能互换。",
      "F24":f"五核PB在B/L2下相对REF的均值分别为{mean(r['REF']/r['B'] for r in p):.6f}/{mean(r['REF']/r['L2_fixed'] for r in p):.6f}；另选PL为{mean(r['REF']/r['L2_best'] for r in p):.6f}。右侧配置比和综合比均先逐图计算再汇总。",
      "F25":f"五核同方案配置比的中位数为{median(r['hardware'] for r in p):.6f}，均值为{mean(r['hardware'] for r in p):.6f}；ECDF局部视窗保留100图分母，左侧仍显示全部核数的完整长尾。",
      "F26":"命中字节率与整体配置收益并非一一对应；计算、等待和搬运竞争共同影响Makespan。本散点不能分别识别容量与带宽的因果贡献。",
      "F27":f"完整{len(d['cache'])}条缓存事件保留。共同窗口内最大占用净降位于e{marker.index}（{marker.time} cycles）：{marker.before}降至{marker.after} bytes。该insert事件净降{marker.net_drop/1024:.0f} KiB，不等于驱逐量，也不用于未核实的Pipe归因。",
      "F28":f"固定同一PB，B与L2的Makespan为{d['timelineB'][0]['T']}和{d['timelineL2'][0]['T']} cycles。仅在L2视图标出F27的全局缓存事件e{marker.index}，不把该事件误配给某个核心0操作。",
      "F29":f"五核共有{len(changed)}对方案不同；在同一L2配置中，另选方案较PB有{sum(r['reselection']>1 for r in changed)}例更快、{sum(r['reselection']==1 for r in changed)}例相同、{sum(r['reselection']<1 for r in changed)}例更慢，不能默认为全部改善。",
      "F30":"8条配置比小于1的记录完整保留；最小值对应case_026五核。图只确认退化事实，不把未经核实的机制写成原因。",
      "F31":"在14个配置组中保留全部胜平负。相同评估配置下的最终解比较并不等于同运行时间、同搜索次数的算法效率比较。",
      "F32":"箱体为四分位范围，须线为1.5IQR，圆点为离群观测，红色菱形标记1800秒补跑。各批次并发负载不同，只报告真实成本，不据此作跨场景算法耗时优劣证明。",
      "F33":"根据实际安全链与依赖带代码构造教学例：依赖带宽度为2时，带内弱连通分量分别形成S0、S1和相互独立的S2/S3；不能把整带强制并为一个Task。示意规模不触发2048操作软分组目标。",
      "F34":"图中1单位为100代理cycles。给定ready=5、duration=5、gap=1，首个可行候选起点为14，即1400代理cycles；左子树最大空隙3小于所需6，可整体跳过。树形不是实际Treap快照，代理时刻不是官方开始时刻。",
    }
