from __future__ import annotations

ISSUE_LIBRARY = [
    {
        "issue_type": "metric_not_regulatory",
        "canonical_question": "Is the population impact metric determinative of regulatory eligibility?",
        "approved_answer": "No. The metric is an analytical output used to provide context for study findings and does not determine regulatory status.",
        "prior_usage": ["NTIA study templates"],
    },
    {
        "issue_type": "clarify_method_scope",
        "canonical_question": "What is the scope of the methodology results?",
        "approved_answer": "Results communicate analytical behavior and assumptions; they do not create policy requirements.",
        "prior_usage": ["Working papers for spectrum sharing analyses"],
    },
    {
        "issue_type": "protection_zone_methodology",
        "canonical_question": "How should readers interpret the protection zone methodology?",
        "approved_answer": "The protection zone methodology explains analytical boundaries and tolerances to guide further study. It does not prescribe regulatory exclusion zones.",
        "prior_usage": ["Protection zone methodology briefs"],
    },
    {
        "issue_type": "terminology_cleanup",
        "canonical_question": "Why are terminology edits being made?",
        "approved_answer": "Terminology is aligned to maintain internal consistency and avoid implying regulatory positions that are not intended.",
        "prior_usage": ["Editorial alignment efforts"],
    },
]


def find_issue(issue_type: str) -> dict | None:
    for issue in ISSUE_LIBRARY:
        if issue["issue_type"] == issue_type:
            return issue
    return None


def detect_issue_type(text: str) -> str:
    lowered = (text or "").lower()
    if any(token in lowered for token in ("population impact", "impact metric", "population metric")):
        return "metric_not_regulatory"
    if "protection zone" in lowered or "tolerance" in lowered:
        return "protection_zone_methodology"
    if "scope" in lowered or "out of scope" in lowered or "regulatory" in lowered:
        return "clarify_method_scope"
    if "terminology" in lowered or "wording" in lowered:
        return "terminology_cleanup"
    return ""
