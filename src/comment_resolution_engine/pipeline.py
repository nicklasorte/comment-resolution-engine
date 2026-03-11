from __future__ import annotations

from pathlib import Path

from .config import load_column_mapping
from .excel_io import read_comment_matrix, write_resolution_workbook
from .pdf_utils import extract_pdf_text, extract_report_context
from .prompt_builder import build_resolution_task, classify_comment_type
from .resolver_schema import ResolutionRow


def _to_resolution_row(record: dict, pdf_text: str) -> ResolutionRow:
    row = ResolutionRow(
        comment_number=str(record.get("comment_number", "") or ""),
        comment=str(record.get("comment", "") or ""),
        line_number=str(record.get("line_number", "") or ""),
        existing_revision_notes=str(record.get("revision", "") or ""),
        status=str(record.get("status", "") or ""),
    )
    row.comment_type = classify_comment_type(row.comment)
    row.source_line_reference = row.line_number
    row.report_context = extract_report_context(row.line_number, pdf_text)
    row.row_status = "Complete" if row.status.strip().lower() in {"complete", "completed", "closed", "resolved"} else "Draft"
    row.proposed_report_text = ""
    row.insert_location = "Use line reference" if row.line_number else ("Identify section using report context" if row.report_context else "TBD")
    row.resolution_task = build_resolution_task(row)
    return row


def run_pipeline(comments_path: str | Path, report_path: str | Path | None, output_path: str | Path, config_path: str | Path | None = None):
    import pandas as pd

    mapping = load_column_mapping(config_path)
    comments_df = read_comment_matrix(comments_path, mapping)
    pdf_text = extract_pdf_text(report_path) if report_path else ""

    rows = [_to_resolution_row(rec, pdf_text=pdf_text) for rec in comments_df.to_dict(orient="records")]

    out_df = pd.DataFrame(
        {
            "Comment Number": [r.comment_number for r in rows],
            "Comment": [r.comment for r in rows],
            "Line Number": [r.line_number for r in rows],
            "Existing Revision Notes": [r.existing_revision_notes for r in rows],
            "Status": [r.row_status for r in rows],
            "Comment Type": [r.comment_type for r in rows],
            "Source Line Reference": [r.source_line_reference for r in rows],
            "Report Context": [r.report_context for r in rows],
            "Insert Location": [r.insert_location for r in rows],
            "Proposed Report Text": [r.proposed_report_text for r in rows],
            "Resolution Task": [r.resolution_task for r in rows],
        }
    )
    write_resolution_workbook(out_df, output_path)
    return out_df
