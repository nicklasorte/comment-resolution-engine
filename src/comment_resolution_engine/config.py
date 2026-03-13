from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable

from .errors import CREError, ErrorCategory


DEFAULT_SYNONYMS: Dict[str, list[str]] = {
    "comment_number": ["comment no.", "comment no", "comment number", "cmt #", "cmt#", "comment #"],
    "reviewer_initials": ["reviewer initials", "initials", "reviewer"],
    "agency": ["agency", "organization", "org"],
    "revision": ["revision", "rev", "working paper revision"],
    "report_version": ["report version", "version", "report rev", "report revision"],
    "section": ["section", "sec."],
    "page": ["page", "pg.", "page number"],
    "line": ["line", "line number", "line no.", "line ref", "source line"],
    "line_number": ["line", "line number", "line no.", "line ref", "source line"],
    "comment_type": [
        "comment type",
        "comment type: editorial/grammar, clarification, technical",
        "type",
        "category",
        "classification",
    ],
    "resolved_against_revision": ["resolved against revision", "resolved revision"],
    "agency_notes": ["agency notes", "comment", "reviewer comment", "agency comment", "notes"],
    "agency_suggested_text": [
        "agency suggested text change",
        "suggested text",
        "proposed text",
        "suggested change",
        "proposed resolution",
        "suggested report text",
        "text change",
    ],
    "ntia_comments": ["ntia comments", "internal comments", "disposition notes"],
    "disposition": ["comment disposition", "accept reject", "accept/reject", "disposition"],
    "resolution": ["resolution", "proposed resolution", "final text", "proposed report text"],
    "comment_disposition": ["comment disposition", "accept reject", "accept/reject", "disposition"],
    "wg_chain_comments": ["working group chain comments", "wg chain comments", "coordination notes"],
    "status": ["status", "state", "resolution status", "row status"],
    "report_context": ["report context", "context", "pdf context"],
    "resolution_task": ["resolution task", "task", "llm task"],
    "generation_mode": ["generation mode", "mode"],
    "review_status": ["review status", "review state"],
    "confidence_score": ["confidence score", "confidence"],
    "provenance_record_id": ["provenance record id", "provenance id"],
    "patch_text": ["patch text", "report patch", "edit text"],
    "patch_source": ["patch source", "patch origin"],
    "patch_confidence": ["patch confidence", "patch certainty"],
    "resolution_basis": ["resolution basis", "basis"],
    "validation_code": ["validation code", "validation issue"],
    "context_confidence": ["context confidence", "context quality"],
    "cluster_label": ["cluster label", "cluster theme"],
    "cluster_size": ["cluster size", "cluster count"],
    "shared_resolution_id": ["shared resolution id", "master resolution id"],
    "canonical_term_used": ["canonical term", "canonical term used"],
    "rule_id": ["rule id", "primary rule id"],
    "rule_source": ["rule source", "rules source"],
    "rule_version": ["rule version", "rule pack version"],
    "rules_profile": ["rules profile", "rule profile"],
    "rules_version": ["rules version", "rules pack version"],
    "matched_rule_types": ["matched rule types", "rule matches"],
}


@dataclass(slots=True)
class ColumnMappingConfig:
    columns: Dict[str, str]
    synonyms: Dict[str, list[str]]

    def all_variants(self, canonical_key: str) -> Iterable[str]:
        variants = [self.columns.get(canonical_key, canonical_key)]
        variants.extend(self.synonyms.get(canonical_key, []))
        return [normalize_header(v) for v in variants if v]

    def resolve_column_name(self, existing_columns: Iterable[str], canonical_key: str) -> str:
        lookup = {normalize_header(col): col for col in existing_columns}
        for variant in self.all_variants(canonical_key):
            if variant in lookup:
                return lookup[variant]
        return self.columns.get(canonical_key, canonical_key)


DEFAULT_MAPPING = ColumnMappingConfig(
    columns={
        "comment_number": "Comment Number",
        "reviewer_initials": "Reviewer Initials",
        "agency": "Agency",
        "revision": "Revision",
        "resolved_against_revision": "Resolved Against Revision",
        "report_version": "Report Version",
        "section": "Section",
        "page": "Page",
        "line": "Line",
        "line_number": "Line",
        "comment_type": "Comment Type: Editorial/Grammar, Clarification, Technical",
        "agency_notes": "Agency Notes",
        "agency_suggested_text": "Agency Suggested Text Change",
        "ntia_comments": "NTIA Comments",
        "disposition": "Comment Disposition",
        "resolution": "Resolution",
        "comment_disposition": "Comment Disposition",
        "wg_chain_comments": "WG Chain Comments",
        "status": "Status",
        "report_context": "Report Context",
        "resolution_task": "Resolution Task",
        "generation_mode": "Generation Mode",
        "review_status": "Review Status",
        "confidence_score": "Confidence Score",
        "provenance_record_id": "Provenance Record Id",
        "comment_cluster_id": "Comment Cluster Id",
        "intent_classification": "Intent Classification",
        "section_group": "Section Group",
        "heat_level": "Heat Level",
        "validation_status": "Validation Status",
        "validation_notes": "Validation Notes",
        "validation_code": "Validation Code",
        "patch_text": "Patch Text",
        "patch_source": "Patch Source",
        "patch_confidence": "Patch Confidence",
        "resolution_basis": "Resolution Basis",
        "context_confidence": "Context Confidence",
        "cluster_label": "Cluster Label",
        "cluster_size": "Cluster Size",
        "shared_resolution_id": "Shared Resolution Id",
        "canonical_term_used": "Canonical Term Used",
        "rule_id": "Rule Id",
        "rule_source": "Rule Source",
        "rule_version": "Rule Version",
        "rules_profile": "Rules Profile",
        "rules_version": "Rules Version",
        "matched_rule_types": "Matched Rule Types",
    },
    synonyms=DEFAULT_SYNONYMS,
)


def normalize_header(value: str) -> str:
    return " ".join(str(value).strip().lower().replace("_", " ").split())


def load_column_mapping(path: str | Path | None) -> ColumnMappingConfig:
    if path is None:
        return DEFAULT_MAPPING

    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise CREError(ErrorCategory.EXTRACTION_ERROR, "PyYAML is required to read --config YAML files. Install dependencies with `pip install -r requirements.txt`.") from exc

    config_path = Path(path)
    raw_data = yaml.safe_load(config_path.read_text()) or {}

    columns = {**DEFAULT_MAPPING.columns, **(raw_data.get("columns") or {})}

    merged_synonyms: Dict[str, list[str]] = {k: list(v) for k, v in DEFAULT_MAPPING.synonyms.items()}
    for key, values in (raw_data.get("synonyms") or {}).items():
        merged_synonyms[key] = list(dict.fromkeys([*merged_synonyms.get(key, []), *values]))

    return ColumnMappingConfig(columns=columns, synonyms=merged_synonyms)
