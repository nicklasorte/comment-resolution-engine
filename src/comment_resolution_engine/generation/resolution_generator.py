from __future__ import annotations

from typing import List, Tuple

from ..adjudication import AdjudicationPolicy, PolicyContext, PolicyDecision, ReasonCode
from ..knowledge.canonical_definitions import lookup_definition, lookup_rationale, match_canonical_term
from ..knowledge.issue_library import detect_issue_type, find_issue
from ..models import AnalyzedComment, ResolutionDecision
from ..rules import RuleEngine, summarize_rule_matches
from ..rules.provenance import GENERATION_MODE_EXTERNAL, GENERATION_MODE_HYBRID, GENERATION_MODE_LOCAL
from ..contracts import DEFAULT_GENERATION_MODE

_POLICY = AdjudicationPolicy()


def _normalize_disposition(value: str) -> str:
    text = (value or "").strip().lower()
    if text.startswith("acc"):
        return "Accept"
    if text.startswith("rej"):
        return "Reject"
    if text.startswith("part"):
        return "Partial Accept"
    return ""


def _policy_context(comment: AnalyzedComment) -> PolicyContext:
    agency = comment.agency or getattr(comment, "source_agency", "") or "Unknown Agency"
    return PolicyContext(
        comment_number=str(comment.id),
        source_agency=agency,
        commenter=comment.reviewer_initials or getattr(comment, "commenter", ""),
        comment_text=comment.agency_notes or comment.effective_comment or "",
        comment_type=comment.normalized_type or comment.comment_type,
        proposed_change=comment.effective_suggested_text or comment.agency_suggested_text,
        target_section=comment.section or "",
        target_page=str(comment.page or ""),
        target_line=str(comment.line or ""),
        status=comment.review_status or comment.status,
        disposition=comment.comment_disposition or "",
        resolution=comment.resolution or "",
        intent=comment.intent_classification,
        resolution_summary=comment.resolution_basis or comment.resolution or "",
        response_text=comment.response_text or comment.resolution,
    )


def determine_disposition(comment: AnalyzedComment, rule_engine: RuleEngine | None = None, run_context=None) -> tuple[str, list, PolicyDecision]:
    rule_matches: list = []
    policy_decision = _POLICY.decide(_policy_context(comment))
    disposition = policy_decision.disposition
    if rule_engine and rule_engine.enabled:
        issue_match, issue_matches = rule_engine.match_issue_pattern(comment, run_context=run_context)
        if issue_match and issue_match.applied_action.get("disposition"):
            rule_matches.extend(issue_matches)
            comment.issue_pattern = comment.issue_pattern or issue_match.applied_action.get("issue_type", "")
            disposition = issue_match.applied_action.get("disposition")
            policy_decision.reason_code = policy_decision.reason_code or ReasonCode.RULE_BASED.value
            return disposition, rule_matches, policy_decision
        disposition, match, disposition_matches = rule_engine.disposition_for_comment(comment, run_context=run_context)
        if disposition:
            if disposition_matches:
                rule_matches.extend(disposition_matches)
            policy_decision.reason_code = policy_decision.reason_code or ReasonCode.RULE_BASED.value
            return disposition, rule_matches, policy_decision

    return disposition, rule_matches, policy_decision


def _choose_resolution_basis(comment: AnalyzedComment, rule_engine: RuleEngine | None, run_context=None) -> Tuple[str, str, str, List]:
    rule_matches: List = []
    issue_type = ""
    if comment.issue_pattern:
        issue_type = comment.issue_pattern
    elif rule_engine and rule_engine.enabled:
        issue_match, issue_matches = rule_engine.match_issue_pattern(comment, run_context=run_context)
        if issue_match:
            issue_type = issue_match.applied_action.get("issue_type", "")
            rule_matches.extend(issue_matches)

    canonical_term = ""
    canonical_matches: List = []
    if rule_engine:
        canonical_term, canonical_matches = rule_engine.resolve_canonical_term(comment)
        rule_matches.extend(canonical_matches)
    if not canonical_term:
        canonical_term = match_canonical_term(" ".join([comment.effective_comment or "", comment.effective_suggested_text or "", comment.report_context or "", comment.cluster_label or ""]))

    if canonical_term:
        return canonical_term, "canonical_definition", canonical_term, rule_matches
    if issue_type:
        return issue_type, "issue_library", canonical_term, rule_matches
    detected_issue = detect_issue_type(" ".join([comment.effective_comment or "", comment.effective_suggested_text or "", comment.cluster_label or ""]))
    if detected_issue:
        return detected_issue, "issue_library", canonical_term, rule_matches
    if comment.cluster_label:
        return comment.cluster_label, "cluster_theme", canonical_term, rule_matches
    return comment.intent_classification or "comment_intent", "comment_intent", canonical_term, rule_matches


