from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .pipeline_result import PipelineRunResult
from .spreadsheet_contract import CONTRACT_PATH


def _package_version() -> str:
    try:
        return metadata.version("comment-resolution-engine")
    except metadata.PackageNotFoundError:
        return "unknown"


def hash_file(path: Path) -> Optional[str]:
    if not path or not Path(path).exists():
        return None
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_entry(path: Path, role: str) -> Optional[Dict[str, Any]]:
    if not path or not Path(path).exists():
        return None
    return {
        "role": role,
        "path": str(path),
        "sha256": hash_file(path),
        "bytes": Path(path).stat().st_size,
    }


def _collect_inputs(result: PipelineRunResult) -> List[Dict[str, Any]]:
    inputs: List[Dict[str, Any]] = []
    inputs.extend(
        entry
        for entry in [
            _file_entry(result.input_paths.get("comments"), "comments_matrix"),
            _file_entry(result.input_paths.get("reviewer_comment_set"), "reviewer_comment_set"),
            _file_entry(result.input_paths.get("config"), "column_mapping"),
            _file_entry(result.input_paths.get("rules"), "rules_pack"),
            _file_entry(result.input_paths.get("constitution"), "constitution_manifest"),
        ]
        if entry
    )

    report_paths = result.input_paths.get("reports") or []
    revision_labels = list(result.pdf_contexts.keys())
    for idx, report_path in enumerate(report_paths):
        label = revision_labels[idx] if idx < len(revision_labels) else f"rev{idx + 1}"
        entry = _file_entry(report_path, f"working_paper_{label}")
        if entry:
            inputs.append(entry)

    return inputs


def _collect_outputs(packaged_outputs: Dict[str, Path]) -> List[Dict[str, Any]]:
    outputs: List[Dict[str, Any]] = []
    for role, path in packaged_outputs.items():
        entry = _file_entry(path, role)
        if entry:
            outputs.append(entry)
    return outputs


def build_run_manifest(
    *,
    result: PipelineRunResult,
    packaged_outputs: Dict[str, Path],
    summary: Dict[str, Any],
    output_dir: Path,
) -> Dict[str, Any]:
    manifest: Dict[str, Any] = {
        "run_id": result.run_id,
        "tool_name": "comment-resolution-engine",
        "tool_version": _package_version(),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "success",
        "warnings": list(result.warnings),
        "output_dir": str(output_dir),
        "counts_summary": summary,
        "inputs": _collect_inputs(result),
        "outputs": _collect_outputs(packaged_outputs),
    }

    constitution_path = result.input_paths.get("constitution")
    manifest["constitution"] = {
        "path": str(constitution_path) if constitution_path else "",
        "sha256": hash_file(constitution_path) if constitution_path else None,
        "pinned_version": result.constitution.pinned_version,
        "pinned_commit": result.constitution.pinned_commit,
        "compatibility_mode": result.constitution.compatibility_mode,
    }

    standards_manifest_path = CONTRACT_PATH
    manifest["standards_manifest"] = {
        "path": str(standards_manifest_path),
        "sha256": hash_file(standards_manifest_path),
    }

    report_path = packaged_outputs.get("constitution_report") or result.constitution_report_path
    if report_path and Path(report_path).exists():
        manifest["constitution_report"] = {
            "path": str(report_path),
            "sha256": hash_file(Path(report_path)),
        }

    return manifest
