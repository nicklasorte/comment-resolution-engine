from __future__ import annotations

from dataclasses import asdict
from typing import Iterable, List

from ..errors import CREError, ErrorCategory

from ..config import ColumnMappingConfig, normalize_header
from ..spreadsheet_contract import CANONICAL_INTERNAL_ORDER, require_canonical_headers
from ..models import CommentRecord


OPTIONAL_COLUMNS = [
    "revision",
    "line_number",
    "wg_chain_comments",
]


def _require_pandas():
    try:
        import pandas as pd
    except ModuleNotFoundError as exc:
        raise CREError(ErrorCategory.EXTRACTION_ERROR, "pandas is required for Excel processing. Install dependencies with `pip install -r requirements.txt`.") from exc
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


def _clean_str(value) -> str:
    text = "" if value is None else str(value).strip()
    return "" if text.lower() in {"nan", "none"} else text


def _extract_value(row, lookup: dict[str, str], mapping: ColumnMappingConfig, canonical_key: str) -> str:
    for variant in mapping.all_variants(canonical_key):
        raw_name = lookup.get(variant)
        if raw_name is not None and raw_name in row:
            return row.get(raw_name, "")
    return ""


def read_comment_matrix(path: str, mapping: ColumnMappingConfig) -> tuple[list[CommentRecord], "pd.DataFrame", "pd.DataFrame"]:
    pd = _require_pandas()
    path_str = str(path)
    if path_str.lower().endswith(".csv"):
        df = pd.read_csv(path_str)
    else:
        df = pd.read_excel(path_str)
    lookup = _build_header_lookup(df.columns.tolist())
    require_canonical_headers(df.columns.tolist())

    records: List[CommentRecord] = []
    for idx, row in df.iterrows():
        data = {canonical: _extract_value(row, lookup, mapping, canonical) for canonical in [*CANONICAL_INTERNAL_ORDER, *OPTIONAL_COLUMNS]}
        revision_value = _clean_str(data.get("revision")) or _clean_str(data.get("report_version"))

        records.append(
            CommentRecord(
                id=str(data.get("comment_number") or idx + 1),
                reviewer_initials=_clean_str(data.get("reviewer_initials")),
                agency=_clean_str(data.get("agency")),
                revision=revision_value,
                report_version=_clean_str(data.get("report_version")),
                section=_clean_str(data.get("section")),
                page=_to_int(data.get("page")),
                line=_to_int(data.get("line")) or _to_int(data.get("line_number")),
                comment_type=_clean_str(data.get("comment_type")),
                agency_notes=_clean_str(data.get("agency_notes")),
                agency_suggested_text=_clean_str(data.get("agency_suggested_text")),
                wg_chain_comments=_clean_str(data.get("wg_chain_comments")),
                comment_disposition=_clean_str(data.get("comment_disposition") or data.get("disposition")),
                resolution=_clean_str(data.get("resolution")),
                raw_row=row.to_dict(),
            )
        )

    normalized_df = pd.DataFrame([asdict(r) for r in records])
    return records, normalized_df, df
