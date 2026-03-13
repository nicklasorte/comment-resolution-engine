from pathlib import Path

import pytest

pd = pytest.importorskip("pandas")

from comment_resolution_engine.pipeline import run_pipeline
from comment_resolution_engine.errors import CREError, ErrorCategory


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
    assert "Resolved Against Revision" in out_df.columns
    assert "Generation Mode" in out_df.columns
    assert "Review Status" in out_df.columns
    assert "Confidence Score" in out_df.columns
    assert "Provenance Record Id" in out_df.columns
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

    with pytest.raises(CREError) as exc:
        run_pipeline(comments_path=comments, report_path=None, output_path=tmp_path / "out.xlsx", config_path=None)
    assert exc.value.category == ErrorCategory.PROVENANCE_ERROR
    assert "working paper PDF is required" in str(exc.value)


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

    with pytest.raises(CREError) as exc:
        run_pipeline(comments_path=comments, report_path=report, output_path=tmp_path / "out.xlsx", config_path=None)
    assert exc.value.category == ErrorCategory.SCHEMA_ERROR
    assert "Revision" in str(exc.value)


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

    with pytest.raises(CREError) as exc:
        run_pipeline(comments_path=comments, report_path=report, output_path=tmp_path / "out.xlsx", config_path=None)
    assert exc.value.category == ErrorCategory.PROVENANCE_ERROR
    assert "rev2" in str(exc.value)


def test_pipeline_maps_blank_revision_to_single_pdf(tmp_path: Path):
    comments = tmp_path / "comments.xlsx"
    df = pd.DataFrame(
        {
            "Comment Number": [1],
            "Agency Notes": ["Clarify methodology limitations"],
            "Comment Type: Editorial/Grammar, Clarification, Technical": ["Technical"],
            "Agency Suggested Text Change": ["The report now notes the limitations of the methodology."],
            "Line": ["12"],
            "Revision": [""],
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
    assert "Resolved Against Revision" in out_df.columns
    assert out_df.iloc[0]["Resolved Against Revision"] == "rev1"
    provenance = (tmp_path / "out_provenance.json").read_text()
    assert "record_id" in provenance
    assert "generated_by_system" in provenance


def test_pipeline_requires_revision_when_multiple_reports(tmp_path: Path):
    comments = tmp_path / "comments.xlsx"
    df = pd.DataFrame(
        {
            "Comment Number": [1],
            "Agency Notes": ["Clarify methodology limitations"],
            "Comment Type: Editorial/Grammar, Clarification, Technical": ["Technical"],
            "Agency Suggested Text Change": ["The report now notes the limitations of the methodology."],
            "Line": ["12"],
            "Revision": [""],
        }
    )
    df.to_excel(comments, index=False)

    report1 = tmp_path / "report1.txt"
    report2 = tmp_path / "report2.txt"
    report1.write_text("Line 1 text")
    report2.write_text("Line 2 text")

    with pytest.raises(CREError) as exc:
        run_pipeline(comments_path=comments, report_path=[report1, report2], output_path=tmp_path / "out.xlsx", config_path=None)
    assert exc.value.category == ErrorCategory.VALIDATION_ERROR
    assert "Revision" in str(exc.value)


def test_pipeline_writes_provenance_metadata(tmp_path: Path):
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

    provenance_path = tmp_path / "out_provenance.json"
    assert provenance_path.exists()
    provenance = pd.read_json(provenance_path)
    assert {"record_id", "record_type", "source_document", "resolved_against_revision", "workflow_name", "review_status", "confidence_score"}.issubset(
        set(provenance.columns)
    )
    assert out_df.iloc[0]["Provenance Record Id"] in provenance["record_id"].tolist()
