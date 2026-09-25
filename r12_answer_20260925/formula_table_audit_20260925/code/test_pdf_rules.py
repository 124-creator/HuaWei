# /// script
# requires-python = ">=3.12"
# dependencies = ["pytest"]
# ///
"""Run: python -B -m pytest -p no:cacheprovider code/test_pdf_rules.py."""
import pdf_rules as rules


def test_equation_tag_normalizes_fullwidth_and_subnumber() -> None:
    assert rules.equation_tag("（ ５．３ a ）") == "5.3a"


def test_equation_tag_rejects_year_ranges_and_measurements() -> None:
    assert rules.equation_tag("(1990-2005)") is None
    assert rules.equation_tag("(28.30)") is None
    assert rules.equation_tag("(3-8)") == "3-8"


def test_equation_reference_is_not_a_standalone_label() -> None:
    assert rules.equation_tag("由式(5.3)可知") is None
    assert rules.equation_tag("Eq. (5.3)") is None


def test_multiline_equation_subnumbers_share_one_unit() -> None:
    assert rules.equation_unit("5.3a") == rules.equation_unit("5.3b") == "5.3"


def test_chinese_table_caption_and_continuation() -> None:
    assert rules.table_tag("表 5.3 各模型参数") == ("5.3", False)
    assert rules.table_tag("续表 5.3 各模型参数") == ("5.3", True)


def test_body_table_reference_is_not_a_caption() -> None:
    assert rules.table_tag("表5.3可以看出模型表现较好。") is None
    assert rules.table_tag("Table 3 shows the results.") is None


def test_english_roman_table_caption() -> None:
    assert rules.table_tag("TABLE IV") == ("IV", False)
    assert rules.table_tag("Table 2: Evaluation settings") == ("2", False)


def test_left_enumeration_is_not_a_right_equation_label() -> None:
    assert rules.right_label((500, 200, 530, 212), (595, 842), 1)
    assert not rules.right_label((50, 200, 80, 212), (595, 842), 1)
    assert rules.right_label((265, 200, 285, 212), (595, 842), 2)
    assert not rules.right_label((500, 800, 530, 812), (595, 842), 1)


def test_glued_label_accepts_section_numbering_on_equations() -> None:
    assert rules.glued_equation_tag("ρ = cov(X,Y)/(σXσY) (3-1)") == "3-1"
    assert rules.glued_equation_tag("T(n) = n log n (3-7)") == "3-7"


def test_glued_label_rejects_bare_enumerations_and_units() -> None:
    assert rules.glued_equation_tag("该方法包括以下步骤：(1)") is None
    assert rules.glued_equation_tag("长度为 (2.3m)") is None
    assert rules.glued_equation_tag("取值 (0.68)") is None


def test_glued_label_rejects_inline_numeric_values() -> None:
    assert rules.glued_equation_tag("O(N! × N) (1.39)") is None
    assert rules.glued_equation_tag("O(3.30)") is None
    assert rules.glued_equation_tag("ranges (2022-2023)") is None


def test_table_rejects_sentence_opening_reports() -> None:
    assert rules.table_tag("表5.3报告了模型结果。") is None
    assert rules.table_tag("Table 3 reports the results.") is None
