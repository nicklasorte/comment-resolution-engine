import json
from pathlib import Path

import pytest

pd = pytest.importorskip("pandas")

from comment_resolution_engine.pipeline import run_pipeline
from comment_resolution_engine.errors import CREError, ErrorCategory
from comment_resolution_engine.spreadsheet_contract import CANONICAL_SPREADSHEET_HEADERS


def test_pipeline_outputs_disposition_and_resolution(tmp_path: Path):
    comments = tmp_path / "comments.xlsx"
    df = pd.DataFrame(
        {
            "Comment Number": [1],
            "Report Version": ["rev1"],
            "Reviewer Initials": ["AB"],
            "Agency": ["NTIA"],
            "Section": ["2.1"],
            "Page": ["1"],
            "Agency Notes": ["Clarify methodology limitations"],
            "Comment Type: Editorial/Grammar, Clarification, Technical": ["Technical"],
            "Agency Suggested Text Change": ["The report now notes the limitations of the methodology."],
            "Line": ["12"],
            "NTIA Comments": [""],
            "Comment Disposition": [""],
            "Resolution": [""],
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

    assert list(out_df.columns) == CANONICAL_SPREADSHEET_HEADERS
    assert out_df.iloc[0]["Comment Disposition"] in {"Accept", "Reject", "Partial Accept"}
    assert out_df.iloc[0]["Resolution"] != ""
    assert (tmp_path / "out_patches.json").exists()
    assert (tmp_path / "out_faq.md").exists()
    assert (tmp_path / "out_section_summary.md").exists()
    assert (tmp_path / "out_briefing.md").exists()
    # Optional metadata should stay off the visible matrix by default
    assert "Provenance Record Id" not in out_df.columns


def test_pipeline_requires_pdf(tmp_path: Path):
    comments = tmp_path / "comments.xlsx"
    df = pd.DataFrame(
        {
            "Comment Number": [1],
            "Report Version": ["rev1"],
            "Reviewer Initials": ["AB"],
            "Agency": ["NTIA"],
            "Section": ["2.1"],
            "Page": ["1"],
            "Agency Notes": ["Clarify methodology limitations"],
            "Comment Type: Editorial/Grammar, Clarification, Technical": ["Technical"],
            "Agency Suggested Text Change": ["The report now notes the limitations of the methodology."],
            "Line": ["12"],
            "NTIA Comments": [""],
            "Comment Disposition": [""],
            "Resolution": [""],
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
    assert "Report Version" in str(exc.value)


def test_pipeline_errors_on_unknown_revision_reference(tmp_path: Path):
    comments = tmp_path / "comments.xlsx"
    df = pd.DataFrame(
        {
            "Comment Number": [1],
            "Report Version": ["rev2"],
            "Reviewer Initials": ["AB"],
            "Agency": ["NTIA"],
            "Section": ["2.1"],
            "Page": ["1"],
            "Agency Notes": ["Clarify methodology limitations"],
            "Comment Type: Editorial/Grammar, Clarification, Technical": ["Technical"],
            "Agency Suggested Text Change": ["The report now notes the limitations of the methodology."],
            "Line": ["12"],
            "NTIA Comments": [""],
            "Comment Disposition": [""],
            "Resolution": [""],
        }
    )
    df.to_excel(comments, index=False)
    report = tmp_path / "report.txt"
    report.write_text("1 Sample line")

    with pytest.raises(CREError) as exc:
        run_pipeline(comments_path=comments, report_path=report, output_path=tmp_path / "out.xlsx", config_path=None)
    assert exc.value.category == ErrorCategory.PROVENANCE_ERROR
    assert "report version 'rev2'" in str(exc.value)


def test_pipeline_maps_blank_revision_to_single_pdf(tmp_path: Path):
    comments = tmp_path / "comments.xlsx"
    df = pd.DataFrame(
        {
            "Comment Number": [1],
            "Report Version": [""],
            "Reviewer Initials": ["AB"],
            "Agency": ["NTIA"],
            "Section": ["2.1"],
            "Page": ["1"],
            "Agency Notes": ["Clarify methodology limitations"],
            "Comment Type: Editorial/Grammar, Clarification, Technical": ["Technical"],
            "Agency Suggested Text Change": ["The report now notes the limitations of the methodology."],
            "Line": ["12"],
            "NTIA Comments": [""],
            "Comment Disposition": [""],
            "Resolution": [""],
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
    assert out_df.iloc[0]["Report Version"] == "rev1"
    provenance_content = json.loads((tmp_path / "out_provenance.json").read_text())
    provenance_payload = provenance_content.get("payload", provenance_content)
    records = provenance_payload["records"] if isinstance(provenance_payload, dict) else provenance_payload
    provenance_text = json.dumps(records)
    assert "record_id" in provenance_text
    assert "generated_by_system" in provenance_text


def test_pipeline_requires_revision_when_multiple_reports(tmp_path: Path):
    comments = tmp_path / "comments.xlsx"
    df = pd.DataFrame(
        {
            "Comment Number": [1],
            "Report Version": [""],
            "Reviewer Initials": ["AB"],
            "Agency": ["NTIA"],
            "Section": ["2.1"],
            "Page": ["1"],
            "Agency Notes": ["Clarify methodology limitations"],
            "Comment Type: Editorial/Grammar, Clarification, Technical": ["Technical"],
            "Agency Suggested Text Change": ["The report now notes the limitations of the methodology."],
            "Line": ["12"],
            "NTIA Comments": [""],
            "Comment Disposition": [""],
            "Resolution": [""],
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
    assert "Report Version" in str(exc.value)


def test_pipeline_writes_provenance_metadata(tmp_path: Path):
    comments = tmp_path / "comments.xlsx"
    df = pd.DataFrame(
        {
            "Comment Number": [1],
            "Report Version": ["rev1"],
            "Reviewer Initials": ["AB"],
            "Agency": ["NTIA"],
            "Section": ["2.1"],
            "Page": ["1"],
            "Agency Notes": ["Clarify methodology limitations"],
            "Comment Type: Editorial/Grammar, Clarification, Technical": ["Technical"],
            "Agency Suggested Text Change": ["The report now notes the limitations of the methodology."],
            "Line": ["12"],
            "NTIA Comments": [""],
            "Comment Disposition": [""],
            "Resolution": [""],
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
        include_metadata_columns=True,
    )

    provenance_path = tmp_path / "out_provenance.json"
    assert provenance_path.exists()
    provenance_raw = json.loads(provenance_path.read_text())
    provenance_payload = provenance_raw.get("payload", provenance_raw)
    records = provenance_payload["records"] if isinstance(provenance_payload, dict) else provenance_payload
    provenance = pd.DataFrame(records)
    assert {"record_id", "record_type", "source_document", "resolved_against_revision", "workflow_name", "review_status", "confidence_score"}.issubset(
        set(provenance.columns)
    )
    assert out_df.iloc[0]["Provenance Record Id"] in provenance["record_id"].tolist()
