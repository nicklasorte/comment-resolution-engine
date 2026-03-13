from __future__ import annotations

from typing import Any, Dict, Iterable, List

from .models import RuleMatchResult

GENERATION_MODE_EXTERNAL = "EXTERNAL_RULE"
GENERATION_MODE_LOCAL = "LOCAL_FALLBACK"
GENERATION_MODE_HYBRID = "HYBRID_RULE_PLUS_FALLBACK"


def summarize_rule_matches(
    matches: Iterable[RuleMatchResult],
    run_metadata: Dict[str, Any],
    *,
    fallback_mode: str = GENERATION_MODE_LOCAL,
) -> Dict[str, Any]:
    match_list: List[RuleMatchResult] = list(matches or [])
    primary = match_list[0] if match_list else None
    mode = GENERATION_MODE_EXTERNAL if match_list else fallback_mode
    if match_list and fallback_mode == GENERATION_MODE_HYBRID:
        mode = GENERATION_MODE_HYBRID
    return {
        "primary_rule_id": primary.rule.rule_id if primary else "",
        "rule_id": primary.rule.rule_id if primary else "",
        "rule_source": (primary.rule.source if primary else "") or run_metadata.get("rules_path", ""),
        "rule_version": (primary.rule.version if primary else "") or run_metadata.get("rules_version") or run_metadata.get("rules_version"),
        "rules_profile": run_metadata.get("rules_profile") or "",
        "rules_version": run_metadata.get("rules_version") or "",
        "matched_rule_types": [m.rule.rule_type for m in match_list],
        "applied_rules": [m.as_metadata() for m in match_list],
        "generation_mode": mode,
    }
