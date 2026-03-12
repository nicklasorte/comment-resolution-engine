from __future__ import annotations

from typing import Tuple

from ..knowledge.canonical_definitions import lookup_definition, lookup_rationale, match_canonical_term
from ..knowledge.issue_library import detect_issue_type, find_issue
from ..models import AnalyzedComment, ResolutionDecision


def _normalize_disposition(value: str) -> str:
    text = (value or "").strip().lower()
    if text.startswith("acc"):
        return "Accept"
    if text.startswith("rej"):
        return "Reject"
    if text.startswith("part"):
        return "Partial Accept"
    return ""


def determine_disposition(comment: AnalyzedComment) -> str:
    if comment.comment_disposition:
        return _normalize_disposition(comment.comment_disposition) or "Accept"

    if comment.intent_classification == "OUT_OF_SCOPE":
        return "Reject"

    if comment.normalized_type == "TECHNICAL" and comment.context_confidence in {"NO_CONTEXT_FOUND"}:
        return "Partial Accept"

    if comment.normalized_type == "EDITORIAL":
        return "Accept"

    if "reject" in (comment.effective_comment or "").lower() and "already" in (comment.effective_comment or "").lower():
        return "Reject"

    return "Accept"


def _choose_resolution_basis(comment: AnalyzedComment) -> Tuple[str, str]:
    issue_type = detect_issue_type(" ".join([comment.effective_comment or "", comment.effective_suggested_text or "", comment.cluster_label or ""]))
    canonical_term = match_canonical_term(" ".join([comment.effective_comment or "", comment.effective_suggested_text or "", comment.report_context or "", comment.cluster_label or ""]))
    if canonical_term:
        return canonical_term, "canonical_definition"
    if issue_type:
        return issue_type, "issue_library"
    if comment.cluster_label:
        return comment.cluster_label, "cluster_theme"
    return comment.intent_classification or "comment_intent", "comment_intent"


def _generate_rationale(comment: AnalyzedComment, disposition: str, basis_value: str, basis_source: str) -> Tuple[str, str]:
    canonical_term = basis_value if basis_source == "canonical_definition" else ""
    rationale_parts: list[str] = []
    if disposition == "Reject":
        rationale_parts.append("The requested change was not adopted")
        if comment.intent_classification == "OUT_OF_SCOPE":
            rationale_parts.append("because the topic is outside the scope of this working paper")
        elif comment.report_context:
            rationale_parts.append(f"because the cited passage already provides the requested detail ({comment.report_context})")
        else:
            rationale_parts.append("because the existing language already reflects the analytical intent")
    elif disposition == "Partial Accept":
        rationale_parts.append("The comment is acknowledged; clarifications will be added while maintaining existing analytical framing.")
    else:
        rationale_parts.append("The report text will be updated to address the comment.")

    if canonical_term:
        rationale = lookup_rationale(canonical_term)
        if rationale:
            rationale_parts.append(rationale)
    elif basis_source.startswith("issue_library"):
        issue = find_issue(basis_value)
        if issue and issue.get("approved_answer"):
            rationale_parts.append(issue["approved_answer"])
    elif comment.cluster_label:
        rationale_parts.append(f"Addresses cluster theme: {comment.cluster_label}")

    text = " ".join(part for part in rationale_parts if part)
    return text or "Resolution provided for traceability.", canonical_term


def _generate_patch_text(comment: AnalyzedComment, disposition: str, basis_value: str, basis_source: str, canonical_term: str) -> Tuple[str, str, str, str]:
    if disposition == "Reject":
        return "", "synthesized_from_comment", "LOW", canonical_term

    if comment.effective_suggested_text:
        confidence = "HIGH" if comment.context_confidence == "EXACT_LINE_MATCH" else "MEDIUM"
        return comment.effective_suggested_text, "suggested_text", confidence, canonical_term

    if canonical_term:
        definition = lookup_definition(canonical_term)
        if definition:
            confidence = "HIGH" if comment.context_confidence == "EXACT_LINE_MATCH" else "MEDIUM"
            return definition, "canonical_definition", confidence, canonical_term

    if basis_source == "cluster_theme" and comment.cluster_label:
        return f"Clarify: {comment.cluster_label}.", "cluster_fix", "MEDIUM", canonical_term

    if comment.effective_comment:
        confidence = "MEDIUM" if comment.context_confidence != "NO_CONTEXT_FOUND" else "LOW"
        return f"Add clarification: {comment.effective_comment}", "synthesized_from_comment", confidence, canonical_term

    return "", "synthesized_from_comment", "LOW", canonical_term


def _ntia_comment(disposition: str, patch_text: str, context_confidence: str) -> str:
    if disposition == "Reject":
        return "Reject. No change to report text; rationale captured in resolution."
    if disposition == "Partial Accept":
        return "Partial Accept. Clarifications will be added while maintaining analytical framing."
    prefix = "Accept."
    if not patch_text:
        return f"{prefix} Additional follow-up needed to finalize patch text."
    if context_confidence != "NO_CONTEXT_FOUND":
        return f"{prefix} Report language drafted for insertion."
    return f"{prefix} Patch drafted; verify placement due to missing PDF context."


def build_resolution_decision(comment: AnalyzedComment) -> ResolutionDecision:
    disposition = determine_disposition(comment)
    basis_value, basis_source = _choose_resolution_basis(comment)
    rationale_text, canonical_term = _generate_rationale(comment, disposition, basis_value, basis_source)
    patch_text, patch_source, patch_confidence, canonical_term_used = _generate_patch_text(comment, disposition, basis_value, basis_source, canonical_term)
    ntia_comment = _ntia_comment(disposition, patch_text, comment.context_confidence)

    return ResolutionDecision(
        disposition=disposition,
        ntia_comment=ntia_comment,
        resolution_text=rationale_text,
        patch_text=patch_text,
        patch_source=patch_source,
        patch_confidence=patch_confidence,
        resolution_basis=basis_value,
        validation_code="",
        validation_status="",
        validation_notes="",
        canonical_term_used=canonical_term_used,
    )
