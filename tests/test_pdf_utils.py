from comment_resolution_engine.pdf_utils import extract_report_context, parse_line_reference


def test_parse_line_reference_single_range_and_list():
    assert parse_line_reference("12") == [12]
    assert parse_line_reference("12-14") == [12, 13, 14]
    assert parse_line_reference("12, 15-16") == [12, 15, 16]


def test_extract_report_context_returns_empty_on_missing_data():
    assert extract_report_context("", "100 text") == ""
    assert extract_report_context("12", "") == ""


def test_extract_report_context_for_numbered_text_lines():
    pdf_text = """
10 Intro statement
11 System assumptions are defined here
12 Compatibility metric is introduced
13 Additional model detail
""".strip()
    context = extract_report_context("12", pdf_text, window=1)
    assert "L11: System assumptions are defined here" in context
    assert "L12: Compatibility metric is introduced" in context
    assert "L13: Additional model detail" in context
