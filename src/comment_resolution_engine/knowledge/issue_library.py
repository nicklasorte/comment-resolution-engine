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
]


def find_issue(issue_type: str) -> dict | None:
    for issue in ISSUE_LIBRARY:
        if issue["issue_type"] == issue_type:
            return issue
    return None
