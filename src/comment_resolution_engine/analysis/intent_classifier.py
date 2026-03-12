from __future__ import annotations

from ..models import NormalizedComment

INTENT_KEYWORDS = {
    "REQUEST_CHANGE": ("change", "update", "modify", "replace", "revise"),
    "REQUEST_CLARIFICATION": ("clarify", "clarification", "unclear", "confusing", "explain"),
    "SUGGEST_EDIT": ("suggest", "edit", "grammar", "typo", "wording"),
    "TECHNICAL_CHALLENGE": ("assumption", "method", "model", "data", "technical", "calculation"),
    "OUT_OF_SCOPE": ("out of scope", "not applicable", "irrelevant"),
}


def classify_intent(comment: NormalizedComment) -> str:
    text = " ".join(
        [
            comment.effective_comment or "",
            comment.effective_suggested_text or "",
            comment.agency_notes or "",
            comment.agency_suggested_text or "",
        ]
    ).lower()

    for intent, keywords in INTENT_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return intent

    if comment.normalized_type == "EDITORIAL":
        return "SUGGEST_EDIT"
    if comment.normalized_type == "TECHNICAL":
        return "TECHNICAL_CHALLENGE"
    return "REQUEST_CLARIFICATION"