def _generate_rationale(comment: AnalyzedComment, disposition: str, basis_value: str, basis_source: str, canonical_term: str) -> Tuple[str, str]:
    canonical_term = canonical_term or (basis_value if basis_source == "canonical_definition" else "")
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


def _apply_summary(decision: ResolutionDecision, comment: AnalyzedComment, summary: dict) -> None:
    decision.rule_id = summary.get("rule_id", "")
    decision.rule_source = summary.get("rule_source", "")
    decision.rule_version = summary.get("rule_version", "")
    decision.rules_profile = summary.get("rules_profile", "")
    decision.rules_version = summary.get("rules_version", "")
    decision.matched_rule_types = summary.get("matched_rule_types", [])
    decision.generation_mode = summary.get("generation_mode", decision.generation_mode or DEFAULT_GENERATION_MODE)
    comment.rule_id = decision.rule_id
    comment.rule_source = decision.rule_source
    comment.rule_version = decision.rule_version
    comment.rules_profile = decision.rules_profile
    comment.rules_version = decision.rules_version
    comment.matched_rule_types = summary.get("matched_rule_types", [])
    comment.generation_mode = decision.generation_mode
    if summary.get("applied_rules"):
        comment.applied_rules.extend(summary.get("applied_rules", []))


def build_resolution_decision(comment: AnalyzedComment, rule_engine: RuleEngine | None = None, run_context=None) -> ResolutionDecision:
    rule_matches: List = []
    disposition, disposition_matches, policy_decision = determine_disposition(comment, rule_engine=rule_engine, run_context=run_context)
    rule_matches.extend(disposition_matches)
    basis_value, basis_source, canonical_term, basis_matches = _choose_resolution_basis(comment, rule_engine, run_context=run_context)
    rule_matches.extend(basis_matches)
    rationale_text, canonical_term = _generate_rationale(comment, disposition, basis_value, basis_source, canonical_term)
    patch_text, patch_source, patch_confidence, canonical_term_used = _generate_patch_text(comment, disposition, basis_value, basis_source, canonical_term)
    ntia_comment = policy_decision.ntia_comment or _ntia_comment(disposition, patch_text, comment.context_confidence)
    change_summary = policy_decision.resolution_summary or rationale_text
    response_text = policy_decision.response_text or rationale_text

    decision = ResolutionDecision(
        disposition=disposition,
        ntia_comment=ntia_comment,
        resolution_text=response_text,
        resolution_summary=change_summary,
        patch_text=patch_text if policy_decision.requires_change else "",
        patch_source=patch_source if policy_decision.requires_change else "",
        patch_confidence=patch_confidence if policy_decision.requires_change else "",
        resolution_basis=basis_value if policy_decision.requires_change else "",
        reason_code=policy_decision.reason_code,
        policy_version=policy_decision.policy_version,
        validation_code="",
        validation_status="",
        validation_notes="",
        canonical_term_used=canonical_term_used,
    )

    if policy_decision.preserve_existing_resolution:
        decision.patch_text = ""
        decision.patch_source = ""
        decision.patch_confidence = ""
        decision.resolution_basis = ""
        decision.resolution_text = policy_decision.response_text or decision.resolution_text
        decision.resolution_summary = policy_decision.resolution_summary or decision.resolution_text
        decision.ntia_comment = policy_decision.ntia_comment or decision.ntia_comment

    if decision.patch_text and decision.patch_text not in (decision.resolution_text or ""):
        decision.resolution_text = f"{decision.resolution_text} Change: {decision.patch_text}".strip()

    if disposition == "Reject" and "because" not in response_text.lower():
        decision.resolution_text = f"{response_text} because {rationale_text}"

    fallback_mode = GENERATION_MODE_HYBRID if rule_matches else GENERATION_MODE_LOCAL
    summary = summarize_rule_matches(rule_matches, rule_engine.rule_pack.to_metadata() if rule_engine and rule_engine.rule_pack else {}, fallback_mode=fallback_mode)
    _apply_summary(decision, comment, summary)
    return decision
