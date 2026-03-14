from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from importlib import metadata
from typing import Any, Dict

from .contracts import (
    ARCHITECTURE_REPO,
    ConstitutionContext,
    DEFAULT_GENERATION_MODE,
    DEFAULT_WORKFLOW_NAME,
    DEFAULT_WORKFLOW_STEP,
    ERROR_TAXONOMY_VERSION,
    IMPLEMENTATION_REPO,
    IMPLEMENTED_SYSTEM_ID,
    PROVENANCE_GUIDANCE_VERSION,
    SCHEMA_VERSION,
    SPEC_VERSION,
)


def _package_version() -> str:
    try:
        return metadata.version("comment-resolution-engine")
    except metadata.PackageNotFoundError:
        return SPEC_VERSION


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class ProvenanceRecord:
    record_id: str
    record_type: str
    source_document: str
    source_revision: str
    resolved_against_revision: str
    workflow_name: str
    workflow_step: str
    generated_by_system: str
    generated_by_repo: str
    generated_by_version: str
    prompt_version: str
    schema_version: str
    provenance_guidance_version: str
    error_taxonomy_version: str
    derived_from: Any
    review_status: str
    confidence_score: str
    constitution_source_repo: str = ARCHITECTURE_REPO
    constitution_version: str = SPEC_VERSION
    constitution_commit: str = ""
    rules_profile: str = ""
    rules_version: str = ""
    created_at: str = ""
    updated_at: str = ""
    generation_mode: str = DEFAULT_GENERATION_MODE

    def asdict(self) -> Dict[str, Any]:
        return asdict(self)


def build_provenance_record(
    record_id: str,
    record_type: str,
    source_document: str,
    source_revision: str,
    resolved_against_revision: str,
    derived_from: Any,
    review_status: str,
    confidence_score: str,
    prompt_version: str | None = None,
    workflow_name: str = DEFAULT_WORKFLOW_NAME,
    workflow_step: str = DEFAULT_WORKFLOW_STEP,
    generation_mode: str = DEFAULT_GENERATION_MODE,
    constitution: ConstitutionContext | None = None,
) -> ProvenanceRecord:
    now = utcnow_iso()
    schema_version = constitution.schema_version if constitution else SCHEMA_VERSION
    provenance_version = constitution.provenance_guidance_version if constitution else PROVENANCE_GUIDANCE_VERSION
    error_taxonomy_version = constitution.error_taxonomy_version if constitution else ERROR_TAXONOMY_VERSION
    prompt_version = prompt_version or (constitution.pinned_version if constitution else SPEC_VERSION)
    rules_profile = constitution.rules_profile if constitution else ""
    rules_version = constitution.rules_version if constitution else ""
    constitution_version = constitution.pinned_version if constitution else SPEC_VERSION
    constitution_commit = constitution.pinned_commit if constitution else ""
    constitution_source_repo = constitution.source_repo if constitution else ARCHITECTURE_REPO
    return ProvenanceRecord(
        record_id=str(record_id),
        record_type=record_type,
        source_document=source_document,
        source_revision=source_revision,
        resolved_against_revision=resolved_against_revision,
        workflow_name=workflow_name,
        workflow_step=workflow_step,
        generated_by_system=IMPLEMENTED_SYSTEM_ID,
        generated_by_repo=IMPLEMENTATION_REPO,
        generated_by_version=_package_version(),
        prompt_version=prompt_version,
        schema_version=schema_version,
        provenance_guidance_version=provenance_version,
        error_taxonomy_version=error_taxonomy_version,
        constitution_source_repo=constitution_source_repo,
        constitution_version=constitution_version or "",
        constitution_commit=constitution_commit or "",
        rules_profile=rules_profile or "",
        rules_version=rules_version or "",
        derived_from=derived_from,
        review_status=review_status,
        confidence_score=confidence_score,
        created_at=now,
        updated_at=now,
        generation_mode=generation_mode,
    )
