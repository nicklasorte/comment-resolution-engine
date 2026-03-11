from comment_resolution_engine.prompt_builder import build_resolution_task, classify_comment_type
from comment_resolution_engine.resolver_schema import ResolutionRow


def test_classify_comment_type_updated_categories():
    assert classify_comment_type("Please clarify this section") == "Clarification"
    assert classify_comment_type("Please define aggregate interference") == "Definition"
    assert classify_comment_type("This request is out of scope") == "Scope"
    assert classify_comment_type("Methodology details are missing") == "Methodology"
    assert classify_comment_type("Assumptions are not conservative") == "Assumption"
    assert classify_comment_type("Provide technical justification") == "Justification"
    assert classify_comment_type("There is a typo") == "Editorial"


def test_resolution_task_includes_context_and_status_handling():
    row = ResolutionRow(
        comment_number="2",
        comment="Clarify assumptions",
        line_number="20-21",
        existing_revision_notes="Tighten language",
        report_context="L20: Existing text.",
        status="Open",
    )
    task = build_resolution_task(row)
    assert "Write 1-3 sentences" in task
    assert "Status handling:" in task
    assert "Comment text: Clarify assumptions" in task
    assert "Line reference: 20-21" in task
    assert "Report context: L20: Existing text." in task
