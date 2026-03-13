from __future__ import annotations

from typing import Any, Dict, Iterable


def _normalize(value: Any) -> str:
    return str(value).strip().lower()


def _as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def _text_from_context(context: Dict[str, Any]) -> str:
    text_parts = []
    for key in ("text", "effective_comment", "combined_text"):
        if context.get(key):
            text_parts.append(str(context[key]))
    return " ".join(text_parts)


def _contains(haystack: str, needles: Iterable[str]) -> bool:
    lowered = haystack.lower()
    for needle in needles:
        if _normalize(needle) in lowered:
            return True
    return False


def matches_rule(match_spec: Dict[str, Any], context: Dict[str, Any]) -> bool:
    if not match_spec:
        return True

    text = _text_from_context(context)

    if "text_contains" in match_spec:
        if not _contains(text, _as_list(match_spec["text_contains"])):
            return False

    if "normalized_contains" in match_spec:
        if not _contains(" ".join(text.split()), _as_list(match_spec["normalized_contains"])):
            return False

    if "field_equals" in match_spec:
        for field, expected in match_spec["field_equals"].items():
            actual = context.get(field)
            if actual is None:
                return False
            if _normalize(actual) != _normalize(expected):
                return False

    if "field_in" in match_spec:
        for field, options in match_spec["field_in"].items():
            actual = context.get(field)
            if _normalize(actual) not in {_normalize(opt) for opt in _as_list(options)}:
                return False

    if "boolean_true" in match_spec:
        for field in _as_list(match_spec["boolean_true"]):
            if not context.get(field):
                return False

    if "numeric_equals" in match_spec:
        for field, expected in match_spec["numeric_equals"].items():
            try:
                actual_num = float(context.get(field))
                expected_num = float(expected)
            except (TypeError, ValueError):
                return False
            if actual_num != expected_num:
                return False

    if "list_contains" in match_spec:
        for field, expected in match_spec["list_contains"].items():
            values = context.get(field) or []
            if _normalize(expected) not in {_normalize(v) for v in values}:
                return False

    return True
