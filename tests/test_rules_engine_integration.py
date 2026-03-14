from __future__ import annotations

import json
from pathlib import Path

import pytest

pd = pytest.importorskip("pandas")

from comment_resolution_engine.errors import CREError, ErrorCategory
from comment_resolution_engine.pipeline import run_pipeline
from comment_resolution_engine.rules.loader import load_rule_pack
from comment_resolution_engine.spreadsheet_contract import CANONICAL_SPREADSHEET_HEADERS


RULE_FIXTURE = Path(__file__).parent / "fixtures" / "rules" / "basic"


def _write_comments(tmp_path: Path, rows: dict) -> Path:
    rows = dict(rows)
    row_count = len(next(iter(rows.values())))
    for header in CANONICAL_SPREADSHEET_HEADERS:
        if header not in rows:
            if header == "Report Version":
                rows[header] = ["rev1"] * row_count
            else:
                rows[header] = [""] * row_count
    path = tmp_path / "comments.xlsx"
    pd.DataFrame(rows).to_excel(path, index=False)
    return path


def _write_report(tmp_path: Path, name: str = "report_rev2.txt") -> Path:
    report = tmp_path / name
    report.write_text("\n".join(["1 Intro text", "2 Body text", "3 Conclusion"]))
    return report


def test_rule_loader_profile_override_and_counts():
    pack = load_rule_pack(RULE_FIXTURE, profile="default", requested_version="0.1.0")
    assert pack.rules_profile == "default"
    assert pack.rules_version == "0.1.0"
    assert pack.loaded_count >= 5
    canonical_terms = {r.rule_id: r for r in pack.canonical_term_rules}
    assert canonical_terms["CANONICAL_METHOD_SCOPE"].action.get("canonical_term") == "methodology_scope_profile"


def test_rule_loader_handles_missing_and_malformed(tmp_path: Path):
    rules_dir = tmp_path / "ruleset"
    rules_dir.mkdir()
    (rules_dir / "canonical_terms.yaml").write_text("- rule_id: ONLY_RULE\n  match: {}\n  action: {}\n")
    pack = load_rule_pack(rules_dir)
    assert pack.loaded_count == 1

    (rules_dir / "issue_patterns.yaml").write_text("bad: [")
    with pytest.raises(CREError) as exc:
        load_rule_pack(rules_dir)
    assert exc.value.category == ErrorCategory.SCHEMA_ERROR


def test_canonical_rule_normalizes_revision_and_canonical_term(tmp_path: Path):
    comments = _write_comments(
        tmp_path,
        {
            "Comment Number": [1],
            "Agency Notes": ["Methodology overview in Rev 02"],
            "Comment Type: Editorial/Grammar, Clarification, Technical": ["Technical"],
            "Agency Suggested Text Change": ["Clarify scope"],
            "Line": ["12"],
            "Report Version": ["rev2"],
        },
    )
    report = _write_report(tmp_path)
    out_df = run_pipeline(
        comments_path=comments,
        report_path=report,
        output_path=tmp_path / "out.xlsx",
        config_path=None,
        rules_path=RULE_FIXTURE,
        rules_profile="default",
        rules_version="0.0.1",
        include_metadata_columns=True,
    )
    assert out_df.iloc[0]["Resolved Against Revision"] == "rev2"
    assert out_df.iloc[0]["Canonical Term Used"] == "methodology_scope_profile"
    assert out_df.iloc[0]["Rule Id"] != ""
    provenance = json.loads((tmp_path / "out_provenance.json").read_text())
    assert provenance[0]["derived_from"]["rules"]["rules_profile"] == "default"
    assert provenance[0]["derived_from"]["rules"]["rules_version"] == "0.0.1"


