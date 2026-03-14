from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from ..errors import CREError, ErrorCategory
from ..models import CommentRecord, ResolutionDecision
from . import (
    ARCHITECTURE_REPO,
    IMPLEMENTATION_REPO,
    IMPLEMENTATION_VERSION,
    SCHEMA_VERSION,
    SPEC_VERSION,
)

CANONICAL_CONTRACT_SOURCE = "spectrum-systems"
CANONICAL_REVIEWER_COMMENT_SET_VERSION = "1.0.0"
CANONICAL_COMMENT_RESOLUTION_MATRIX_VERSION = "1.0.0"
CANONICAL_PROVENANCE_RECORD_VERSION = "1.0.0"
CANONICAL_PATCH_RECORD_VERSION = "1.0.0"
CANONICAL_SHARED_RESOLUTION_VERSION = "1.0.0"
CANONICAL_PROVENANCE_RECORD_SET_VERSION = "1.0.0"
CANONICAL_REV2_SECTION_VERSION = "1.0.0"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_structured_file(path: Path) -> Dict[str, Any]:
    text = path.read_text()
    if path.suffix.lower() in {".yaml", ".yml"}:
        try:
            import yaml
        except ModuleNotFoundError as exc:
            raise CREError(ErrorCategory.EXTRACTION_ERROR, "PyYAML is required to read contract YAML files.") from exc

        return yaml.safe_load(text) or {}
    return json.loads(text)


def _require_pandas():
    try:
        import pandas as pd
    except ModuleNotFoundError as exc:
        raise CREError(ErrorCategory.EXTRACTION_ERROR, "pandas is required for contract artifact handling. Install dependencies with `pip install -r requirements.txt`.") from exc
    return pd


def _ensure(value: Any, message: str, category: ErrorCategory = ErrorCategory.SCHEMA_ERROR) -> Any:
    if value is None or value == "":
        raise CREError(category, message)
    return value


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))


def _hash_payload(payload: Any) -> str:
    return f"sha256:{hashlib.sha256(_canonical_json(payload).encode('utf-8')).hexdigest()}"


def build_artifact_envelope(
    payload: Any,
    *,
    artifact_id: str,
    description: str,
    artifact_type: str | None = None,
    artifact_version: str | None = None,
    produced_by: str = IMPLEMENTATION_REPO,
    tool_version: str = IMPLEMENTATION_VERSION,
    input_artifacts: Optional[list] = None,
    source_files: Optional[list] = None,
    schema_reference: str | None = None,
    created_at: str | None = None,
) -> Dict[str, Any]:
    payload_dict = payload.copy() if isinstance(payload, dict) else payload
    resolved_type = artifact_type or (payload_dict.get("artifact_type") if isinstance(payload_dict, dict) else "")
    resolved_version = artifact_version or (payload_dict.get("artifact_version") if isinstance(payload_dict, dict) else "")

    if isinstance(payload_dict, dict):
        payload_dict.setdefault("artifact_type", resolved_type)
        payload_dict.setdefault("artifact_version", resolved_version)
        payload_dict.setdefault("artifact_id", artifact_id)
        payload_dict.setdefault("generated_at", created_at or _utcnow_iso())

    reference = schema_reference
    if not reference and isinstance(payload_dict, dict) and resolved_type:
        contract_version = payload_dict.get("contract_version") or resolved_version or payload_dict.get("schema_version") or ""
        reference = f"{payload_dict.get('standards_source_repo', CANONICAL_CONTRACT_SOURCE)}/{resolved_type}@{contract_version}"

    created_at_utc = created_at or (payload_dict.get("generated_at") if isinstance(payload_dict, dict) else None) or _utcnow_iso()
    payload_hash = _hash_payload(payload_dict)

    return {
        "artifact_type": resolved_type,
        "artifact_version": resolved_version,
        "artifact_id": artifact_id,
        "created_at_utc": created_at_utc,
        "produced_by": produced_by,
        "tool_version": tool_version,
        "input_artifacts": input_artifacts or [],
        "source_files": source_files or [],
        "schema_reference": reference or "",
        "hash": payload_hash,
        "description": description,
        "payload": payload_dict,
    }


