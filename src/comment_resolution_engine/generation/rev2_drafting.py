from __future__ import annotations

import re
from typing import Dict, Iterable, List, Sequence

from ..ingest.pdf_parser import PdfContext
from ..knowledge.canonical_definitions import lookup_definition
from ..models import AnalyzedComment, ResolutionDecision, SectionRewrite, SharedResolution

DEFAULT_DRAFT_MODE = "CLEAN_REWRITE"
DRAFT_MODES = {"MINIMAL_EDIT", "CLEAN_REWRITE", "TECHNICAL_CLARIFICATION", "EXECUTIVE_PLAIN_LANGUAGE"}


def _normalize_mode(mode: str) -> str:
    candidate = (mode or "").strip().upper()
    return candidate if candidate in DRAFT_MODES else DEFAULT_DRAFT_MODE


def _parse_section_key(section: str) -> tuple[int, ...]:
    parts = [p for p in re.split(r"[^\d]+", str(section)) if p.isdigit()]
    return tuple(int(p) for p in parts)


def _collect_original_text(comments: Sequence[AnalyzedComment]) -> str:
    contexts: list[str] = []
    for comment in comments:
        if comment.report_context:
            contexts.append(comment.report_context)
    if contexts:
        deduped = list(dict.fromkeys(contexts))
        return " | ".join(deduped)
    return "Original section text unavailable from PDF context; rely on matrix and comment history."


def _derive_revision_themes(comments: Sequence[AnalyzedComment], shared_resolutions: list[SharedResolution]) -> list[str]:
    themes: list[str] = []
    cluster_labels = [c.cluster_label for c in comments if c.cluster_label]
    intents = [c.intent_classification for c in comments if c.intent_classification]
    heat_levels = [c.heat_level for c in comments if c.heat_level]
    if cluster_labels:
        themes.extend(cluster_labels[:3])
    if any(intent == "TECHNICAL_CHALLENGE" for intent in intents):
        themes.append("clarify methodology and technical assumptions")
    if any(intent == "REQUEST_CLARIFICATION" for intent in intents):
        themes.append("respond to recurring clarification requests")
    if any(intent == "SUGGEST_EDIT" for intent in intents):
        themes.append("streamline wording and terminology")
    if any(intent == "REQUEST_CHANGE" for intent in intents):
        themes.append("address requested report changes")
    if any(level == "STRUCTURALLY_UNSTABLE" for level in heat_levels):
        themes.append("stabilize high-volume section")

    section_id = comments[0].section or "Unspecified"
    if any(sr.target_section == section_id for sr in shared_resolutions):
        themes.append("apply shared fix across clustered comments")

    deduped = list(dict.fromkeys([t for t in themes if t]))
    return deduped or ["summarize and reconcile comment feedback"]


def _shared_fix_texts(section_id: str, shared_resolutions: list[SharedResolution]) -> list[str]:
    fixes = [sr.shared_fix_text for sr in shared_resolutions if sr.target_section == section_id and sr.shared_fix_text]
    return list(dict.fromkeys(fixes))


def _patch_candidates(
    comments: Sequence[AnalyzedComment],
    decision_lookup: Dict[str, ResolutionDecision],
) -> list[str]:
    prioritized: list[str] = []
    for comment in comments:
        decision = decision_lookup.get(comment.id)
        if not decision or not decision.patch_text:
            continue
        if decision.patch_confidence in {"HIGH", "MEDIUM"}:
            prioritized.append(decision.patch_text)
    if prioritized:
        return list(dict.fromkeys(prioritized))
    fallbacks: list[str] = []
    for comment in comments:
        decision = decision_lookup.get(comment.id)
        if decision and decision.resolution_text:
            fallbacks.append(decision.resolution_text)
    return list(dict.fromkeys(fallbacks))


def _canonical_definition_lines(comments: Sequence[AnalyzedComment]) -> list[str]:
    definitions: list[str] = []
    for comment in comments:
        if comment.canonical_term_used:
            definition = lookup_definition(comment.canonical_term_used)
            if definition:
                definitions.append(definition)
    return list(dict.fromkeys(definitions))


