from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List

import pandas as pd

from ..config import ColumnMappingConfig, DEFAULT_MAPPING
from .scoring import CommentExpectation


def _normalize(value) -> str:
    if value is None:
        return ""
    text = str(value)
    if text.lower() in {"nan", "none"}:
        return ""
    return text.strip()


def _column(df: pd.DataFrame, mapping: ColumnMappingConfig, key: str) -> str | None:
    name = mapping.resolve_column_name(df.columns, key)
    return name if name in df.columns else None


def _row_needs_review(row: pd.Series, expected: CommentExpectation | None, mapping: ColumnMappingConfig) -> List[str]:
    reasons: List[str] = []

    validation_col = _column(row.to_frame().T, mapping, "validation_status")
    context_col = _column(row.to_frame().T, mapping, "report_context")
    context_confidence_col = _column(row.to_frame().T, mapping, "context_confidence")
    resolution_col = _column(row.to_frame().T, mapping, "resolution")
    ntia_col = _column(row.to_frame().T, mapping, "ntia_comments")
    comment_type_col = _column(row.to_frame().T, mapping, "comment_type")

    validation_status = _normalize(row.get(validation_col)) if validation_col else ""
    context_text = _normalize(row.get(context_col)) if context_col else ""
    context_confidence = _normalize(row.get(context_confidence_col)) if context_confidence_col else ""
    resolution = _normalize(row.get(resolution_col)) if resolution_col else ""
    ntia = _normalize(row.get(ntia_col)) if ntia_col else ""
    comment_type = _normalize(row.get(comment_type_col)) if comment_type_col else ""

    if validation_status and validation_status.upper() not in {"PASS"}:
        reasons.append(f"validation_status={validation_status}")
    if expected and expected.requires_context and not context_text:
        reasons.append("missing_required_context")
    if comment_type.upper() == "TECHNICAL" and context_confidence in {"NO_CONTEXT_FOUND"}:
        reasons.append("technical_no_context")
    if expected and expected.require_resolution and not resolution:
        reasons.append("missing_resolution_text")
    if expected and expected.require_ntia_comment and not ntia:
        reasons.append("missing_ntia_comment")

    return reasons


def build_adjudication_queue(
    output_df: pd.DataFrame,
    expectations: dict[str, CommentExpectation],
    mapping: ColumnMappingConfig = DEFAULT_MAPPING,
) -> list[dict]:
    queue: list[dict] = []
    id_col = mapping.resolve_column_name(output_df.columns, "comment_number")
    disposition_col = mapping.resolve_column_name(output_df.columns, "disposition")
    intent_col = mapping.resolve_column_name(output_df.columns, "intent_classification")
    section_col = mapping.resolve_column_name(output_df.columns, "section_group")
    validation_col = mapping.resolve_column_name(output_df.columns, "validation_status")

    for _, row in output_df.iterrows():
        cid = _normalize(row.get(id_col))
        exp = expectations.get(cid)
        reasons = _row_needs_review(row, exp, mapping)
        if exp and exp.requires_human_review and "requires_human_review" not in reasons:
            reasons.append("marked_in_expectations")
        if reasons:
            queue.append(
                {
                    "comment_id": cid,
                    "disposition": _normalize(row.get(disposition_col)),
                    "intent_classification": _normalize(row.get(intent_col)),
                    "section_group": _normalize(row.get(section_col)),
                    "validation_status": _normalize(row.get(validation_col)),
                    "reasons": reasons,
                }
            )
    return queue


def export_queue(queue: Iterable[dict], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(list(queue), indent=2))
    return output_path
