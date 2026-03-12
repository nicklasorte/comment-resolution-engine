import json
from pathlib import Path

import pytest

pd = pytest.importorskip("pandas")

from comment_resolution_engine.generation.rev2_drafting import build_section_rewrites
from comment_resolution_engine.models import AnalyzedComment, ResolutionDecision, SectionRewrite, SharedResolution
from comment_resolution_engine.pipeline import run_pipeline
from comment_resolution_engine.validation.rev2_validator import validate_section_rewrite


def _analyzed_comment(
    cid: str,
    section: str,
    cluster_id: str,
    cluster_label: str,
    suggested_text: str,
    context: str = "",
    context_confidence: str = "EXACT_LINE_MATCH",
    heat_level: str = "HIGH",
) -> AnalyzedComment:
    return AnalyzedComment(
        id=cid,
        reviewer_initials="AB",
        agency="Agency",
        report_version="Draft",
        section=section,
        page=1,
        line=10,
        comment_type="Technical",
        agency_notes=suggested_text,
        agency_suggested_text=suggested_text,
        wg_chain_comments="",
        comment_disposition="",
        resolution="",
        raw_row={},
        normalized_type="TECHNICAL",
        effective_comment=suggested_text,
        effective_suggested_text=suggested_text,
        report_context=context,
        context_confidence=context_confidence,
        cluster_id=cluster_id,
        cluster_label=cluster_label,
        cluster_size=2,
        section_group=section,
        intent_classification="REQUEST_CLARIFICATION",
        heat_level=heat_level,
        heat_count=2,
        resolution_basis="methodology_scope",
        patch_source="suggested_text",
        patch_text=suggested_text,
        patch_confidence="HIGH",
        shared_resolution_id="MR-01",
        canonical_term_used="methodology_scope",
    )


def test_rev2_pipeline_outputs_rewrites_and_draft(tmp_path: Path):
    comments_path = tmp_path / "comments.xlsx"
    df = pd.DataFrame(
        {
            "Comment Number": [1, 2],
            "Agency Notes": [
                "Clarify that Figure 5 reference is informational only.",
                "Explain methodology scope in Section 3.1.",
            ],
            "Comment Type: Editorial/Grammar, Clarification, Technical": ["Technical", "Technical"],
            "Agency Suggested Text Change": [
                "Figure 5 remains unchanged; add note that it is illustrative.",
                "Section 3.1 describes an analytical estimate, not a regulatory rule.",
            ],
            "Section": ["3.1", "3.1"],
            "Line": ["12", "18"],
        }
    )
    df.to_excel(comments_path, index=False)

    pdf_path = tmp_path / "report.txt"
    pdf_path.write_text("\n".join(["12 Figure 5 shows the illustrative layout", "18 Section 3.1 describes an analytical estimate"]))

    output_path = tmp_path / "out.xlsx"
    run_pipeline(
        comments_path=comments_path,
        report_path=pdf_path,
        output_path=output_path,
        config_path=None,
        draft_rev2=True,
        assemble_rev2=True,
        draft_mode="CLEAN_REWRITE",
    )

    rev2_sections_path = tmp_path / "out_rev2_sections.json"
    rev2_draft_path = tmp_path / "out_rev2_draft.md"
    rev2_appendix_path = tmp_path / "out_rev2_appendix.md"
    assert rev2_sections_path.exists()
    assert rev2_draft_path.exists()
    assert rev2_appendix_path.exists()

    rewrites = json.loads(rev2_sections_path.read_text())
    assert rewrites
    first = rewrites[0]
    assert first["revised_text"]
    assert first["source_comment_ids"]
    assert first["revision_themes"]
    assert "context_confidence_summary" in first

    draft_text = rev2_draft_path.read_text()
    assert "Rev-2 Draft Narrative" in draft_text
    assert "remain unchanged" not in draft_text
    assert "Shared fixes applied" not in draft_text


