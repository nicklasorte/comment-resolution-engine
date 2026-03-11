from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .config import ColumnMappingConfig, normalize_header

if TYPE_CHECKING:
    import pandas as pd

CANONICAL_COLUMNS = ["comment_number", "comment", "line_number", "revision", "status"]
OUTPUT_COLUMNS = [
    "Comment Number",
    "Comment",
    "Line Number",
    "Existing Revision Notes",
    "Status",
    "Comment Type",
    "Source Line Reference",
    "Report Context",
    "Insert Location",
    "Proposed Report Text",
    "Resolution Task",
]


def _require_pandas():
    try:
        import pandas as pd
    except ModuleNotFoundError as exc:
        raise RuntimeError("pandas is required for Excel processing. Install dependencies with `pip install -r requirements.txt`.") from exc
    return pd


def _require_openpyxl():
    try:
        from openpyxl import load_workbook
        from openpyxl.styles import Alignment, Font
    except ModuleNotFoundError as exc:
        raise RuntimeError("openpyxl is required for Excel formatting. Install dependencies with `pip install -r requirements.txt`.") from exc
    return load_workbook, Alignment, Font


def _build_header_lookup(columns: list[str]) -> dict[str, str]:
    return {normalize_header(col): col for col in columns}


def normalize_comment_matrix(df: "pd.DataFrame", mapping: ColumnMappingConfig) -> "pd.DataFrame":
    pd = _require_pandas()
    lookup = _build_header_lookup(df.columns.tolist())
    normalized = {}

    for canonical in CANONICAL_COLUMNS:
        raw_column_name = ""
        for variant in mapping.all_variants(canonical):
            if variant in lookup:
                raw_column_name = lookup[variant]
                break
        normalized[canonical] = df[raw_column_name] if raw_column_name else ""

    out_df = pd.DataFrame(normalized)
    return out_df.fillna("")


def read_comment_matrix(path: str | Path, mapping: ColumnMappingConfig):
    pd = _require_pandas()
    df = pd.read_excel(path)
    return normalize_comment_matrix(df, mapping)


def write_resolution_workbook(df, output_path: str | Path) -> None:
    load_workbook, Alignment, Font = _require_openpyxl()

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    ordered = df.reindex(columns=OUTPUT_COLUMNS)
    ordered.to_excel(output, index=False)

    wb = load_workbook(output)
    ws = wb.active
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions

    widths = {"A": 16, "B": 45, "C": 14, "D": 30, "E": 14, "F": 16, "G": 22, "H": 55, "I": 22, "J": 55, "K": 70}
    for col, width in widths.items():
        ws.column_dimensions[col].width = width

    wrap_cols = {"B", "D", "H", "J", "K"}
    for row in ws.iter_rows(min_row=1, max_row=ws.max_row, min_col=1, max_col=ws.max_column):
        for cell in row:
            if cell.row == 1:
                cell.font = Font(bold=True)
            cell.alignment = Alignment(vertical="top", wrap_text=cell.column_letter in wrap_cols)

    wb.save(output)
