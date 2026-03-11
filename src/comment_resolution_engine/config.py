from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable


DEFAULT_SYNONYMS: Dict[str, list[str]] = {
    "comment_number": ["comment no.", "comment no", "comment number", "cmt #", "cmt#", "comment #"],
    "reviewer_initials": ["reviewer initials", "initials", "reviewer"],
    "agency": ["agency", "organization", "org"],
    "report_version": ["report version", "version", "report rev", "report revision"],
    "section": ["section", "sec."],
    "page": ["page", "pg."],
    "line_number": ["line", "line number", "line no.", "line ref", "source line"],
    "comment_type": [
        "comment type",
        "comment type: editorial/grammar, clarification, technical",
        "type",
        "category",
        "classification",
    ],
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
    "status": ["status", "state", "resolution status", "row status"],
    "report_context": ["report context", "context", "pdf context"],
    "resolution_task": ["resolution task", "task", "llm task"],
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
        "report_version": "Report Version",
        "section": "Section",
        "page": "Page",
        "line_number": "Line",
        "comment_type": "Comment Type: Editorial/Grammar, Clarification, Technical",
        "agency_notes": "Agency Notes",
        "agency_suggested_text": "Agency Suggested Text Change",
        "ntia_comments": "NTIA Comments",
        "disposition": "Comment Disposition",
        "resolution": "Resolution",
        "status": "Status",
        "report_context": "Report Context",
        "resolution_task": "Resolution Task",
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
        raise RuntimeError("PyYAML is required to read --config YAML files. Install dependencies with `pip install -r requirements.txt`.") from exc

    config_path = Path(path)
    raw_data = yaml.safe_load(config_path.read_text()) or {}

    columns = {**DEFAULT_MAPPING.columns, **(raw_data.get("columns") or {})}

    merged_synonyms: Dict[str, list[str]] = {k: list(v) for k, v in DEFAULT_MAPPING.synonyms.items()}
    for key, values in (raw_data.get("synonyms") or {}).items():
        merged_synonyms[key] = list(dict.fromkeys([*merged_synonyms.get(key, []), *values]))

    return ColumnMappingConfig(columns=columns, synonyms=merged_synonyms)