def validate_artifact_envelope(artifact: Dict[str, Any], expected_type: str | None = None) -> Dict[str, Any]:
    if not isinstance(artifact, dict):
        raise CREError(ErrorCategory.SCHEMA_ERROR, "Artifact envelope must be a mapping.")
    payload = artifact.get("payload")
    _ensure(payload is not None, "Artifact envelope must include payload.")
    _ensure(artifact.get("artifact_type"), "artifact_type is required in the envelope.")
    _ensure(artifact.get("artifact_id"), "artifact_id is required in the envelope.")
    if expected_type and artifact.get("artifact_type") != expected_type:
        raise CREError(ErrorCategory.SCHEMA_ERROR, f"artifact_type must be '{expected_type}'.")
    _ensure(artifact.get("artifact_version"), "artifact_version is required in the envelope.")
    _ensure(artifact.get("created_at_utc"), "created_at_utc is required in the envelope.")
    _ensure(artifact.get("produced_by"), "produced_by is required in the envelope.")
    _ensure(artifact.get("tool_version"), "tool_version is required in the envelope.")
    _ensure(isinstance(artifact.get("input_artifacts"), list), "input_artifacts must be a list.")
    _ensure(isinstance(artifact.get("source_files"), list), "source_files must be a list.")
    _ensure(artifact.get("schema_reference") is not None, "schema_reference is required in the envelope.")
    _ensure(artifact.get("hash"), "hash is required in the envelope.")
    if _hash_payload(payload) != artifact["hash"]:
        raise CREError(ErrorCategory.SCHEMA_ERROR, "Artifact envelope hash does not match payload contents.")
    return artifact


def _unwrap_artifact(candidate: Dict[str, Any], expected_type: str | None = None) -> Tuple[Dict[str, Any], Dict[str, Any] | None]:
    if isinstance(candidate, dict) and "payload" in candidate:
        validate_artifact_envelope(candidate, expected_type=expected_type)
        payload = candidate["payload"]
        if not isinstance(payload, dict):
            raise CREError(ErrorCategory.SCHEMA_ERROR, "Artifact payload must be a mapping.")
        return payload, candidate
    return candidate, None

def _to_int(value) -> Optional[int]:
    try:
        if value is None or (isinstance(value, float) and value != value):
            return None
        text = str(value).strip()
        if not text:
            return None
        return int(float(text))
    except (TypeError, ValueError):
        return None


def _normalize_comment_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    comment_id = str(entry.get("comment_id") or entry.get("id") or "").strip()
    revision = str(entry.get("revision") or entry.get("revision_id") or entry.get("working_paper_revision") or "").strip()
    comment_text = str(entry.get("comment_text") or entry.get("agency_notes") or entry.get("comment") or "").strip()
    suggested_text = str(entry.get("suggested_text") or entry.get("agency_suggested_text") or "").strip()

    return {
        "comment_id": comment_id,
        "reviewer_initials": str(entry.get("reviewer_initials") or entry.get("reviewer") or "").strip(),
        "agency": str(entry.get("agency") or "").strip(),
        "revision": revision,
        "report_version": str(entry.get("report_version") or "").strip(),
        "section": str(entry.get("section") or "").strip(),
        "page": _to_int(entry.get("page")),
        "line": _to_int(entry.get("line")),
        "comment_type": str(entry.get("comment_type") or "").strip(),
        "agency_notes": comment_text,
        "agency_suggested_text": suggested_text,
        "wg_chain_comments": str(entry.get("wg_chain_comments") or entry.get("coordination_notes") or "").strip(),
        "status": str(entry.get("status") or "").strip(),
        "provenance": entry.get("provenance") or {},
    }


def validate_reviewer_comment_set(payload: Dict[str, Any], allow_blank_revision: bool = False) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise CREError(ErrorCategory.SCHEMA_ERROR, "Reviewer comment set must be a mapping.")
    payload, envelope = _unwrap_artifact(payload, expected_type=None)
    artifact_type = payload.get("artifact_type") or (envelope or {}).get("artifact_type")
    if artifact_type not in {"reviewer_comment_set", "reviewer_comments"}:
        raise CREError(ErrorCategory.SCHEMA_ERROR, "artifact_type must be 'reviewer_comment_set'.")

    comments = payload.get("comments")
    if not isinstance(comments, list) or not comments:
        raise CREError(ErrorCategory.SCHEMA_ERROR, "comments must be a non-empty list.")

    normalized_comments: List[Dict[str, Any]] = []
    for idx, entry in enumerate(comments):
        if not isinstance(entry, dict):
            raise CREError(ErrorCategory.SCHEMA_ERROR, f"Comment at index {idx} must be a mapping.")
        normalized = _normalize_comment_entry(entry)
        _ensure(normalized["comment_id"], f"comment_id is required for comment index {idx}.")
        if not allow_blank_revision:
            _ensure(normalized["revision"], f"revision is required for comment {normalized['comment_id']}.")
        _ensure(normalized["agency_notes"], f"comment_text/agency_notes is required for comment {normalized['comment_id']}.")
        normalized_comments.append(normalized)

    artifact_id = str(payload.get("artifact_id") or payload.get("id") or "").strip()
    if not artifact_id and envelope:
        artifact_id = str(envelope.get("artifact_id") or "").strip()
    source_repo = str(payload.get("standards_source_repo") or CANONICAL_CONTRACT_SOURCE)
    artifact_version = str(payload.get("artifact_version") or (envelope or {}).get("artifact_version") or CANONICAL_REVIEWER_COMMENT_SET_VERSION)
    schema_version = str(payload.get("schema_version") or (envelope or {}).get("schema_version") or SCHEMA_VERSION)
    contract_version = str(payload.get("contract_version") or artifact_version)

    return {
        "artifact_type": "reviewer_comment_set",
        "artifact_id": artifact_id,
        "artifact_version": artifact_version,
        "schema_version": schema_version,
        "contract_version": contract_version,
        "standards_source_repo": source_repo,
        "produced_by": payload.get("produced_by") or payload.get("source_system") or "",
        "generated_at": payload.get("generated_at"),
        "comments": normalized_comments,
        "metadata": payload.get("metadata") or {},
    }


