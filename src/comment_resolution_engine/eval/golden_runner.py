from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence

from ..pipeline import run_pipeline
from .adjudication_queue import build_adjudication_queue, export_queue
from .report import aggregate_metrics, render_markdown
from .scoring import GoldenExpectations, load_expectations, score_case


@dataclass(slots=True)
class GoldenCase:
    case_id: str
    comments_path: Path
    report_paths: List[Path]
    config_path: Path | None
    rules_path: Path | None
    rules_profile: str | None
    rules_version: str | None
    expectations: GoldenExpectations


def _resolve_path(base: Path, raw: str | None) -> Path | None:
    if raw is None:
        return None
    path = Path(raw)
    if path.is_absolute():
        return path
    return base / path


def load_case(manifest_path: Path, base_dir: Path) -> GoldenCase:
    data = json.loads(manifest_path.read_text())
    inputs = data.get("inputs") or {}
    case_id = data.get("case_id") or manifest_path.stem.replace("_expected", "")
    comments_path = _resolve_path(base_dir, inputs.get("comments_path"))
    report_paths = [_resolve_path(base_dir, p) for p in inputs.get("reports") or []]
    config_path = _resolve_path(base_dir, inputs.get("config_path"))
    rules_path = _resolve_path(base_dir, inputs.get("rules_path"))
    expectations = load_expectations((data.get("expectations") or {}))
    return GoldenCase(
        case_id=case_id,
        comments_path=comments_path,
        report_paths=[p for p in report_paths if p],
        config_path=config_path,
        rules_path=rules_path,
        rules_profile=inputs.get("rules_profile"),
        rules_version=inputs.get("rules_version"),
        expectations=expectations,
    )


def discover_cases(base_dir: Path) -> List[GoldenCase]:
    expected_dir = base_dir / "expected"
    manifests = sorted(expected_dir.glob("*_expected.json"))
    return [load_case(manifest, base_dir) for manifest in manifests]


def _read_provenance(output_path: Path) -> Sequence[dict]:
    provenance_file = output_path.with_name(output_path.stem + "_provenance.json")
    if provenance_file.exists():
        return json.loads(provenance_file.read_text() or "[]")
    return []


def run_case(case: GoldenCase, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{case.case_id}_resolved.xlsx"
    output_df = run_pipeline(
        comments_path=case.comments_path,
        report_path=case.report_paths,
        output_path=output_path,
        config_path=case.config_path,
        rules_path=case.rules_path,
        rules_profile=case.rules_profile,
        rules_version=case.rules_version,
        rules_strict=False,
    )
    provenance_records = _read_provenance(output_path)
    queue = build_adjudication_queue(output_df, case.expectations.comments)
    queue_path = export_queue(queue, output_dir / f"{case.case_id}_review_queue.json")
    result = score_case(case.case_id, output_df, provenance_records, [q["comment_id"] for q in queue], case.expectations)
    result["queue_path"] = str(queue_path)
    result["provenance_records"] = provenance_records
    return result


def run_suite(cases: Iterable[GoldenCase], output_dir: Path) -> dict:
    results: List[dict] = []
    for case in cases:
        results.append(run_case(case, output_dir))
    aggregate = aggregate_metrics(results)

    metrics_path = output_dir / "golden_metrics.json"
    metrics_path.write_text(json.dumps({"aggregate": aggregate, "cases": results}, indent=2))
    markdown_path = output_dir / "golden_metrics.md"
    markdown_path.write_text(render_markdown(results, aggregate))
    return {"aggregate": aggregate, "cases": results, "metrics_path": str(metrics_path), "markdown_path": str(markdown_path)}


def _default_base_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "golden"


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run golden-set evaluation for comment-resolution-engine.")
    parser.add_argument("--base-dir", type=Path, default=_default_base_dir(), help="Path to the golden directory.")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/golden"), help="Where to write evaluation artifacts.")
    parser.add_argument("--case-id", type=str, default=None, help="Optional single case id to run.")
    args = parser.parse_args(argv)

    base_dir: Path = args.base_dir
    cases = discover_cases(base_dir)
    if args.case_id:
        cases = [c for c in cases if c.case_id == args.case_id]
    if not cases:
        raise SystemExit("No golden cases found.")

    run_suite(cases, args.output_dir)


if __name__ == "__main__":
    main()
