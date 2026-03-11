from __future__ import annotations

from .resolver_schema import ResolutionRow


def classify_comment_type(comment_text: str) -> str:
    text = (comment_text or "").lower()

    if any(k in text for k in ["typo", "grammar", "format", "editorial", "spelling", "punctuation"]):
        return "Editorial"
    if any(k in text for k in ["define", "definition", "term means", "acronym"]):
        return "Definition"
    if any(k in text for k in ["scope", "out of scope", "outside scope", "not in this report"]):
        return "Scope"
    if any(k in text for k in ["method", "methodology", "approach", "calculation", "model"]):
        return "Methodology"
    if any(k in text for k in ["assumption", "assume", "conservative", "worst-case"]):
        return "Assumption"
    if any(k in text for k in ["justify", "justification", "rationale", "basis"]):
        return "Justification"
    if any(k in text for k in ["clarify", "unclear", "explain"]):
        return "Clarification"
    return "General"


def build_resolution_task(row: ResolutionRow) -> str:
    status_instruction = (
        "Status handling: if status is completed/complete/closed/resolved, set output Status to Complete and keep Proposed Report Text blank unless updated text is explicitly required."
    )

    bits = [
        "Write 1-3 sentences of report-ready text that can be inserted directly into the report.",
        "Style rules: no meta-response language; do not mention reviewers/comments/responses; keep wording specific, neutral, and technically precise.",
        status_instruction,
        f"Comment text: {row.comment or 'N/A'}.",
        f"Line reference: {row.line_number or 'N/A'}.",
    ]

    if row.existing_revision_notes:
        bits.append(f"Existing revision notes: {row.existing_revision_notes}.")

    if row.report_context:
        bits.append(f"Report context: {row.report_context}.")
    else:
        bits.append("Report context: not available from PDF extraction.")

    return " ".join(bits)
