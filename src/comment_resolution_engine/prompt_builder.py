from __future__ import annotations

from .resolver_schema import ResolutionRow


def classify_comment_type(comment_text: str) -> str:
    text = (comment_text or "").lower()
    if any(k in text for k in ["typo", "grammar", "edit"]):
        return "Editorial"
    if any(k in text for k in ["clarify", "explain", "define"]):
        return "Clarification"
    if any(k in text for k in ["method", "assumption", "analysis", "model"]):
        return "Technical"
    return "General"


def build_resolution_task(row: ResolutionRow) -> str:
    status = (row.status or "").strip().lower()
    if status in {"complete", "completed", "closed", "resolved"}:
        return "Status indicates comment is complete. Set Status to Complete and keep Proposed Report Text blank unless updated report text is provided."

    bits = [
        "Write 1-3 sentences of report-ready text that can be inserted directly into the report.",
        "Do not mention the comment process or phrases like 'in response to comment'.",
        f"Comment number: {row.comment_number or 'N/A'}.",
        f"Comment text: {row.comment or 'N/A'}",
    ]
    if row.line_number:
        bits.append(f"Line reference: {row.line_number}.")
    if row.revision:
        bits.append(f"Existing revision notes: {row.revision}.")
    return " ".join(bits)
