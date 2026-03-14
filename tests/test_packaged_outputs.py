import json
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


def test_packaged_cli_outputs(tmp_path: Path):
    output_path = tmp_path / "legacy.xlsx"
    packaged_dir = tmp_path / "packaged"
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}

    subprocess.run(
        [
            sys.executable,
            "-m",
            "comment_resolution_engine.cli",
            "--reviewer-comment-set",
            "docs/demo/inputs/reviewer_comments.json",
            "--report",
            "docs/demo/inputs/demo_working_paper.pdf",
            "--output",
            str(output_path),
            "--output-dir",
            str(packaged_dir),
            "--emit-run-manifest",
        ],
        cwd=REPO_ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    manifest_path = packaged_dir / "run_manifest.json"
    summary_path = packaged_dir / "summary.json"
    legacy_matrix_path = packaged_dir / "artifacts" / "legacy_comment_resolution_matrix.xlsx"
    canonical_matrix_path = packaged_dir / "artifacts" / "comment_resolution_matrix.json"
    provenance_record_path = packaged_dir / "artifacts" / "provenance_record.json"
    normalized_records_path = packaged_dir / "debug" / "normalized_records.json"

    assert manifest_path.exists()
    assert summary_path.exists()
    assert legacy_matrix_path.exists()
    assert canonical_matrix_path.exists()
    assert provenance_record_path.exists()
    assert normalized_records_path.exists()

    manifest = json.loads(manifest_path.read_text())
    outputs = {entry["role"]: entry for entry in manifest.get("outputs", [])}
    assert manifest.get("status") == "success"
    assert manifest.get("run_id")
    assert outputs.get("comment_resolution_matrix", {}).get("sha256")
    assert outputs.get("provenance_record", {}).get("path") == str(provenance_record_path)
    assert outputs.get("constitution_report", {}).get("sha256")

    summary = json.loads(summary_path.read_text())
    assert summary.get("total_comments", 0) >= 1
    assert "counts_by_disposition" in summary
    assert summary.get("comments_needing_response") is not None
