from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableSequence, Sequence

from ..errors import CREError, ErrorCategory


class Strictness(str, Enum):
    PERMISSIVE = "permissive"
    STRICT = "strict"

    @classmethod
    def from_value(cls, value: str | Strictness | None) -> Strictness:
        if isinstance(value, Strictness):
            return value
        text = (value or "").strip().lower()
        if text == cls.STRICT.value:
            return cls.STRICT
        return cls.PERMISSIVE


@dataclass(slots=True)
class ValidationWarning:
    file: str
    rule_id: str | None
    field: str | None
    message: str
    category: ErrorCategory

    def asdict(self) -> Dict[str, Any]:
        return {
            "file": self.file,
            "rule_id": self.rule_id,
            "field": self.field,
            "message": self.message,
            "category": self.category.value,
        }


class RulePackValidationError(CREError):
    def __init__(self, category: ErrorCategory, message: str, *, file: str | None = None, rule_id: str | None = None):
        prefix = f"{file}: " if file else ""
        suffix = f" (rule {rule_id})" if rule_id else ""
        super().__init__(category, f"{prefix}{message}{suffix}".strip())
        self.file = file
        self.rule_id = rule_id


ALLOWED_DISPOSITIONS = {"accept", "reject", "partial", "partial accept", "defer"}
ALLOWED_WORKFLOW_STATUS = {"open", "pending", "resolved", "needs_review", "blocked", "out_of_scope"}
ALLOWED_VALIDATION_STATUS = {"pass", "fail", "warn", "needs_review"}

COMMON_RULE_FIELDS_REQUIRED = {"rule_id", "rule_type"}
COMMON_RULE_FIELDS_OPTIONAL = {
    "priority",
    "enabled",
    "match",
    "action",
    "rationale_template",
    "patch_template",
    "source",
    "version",
    "id",  # alias for rule_id
}
ALLOWED_COMMON_FIELDS = COMMON_RULE_FIELDS_REQUIRED | COMMON_RULE_FIELDS_OPTIONAL

RULE_SPECIFIC_FIELDS: Mapping[str, set[str]] = {
    "canonical_term": set(),
    "issue_pattern": set(),
    "disposition": set(),
    "drafting": set(),
    "validation": set(),
}

COMMON_ACTION_FIELDS = {"scope", "notes", "notes_template"}
ACTION_FIELDS: Mapping[str, set[str]] = {
    "canonical_term": {"replace_with", "normalized_value", "set_field", "canonical_term"},
    "issue_pattern": {"issue_type", "notes_template", "classification", "disposition"},
    "disposition": {"disposition", "workflow_status", "notes_template", "patch_template"},
    "drafting": {
        "append_text",
        "prepend_text",
        "replace_text",
        "append_resolution",
        "prepend_resolution",
        "append_ntia_comment",
        "notes_template",
    },
    "validation": {
        "block",
        "blocking",
        "error_category",
        "error_message",
        "message",
        "validation_status",
        "status",
        "validation_code",
        "code",
        "validation_notes",
        "notes",
    },
}


def _warn_or_error(
    strictness: Strictness,
    warnings: MutableSequence[ValidationWarning],
    *,
    file: str,
    rule_id: str | None,
    field: str | None,
    category: ErrorCategory,
    message: str,
) -> None:
    if strictness == Strictness.STRICT:
        raise RulePackValidationError(category, message, file=file, rule_id=rule_id)
    warnings.append(ValidationWarning(file=file, rule_id=rule_id, field=field, message=message, category=category))