def load_reviewer_comment_set(path: Path) -> Dict[str, Any]:
    data = _load_structured_file(path)
    normalized = validate_reviewer_comment_set(data)
    normalized["source_path"] = str(path)
    if not normalized["artifact_id"]:
        normalized["artifact_id"] = path.stem
    return normalized


def build_comment_records_from_artifact(artifact: Dict[str, Any], mapping) -> Tuple[List[CommentRecord], "pd.DataFrame", "pd.DataFrame"]:
    pd = _require_pandas()
    records: List[CommentRecord] = []
    rows: List[Dict[str, Any]] = []
    for idx, comment in enumerate(artifact["comments"]):
        comment_id = comment["comment_id"] or idx + 1
        records.append(
            CommentRecord(
                id=str(comment_id),
                reviewer_initials=comment.get("reviewer_initials", ""),
                agency=comment.get("agency", ""),
                revision=comment.get("revision", ""),
                report_version=comment.get("report_version", ""),
                section=comment.get("section", ""),
                page=comment.get("page"),
                line=comment.get("line"),
                comment_type=comment.get("comment_type", ""),
                agency_notes=comment.get("agency_notes", ""),
                agency_suggested_text=comment.get("agency_suggested_text", ""),
                wg_chain_comments=comment.get("wg_chain_comments", ""),
                comment_disposition="",
                resolution="",
                raw_row=comment,
            )
        )
        rows.append(
            {
                mapping.resolve_column_name([], "comment_number"): comment_id,
                mapping.resolve_column_name([], "reviewer_initials"): comment.get("reviewer_initials", ""),
                mapping.resolve_column_name([], "agency"): comment.get("agency", ""),
                mapping.resolve_column_name([], "revision"): comment.get("revision", ""),
                mapping.resolve_column_name([], "report_version"): comment.get("report_version", ""),
                mapping.resolve_column_name([], "section"): comment.get("section", ""),
                mapping.resolve_column_name([], "page"): comment.get("page"),
                mapping.resolve_column_name([], "line"): comment.get("line"),
                mapping.resolve_column_name([], "comment_type"): comment.get("comment_type", ""),
                mapping.resolve_column_name([], "agency_notes"): comment.get("agency_notes", ""),
                mapping.resolve_column_name([], "agency_suggested_text"): comment.get("agency_suggested_text", ""),
                mapping.resolve_column_name([], "wg_chain_comments"): comment.get("wg_chain_comments", ""),
                mapping.resolve_column_name([], "status"): comment.get("status", ""),
            }
        )
    raw_df = pd.DataFrame(rows)
    normalized_df = pd.DataFrame([asdict(r) for r in records])
    return records, normalized_df, raw_df


