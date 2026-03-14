from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Dict, Iterable, List

from .config import normalize_header
from .errors import CREError, ErrorCategory

try:
    import yaml
except ModuleNotFoundError as exc:  # pragma: no cover - import guarded in tests
    raise CREError(
        ErrorCategory.EXTRACTION_ERROR,
        "PyYAML is required to load the matrix contract. Install dependencies with `pip install -r requirements.txt`.",
    ) from exc


def normalize_label(label: str) -> str:
    return normalize_header(label)


def normalized_contract_label(label: str) -> str:
    normalized = normalize_label(label)
    return re.sub(r"\.\d+$", "", normalized)


def _cell_is_blank(value) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and value != value:
        return True
    text = str(value).strip()
    return text == "" or text.lower() in {"nan", "none"}


CONTRACT_PATH = Path(__file__).resolve().parents[2] / "config/contracts/matrix_contract.yaml"


@dataclass(slots=True)
class MatrixContract:
    version: str
    required_headers: List[str]
    optional_headers: List[str]
    metadata_headers: List[str]
    generated_headers: List[str]
    base_order: List[str]
    optional_order: List[str]
    metadata_order: List[str]
    header_to_key: Dict[str, str]
    completion_values: set[str]
    status_header: str
    disposition_header: str
    resolution_header: str

    @property
    def key_to_header(self) -> Dict[str, str]:
        return {v: k for k, v in self.header_to_key.items()}

    @property
    def normalized_required(self) -> set[str]:
        return {normalized_contract_label(h) for h in self.required_headers}

    @property
    def normalized_all_headers(self) -> set[str]:
        return {normalized_contract_label(h) for h in self.header_to_key}

    @property
    def optional_input_keys(self) -> List[str]:
        return [self.header_to_key[h] for h in self.optional_headers if h in self.header_to_key]

    @property
    def metadata_keys(self) -> List[str]:
        return [self.header_to_key[h] for h in self.metadata_headers if h in self.header_to_key]

    def output_headers(self, existing_headers: Iterable[str], include_metadata: bool = False) -> List[str]:
        normalized_existing = {normalized_contract_label(h) for h in existing_headers}
        ordered: List[str] = [h for h in self.base_order if normalized_contract_label(h) in normalized_existing]
        ordered.extend([h for h in self.optional_order if normalized_contract_label(h) in normalized_existing])
        if include_metadata:
            ordered.extend([h for h in self.metadata_order if normalized_contract_label(h) in normalized_existing])
        unique_ordered: List[str] = []
        seen: set[str] = set()
        for header in ordered:
            normalized = normalized_contract_label(header)
            if normalized not in seen:
                unique_ordered.append(header)
                seen.add(normalized)
        return unique_ordered

    def row_status(self, status_value: str, disposition_value: str = "") -> str:
        status_norm = normalize_label(status_value)
        disposition_norm = normalize_label(disposition_value)
        return "Complete" if status_norm in self.completion_values or disposition_norm in self.completion_values else "Draft"

    def duplicate_headers(self, headers: Iterable[str]) -> List[str]:
        canonical_names = self.normalized_all_headers
        seen: Dict[str, str] = {}
        duplicates: List[str] = []
        for col in headers:
            normalized = normalized_contract_label(col)
            if normalized in canonical_names:
                if normalized in seen:
                    duplicates.extend([seen[normalized], col])
                else:
                    seen[normalized] = col
        return duplicates

    def validate_collisions(self, existing_headers: Iterable[str], include_metadata: bool = False) -> None:
        if not include_metadata:
            return
        normalized_existing = {normalized_contract_label(h): h for h in existing_headers}
        protected_metadata = [
            h for h in self.metadata_order if normalized_contract_label(h) not in {normalized_contract_label(o) for o in self.optional_order}
        ]
        collisions = [
            normalized_existing[normalized_contract_label(h)] for h in protected_metadata if normalized_contract_label(h) in normalized_existing
        ]
        if collisions:
            raise CREError(
                ErrorCategory.SCHEMA_ERROR,
                f"ERROR: Output metadata columns would collide with existing input columns: {', '.join(collisions)}. Remove these columns or omit --include-metadata-columns.",
            )

    @classmethod
    def from_dict(cls, data: dict) -> "MatrixContract":
        headers = data.get("headers") or {}
        required_map: Dict[str, str] = headers.get("required") or {}
        optional_map: Dict[str, str] = headers.get("optional") or {}
        metadata_map: Dict[str, str] = headers.get("metadata") or {}
        header_to_key = {**required_map, **optional_map, **metadata_map}
        generated_headers = data.get("generated_headers") or []
        order_data = data.get("order") or {}
        base_order = order_data.get("base") or list(required_map.keys())
        optional_order = order_data.get("optional") or list(optional_map.keys())
        metadata_order = order_data.get("metadata") or list(metadata_map.keys())
        completion = data.get("completion_rules") or {}
        missing_in_order = [
            h for h in [*base_order, *optional_order, *metadata_order] if normalized_contract_label(h) not in {normalized_contract_label(k) for k in header_to_key}
        ]
        if missing_in_order:
            raise CREError(
                ErrorCategory.SCHEMA_ERROR,
                f"Matrix contract order references undefined headers: {', '.join(missing_in_order)}",
            )
        return cls(
            version=str(data.get("version") or "0"),
            required_headers=list(required_map.keys()),
            optional_headers=list(optional_map.keys()),
            metadata_headers=list(metadata_map.keys()),
            generated_headers=list(generated_headers),
            base_order=list(base_order),
            optional_order=list(optional_order),
            metadata_order=list(metadata_order),
            header_to_key=header_to_key,
            completion_values={normalize_label(v) for v in completion.get("completed_values", [])},
            status_header=completion.get("status_header") or "Status",
            disposition_header=completion.get("disposition_header") or "Comment Disposition",
            resolution_header=completion.get("resolution_header") or "Resolution",
        )


