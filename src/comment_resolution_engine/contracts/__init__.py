from __future__ import annotations

from pathlib import Path

from .models import ConstitutionContext

IMPLEMENTED_SYSTEM_ID = "SYS-001"
ARCHITECTURE_REPO = "spectrum-systems"
SPEC_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0.0"
PROVENANCE_GUIDANCE_VERSION = "1.0.0"
ERROR_TAXONOMY_VERSION = "1.0.0"
IMPLEMENTATION_REPO = "comment-resolution-engine"
DEFAULT_WORKFLOW_NAME = "NTIA Comment Resolution Pipeline"
DEFAULT_WORKFLOW_STEP = "generate_outputs"
DEFAULT_GENERATION_MODE = "DETERMINISTIC_PIPELINE"

DEFAULT_CONSTITUTION_PATH = Path("config/constitution.yaml")


def default_constitution_context() -> ConstitutionContext:
    return ConstitutionContext(
        source_repo=ARCHITECTURE_REPO,
        system_id=IMPLEMENTED_SYSTEM_ID,
        pinned_version=SPEC_VERSION,
        schema_version=SCHEMA_VERSION,
        provenance_guidance_version=PROVENANCE_GUIDANCE_VERSION,
        error_taxonomy_version=ERROR_TAXONOMY_VERSION,
        compatibility_mode="strict",
        fingerprint={},
    )


__all__ = [
    "ConstitutionContext",
    "ARCHITECTURE_REPO",
    "DEFAULT_CONSTITUTION_PATH",
    "DEFAULT_GENERATION_MODE",
    "DEFAULT_WORKFLOW_NAME",
    "DEFAULT_WORKFLOW_STEP",
    "ERROR_TAXONOMY_VERSION",
    "IMPLEMENTATION_REPO",
    "IMPLEMENTED_SYSTEM_ID",
    "PROVENANCE_GUIDANCE_VERSION",
    "SCHEMA_VERSION",
    "SPEC_VERSION",
    "default_constitution_context",
]
