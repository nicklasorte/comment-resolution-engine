from pathlib import Path

import pytest

pd = pytest.importorskip("pandas")

from comment_resolution_engine.pipeline import run_pipeline


def test_pipeline_outputs_disposition_and_resolution(tmp_path: Path):
    comments = tmp_path / "comments.xlsx"
    df = pd.DataFrame(
        {
            "Comment Number": [1],
            "Agency Notes": ["Clarify methodology limitations"],
            "Comment Type: Editorial/Grammar, Clarification, Technical": ["Technical"],
            "Agency Suggested Text Change": ["The report now notes the limitations of the methodology."],
            "Line": ["12"],
        }
    )
    df.to_excel(comments, index=False)

    output_path = tmp_path / "out.xlsx"
    out_df = run_pipeline(
        comments_path=comments,
        report_path=None,
        output_path=output_path,
        config_path=None,
    )

    assert "NTIA Comments" in out_df.columns
    assert "Comment Disposition" in out_df.columns
    assert "Resolution" in out_df.columns
    assert "Comment Cluster Id" in out_df.columns
    assert "Validation Status" in out_df.columns
    assert out_df.iloc[0]["Comment Disposition"] in {"Accept", "Reject"}
    assert out_df.iloc[0]["Resolution"] != ""
    assert (tmp_path / "out_patches.json").exists()
    assert (tmp_path / "out_faq.md").exists()
    assert (tmp_path / "out_section_summary.md").exists()
    assert (tmp_path / "out_briefing.md").exists()
