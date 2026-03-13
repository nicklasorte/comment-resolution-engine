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
            "Revision": ["rev1"],
        }
    )
    df.to_excel(comments, index=False)

    report = tmp_path / "report.txt"
    report.write_text("\n".join(["10 Intro text", "11 Lead-in", "12 Methodology limitations described here"]))

    output_path = tmp_path / "out.xlsx"
    out_df = run_pipeline(
        comments_path=comments,
        report_path=report,
        output_path=output_path,
        config_path=None,
    )

    assert "NTIA Comments" in out_df.columns
    assert "Comment Disposition" in out_df.columns
    assert "Resolution" in out_df.columns
    assert "Comment Cluster Id" in out_df.columns
    assert "Patch Text" in out_df.columns
    assert "Patch Source" in out_df.columns
    assert "Context Confidence" in out_df.columns
    assert "Resolution Basis" in out_df.columns
    assert "Validation Code" in out_df.columns
    assert "Shared Resolution Id" in out_df.columns
    assert "Validation Status" in out_df.columns
    assert "Revision" in out_df.columns
    assert out_df.iloc[0]["Comment Disposition"] in {"Accept", "Reject", "Partial Accept"}
    assert out_df.iloc[0]["Resolution"] != ""
    assert out_df.iloc[0]["Patch Text"] != ""
    assert (tmp_path / "out_patches.json").exists()
    assert (tmp_path / "out_faq.md").exists()
    assert (tmp_path / "out_section_summary.md").exists()
    assert (tmp_path / "out_briefing.md").exists()


def test_pipeline_requires_pdf(tmp_path: Path):
    comments = tmp_path / "comments.xlsx"
    df = pd.DataFrame(
        {
            "Comment Number": [1],
            "Agency Notes": ["Clarify methodology limitations"],
            "Comment Type: Editorial/Grammar, Clarification, Technical": ["Technical"],
            "Agency Suggested Text Change": ["The report now notes the limitations of the methodology."],
            "Line": ["12"],
            "Revision": ["rev1"],
        }
    )
    df.to_excel(comments, index=False)

    with pytest.raises(RuntimeError, match="ERROR: A working paper PDF is required"):
        run_pipeline(comments_path=comments, report_path=None, output_path=tmp_path / "out.xlsx", config_path=None)


def test_pipeline_rejects_missing_revision_column(tmp_path: Path):
    comments = tmp_path / "comments.xlsx"
    df = pd.DataFrame(
        {
            "Comment Number": [1],
            "Agency Notes": ["Clarify methodology limitations"],
        }
    )
    df.to_excel(comments, index=False)
    report = tmp_path / "report.txt"
    report.write_text("1 Sample line")

    with pytest.raises(RuntimeError, match="ERROR: Comments spreadsheet must contain a 'Revision' column"):
        run_pipeline(comments_path=comments, report_path=report, output_path=tmp_path / "out.xlsx", config_path=None)


def test_pipeline_errors_on_unknown_revision_reference(tmp_path: Path):
    comments = tmp_path / "comments.xlsx"
    df = pd.DataFrame(
        {
            "Comment Number": [1],
            "Agency Notes": ["Clarify methodology limitations"],
            "Comment Type: Editorial/Grammar, Clarification, Technical": ["Technical"],
            "Agency Suggested Text Change": ["The report now notes the limitations of the methodology."],
            "Line": ["12"],
            "Revision": ["rev2"],
        }
    )
    df.to_excel(comments, index=False)
    report = tmp_path / "report.txt"
    report.write_text("1 Sample line")

    with pytest.raises(RuntimeError, match="ERROR: Comment references revision 'rev2'"):
        run_pipeline(comments_path=comments, report_path=report, output_path=tmp_path / "out.xlsx", config_path=None)
