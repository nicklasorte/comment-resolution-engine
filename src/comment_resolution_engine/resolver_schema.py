from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ResolutionRow:
    comment_number: str = ""
    reviewer_initials: str = ""
    agency: str = ""
    report_version: str = ""
    section: str = ""
    page: str = ""
    line_number: str = ""
    comment_type: str = ""
    agency_notes: str = ""
    agency_suggested_text: str = ""
    status: str = ""
    ntia_comments: str = ""
    disposition: str = ""
    resolution: str = ""
    report_context: str = ""
    resolution_task: str = ""
    row_status: str = "Draft"
    effective_comment: str = ""
    effective_suggested_text: str = ""
    existing_ntia_comments: str = ""
    existing_disposition: str = ""
    existing_resolution: str = ""
