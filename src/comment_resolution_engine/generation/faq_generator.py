from __future__ import annotations

from collections import defaultdict
from typing import Iterable, List

from ..knowledge.canonical_definitions import lookup_definition, match_canonical_term
from ..knowledge.issue_library import detect_issue_type, find_issue
from ..models import AnalyzedComment, FAQEntry, ResolutionDecision


def _build_answer(cluster_comments: list[AnalyzedComment], decision_lookup: dict[str, ResolutionDecision] | None) -> str:
    aggregated = " ".join([c.effective_comment or "" for c in cluster_comments])
    canonical_term = match_canonical_term(aggregated + " " + (cluster_comments[0].cluster_label or ""))
    if canonical_term:
        definition = lookup_definition(canonical_term)
        if definition:
            return definition

    issue_type = detect_issue_type(aggregated + " " + (cluster_comments[0].cluster_label or ""))
    issue = find_issue(issue_type) if issue_type else None
    if issue:
        return issue.get("approved_answer", "") or aggregated

    if decision_lookup:
        for comment in cluster_comments:
            decision = decision_lookup.get(comment.id)
            if decision and decision.patch_text:
                return f"{decision.resolution_text} Patch: {decision.patch_text}"

    representative = cluster_comments[0]
    return representative.effective_comment or representative.effective_suggested_text or "Clarification has been provided in the report."


def generate_faq(comments: Iterable[AnalyzedComment], decision_lookup: dict[str, ResolutionDecision] | None = None) -> List[FAQEntry]:
    clustered: defaultdict[str, list[AnalyzedComment]] = defaultdict(list)
    for comment in comments:
        if comment.cluster_id:
            clustered[comment.cluster_id].append(comment)

    faqs: List[FAQEntry] = []
    counter = 1
    for cluster_id, cluster_comments in clustered.items():
        if len(cluster_comments) < 2:
            continue
        cluster_label = cluster_comments[0].cluster_label or f"Cluster {cluster_id}"
        question = f"How are we addressing {cluster_label.lower()}?"
        answer = _build_answer(cluster_comments, decision_lookup)
        related = [c.id for c in cluster_comments]
        sections = sorted({c.section for c in cluster_comments if c.section})
        faqs.append(
            FAQEntry(
                faq_id=f"FAQ-{counter:02d}",
                normalized_question=question,
                canonical_answer=answer,
                related_comment_ids=related,
                affected_sections=sections,
            )
        )
        counter += 1
    return faqs
