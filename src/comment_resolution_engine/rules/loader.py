from __future__ import annotations

from dataclasses import fields
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple, Type

import yaml

from ..errors import CREError, ErrorCategory
from .models import (
    BaseRule,
    CanonicalTermRule,
    DispositionRule,
    DraftingRule,
    IssuePatternRule,
    RulePack,
    ValidationRule,
)
from .schema_validation import (
    RulePackValidationError,
    Strictness,
    ValidationWarning,
    validate_profile_overrides,
    validate_rules_payload,
)


RULE_FILE_MAP: List[Tuple[str, Type[BaseRule], str]] = [
    ("canonical_terms.yaml", CanonicalTermRule, "canonical_term"),
    ("issue_patterns.yaml", IssuePatternRule, "issue_pattern"),
    ("disposition_rules.yaml", DispositionRule, "disposition"),
    ("drafting_rules.yaml", DraftingRule, "drafting"),
    ("validation_rules.yaml", ValidationRule, "validation"),
]


class RulePackLoadError(CREError):
    def __init__(self, category: ErrorCategory, message: str, *, file: str | None = None, rule_id: str | None = None):
        prefix = f"{file}: " if file else ""
        suffix = f" (rule {rule_id})" if rule_id else ""
        super().__init__(category, f"{prefix}{message}{suffix}".strip())
        self.file = file
        self.rule_id = rule_id


def _known_fields(rule_cls: Type[BaseRule]) -> set[str]:
    return {f.name for f in fields(rule_cls)}


def _coerce_rule(entry: Dict[str, Any], rule_cls: Type[BaseRule], default_type: str, source: str) -> BaseRule:
    payload: Dict[str, Any] = {k: v for k, v in entry.items() if k in _known_fields(rule_cls)}
    payload.setdefault("rule_id", entry.get("id") or entry.get("rule_id"))
    payload.setdefault("rule_type", entry.get("rule_type") or default_type)
    payload.setdefault("priority", entry.get("priority", 0))
    payload.setdefault("enabled", entry.get("enabled", True))
    payload["match"] = entry.get("match") or {}
    payload["action"] = entry.get("action") or {}
    payload["rationale_template"] = entry.get("rationale_template", "")
    payload["patch_template"] = entry.get("patch_template", "")
    payload["source"] = entry.get("source", source)
    payload["version"] = entry.get("version", "")

    missing = [key for key in ("rule_id",) if not payload.get(key)]
    if missing:
        raise CREError(ErrorCategory.SCHEMA_ERROR, f"Rule missing required fields: {', '.join(missing)}")

    try:
        return rule_cls(**payload)  # type: ignore[arg-type]
    except TypeError as exc:
        raise CREError(ErrorCategory.VALIDATION_ERROR, f"Invalid rule structure for {payload.get('rule_id')}: {exc}") from exc


def _load_rules_file(
    path: Path, rule_cls: Type[BaseRule], default_type: str, source: str, *, strictness: Strictness, warnings: List[ValidationWarning]
) -> List[BaseRule]:
    try:
        raw = yaml.safe_load(path.read_text()) if path.exists() else None
    except yaml.YAMLError as exc:
        raise RulePackLoadError(ErrorCategory.SCHEMA_ERROR, f"Malformed YAML: {exc}", file=path.name) from exc

    if raw is None:
        return []
    try:
        warnings.extend(validate_rules_payload(raw, file=path, expected_type=default_type, strictness=strictness))
    except RulePackValidationError as exc:
        raise RulePackLoadError(exc.category, str(exc), file=exc.file, rule_id=exc.rule_id) from exc

    rules: List[BaseRule] = []
    for entry in raw:
        rules.append(_coerce_rule(entry, rule_cls, default_type, source))
    return rules


def _apply_profile_overrides(
    base_rules: List[BaseRule],
    overrides: Iterable[Dict[str, Any]],
    rule_cls: Type[BaseRule],
    default_type: str,
    source: str,
) -> List[BaseRule]:
    rules = list(base_rules)
    for entry in overrides:
        override_rule = _coerce_rule(entry, rule_cls, default_type, source)
        replaced = False
        for idx, existing in enumerate(rules):
            if existing.rule_id == override_rule.rule_id:
                rules[idx] = override_rule
                replaced = True
                break
        if not replaced:
            rules.append(override_rule)
    return rules


def _load_profile(path: Path, *, strictness: Strictness, warnings: List[ValidationWarning]) -> Dict[str, list]:
    if not path.exists():
        return {}
    try:
        raw = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as exc:
        raise RulePackLoadError(ErrorCategory.SCHEMA_ERROR, f"Malformed YAML: {exc}", file=path.name) from exc
    try:
        warnings.extend(validate_profile_overrides(raw, file=path, strictness=strictness))
    except RulePackValidationError as exc:
        raise RulePackLoadError(exc.category, str(exc), file=exc.file, rule_id=exc.rule_id) from exc
    return {k: (v or []) for k, v in raw.items()}


def load_rule_pack(
    path: str | Path,
    profile: str | None = None,
    requested_version: str | None = None,
    *,
    strictness: Strictness | str = Strictness.PERMISSIVE,
) -> RulePack:
    rules_dir = Path(path)
    if not rules_dir.exists() or not rules_dir.is_dir():
        raise CREError(ErrorCategory.EXTRACTION_ERROR, f"Rules path {path} was not found or is not a directory.")

    strict = Strictness.from_value(strictness)
    validation_warnings: List[ValidationWarning] = []
    profile_name = profile or "default"
    profile_path = rules_dir / "profiles" / f"{profile_name}.yaml"
    profile_data = _load_profile(profile_path, strictness=strict, warnings=validation_warnings) if profile_path.exists() else {}
    if not profile and not profile_data:
        default_profile_path = rules_dir / "profiles" / "default.yaml"
        profile_name = "default" if default_profile_path.exists() else "local-defaults"
        profile_data = _load_profile(default_profile_path, strictness=strict, warnings=validation_warnings) if default_profile_path.exists() else {}

    canonical_rules: List[BaseRule] = []
    issue_rules: List[BaseRule] = []
    disposition_rules: List[BaseRule] = []
    drafting_rules: List[BaseRule] = []
    validation_rules: List[BaseRule] = []

    for filename, rule_cls, default_type in RULE_FILE_MAP:
        rules = _load_rules_file(rules_dir / filename, rule_cls, default_type, str(rules_dir), strictness=strict, warnings=validation_warnings)
        overrides = profile_data.get(filename.replace(".yaml", "")) or profile_data.get(default_type + "s") or []
        if overrides:
            rules = _apply_profile_overrides(rules, overrides, rule_cls, default_type, str(rules_dir))

        if rule_cls is CanonicalTermRule:
            canonical_rules = rules
        elif rule_cls is IssuePatternRule:
            issue_rules = rules
        elif rule_cls is DispositionRule:
            disposition_rules = rules
        elif rule_cls is DraftingRule:
            drafting_rules = rules
        elif rule_cls is ValidationRule:
            validation_rules = rules

    return RulePack(
        source_path=str(rules_dir),
        rules_profile=profile_name,
        rules_version=requested_version or "",
        validation_warnings=[w.asdict() for w in validation_warnings],
        canonical_term_rules=[r for r in canonical_rules if r.enabled],
        issue_pattern_rules=[r for r in issue_rules if r.enabled],
        disposition_rules=[r for r in disposition_rules if r.enabled],
        drafting_rules=[r for r in drafting_rules if r.enabled],
        validation_rules=[r for r in validation_rules if r.enabled],
        metadata={"requested_version": requested_version},
    )
