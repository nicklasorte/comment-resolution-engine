from __future__ import annotations

from .config import normalize_header
from .resolver_schema import ResolutionRow


def normalize_comment_type(raw_value: str) -> str:
    text = normalize_header(raw_value or "")
    if not text:
        return ""
    if "technical" in text:
        return "Technical"
    if "clarification" in text or "clarify" in text:
        return "Clarification"
    if "editorial" in text or "grammar" in text or "grammatical" in text:
        return "Editorial/Grammar"
    if text in {"editorial", "grammatical", "grammar"}:
        return "Editorial/Grammar"
    return ""


def extract_effective_comment(agency_notes: str, agency_suggested_text: str) -> str:
    if agency_notes and str(agency_notes).strip():
        return str(agency_notes).strip()
    if agency_suggested_text and str(agency_suggested_text).strip():
        return str(agency_suggested_text).strip()
    return ""


def extract_effective_suggested_text(agency_suggested_text: str) -> str:
    return str(agency_suggested_text).strip() if agency_suggested_text else ""


def determine_accept_reject(row: ResolutionRow) -> str:
    if row.row_status == "Complete":
        return "Accept"

    content = " ".join([row.effective_comment, row.effective_suggested_text]).lower()
    ctype = row.comment_type

    def contains_any(keywords: tuple[str, ...]) -> bool:
        return any(k in content for k in keywords)

    if ctype == "Technical":
        return "Reject" if contains_any(("already addressed", "out of scope", "not applicable", "no change", "reject")) else "Accept"
    if ctype == "Clarification":
        return "Reject" if contains_any(("already clear", "sufficiently clear", "redundant", "misread")) else "Accept"
    if ctype == "Editorial/Grammar":
        return "Reject" if contains_any(("stet", "leave as is", "changes meaning")) else "Accept"

    return "Accept"


def draft_ntia_comments(row: ResolutionRow) -> str:
    if row.row_status == "Complete":
        return "Already completed."

    if row.disposition == "Accept":
        if row.effective_suggested_text:
            return "Accept. Issue noted and agency suggested text is incorporated with NTIA edits as needed."
        if row.effective_comment:
            return f"Accept. The comment identifies an issue to address: {row.effective_comment}"
        return "Accept. No additional detail provided; NTIA will refine text."

    if row.effective_comment:
        return f"Reject. Report already covers this point or no change is needed: {row.effective_comment}"
    return "Reject. No change to report text."


def draft_resolution(row: ResolutionRow) -> str:
    if row.row_status == "Complete":
        return row.existing_resolution or row.resolution or ""

    if row.disposition == "Reject":
        return row.existing_resolution or "No change to report text."

    if row.effective_suggested_text:
        return row.effective_suggested_text

    if row.effective_comment:
        if row.comment_type == "Clarification":
            return f"The report clarifies: {row.effective_comment}"
        if row.comment_type == "Editorial/Grammar":
            return f"Corrected wording: {row.effective_comment}"
        return f"The report now addresses: {row.effective_comment}"

    return row.existing_resolution or ""


def build_resolution_task(row: ResolutionRow) -> str:
    prefix = "Draft NTIA Comments, Comment Disposition (Accept/Reject), and Resolution text that can be inserted into the report."
    details = [
        f"Comment number: {row.comment_number or 'N/A'}.",
        f"Agency notes: {row.agency_notes or 'N/A'}.",
    ]
    if row.line_number:
        details.append(f"Line reference: {row.line_number}.")
    if row.agency_suggested_text:
        details.append("Agency provided suggested text.")
    if row.report_context:
        details.append("Report context available from PDF.")
    return " ".join([prefix, *details])
