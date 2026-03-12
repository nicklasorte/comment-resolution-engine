from __future__ import annotations

from ..models import AnalyzedComment, ResolutionDecision


def _contains_change_language(text: str) -> bool:
    text = text.lower()
    return any(token in text for token in ("now", "updated", "clarifies", "adds", "revised", "refined", "adjusted", "incorporated"))


def validate_resolution(comment: AnalyzedComment, decision: ResolutionDecision) -> ResolutionDecision:
    status = "PASS"
    notes: list[str] = []

    if decision.disposition == "Accept":
        if not _contains_change_language(decision.resolution_text):
            status = "FAIL"
            notes.append("Accept resolution must state the specific change to the report.")
    else:
        if "because" not in decision.resolution_text.lower() and "rationale" not in decision.resolution_text.lower():
            status = "FAIL"
            notes.append("Reject resolution must provide justification.")

    if comment.normalized_type == "EDITORIAL" and decision.disposition != "Accept":
        status = "WARN"
        notes.append("Editorial comments should normally be accepted unless they introduce ambiguity.")

    if comment.normalized_type == "TECHNICAL":
        if not comment.report_context and "section" not in decision.resolution_text.lower() and "method" not in decision.resolution_text.lower():
            if status == "PASS":
                status = "WARN"
            notes.append("Technical resolutions should reference report section, method, or context.")

    decision.validation_status = status
    decision.validation_notes = "; ".join(notes)
    return decision
