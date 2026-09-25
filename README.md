# HuaWei — 2026华为杯A题 团队工作区（私有）

本仓库为「通用神经网络处理器下的多核调度问题」团队工作区。**请保持私有**；竞赛结束（2026-09-27 12:00）前不要公开或对外分享。

## 目录导航

| 路径 | 内容 |
|---|---|
| `r12_answer_20260925/paper_full_v1/` | **全文论文v1（现行）**：Word草稿 `out/R12论文_v1.docx`、全文Markdown、各章源稿、数字溯源与风险处置记录，见该目录README |
| `r12_answer_20260925/` | **R12全量派生工程**（本轮所有产出，详见下表） |
| `参考材料/2026华为杯A题_队友模板_P0候选_v0.6.docx` | 队友提供的结构与格式模板；**其内数值与方法属于另一套解，仅作格式参考，勿与R12数字混用** |

### r12_answer_20260925/ 内部结构

| 子目录 | 内容 |
|---|---|
| `reproduction/NPU_R12/` | R12求解器代码指纹副本（round6–12源码、src、official），按冻结指纹复制、未改算法 |
| `publication/` | 三问解答（`solutions/Q1–Q3.md`）、逐例冻结表（`tables/`）、closeout来源与C3官方格子（`sources/`） |
| `figures_v3/` | **现行34图版**：`figures/`（PDF+600dpiPNG+SVG）、`answers/`（Q1–Q3图文整合稿）、`delivery/`（图册、共享zip、图件说明）、`code/`、`qa/` |
| `figures_v2/`、`figures32/` | 历史版本图件（v2优化版、v1原始32图版），保留用于追溯 |
| `formulas_tables_v1/` | **38条编号公式＋13张三线表工作稿**＋生成/验证代码（`code/build_doc.py`、`verify_doc.py`）、来源哈希 |
| `paper_full_v1/` | **全文论文v1**：摘要至第10章、参考文献、附录全部成稿；统一编号后的Word草稿与PDF预览；`code/` 可从冻结数据一键重建表格、图、全文与docx |
| `web_agent_kit_v1/` | **网页agent写作输入包**与第4–7章原稿（已被 `paper_full_v1/` 吸收并修订，原稿保留备查） |
| `formula_table_audit_20260925/` | 54篇参考论文的公式/表格统计：`REPORT.md`、逐篇CSV、候选证据、代码 |
| `team_share/`、`qa/` | 队友转发包与渲染/检查记录 |
| 根级 `*_RECEIPT.json`、`*_CHECK*.json` | 各环节验证收据（作者自检，非独立科学验收） |

## 上传边界说明

- 未包含：`formula_table_audit_20260925/refs/`（四篇第三方期刊PDF，版权原因；可按 `INPUTS.json` 中的URL与SHA256自行重新下载）与 `cache/`（提取缓存，可再生成）。
- 文件内可能含本机绝对路径与团队内部信息，**仅供团队私有协作**。
- 所有数字以冻结CSV与各收据为准；仓库内容不构成科学验收、不代表竞赛提交稿。