def test_issue_pattern_precedes_local_heuristics(tmp_path: Path):
    comments = _write_comments(
        tmp_path,
        {
            "Comment Number": [1],
            "Agency Notes": ["This was already addressed in later revision."],
            "Comment Type: Editorial/Grammar, Clarification, Technical": ["Technical"],
            "Line": ["5"],
            "Report Version": ["rev2"],
        },
    )
    report = _write_report(tmp_path)
    out_df = run_pipeline(
        comments_path=comments,
        report_path=report,
        output_path=tmp_path / "out.xlsx",
        config_path=None,
        rules_path=RULE_FIXTURE,
        include_metadata_columns=True,
    )
    assert out_df.iloc[0]["Comment Disposition"] == "Reject"
    assert "already_addressed" in out_df.iloc[0]["Resolution Basis"]


def test_validation_rules_block_missing_revision(tmp_path: Path):
    comments = _write_comments(
        tmp_path,
        {
            "Comment Number": [1],
            "Agency Notes": ["Missing referenced revision"],
            "Comment Type: Editorial/Grammar, Clarification, Technical": ["Technical"],
            "Line": ["1"],
            "Report Version": ["rev99"],
        },
    )
    report = _write_report(tmp_path, name="report_rev1.txt")
    with pytest.raises(CREError) as exc:
        run_pipeline(
            comments_path=comments,
            report_path=report,
            output_path=tmp_path / "out.xlsx",
            config_path=None,
            rules_path=RULE_FIXTURE,
        )
    assert exc.value.category == ErrorCategory.PROVENANCE_ERROR
    assert "report version 'rev99'" in str(exc.value)


def test_validation_rules_block_when_no_pdfs(tmp_path: Path):
    comments = _write_comments(
        tmp_path,
        {
            "Comment Number": [1],
            "Agency Notes": ["No PDFs provided"],
            "Comment Type: Editorial/Grammar, Clarification, Technical": ["Technical"],
            "Line": ["1"],
            "Report Version": ["rev1"],
        },
    )
    with pytest.raises(CREError) as exc:
        run_pipeline(
            comments_path=comments,
            report_path=None,
            output_path=tmp_path / "out.xlsx",
            config_path=None,
            rules_path=RULE_FIXTURE,
        )
    assert exc.value.category == ErrorCategory.PROVENANCE_ERROR
    assert "No working paper PDFs were supplied" in str(exc.value)


def test_disposition_and_drafting_rules_apply(tmp_path: Path):
    comments = _write_comments(
        tmp_path,
        {
            "Comment Number": [1],
            "Agency Notes": ["Check revision lineage"],
            "Comment Type: Editorial/Grammar, Clarification, Technical": ["Technical"],
            "Agency Suggested Text Change": [""],
            "Line": [""],
            "Report Version": ["rev2"],
        },
    )
    report = _write_report(tmp_path)
    out_df = run_pipeline(
        comments_path=comments,
        report_path=report,
        output_path=tmp_path / "out.xlsx",
        config_path=None,
        rules_path=RULE_FIXTURE,
    )
    assert out_df.iloc[0]["Comment Disposition"] == "Accept"
    assert "Includes revision lineage" in out_df.iloc[0]["Resolution"]
    assert "Review required for context" in out_df.iloc[0]["NTIA Comments"]


def test_pipeline_fallback_without_rules_path(tmp_path: Path):
    comments = _write_comments(
        tmp_path,
        {
            "Comment Number": [1],
            "Agency Notes": ["Clarify methodology limitations"],
            "Comment Type: Editorial/Grammar, Clarification, Technical": ["Technical"],
            "Agency Suggested Text Change": ["The report now notes the limitations of the methodology."],
            "Line": ["12"],
            "Report Version": ["rev1"],
        },
    )
    report = _write_report(tmp_path, name="report_rev1.txt")
    out_df = run_pipeline(
        comments_path=comments,
        report_path=report,
        output_path=tmp_path / "out.xlsx",
        config_path=None,
        include_metadata_columns=True,
    )
    assert "Rule Id" in out_df.columns
    assert out_df.iloc[0]["Rule Id"] in {"", None}
