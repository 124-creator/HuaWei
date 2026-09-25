# /// script
# requires-python = ">=3.12"
# dependencies = ["pytest"]
# ///
"""Run with existing Python: pytest -p no:cacheprovider code/test_reader_view.py."""
import pytest
from reader_view import reader_copy


def source(body: str) -> str:
    return "# Q1\n> root: E:/private\n## 目录\n1. meta\n## 1. Model\n" + body + "\n## 附录 A　索引\nprivate bookkeeping\n"


def test_display_math_is_not_a_code_block() -> None:
    rendered = source("```latex\nx=1\n```")
    actual = reader_copy(rendered)
    assert "$$\nx=1\n$$" in actual
    assert "```latex" not in actual


def test_private_envelope_does_not_enter_reader_body() -> None:
    rendered = source("<sub>section: id</sub>\n<!-- evidence: x -->\n1.016766")
    actual = reader_copy(rendered)
    assert "E:/private" not in actual and "<!--" not in actual and "<sub>" not in actual
    assert "1.016766" in actual


def test_relative_assets_and_python_examples_are_preserved() -> None:
    body = "![plot](../figures/a.png)\n```python\nx = 2\n```"
    actual = reader_copy(source(body))
    assert body in actual


def test_unclosed_math_is_rejected() -> None:
    rendered = source("```latex\nx=1")
    with pytest.raises(ValueError):
        reader_copy(rendered)


def test_absolute_path_in_substantive_body_is_rejected() -> None:
    rendered = source("Data: D:/private/results.csv")
    with pytest.raises(ValueError):
        reader_copy(rendered)


def test_missing_document_boundary_is_rejected() -> None:
    with pytest.raises(ValueError):
        reader_copy("# unexpected format")
