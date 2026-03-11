from comment_resolution_engine.prompt_builder import (
    build_resolution_task,
    determine_accept_reject,
    draft_ntia_comments,
    draft_resolution,
    extract_effective_comment,
    extract_effective_suggested_text,
    normalize_comment_type,
)
from comment_resolution_engine.resolver_schema import ResolutionRow


def test_normalize_comment_type_variations():
    assert normalize_comment_type("technical") == "Technical"
    assert normalize_comment_type("Clarification") == "Clarification"
    assert normalize_comment_type("Editorial / Grammatical") == "Editorial/Grammar"


def test_effective_comment_and_suggested_text():
    assert extract_effective_comment("Primary note", "Alternate text") == "Primary note"
    assert extract_effective_comment("", "Alternate text") == "Alternate text"
    assert extract_effective_suggested_text(" Suggested  ") == "Suggested"


def test_determine_accept_reject_and_ntia_comments():
    row = ResolutionRow(comment_type="Technical", effective_comment="Missing assumption", effective_suggested_text="")
    row.row_status = "Draft"
    assert determine_accept_reject(row) == "Accept"

    row2 = ResolutionRow(comment_type="Editorial/Grammar", effective_comment="stet", effective_suggested_text="")
    row2.row_status = "Draft"
    assert determine_accept_reject(row2) == "Reject"

    row2.disposition = "Reject"
    assert draft_ntia_comments(row2).startswith("Reject.")


def test_draft_resolution_paths():
    row = ResolutionRow(comment_type="Clarification", effective_comment="scope of analysis", disposition="Accept")
    row.row_status = "Draft"
    assert "clarifies" in draft_resolution(row)

    completed = ResolutionRow(row_status="Complete", existing_resolution="Kept text")
    assert draft_resolution(completed) == "Kept text"


def test_build_resolution_task_mentions_fields():
    row = ResolutionRow(comment_number="7", agency_notes="Refine scope", line_number="20")
    row.resolution_task = build_resolution_task(row)
    assert "NTIA Comments" in row.resolution_task or "Draft NTIA Comments" in row.resolution_task
