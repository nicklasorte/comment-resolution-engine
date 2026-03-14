from comment_resolution_engine.contracts import (
    ARCHITECTURE_REPO,
    ERROR_TAXONOMY_VERSION,
    IMPLEMENTED_SYSTEM_ID,
    PROVENANCE_GUIDANCE_VERSION,
    SCHEMA_VERSION,
    SPEC_VERSION,
)
from comment_resolution_engine.contracts.compatibility import evaluate_compatibility
from comment_resolution_engine.contracts.loader import load_constitution_manifest
from comment_resolution_engine.contracts.models import EngineContractState


def test_loads_constitution_manifest(tmp_path):
    manifest_path = tmp_path / "constitution.yaml"
    manifest_path.write_text(
        """source_repo: spectrum-systems
system_id: SYS-001
pinned_version: v9.9.9
schema_refs:
  - id: schema
    path: ../docs/system-spec-comment-resolution-engine.md
    version: 1.0.0
rules_profile_refs:
  - profile: default
    version: 1.0.0
prompt_refs:
  - id: p
    path: ../prompts/resolution_engine.md
    version: 1.0.0
provenance_standard_ref:
  id: prov
  path: ../docs/provenance-implementation-guidance.md
  version: 1.0.0
error_taxonomy_ref:
  id: err
  path: ../docs/error-taxonomy.md
  version: 1.0.0
compatibility_mode: warn
"""
    )
    manifest = load_constitution_manifest(manifest_path)
    assert manifest.system_id == "SYS-001"
    assert manifest.pinned_version == "v9.9.9"
    assert manifest.compatibility_mode == "warn"
    assert manifest.provenance_standard_ref.kind == "provenance"


def test_constitution_compatibility_warns_on_drift():
    manifest = load_constitution_manifest()
    engine_state = EngineContractState(
        source_repo=ARCHITECTURE_REPO,
        system_id=IMPLEMENTED_SYSTEM_ID,
        spec_version=SPEC_VERSION,
        schema_version="9.9.9",
        provenance_version=PROVENANCE_GUIDANCE_VERSION,
        error_taxonomy_version=ERROR_TAXONOMY_VERSION,
        rules_profile="default",
    )
    report = evaluate_compatibility(manifest, engine_state, compatibility_mode_override="warn")
    assert any(f.code == "SCHEMA_DRIFT" for f in report.findings)
    assert report.compatible is True
    assert report.constitution_context.pinned_version == manifest.pinned_version
