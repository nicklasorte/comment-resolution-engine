from __future__ import annotations

from pathlib import Path

from .config import load_column_mapping
from .excel_io import normalize_comment_matrix, write_resolution_workbook
from .pdf_utils import extract_pdf_text, extract_report_context
from .prompt_builder import (
    build_resolution_task,
    determine_accept_reject,
    draft_ntia_comments,
    draft_resolution,
    extract_effective_comment,
    extract_effective_suggested_text,
    normalize_comment_type,
)
from .resolver_schema import ResolutionRow


def _row_status(status: str) -> str:
    status_text = (status or "").strip().lower()
    return "Complete" if status_text in {"complete", "completed", "closed", "resolved", "done"} else "Draft"


def _prepare_rows(normalized_df, raw_df, pdf_text: str):
    rows: list[ResolutionRow] = []
    for idx, record in enumerate(normalized_df.to_dict(orient="records")):
        row = ResolutionRow(
            comment_number=str(record.get("comment_number", "") or ""),
            reviewer_initials=str(record.get("reviewer_initials", "") or ""),
            agency=str(record.get("agency", "") or ""),
            report_version=str(record.get("report_version", "") or ""),
            section=str(record.get("section", "") or ""),
            page=str(record.get("page", "") or ""),
            line_number=str(record.get("line_number", "") or ""),
            comment_type=str(record.get("comment_type", "") or ""),
            agency_notes=str(record.get("agency_notes", "") or ""),
            agency_suggested_text=str(record.get("agency_suggested_text", "") or ""),
            status=str(record.get("status", "") or ""),
            existing_ntia_comments=str(record.get("ntia_comments", "") or ""),
            existing_disposition=str(record.get("disposition", "") or ""),
            existing_resolution=str(record.get("resolution", "") or ""),
        )

        row.row_status = _row_status(row.status)
        row.comment_type = normalize_comment_type(row.comment_type) or normalize_comment_type(row.agency_notes) or normalize_comment_type(row.agency_suggested_text) or "Clarification"
        row.effective_comment = extract_effective_comment(row.agency_notes, row.agency_suggested_text)
        row.effective_suggested_text = extract_effective_suggested_text(row.agency_suggested_text)

        if pdf_text:
            row.report_context = extract_report_context(row.line_number, pdf_text) or "Report context not available from provided PDF excerpt."
        else:
            row.report_context = ""

        row.disposition = row.existing_disposition or determine_accept_reject(row)
        row.ntia_comments = row.existing_ntia_comments or draft_ntia_comments(row)
        row.resolution = row.existing_resolution or draft_resolution(row)
        row.resolution_task = build_resolution_task(row)
        rows.append(row)
    return rows


def run_pipeline(comments_path: str | Path, report_path: str | Path | None, output_path: str | Path, config_path: str | Path | None = None):
    import pandas as pd

    mapping = load_column_mapping(config_path)
    pd_mod = pd

    raw_df = pd_mod.read_excel(comments_path)
    normalized_df = normalize_comment_matrix(raw_df, mapping)
    pdf_text = extract_pdf_text(report_path) if report_path else ""

    rows = _prepare_rows(normalized_df, raw_df, pdf_text)

    output_df = raw_df.copy()

    def _series(values: list[str]):
        return pd_mod.Series([str(v) if v is not None else "" for v in values], index=output_df.index)

    def _set_column(canonical_key: str, values: list[str], always_override: bool = False):
        col_name = mapping.resolve_column_name(output_df.columns, canonical_key)
        series = _series(values)
        if always_override or col_name not in output_df.columns:
            output_df[col_name] = series
            return

        existing = output_df[col_name]
        existing_str = existing.where(existing.notna(), "").astype(str).replace("nan", "")
        output_df[col_name] = existing_str.where(existing_str.str.strip() != "", series)

    # Ensure baseline columns exist (preserve existing values when present)
    _set_column("comment_number", [r.comment_number for r in rows], always_override=False)
    _set_column("reviewer_initials", [r.reviewer_initials for r in rows], always_override=False)
    _set_column("agency", [r.agency for r in rows], always_override=False)
    _set_column("report_version", [r.report_version for r in rows], always_override=False)
    _set_column("section", [r.section for r in rows], always_override=False)
    _set_column("page", [r.page for r in rows], always_override=False)
    _set_column("line_number", [r.line_number for r in rows], always_override=False)
    _set_column("comment_type", [r.comment_type for r in rows], always_override=True)
    _set_column("agency_notes", [r.agency_notes for r in rows], always_override=False)
    _set_column("agency_suggested_text", [r.agency_suggested_text for r in rows], always_override=False)

    # Primary outputs
    _set_column("ntia_comments", [r.ntia_comments for r in rows], always_override=True)
    _set_column("disposition", [r.disposition for r in rows], always_override=True)
    _set_column("resolution", [r.resolution for r in rows], always_override=True)
    _set_column("report_context", [r.report_context for r in rows], always_override=True)
    _set_column("resolution_task", [r.resolution_task for r in rows], always_override=True)

    write_resolution_workbook(output_df, output_path)
    return output_df