def load_matrix_contract(path: Path = CONTRACT_PATH) -> MatrixContract:
    if not path.exists():
        raise CREError(ErrorCategory.SCHEMA_ERROR, f"Matrix contract file not found at {path}")
    data = yaml.safe_load(path.read_text()) or {}
    return MatrixContract.from_dict(data)


MATRIX_CONTRACT = load_matrix_contract()

CANONICAL_SPREADSHEET_HEADERS: List[str] = MATRIX_CONTRACT.base_order
HEADER_TO_KEY = MATRIX_CONTRACT.header_to_key
KEY_TO_HEADER = MATRIX_CONTRACT.key_to_header
CANONICAL_INTERNAL_ORDER: List[str] = [HEADER_TO_KEY[h] for h in CANONICAL_SPREADSHEET_HEADERS]
OPTIONAL_INPUT_HEADERS: List[str] = MATRIX_CONTRACT.optional_order
OPTIONAL_INPUT_KEYS: List[str] = MATRIX_CONTRACT.optional_input_keys
METADATA_HEADERS: List[str] = MATRIX_CONTRACT.metadata_order
METADATA_KEYS: List[str] = MATRIX_CONTRACT.metadata_keys


def required_headers_missing(headers: Iterable[str]) -> List[str]:
    normalized = {normalized_contract_label(col) for col in headers}
    missing = [header for header in CANONICAL_SPREADSHEET_HEADERS if normalized_contract_label(header) not in normalized]
    return missing


def require_canonical_headers(headers: Iterable[str]) -> None:
    missing = required_headers_missing(headers)
    duplicates = MATRIX_CONTRACT.duplicate_headers(headers)
    if missing:
        raise CREError(
            ErrorCategory.SCHEMA_ERROR, f"ERROR: Comments spreadsheet is missing required headers: {', '.join(missing)}"
        )
    if duplicates:
        raise CREError(
            ErrorCategory.SCHEMA_ERROR,
            f"ERROR: Comments spreadsheet contains duplicate canonical headers: {', '.join(dict.fromkeys(duplicates))}",
        )


def validate_completed_rows(df) -> None:
    status_col = MATRIX_CONTRACT.status_header
    disposition_col = MATRIX_CONTRACT.disposition_header
    resolution_col = MATRIX_CONTRACT.resolution_header
    for idx, row in df.iterrows():
        row_status = MATRIX_CONTRACT.row_status(row.get(status_col, ""), row.get(disposition_col, ""))
        if row_status == "Complete":
            if _cell_is_blank(row.get(disposition_col, "")):
                raise CREError(
                    ErrorCategory.VALIDATION_ERROR,
                    f"ERROR: Row {idx + 2} is marked complete but missing Comment Disposition.",
                )
            if _cell_is_blank(row.get(resolution_col, "")):
                raise CREError(
                    ErrorCategory.VALIDATION_ERROR,
                    f"ERROR: Row {idx + 2} is marked complete but missing Resolution text.",
                )


def reorder_to_canonical(df, include_metadata: bool = False):
    """Return a copy ordered with canonical headers first, then optional, then metadata in deterministic order."""
    try:
        import pandas as _pd  # noqa: F401
    except ModuleNotFoundError:
        return df

    require_canonical_headers(df.columns.tolist())
    lookup = {normalized_contract_label(col): col for col in df.columns}
    ordered_headers = MATRIX_CONTRACT.output_headers(df.columns.tolist(), include_metadata=include_metadata)

    ordered = {}
    for header in ordered_headers:
        normalized = normalized_contract_label(header)
        source_col = lookup.get(normalized)
        if source_col is not None:
            ordered[header] = df[source_col]
    return _pd.DataFrame(ordered)