def build_adapter_artifact(records: Iterable[CommentRecord], source_path: str | Path | None = None) -> Dict[str, Any]:
    return {
        "artifact_type": "reviewer_comment_set",
        "artifact_id": Path(source_path).stem if source_path else "legacy-matrix",
        "artifact_version": "legacy-adapter",
        "schema_version": SCHEMA_VERSION,
        "contract_version": CANONICAL_REVIEWER_COMMENT_SET_VERSION,
        "standards_source_repo": CANONICAL_CONTRACT_SOURCE,
        "produced_by": IMPLEMENTATION_REPO,
        "generated_at": _utcnow_iso(),
        "comments": [
            {
                "comment_id": r.id,
                "reviewer_initials": r.reviewer_initials,
                "agency": r.agency,
                "revision": r.revision,
                "report_version": r.report_version,
                "section": r.section,
                "page": r.page,
                "line": r.line,
                "comment_type": r.comment_type,
                "agency_notes": r.agency_notes,
                "agency_suggested_text": r.agency_suggested_text,
                "wg_chain_comments": r.wg_chain_comments,
                "status": r.review_status,
                "provenance": r.provenance,
            }
            for r in records
        ],
        "metadata": {"adapted_from": str(source_path) if source_path else "in-memory"},
    }


def _build_trace_metadata(comment, decision, provenance_record: Dict[str, Any]) -> Dict[str, Any]:
    trace = {
        "source_comment_id": comment.id,
        "provenance_record_id": comment.provenance_record_id or provenance_record.get("record_id"),
        "rules_profile": comment.rules_profile,
        "rule_id": comment.rule_id,
        "rule_version": comment.rule_version,
        "resolved_against_revision": comment.resolved_against_revision,
    }
    if comment.source_document:
        trace["source_document"] = comment.source_document
    if comment.shared_resolution_id:
        trace["shared_resolution_id"] = comment.shared_resolution_id
    if comment.matched_rule_types:
        trace["matched_rule_types"] = comment.matched_rule_types
    if comment.generation_mode:
        trace["generation_mode"] = comment.generation_mode
    if decision.validation_status:
        trace["validation_status"] = decision.validation_status
    if decision.validation_code:
        trace["validation_code"] = decision.validation_code
    return trace


def build_comment_resolution_matrix_artifact(
    run_id: str,
    input_artifact: Dict[str, Any],
    comments: List[Any],
    decisions: List[ResolutionDecision],
    provenance_records: List[Dict[str, Any]],
    constitution: Any,
    rules_metadata: Dict[str, Any],
) -> Dict[str, Any]:
    rows = []
    provenance_lookup = {rec.get("record_id"): rec for rec in provenance_records}
    for comment, decision in zip(comments, decisions):
        prov = provenance_lookup.get(comment.provenance_record_id) or {}
        rows.append(
            {
                "comment_id": comment.id,
                "upstream_comment_id": comment.id,
                "revision_id": comment.revision,
                "resolved_against_revision": comment.resolved_against_revision,
                "reviewer_initials": comment.reviewer_initials,
                "agency": comment.agency,
                "section": comment.section,
                "page": comment.page,
                "line": comment.line,
                "comment_type": comment.normalized_type or comment.comment_type,
                "agency_comment": comment.agency_notes,
                "agency_suggested_text": comment.agency_suggested_text,
                "wg_chain_comments": comment.wg_chain_comments,
                "disposition": decision.disposition,
                "ntia_comment": decision.ntia_comment,
                "resolution_text": decision.resolution_text,
                "resolution_basis": decision.resolution_basis,
                "patch_text": decision.patch_text,
                "patch_source": decision.patch_source,
                "status": comment.review_status or decision.validation_status,
                "comment_cluster_id": comment.cluster_id,
                "intent_classification": comment.intent_classification,
                "section_group": comment.section_group,
                "heat_level": comment.heat_level,
                "shared_resolution_id": comment.shared_resolution_id,
                "canonical_term_used": decision.canonical_term_used,
                "generation_mode": comment.generation_mode,
                "trace": _build_trace_metadata(comment, decision, prov),
                "provenance": prov,
            }
        )

    return {
        "artifact_type": "comment_resolution_matrix",
        "artifact_id": run_id,
        "artifact_version": CANONICAL_COMMENT_RESOLUTION_MATRIX_VERSION,
        "schema_version": SCHEMA_VERSION,
        "standards_source_repo": CANONICAL_CONTRACT_SOURCE,
        "contract_version": CANONICAL_COMMENT_RESOLUTION_MATRIX_VERSION,
        "resolution_run_id": run_id,
        "generated_at": _utcnow_iso(),
        "source_reviewer_comment_set": {
            "id": input_artifact.get("artifact_id"),
            "version": input_artifact.get("artifact_version"),
            "contract_version": input_artifact.get("contract_version"),
            "schema_version": input_artifact.get("schema_version"),
            "standards_source_repo": input_artifact.get("standards_source_repo"),
        },
        "constitution": {
            "source_repo": constitution.source_repo if constitution else ARCHITECTURE_REPO,
            "pinned_version": constitution.pinned_version if constitution else SPEC_VERSION,
            "pinned_commit": constitution.pinned_commit if constitution else "",
            "compatibility_mode": constitution.compatibility_mode if constitution else "strict",
        },
        "rules_context": rules_metadata,
        "rows": rows,
    }


