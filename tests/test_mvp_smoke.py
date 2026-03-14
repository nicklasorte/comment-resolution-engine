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
