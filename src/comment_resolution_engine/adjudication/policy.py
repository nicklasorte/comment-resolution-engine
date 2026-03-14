from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from ..errors import CREError, ErrorCategory

POLICY_VERSION = "1.0.0"

_COMPLETED_VALUES = {"completed", "complete", "closed", "resolved", "done", "no action", "no action needed"}
_PARTIAL_VALUES = {"partial", "partially accepted", "accepted in part", "partially adopt"}
_REJECT_VALUES = {"reject", "rejected"}
_DUPLICATE_VALUES = {"duplicate", "dup"}
_OUT_OF_SCOPE_SIGNALS = {"out of scope", "outside scope"}


def _norm(value: str) -> str:
    return str(value or "").strip()


def _norm_lower(value: str) -> str:
    return _norm(value).lower()


def _truncate(text: str, limit: int = 220) -> str:
    clean = _norm(text)
    return clean if len(clean) <= limit else f"{clean[:limit].rstrip()}..."


def _target_reference(section: str, page: str, line: str) -> str:
    parts: list[str] = []
    if section:
        parts.append(f"Section {section}")
    if page:
        parts.append(f"p. {page}")
    if line:
        parts.append(f"l. {line}")
    return ", ".join(parts)


class ReasonCode(str, Enum):
    EDITORIAL_ACCEPTED = "EDITORIAL_ACCEPTED"
    TECHNICAL_ACCEPTED = "TECHNICAL_ACCEPTED"
    TECHNICAL_ACCEPTED_PARTIAL = "TECHNICAL_ACCEPTED_PARTIAL"
    CLARIFICATION_PROVIDED = "CLARIFICATION_PROVIDED"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    DUPLICATE_COMMENT = "DUPLICATE_COMMENT"
    NO_CHANGE_NEEDED = "NO_CHANGE_NEEDED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    REJECTED_WITH_RATIONALE = "REJECTED_WITH_RATIONALE"
    RULE_BASED = "RULE_BASED"


@dataclass(slots=True)
class PolicyContext:
    comment_number: str
    source_agency: str
    commenter: str
    comment_text: str
    comment_type: str
    proposed_change: str = ""
    target_section: str = ""
    target_page: str = ""
    target_line: str = ""
    status: str = ""
    disposition: str = ""
    resolution: str = ""
    intent: str = ""
    resolution_summary: str = ""
    response_text: str = ""


@dataclass(slots=True)
class PolicyDecision:
    disposition: str
    reason_code: str
    response_text: str
    resolution_summary: str
    ntia_comment: str
    change_description: str
    target_reference: str
    requires_change: bool = True
    preserve_existing_resolution: bool = False
    policy_version: str = POLICY_VERSION


def _validate_context(ctx: PolicyContext) -> None:
    missing: list[str] = []
    if not _norm(ctx.comment_number):
        missing.append("comment_number")
    if not _norm(ctx.source_agency):
        missing.append("source_agency")
    if not _norm(ctx.comment_text):
        missing.append("comment_text")
    if not _norm(ctx.comment_type):
        missing.append("comment_type")
    if missing:
        raise CREError(
            ErrorCategory.VALIDATION_ERROR,
            f"ERROR: Missing required comment fields for adjudication: {', '.join(missing)}",
        )


