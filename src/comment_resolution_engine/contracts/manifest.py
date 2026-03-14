from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, List

import yaml

from ..errors import CREError, ErrorCategory
from . import DEFAULT_CONSTITUTION_PATH
from .models import ArtifactRef, ConstitutionManifest, RulesProfileRef


def _ensure_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _parse_artifact_ref(raw: Any, fallback_id: str, kind: str | None = None) -> ArtifactRef:
    if isinstance(raw, str):
        return ArtifactRef(id=fallback_id, path=raw, kind=kind)
    if isinstance(raw, dict):
        return ArtifactRef(
            id=str(raw.get("id") or fallback_id),
            path=raw.get("path"),
            version=str(raw.get("version")) if raw.get("version") is not None else None,
            checksum=raw.get("checksum"),
            kind=raw.get("kind") or kind,
        )
    raise CREError(ErrorCategory.SCHEMA_ERROR, f"Invalid artifact reference for {fallback_id}: expected string or mapping.")


def _parse_rules_ref(raw: Any, fallback_id: str) -> RulesProfileRef:
    if isinstance(raw, str):
        return RulesProfileRef(id=fallback_id, profile=raw, path=None)
    if isinstance(raw, dict):
        return RulesProfileRef(
            id=str(raw.get("id") or raw.get("profile") or fallback_id),
            profile=raw.get("profile") or raw.get("id") or fallback_id,
            path=raw.get("path"),
            version=str(raw.get("version")) if raw.get("version") is not None else None,
            checksum=raw.get("checksum"),
            kind=raw.get("kind"),
        )
    raise CREError(ErrorCategory.SCHEMA_ERROR, f"Invalid rules reference for {fallback_id}: expected string or mapping.")


def load_manifest(path: str | Path | None = None) -> ConstitutionManifest:
    manifest_path = Path(path) if path else DEFAULT_CONSTITUTION_PATH
    if not manifest_path.exists():
        raise CREError(ErrorCategory.SCHEMA_ERROR, f"Constitution manifest not found at {manifest_path}")
    data = yaml.safe_load(manifest_path.read_text()) or {}

    compatibility_mode = str(data.get("compatibility_mode", "strict") or "strict").lower()
    if compatibility_mode not in {"strict", "warn"}:
        raise CREError(ErrorCategory.SCHEMA_ERROR, "compatibility_mode must be either 'strict' or 'warn'.")

    pinned_commit = data.get("pinned_commit")
    pinned_version = data.get("pinned_version")
    if not pinned_commit and not pinned_version:
        raise CREError(ErrorCategory.SCHEMA_ERROR, "Constitution manifest must declare either pinned_commit or pinned_version.")

    source_repo = data.get("source_repo")
    system_id = data.get("system_id")
    if not source_repo or not system_id:
        raise CREError(ErrorCategory.SCHEMA_ERROR, "Constitution manifest must declare source_repo and system_id.")

    schema_refs = [_parse_artifact_ref(item, f"schema-{idx}", kind="schema") for idx, item in enumerate(_ensure_list(data.get("schema_refs")))]
    rules_refs = [_parse_rules_ref(item, f"rules-{idx}") for idx, item in enumerate(_ensure_list(data.get("rules_profile_refs")))]
    prompt_refs = [_parse_artifact_ref(item, f"prompt-{idx}", kind="prompt") for idx, item in enumerate(_ensure_list(data.get("prompt_refs")))]

    provenance_ref_raw = data.get("provenance_standard_ref")
    error_taxonomy_raw = data.get("error_taxonomy_ref")
    if not provenance_ref_raw or not error_taxonomy_raw:
        raise CREError(ErrorCategory.SCHEMA_ERROR, "Constitution manifest must declare provenance_standard_ref and error_taxonomy_ref.")

    provenance_ref = _parse_artifact_ref(provenance_ref_raw, "provenance", kind="provenance")
    error_taxonomy_ref = _parse_artifact_ref(error_taxonomy_raw, "error-taxonomy", kind="error_taxonomy")

    return ConstitutionManifest(
        source_repo=str(source_repo),
        system_id=str(system_id),
        pinned_commit=str(pinned_commit) if pinned_commit else None,
        pinned_version=str(pinned_version) if pinned_version else None,
        schema_refs=schema_refs,
        rules_profile_refs=rules_refs,
        prompt_refs=prompt_refs,
        provenance_standard_ref=provenance_ref,
        error_taxonomy_ref=error_taxonomy_ref,
        compatibility_mode=compatibility_mode,
        manifest_path=manifest_path,
    )
