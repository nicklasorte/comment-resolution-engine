from __future__ import annotations

from collections import Counter, defaultdict
from typing import Iterable, List

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
        intent_themes = [_theme_from_comment(c) for c in bucket]
        cluster_themes = [c.cluster_label for c in bucket if c.cluster_label]
        top_phrases = [phrase for phrase, _ in Counter(cluster_themes).most_common(3) if phrase]
        combined_themes = sorted({*intent_themes, *top_phrases})
        revision_strategy: list[str] = []
        if any(c.intent_classification == "TECHNICAL_CHALLENGE" for c in bucket):
            revision_strategy.append("Add purpose paragraph explaining analytical intent vs. regulatory effect.")
            revision_strategy.append("Clarify assumptions and tolerance values referenced in comments.")
        if any(c.normalized_type == "EDITORIAL" for c in bucket):
            revision_strategy.append("Apply terminology cleanup to maintain consistent vocabulary.")
        if not revision_strategy:
            revision_strategy.append("Summarize and respond to clarification requests in plain language.")

        briefs.append(SectionIssueBrief(section=section, total_comments=len(bucket), themes=combined_themes, revision_strategy=revision_strategy))
    return briefs


def top_briefing_points(briefs: Iterable[SectionIssueBrief], limit: int = 4) -> List[str]:
    sorted_briefs = sorted(briefs, key=lambda b: b.total_comments, reverse=True)
    return [f"{brief.section}: {brief.total_comments} comments focused on {', '.join(brief.themes)}" for brief in sorted_briefs[:limit]]
