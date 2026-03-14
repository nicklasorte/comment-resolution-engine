from pathlib import Path

import pytest
import yaml

from comment_resolution_engine.contracts.artifacts import (
    build_comment_resolution_matrix_artifact,
    build_provenance_record_artifact,
    load_reviewer_comment_set,
    new_resolution_run_id,
    validate_comment_resolution_matrix_artifact,
    validate_provenance_record_artifact,
    validate_reviewer_comment_set,
)
from comment_resolution_engine.errors import CREError
from comment_resolution_engine.pipeline import run_pipeline
from comment_resolution_engine.spreadsheet_contract import MATRIX_CONTRACT

pd = pytest.importorskip("pandas")


def test_contract_declaration_file_exists():
    decl_path = Path("config/contracts/contract_declaration.yaml")
    assert decl_path.exists()
    data = yaml.safe_load(decl_path.read_text())
    assert data.get("repo_role") == "engine_repo"
    assert "reviewer_comment_set" in data.get("consumed_artifact_types", [])
    assert "comment_resolution_matrix" in data.get("produced_artifact_types", [])


def test_reviewer_comment_set_example_validates():
    artifact = load_reviewer_comment_set(Path("examples/contracts/reviewer_comment_set_example.json"))
    assert artifact["artifact_type"] == "reviewer_comment_set"
    assert len(artifact["comments"]) == 2
    validate_reviewer_comment_set(artifact)


def test_comment_resolution_matrix_example_validates():
    matrix_path = Path("examples/contracts/comment_resolution_matrix_example.json")
    matrix_artifact = yaml.safe_load(matrix_path.read_text())
    validate_comment_resolution_matrix_artifact(matrix_artifact)
    assert matrix_artifact["rows"][0]["comment_id"] == "C-001"


def test_provenance_record_example_validates():
    prov_path = Path("examples/contracts/provenance_record_example.json")
    prov_artifact = yaml.safe_load(prov_path.read_text())
    validate_provenance_record_artifact(prov_artifact)
    assert prov_artifact["records"][0]["record_id"] == "prov-C-001"


def test_pipeline_emits_canonical_artifacts(tmp_path: Path):
    comments = tmp_path / "comments.xlsx"
    df = pd.DataFrame(
        {
            "Comment Number": [1],
            "Report Version": ["rev1"],
            "Reviewer Initials": ["AB"],
            "Agency": ["NTIA"],
            "Section": ["1"],
            "Page": ["1"],
            "Agency Notes": ["Clarify scope"],
            "Comment Type: Editorial/Grammar, Clarification, Technical": ["Technical"],
            "Agency Suggested Text Change": ["State scope explicitly"],
            "Line": ["12"],
            "NTIA Comments": [""],
            "Comment Disposition": [""],
            "Resolution": [""],
        }
    )
    df.to_excel(comments, index=False)

    report = tmp_path / "report.txt"
    report.write_text("\n".join(["10 Intro text", "11 Lead-in", "12 Scope text"]))

    output_path = tmp_path / "out.xlsx"
    run_pipeline(comments_path=comments, report_path=report, output_path=output_path, config_path=None)

    matrix_path = tmp_path / "out_comment_resolution_matrix.json"
    provenance_path = tmp_path / "out_provenance_record.json"
    assert matrix_path.exists()
    assert provenance_path.exists()

    matrix_artifact = yaml.safe_load(matrix_path.read_text())
    prov_artifact = yaml.safe_load(provenance_path.read_text())

    validate_comment_resolution_matrix_artifact(matrix_artifact)
    validate_provenance_record_artifact(prov_artifact)
    assert matrix_artifact["rows"][0]["comment_id"] == "1"
    assert matrix_artifact["rows"][0]["trace"]["source_comment_id"] == "1"
    assert prov_artifact["resolution_run_id"] == matrix_artifact["resolution_run_id"]


def test_missing_required_field_raises():
    bad_matrix = {
        "artifact_type": "comment_resolution_matrix",
        "resolution_run_id": new_resolution_run_id(),
        "rows": [{"comment_id": "1", "resolution_text": "text only"}],
    }
    with pytest.raises(CREError):
        validate_comment_resolution_matrix_artifact(bad_matrix)


def test_matrix_contract_yaml_loaded():
    assert "Comment Number" in MATRIX_CONTRACT.required_headers
    assert set(MATRIX_CONTRACT.generated_headers) == {"NTIA Comments", "Comment Disposition", "Resolution"}
    assert MATRIX_CONTRACT.completion_values
