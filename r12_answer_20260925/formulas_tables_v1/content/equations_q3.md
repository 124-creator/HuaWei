# 问题三：共享只读L2编号公式（11条）

**来源约定**：Q3.md指冻结解答 `publication/solutions/Q3.md`。容量 $1\,\mathrm{MiB}=1048576$ bytes、读带宽250 bytes/cycle；DDR为60 bytes/cycle。

（3-1）FIFO容量约束

$$
H(t)=\sum_{\tau\in Q(t)} b_\tau\ \le\ 1048576.
\tag{3-1}
$$

- $Q(t)$：按插入先后排列的逻辑张量FIFO；$b_\tau$ 为字节数。来源：Q3.md 第12–14行。

（3-2）逐图按字节命中率

$$
h_i=\frac{B_{\mathrm{hit},i}}{B_{\mathrm{hit},i}+B_{\mathrm{miss},i}},\qquad B_{\mathrm{hit},i}+B_{\mathrm{miss},i}>0;\quad \text{分母为零时沿原版约定 }h_i=0.
\tag{3-2}
$$

- 命中在发射时决定带宽池；插入在完成时尝试；命中不刷新已有键的FIFO次序。来源：Q3.md 第17–19行与第9行。

（3-3）两个互不占用的带宽池约束

$$
\sum_{j\in\mathcal A_p(t)} v_j(t)\ \le\ B_p,\qquad B_{\mathrm{DDR}}=60,\quad B_{\mathrm{L2}}=250\ \text{bytes/cycle}.
\tag{3-3}
$$

- $\mathcal A_p(t)$：池 $p$ 的在途传输集合；每个池由全部核心共享。来源：Q3.md 第22–24行。

（3-4）单次搬运的理想参考延迟（忽略取整与并发）

$$
d_{\mathrm{DDR}}^{\mathrm{isolated}}=b/60,\qquad d_{\mathrm{L2}}^{\mathrm{isolated}}=b/250.
\tag{3-4}
$$

- 仅用于解释独立读池，不替代原版事件模拟。来源：Q3.md 第29–31行。

（3-5）同方案配置比

$$
R_{\mathrm{hw},i,k}=\frac{T_B\!\left(P_{B,i,k}\right)}{T_L\!\left(P_{B,i,k}\right)}.
\tag{3-5}
$$

- 分子分母为同一方案在无/有L2下的官方Makespan。来源：Q3.md 第45行。

（3-6）分别选优综合比

$$
R_{\mathrm{select},i,k}=\frac{T_B\!\left(P_{B,i,k}\right)}{T_L\!\left(P_{L,i,k}\right)}.
\tag{3-6}
$$

- 包含选解变化，不能称纯硬件收益。来源：Q3.md 第49行。

（3-7）逐例分解恒等式

$$
R_{\mathrm{select},i,k}=R_{\mathrm{hw},i,k}\cdot\frac{T_L\!\left(P_{B,i,k}\right)}{T_L\!\left(P_{L,i,k}\right)}.
\tag{3-7}
$$

- 逐例成立，不意味着三个算术均值可直接相乘。来源：Q3.md 第53–55行。

（3-8）同方案配置比均值

$$
\overline R_{\mathrm{hw},k}=\frac{1}{100}\sum_{i=1}^{100}R_{\mathrm{hw},i,k}.
\tag{3-8}
$$

- 两条主性能曲线分别用同一个整图REF归一化；配置比另行对100个逐图比值取平均，不能用两条均值曲线相除。来源：Q3.md 第58–60行。

（3-9）固定 $P_B$ 开启L2相对REF的均值

$$
\overline S_{L2}^{\mathrm{fixed}}=\frac{1}{100}\sum_{i=1}^{100}\frac{T_{\mathrm{REF},i}}{T_L\!\left(P_{B,i}\right)}=4.187457.
\tag{3-9}
$$

- 与"另选 $P_L$"口径分开报告。来源：Q3.md 第82行。

（3-10）L2独立选优相对REF的均值

$$
\overline S_{L2}^{\mathrm{select}}=\frac{1}{100}\sum_{i=1}^{100}\frac{T_{\mathrm{REF},i}}{T_L\!\left(P_{L,i}\right)}=4.218978.
\tag{3-10}
$$

- 来自冻结主表 `selected_summary.csv`（L2,5）。来源：Q3.md 第5行与closeout主表。

（3-11）逐图命中字节率的算术平均

$$
\overline h=\frac{1}{100}\sum_{i=1}^{100}h_i=23.4614\%.
\tag{3-11}
$$

- 不是把100图命中字节池化后计算的命中率，也不是Makespan下降比例。来源：Q3.md 第92行。

## 三线表（问题三）

{{TABLE:q3_ratios}}

{{TABLE:q3_cases}}

{{TABLE:q3_degraded}}

{{TABLE:q3_cost5}}

{{TABLE:q3_summary}}
