from __future__ import annotations

from collections import defaultdict
from typing import Iterable, List, Tuple

from ..models import AnalyzedComment, SectionIssueBrief


def _theme_from_comment(comment: AnalyzedComment) -> str:
    if comment.intent_classification == "TECHNICAL_CHALLENGE":
        return "technical method clarification"
    if comment.intent_classification == "REQUEST_CHANGE":
        return "requested report change"
    if comment.intent_classification == "SUGGEST_EDIT":
        return "editorial cleanup"
    return "clarification"


def build_section_briefs(comments: Iterable[AnalyzedComment]) -> List[SectionIssueBrief]:
    grouped: defaultdict[str, list[AnalyzedComment]] = defaultdict(list)
    for comment in comments:
        grouped[comment.section or "Unspecified"].append(comment)

    briefs: List[SectionIssueBrief] = []
    for section, bucket in grouped.items():
        themes = sorted({(_theme_from_comment(c)) for c in bucket})
        revision_strategy = [
            "Add short purpose paragraph for the section.",
            "Clarify terminology and assumptions raised in comments.",
            "Ensure examples align with analytical intent rather than policy.",
        ]
        briefs.append(SectionIssueBrief(section=section, total_comments=len(bucket), themes=themes, revision_strategy=revision_strategy))
    return briefs


def top_briefing_points(briefs: Iterable[SectionIssueBrief], limit: int = 4) -> List[str]:
    sorted_briefs = sorted(briefs, key=lambda b: b.total_comments, reverse=True)
    return [f"{brief.section}: {brief.total_comments} comments focused on {', '.join(brief.themes)}" for brief in sorted_briefs[:limit]]
