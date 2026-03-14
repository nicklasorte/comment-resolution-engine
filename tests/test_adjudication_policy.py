import json
from pathlib import Path

import pytest

from comment_resolution_engine.adjudication import AdjudicationPolicy, PolicyContext, ReasonCode
from comment_resolution_engine.errors import CREError, ErrorCategory


FIXTURES = Path(__file__).parent / "fixtures" / "adjudication" / "cases.json"


def _load_cases():
    return json.loads(FIXTURES.read_text())


def _context_from_case(case: dict) -> PolicyContext:
    return PolicyContext(
        comment_number=str(case.get("id") or case.get("comment_number") or "1"),
        source_agency=case.get("source_agency", "NTIA"),
        commenter=case.get("commenter", "AA"),
        comment_text=case.get("comment_text", ""),
        comment_type=case.get("comment_type", ""),
        proposed_change=case.get("proposed_change", ""),
        target_section=str(case.get("target_section", "")),
        target_page=str(case.get("target_page", "")),
        target_line=str(case.get("target_line", "")),
        status=case.get("status", ""),
        disposition=case.get("disposition", ""),
        resolution=case.get("resolution", ""),
        intent=case.get("intent", ""),
        resolution_summary=case.get("resolution_summary", ""),
        response_text=case.get("response_text", ""),
    )


def test_policy_maps_fixture_cases():
    policy = AdjudicationPolicy()
    for case in _load_cases():
        ctx = _context_from_case(case)
        decision = policy.decide(ctx)
        assert decision.disposition == case["expected_disposition"]
        assert decision.reason_code == case["expected_reason_code"]
        assert decision.response_text
        if decision.disposition.lower().startswith("completed"):
            assert decision.preserve_existing_resolution


def test_policy_is_deterministic():
    policy = AdjudicationPolicy()
    ctx = _context_from_case(_load_cases()[0])
    first = policy.decide(ctx)
    second = policy.decide(ctx)
    assert first == second


def test_policy_validates_missing_fields():
    policy = AdjudicationPolicy()
    ctx = PolicyContext(
        comment_number="",
        source_agency="",
        commenter="",
        comment_text="",
        comment_type="",
    )
    with pytest.raises(CREError) as exc:
        policy.decide(ctx)
    assert exc.value.category == ErrorCategory.VALIDATION_ERROR


def test_completed_preserves_resolution_text():
    policy = AdjudicationPolicy()
    ctx = PolicyContext(
        comment_number="COMP-1",
        source_agency="FCC",
        commenter="AA",
        comment_text="Already handled.",
        comment_type="Editorial",
        status="completed",
        resolution="Existing resolution text",
    )
    decision = policy.decide(ctx)
    assert decision.disposition == "Completed"
    assert decision.preserve_existing_resolution
    assert decision.response_text == "Existing resolution text"


def test_duplicate_marks_no_change():
    policy = AdjudicationPolicy()
    ctx = PolicyContext(
        comment_number="DUP-1",
        source_agency="FCC",
        commenter="AA",
        comment_text="Duplicate of another comment.",
        comment_type="Technical",
        status="duplicate",
    )
    decision = policy.decide(ctx)
    assert decision.reason_code == ReasonCode.DUPLICATE_COMMENT.value
    assert not decision.requires_change


def test_rejection_includes_rationale_phrase():
    policy = AdjudicationPolicy()
    ctx = PolicyContext(
        comment_number="R-10",
        source_agency="DOC",
        commenter="AA",
        comment_text="Request is outside the scope of this paper.",
        comment_type="Technical",
        disposition="Reject",
    )
    decision = policy.decide(ctx)
    assert "because" in decision.response_text.lower()

