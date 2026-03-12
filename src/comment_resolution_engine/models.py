from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(slots=True)
class CommentRecord:
    """Raw record captured from the comment matrix before normalization."""

    id: str
    reviewer_initials: str
    agency: str
    report_version: str
    section: str
    page: Optional[int]
    line: Optional[int]
    comment_type: str
    agency_notes: str
    agency_suggested_text: str
    wg_chain_comments: str = ""
    comment_disposition: str = ""
    resolution: str = ""
    raw_row: dict = field(default_factory=dict)


@dataclass(slots=True)
class NormalizedComment(CommentRecord):
    """Normalized record after ingest + normalization."""

    normalized_type: str = ""
    effective_comment: str = ""
    effective_suggested_text: str = ""
    report_context: str = ""
    context_confidence: str = ""


@dataclass(slots=True)
class AnalyzedComment(NormalizedComment):
    """Record enriched with analysis stage artifacts."""

    cluster_id: str = ""
    cluster_label: str = ""
    cluster_size: int = 0
    section_group: str = ""
    intent_classification: str = ""
    heat_level: str = ""
    heat_count: int = 0
    resolution_basis: str = ""
    patch_source: str = ""
    patch_text: str = ""
    patch_confidence: str = ""
    shared_resolution_id: str = ""
    canonical_term_used: str = ""


@dataclass(slots=True)
class ClusterInfo:
    cluster_id: str
    cluster_label: str
    cluster_size: int
    representative_comment_id: str
    sections: List[str] = field(default_factory=list)


@dataclass(slots=True)
class ResolutionDecision:
    disposition: str
    ntia_comment: str
    resolution_text: str
    patch_text: str
    patch_source: str
    patch_confidence: str
    resolution_basis: str
    validation_code: str = ""
    validation_status: str = ""
    validation_notes: str = ""
    canonical_term_used: str = ""


@dataclass(slots=True)
class PatchRecord:
    comment_id: str
    target_section: str
    target_lines: str
    action_type: str
    old_text: str
    new_text: str
    rationale: str
    patch_source: str
    confidence: str
    shared_resolution_id: str = ""


@dataclass(slots=True)
class SharedResolution:
    master_resolution_id: str
    linked_comment_ids: List[str]
    shared_fix_text: str
    target_section: str


@dataclass(slots=True)
class FAQEntry:
    faq_id: str
    normalized_question: str
    canonical_answer: str
    related_comment_ids: List[str] = field(default_factory=list)
    affected_sections: List[str] = field(default_factory=list)


@dataclass(slots=True)
class SectionIssueBrief:
    section: str
    total_comments: int
    themes: List[str]
    revision_strategy: List[str]


@dataclass(slots=True)
class SectionRewrite:
    section_id: str
    section_title: str
    draft_mode: str
    source_comment_ids: List[str]
    source_cluster_ids: List[str]
    source_master_resolution_ids: List[str]
    revision_themes: List[str]
    original_text: str
    revised_text: str
    revision_rationale: str
    open_issues: List[str] = field(default_factory=list)
    confidence: str = "MEDIUM"
    canonical_terms_used: List[str] = field(default_factory=list)
    context_confidence_summary: str = ""
    validation_codes: List[str] = field(default_factory=list)
    shared_fix_count: int = 0
    source_patch_ids: List[str] = field(default_factory=list)
    source_patch_count: int = 0
    grounded_from_original_text: bool = False
    grounding_quality: str = "NONE"
