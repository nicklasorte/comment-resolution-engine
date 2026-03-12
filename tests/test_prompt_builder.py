from comment_resolution_engine.generation.resolution_generator import build_resolution_decision
from comment_resolution_engine.models import AnalyzedComment
from comment_resolution_engine.normalize.comment_normalizer import derive_effective_comment, derive_effective_suggested_text, normalize_type


def _base_comment(**kwargs):
    defaults = dict(
        id="1",
        reviewer_initials="AB",
        agency="Agency",
        report_version="Draft",
        section="1.1",
        page=1,
        line=10,
        comment_type="Technical",
        agency_notes="Clarify the population impact metric purpose",
        agency_suggested_text="Add language that the metric is analytical, not regulatory.",
        wg_chain_comments="",
        comment_disposition="",
        resolution="",
        raw_row={},
        normalized_type="TECHNICAL",
        effective_comment="Clarify the population impact metric purpose",
        effective_suggested_text="Add language that the metric is analytical, not regulatory.",
        report_context="L10: Metric definition paragraph",
        cluster_id="C001",
        section_group="1.1",
        intent_classification="REQUEST_CLARIFICATION",
        heat_level="LOW",
        heat_count=1,
    )
    defaults.update(kwargs)
    return AnalyzedComment(**defaults)


def test_normalization_helpers():
    assert normalize_type("Technical Comment") == "TECHNICAL"
    assert derive_effective_comment("Primary", "Secondary") == "Primary"
    assert derive_effective_comment("", "Secondary") == "Secondary"
    assert derive_effective_suggested_text("  Suggested text  ") == "Suggested text"


def test_resolution_generation_includes_change_language():
    comment = _base_comment()
    decision = build_resolution_decision(comment)
    assert decision.disposition == "Accept"
    assert "clarifies" in decision.resolution_text.lower() or "now" in decision.resolution_text.lower()
    assert decision.ntia_comment.startswith("Accept")