def _validate_common_fields(
    entry: Dict[str, Any], *, expected_type: str, file: str, strictness: Strictness, warnings: MutableSequence[ValidationWarning]
) -> str:
    rule_id = entry.get("rule_id") or entry.get("id")
    if not rule_id or not str(rule_id).strip():
        raise RulePackValidationError(ErrorCategory.SCHEMA_ERROR, "Rule missing required field 'rule_id'", file=file, rule_id=str(rule_id or ""))

    rule_type = entry.get("rule_type")
    if rule_type and str(rule_type).strip() != expected_type:
        raise RulePackValidationError(
            ErrorCategory.SCHEMA_ERROR, f"rule_type '{rule_type}' does not match expected '{expected_type}'", file=file, rule_id=str(rule_id)
        )
    if not rule_type:
        _warn_or_error(
            strictness,
            warnings,
            file=file,
            rule_id=str(rule_id),
            field="rule_type",
            category=ErrorCategory.SCHEMA_ERROR,
            message=f"Missing rule_type; defaulting to '{expected_type}'.",
        )

    unknown_keys = set(entry.keys()) - ALLOWED_COMMON_FIELDS - RULE_SPECIFIC_FIELDS.get(expected_type, set())
    if unknown_keys:
        _warn_or_error(
            strictness,
            warnings,
            file=file,
            rule_id=str(rule_id),
            field=None,
            category=ErrorCategory.SCHEMA_ERROR,
            message=f"Unknown keys {sorted(unknown_keys)} in rule.",
        )

    if "priority" in entry and entry["priority"] is not None and not isinstance(entry["priority"], int):
        raise RulePackValidationError(ErrorCategory.VALIDATION_ERROR, "priority must be an integer", file=file, rule_id=str(rule_id))
    if "enabled" in entry and entry["enabled"] is not None and not isinstance(entry["enabled"], bool):
        raise RulePackValidationError(ErrorCategory.VALIDATION_ERROR, "enabled must be a boolean", file=file, rule_id=str(rule_id))
    if "match" in entry and entry["match"] is not None and not isinstance(entry["match"], dict):
        raise RulePackValidationError(ErrorCategory.VALIDATION_ERROR, "match must be a mapping", file=file, rule_id=str(rule_id))
    if "action" in entry and entry["action"] is not None and not isinstance(entry["action"], dict):
        raise RulePackValidationError(ErrorCategory.VALIDATION_ERROR, "action must be a mapping", file=file, rule_id=str(rule_id))
    if entry.get("rationale_template") not in (None, "") and not isinstance(entry.get("rationale_template"), str):
        raise RulePackValidationError(ErrorCategory.VALIDATION_ERROR, "rationale_template must be a string", file=file, rule_id=str(rule_id))
    if entry.get("patch_template") not in (None, "") and not isinstance(entry.get("patch_template"), str):
        raise RulePackValidationError(ErrorCategory.VALIDATION_ERROR, "patch_template must be a string", file=file, rule_id=str(rule_id))
    if entry.get("source") not in (None, "") and not isinstance(entry.get("source"), str):
        raise RulePackValidationError(ErrorCategory.VALIDATION_ERROR, "source must be a string", file=file, rule_id=str(rule_id))
    if entry.get("version") not in (None, "") and not isinstance(entry.get("version"), (str, int, float)):
        raise RulePackValidationError(ErrorCategory.VALIDATION_ERROR, "version must be string-like", file=file, rule_id=str(rule_id))
    return str(rule_id)


def _validate_action_keys(
    entry: Dict[str, Any], *, expected_type: str, file: str, rule_id: str, strictness: Strictness, warnings: MutableSequence[ValidationWarning]
) -> None:
    action = entry.get("action") or {}
    if not isinstance(action, dict):
        raise RulePackValidationError(ErrorCategory.VALIDATION_ERROR, "action must be a mapping", file=file, rule_id=rule_id)
    allowed = COMMON_ACTION_FIELDS | ACTION_FIELDS.get(expected_type, set())
    unknown = set(action.keys()) - allowed
    if unknown:
        _warn_or_error(
            strictness,
            warnings,
            file=file,
            rule_id=rule_id,
            field="action",
            category=ErrorCategory.SCHEMA_ERROR,
            message=f"Unknown action keys {sorted(unknown)}",
        )


