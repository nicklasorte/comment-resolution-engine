from __future__ import annotations

from ..models import AnalyzedComment, ResolutionDecision
from ..rules import RuleEngine, summarize_rule_matches
from ..rules.provenance import GENERATION_MODE_HYBRID, GENERATION_MODE_LOCAL


def validate_resolution(
    comment: AnalyzedComment, decision: ResolutionDecision, rule_engine: RuleEngine | None = None, run_context=None
) -> ResolutionDecision:
    status = decision.validation_status or "PASS"
    notes: list[str] = [n for n in (decision.validation_notes.split(";") if decision.validation_notes else []) if n]
    codes: list[str] = [c for c in (decision.validation_code.split("|") if decision.validation_code else []) if c]
    rule_matches = []

    if rule_engine and rule_engine.enabled:
        matches, status_override, code_override, notes_override = rule_engine.apply_validation_rules(comment, decision, run_context=run_context)
        rule_matches.extend(matches)
        status = status_override or status
        if code_override:
            codes.extend([c for c in code_override.split("|") if c])
        if notes_override:
            notes.append(notes_override)

    if decision.disposition.lower().startswith("completed"):
        decision.validation_code = "|".join(dict.fromkeys(codes))
        decision.validation_status = status or "PASS"
        decision.validation_notes = "; ".join(notes)
        return decision

    if decision.disposition == "Accept":
        if not decision.patch_text:
            status = "FAIL" if status in {"PASS", ""} else status
            codes.append("ACCEPT_NO_PATCH_TEXT")
            notes.append("Accept disposition requires patch_text.")
    elif decision.disposition == "Reject":
        if "because" not in decision.resolution_text.lower() and "reason" not in decision.resolution_text.lower():
            status = "FAIL" if status in {"PASS", ""} else status
            codes.append("REJECT_NO_RATIONALE")
            notes.append("Reject disposition must include rationale.")
    else:
        if not decision.patch_text:
            status = "WARN" if status == "PASS" else status
            codes.append("EMPTY_PATCH")
            notes.append("Partial accept provided without patch text.")

    if not decision.reason_code:
        status = status if status in {"FAIL", "needs_review"} else "WARN"
        codes.append("MISSING_REASON_CODE")
        notes.append("Reason code is required for traceability.")

    if comment.normalized_type == "TECHNICAL":
        if comment.context_confidence in {"NO_CONTEXT_FOUND"}:
            status = status if status in {"FAIL", "needs_review"} else "WARN"
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
    if rule_matches and rule_engine and rule_engine.rule_pack:
        summary = summarize_rule_matches(rule_matches, rule_engine.rule_pack.to_metadata(), fallback_mode=GENERATION_MODE_HYBRID)
        decision.matched_rule_types = list(dict.fromkeys((decision.matched_rule_types or []) + summary.get("matched_rule_types", [])))
        decision.rule_id = decision.rule_id or summary.get("rule_id", "")
        decision.rule_source = decision.rule_source or summary.get("rule_source", "")
        decision.rule_version = decision.rule_version or summary.get("rule_version", "")
        decision.rules_profile = decision.rules_profile or summary.get("rules_profile", "")
        decision.rules_version = decision.rules_version or summary.get("rules_version", "")
        decision.generation_mode = summary.get("generation_mode", decision.generation_mode or GENERATION_MODE_LOCAL)
    return decision
