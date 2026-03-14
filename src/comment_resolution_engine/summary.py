from __future__ import annotations

from collections import Counter
from typing import Dict

import pandas as pd

from .pipeline_result import PipelineRunResult
from .spreadsheet_contract import HEADER_TO_KEY, MATRIX_CONTRACT, normalize_label


def _is_missing(value) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and pd.isna(value):
        return True
    text = str(value).strip()
    return text == "" or text.lower() == "nan"


def _resolve_column(df: pd.DataFrame, mapping, canonical_key: str | None) -> str | None:
    if not canonical_key:
        return None
    col = mapping.resolve_column_name(df.columns, canonical_key)
    return col if col in df.columns else None


def _counter(values) -> Dict[str, int]:
    counter = Counter()
    for value in values:
        label = str(value or "").strip() or "Unspecified"
        counter[label] += 1
    return dict(counter)


def build_summary(result: PipelineRunResult) -> Dict[str, object]:
    df = result.output_df
    raw_df = result.raw_df
    mapping = result.mapping

    disposition_key = HEADER_TO_KEY.get(MATRIX_CONTRACT.disposition_header, "comment_disposition")
    status_key = HEADER_TO_KEY.get(MATRIX_CONTRACT.status_header, "status")

    disposition_col = _resolve_column(df, mapping, disposition_key)
    status_col = _resolve_column(df, mapping, status_key)
    agency_col = _resolve_column(df, mapping, "agency")

    total_comments = len(df)
    disposition_values = (
        df[disposition_col].tolist() if disposition_col else [d.disposition for d in result.decisions]
    )
    counts_by_disposition = _counter(disposition_values)

    completed_comments = 0
    for idx in range(total_comments):
        status_value = df[status_col].iloc[idx] if status_col else ""
        disposition_value = (
            df[disposition_col].iloc[idx]
            if disposition_col
            else (result.decisions[idx].disposition if idx < len(result.decisions) else "")
        )
        if MATRIX_CONTRACT.row_status(status_value, disposition_value) == "Complete":
            completed_comments += 1
    comments_needing_response = max(total_comments - completed_comments, 0)

    reason_codes = []
    for decision in result.decisions:
        reason = decision.validation_code or decision.resolution_basis or ""
        reason_codes.append(reason or "unspecified")
    counts_by_reason_code = _counter(reason_codes)

    if agency_col:
        agency_counts = _counter(df[agency_col].tolist())
    else:
        agency_counts = _counter([c.agency for c in result.analyzed_comments])

    missing_field_count = 0
    for header in MATRIX_CONTRACT.required_headers:
        key = HEADER_TO_KEY.get(header) or normalize_label(header)
        col = _resolve_column(raw_df, mapping, key)
        if not col:
            missing_field_count += len(raw_df)
            continue
        series = raw_df[col]
        missing_field_count += int(series.apply(_is_missing).sum())

    duplicate_count = 0
    comment_key = "comment_number"
    comment_col = _resolve_column(raw_df, mapping, comment_key)
    if comment_col:
        normalized_ids = raw_df[comment_col].dropna().astype(str).str.strip()
        duplicate_count = int(len(normalized_ids) - normalized_ids.nunique())

    return {
        "total_comments": total_comments,
        "completed_comments": completed_comments,
        "comments_needing_response": comments_needing_response,
        "counts_by_disposition": counts_by_disposition,
        "counts_by_reason_code": counts_by_reason_code,
        "counts_by_source_agency": agency_counts,
        "missing_field_count": int(missing_field_count),
        "duplicate_comment_id_count": duplicate_count,
    }
