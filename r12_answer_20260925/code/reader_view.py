# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Reader-only presentation adapter for the existing solution-doc output.

AI-assisted: OpenCode/Sisyphus, OpenAI; public model release date unverified.
"""
import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ReaderViewError(ValueError):
    reason: str

    def __str__(self) -> str:
        return self.reason


def reader_copy(rendered: str) -> str:
    """Remove only the known renderer envelope; preserve scientific body content."""
    begin = re.search(r"^## 1\. ", rendered, re.MULTILINE)
    end = re.search(r"^## 附录 A", rendered, re.MULTILINE)
    if begin is None or end is None or end.start() <= begin.start():
        raise ReaderViewError("Unrecognized solution-doc boundaries")
    title = rendered.splitlines()[0].split(" —— 解题文档", 1)[0]
    output = [title, ""]
    math_open = False
    for line in rendered[begin.start():end.start()].splitlines():
        if line.startswith("<sub>section:") or line.startswith("<!-- evidence:"):
            continue
        if line == "```latex":
            if math_open:
                raise ReaderViewError("Nested mathematical code block")
            math_open = True
            output.append("$$")
            continue
        if math_open and line == "```":
            math_open = False
            output.append("$$")
            continue
        if re.match(r"^  \d+\. ", line):
            if output[-1] and not re.match(r"^\d+\. ", output[-1]):
                output.append("")
            line = line.lstrip()
        if line.startswith("|") and output[-1] and not output[-1].startswith("|"):
            output.append("")
        output.append(line)
    if math_open:
        raise ReaderViewError("Unclosed mathematical code block")
    result = re.sub(r"\n{3,}", "\n\n", "\n".join(output)).strip() + "\n"
    if re.search(r"(?<![A-Za-z])[A-Za-z]:[\\/]|/(?:home|mnt|Users)/|Dreamboat|AGent员工", result):
        raise ReaderViewError("Private path remains in substantive text")
    return result
