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


RULE_FILE_MAP: List[Tuple[str, Type[BaseRule], str]] = [
    ("canonical_terms.yaml", CanonicalTermRule, "canonical_term"),
    ("issue_patterns.yaml", IssuePatternRule, "issue_pattern"),
    ("disposition_rules.yaml", DispositionRule, "disposition"),
    ("drafting_rules.yaml", DraftingRule, "drafting"),
    ("validation_rules.yaml", ValidationRule, "validation"),
]


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


def _load_rules_file(path: Path, rule_cls: Type[BaseRule], default_type: str, source: str) -> List[BaseRule]:
    try:
        raw = yaml.safe_load(path.read_text()) if path.exists() else None
    except yaml.YAMLError as exc:
        raise CREError(ErrorCategory.SCHEMA_ERROR, f"Malformed YAML in {path.name}: {exc}") from exc

    if raw is None:
        return []
    if not isinstance(raw, list):
        raise CREError(ErrorCategory.SCHEMA_ERROR, f"Expected a list of rules in {path.name}.")

    rules: List[BaseRule] = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise CREError(ErrorCategory.SCHEMA_ERROR, f"Rule entries in {path.name} must be dictionaries.")
        rules.append(_coerce_rule(entry, rule_cls, default_type, source))
    return rules


def _apply_profile_overrides(
    base_rules: List[BaseRule], overrides: Iterable[Dict[str, Any]], rule_cls: Type[BaseRule], default_type: str, source: str
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


def _load_profile(path: Path) -> Dict[str, list]:
    if not path.exists():
        return {}
    try:
        raw = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as exc:
        raise CREError(ErrorCategory.SCHEMA_ERROR, f"Malformed YAML in profile {path.name}: {exc}") from exc
    if not isinstance(raw, dict):
        raise CREError(ErrorCategory.SCHEMA_ERROR, f"Profile {path.name} must be a mapping of rule sections.")
    return {k: (v or []) for k, v in raw.items()}


def load_rule_pack(path: str | Path, profile: str | None = None, requested_version: str | None = None) -> RulePack:
    rules_dir = Path(path)
    if not rules_dir.exists() or not rules_dir.is_dir():
        raise CREError(ErrorCategory.EXTRACTION_ERROR, f"Rules path {path} was not found or is not a directory.")

    profile_name = profile or "default"
    profile_path = rules_dir / "profiles" / f"{profile_name}.yaml"
    profile_data = _load_profile(profile_path) if profile_path.exists() else {}
    if not profile and not profile_data:
        default_profile_path = rules_dir / "profiles" / "default.yaml"
        profile_name = "default" if default_profile_path.exists() else "local-defaults"
        profile_data = _load_profile(default_profile_path) if default_profile_path.exists() else {}

    canonical_rules: List[BaseRule] = []
    issue_rules: List[BaseRule] = []
    disposition_rules: List[BaseRule] = []
    drafting_rules: List[BaseRule] = []
    validation_rules: List[BaseRule] = []

    for filename, rule_cls, default_type in RULE_FILE_MAP:
        rules = _load_rules_file(rules_dir / filename, rule_cls, default_type, str(rules_dir))
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
        canonical_term_rules=[r for r in canonical_rules if r.enabled],
        issue_pattern_rules=[r for r in issue_rules if r.enabled],
        disposition_rules=[r for r in disposition_rules if r.enabled],
        drafting_rules=[r for r in drafting_rules if r.enabled],
        validation_rules=[r for r in validation_rules if r.enabled],
        metadata={"requested_version": requested_version},
    )
