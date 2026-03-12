from __future__ import annotations

from dataclasses import asdict
from typing import Iterable, List

from ..config import ColumnMappingConfig, normalize_header
from ..models import CommentRecord


CANONICAL_COLUMNS = [
    "comment_number",
    "reviewer_initials",
    "agency",
    "report_version",
    "section",
    "page",
    "line",
    "line_number",
    "comment_type",
    "agency_notes",
    "agency_suggested_text",
    "wg_chain_comments",
    "comment_disposition",
    "resolution",
]


def _require_pandas():
    try:
        import pandas as pd
    except ModuleNotFoundError as exc:
        raise RuntimeError("pandas is required for Excel processing. Install dependencies with `pip install -r requirements.txt`.") from exc
    return pd


def _build_header_lookup(columns: Iterable[str]) -> dict[str, str]:
    return {normalize_header(col): col for col in columns}


def _to_int(value) -> int | None:
    try:
        if value is None or (isinstance(value, float) and value != value):
            return None
        text = str(value).strip()
        if not text:
            return None
        return int(float(text))
    except (TypeError, ValueError):
        return None


def _extract_value(row, lookup: dict[str, str], mapping: ColumnMappingConfig, canonical_key: str) -> str:
    for variant in mapping.all_variants(canonical_key):
        raw_name = lookup.get(variant)
        if raw_name is not None and raw_name in row:
            return row.get(raw_name, "")
    return ""


def read_comment_matrix(path: str, mapping: ColumnMappingConfig) -> tuple[list[CommentRecord], "pd.DataFrame", "pd.DataFrame"]:
    pd = _require_pandas()
    df = pd.read_excel(path)
    lookup = _build_header_lookup(df.columns.tolist())

    records: List[CommentRecord] = []
    for idx, row in df.iterrows():
        data = {canonical: _extract_value(row, lookup, mapping, canonical) for canonical in CANONICAL_COLUMNS}

        records.append(
            CommentRecord(
                id=str(data.get("comment_number") or idx + 1),
                reviewer_initials=str(data.get("reviewer_initials") or "").strip(),
                agency=str(data.get("agency") or "").strip(),
                report_version=str(data.get("report_version") or "").strip(),
                section=str(data.get("section") or "").strip(),
                page=_to_int(data.get("page")),
                line=_to_int(data.get("line")) or _to_int(data.get("line_number")),
                comment_type=str(data.get("comment_type") or "").strip(),
                agency_notes=str(data.get("agency_notes") or "").strip(),
                agency_suggested_text=str(data.get("agency_suggested_text") or "").strip(),
                wg_chain_comments=str(data.get("wg_chain_comments") or "").strip(),
                comment_disposition=str(data.get("comment_disposition") or data.get("disposition") or "").strip(),
                resolution=str(data.get("resolution") or "").strip(),
                raw_row=row.to_dict(),
            )
        )

    normalized_df = pd.DataFrame([asdict(r) for r in records])
    return records, normalized_df, df