class AdjudicationPolicy:
    """
    Deterministic mapping from comment metadata to disposition, reason code, and response template.
    """

    name = "deterministic_policy"
    version = POLICY_VERSION

    def decide(self, ctx: PolicyContext) -> PolicyDecision:
        _validate_context(ctx)

        disposition_hint = _norm_lower(ctx.disposition)
        status_hint = _norm_lower(ctx.status)
        comment_text = _norm(ctx.comment_text)
        comment_type = _norm_lower(ctx.comment_type)
        proposed_change = _truncate(ctx.proposed_change or "")
        target_ref = _target_reference(_norm(ctx.target_section), _norm(ctx.target_page), _norm(ctx.target_line))

        def _no_change(reason: ReasonCode, message: str, ntia: str, preserve_existing: bool = False) -> PolicyDecision:
            return PolicyDecision(
                disposition="Completed" if preserve_existing else "Reject",
                reason_code=reason.value,
                response_text=_norm(ctx.response_text or ctx.resolution) if preserve_existing else message,
                resolution_summary=message,
                ntia_comment=ntia,
                change_description="",
                target_reference=target_ref,
                requires_change=False,
                preserve_existing_resolution=preserve_existing,
            )

        if disposition_hint in _COMPLETED_VALUES or status_hint in _COMPLETED_VALUES:
            summary = "Already completed; no further action needed."
            ntia = "Completed in source matrix; preserve existing resolution."
            return _no_change(ReasonCode.NO_CHANGE_NEEDED, summary, ntia, preserve_existing=True)

        if any(token in disposition_hint for token in _DUPLICATE_VALUES) or any(token in comment_text.lower() for token in _DUPLICATE_VALUES):
            msg = "No change. Duplicate of another comment; track under the primary entry."
            ntia = "Duplicate comment; linked to primary record."
            return _no_change(ReasonCode.DUPLICATE_COMMENT, msg, ntia, preserve_existing=False)

        if any(sig in comment_text.lower() for sig in _OUT_OF_SCOPE_SIGNALS) or any(sig in disposition_hint for sig in _OUT_OF_SCOPE_SIGNALS) or ctx.intent == "OUT_OF_SCOPE":
            msg = "Rejected because the request is outside the scope of the working paper."
            ntia = "Out of scope; no edit planned."
            return _no_change(ReasonCode.OUT_OF_SCOPE, msg, ntia, preserve_existing=False)

        if disposition_hint in _REJECT_VALUES:
            rationale = _truncate(ctx.resolution_summary or comment_text or "no supporting rationale provided")
            message = f"Rejected because {rationale}"
            return PolicyDecision(
                disposition="Reject",
                reason_code=ReasonCode.REJECTED_WITH_RATIONALE.value,
                response_text=message,
                resolution_summary=rationale,
                ntia_comment="Rejected with documented rationale.",
                change_description="",
                target_reference=target_ref,
                requires_change=False,
            )

        if comment_type.startswith("clar") or "clarification" in comment_text.lower():
            change = proposed_change or _truncate(comment_text, limit=160)
            message = f"Accepted for clarification. We will add targeted language in {target_ref or 'the relevant section'} to address: {change}"
            return PolicyDecision(
                disposition="Accept",
                reason_code=ReasonCode.CLARIFICATION_PROVIDED.value,
                response_text=message,
                resolution_summary=message,
                ntia_comment="Clarification will be incorporated.",
                change_description=change,
                target_reference=target_ref,
            )

        if "editorial" in comment_type or "grammar" in comment_type:
            change = proposed_change or _truncate(comment_text, limit=160)
            message = f"Accepted. Editorial correction will be applied in {target_ref or 'the document'} to address: {change}"
            return PolicyDecision(
                disposition="Accept",
                reason_code=ReasonCode.EDITORIAL_ACCEPTED.value,
                response_text=message,
                resolution_summary=message,
                ntia_comment="Editorial fix to be incorporated.",
                change_description=change,
                target_reference=target_ref,
            )

        if disposition_hint in _PARTIAL_VALUES or status_hint in _PARTIAL_VALUES or (comment_type.startswith("tech") and not proposed_change):
            change = proposed_change or _truncate(comment_text, limit=160)
            message = f"Accepted in part. We will add clarification in {target_ref or 'the relevant section'} to cover: {change}. Remaining items will be noted for future review."
            return PolicyDecision(
                disposition="Partial Accept",
                reason_code=ReasonCode.TECHNICAL_ACCEPTED_PARTIAL.value,
                response_text=message,
                resolution_summary=message,
                ntia_comment="Partial accept; clarification drafted.",
                change_description=change,
                target_reference=target_ref,
            )

        # Default: accepted/incorporated
        change = proposed_change or _truncate(comment_text, limit=160)
        ntia_comment = "Accepted; incorporated into draft."
        disposition = "Accept"
        reason_code_enum = ReasonCode.TECHNICAL_ACCEPTED if comment_type.startswith("tech") else ReasonCode.EDITORIAL_ACCEPTED
        message = f"Accepted. We will incorporate the change in {target_ref or 'the relevant section'} to address: {change}"
        return PolicyDecision(
            disposition=disposition,
            reason_code=reason_code_enum.value,
            response_text=message,
            resolution_summary=message,
            ntia_comment=ntia_comment,
            change_description=change,
            target_reference=target_ref,
        )
