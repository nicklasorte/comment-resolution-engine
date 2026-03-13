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
        self.warnings: List[str] = []

    @property
    def enabled(self) -> bool:
        return bool(self.rule_pack)

    def _precedence_rank(self, rule_type: str) -> int:
        order = {
            "profile_override": 1,
            "section_hook": 2,
            "issue_pattern": 3,
            "disposition": 3,
            "validation": 3,
            "canonical_term": 4,
            "drafting": 4,
        }
        return order.get(rule_type, 5)

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

    def _select_first_with_conflicts(
        self,
        rules: Iterable[BaseRule],
        context: Dict[str, Any],
        *,
        match_basis: str,
        value_getter,
    ) -> Tuple[Any | None, RuleMatchResult | None, List[RuleMatchResult]]:
        matches: List[RuleMatchResult] = []
        selected: RuleMatchResult | None = None
        selected_value: Any | None = None
        best_priority: int | None = None
        sorted_rules = self._sorted(rules)
        for rule in sorted_rules:
            priority = int(rule.priority or 0)
            if best_priority is not None and priority < best_priority:
                break
            context_payload = dict(context)
            if matches_rule(rule.match, context_payload):
                best_priority = priority if best_priority is None else best_priority
                applied_action = rule.action or {}
                result = self._result(rule, context_payload, applied_action, match_basis=match_basis)
                matches.append(result)
                value = value_getter(applied_action)
                if selected is None:
                    selected = result
                    selected_value = value
                else:
                    if value != selected_value:
                        result.applied = False
                        result.skip_reason = "conflict"
                        result.conflict_with = [selected.rule.rule_id]
                        selected.conflict_with.append(result.rule.rule_id)
                        self.warnings.append(
                            f"Conflict in {match_basis} rules at priority {priority}: {selected.rule.rule_id} vs {result.rule.rule_id}"
                        )
                    else:
                        result.applied = False
                        result.skip_reason = "shadowed_by_same_priority"
        return selected_value, selected, matches

    def _result(
        self,
        rule: BaseRule,
        context: Dict[str, Any],
        applied_action: Dict[str, Any],
        *,
        match_basis: str = "",
        applied: bool = True,
        skip_reason: str = "",
        conflict_with: Iterable[str] | None = None,
    ) -> RuleMatchResult:
        rules_profile = self.rule_pack.rules_profile if self.rule_pack else ""
        rules_version = self.rule_pack.rules_version if self.rule_pack else ""
        return RuleMatchResult(
            rule=rule,
            matched=True,
            context=context,
            applied_action=applied_action,
            match_basis=match_basis,
            precedence_rank=self._precedence_rank(rule.rule_type),
            applied=applied,
            skip_reason=skip_reason,
            conflict_with=list(conflict_with or []),
            generation_mode=GENERATION_MODE_EXTERNAL if self.rule_pack else GENERATION_MODE_LOCAL,
            rules_profile=rules_profile,
            rules_version=rules_version,
        )

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
                result = self._result(
                    rule,
                    context,
                    applied_action,
                    match_basis="run_validation",
                    applied=True,
                )
                matches.append(result)
                message = applied_action.get("message") or applied_action.get("error_message")
                category = applied_action.get("error_category", "VALIDATION_ERROR")
                blocking = applied_action.get("blocking", applied_action.get("block", True))
                if blocking:
                    raise CREError(ErrorCategory(category), message or "Blocking validation rule triggered.")
        return matches

    def apply_canonical_rules(self, comment: Any, run_context: Dict[str, Any] | None = None) -> List[RuleMatchResult]:
        matches: List[RuleMatchResult] = []
        if not self.enabled or not self.rule_pack:
            return matches
        applied_fields: Dict[str, Tuple[Any, str]] = {}
        for rule in self._sorted(self.rule_pack.canonical_term_rules):
            context = self._build_context(comment, run_context=run_context)
            if matches_rule(rule.match, context):
                applied_action = dict(rule.action or {})
                conflict_with: List[str] = []
                applied_any = False
                if applied_action.get("set_field"):
                    for field, value in applied_action["set_field"].items():
                        if field in applied_fields and applied_fields[field][0] != value:
                            conflict_with.append(applied_fields[field][1])
                        else:
                            applied_fields[field] = (value, rule.rule_id)
                            setattr(comment, field, value)
                            applied_any = True
                canonical_term = applied_action.get("canonical_term")
                if canonical_term is not None:
                    if "canonical_term" in applied_fields and applied_fields["canonical_term"][0] != canonical_term:
                        conflict_with.append(applied_fields["canonical_term"][1])
                    else:
                        applied_fields["canonical_term"] = (canonical_term, rule.rule_id)
                        if hasattr(comment, "canonical_term_used") and not getattr(comment, "canonical_term_used"):
                            setattr(comment, "canonical_term_used", canonical_term)
                        applied_any = True
                result = self._result(
                    rule,
                    context,
                    applied_action,
                    match_basis="canonical_term",
                    conflict_with=conflict_with,
                )
                if conflict_with and not applied_any:
                    result.applied = False
                    result.skip_reason = "conflict"
                    self.warnings.append(f"Canonical term conflict for {rule.rule_id}: fields {conflict_with}")
                for prior in matches:
                    if prior.rule.rule_id in conflict_with:
                        prior.conflict_with.append(rule.rule_id)
                matches.append(result)
        return matches

    def match_issue_pattern(self, comment: Any, run_context: Dict[str, Any] | None = None) -> Tuple[RuleMatchResult | None, List[RuleMatchResult]]:
        if not self.enabled or not self.rule_pack:
            return None, []
        context = self._build_context(comment, run_context=run_context)
        value, selected, matches = self._select_first_with_conflicts(
            self.rule_pack.issue_pattern_rules,
            context,
            match_basis="issue_pattern",
            value_getter=lambda action: action.get("issue_type") or action.get("disposition") or "",
        )
        return selected, matches

    def disposition_for_comment(
        self, comment: Any, run_context: Dict[str, Any] | None = None
    ) -> Tuple[str | None, RuleMatchResult | None, List[RuleMatchResult]]:
        if not self.enabled or not self.rule_pack:
            return None, None, []
        context = self._build_context(comment, run_context=run_context)
        value, selected, matches = self._select_first_with_conflicts(
            self.rule_pack.disposition_rules,
            context,
            match_basis="disposition",
            value_getter=lambda action: action.get("disposition"),
        )
        return value, selected, matches

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

        blocking_seen: Tuple[str, int] | None = None
        for rule in self._sorted(self.rule_pack.validation_rules):
            scope = rule.action.get("scope", "comment") if isinstance(rule.action, dict) else "comment"
            if scope != "comment":
                continue
            context = self._build_context(comment, decision, run_context)
            if matches_rule(rule.match, context):
                action = rule.action or {}
                result = self._result(rule, context, action, match_basis="validation")
                matches.append(result)
                if action.get("error_category") and action.get("blocking", action.get("block", False)):
                    priority = int(rule.priority or 0)
                    if blocking_seen and priority < blocking_seen[1]:
                        result.applied = False
                        result.skip_reason = "shadowed_by_higher_priority"
                        result.conflict_with = [blocking_seen[0]]
                        continue
                    if blocking_seen and blocking_seen[1] == priority:
                        result.applied = False
                        result.skip_reason = "conflict"
                        result.conflict_with = [blocking_seen[0]]
                        self.warnings.append(
                            f"Validation rule conflict at priority {priority}: {blocking_seen[0]} vs {rule.rule_id}"
                        )
                        for prior in matches:
                            if prior.rule.rule_id == blocking_seen[0]:
                                prior.conflict_with.append(rule.rule_id)
                        continue
                    blocking_seen = (rule.rule_id, priority)
                status = action.get("status", action.get("validation_status", status or "FAIL"))
                if action.get("code") or action.get("validation_code"):
                    codes.append(action.get("code") or action.get("validation_code"))
                if action.get("notes") or action.get("validation_notes"):
                    notes_parts.append(action.get("notes") or action.get("validation_notes"))
                if action.get("error_category") and action.get("blocking", action.get("block", False)):
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

        applied_replace: Dict[str, Tuple[int, str]] = {}
        for rule in self._sorted(self.rule_pack.drafting_rules):
            context = self._build_context(comment, decision, run_context)
            if matches_rule(rule.match, context):
                action = rule.action or {}
                result = self._result(rule, context, action, match_basis="drafting")
                matches.append(result)
                priority = int(rule.priority or 0)
                if action.get("replace_text"):
                    existing = applied_replace.get("resolution")
                    if existing:
                        if existing[0] > priority:
                            result.applied = False
                            result.skip_reason = "shadowed_by_higher_priority"
                            result.conflict_with = [existing[1]]
                            continue
                        if existing[0] == priority:
                            result.applied = False
                            result.skip_reason = "conflict"
                            result.conflict_with = [existing[1]]
                            self.warnings.append(f"Drafting conflict at priority {priority}: {existing[1]} vs {rule.rule_id}")
                            for prior in matches:
                                if prior.rule.rule_id == existing[1]:
                                    prior.conflict_with.append(rule.rule_id)
                            continue
                    applied_replace["resolution"] = (priority, rule.rule_id)
                    resolution_text = action["replace_text"].format(**context).strip()
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
                    matches.append(
                        self._result(
                            rule,
                            context,
                            rule.action or {},
                            match_basis="canonical_term",
                        )
                    )
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
