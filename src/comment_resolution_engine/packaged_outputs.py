from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from .pipeline_result import PipelineRunResult
from .run_manifest import build_run_manifest
from .summary import build_summary


@dataclass(slots=True)
class OutputLayout:
    root: Path
    artifacts_dir: Path
    debug_dir: Path
    manifest_path: Path
    summary_path: Path
    comment_resolution_matrix_path: Path
    provenance_record_path: Path
    legacy_workbook_path: Path
    patches_path: Path
    shared_resolutions_path: Path
    faq_path: Path
    section_summary_path: Path
    briefing_path: Path
    normalized_records_path: Path
    adjudication_decisions_path: Path
    provenance_records_path: Path
    reviewer_comment_set_path: Path
    constitution_report_path: Path


def build_output_layout(output_dir: Path) -> OutputLayout:
    root = Path(output_dir)
    artifacts_dir = root / "artifacts"
    debug_dir = root / "debug"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    debug_dir.mkdir(parents=True, exist_ok=True)
    return OutputLayout(
        root=root,
        artifacts_dir=artifacts_dir,
        debug_dir=debug_dir,
        manifest_path=root / "run_manifest.json",
        summary_path=root / "summary.json",
        comment_resolution_matrix_path=artifacts_dir / "comment_resolution_matrix.json",
        provenance_record_path=artifacts_dir / "provenance_record.json",
        legacy_workbook_path=artifacts_dir / "legacy_comment_resolution_matrix.xlsx",
        patches_path=artifacts_dir / "patches.json",
        shared_resolutions_path=artifacts_dir / "shared_resolutions.json",
        faq_path=artifacts_dir / "faq.md",
        section_summary_path=artifacts_dir / "section_summary.md",
        briefing_path=artifacts_dir / "briefing.md",
        normalized_records_path=debug_dir / "normalized_records.json",
        adjudication_decisions_path=debug_dir / "adjudication_decisions.json",
        provenance_records_path=debug_dir / "provenance_records.json",
        reviewer_comment_set_path=artifacts_dir / "reviewer_comment_set.json",
        constitution_report_path=artifacts_dir / "constitution_report.json",
    )


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str))


def _copy_if_exists(source: Optional[Path], destination: Path) -> Optional[Path]:
    if source and Path(source).exists():
        source_path = Path(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            if source_path.resolve() == destination.resolve():
                return destination
        except FileNotFoundError:
            pass
        shutil.copy2(source_path, destination)
        return destination
    return None


def package_outputs(result: PipelineRunResult, output_dir: Path, emit_manifest: bool = False):
    layout = build_output_layout(output_dir)
    outputs: Dict[str, Path] = {}

    source_paths = result.output_paths
    outputs_map = {
        "comment_resolution_matrix": (source_paths.get("comment_resolution_matrix"), layout.comment_resolution_matrix_path),
        "provenance_record": (source_paths.get("provenance_record"), layout.provenance_record_path),
        "legacy_comment_resolution_matrix": (source_paths.get("legacy_workbook"), layout.legacy_workbook_path),
        "patches": (source_paths.get("patches"), layout.patches_path),
        "shared_resolutions": (source_paths.get("shared_resolutions"), layout.shared_resolutions_path),
        "faq": (source_paths.get("faq"), layout.faq_path),
        "section_summary": (source_paths.get("section_summary"), layout.section_summary_path),
        "briefing": (source_paths.get("briefing"), layout.briefing_path),
        "provenance_records": (source_paths.get("provenance_records"), layout.provenance_records_path),
        "constitution_report": (result.input_paths.get("constitution_report"), layout.constitution_report_path),
    }

    for role, (source, destination) in outputs_map.items():
        copied = _copy_if_exists(source, destination)
        if copied:
            outputs[role] = copied

    _write_json(layout.reviewer_comment_set_path, result.reviewer_artifact)
    outputs["reviewer_comment_set"] = layout.reviewer_comment_set_path

    normalized_records = result.normalized_df.to_dict(orient="records")
    decisions_payload = [
        {
            "comment_id": comment.id,
            "disposition": decision.disposition,
            "resolution_text": decision.resolution_text,
            "validation_status": decision.validation_status,
            "validation_code": decision.validation_code,
            "matched_rule_types": decision.matched_rule_types,
            "rule_id": decision.rule_id,
            "rule_version": decision.rule_version,
            "rules_profile": decision.rules_profile,
        }
        for comment, decision in zip(result.analyzed_comments, result.decisions)
    ]

    _write_json(layout.normalized_records_path, normalized_records)
    _write_json(layout.adjudication_decisions_path, decisions_payload)
    outputs["normalized_records"] = layout.normalized_records_path
    outputs["adjudication_decisions"] = layout.adjudication_decisions_path

    summary_payload = build_summary(result)
    _write_json(layout.summary_path, summary_payload)
    outputs["summary"] = layout.summary_path

    manifest_payload = None
    if emit_manifest:
        manifest_payload = build_run_manifest(
            result=result,
            packaged_outputs=outputs,
            summary=summary_payload,
            output_dir=layout.root,
        )
        _write_json(layout.manifest_path, manifest_payload)

    return {
        "layout": layout,
        "outputs": outputs,
        "summary": summary_payload,
        "manifest": manifest_payload,
    }