def validate_comment_resolution_matrix_artifact(artifact: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(artifact, dict):
        raise CREError(ErrorCategory.SCHEMA_ERROR, "Artifact must be a mapping.")
    payload, envelope = _unwrap_artifact(artifact, expected_type="comment_resolution_matrix")
    target = payload
    if target.get("artifact_type") != "comment_resolution_matrix":
        raise CREError(ErrorCategory.SCHEMA_ERROR, "artifact_type must be comment_resolution_matrix.")
    _ensure(target.get("artifact_id") or target.get("resolution_run_id"), "artifact_id or resolution_run_id is required for comment_resolution_matrix.")
    _ensure(target.get("resolution_run_id"), "resolution_run_id is required for comment_resolution_matrix.")
    rows = target.get("rows")
    if not isinstance(rows, list) or not rows:
        raise CREError(ErrorCategory.SCHEMA_ERROR, "comment_resolution_matrix rows must be a non-empty list.")
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            raise CREError(ErrorCategory.SCHEMA_ERROR, f"Row {idx} must be a mapping.")
        _ensure(row.get("comment_id"), f"Row {idx} missing comment_id.")
        _ensure(row.get("revision_id"), f"Row {idx} missing revision_id.")
        _ensure(row.get("resolution_text"), f"Row {idx} missing resolution_text for comment {row.get('comment_id')}.")
        _ensure(row.get("disposition"), f"Row {idx} missing disposition for comment {row.get('comment_id')}.")
        trace = row.get("trace") or {}
        _ensure(trace.get("source_comment_id"), f"Row {idx} missing trace.source_comment_id.")
    return target


def build_provenance_record_artifact(
    run_id: str,
    input_artifact: Dict[str, Any],
    matrix_artifact: Dict[str, Any],
    provenance_records: List[Dict[str, Any]],
    constitution: Any,
) -> Dict[str, Any]:
    return {
        "artifact_type": "provenance_record",
        "artifact_id": run_id,
        "artifact_version": CANONICAL_PROVENANCE_RECORD_VERSION,
        "schema_version": SCHEMA_VERSION,
        "standards_source_repo": CANONICAL_CONTRACT_SOURCE,
        "contract_version": CANONICAL_PROVENANCE_RECORD_VERSION,
        "resolution_run_id": run_id,
        "source_reviewer_comment_set": {
            "id": input_artifact.get("artifact_id"),
            "version": input_artifact.get("artifact_version"),
            "contract_version": input_artifact.get("contract_version"),
        },
        "source_comment_resolution_matrix": {
            "id": matrix_artifact.get("resolution_run_id"),
            "version": matrix_artifact.get("artifact_version"),
            "schema_version": matrix_artifact.get("schema_version"),
        },
        "constitution": {
            "source_repo": constitution.source_repo if constitution else ARCHITECTURE_REPO,
            "pinned_version": constitution.pinned_version if constitution else SPEC_VERSION,
            "pinned_commit": constitution.pinned_commit if constitution else "",
        },
        "generated_at": _utcnow_iso(),
        "records": provenance_records,
    }


def validate_provenance_record_artifact(artifact: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(artifact, dict):
        raise CREError(ErrorCategory.SCHEMA_ERROR, "Artifact must be a mapping.")
    payload, envelope = _unwrap_artifact(artifact, expected_type="provenance_record")
    target = payload
    if target.get("artifact_type") != "provenance_record":
        raise CREError(ErrorCategory.SCHEMA_ERROR, "artifact_type must be provenance_record.")
    _ensure(target.get("artifact_id") or target.get("resolution_run_id"), "artifact_id or resolution_run_id is required for provenance_record.")
    _ensure(target.get("resolution_run_id"), "resolution_run_id is required for provenance_record.")
    records = target.get("records")
    if not isinstance(records, list) or not records:
        raise CREError(ErrorCategory.SCHEMA_ERROR, "provenance_record requires non-empty records.")
    for idx, record in enumerate(records):
        _ensure(record.get("record_id"), f"Provenance record {idx} missing record_id.")
        _ensure(record.get("record_type"), f"Provenance record {idx} missing record_type.")
        _ensure(record.get("source_revision"), f"Provenance record {idx} missing source_revision.")
    return target


def new_resolution_run_id() -> str:
    return f"resolution-run-{uuid.uuid4().hex}"
