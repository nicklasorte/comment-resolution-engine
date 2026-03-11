from comment_resolution_engine.prompt_builder import build_resolution_task, classify_comment_type
from comment_resolution_engine.resolver_schema import ResolutionRow


def test_classify_comment_type():
    assert classify_comment_type("Please clarify this method") == "Clarification"
    assert classify_comment_type("There is a typo") == "Editorial"


def test_completed_status_task():
    row = ResolutionRow(comment_number="5", comment="Done", status="Completed")
    task = build_resolution_task(row)
    assert "Status indicates comment is complete" in task


def test_open_status_task_contains_core_rules():
    row = ResolutionRow(comment_number="2", comment="Clarify assumptions", line_number="20")
    task = build_resolution_task(row)
    assert "Write 1-3 sentences" in task
    assert "Do not mention the comment process" in task
    assert "Line reference: 20" in task
