"""Render a human report from the final audited checkpoint (no new experiments)."""
import json,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads((ROOT/p).read_text())
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--export-dir',type=Path,default=ROOT);args=parser.parse_args();args.export_dir.mkdir(parents=True,exist_ok=True)
 a=read('stage3_reports/evidence_audit_stage3.json');cover=read('stage3_reports/frozen_coverage.json');base=read('stage3_reports/baseline_coverage_stage3.json');sel=read('stage3_reports/targeted_selected_summary.json')
 lines=['# 第三轮：覆盖率推进、Trace归因与受控优化','', '依据用户给定赛题、原始附件、前两轮证据和本轮实际执行记录。所有时钟周期均来自原版评估结果；本文不使用替代评分器，不把未完成项插补为成功。','',
 '## 1. 本轮完成范围与未完成项','',f"固定单核基准：由91例推进到{base['successful']}例；仍缺：{', '.join(base['missing']) or '无'}。",'',
 f"冻结评测矩阵事先声明1400项：100例×2～5核×A/B/L2的1200项，加100例×1核×B/L2的200项。当前状态：{cover['counts']}。已有{cover['cases_with_any_completed']}个用例至少完成一项，其中{cover['cases_with_all_14_completed']}个用例完成全部14项。",'',
 '未运行、取消、超时、评估错误分别保留。按输入文件大小排序只为安排执行，已完成子集不是随机样本；在所有基准和对应场景齐备前，不给出正式100例平均加速比，也不以缺失项为1。','',
 '本轮新增单核记录：','', '| 用例 | 状态 | Makespan/cycles | 本次墙钟/秒 |','|---|---|---:|---:|']
 for p in sorted((ROOT/'stage3_results/baseline').glob('case_*.json')):
  if p.name.endswith('.official.json'):continue
  r=json.loads(p.read_text());lines.append(f"| {r['case']} | {r['status']} | {r.get('makespan','—')} | {r.get('wall_seconds',0):.2f} |")
 lines += ['', '本轮未以延长基准的运行上限替代求解器效率分析。固定基准是整图单Task，由赛题规定；原版核内和场景A模拟存在重复状态扫描。额外80秒插桩观察只用于诊断，在观测区间内操作数量和模拟时间持续推进；插桩记录不是正式结果，不能据超时断言死循环。', '',
 '## 2. 冻结覆盖协议','',
 '调度算法固定为上一轮v0.2：每个多核场景单次求解软预算600秒、每候选评估上限120秒、基于全局计算下界的3%差距停止。候选、参数及源码哈希冻结；没有按测试用例临时指定“历史最好方案”。构造与I/O并非硬实时中断。', '',
 '1核B/L2采用同一个整图单核方案，进行配置对照，不用优化后的单核替换A入口的固定基准。2～5核B/L2分别选优时可能选择不同方案；纯硬件对照必须通过计划哈希匹配另做，详见`fixed_plan_cache_controls.json`。', '',
 '新Trace引导迁移和读取时机候选属于分离的开发轨道，未混入冻结矩阵。因此开发样本中的新最好值与冻结矩阵的数值可能不同，这是实验协议区别，不是选择性改写结果。','',
 '冻结覆盖按核数、场景统计：','', '| 配置 | 状态计数 |','|---|---|']
 for setting,counts in sorted(cover['by_setting'].items()):lines.append(f'| {setting} | {counts} |')
 lines += ['', '## 3. 从实际Trace重建等待条件','',
 '对005、006、010的已有四核B方案，重建原版展开图的计算依赖、MEMORY_REUSE容量额度复用依赖、同Pipe先后和跨核COPY释放；逐操作核对：', '',
 '`start(v)=max(data predecessors finish, memory-reuse predecessors finish, previous same-Pipe finish, source COPY_OUT finish+500)`。空前驱取0。', '',
 '这些方案中的所有开始时刻均匹配，未留下无法解释的开始滞后。MEMORY_REUSE是为了安全复用存储额度加入的先后关系；Spill为0不等于不存在这种等待。', '',
 '取一条与最终结束时刻相连的实际关键链，按固定规则打破并列。下面分解严格加总为该方案Makespan：', '',
 '| 用例 | 计算周期 | DDR独占参考周期 | DDR共享与取整附加周期 | 跨核固定同步周期 | Makespan |','|---|---:|---:|---:|---:|---:|']
 for c in ('case_005','case_006','case_010'):
  r=read(f'stage3_results/trace/{c}_B.json');d=r['critical_chain_duration_decomposition'];lines.append(f"| {c} | {d.get('compute_PIPE_M',0)+d.get('compute_PIPE_V',0)} | {d['DDR_solo_cycles']} | {d['DDR_contention_and_rounding_cycles']} | {d['explicit_cross_release_delay']} | {r['makespan']} |")
 lines += ['', '005的关键链含34次500周期跨核同步；006、010分别含4次和6次。005需要优先核查同步链与带宽重叠，006的这条关键链以向量计算为主，010是计算、搬运和跨核释放混合限制。', '',
 '**限制：**这是一份既定时序的事后分解，不是去掉某项后必能节省的周期数。COPY时长随整个调度改变而改变，关键链也可能切换；不能把多个Pipe的等待周期相加再除以Makespan作为全局损失比例。', '',
 '## 4. 有限、可验证的局部改动','',
 '只在005、006、010上，沿已观测关键跨核张量连接，尝试完整链块的生产侧/消费侧迁移以及少量相连块的共同迁移。每例最多实际评估8份候选；用精确张量通信增量和资源下界筛选，最终由原版Makespan选解。001、014没有新增搜索。', '',
 '| 用例 | 上轮四核B最好值 | 本轮B最好值 | B耗时下降 | 上轮L2独立最好值 | 本轮L2独立最好值 | L2耗时下降 |','|---|---:|---:|---:|---:|---:|---:|']
 for r in sel:lines.append(f"| {r['case']} | {r['old_B']} | {r['new_B']} | {100*r['B_time_reduction']:.4f}% | {r['old_L2_independent_best']} | {r['new_L2_independent_best']} | {100*r['L2_time_reduction']:.4f}% |")
 lines += ['', '这些是三个开发用例、四核配置下的结果，不代表全100例的平均改善。24份迁移候选均保留；存在明显劣化候选，没有只保存最好结果。新B最好方案又在B与L2下独立重跑，得到一致B结果。', '',
 '005改进后的关键链仍有34次跨核释放；006由4次变为5次而Makespan略降；010仍是6次。由此可见，局部减少某条旧关键依赖并不保证新关键链上的同步次数减少，总目标仍需全流程评价。原图计算操作和周期没有改变，改变的是哪些操作落在最终关键链上。', '',
 '## 5. 内部张量与最后使用位置的驻留代理','',
 '新增`residency_proxy.py`：统计每个核心上所有触及的内部和外部张量、首次触及位置、最后使用位置、最后使用操作、跨子图覆盖数，并计算无换出假设下的活跃量、大小×位置跨度以及超容量面积。', '',
 '其坐标是“局部计算操作位置”，不是模拟时钟。忽略真实COPY完成、预取、换入换出和跨Pipe重叠，所以仅是软压力指标。', '',
 '复用014上一轮的固定分核前后方案做方向性校准：新代理的L1压力随排序降低，与真实Spill由60,399,504降至18,949,008字节的方向一致。本轮没有为014再次搜索更好方案。', '',
 '**必须保留的反例：**006核心0的静态UB峰值估计为150,528字节，高于131,072字节容量；同方案实际Trace重建UB峰值为68,614字节，且Spill为0。这说明代理不能作为非法判据，也尚不能称为准确的Spill预测器。未把这一未充分校准的代理强制接入冻结求解器。', '',
 '## 6. FIFO读取时机：先解释实际未命中类型','',
 '逐事件重放Cache查询、插入和淘汰，验证命中不更新FIFO顺序、插入在读取完成之后，并核对命中字节与官方cache_stats一致。三个旧L2最好方案均没有发生淘汰，所以本轮不把它们的未命中归咎于容量淘汰。', '',
 '| 用例 | 首次/无在途同数据未命中次数 | 同数据尚在读入时的重叠未命中 | 命中次数 | 淘汰次数 |','|---|---:|---:|---:|---:|']
 for c in ('case_005','case_006','case_010'):
  r=read(f'stage3_results/trace/{c}_L2best.json')['fifo'];v=r['requests'];lines.append(f"| {c} | {v.get('cold_miss_without_inflight',0)} | {v.get('miss_while_same_tensor_inflight',0)} | {v.get('hit',0)} | {r['eviction_count']} |")
 lines += ['', '读取时机策略保持核心分配和B场景切图COPY总量不变，只在合法链块边界拆分现有子图、调整先读者或后读者所在子图顺序。没有插入空等、预热操作或新依赖。每例最多6个实际候选，共18个。', '',
 '| 用例 | 原L2方案 | 仅时机调整的最好L2结果 | 说明 |','|---|---:|---:|---|',
 '| case_005 | 50,981 | 50,887 | 命中次数和字节未增加，时序改变减少了所选关键链的共享搬运附加时间 |',
 '| case_006 | 25,366 | 25,366 | 未取得改善，保留原方案 |',
 '| case_010 | 25,518 | 25,384 | 重叠未命中由3次降为2次，命中由67次增为68次 |', '',
 '006、010最后独立选优的25,230和24,135周期来自新迁移方案的L2评估，不是上述时机策略单独取得的值。005仍选时机方案50,887；问题2新B方案开启L2为51,347，不能直接作为其L2最终方案。', '',
 '这只是由实际FIFO读取事件指导的有限时机优化，不是已解决所有大工作集的FIFO淘汰优化。冷数据重叠读取变成命中也可能以其他计算等待为代价，仍以Makespan判断。', '',
 '## 7. 工程与证据','',
 f"从原始上传ZIP逐文件比对，114个官方文件完全一致。24项单元测试通过；本轮审计{a['successful_official_records_audited']}条成功官方结果记录（包含重复、对照、候选），不同原始结果哈希{a['distinct_raw_hashes']}个。检查包括结果/输入/配置哈希、Makespan与最后结束时刻、COPY量分解、核内峰值、Cache比例和{a['tensor_traffic_and_lower_bound_checks']}条张量通信/下界核验。", '',
 f"18份时序诊断含重复对照，不是18种算法；全部开始时刻解释无残差。运行时`-S`对照核对了{a['startup_matches']}个相同配置的选中方案哈希及Makespan一致。此项只避免site初始化开销，不能宣传为大型仿真按相同比例提速。", '',
 '所有墙钟来自共享容器，基准、多核实验和审计部分并发，不是独占机器的性能认证。错误、取消与超时保留；未完成任务停止在检查点，不在回复后继续后台运行。', '',
 '## 8. 后续顺序与复现','',
 '优先补齐剩余固定基准并继续冻结矩阵；其次做全量消融和相同计划的B/L2对照。只有在全量验证充分后，再决定是否把Trace迁移或时机策略纳入最终默认算法。不能以三个开发例子的改善替代题目要求的全部用例结果。', '',
 '见`README_STAGE3.md`。缺失基准重试入口为`src/resume_missing_baselines.py`，全量检查点入口为`src/coverage_matrix.py --resume`。3600秒补跑上限只是运行配置，不保证成功。更换Python版本或冻结源码时，应建立新实验目录并记录环境，不能强行覆盖原协议。', '',
 '**结论：**本轮已经完成从“猜测瓶颈”到“重建实际等待并检验有限改动”的推进，也扩大了覆盖，但正式全量实验尚未完成。缺失项清楚保留，不能据此给出100例正式平均曲线或奖项判断。', '']
 text='\n'.join(lines);(ROOT/'第三轮报告.md').write_text(text);(args.export_dir/'NPU_第三轮覆盖推进与Trace诊断报告.md').write_text(text);print('report written',len(text))
if __name__=='__main__':main()
