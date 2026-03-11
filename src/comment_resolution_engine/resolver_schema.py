from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ResolutionRow:
    comment_number: str
    comment: str
    line_number: str = ""
    existing_revision_notes: str = ""
    status: str = ""
    source_line_reference: str = ""
    comment_type: str = ""
    report_context: str = ""
    insert_location: str = ""
    proposed_report_text: str = ""
    row_status: str = "Draft"
    resolution_task: str = ""
