from __future__ import annotations

from typing import List, Optional

from . import SCHEMA_VERSION
from .fingerprint import fingerprint_manifest
from .models import (
    CompatibilityFinding,
    CompatibilityReport,
    ConstitutionContext,
    ConstitutionManifest,
    EngineContractState,
    utcnow_iso,
)


def _drift_severity(mode: str, fail_on_drift: bool) -> str:
    return "ERROR" if mode == "strict" or fail_on_drift else "WARN"


def _add_findings(findings: List[CompatibilityFinding], code: str, message: str, severity: str, details: Optional[Dict] = None):
    findings.append(CompatibilityFinding(code=code, message=message, severity=severity, details=details or {}))


def _select_rules_ref(manifest: ConstitutionManifest, requested_profile: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    if not manifest.rules_profile_refs:
        return requested_profile, None
    if requested_profile:
        for ref in manifest.rules_profile_refs:
            if ref.profile == requested_profile or ref.id == requested_profile:
                return requested_profile, ref.version
    ref = manifest.rules_profile_refs[0]
    return ref.profile or ref.id, ref.version


def evaluate_compatibility(
    manifest: ConstitutionManifest,
    engine_state: EngineContractState,
    compatibility_mode_override: Optional[str] = None,
    fail_on_drift: bool = False,
) -> CompatibilityReport:
    mode = (compatibility_mode_override or manifest.compatibility_mode or "strict").lower()
    fingerprint = fingerprint_manifest(manifest)
    findings: List[CompatibilityFinding] = []
    drift_sev = _drift_severity(mode, fail_on_drift)

    if manifest.system_id != engine_state.system_id:
        _add_findings(
            findings,
            "SYSTEM_MISMATCH",
            f"Manifest declares system_id {manifest.system_id} but engine implements {engine_state.system_id}.",
            "ERROR",
        )
    if manifest.source_repo != engine_state.source_repo:
        _add_findings(
            findings,
            "SOURCE_REPO_MISMATCH",
            f"Manifest source_repo {manifest.source_repo} does not match engine source {engine_state.source_repo}.",
            "ERROR",
        )
    if not manifest.schema_refs:
        _add_findings(findings, "SCHEMA_REF_MISSING", "No schema_refs declared in constitution manifest.", "ERROR")
    if not manifest.prompt_refs:
        _add_findings(findings, "PROMPT_REF_MISSING", "No prompt_refs declared in constitution manifest.", drift_sev)
    if not manifest.rules_profile_refs:
        _add_findings(findings, "RULES_PROFILE_MISSING", "No rules_profile_refs declared in constitution manifest.", drift_sev)

    selected_profile, manifest_rules_version = _select_rules_ref(manifest, engine_state.rules_profile)
    if engine_state.rules_profile and engine_state.rules_profile not in {selected_profile}:
        _add_findings(
            findings,
            "RULES_PROFILE_MISMATCH",
            f"Requested rules profile '{engine_state.rules_profile}' not present in constitution manifest.",
            drift_sev,
        )

    for ref, fp in zip(manifest.schema_refs, fingerprint.get("schemas", [])):
        if not fp.get("exists"):
            _add_findings(findings, "SCHEMA_REF_NOT_FOUND", f"Schema reference {ref.id} not found at {fp.get('resolved_path') or ref.path}.", drift_sev)
        if ref.version and engine_state.schema_version and ref.version != engine_state.schema_version:
            _add_findings(
                findings,
                "SCHEMA_DRIFT",
                f"Schema version {engine_state.schema_version} differs from manifest {ref.version}.",
                drift_sev,
            )

    prov_ref = manifest.provenance_standard_ref
    if prov_ref and prov_ref.version and engine_state.provenance_version and prov_ref.version != engine_state.provenance_version:
        _add_findings(
            findings,
            "PROVENANCE_DRIFT",
            f"Provenance guidance version {engine_state.provenance_version} differs from manifest {prov_ref.version}.",
            drift_sev,
        )

    err_ref = manifest.error_taxonomy_ref
    if err_ref and err_ref.version and engine_state.error_taxonomy_version and err_ref.version != engine_state.error_taxonomy_version:
        _add_findings(
            findings,
            "ERROR_TAXONOMY_DRIFT",
            f"Error taxonomy version {engine_state.error_taxonomy_version} differs from manifest {err_ref.version}.",
            drift_sev,
        )

    for ref, fp in zip(manifest.prompt_refs, fingerprint.get("prompts", [])):
        if not fp.get("exists"):
            _add_findings(findings, "PROMPT_REF_NOT_FOUND", f"Prompt reference {ref.id} not found at {fp.get('resolved_path') or ref.path}.", drift_sev)

    compatible = not any(f.severity == "ERROR" for f in findings)

    constitution_context = ConstitutionContext(
        source_repo=manifest.source_repo,
        system_id=manifest.system_id,
        pinned_version=manifest.pinned_version,
        pinned_commit=manifest.pinned_commit,
        schema_version=engine_state.schema_version or SCHEMA_VERSION,
        provenance_guidance_version=manifest.provenance_standard_ref.version if manifest.provenance_standard_ref else engine_state.provenance_version,
        error_taxonomy_version=manifest.error_taxonomy_ref.version if manifest.error_taxonomy_ref else engine_state.error_taxonomy_version,
        rules_profile=selected_profile or engine_state.rules_profile,
        rules_version=engine_state.rules_version or manifest_rules_version,
        prompt_versions={ref.id: ref.version or "" for ref in manifest.prompt_refs},
        compatibility_mode=mode,
        fingerprint=fingerprint,
    )

    return CompatibilityReport(
        manifest=manifest,
        engine_state=engine_state,
        fingerprint=fingerprint,
        findings=findings,
        compatibility_mode=mode,
        compatible=compatible,
        generated_at=utcnow_iso(),
        constitution_context=constitution_context,
    )
