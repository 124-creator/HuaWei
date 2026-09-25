# 问题二：场景B编号公式（12条）

**来源约定**：Q2.md指冻结解答 `publication/solutions/Q2.md`。B每核全部子图合并为一个Task。

（2-1）评价算子与目标

$$
T_B(P)=\operatorname{Makespan}\!\left(\operatorname{Eval}^{\mathrm{orig}}_B(G,P;\theta)\right).
\tag{2-1}
$$

- 单位：cycles；与场景A同一方案表示 $P=(g,a,\pi)$。来源：Q2.md 第12行。

（2-2）字典序择优

$$
\min_{P\in\mathcal F_B}^{\mathrm{lex}}\left(T_B(P),\,D_{\mathrm{added}}(P)\right).
\tag{2-2}
$$

- 先比Makespan，相同时比新增COPY。来源：Q2.md 第16–18行。

（2-3）跨核OUT完成后同步（目标COPY_IN的必要释放条件）

$$
s(\mathrm{COPY\_IN}_e)\ \ge\ f(\mathrm{COPY\_OUT}_e)+500.
\tag{2-3}
$$

- $s,f$ 为开始、完成时刻；$e$ 为一条实际跨核传输。目标操作还须满足Pipe FIFO、本地前驱与内存申请次序；该式不等于"立即发射"。来源：Q2.md 第21–24行。

（2-4）单生产者中间张量的Spill前边界COPY计账

$$
D^{B}_{\text{边界}}(t_b)=\begin{cases}(r+1)\,b,&r>0,\\ 0,&r=0,\end{cases}
\tag{2-4}
$$

- $b$ 为张量字节数；$r$ 为不同远端消费核心数；计一次写出加 $r$ 次读入。该特例不含Spill、原始输入重复读入与最终输出。来源：Q2.md 第26行。

（2-5）微批核心归属不变式

$$
a_{\mathrm{new}}\!\left(g_{\mathrm{new}}(u)\right)=a_{\mathrm{old}}\!\left(g_{\mathrm{old}}(u)\right),\qquad \forall u\in U.
\tag{2-5}
$$

- 窗口外顺序与所有原操作核心归属均不改变。来源：Q2.md 第39行。

（2-6）partition计账不变（B每核一个Task的直接推论）

$$
D_{\mathrm{partition,new}}^{B}=D_{\mathrm{partition,old}}^{B}.
\tag{2-6}
$$

- partition指Spill前边界COPY；顺序与Spill仍可改变，不能推出Makespan不变。来源：Q2.md 第45–47行。

（2-7）候选家族定义（活动核数与驻留组织）

$$
\mathcal C_{\mathrm{family}}=\left\{\left(m,\mathrm{target}\right):\ m\le k,\ \mathrm{target}\in\{0,512,2048\}\right\},\qquad \text{补空队列使输出始终含 }k\text{ 条核心队列}.
\tag{2-7}
$$

- 该扩展阶段最多评价六个新候选。来源：Q2.md 第32行。

（2-8）Spill触发的微批诊断条件

$$
\mathrm{size}(t_b)\ge \tfrac14 C_{m},\qquad \mathrm{dist}\!\left(s_{\mathrm{before}},s_{\mathrm{after}}\right)\le 8.
\tag{2-8}
$$

- 仅当当前成功B/L2结果 `spill_added_copy_bytes>0` 时进行诊断；$C_m$ 为对应容器容量。来源：Q2.md 第34–36行。

（2-9）微批窗口参数约束

$$
w\in\{4,8\},\qquad \#\{\text{窗口}\}\le16\ (\text{互不重叠}),\qquad \#\{\text{原计算操作}\}\le128\ (\text{每窗口}).
\tag{2-9}
$$

- 窗口内用稳定Kahn顺序优先复用最近使用的大型外部输入，平局沿原位置与ID确定。来源：Q2.md 第36行。

（2-10）阶段平均加速比（同次请求）

$$
\overline S_{\mathrm{stage}}=\frac{1}{100}\sum_{i=1}^{100}\frac{T_{\mathrm{REF},i}}{T_{\mathrm{stage},i}},\qquad \mathrm{stage}\in\{\mathrm{control},\mathrm{indexed},\mathrm{full}\}.
\tag{2-10}
$$

- 三阶段共享同一总软预算；不构成等预算独立消融。来源：Q2.md 第79行与图F19。

（2-11）相对C3的逐图耗时降幅均值

$$
\overline\rho_B=\frac{1}{100}\sum_{i=1}^{100}\left(1-\frac{T_{\mathrm{R12},i}}{T_{\mathrm{C3},i}}\right)=34.4910\%.
\tag{2-11}
$$

- 非程序墙钟降幅。来源：Q2.md 第79行。

（2-12）阶段严格改善计数

$$
N_{j}=\#\left\{i:\ T_{\mathrm{stage}_{j+1},i}<T_{\mathrm{stage}_{j},i}\right\},\qquad (N_{\text{插入}},N_{\text{微批}})=(12,\,2).
\tag{2-12}
$$

- 其余含相同、未触发或未完成；微批阶段两个改善例为 case_067 与 case_073。来源：Q2.md 第79行与图F19/F21。

## 三线表（问题二）

{{TABLE:q2_main}}

{{TABLE:q2_copy5}}

{{TABLE:q2_stages}}

{{TABLE:q2_case073}}
