"""合稿：按章顺序拼接，统一公式/表/图编号，插入图件，生成参考文献。

输出
  ../全文_R12论文_v1.md          人读版（Typora/Obsidian可渲染公式与图片）
  ../out/_pandoc_input.md          转docx用的中间稿（含公式编号标记与题注样式）
  ../qa/编号映射.json             旧占位编号 → 全文编号
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                     # paper_full_v1/
R12 = ROOT.parent
sys.path.insert(0, str(HERE))
from textutil import curly_quotes  # noqa: E402

ORDER = ["00_摘要.md", "01_问题重述.md", "02_问题分析.md", "03_模型假设与符号说明.md", "04_统一建模.md",
         "05_问题一.md", "06_问题二.md", "07_问题三.md", "08_模型检验与算法分析.md", "09_模型评价与推广.md",
         "10_结论.md", "REFS", "12_附录.md"]
REFS = json.loads((HERE / "refs.json").read_text(encoding="utf-8"))
NEW_FIGS = {"F35": "全文技术路线"}

EQ_LABEL = re.compile(r"^【式\(([^)]+)\)】\s*$")
TAB_CAP = re.compile(r"^\*\*表(\S+?)\s{1,3}(.+?)\*\*\s*$")
INCLUDE = re.compile(r"^<!-- include: (\S+) -->\s*$")


def fig_info(fid: str) -> tuple[str, Path]:
    if fid in NEW_FIGS:
        return NEW_FIGS[fid], ROOT / "figures" / f"{fid}.png"
    meta = json.loads((R12 / "figures_v3/metadata" / f"{fid}.json").read_text(encoding="utf-8"))
    return meta["title"], R12 / "figures_v3/delivery/figures" / f"{fid}.png"


def chapter_no(name: str) -> int | None:
    m = re.match(r"(\d\d)_", name)
    n = int(m.group(1)) if m else None
    return n if n and 1 <= n <= 10 else None


def load() -> list[tuple[str, list[str]]]:
    chapters = []
    for name in ORDER:
        if name == "REFS":
            chapters.append((name, []))
            continue
        lines = []
        for line in (ROOT / "chapters" / name).read_text(encoding="utf-8").split("\n"):
            m = INCLUDE.match(line)
            if m:
                lines.extend((ROOT / "chapters" / m.group(1)).read_text(encoding="utf-8").rstrip("\n").split("\n"))
            else:
                lines.append(line)
        text = "\n".join(lines)
        # 弯引号：跳过围栏代码块
        parts = re.split(r"(```.*?```)", text, flags=re.S)
        text = "".join(p if p.startswith("```") else curly_quotes(p) for p in parts)
        chapters.append((name, text.split("\n")))
    return chapters


def build():
    chapters = load()
    eq_map, tab_map, fig_map, fig_first = {}, {}, {}, {}
    # 1. 公式与表格编号（按展示位置）
    for name, lines in chapters:
        n = chapter_no(name)
        ei = ti = 0
        for i, line in enumerate(lines):
            m = EQ_LABEL.match(line)
            if m:
                prev = next(l for l in reversed(lines[:i]) if l.strip())
                if prev.strip() != "$$":
                    raise SystemExit(f"{name}: 公式标签前不是展示公式: {line}")
                if n is None:
                    raise SystemExit(f"{name}: 该部分不应含编号公式")
                ei += 1
                label = m.group(1)
                if label in eq_map:
                    raise SystemExit(f"公式重复展示: {label}")
                eq_map[label] = f"{n}-{ei}"
            m = TAB_CAP.match(line)
            if m:
                label = m.group(1)
                if label in tab_map:
                    raise SystemExit(f"表号重复: {label}")
                if n is None:
                    tab_map[label] = label
                else:
                    ti += 1
                    tab_map[label] = f"{n}-{ti}"
    # 2. 图编号（按首次引用）
    for name, lines in chapters:
        n = chapter_no(name)
        for i, line in enumerate(lines):
            for fid in re.findall(r"【图(F\d+)】", line):
                if fid not in fig_map:
                    if n is None:
                        raise SystemExit(f"{name}: 图{fid}首次引用不在正文章节")
                    k = 1 + sum(1 for v in fig_map.values() if v.startswith(f"{n}-"))
                    fig_map[fid] = f"{n}-{k}"
                    fig_first[fid] = (name, i)
    # 3. 参考文献编号（按首次引用）
    cite_order: list[str] = []
    for name, lines in chapters:
        for line in lines:
            for key in re.findall(r"\[@([\w-]+)\]", line):
                if key not in REFS:
                    raise SystemExit(f"未知文献键: {key}")
                if key not in cite_order:
                    cite_order.append(key)
    cite_no = {k: i + 1 for i, k in enumerate(cite_order)}

    def sub_refs(line: str) -> str:
        def eq(m):
            if m.group(1) not in eq_map:
                raise SystemExit(f"引用了未展示的公式: {m.group(1)}")
            return f"式({eq_map[m.group(1)]})"
        def tab(m):
            if m.group(1) not in tab_map:
                raise SystemExit(f"引用了不存在的表: {m.group(1)}")
            return f"表{tab_map[m.group(1)]}"
        def fig(m):
            return f"图{fig_map[m.group(1)]}"
        line = re.sub(r"【式\(([^)]+)\)】", eq, line)
        line = re.sub(r"【表([^】]+)】", tab, line)
        line = re.sub(r"【图(F\d+)】", fig, line)
        def cites(m):
            keys = re.findall(r"\[@([\w-]+)\]", m.group(0))
            return "[" + ",".join(str(cite_no[k]) for k in keys) + "]"
        line = re.sub(r"(?:\[@[\w-]+\])+", cites, line)
        return line

    human, pand = [], []
    for name, lines in chapters:
        if name == "REFS":
            block = ["# 参考文献", ""] + [f"[{cite_no[k]}] {REFS[k]}" for k in cite_order for _ in [0]]
            block = [block[0], ""] + sum(([b, ""] for b in block[2:]), [])
            human += block
            pand += block
            continue
        insert_after = {}
        for fid, (fname, idx) in fig_first.items():
            if fname == name:
                j = idx
                while j + 1 < len(lines) and lines[j + 1].strip():
                    j += 1
                insert_after.setdefault(j, []).append(fid)
        for i, line in enumerate(lines):
            m = EQ_LABEL.match(line)
            if m:
                tag = eq_map[m.group(1)]
                # 人读版：把编号写进公式；docx版：标记段落，后处理为右对齐编号
                k = len(human) - 1
                while human[k].strip() != "$$":
                    k -= 1
                human.insert(k, f"\\tag{{{tag}}}")
                pand.append(f"EQNO({tag})")
                continue
            m = TAB_CAP.match(line)
            if m:
                cap = f"表{tab_map[m.group(1)]}  {sub_refs(m.group(2))}"
                human.append(f"**{cap}**")
                pand += ['::: {custom-style="表题"}', cap, ":::"]
                continue
            out = sub_refs(line)
            human.append(out)
            pand.append(out)
            for fid in insert_after.get(i, []):
                title, path = fig_info(fid)
                cap = f"图{fig_map[fid]}  {title}"
                rel = Path(os.path.relpath(path, ROOT)).as_posix()
                human += ["", f"![{cap}]({rel})", "", f"*{cap}*"]
                pand += ["", f"![]({path.as_posix()}){{width=15.5cm}}", "", '::: {custom-style="图题"}', cap, ":::"]
        human.append("")
        pand.append("")
    def hard_breaks(lines):
        """算法块（引用块）逐行换行：连续两行都有内容时在前一行末加两个空格。"""
        out = list(lines)
        for i in range(len(out) - 1):
            a, b = out[i], out[i + 1]
            if a.startswith(">") and b.startswith(">") and a.strip("> ").strip() and b.strip("> ").strip():
                out[i] = a.rstrip() + "  "
        return out
    human = hard_breaks(human)
    pand = hard_breaks(pand)
    text = "\n".join(human)
    (ROOT / "全文_R12论文_v1.md").write_text(text, encoding="utf-8")
    (ROOT / "out").mkdir(exist_ok=True)
    (ROOT / "out/_pandoc_input.md").write_text("\n".join(pand), encoding="utf-8")
    mapping = {"equations": eq_map, "tables": tab_map, "figures": fig_map, "citations": cite_no}
    (ROOT / "qa/编号映射.json").write_text(json.dumps(mapping, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"equations {len(eq_map)}, tables {len(tab_map)}, figures {len(fig_map)}, refs {len(cite_no)}")


if __name__ == "__main__":
    build()
