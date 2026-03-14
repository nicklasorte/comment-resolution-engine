from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass(slots=True)
class ArtifactRef:
    id: str
    path: Optional[str] = None
    version: Optional[str] = None
    checksum: Optional[str] = None
    kind: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RulesProfileRef(ArtifactRef):
    profile: Optional[str] = None


@dataclass(slots=True)
class ConstitutionManifest:
    source_repo: str
    system_id: str
    pinned_commit: Optional[str] = None
    pinned_version: Optional[str] = None
    schema_refs: List[ArtifactRef] = field(default_factory=list)
    rules_profile_refs: List[RulesProfileRef] = field(default_factory=list)
    prompt_refs: List[ArtifactRef] = field(default_factory=list)
    provenance_standard_ref: Optional[ArtifactRef] = None
    error_taxonomy_ref: Optional[ArtifactRef] = None
    compatibility_mode: str = "strict"
    manifest_path: Optional[Path] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_repo": self.source_repo,
            "system_id": self.system_id,
            "pinned_commit": self.pinned_commit,
            "pinned_version": self.pinned_version,
            "schema_refs": [ref.to_dict() for ref in self.schema_refs],
            "rules_profile_refs": [ref.to_dict() for ref in self.rules_profile_refs],
            "prompt_refs": [ref.to_dict() for ref in self.prompt_refs],
            "provenance_standard_ref": self.provenance_standard_ref.to_dict() if self.provenance_standard_ref else None,
            "error_taxonomy_ref": self.error_taxonomy_ref.to_dict() if self.error_taxonomy_ref else None,
            "compatibility_mode": self.compatibility_mode,
            "manifest_path": str(self.manifest_path) if self.manifest_path else None,
        }


@dataclass(slots=True)
class EngineContractState:
    source_repo: str
    system_id: str
    spec_version: Optional[str]
    schema_version: Optional[str]
    provenance_version: Optional[str]
    error_taxonomy_version: Optional[str]
    rules_profile: Optional[str] = None
    rules_version: Optional[str] = None
    prompt_versions: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ConstitutionContext:
    source_repo: str
    system_id: str
    pinned_version: Optional[str] = None
    pinned_commit: Optional[str] = None
    schema_version: Optional[str] = None
    provenance_guidance_version: Optional[str] = None
    error_taxonomy_version: Optional[str] = None
    rules_profile: Optional[str] = None
    rules_version: Optional[str] = None
    prompt_versions: Dict[str, str] = field(default_factory=dict)
    compatibility_mode: str = "strict"
    fingerprint: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class CompatibilityFinding:
    code: str
    message: str
    severity: str = "ERROR"
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class CompatibilityReport:
    manifest: ConstitutionManifest
    engine_state: EngineContractState
    fingerprint: Dict[str, Any]
    findings: List[CompatibilityFinding]
    compatibility_mode: str
    compatible: bool
    generated_at: str
    constitution_context: ConstitutionContext

    def to_dict(self) -> Dict[str, Any]:
        return {
            "manifest": self.manifest.to_dict(),
            "engine_state": self.engine_state.to_dict(),
            "fingerprint": self.fingerprint,
            "findings": [f.to_dict() for f in self.findings],
            "compatibility_mode": self.compatibility_mode,
            "compatible": self.compatible,
            "generated_at": self.generated_at,
            "constitution_context": self.constitution_context.to_dict(),
        }

    def to_json(self) -> str:
        import json

        return json.dumps(self.to_dict(), indent=2, default=str)


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
