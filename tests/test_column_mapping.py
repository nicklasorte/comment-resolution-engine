import pytest

pd = pytest.importorskip("pandas")

from comment_resolution_engine.config import load_column_mapping
from comment_resolution_engine.excel_io import OPTIONAL_INTERNAL_COLUMNS, normalize_comment_matrix
from comment_resolution_engine.spreadsheet_contract import CANONICAL_INTERNAL_ORDER


def test_normalize_comment_matrix_with_synonyms():
    mapping = load_column_mapping(None)
    source = pd.DataFrame(
        {
            "Comment Number": [1],
            "Reviewer Initials": ["JD"],
            "Agency": ["NTIA"],
            "Report Version": ["rev1"],
            "Section": ["2.1"],
            "Page": ["1"],
            "Line": ["102-105"],
            "Comment Type: Editorial/Grammar, Clarification, Technical": ["Technical"],
            "Agency Notes": ["Clarify assumptions"],
            "Agency Suggested Text Change": ["Add assumption language"],
            "NTIA Comments": [""],
            "Comment Disposition": [""],
            "Resolution": [""],
        }
    )

    out = normalize_comment_matrix(source, mapping)

    expected_columns = [*CANONICAL_INTERNAL_ORDER, *OPTIONAL_INTERNAL_COLUMNS]
    assert list(out.columns) == expected_columns
    assert out.iloc[0]["comment_number"] == 1
    assert out.iloc[0]["line"] == "102-105"
    assert out.iloc[0]["agency_notes"] == "Clarify assumptions"
    assert out.iloc[0]["agency_suggested_text"] == "Add assumption language"
    assert out.iloc[0]["report_version"] == "rev1"
