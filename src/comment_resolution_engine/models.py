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


@dataclass(slots=True)
class AnalyzedComment(NormalizedComment):
    """Record enriched with analysis stage artifacts."""

    cluster_id: str = ""
    section_group: str = ""
    intent_classification: str = ""
    heat_level: str = ""
    heat_count: int = 0


@dataclass(slots=True)
class ResolutionDecision:
    disposition: str
    ntia_comment: str
    resolution_text: str
    validation_status: str = ""
    validation_notes: str = ""


@dataclass(slots=True)
class PatchRecord:
    comment_id: str
    target_section: str
    target_lines: str
    action_type: str
    old_text: str
    new_text: str
    rationale: str


@dataclass(slots=True)
class SharedResolution:
    master_resolution_id: str
    linked_comment_ids: List[str]
    shared_fix_text: str


@dataclass(slots=True)
class FAQEntry:
    faq_id: str
    question: str
    answer: str
    related_comments: List[str] = field(default_factory=list)
    affected_sections: List[str] = field(default_factory=list)


@dataclass(slots=True)
class SectionIssueBrief:
    section: str
    total_comments: int
    themes: List[str]
    revision_strategy: List[str]
