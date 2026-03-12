from __future__ import annotations

from ..models import AnalyzedComment, ResolutionDecision


def validate_resolution(comment: AnalyzedComment, decision: ResolutionDecision) -> ResolutionDecision:
    status = "PASS"
    notes: list[str] = []
    codes: list[str] = []

    if decision.disposition == "Accept":
        if not decision.patch_text:
            status = "FAIL"
            codes.append("ACCEPT_NO_PATCH_TEXT")
            notes.append("Accept disposition requires patch_text.")
    elif decision.disposition == "Reject":
        if "because" not in decision.resolution_text.lower() and "reason" not in decision.resolution_text.lower():
            status = "FAIL"
            codes.append("REJECT_NO_RATIONALE")
            notes.append("Reject disposition must include rationale.")
    else:
        if not decision.patch_text:
            status = "WARN" if status == "PASS" else status
            codes.append("EMPTY_PATCH")
            notes.append("Partial accept provided without patch text.")

    if comment.normalized_type == "TECHNICAL":
        if comment.context_confidence in {"NO_CONTEXT_FOUND"}:
            status = "WARN" if status != "FAIL" else status
            codes.append("TECH_COMMENT_NO_CONTEXT")
            notes.append("Technical comment lacks PDF context.")
        elif comment.context_confidence == "PAGE_APPROXIMATION":
            codes.append("LOW_CONTEXT_CONFIDENCE")
            notes.append("Context pulled from page approximation; verify placement.")

    if comment.cluster_size > 1 and decision.disposition in {"Accept", "Partial Accept"} and not comment.shared_resolution_id:
        codes.append("SHARED_RESOLUTION_NOT_LINKED")
        status = "WARN" if status != "FAIL" else status
        notes.append("Clustered comments should link to a shared resolution.")

    decision.validation_code = "|".join(dict.fromkeys(codes))
    decision.validation_status = status
    decision.validation_notes = "; ".join(notes)
    return decision
