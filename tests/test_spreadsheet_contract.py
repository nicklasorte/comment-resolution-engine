from pathlib import Path

import pytest

pd = pytest.importorskip("pandas")

from comment_resolution_engine.config import load_column_mapping
from comment_resolution_engine.errors import CREError, ErrorCategory
from comment_resolution_engine.ingest import read_comment_matrix
from comment_resolution_engine.spreadsheet_contract import CANONICAL_SPREADSHEET_HEADERS


def _base_row() -> dict:
    return {
        "Comment Number": [1],
        "Reviewer Initials": ["AB"],
        "Agency": ["NTIA"],
        "Report Version": ["rev1"],
        "Section": ["1.1"],
        "Page": ["1"],
        "Line": ["5"],
        "Comment Type: Editorial/Grammar, Clarification, Technical": ["Technical"],
        "Agency Notes": ["Test note"],
        "Agency Suggested Text Change": ["Suggested"],
        "NTIA Comments": [""],
        "Comment Disposition": [""],
        "Resolution": [""],
    }


def test_import_accepts_canonical_headers(tmp_path: Path):
    path = tmp_path / "matrix.xlsx"
    df = pd.DataFrame(_base_row())
    df.to_excel(path, index=False)

    mapping = load_column_mapping(None)
    records, normalized_df, raw_df = read_comment_matrix(str(path), mapping)

    assert len(records) == 1
    assert records[0].report_version == "rev1"
    assert list(raw_df.columns) == CANONICAL_SPREADSHEET_HEADERS
    assert not normalized_df.isnull().any().any()


def test_import_rejects_missing_required_header(tmp_path: Path):
    path = tmp_path / "matrix.xlsx"
    row = _base_row()
    row.pop("Agency")
    pd.DataFrame(row).to_excel(path, index=False)

    with pytest.raises(CREError) as exc:
        read_comment_matrix(str(path), load_column_mapping(None))
    assert exc.value.category == ErrorCategory.SCHEMA_ERROR
    assert "Agency" in str(exc.value)
