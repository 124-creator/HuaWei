# R12 三问解答候选

## 当前队友阅读版

本目录的三份 `publication/solutions/Q1.md` 至 `Q3.md` 已更新为公式可渲染、无本机路径的阅读稿。对外转发请使用 **`R12_team_share.zip`** 或 `team_share/` 整个目录，保留图片及表格的相对位置。

旧 `R12_answers_candidate.zip`、根目录原 `SHA256SUMS.json` 与 `PACKAGE_RECEIPT.json` 是上一版候选的历史记录，不用于核对现行阅读稿。旧稿及对应清单另存 `qa/before_team_share/`；当前共享包清单为 `team_share/MANIFEST.json`，检查记录为 `qa/SHARE_CHECK.json`。原始带来源信息的渲染稿仍保存在 `qa/share_renderer/`。

本目录是现有团队实验结果的派生文稿，不是新比赛实例，不覆盖本机C3，也不改变原任务审批。所有正式实验仍以冻结R12方案和原始官方结果为证据；这里没有新求解或新评分。

## 先读三份答案

- [问题一：场景A](publication/solutions/Q1.md)：模型、Task粒度与插入调度、全量曲线、搬运权衡及预算例外。
- [问题二：场景B](publication/solutions/Q2.md)：同核驻留与容量、Spill微批、通信不变性、性能与运行成本。
- [问题三：共享只读L2](publication/solutions/Q3.md)：FIFO与独立带宽、同方案对照、分别选优、收益异质性及退化例。
- [复现说明](REPRODUCE.md)：输入、代码、环境、输出命名、预算及统计口径。
- [证据定位](EVIDENCE_GUIDE.md)：公式、算法、数值、案例和图件分别对应的原件与源码位置。

三份Markdown均由现有工作流 `solution-doc` 从章节JSON和数值投影渲染。`publication/RESULTS.json` 由冻结表计算得到，仅服务于显示绑定；不是另立科学结果或改写主实验。计划签名为本轮工作范围文件的哈希，不是用户D批准。

## 原题交付定位

| 原题要求 | 本候选材料 |
|---|---|
| Q1、Q2模型与算法 | 对应Q1.md、Q2.md的模型与求解章节 |
| Q1、Q2的1至5核平均曲线 | `publication/figures/q1_curve.*`、`q2_curve.*` |
| Q3两配置曲线及同核配置比 | `publication/figures/q3_configuration.*`、Q3.md |
| Q1逐例Makespan、额外搬运 | `publication/tables/Q1_per_case.csv`，400行 |
| Q2逐例指标 | `publication/tables/Q2_per_case.csv`，500行 |
| Q3逐例两配置指标与命中字节率 | `publication/tables/Q3_per_case.csv`，500对 |
| 已观察退化 | `publication/tables/Q3_degraded.csv`，8对；与C3比较另列 |
| 运行时间和搬运分解 | `publication/tables/summary.csv`、逐例表 |
| 可复现Python程序 | `reproduction/NPU_R12/`，按冻结指纹复制，不改算法 |
| 证据定位 | `SOURCE_MANIFEST.json`、`publication/sources/closeout/` |

图件提供原生矢量PDF、600dpi PNG和SVG。Cairo系统库不可用，因此保留工作流样式设置，使用Matplotlib原生导出；不修改系统环境。PDF实际渲染证据位于 `qa/`。

## 必须保留的限定

1. 原图100个；1400是配置数量，不是1400张独立图。均值均先逐图计算比值再汇总。
2. 原4个case_087 A场景600秒失败已保留，最终采用1800秒补跑。不能称历史零失败。
3. C3是事后同输入/同评分口径的对照，不是同搜索预算消融；更快不等于每例COPY更少。
4. Q3的同方案配置比与分别选优比不能互换。这里研究指定容量和带宽的联合效应，没有分别变动两个参数。
5. 本次属于作者的计算、内容和视觉自检，不是外部独立科学审阅。最终队员审阅、规范引用、AI披露及D4仍待完成。
6. 原版数据、方案和大体积时间线仍由冻结清单定位；候选包不复制全套大型原始时间线。正式附件格式、大小、匿名和当届模板检查不由内部ZIP替代。

## AI辅助说明

本轮用途为从已完成实验整理统计、代码和内部文稿。宿主为OpenCode，助手标识Sisyphus，运行上下文声明的模型ID为 `openai/gpt-6-astra`，提供方OpenAI；该型号的官方公开版本和颁布日期未独立核实，不能当作已完成正式披露。原团队算法的AI使用来源需要队员另据真实记录补充，不能把本轮整理者当作其作者。

队员需实质理解模型和结果，核实公式及引用，并以自己的语言组织最终解答。本候选不等于可直接提交的队伍原创终稿，也不承诺最优性或奖项。
