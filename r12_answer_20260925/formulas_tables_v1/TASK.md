# 公式与三线表工作稿 v1（TASK）

用户授权：把R12三问的编号公式与三线表做成**独立文档**，最后再融合进论文；两者都必须**基于我们的产出**（冻结解答、冻结CSV、真实代码），不得新造实验或不存在的公式。

## 范围
- 不改三类冻结资产：`publication/solutions/Q1–Q3.md`、`publication/sources/closeout/**`、`figures_v3/`。
- 公式：全部来自冻结解答、冻结代码（`round12_src/solve_round12.py`、`round12_src/fast_calendar.py`、`round7_src/task_frontier.py`、`src/solver.py`）与题面规则；每条标注来源与单位。
- 表格：13张，数值由 `code/build_doc.py` 从closeout CSV逐项重算生成；禁止手抄。C3对照与Q3比值同时与冻结对照表交叉核对。
- 编号风格：公式 (1-1)… 表 表1-1…（融合时按终稿模板重排）。
- 本文档是工作稿：不构成科学验收，融合后仍需按工作流做三线表线宽、OMML与逐页检查。

## 输出
- `公式与三线表工作稿.md`（主文件，含符号与来源注）
- `code/build_doc.py`（生成，确定性可复跑）、`code/verify_doc.py`（重放+抽查断言）
- `SOURCES.json`（所用冻结文件哈希）、`RECEIPT.json`（验证结果）
