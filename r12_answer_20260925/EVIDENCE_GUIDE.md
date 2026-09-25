# 文稿证据定位

本表说明正文中的证据标签，不把标签出现或哈希一致当作科学证明。正文的假设、推导、实测与限制仍须分别阅读。

| 标签或主张 | 可核对文件与位置 |
|---|---|
| original_problem | `publication/sources/original_problem.docx`：1.3目标、1.4指标、三问原文、附录B.4/B.5及C/D |
| R12_source：实际调用链与择优 | `reproduction/NPU_R12/round12_src/solve_round12.py` 的 `solve`、`evaluate`；R10、R7同名入口 |
| R12_source：Spill窗口与通信不变 | `round12_src/residency_bands.py` 的 `affinity_order`、`candidates`；`publication/sources/METHOD_R12.md` 第3至5节 |
| R12_source：A层带与插入 | `round7_src/generate_tasks.py`、`round7_src/task_frontier.py`；`round12_src/fast_insertion.py`、`fast_calendar.py` |
| FIFO发射与完成语义 | `reproduction/NPU_R12/official/code/multicore_cut_evaluate_problem_3.py`：`insert_cache`、`retire`、`issue`，约416至578行 |
| frozen_results：主实验 | `publication/sources/closeout/results/selected_per_case.csv` 与 `selection.json`，按case/cores/scene定位 |
| frozen_results：同方案控制 | 同目录 `q3_paired_per_case.csv`、`pairs.json`、`paired_results.json`；按case/cores定位，方案哈希与原结果路径保留 |
| 冻结约束检查的覆盖与边界 | 同目录 `verification.json`，1470组既有检查，不是本轮重新运行模拟器 |
| 首次失败与扩展预算 | 同目录 `original_failures.json`、`budget_exceptions.csv`；case_087的A2至A5 |
| C3比较 | `publication/sources/C3_official_cells.csv` 与 `tables/comparison_C3.csv`；前者仅为旧基线，后者由本轮逐图配对计算 |
| 显示数值 | `publication/RESULTS.json` → `tables/display_values.csv` → `code/derive.py` → 冻结逐例输入；来源列为数值键，聚合为first |
| 图片 | `publication/figures/plot_data.json`、各PDF/PNG/SVG；来源是冻结曲线CSV与C3逐例表 |

本机C3方法表述曾与原 `E:/HWCupA2026/solutions/Q1.md`、`Q2.md`、`Q3.md` 对照。它们仍受保护，不在此改写；候选包中的C3数值来源已复制，C3整套原始时间线未复制。

## 本轮实际自检

- `CHECK_RECEIPT.json`：输入保护、数值绑定、主要比值重算、附录数量、链接、语法与单元测试。
- `RENDER_Q1.json` 至 `RENDER_Q3.json`：现有渲染器的实际退出码、未解析值和过期绑定检查。
- `VISUAL_REVIEW.md`：直接查看全部3张PDF实际渲染图的作者视觉记录。
- `SHA256SUMS.json`、`PACKAGE_RECEIPT.json`：打包后的实际字节清单与ZIP核对。

这些文件记录工程和作者自检。外部独立科学审阅、队员改写、规范引用与正式提交审批未由本轮代签。