def _validate_canonical_rule(entry: Dict[str, Any], *, file: str, rule_id: str, strictness: Strictness, warnings: MutableSequence[ValidationWarning]) -> None:
    action = entry.get("action") or {}
    if not any(key in action for key in ("replace_with", "normalized_value", "canonical_term", "set_field")):
        _warn_or_error(
            strictness,
            warnings,
            file=file,
            rule_id=rule_id,
            field="action",
            category=ErrorCategory.VALIDATION_ERROR,
            message="Canonical term rules should specify an action to normalize or set canonical_term.",
        )


def _validate_issue_pattern_rule(
    entry: Dict[str, Any], *, file: str, rule_id: str, strictness: Strictness, warnings: MutableSequence[ValidationWarning]
) -> None:
    action = entry.get("action") or {}
    if not action:
        _warn_or_error(
            strictness,
            warnings,
            file=file,
            rule_id=rule_id,
            field="action",
            category=ErrorCategory.VALIDATION_ERROR,
            message="Issue pattern rule has empty action.",
        )


def _validate_disposition_rule(
    entry: Dict[str, Any], *, file: str, rule_id: str, strictness: Strictness, warnings: MutableSequence[ValidationWarning]
) -> None:
    action = entry.get("action") or {}
    if "disposition" in action:
        disposition = str(action["disposition"]).strip().lower()
        if disposition not in ALLOWED_DISPOSITIONS:
            raise RulePackValidationError(
                ErrorCategory.VALIDATION_ERROR,
                f"Unsupported disposition '{action['disposition']}'. Allowed: {sorted(ALLOWED_DISPOSITIONS)}",
                file=file,
                rule_id=rule_id,
            )
    if "workflow_status" in action:
        status = str(action["workflow_status"]).strip().lower()
        if status not in ALLOWED_WORKFLOW_STATUS:
            raise RulePackValidationError(
                ErrorCategory.VALIDATION_ERROR,
                f"Unsupported workflow_status '{action['workflow_status']}'. Allowed: {sorted(ALLOWED_WORKFLOW_STATUS)}",
                file=file,
                rule_id=rule_id,
            )


def _validate_drafting_rule(
    entry: Dict[str, Any], *, file: str, rule_id: str, strictness: Strictness, warnings: MutableSequence[ValidationWarning]
) -> None:
    action = entry.get("action") or {}
    for key in ("append_text", "prepend_text", "replace_text", "append_resolution", "prepend_resolution", "append_ntia_comment"):
        if key in action and not isinstance(action.get(key), str):
            raise RulePackValidationError(ErrorCategory.VALIDATION_ERROR, f"Drafting action '{key}' must be a string", file=file, rule_id=rule_id)


def _validate_validation_rule(
    entry: Dict[str, Any], *, file: str, rule_id: str, strictness: Strictness, warnings: MutableSequence[ValidationWarning]
) -> None:
    action = entry.get("action") or {}
    if "error_category" in action:
        category = str(action["error_category"])
        if category not in {c.value for c in ErrorCategory}:
            raise RulePackValidationError(
                ErrorCategory.VALIDATION_ERROR,
                f"Invalid error_category '{category}'. Allowed: {[c.value for c in ErrorCategory]}",
                file=file,
                rule_id=rule_id,
            )
    if "status" in action or "validation_status" in action:
        status_value = str(action.get("status") or action.get("validation_status")).strip().lower()
        if status_value and status_value not in ALLOWED_VALIDATION_STATUS:
            raise RulePackValidationError(
                ErrorCategory.VALIDATION_ERROR,
                f"Invalid validation status '{status_value}'. Allowed: {sorted(ALLOWED_VALIDATION_STATUS)}",
                file=file,
                rule_id=rule_id,
            )
    blocking = action.get("block") if "block" in action else action.get("blocking")
    if blocking is not None and not isinstance(blocking, bool):
        raise RulePackValidationError(ErrorCategory.VALIDATION_ERROR, "blocking/block must be a boolean", file=file, rule_id=rule_id)
    if blocking:
        if not action.get("error_category"):
            raise RulePackValidationError(ErrorCategory.VALIDATION_ERROR, "Blocking validation rule requires error_category", file=file, rule_id=rule_id)
        if not action.get("error_message") and not action.get("message"):
            raise RulePackValidationError(ErrorCategory.VALIDATION_ERROR, "Blocking validation rule requires error_message/message", file=file, rule_id=rule_id)


