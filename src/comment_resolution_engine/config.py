from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable


DEFAULT_SYNONYMS: Dict[str, list[str]] = {
    "comment_number": ["comment no.", "comment no", "comment number", "cmt #", "cmt#", "comment #"],
    "comment": ["comment", "comment text", "agency comment", "issue"],
    "line_number": ["line", "line number", "line no.", "line ref", "source line"],
    "revision": ["rev", "revision", "proposed revision", "report revision"],
    "status": ["status", "state", "resolution status"],
}


@dataclass(slots=True)
class ColumnMappingConfig:
    columns: Dict[str, str]
    synonyms: Dict[str, list[str]]

    def all_variants(self, canonical_key: str) -> Iterable[str]:
        variants = [self.columns.get(canonical_key, canonical_key)]
        variants.extend(self.synonyms.get(canonical_key, []))
        return [normalize_header(v) for v in variants if v]


DEFAULT_MAPPING = ColumnMappingConfig(
    columns={
        "comment_number": "Comment Number",
        "comment": "Comment",
        "line_number": "Line Number",
        "revision": "Revision",
        "status": "Status",
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
