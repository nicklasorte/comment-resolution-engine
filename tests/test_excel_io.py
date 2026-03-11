from pathlib import Path

import pytest

pd = pytest.importorskip("pandas")
pytest.importorskip("openpyxl")
from openpyxl import load_workbook

from comment_resolution_engine.excel_io import write_resolution_workbook


def test_write_resolution_workbook_formats_sheet(tmp_path: Path):
    output = tmp_path / "out.xlsx"
    df = pd.DataFrame(
        {
            "Comment Number": ["1"],
            "Comment": ["Clarify assumptions"],
            "Line Number": ["33"],
            "Existing Revision Notes": ["Update assumptions section"],
            "Status": ["Draft"],
            "Comment Type": ["Assumption"],
            "Source Line Reference": ["33"],
            "Report Context": ["L33: Existing report language."],
            "Insert Location": ["Sec 2"],
            "Proposed Report Text": [""],
            "Resolution Task": ["Write 1-3 sentences..."],
        }
    )

    write_resolution_workbook(df, output)

    wb = load_workbook(output)
    ws = wb.active
    assert ws.freeze_panes == "A2"
    assert ws.auto_filter.ref is not None
    assert ws["D1"].value == "Existing Revision Notes"
    assert ws["H2"].alignment.wrap_text is True
