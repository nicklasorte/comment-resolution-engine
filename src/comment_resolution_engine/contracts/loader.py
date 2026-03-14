from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

from ..errors import CREError, ErrorCategory
from . import ARCHITECTURE_REPO, DEFAULT_CONSTITUTION_PATH, IMPLEMENTED_SYSTEM_ID, PROVENANCE_GUIDANCE_VERSION, SCHEMA_VERSION, SPEC_VERSION, ERROR_TAXONOMY_VERSION
from .compatibility import evaluate_compatibility
from .manifest import load_manifest
from .models import CompatibilityReport, ConstitutionContext, EngineContractState


def load_constitution_manifest(path: str | Path | None = None):
    return load_manifest(path)


def load_constitution(
    manifest_path: str | Path | None = None,
    compatibility_mode: str | None = None,
    rules_profile: str | None = None,
    rules_version: str | None = None,
    fail_on_drift: bool = False,
    require_compatible: bool = True,
    report_path: str | Path | None = None,
) -> tuple[ConstitutionContext, CompatibilityReport]:
    manifest = load_manifest(manifest_path or DEFAULT_CONSTITUTION_PATH)
    engine_state = EngineContractState(
        source_repo=ARCHITECTURE_REPO,
        system_id=IMPLEMENTED_SYSTEM_ID,
        spec_version=SPEC_VERSION,
        schema_version=SCHEMA_VERSION,
        provenance_version=PROVENANCE_GUIDANCE_VERSION,
        error_taxonomy_version=ERROR_TAXONOMY_VERSION,
        rules_profile=rules_profile,
        rules_version=rules_version,
    )
    report = evaluate_compatibility(
        manifest=manifest,
        engine_state=engine_state,
        compatibility_mode_override=compatibility_mode,
        fail_on_drift=fail_on_drift,
    )
    if report_path:
        report_location = Path(report_path)
        report_location.parent.mkdir(parents=True, exist_ok=True)
        report_location.write_text(report.to_json())
    if require_compatible and not report.compatible:
        raise CREError(ErrorCategory.PROVENANCE_ERROR, "Constitution compatibility failed. See constitution report for details.")
    return report.constitution_context, report
