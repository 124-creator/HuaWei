# 本程序及代码是在人工智能工具辅助下完成的。
# 人工智能工具名称、版本/型号、开发机构/公司、版本发布日期：【由参赛队按实际使用情况填写，见论文附录D】
"""共用文本工具：中文弯引号规范化（跳过公式与代码片段）。"""
import re

_SKIP = re.compile(r"(\$\$.*?\$\$|\$[^$\n]+\$|`[^`\n]*`)", re.S)


def curly_quotes(text: str) -> str:
    out = []
    for block in text.split("\n"):
        parts = _SKIP.split(block)
        opened = False
        for i, part in enumerate(parts):
            if i % 2 == 1:  # math or code
                continue
            chars = []
            for ch in part:
                if ch == '"':
                    chars.append("”" if opened else "“")
                    opened = not opened
                else:
                    chars.append(ch)
            parts[i] = "".join(chars)
        out.append("".join(parts))
    return "\n".join(out)
