from __future__ import annotations

from typing import Iterable, List

from .config import normalize_header
from .errors import CREError, ErrorCategory

# Canonical MVP spreadsheet contract (human-facing)
CANONICAL_SPREADSHEET_HEADERS: List[str] = [
    "Comment Number",
    "Reviewer Initials",
    "Agency",
    "Report Version",
    "Section",
    "Page",
    "Line",
    "Comment Type: Editorial/Grammar, Clarification, Technical",
    "Agency Notes",
    "Agency Suggested Text Change",
    "NTIA Comments",
    "Comment Disposition",
    "Resolution",
]

# Stable internal field names for the canonical headers
HEADER_TO_KEY = {
    "Comment Number": "comment_number",
    "Reviewer Initials": "reviewer_initials",
    "Agency": "agency",
    "Report Version": "report_version",
    "Section": "section",
    "Page": "page",
    "Line": "line",
    "Comment Type: Editorial/Grammar, Clarification, Technical": "comment_type",
    "Agency Notes": "agency_notes",
    "Agency Suggested Text Change": "agency_suggested_text",
    "NTIA Comments": "ntia_comments",
    "Comment Disposition": "comment_disposition",
    "Resolution": "resolution",
}

KEY_TO_HEADER = {v: k for k, v in HEADER_TO_KEY.items()}
CANONICAL_INTERNAL_ORDER: List[str] = [HEADER_TO_KEY[h] for h in CANONICAL_SPREADSHEET_HEADERS]


def normalize_label(label: str) -> str:
    return normalize_header(label)


def required_headers_missing(headers: Iterable[str]) -> List[str]:
    normalized = {normalize_label(col) for col in headers}
    missing = [header for header in CANONICAL_SPREADSHEET_HEADERS if normalize_label(header) not in normalized]
    return missing


def require_canonical_headers(headers: Iterable[str]) -> None:
    missing = required_headers_missing(headers)
    if missing:
        raise CREError(ErrorCategory.SCHEMA_ERROR, f"ERROR: Comments spreadsheet is missing required headers: {', '.join(missing)}")


def reorder_to_canonical(df, include_metadata: bool = False):
    """Return a copy ordered with canonical headers first, optionally appending remaining metadata columns."""
    try:
        import pandas as _pd  # noqa: F401
    except ModuleNotFoundError:
        return df

    require_canonical_headers(df.columns.tolist())
    canonical_headers = [col for col in CANONICAL_SPREADSHEET_HEADERS if col in df.columns]
    metadata_columns: List[str] = []
    if include_metadata:
        metadata_columns = [col for col in df.columns if col not in canonical_headers]
    ordered_columns = canonical_headers + metadata_columns
    return df.loc[:, ordered_columns]
