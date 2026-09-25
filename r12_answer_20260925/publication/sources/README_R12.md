# NPU R12 优化包｜先读本页

本包是可独立运行的R12.0实验工程。新内容是快速插入日历、Spill引导的局部微批，以及对应实验和核验工具。旧代码、100个原图、config.txt、官方评估器未改。不是此前大包的分卷，也不依赖不可访问的旧工作区。

## 快速开始

已验证环境：Linux、CPython 3.13.5、标准库。进程清理依赖/proc；原生Windows/macOS未验收。Windows应在可用的Linux/WSL环境运行。无须GPU/NPU、AI API或联网依赖。文稿生成等旧辅助脚本不属于本次核心复现的依赖。

```bash
cd NPU_R12
python3 -m venv --without-pip .venv
.venv/bin/python -S round12_tools/verify_package.py
.venv/bin/python -S -m unittest discover -s round12_tests -v
.venv/bin/python -S round12_src/solve_round12.py official/data/case_073.json -n 5 --scene B --budget 600 --out work/case073_B5
```

也可执行`bash quickstart_r12.sh`，它只运行校验、11项新增测试和case_073五核B，不会启动100例长批次。输出目录必须是新目录或空目录。

最终方案为`selected_plan.json`，同时自动导出`case_073_multicore_res.json`。两个文件逐字节相同，仅含`node_to_subgraph`和`core_schedules`。report.json和各子目录保留控制、候选、原版返回值、状态及哈希。

## 独立官方复核

```bash
.venv/bin/python -S official/code/multicore_cut_evaluate_problem_2.py \
 official/data/case_073.json work/case073_B5/case_073_multicore_res.json \
 --config official/data/config.txt -o work/case073_B5/rechecked.json \
 --trace-output work/case073_B5/rechecked_trace.json \
 --log-output work/case073_B5/rechecked_log.txt
```

A用problem_1，L2用problem_3。显式传入方案，不要求在原图目录写输出。控制参考值仅用于求解后核查，不是查表输入。不同运行预算与环境可能影响候选覆盖；不能手工改结果以匹配参考值。

## 三个profile

- `reference`：从原图调用未改的R11。用于独立对照。
- `indexed`：原R10加快速日历的插入候选，不做微批。
- `full`：默认，indexed加两个有界局部微批候选。

微批只对B/L2中实际有Spill且有合适大张量窗口的方案触发。A没有套用B的驻留策略。无法确认的候选保留timeout/failed状态，只有完整评价成功者参与选解。

## 完整五核B复现与续跑

```bash
.venv/bin/python -S round12_src/run_matrix.py --cases all --cores 5 --scenes B --workers 1 --budget 600 --out work/reproduce_B5
```

同参数加`--resume`继续。程序核对协议、源码、输入和成功方案/原版输出哈希；其他版本或参数请使用新目录。默认单工作进程，避免大图同时展开造成内存压力。600秒是单请求软预算，不是整批总时间。

继续新版本全核数可用`--cores 2 3 4 5 --scenes A B L2`，但该命令是待运行任务，不能当作本轮已完成记录。

## 日历等价性与性能复现

```bash
.venv/bin/python -S round12_src/benchmark_generators.py --out work/generation_B5 --timeout 30
```

此比较只测候选生成，包含图读取与结构检查，不测官方评分或完整求解。原/快两者的调用顺序按用例位置交替，共同上限30秒。超时原方法的后续180秒核验另存，不与首次30秒结果混淆。

## 文件职责和结果包

`METHOD_R12.md`为方法及证明；`round12_reports/`为协议、汇总、CSV和核验；`round12_src/`为新算法；其他round/src及official目录为原依赖。

独立的结果ZIP保存`NPU_R12/round12_results/`文件树。若有多个编号结果包，各自是普通ZIP，请全部解压到相同父目录合并；不需要二进制拼接。代码包可独立求解；不下载结果包时，不能声称拥有本轮全部旧原版时间线。

当前结果分为NPU_R12_Evidence_01.zip至NPU_R12_Evidence_08.zip，均为独立普通ZIP。先逐一解压到与核心包相同的父目录，再执行完整清单核查：

```bash
.venv/bin/python -S round12_tools/verify_package.py --with-evidence
```

新证据统计与科学检查：

```bash
.venv/bin/python -S round12_tools/analyze_results.py
.venv/bin/python -S round12_tools/audit_results.py
```

这两条命令读取包内本轮结果；完整结果包不存在时，不应把空检查当作已完成科学验收。报告中保留开发/独立消融/主批次的不同范围，继承的单核分母单独注明。

## 限制

不更改旧论文，也未修复旧PDF缺字；本轮报告应独立阅读。没有宣称新版本全1200配置、全部历史原始日志恢复、全局最优或奖项。本次核心包与结果包应按清单核验再转发，不使用旧失效下载链接。
