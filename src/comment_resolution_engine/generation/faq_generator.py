from __future__ import annotations

from collections import defaultdict
from typing import Iterable, List

from ..models import AnalyzedComment, FAQEntry


def generate_faq(comments: Iterable[AnalyzedComment]) -> List[FAQEntry]:
    clustered: defaultdict[str, list[AnalyzedComment]] = defaultdict(list)
    for comment in comments:
        if comment.cluster_id:
            clustered[comment.cluster_id].append(comment)

    faqs: List[FAQEntry] = []
    counter = 1
    for cluster_id, cluster_comments in clustered.items():
        if len(cluster_comments) < 2:
            continue
        question = f"What is the common resolution for cluster {cluster_id}?"
        answer = cluster_comments[0].effective_comment or cluster_comments[0].effective_suggested_text or "Clarification has been provided in the report."
        related = [c.id for c in cluster_comments]
        sections = sorted({c.section for c in cluster_comments if c.section})
        faqs.append(
            FAQEntry(
                faq_id=f"FAQ-{counter:02d}",
                question=question,
                answer=answer,
                related_comments=related,
                affected_sections=sections,
            )
        )
        counter += 1
    return faqs
