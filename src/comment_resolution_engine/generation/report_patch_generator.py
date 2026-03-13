from __future__ import annotations

from collections import defaultdict
from typing import Iterable, List

from ..models import AnalyzedComment, PatchRecord, ResolutionDecision, SharedResolution


def _action_type(comment: AnalyzedComment, decision: ResolutionDecision) -> str:
    if decision.disposition == "Partial Accept":
        return "CLARIFY"
    if comment.normalized_type == "EDITORIAL":
        return "CLARIFY"
    if comment.effective_suggested_text:
        return "REPLACE"
    if comment.intent_classification == "REQUEST_CLARIFICATION":
        return "CLARIFY"
    return "APPEND"


def build_patch_records(comments: Iterable[AnalyzedComment], decision_lookup: dict[str, ResolutionDecision]) -> List[PatchRecord]:
    patches: List[PatchRecord] = []
    for comment in comments:
        decision = decision_lookup.get(comment.id)
        if not decision or decision.disposition == "Reject":
            continue

        if not decision.patch_text:
            continue

        action = _action_type(comment, decision)
        target_lines = str(comment.line) if comment.line is not None else ""
        rationale = decision.resolution_text or comment.effective_comment or "Implements accepted comment."
        patches.append(
            PatchRecord(
                comment_id=comment.id,
                target_section=comment.section or "",
                target_lines=target_lines,
                action_type=action,
                old_text=comment.report_context or "",
                new_text=decision.patch_text,
                rationale=rationale,
                patch_source=decision.patch_source,
                confidence=decision.patch_confidence,
                shared_resolution_id=comment.shared_resolution_id or "",
                source_revision=comment.revision,
                resolved_against_revision=comment.resolved_against_revision or comment.revision,
                provenance_record_id=comment.provenance_record_id or "",
                provenance=comment.provenance or {},
                generation_mode=decision.generation_mode,
                matched_rule_types=decision.matched_rule_types or [],
                rule_id=decision.rule_id,
                rule_source=decision.rule_source,
                rule_version=decision.rule_version,
                rules_profile=decision.rules_profile,
                rules_version=decision.rules_version,
            )
        )
    return patches


def build_shared_resolutions(comments: Iterable[AnalyzedComment], decision_lookup: dict[str, ResolutionDecision]) -> List[SharedResolution]:
    cluster_to_comments: defaultdict[str, list[str]] = defaultdict(list)
    for comment in comments:
        decision = decision_lookup.get(comment.id)
        if not decision or decision.disposition == "Reject":
            continue
        if comment.cluster_id:
            cluster_to_comments[comment.cluster_id].append(comment.id)

    shared: List[SharedResolution] = []
    counter = 1
    for cluster_id, ids in cluster_to_comments.items():
        if len(ids) < 2:
            continue
        target_section = ""
        for comment in comments:
            if comment.id in ids and comment.section:
                target_section = comment.section
                break
        cluster_label = ""
        shared_fix_text = ""
        for comment in comments:
            if comment.id in ids:
                if comment.cluster_label:
                    cluster_label = comment.cluster_label
                decision = decision_lookup.get(comment.id)
                if decision and decision.patch_text:
                    shared_fix_text = decision.patch_text
                    break
                if decision and decision.resolution_text and not shared_fix_text:
                    shared_fix_text = decision.resolution_text
        if not shared_fix_text and cluster_label:
            shared_fix_text = f"Apply consolidated fix for cluster: {cluster_label}"
        shared.append(
            SharedResolution(
                master_resolution_id=f"MR-{counter:02d}",
                linked_comment_ids=ids,
                shared_fix_text=shared_fix_text or "Add consolidated clarification to address overlapping concerns across linked comments.",
                target_section=target_section,
            )
        )
        counter += 1
    return shared