def test_rev2_modes_and_validation_differ():
    comment = _analyzed_comment(
        cid="1",
        section="1.0",
        cluster_id="C001",
        cluster_label="method tolerance clarity",
        suggested_text="Clarify tolerance is analytical, not regulatory.",
        context="L10: Tolerance is explained near Figure 1",
    )
    decision = ResolutionDecision(
        disposition="Accept",
        ntia_comment="Accept for clarification.",
        resolution_text="Report clarifies methodology scope.",
        patch_text="Clarify tolerance is analytical, not regulatory.",
        patch_source="suggested_text",
        patch_confidence="HIGH",
        resolution_basis="methodology_scope",
        validation_code="",
        validation_status="",
        validation_notes="",
        canonical_term_used="methodology_scope",
    )
    decisions = {"1": decision}
    shared = [SharedResolution(master_resolution_id="MR-01", linked_comment_ids=["1"], shared_fix_text="Shared fix: clarify methodology scope.", target_section="1.0")]

    clean_rewrite = build_section_rewrites([comment], decisions, shared, draft_mode="CLEAN_REWRITE")
    exec_rewrite = build_section_rewrites([comment], decisions, shared, draft_mode="EXECUTIVE_PLAIN_LANGUAGE")

    assert clean_rewrite[0].revised_text != exec_rewrite[0].revised_text
    validated = validate_section_rewrite(clean_rewrite[0])
    assert "REV2_EMPTY" not in validated.validation_codes
    assert "REV2_META_COMMENTARY" not in validated.validation_codes
    assert "rewrite" not in validated.revised_text.lower()


def test_rev2_validation_and_open_issue_handling():
    comment_a = _analyzed_comment(
        cid="1",
        section="2.0",
        cluster_id="C001",
        cluster_label="terminology consistency",
        suggested_text="Align terminology with glossary definition.",
        context="L12: Terminology should match glossary",
    )
    comment_b = _analyzed_comment(
        cid="2",
        section="2.0",
        cluster_id="C001",
        cluster_label="terminology consistency",
        suggested_text="Clarify the same glossary term without changing meaning.",
        context="L15: Term is repeated",
    )
    decision_a = ResolutionDecision(
        disposition="Accept",
        ntia_comment="accepted",
        resolution_text="Term aligned with glossary.",
        patch_text="Aligns the term with glossary usage.",
        patch_source="suggested_text",
        patch_confidence="HIGH",
        resolution_basis="terminology",
        validation_code="",
        validation_status="",
        validation_notes="",
        canonical_term_used="terminology",
    )
    decision_b = ResolutionDecision(
        disposition="Reject",
        ntia_comment="reject minimal change",
        resolution_text="Term clarified without glossary change.",
        patch_text="Clarifies the glossary term meaning without altering usage.",
        patch_source="suggested_text",
        patch_confidence="MEDIUM",
        resolution_basis="terminology",
        validation_code="",
        validation_status="",
        validation_notes="",
        canonical_term_used="terminology",
    )
    decisions = {"1": decision_a, "2": decision_b}
    shared = [
        SharedResolution(
            master_resolution_id="MR-02",
            linked_comment_ids=["1", "2"],
            shared_fix_text="Use glossary term consistently and note non-regulatory intent.",
            target_section="2.0",
        )
    ]

    rewrites = build_section_rewrites([comment_a, comment_b], decisions, shared, draft_mode="MINIMAL_EDIT")
    rewrite = rewrites[0]
    validated = validate_section_rewrite(rewrite)

    assert "CONFLICTING_COMMENTS" not in rewrite.open_issues
    assert rewrite.shared_fix_count == 1
    assert rewrite.source_patch_count == 2
    assert validated.revised_text.count(";") < 3
    assert "REV2_PATCH_STITCHING" not in validated.validation_codes


def test_rev2_validation_meta_and_grounding_flags():
    rewrite = SectionRewrite(
        section_id="4.0",
        section_title="4.0",
        draft_mode="CLEAN_REWRITE",
        source_comment_ids=["1"],
        source_cluster_ids=[],
        source_master_resolution_ids=[],
        revision_themes=["terminology clarity"],
        original_text="",
        revised_text="Shared fixes applied; patch A; patch B; Source text reference L12.",
        revision_rationale="",
    )
    validated = validate_section_rewrite(rewrite)
    assert "REV2_META_COMMENTARY" in validated.validation_codes
    assert "REV2_PATCH_STITCHING" in validated.validation_codes
    assert "REV2_SOURCE_DUMP" in validated.validation_codes
    assert validated.confidence == "LOW"


def test_rev2_figure_reference_not_recreated():
    rewrite = SectionRewrite(
        section_id="5.0",
        section_title="5.0",
        draft_mode="MINIMAL_EDIT",
        source_comment_ids=["1"],
        source_cluster_ids=[],
        source_master_resolution_ids=[],
        revision_themes=["figure reference"],
        original_text="",
        revised_text="Figure 5 remains unchanged and is referenced for context.",
        revision_rationale="",
        grounded_from_original_text=True,
        grounding_quality="HIGH",
    )
    validated = validate_section_rewrite(rewrite)
    assert "REV2_FIGURE_RECREATION_ATTEMPT" not in validated.validation_codes
