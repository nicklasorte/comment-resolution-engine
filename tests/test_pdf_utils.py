from comment_resolution_engine.ingest.pdf_parser import PdfContext, parse_line_reference


def test_parse_line_reference_single_range_and_list():
    assert parse_line_reference("12") == [12]
    assert parse_line_reference("12-14") == [12, 13, 14]
    assert parse_line_reference("12, 15-16") == [12, 15, 16]


def test_extract_report_context_window():
    ctx = PdfContext(
        pages={
            1: [
                (10, "Intro statement"),
                (11, "System assumptions are defined here"),
                (12, "Compatibility metric is introduced"),
                (13, "Additional model detail"),
                (16, "Trailing detail"),
            ]
        }
    )
    context, confidence = ctx.extract_window(page=1, line_reference="12", window=2)
    assert "L11: System assumptions are defined here" in context
    assert "L12: Compatibility metric is introduced" in context
    assert "L13: Additional model detail" in context
    assert confidence == "EXACT_LINE_MATCH"