RULE_VALIDATORS = {
    "canonical_term": _validate_canonical_rule,
    "issue_pattern": _validate_issue_pattern_rule,
    "disposition": _validate_disposition_rule,
    "drafting": _validate_drafting_rule,
    "validation": _validate_validation_rule,
}


def validate_rule_entry(
    entry: Dict[str, Any],
    *,
    expected_type: str,
    file: str,
    strictness: Strictness,
    warnings: MutableSequence[ValidationWarning],
) -> None:
    rule_id = _validate_common_fields(entry, expected_type=expected_type, file=file, strictness=strictness, warnings=warnings)
    _validate_action_keys(entry, expected_type=expected_type, file=file, rule_id=rule_id, strictness=strictness, warnings=warnings)
    validator = RULE_VALIDATORS.get(expected_type)
    if validator:
        validator(entry, file=file, rule_id=rule_id, strictness=strictness, warnings=warnings)


def validate_rules_payload(
    payload: Sequence[Any],
    *,
    file: Path,
    expected_type: str,
    strictness: Strictness = Strictness.PERMISSIVE,
) -> List[ValidationWarning]:
    strict = Strictness.from_value(strictness)
    warnings: List[ValidationWarning] = []
    if payload is None:
        return warnings
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise RulePackValidationError(
            ErrorCategory.SCHEMA_ERROR,
            f"Expected a list of rules in {file.name}.",
            file=file.name,
        )
    for entry in payload:
        if not isinstance(entry, dict):
            raise RulePackValidationError(ErrorCategory.SCHEMA_ERROR, f"Rule entries in {file.name} must be dictionaries.", file=file.name)
        validate_rule_entry(entry, expected_type=expected_type, file=file.name, strictness=strict, warnings=warnings)
    return warnings


PROFILE_SECTION_MAP = {
    "canonical_terms": "canonical_term",
    "canonical_term_rules": "canonical_term",
    "issue_patterns": "issue_pattern",
    "disposition_rules": "disposition",
    "drafting_rules": "drafting",
    "validation_rules": "validation",
}


def validate_profile_overrides(
    profile_payload: Mapping[str, Any],
    *,
    file: Path,
    strictness: Strictness = Strictness.PERMISSIVE,
) -> List[ValidationWarning]:
    strict = Strictness.from_value(strictness)
    warnings: List[ValidationWarning] = []
    if profile_payload is None:
        return warnings
    if not isinstance(profile_payload, Mapping):
        raise RulePackValidationError(ErrorCategory.SCHEMA_ERROR, f"Profile {file.name} must be a mapping of rule sections.", file=file.name)

    for section, overrides in profile_payload.items():
        expected_type = PROFILE_SECTION_MAP.get(section)
        if expected_type is None:
            _warn_or_error(
                strict,
                warnings,
                file=file.name,
                rule_id=None,
                field=section,
                category=ErrorCategory.SCHEMA_ERROR,
                message=f"Unknown profile section '{section}'",
            )
            continue
        if overrides is None:
            continue
        if not isinstance(overrides, Iterable) or isinstance(overrides, (str, bytes)):
            raise RulePackValidationError(
                ErrorCategory.SCHEMA_ERROR,
                f"Overrides for section '{section}' must be a list.",
                file=file.name,
            )
        warnings.extend(
            validate_rules_payload(list(overrides), file=file, expected_type=expected_type, strictness=strict),
        )
    return warnings