def _compose_revised_text(
    section_id: str,
    draft_mode: str,
    themes: list[str],
    shared_fixes: list[str],
    patch_candidates: list[str],
    canonical_definitions: list[str],
    original_text: str,
) -> str:
    lead_in = ""
    if draft_mode == "MINIMAL_EDIT":
        lead_in = f"Section {section_id} keeps its structure; targeted edits address: {', '.join(themes)}."
    elif draft_mode == "TECHNICAL_CLARIFICATION":
        lead_in = f"Section {section_id} now foregrounds methodology, assumptions, and limitations tied to: {', '.join(themes)}."
    elif draft_mode == "EXECUTIVE_PLAIN_LANGUAGE":
        lead_in = f"Section {section_id} is retold in plain language so decision-makers can see what changes and why ({', '.join(themes)})."
    else:
        lead_in = f"Section {section_id} is rewritten for coherence while resolving: {', '.join(themes)}."

    paragraphs: list[str] = [lead_in]

    if shared_fixes:
        paragraphs.append(f"Shared fixes applied for clustered feedback: {'; '.join(shared_fixes)}")

    if patch_candidates:
        paragraphs.append(f"Integrated updates drawn from accepted patches: {'; '.join(patch_candidates)}")

    if canonical_definitions:
        paragraphs.append(f"Canonical definitions retained for consistency: {'; '.join(canonical_definitions)}")

    if draft_mode == "EXECUTIVE_PLAIN_LANGUAGE":
        paragraphs.append("Summary for non-technical readers: the section keeps the same findings, emphasizes intent, and consolidates caveats.")
    elif draft_mode == "TECHNICAL_CLARIFICATION":
        paragraphs.append("Technical emphasis: explicitly state analytical scope, key tolerances, and any non-regulatory nature of cited metrics.")

    if not patch_candidates and not shared_fixes:
        paragraphs.append("No high-confidence patch text was available; edits lean on existing section wording.")

    paragraphs.append(f"Source text reference: {original_text}")
    return " ".join([p for p in paragraphs if p])


def _revision_rationale(themes: list[str], shared_fixes: list[str], patch_candidates: list[str]) -> str:
    rationale_parts: list[str] = []
    if shared_fixes:
        rationale_parts.append("Consolidates shared fixes across clustered comments.")
    if patch_candidates:
        rationale_parts.append("Uses accepted patch text and contextual clarifications.")
    rationale_parts.append(f"Addresses revision themes: {', '.join(themes)}.")
    return " ".join(rationale_parts)


def _context_confidence_summary(comments: Sequence[AnalyzedComment]) -> str:
    counters: Dict[str, int] = {}
    for comment in comments:
        key = comment.context_confidence or "UNKNOWN"
        counters[key] = counters.get(key, 0) + 1
    return " | ".join(f"{k}:{v}" for k, v in sorted(counters.items()))


def _detect_open_issues(
    comments: Sequence[AnalyzedComment],
    original_text: str,
    decision_lookup: Dict[str, ResolutionDecision] | None,
) -> list[str]:
    issues: list[str] = []
    dispositions = {decision_lookup.get(c.id).disposition for c in comments if decision_lookup and decision_lookup.get(c.id)}
    if len(dispositions) > 1:
        issues.append("CONFLICTING_COMMENTS")
    if not original_text or "unavailable" in original_text.lower():
        issues.append("MISSING_SECTION_TEXT")
    if any(c.context_confidence in {"NO_CONTEXT_FOUND", "PAGE_APPROXIMATION"} for c in comments):
        issues.append("LOW_CONTEXT_CONFIDENCE")
    if any((c.patch_confidence or "").upper() == "LOW" for c in comments):
        issues.append("PATCH_CONFLICT")
    return list(dict.fromkeys(issues))


def _score_confidence(open_issues: list[str]) -> str:
    if any(issue in {"MISSING_SECTION_TEXT", "CONFLICTING_COMMENTS"} for issue in open_issues):
        return "LOW"
    if open_issues:
        return "MEDIUM"
    return "HIGH"


