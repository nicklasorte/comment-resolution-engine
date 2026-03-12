from __future__ import annotations

from typing import Tuple

from ..knowledge.canonical_definitions import lookup_definition
from ..models import AnalyzedComment, ResolutionDecision


def _normalize_disposition(value: str) -> str:
    text = (value or "").strip().lower()
    if text.startswith("acc"):
        return "Accept"
    if text.startswith("rej"):
        return "Reject"
    return ""


def determine_disposition(comment: AnalyzedComment) -> str:
    if comment.comment_disposition:
        return _normalize_disposition(comment.comment_disposition) or "Accept"

    if comment.normalized_type == "EDITORIAL":
        return "Accept"
    if comment.intent_classification == "OUT_OF_SCOPE":
        return "Reject"
    if comment.intent_classification == "TECHNICAL_CHALLENGE" and "out of scope" in (comment.effective_comment or "").lower():
        return "Reject"
    return "Accept"


def _render_accept_resolution(comment: AnalyzedComment) -> str:
    base_reference = ""
    if comment.report_context:
        base_reference = f"Based on the cited text ({comment.report_context}), the report now clarifies that "
    elif comment.section:
        base_reference = f"In Section {comment.section}, the report now clarifies that "
    else:
        base_reference = "The report now clarifies that "

    payload = comment.effective_suggested_text or comment.effective_comment or "the analysis language has been refined for clarity."
    if comment.normalized_type == "EDITORIAL":
        payload = comment.effective_suggested_text or comment.effective_comment or "terminology has been standardized."

    return f"{base_reference}{payload}"


def _render_reject_resolution(comment: AnalyzedComment) -> str:
    rationale = "the existing language already reflects the analytical approach."
    if "out of scope" in (comment.effective_comment or "").lower():
        rationale = "the requested change is outside the scope of this working paper."
    elif comment.report_context:
        rationale = f"the cited text ({comment.report_context}) already provides this detail."
    return f"The suggested modification was not adopted because {rationale}"


def generate_resolution(comment: AnalyzedComment, disposition: str) -> Tuple[str, str]:
    if disposition == "Reject":
        resolution_text = _render_reject_resolution(comment)
        ntia_comment = "Reject. No change to report text; rationale provided in resolution."
    else:
        resolution_text = _render_accept_resolution(comment)
        ntia_comment = "Accept. Report language updated for clarity and traceability."
        if comment.normalized_type == "TECHNICAL":
            definition = lookup_definition("population_impact_metric")
            if definition and definition.lower() not in resolution_text.lower():
                resolution_text = f"{resolution_text} {definition}"
    return resolution_text, ntia_comment


def build_resolution_decision(comment: AnalyzedComment) -> ResolutionDecision:
    disposition = determine_disposition(comment)
    resolution_text, ntia_comment = generate_resolution(comment, disposition)
    return ResolutionDecision(
        disposition=disposition,
        ntia_comment=ntia_comment,
        resolution_text=resolution_text,
        validation_status="",
        validation_notes="",
    )
