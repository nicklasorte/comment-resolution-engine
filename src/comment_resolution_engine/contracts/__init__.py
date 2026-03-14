from __future__ import annotations

from pathlib import Path

import tomllib

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
PYPROJECT_PATH = Path(__file__).resolve().parents[3] / "pyproject.toml"


def _load_implementation_version() -> str:
    try:
        import importlib.metadata as importlib_metadata

        return importlib_metadata.version("comment-resolution-engine")
    except Exception:
        try:
            data = tomllib.loads(PYPROJECT_PATH.read_text())
            return (
                data.get("project", {}).get("version")
                or data.get("tool", {}).get("poetry", {}).get("version")
                or "0.0.0"
            )
        except Exception:
            return "0.0.0"


IMPLEMENTATION_VERSION = _load_implementation_version()


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
