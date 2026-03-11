import pytest

pd = pytest.importorskip("pandas")

from comment_resolution_engine.config import load_column_mapping
from comment_resolution_engine.excel_io import normalize_comment_matrix


def test_normalize_comment_matrix_with_synonyms():
    mapping = load_column_mapping(None)
    source = pd.DataFrame(
        {
            "Cmt #": [1],
            "Agency Comment": ["Clarify assumptions"],
            "Line": ["102-105"],
            "Rev": ["Add assumption language"],
            "Resolution Status": ["Open"],
        }
    )

    out = normalize_comment_matrix(source, mapping)

    assert list(out.columns) == ["comment_number", "comment", "line_number", "revision", "status"]
    assert out.iloc[0]["comment_number"] == 1
    assert out.iloc[0]["line_number"] == "102-105"
