from __future__ import annotations

from collections import defaultdict
from typing import Iterable, List, Tuple

from ..models import AnalyzedComment, PatchRecord, SharedResolution


def _action_type(comment: AnalyzedComment) -> str:
    if comment.normalized_type == "EDITORIAL":
        return "CLARIFY"
    if comment.effective_suggested_text:
        return "REPLACE"
    if comment.intent_classification == "REQUEST_CLARIFICATION":
        return "CLARIFY"
    return "APPEND"


def build_patch_records(comments: Iterable[AnalyzedComment], disposition_lookup: dict[str, str], resolutions: dict[str, str]) -> List[PatchRecord]:
    patches: List[PatchRecord] = []
    for comment in comments:
        disposition = disposition_lookup.get(comment.id, "Accept")
        if disposition != "Accept":
            continue

        action = _action_type(comment)
        target_lines = str(comment.line) if comment.line is not None else ""
        rationale = comment.effective_comment or "Implements accepted comment."
        patches.append(
            PatchRecord(
                comment_id=comment.id,
                target_section=comment.section or "",
                target_lines=target_lines,
                action_type=action,
                old_text=comment.report_context or "",
                new_text=resolutions.get(comment.id, "") or comment.effective_suggested_text or comment.effective_comment,
                rationale=rationale,
            )
        )
    return patches


def build_shared_resolutions(comments: Iterable[AnalyzedComment], disposition_lookup: dict[str, str]) -> List[SharedResolution]:
    cluster_to_comments: defaultdict[str, list[str]] = defaultdict(list)
    for comment in comments:
        if disposition_lookup.get(comment.id, "Accept") != "Accept":
            continue
        if comment.cluster_id:
            cluster_to_comments[comment.cluster_id].append(comment.id)

    shared: List[SharedResolution] = []
    counter = 1
    for cluster_id, ids in cluster_to_comments.items():
        if len(ids) < 2:
            continue
        shared.append(
            SharedResolution(
                master_resolution_id=f"MR-{counter:02d}",
                linked_comment_ids=ids,
                shared_fix_text="Add consolidated clarification to address overlapping concerns across linked comments.",
            )
        )
        counter += 1
    return shared
