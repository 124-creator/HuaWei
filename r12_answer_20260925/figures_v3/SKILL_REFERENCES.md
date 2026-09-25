# 本轮 GitHub skills 参考与取舍

核验日期：2026-09-25。星数是 GitHub API 返回的仓库总星数，不是单个 skill 的星数，也不代表科学正确性认证。

| 仓库 | 核验星数 | 本轮读取的 skill | 使用范围 |
|---|---:|---|---|
| [K-Dense-AI/scientific-agent-skills](https://github.com/K-Dense-AI/scientific-agent-skills) | 46,561 | scientific-visualization | 保留原始数据、诚实坐标、颜色冗余编码、固定物理宽度、矢量导出和最终文件检查 |
| 同上 | 同上，不重复计数 | scientific-schematics | 只借鉴标签、间距、组件与关系逐项复核；不使用其外部AI生图链 |
| [anthropics/skills](https://github.com/anthropics/skills) | 178,003 | canvas-design | 借鉴空间层次、减少冗余文字和二次视觉精修；不照搬海报化、装饰性艺术表达 |

## 可定位版本
- K-Dense main：`49c6e97775eaa18ba791bebe23162a70ae601c18`。
- Anthropic main：`33375500bcea98d610eb30ce10ac4e59b89c390d`。
- [scientific-visualization 原文](https://github.com/K-Dense-AI/scientific-agent-skills/blob/49c6e97775eaa18ba791bebe23162a70ae601c18/skills/scientific-visualization/SKILL.md)
- [scientific-schematics 原文](https://github.com/K-Dense-AI/scientific-agent-skills/blob/49c6e97775eaa18ba791bebe23162a70ae601c18/skills/scientific-schematics/SKILL.md)
- [canvas-design 原文](https://github.com/anthropics/skills/blob/33375500bcea98d610eb30ce10ac4e59b89c390d/skills/canvas-design/SKILL.md)

旧仓库名 claude-scientific-skills 已由 GitHub API 重定向到 scientific-agent-skills；本轮使用当前 skills/ 路径，不使用已失效的 scientific-skills/ 路径。

## 不采用的部分
- scientific-schematics 的默认路径会把提示词和图片送往外部服务，且只输出栅格PNG，无法保证精确关系与可编辑矢量。因此未运行该链，不上传比赛数据、不读取API密钥。
- canvas-design面向艺术画布，不可用于弱化科学标签、制造虚构模型、追求装饰性3D或删去负结果。
- 不安装任何 skill 或依赖，不运行远端脚本；这里只读取公开规范，绘图代码为本地实现。

## 本轮落实
- F01/F02/F05/F06/F13/F14/F22/F23：对象和资源边界优先，取消求解步骤和判断分支式流程图；示意数据显式标注。
- F08：完整400格与对称log2色标不变，额外标记全部退化格。
- F18：非零Spill细节与完整100图累计分布并列，显式保留零值数量。
- F19：保留逐例比值均值，标注实际阶段增量和局部放大，不称等预算消融。
- F28：同一PB、同一绝对时间轴，增加共同时间窗口的局部放大，不做各自归一化。
- 来源、CSV、字号、导出尺寸与人工读图分开核验，不把脚本PASS等同科学验收。

此前多篇论文只借鉴构造方法，不复制其图形、结果或算法。上述公开规范仅作方法参考，未整段复制其代码或素材到图件。
