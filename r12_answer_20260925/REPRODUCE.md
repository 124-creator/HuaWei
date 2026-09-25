# R12 复现与证据说明

## 1. 哪些文件是主解

算法入口是 `reproduction/NPU_R12/round12_src/solve_round12.py`，profile固定为 `full`。此入口会调用R10、R7、R6等已有依赖；这些是同次请求中的算法模块，不是拼接旧版本成绩。代码按当前1400格清单的68份源码指纹复制，另含固定config。

`code/` 里的本轮脚本只做取数、绘图、章节整理和检查，不是新求解器。旧C3正式文件、旧团队文稿和原始运行结果均不修改。

## 2. 环境与输入

- 求解器使用Linux/WSL中的CPython和标准库。已完成实验使用过WSL Ubuntu 24.04 / Python 3.12.3；原包还记录了Linux / Python 3.13.5。原生Windows进程管理不是求解器已验证路径。
- 本次文稿整理使用Windows / Python 3.12.2、Matplotlib 3.11.1。新数值助手使用标准库，测试使用已有pytest；不安装新依赖。
- 将原始100个 `case_*.json` 放入 `reproduction/NPU_R12/official/data/`，或单例命令显式传其他原图路径。候选代码包不重复包含100个大型图；输入原件来自官方题包或团队已经核对过的代码包。
- 绝不能调整config以提高主结果。L1/UB为524288/131072 bytes，DDR为60 bytes/cycle；L2为1048576 bytes、250 bytes/cycle。
- 图、config和源码的预期SHA256在 `publication/sources/closeout/results/selection.json`。该清单的绝对路径是本次实验的定位记录，不应直接当作另一台机器的有效路径。

## 3. 单例从原图求解

以下是供队员在Linux/WSL复现时运行的命令，本次文稿整理没有执行这些求解命令。以 `reproduction/NPU_R12/` 为当前目录，使用已有Python解释器；输出必须是新的或空目录。

```bash
python3 -B -S round12_src/solve_round12.py official/data/case_001.json -n 2 --scene A --profile full --budget 600 --out work/repro_case001_A2
```

将 `--scene` 改成 `B` 或 `L2`，核数设为1至5，即对应其他场景；问题一正式多核点为2至5。输出 `selected_plan.json` 与 `<case>_multicore_res.json` 内容相同，顶层仅含 `node_to_subgraph` 和 `core_schedules`。`report.json` 保留控制、候选、失败、预算、源码和最终结果位置。

若需要用官方程序单独复核已有方案，以B为例：

```bash
python3 -B -S official/code/multicore_cut_evaluate_problem_2.py official/data/case_001.json work/repro_case001_B2/selected_plan.json --config official/data/config.txt -o work/repro_case001_B2/check.json --trace-output work/repro_case001_B2/check_trace.json --log-output work/repro_case001_B2/check.log
```

A用 `problem_1`，L2用 `problem_3`；后一个命令必须先有相应B方案目录，不能把示例路径当作已经生成。

## 4. 全矩阵与例外

仅在队员确实需要重新运行、且预算允许时使用：

```bash
python3 -B -S round12_src/run_matrix.py --cases all --cores 2 3 4 5 --scenes A B L2 --workers 1 --budget 600 --out work/repro_main
python3 -B -S round12_src/run_matrix.py --cases all --cores 1 --scenes B L2 --workers 1 --budget 600 --out work/repro_onecore
```

这两条命令是复现方法说明，不是自动续跑授权。当前主结果为1396个600秒预算结果，加case_087 A2/A3/A4/A5四个1800秒独立补跑。原失败及补跑映射见冻结清单和 `budget_exceptions.csv`，不得静默将失败替成0、1或删例。并发和机器负载可能改变软预算内候选覆盖，因此不承诺跨机器每个请求都与历史方案逐字节相同。

## 5. 问题三必须怎样复现

同方案硬件对照：对每个B最终方案P_B，用相同图、核数和config分别运行problem_2和problem_3，再计算 `T_B(P_B)/T_L2(P_B)`。另一份L2独立选优方案P_L的结果另列，不能混入同方案分母。

当前500对里430对复用相同最终方案、62对复用哈希完全匹配的已有L2候选、8对补了官方L2评分。补评未反馈主算法选型。证据路径和方案哈希保存在 `q3_paired_per_case.csv`、`paired_results.json`；如迁移机器，须先恢复所指向的大文件，不能仅凭小清单声称全量原始时间线在包内。

Cache命中率按每图命中字节/可服务访问字节计算；跨图展示其算术均值。没有L2的Cache字段不可适用。额外COPY沿官方模拟前计账，不扣减命中字节后冒充物理DDR净流量。

## 6. 复算文稿而不重新求解

在本次原环境，以本目录为当前目录，使用已有Python：

```powershell
python -B -m pytest -p no:cacheprovider code/test_metrics.py
python -B code/derive.py
python -B code/charts.py
python -B code/render.py Q1
python -B code/render.py Q2
python -B code/render.py Q3
python -B code/check_delivery.py
```

`derive.py` 只重建本目录的派生表和数值投影；`charts.py` 与 `render.py` 按 `SOURCE_MANIFEST.json` 定位原工作流样式及渲染器。迁移机器后若没有该只读工作流路径，应直接阅读已生成材料，或由维护者显式配置正确路径，不伪造已运行记录。源文件重新冻结使用 `prepare.py WORKSPACE R12_CODE_ROOT`，它拒绝覆盖已存在的源快照；不要对当前冻结目录重复执行。

正文数值由一行宽表进入 `publication/RESULTS.json.paper_values`，再由未改动的工作流 `solution-doc` 渲染。该投影的存在不更改主实验，不签署科学审阅、原任务接受或D4。
