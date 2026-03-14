from pathlib import Path

from comment_resolution_engine.eval.golden_runner import discover_cases, run_suite


def test_golden_runner_executes_sample_cases(tmp_path):
    base_dir = Path(__file__).resolve().parents[2] / "golden"
    cases = discover_cases(base_dir)
    result = run_suite(cases, tmp_path)

    metrics_path = tmp_path / "golden_metrics.json"
    markdown_path = tmp_path / "golden_metrics.md"
    assert metrics_path.exists()
    assert markdown_path.exists()
    assert result["cases"]
    for case_result in result["cases"]:
        assert case_result["metrics"]["disposition_accuracy"] > 0
        queue_path = Path(case_result["queue_path"])
        assert queue_path.exists()
