import pytest

pd = pytest.importorskip("pandas")

from comment_resolution_engine.config import load_column_mapping
from comment_resolution_engine.excel_io import CANONICAL_COLUMNS, normalize_comment_matrix


def test_normalize_comment_matrix_with_synonyms():
    mapping = load_column_mapping(None)
    source = pd.DataFrame(
        {
            "Cmt #": [1],
            "Reviewer Comment": ["Clarify assumptions"],
            "Line": ["102-105"],
            "Suggested Text": ["Add assumption language"],
            "Resolution Status": ["Open"],
            "Category": ["technical"],
            "Internal Comments": ["Existing note"],
            "Accept/Reject": ["Reject"],
            "Proposed Resolution": ["No change"],
            "Revision": ["rev1"],
        }
    )

    out = normalize_comment_matrix(source, mapping)

    assert list(out.columns) == CANONICAL_COLUMNS
    assert out.iloc[0]["comment_number"] == 1
    assert out.iloc[0]["line"] == "102-105"
    assert out.iloc[0]["agency_notes"] == "Clarify assumptions"
    assert out.iloc[0]["agency_suggested_text"] == "Add assumption language"
    assert out.iloc[0]["status"] == "Open"
    assert out.iloc[0]["disposition"] == "Reject"
    assert out.iloc[0]["revision"] == "rev1"
