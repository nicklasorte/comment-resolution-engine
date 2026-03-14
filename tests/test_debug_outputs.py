import json
from pathlib import Path

import pytest

pd = pytest.importorskip("pandas")

from comment_resolution_engine.pipeline import run_pipeline


def test_run_pipeline_emits_debug_json(tmp_path: Path):
    comments = tmp_path / "comments.xlsx"
    df = pd.DataFrame(
        {
            "Comment Number": [1],
            "Report Version": ["rev1"],
            "Reviewer Initials": ["AB"],
            "Agency": ["NTIA"],
            "Section": ["2.1"],
            "Page": ["1"],
            "Line": ["12"],
            "Comment Type: Editorial/Grammar, Clarification, Technical": ["Editorial/Grammar"],
            "Agency Notes": ["Fix punctuation in the summary paragraph."],
            "Agency Suggested Text Change": ["Correct punctuation."],
            "NTIA Comments": [""],
            "Comment Disposition": [""],
            "Resolution": [""],
            "Status": [""],
        }
    )
    df.to_excel(comments, index=False)

    report = tmp_path / "report.txt"
    report.write_text("1 Sample line")

    debug_path = tmp_path / "out_debug.json"
    output_path = tmp_path / "out.xlsx"
    out_df = run_pipeline(comments_path=comments, report_path=report, output_path=output_path, config_path=None, debug_output=debug_path)

    assert debug_path.exists()
    payload = json.loads(debug_path.read_text())
    assert payload and payload[0]["reason_code"]
    assert payload[0]["response_text"]
    assert out_df.iloc[0]["Comment Disposition"] in {"Accept", "Reject", "Partial Accept"}


def test_completed_row_keeps_resolution_and_reason(tmp_path: Path):
    comments = tmp_path / "comments.xlsx"
    df = pd.DataFrame(
        {
            "Comment Number": [1],
            "Report Version": ["rev1"],
            "Reviewer Initials": ["AB"],
            "Agency": ["NTIA"],
            "Section": ["1.1"],
            "Page": ["1"],
            "Line": ["2"],
            "Comment Type: Editorial/Grammar, Clarification, Technical": ["Editorial"],
            "Agency Notes": ["Completed earlier."],
            "Agency Suggested Text Change": [""],
            "NTIA Comments": [""],
            "Comment Disposition": ["Completed"],
            "Resolution": ["Existing resolution"],
            "Status": ["Completed"],
        }
    )
    df.to_excel(comments, index=False)
    report = tmp_path / "report.txt"
    report.write_text("1 Sample line")

    debug_path = tmp_path / "completed_debug.json"
    output_path = tmp_path / "out.xlsx"
    out_df = run_pipeline(comments_path=comments, report_path=report, output_path=output_path, config_path=None, debug_output=debug_path)

    payload = json.loads(debug_path.read_text())
    assert payload[0]["reason_code"] == "NO_CHANGE_NEEDED"
    assert payload[0]["response_text"] == "Existing resolution"
    assert out_df.iloc[0]["Resolution"] == "Existing resolution"
