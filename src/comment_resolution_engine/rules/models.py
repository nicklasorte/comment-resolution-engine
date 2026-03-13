from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(slots=True)
class BaseRule:
    rule_id: str
    rule_type: str
    priority: int = 0
    enabled: bool = True
    match: Dict[str, Any] = field(default_factory=dict)
    action: Dict[str, Any] = field(default_factory=dict)
    rationale_template: str = ""
    patch_template: str = ""
    source: str = ""
    version: str = ""


@dataclass(slots=True)
class CanonicalTermRule(BaseRule):
    rule_type: str = "canonical_term"


@dataclass(slots=True)
class IssuePatternRule(BaseRule):
    rule_type: str = "issue_pattern"


@dataclass(slots=True)
class DispositionRule(BaseRule):
    rule_type: str = "disposition"


@dataclass(slots=True)
class DraftingRule(BaseRule):
    rule_type: str = "drafting"


@dataclass(slots=True)
class ValidationRule(BaseRule):
    rule_type: str = "validation"


@dataclass(slots=True)
class RulePack:
    source_path: str
    rules_profile: str = "default"
    rules_version: str = ""
    canonical_term_rules: List[CanonicalTermRule] = field(default_factory=list)
    issue_pattern_rules: List[IssuePatternRule] = field(default_factory=list)
    disposition_rules: List[DispositionRule] = field(default_factory=list)
    drafting_rules: List[DraftingRule] = field(default_factory=list)
    validation_rules: List[ValidationRule] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def loaded_count(self) -> int:
        return sum(
            len(collection)
            for collection in [
                self.canonical_term_rules,
                self.issue_pattern_rules,
                self.disposition_rules,
                self.drafting_rules,
                self.validation_rules,
            ]
        )

    def to_metadata(self) -> Dict[str, Any]:
        return {
            "rules_path": self.source_path,
            "rules_profile": self.rules_profile,
            "rules_version": self.rules_version or self.metadata.get("rules_version"),
            "rules_loaded_count": self.loaded_count,
        }


@dataclass(slots=True)
class RuleMatchResult:
    rule: BaseRule
    matched: bool
    context: Dict[str, Any] = field(default_factory=dict)
    applied_action: Dict[str, Any] = field(default_factory=dict)

    def as_metadata(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule.rule_id,
            "rule_type": self.rule.rule_type,
            "rule_source": self.rule.source,
            "rule_version": self.rule.version,
            "applied_action": self.applied_action,
        }

