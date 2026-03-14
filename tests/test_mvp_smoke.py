import json
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parent.parent


def test_mvp_cli_smoke(tmp_path):
    output_path = tmp_path / "test_adjudicated.xlsx"

    subprocess.run(
        [
            sys.executable,
            "resolve_comments.py",
            "--matrix",
            "examples/sample_matrix.xlsx",
            "--paper",
            "examples/sample_working_paper.pdf",
            "--output",
            str(output_path),
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert output_path.exists()
    df = pd.read_excel(output_path)
    assert not df.empty


def test_reviewer_comment_set_cli_smoke(tmp_path):
    output_path = tmp_path / "artifact_output.xlsx"
    matrix_path = output_path.with_name(output_path.stem + "_comment_resolution_matrix.json")
    provenance_path = output_path.with_name(output_path.stem + "_provenance_record.json")
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}

    subprocess.run(
        [
            sys.executable,
            "-m",
            "comment_resolution_engine.cli",
            "--reviewer-comment-set",
            "examples/contracts/reviewer_comment_set_example.json",
            "--report",
            "examples/sample_working_paper.pdf",
            "--output",
            str(output_path),
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    assert output_path.exists()
    assert matrix_path.exists()
    assert provenance_path.exists()

    with matrix_path.open() as f:
        matrix_artifact = json.load(f)
    with provenance_path.open() as f:
        provenance_artifact = json.load(f)

    matrix_payload = matrix_artifact.get("payload", matrix_artifact)
    provenance_payload = provenance_artifact.get("payload", provenance_artifact)

    assert matrix_artifact.get("artifact_type") == "comment_resolution_matrix"
    assert matrix_payload.get("rows")
    assert matrix_payload.get("source_reviewer_comment_set", {}).get("id") == "example-reviewer-comment-set"

    assert provenance_artifact.get("artifact_type") == "provenance_record"
    assert provenance_payload.get("records")
