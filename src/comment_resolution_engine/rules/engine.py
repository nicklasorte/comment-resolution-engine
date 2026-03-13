from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Dict, Iterable, List, Tuple

from ..errors import CREError, ErrorCategory
from ..knowledge.canonical_definitions import match_canonical_term as local_match_canonical
from ..knowledge.issue_library import detect_issue_type
from ..models import AnalyzedComment, ResolutionDecision
from .matcher import matches_rule
from .models import BaseRule, RuleMatchResult, RulePack, ValidationRule
from .provenance import GENERATION_MODE_EXTERNAL, GENERATION_MODE_HYBRID, GENERATION_MODE_LOCAL, summarize_rule_matches


class RuleEngine:
    def __init__(self, rule_pack: RulePack | None):
        self.rule_pack = rule_pack

    @property
    def enabled(self) -> bool:
        return bool(self.rule_pack)

    def _sorted(self, rules: Iterable[BaseRule]) -> List[BaseRule]:
        return sorted(list(rules), key=lambda r: (-int(r.priority or 0), r.rule_id))

    def _to_dict(self, payload: Any) -> Dict[str, Any]:
        if payload is None:
            return {}
        if is_dataclass(payload):
            return asdict(payload)
        if isinstance(payload, dict):
            return dict(payload)
        return payload.__dict__ if hasattr(payload, "__dict__") else {}

    def _build_context(self, comment: Any | None = None, decision: Any | None = None, run_context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        context: Dict[str, Any] = {}
        context.update(self._to_dict(run_context))
        context.update(self._to_dict(decision))
        comment_dict = self._to_dict(comment)
        context.update(comment_dict)
        text_parts = [
            comment_dict.get("effective_comment", ""),
            comment_dict.get("effective_suggested_text", ""),
            comment_dict.get("agency_notes", ""),
            comment_dict.get("agency_suggested_text", ""),
            comment_dict.get("cluster_label", ""),
            comment_dict.get("report_context", ""),
        ]
        context["text"] = " ".join(part for part in text_parts if part)
        return context

    def apply_run_validations(self, run_context: Dict[str, Any]) -> List[RuleMatchResult]:
        matches: List[RuleMatchResult] = []
        if not self.enabled or not self.rule_pack:
            return matches
        for rule in self._sorted(self.rule_pack.validation_rules):
            scope = rule.action.get("scope", "comment") if isinstance(rule.action, dict) else "comment"
            if scope != "run":
                continue
            context = self._build_context(run_context=run_context)
            if matches_rule(rule.match, context):
                applied_action = rule.action or {}
                matches.append(RuleMatchResult(rule=rule, matched=True, context=context, applied_action=applied_action))
                message = applied_action.get("message")
                category = applied_action.get("error_category", "VALIDATION_ERROR")
                if applied_action.get("blocking", True):
                    raise CREError(ErrorCategory(category), message or "Blocking validation rule triggered.")
        return matches

    def apply_canonical_rules(self, comment: Any, run_context: Dict[str, Any] | None = None) -> List[RuleMatchResult]:
        matches: List[RuleMatchResult] = []
        if not self.enabled or not self.rule_pack:
            return matches
        for rule in self._sorted(self.rule_pack.canonical_term_rules):
            context = self._build_context(comment, run_context=run_context)
            if matches_rule(rule.match, context):
                applied_action = dict(rule.action or {})
                if applied_action.get("set_field"):
                    for field, value in applied_action["set_field"].items():
                        setattr(comment, field, value)
                if applied_action.get("canonical_term"):
                    if hasattr(comment, "canonical_term_used") and not getattr(comment, "canonical_term_used"):
                        setattr(comment, "canonical_term_used", applied_action.get("canonical_term"))
                matches.append(RuleMatchResult(rule=rule, matched=True, context=context, applied_action=applied_action))
        return matches

    def match_issue_pattern(self, comment: Any, run_context: Dict[str, Any] | None = None) -> RuleMatchResult | None:
        if not self.enabled or not self.rule_pack:
            return None
        for rule in self._sorted(self.rule_pack.issue_pattern_rules):
            context = self._build_context(comment, run_context=run_context)
            if matches_rule(rule.match, context):
                return RuleMatchResult(rule=rule, matched=True, context=context, applied_action=rule.action or {})
        return None

    def disposition_for_comment(self, comment: Any, run_context: Dict[str, Any] | None = None) -> Tuple[str | None, RuleMatchResult | None]:
        if not self.enabled or not self.rule_pack:
            return None, None
        for rule in self._sorted(self.rule_pack.disposition_rules):
            context = self._build_context(comment, run_context=run_context)
            if matches_rule(rule.match, context):
                action = rule.action or {}
                return action.get("disposition"), RuleMatchResult(rule=rule, matched=True, context=context, applied_action=action)
        return None, None

    def apply_validation_rules(
        self, comment: AnalyzedComment, decision: ResolutionDecision, run_context: Dict[str, Any] | None = None
    ) -> Tuple[List[RuleMatchResult], str, str, str]:
        matches: List[RuleMatchResult] = []
        status = decision.validation_status
        code = decision.validation_code
        notes = decision.validation_notes
        if not self.enabled or not self.rule_pack:
            return matches, status, code, notes

        codes: List[str] = [c for c in (code.split("|") if code else []) if c]
        notes_parts: List[str] = [n for n in (notes.split(";") if notes else []) if n]

        for rule in self._sorted(self.rule_pack.validation_rules):
            scope = rule.action.get("scope", "comment") if isinstance(rule.action, dict) else "comment"
            if scope != "comment":
                continue
            context = self._build_context(comment, decision, run_context)
            if matches_rule(rule.match, context):
                action = rule.action or {}
                matches.append(RuleMatchResult(rule=rule, matched=True, context=context, applied_action=action))
                status = action.get("status", status or "FAIL")
                if action.get("code"):
                    codes.append(action["code"])
                if action.get("notes"):
                    notes_parts.append(action["notes"])
                if action.get("error_category") and action.get("blocking"):
                    raise CREError(ErrorCategory(action["error_category"]), action.get("message", "Blocking validation rule triggered."))

        joined_codes = "|".join(dict.fromkeys(codes))
        joined_notes = "; ".join(part for part in notes_parts if part)
        return matches, status or decision.validation_status, joined_codes, joined_notes

    def apply_drafting_rules(
        self, comment: AnalyzedComment, decision: ResolutionDecision, run_context: Dict[str, Any] | None = None
    ) -> Tuple[List[RuleMatchResult], str, str]:
        matches: List[RuleMatchResult] = []
        resolution_text = decision.resolution_text
        ntia_comment = decision.ntia_comment
        if not self.enabled or not self.rule_pack:
            return matches, resolution_text, ntia_comment

        for rule in self._sorted(self.rule_pack.drafting_rules):
            context = self._build_context(comment, decision, run_context)
            if matches_rule(rule.match, context):
                action = rule.action or {}
                matches.append(RuleMatchResult(rule=rule, matched=True, context=context, applied_action=action))
                if action.get("append_resolution"):
                    resolution_text = f"{resolution_text} {action['append_resolution'].format(**context).strip()}".strip()
                if action.get("prepend_resolution"):
                    resolution_text = f"{action['prepend_resolution'].format(**context).strip()} {resolution_text}".strip()
                if action.get("append_ntia_comment"):
                    ntia_comment = f"{ntia_comment} {action['append_ntia_comment'].format(**context).strip()}".strip()
        return matches, resolution_text, ntia_comment

    def resolve_canonical_term(self, comment: Any) -> Tuple[str, List[RuleMatchResult]]:
        matches: List[RuleMatchResult] = []
        canonical = ""
        if self.enabled and self.rule_pack:
            for rule in self._sorted(self.rule_pack.canonical_term_rules):
                context = self._build_context(comment)
                if matches_rule(rule.match, context):
                    canonical = rule.action.get("canonical_term", "")
                    matches.append(RuleMatchResult(rule=rule, matched=True, context=context, applied_action=rule.action or {}))
                    break

        if not canonical:
            canonical = local_match_canonical(self._build_context(comment).get("text", ""))
        return canonical, matches

    def summarize_matches(self, matches: Iterable[RuleMatchResult]) -> Dict[str, Any]:
        if not self.rule_pack:
            return summarize_rule_matches(matches, {}, fallback_mode=GENERATION_MODE_LOCAL)
        return summarize_rule_matches(matches, self.rule_pack.to_metadata(), fallback_mode=GENERATION_MODE_LOCAL)

    def fallback_issue_type(self, comment: Any) -> str:
        return detect_issue_type(self._build_context(comment).get("text", ""))
