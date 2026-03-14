from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Dict, Iterable, List

from .models import ArtifactRef, ConstitutionManifest, RulesProfileRef


def _sha256_for_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _hash_directory(path: Path) -> str:
    digest = hashlib.sha256()
    for file_path in sorted(p for p in path.rglob("*") if p.is_file()):
        digest.update(str(file_path.relative_to(path)).encode("utf-8"))
        digest.update(_sha256_for_path(file_path).encode("utf-8"))
    return digest.hexdigest()


def _fingerprint_ref(ref: ArtifactRef, base_path: Path) -> Dict[str, object]:
    resolved_path = base_path.joinpath(ref.path).resolve() if ref.path else None
    exists = resolved_path is not None and resolved_path.exists()
    sha_value = None
    if exists and resolved_path.is_file():
        sha_value = _sha256_for_path(resolved_path)
    elif exists and resolved_path.is_dir():
        sha_value = _hash_directory(resolved_path)
    return {
        "id": ref.id,
        "kind": ref.kind,
        "path": ref.path,
        "resolved_path": str(resolved_path) if resolved_path else None,
        "exists": bool(exists),
        "version": ref.version,
        "checksum": ref.checksum,
        "is_directory": bool(resolved_path.is_dir()) if resolved_path else False,
        "sha256": sha_value,
    }


def _fingerprint_refs(refs: Iterable[ArtifactRef], base_path: Path) -> List[Dict[str, object]]:
    return [_fingerprint_ref(ref, base_path) for ref in refs]


def fingerprint_manifest(manifest: ConstitutionManifest) -> Dict[str, object]:
    base_path = manifest.manifest_path.parent if manifest.manifest_path else Path(".")
    return {
        "source_repo": manifest.source_repo,
        "system_id": manifest.system_id,
        "pinned_commit": manifest.pinned_commit,
        "pinned_version": manifest.pinned_version,
        "schemas": _fingerprint_refs(manifest.schema_refs, base_path),
        "rules_profiles": _fingerprint_refs(manifest.rules_profile_refs, base_path),
        "prompts": _fingerprint_refs(manifest.prompt_refs, base_path),
        "provenance_standard": _fingerprint_ref(manifest.provenance_standard_ref, base_path) if manifest.provenance_standard_ref else None,
        "error_taxonomy": _fingerprint_ref(manifest.error_taxonomy_ref, base_path) if manifest.error_taxonomy_ref else None,
    }