def build_section_rewrites(
    comments: Iterable[AnalyzedComment],
    decision_lookup: Dict[str, ResolutionDecision],
    shared_resolutions: Iterable[SharedResolution],
    draft_mode: str = DEFAULT_DRAFT_MODE,
    draft_sections: list[str] | None = None,
    high_priority_only: bool = False,
    require_shared_fix: bool = False,
    heat_levels: Dict[str, tuple[int, str]] | None = None,
    pdf_context: PdfContext | None = None,
) -> List[SectionRewrite]:
    grouped: Dict[str, list[AnalyzedComment]] = {}
    for comment in comments:
        section = comment.section or "Unspecified"
        grouped.setdefault(section, []).append(comment)

    target_sections = set(grouped.keys())
    if draft_sections:
        requested = {s.strip() for s in draft_sections if s}
        target_sections = {s for s in target_sections if s in requested}
    if high_priority_only and heat_levels:
        target_sections = {s for s in target_sections if heat_levels.get(s, (0, ""))[1] in {"HIGH", "STRUCTURALLY_UNSTABLE"}}
    shared_by_section: Dict[str, list[SharedResolution]] = {}
    for sr in shared_resolutions:
        shared_by_section.setdefault(sr.target_section or "Unspecified", []).append(sr)
    if require_shared_fix:
        target_sections = {s for s in target_sections if s in shared_by_section}

    rewrites: list[SectionRewrite] = []
    normalized_mode = _normalize_mode(draft_mode)
    for section_id in sorted(target_sections, key=_parse_section_key):
        bucket = grouped.get(section_id, [])
        if not bucket:
            continue
        section_shared = shared_by_section.get(section_id, [])
        themes = _derive_revision_themes(bucket, section_shared)
        original_text = _collect_original_text(bucket)
        shared_fixes = _shared_fix_texts(section_id, section_shared)
        patch_candidates = _patch_candidates(bucket, decision_lookup)
        canonical_definitions = _canonical_definition_lines(bucket)

        revised_text = _compose_revised_text(
            section_id=section_id,
            draft_mode=normalized_mode,
            themes=themes,
            shared_fixes=shared_fixes,
            patch_candidates=patch_candidates,
            canonical_definitions=canonical_definitions,
            original_text=original_text,
        )
        rationale = _revision_rationale(themes, shared_fixes, patch_candidates)
        open_issues = _detect_open_issues(bucket, original_text, decision_lookup)
        confidence = _score_confidence(open_issues)
        master_ids = [sr.master_resolution_id for sr in section_shared]
        canonical_terms_used = [c.canonical_term_used for c in bucket if c.canonical_term_used]

        rewrites.append(
            SectionRewrite(
                section_id=section_id,
                section_title=section_id,
                draft_mode=normalized_mode,
                source_comment_ids=[c.id for c in bucket],
                source_cluster_ids=sorted({c.cluster_id for c in bucket if c.cluster_id}),
                source_master_resolution_ids=sorted(dict.fromkeys(master_ids)),
                revision_themes=themes,
                original_text=original_text,
                revised_text=revised_text,
                revision_rationale=rationale,
                open_issues=open_issues,
                confidence=confidence,
                canonical_terms_used=sorted(dict.fromkeys(canonical_terms_used)),
                context_confidence_summary=_context_confidence_summary(bucket),
            )
        )
    return rewrites


def assemble_rev2_draft(rewrites: Iterable[SectionRewrite]) -> list[str]:
    lines: list[str] = ["# Rev-2 Draft Narrative", "Figures and tables remain unchanged from the prior draft unless noted.", ""]
    sorted_rewrites = sorted(list(rewrites), key=lambda r: _parse_section_key(r.section_id))
    for rewrite in sorted_rewrites:
        lines.append(f"## Section {rewrite.section_id} ({rewrite.draft_mode})")
        lines.append(rewrite.revised_text)
        lines.append(f"Revision themes: {', '.join(rewrite.revision_themes)}.")
        if rewrite.open_issues:
            lines.append(f"Open issues: {', '.join(rewrite.open_issues)}.")
        else:
            lines.append("Open issues: none noted.")
        lines.append("[Figure/Table references remain unchanged from prior draft.]")
        lines.append("")

    lines.append("## Revision Notes Appendix")
    for rewrite in sorted_rewrites:
        lines.append(f"- Section {rewrite.section_id}: confidence {rewrite.confidence}; sources {len(rewrite.source_comment_ids)} comments; themes {', '.join(rewrite.revision_themes)}.")
    return lines
