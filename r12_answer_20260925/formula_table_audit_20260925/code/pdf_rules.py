# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Conservative label classification. Unit tests precede extraction."""
from dataclasses import dataclass
import re
import unicodedata


@dataclass(frozen=True, slots=True)
class TextLine:
    text: str
    box: tuple[float, float, float, float]
    size: float


@dataclass(frozen=True, slots=True)
class Hit:
    kind: str
    tag: str
    page: int
    box: tuple[float, float, float, float]
    text: str
    continued: bool = False


def normalized(text: str) -> str:
    return unicodedata.normalize("NFKC", text).replace("−", "-").replace("–", "-").strip()


def equation_tag(text: str) -> str | None:
    compact = re.sub(r"\s+", "", normalized(text))
    match = re.fullmatch(r"\(([A-Z](?:[.-])?)?(\d+(?:[.-]\d+)*[a-z]?)\)", compact)
    if not match:
        return None
    tag = (match[1] or "") + match[2]
    if re.search(r"[.-]", tag):
        if int(re.split(r"[.-]", tag)[0]) > 20:
            return None
    return tag


def equation_unit(tag: str) -> str:
    return re.sub(r"[a-z]$", "", tag)


def table_tag(text: str) -> tuple[str, bool] | None:
    text = normalized(text)
    if len(text) > 130 or re.search(r"\.{3,}|…{2,}", text):
        return None
    cn = re.match(r"^(续)?表\s*(\d+(?:\s*[.-]\s*\d+)*)(.*)$", text)
    if cn:
        rest = cn[3].strip()
        if re.match(r"^(可以|可见|可知|可看|显示|给出|表明|说明|中的|中可以|中给出|所示|为\S|列出|展示了|报告|所述|内容|数据|统计|信息|呈现|对应)", rest):
            return None
        return re.sub(r"\s+", "", cn[2]), bool(cn[1] or "续" in rest)
    en = re.match(r"^(?:TABLE|Table)\s+([IVXLCDM]+|\d+(?:[.-]\d+)*)(?:[.:]|\s|$)(.*)$", text)
    if en:
        if re.match(r"^(shows|lists|presents|provides|summarizes|illustrates|reports|compares|gives|describes|and|is|in)\b", en[2].strip(), re.I):
            return None
        return en[1], "continued" in text.lower()
    return None


def glued_equation_tag(text: str) -> str | None:
    """A hyphen-numbered label at the end of an equation row, e.g. '... (3-7)'.

    Only the hyphenated section form with whitespace before the parenthesis is
    accepted; decimal values such as 'O(1.39)' inside table cells share the
    digits-only shape and are deliberately excluded here.
    """
    compact = normalized(text)
    match = re.search(r"\s\((\d{1,2})-(\d{1,2})\)$", compact)
    if not match:
        return None
    first, second = int(match[1]), int(match[2])
    return f"{match[1]}-{match[2]}" if 1 <= first <= 30 and 1 <= second <= 99 else None


def right_label(box: tuple[float, float, float, float], page_size: tuple[float, float], columns: int) -> bool:
    x0, y0, x1, y1 = box
    width, height = page_size
    if not .05 * height < y0 < .94 * height or x1 - x0 > .14 * width:
        return False
    if columns == 2:
        return x1 > .80 * width or (.44 * width < x1 < .55 * width and x0 > .40 * width)
    return x0 > .58 * width and x1 > .80 * width


def heading_kind(text: str) -> str | None:
    text = re.sub(r"\s+", "", normalized(text))
    if len(text) > 65 or re.search(r"\.{3,}|…{2,}", text):
        return None
    if re.fullmatch(r"(?:[一二三四五六七八九十百\dIVXLC]+[.、:]?)?(?:参考文献|参考资料|REFERENCES|References)", text):
        return "references"
    if re.match(r"^(?:[一二三四五六七八九十\d]+[.、:]?)?附录", text) or re.match(r"^(?:APPENDIX|Appendix|APPENDICES|Appendices)(?:[A-Z:.-]|$)", text):
        return "appendix"
    if re.fullmatch(r"(?:1[.、]?|一[、.]?|I[.]?)(?:问题重述|问题背景|引言|绪论|概述|INTRODUCTION|Introduction)", text):
        return "body_start"
    if text in {"目录", "Contents", "CONTENTS"}:
        return "toc"
    return None
