from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Tuple

from ..ingest.pdf_parser import PdfContext, parse_line_reference
from ..knowledge.canonical_definitions import lookup_definition
from ..models import AnalyzedComment, ResolutionDecision, SectionRewrite, SharedResolution

DEFAULT_DRAFT_MODE = "CLEAN_REWRITE"
DRAFT_MODES = {"MINIMAL_EDIT", "CLEAN_REWRITE", "TECHNICAL_CLARIFICATION", "EXECUTIVE_PLAIN_LANGUAGE"}

THEME_STOPWORDS = {
    "the",
    "and",
    "for",
    "that",
    "this",
    "with",
    "from",
    "section",
    "draft",
    "report",
    "clarification",
    "clarify",
    "request",
    "change",
    "comment",
    "edit",
    "reword",
    "update",
}


@dataclass(slots=True)
class SectionSourceText:
    text: str
    grounded: bool
    quality: str
    note: str = ""


def _normalize_mode(mode: str) -> str:
    candidate = (mode or "").strip().upper()
    return candidate if candidate in DRAFT_MODES else DEFAULT_DRAFT_MODE


def _parse_section_key(section: str) -> tuple[int, ...]:
    parts = [p for p in re.split(r"[^\d]+", str(section)) if p.isdigit()]
    return tuple(int(p) for p in parts)


def _extract_lines_from_context(context: str) -> list[int]:
    if not context:
        return []
    return [int(m) for m in re.findall(r"[~]?L(\d+)", context)]


def _clean_context_snippet(snippet: str) -> str:
    cleaned = re.sub(r"[~]?L\d+:\s*", "", snippet or "").strip()
    cleaned = re.sub(r"\s*\|\s*", " ", cleaned)
    return cleaned


def _token_overlap_ratio(a: str, b: str) -> float:
    a_tokens = {t for t in re.findall(r"[A-Za-z][\w\-]+", a.lower()) if t not in THEME_STOPWORDS}
    b_tokens = {t for t in re.findall(r"[A-Za-z][\w\-]+", b.lower()) if t not in THEME_STOPWORDS}
    if not a_tokens or not b_tokens:
        return 0.0
    return len(a_tokens & b_tokens) / max(len(a_tokens), len(b_tokens))


def _collect_original_text(comments: Sequence[AnalyzedComment], pdf_context: PdfContext | None) -> SectionSourceText:
    if not comments:
        return SectionSourceText(text="", grounded=False, quality="NONE", note="No comments to reconstruct section text.")

    page_windows: Dict[int, set[int]] = {}
    for comment in comments:
        page = int(comment.page) if comment.page is not None else None
        lines: list[int] = []
        lines.extend(parse_line_reference(comment.line) if comment.line else [])
        lines.extend(_extract_lines_from_context(comment.report_context or ""))
        if not lines:
            continue
        page_key = page
        if page_key is None and pdf_context and pdf_context.pages:
            page_key = next(iter(pdf_context.pages.keys()), None)
        if page_key is None:
            continue
        window = page_windows.setdefault(page_key, set())
        for ln in lines:
            for neighbor in range(max(1, ln - 2), ln + 3):
                window.add(neighbor)

    if pdf_context and (pdf_context.pages or pdf_context.raw_pages) and page_windows:
        assembled_segments: list[str] = []
        grounded_pages = 0
        for page_idx in sorted(page_windows.keys()):
            page_lines = {ln: text for ln, text in pdf_context.pages.get(page_idx, [])}
            chosen = sorted(ln for ln in page_windows[page_idx] if ln in page_lines)
            if not chosen:
                continue
            grounded_pages += 1
            sentences: list[str] = []
            previous = None
            for ln in chosen:
                if previous and ln - previous > 1:
                    sentences.append("")
                sentences.append(page_lines[ln])
                previous = ln
            collapsed = " ".join(part for part in sentences if part.strip())
            if collapsed:
                assembled_segments.append(collapsed)
        if assembled_segments:
            quality = "HIGH" if grounded_pages > 1 or sum(len(seg.split()) for seg in assembled_segments) > 40 else "MEDIUM"
            return SectionSourceText(text="\n\n".join(assembled_segments), grounded=True, quality=quality, note="")

    fallback_contexts: list[str] = []
    for comment in comments:
        if comment.report_context:
            fallback_contexts.append(_clean_context_snippet(comment.report_context))
    fallback_contexts = [c for c in dict.fromkeys(fallback_contexts) if c]
    if fallback_contexts:
        stitched = " ".join(fallback_contexts)
        return SectionSourceText(text=stitched, grounded=False, quality="LOW", note="Used stitched comment contexts; original page text unavailable.")

    return SectionSourceText(text="", grounded=False, quality="NONE", note="Original section text unavailable from PDF context; rely on matrix and comment history.")


def _derive_revision_themes(comments: Sequence[AnalyzedComment], shared_resolutions: list[SharedResolution]) -> list[str]:
    themes: list[str] = []
    cluster_labels = [c.cluster_label for c in comments if c.cluster_label]
    intents = [c.intent_classification for c in comments if c.intent_classification]
    canonical_terms = [c.canonical_term_used for c in comments if c.canonical_term_used]
    resolution_bases = [c.resolution_basis for c in comments if c.resolution_basis]
    text_pool = [c.effective_comment for c in comments if c.effective_comment] + [c.agency_suggested_text for c in comments if c.agency_suggested_text]

    if cluster_labels:
        themes.extend(cluster_labels[:4])

    def _top_keywords(texts: list[str], limit: int = 3) -> list[str]:
        tokens: list[str] = []
        for text in texts:
            words = re.findall(r"[A-Za-z][\w\-]+", text.lower())
            tokens.extend([w for w in words if len(w) > 3 and w not in THEME_STOPWORDS])
        freq = Counter(tokens)
        return [w for w, _ in freq.most_common(limit)]

    keyword_phrases = _top_keywords(text_pool, limit=4)
    if keyword_phrases:
        themes.extend([f"{kw} clarity" for kw in keyword_phrases])

    for basis in resolution_bases:
        if basis:
            themes.append(basis.replace("_", " "))

    for term in canonical_terms:
        if term:
            themes.append(f"define {term.replace('_', ' ')} precisely")

    if any(intent == "TECHNICAL_CHALLENGE" for intent in intents):
        themes.append("explain analytical assumptions and methods")
    if any(intent == "REQUEST_CLARIFICATION" for intent in intents):
        themes.append("resolve recurring clarifications from reviewers")
    if any(intent == "SUGGEST_EDIT" for intent in intents):
        themes.append("tighten wording and terminology where unclear")
    if any(intent == "REQUEST_CHANGE" for intent in intents):
        themes.append("incorporate requested report changes with justification")
    if any((c.heat_level or "").upper() == "STRUCTURALLY_UNSTABLE" for c in comments):
        themes.append("stabilize high-volume or volatile section")

    section_id = comments[0].section or "Unspecified"
    if any(sr.target_section == section_id for sr in shared_resolutions):
        themes.append("harmonize shared fixes across clustered feedback")

    deduped = list(dict.fromkeys([t for t in themes if t]))
    return deduped or ["restate section content and reconcile reviewer themes"]


def _shared_fix_texts(section_id: str, shared_resolutions: list[SharedResolution]) -> list[str]:
    fixes = [sr.shared_fix_text for sr in shared_resolutions if sr.target_section == section_id and sr.shared_fix_text]
    return list(dict.fromkeys(fixes))


def _patch_candidates(
    comments: Sequence[AnalyzedComment],
    decision_lookup: Dict[str, ResolutionDecision],
) -> list[Tuple[str, str]]:
    prioritized: list[Tuple[str, str]] = []
    for comment in comments:
        decision = decision_lookup.get(comment.id)
        if not decision or not decision.patch_text:
            continue
        if decision.patch_confidence in {"HIGH", "MEDIUM"}:
            prioritized.append((decision.patch_text, comment.id))
    if prioritized:
        deduped: list[Tuple[str, str]] = []
        seen: set[str] = set()
        for text, cid in prioritized:
            key = text.strip()
            if key in seen:
                continue
            seen.add(key)
            deduped.append((text, cid))
        return deduped
    fallbacks: list[Tuple[str, str]] = []
    for comment in comments:
        decision = decision_lookup.get(comment.id)
        if decision and decision.resolution_text:
            fallbacks.append((decision.resolution_text, comment.id))
    deduped_fallbacks: list[Tuple[str, str]] = []
    seen_fallbacks: set[str] = set()
    for text, cid in fallbacks:
        key = text.strip()
        if key in seen_fallbacks:
            continue
        seen_fallbacks.add(key)
        deduped_fallbacks.append((text, cid))
    return deduped_fallbacks


def _canonical_definition_lines(comments: Sequence[AnalyzedComment]) -> list[str]:
    definitions: list[str] = []
    for comment in comments:
        if comment.canonical_term_used:
            definition = lookup_definition(comment.canonical_term_used)
            if definition:
                definitions.append(definition)
    return list(dict.fromkeys(definitions))


def _normalize_sentence(text: str) -> str:
    cleaned = _clean_context_snippet(text)
    cleaned = re.sub(r"^(shared fix|shared resolution|patch|accepted patch|fix)\s*[:\-]\s*", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"^(section\s+\d+(?:\.\d+)*)\s*[:\-]?\s*", "", cleaned, flags=re.IGNORECASE).strip()
    if cleaned and cleaned[-1] not in ".?!":
        cleaned += "."
    return cleaned


def _filter_canonical_definitions(canonical_definitions: list[str], themes: list[str], original_text: str) -> list[str]:
    if not canonical_definitions:
        return []
    lowered_themes = " ".join(themes).lower()
    lowered_original = (original_text or "").lower()
    selected: list[str] = []
    for definition in canonical_definitions:
        term = definition.split(":")[0].lower() if ":" in definition else definition.lower()
        if term in lowered_themes or term in lowered_original:
            selected.append(definition)
    return selected


def _split_sentences(text: str) -> list[str]:
    if not text:
        return []
    pieces = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in pieces if p.strip()]


def _compose_revised_text(
    section_id: str,
    draft_mode: str,
    themes: list[str],
    shared_fixes: list[str],
    patch_candidates: list[Tuple[str, str]],
    canonical_definitions: list[str],
    original_text: SectionSourceText,
) -> str:
    themes_text = ", ".join(themes[:3])
    mode_intro = ""
    if draft_mode == "MINIMAL_EDIT":
        mode_intro = f"The section preserves its structure while tightening clarity on {themes_text}."
    elif draft_mode == "TECHNICAL_CLARIFICATION":
        mode_intro = f"The section foregrounds methodology, assumptions, and limits tied to {themes_text}."
    elif draft_mode == "EXECUTIVE_PLAIN_LANGUAGE":
        mode_intro = f"In plain language, the section highlights the main findings and their caveats around {themes_text}."
    else:
        mode_intro = f"The section is presented for coherence, centering {themes_text}."

    base_sentences = _split_sentences(original_text.text)
    normalized_shared = [_normalize_sentence(sf) for sf in shared_fixes]
    normalized_patches = [_normalize_sentence(text) for text, _ in patch_candidates]
    canonical_for_text = _filter_canonical_definitions(canonical_definitions, themes, original_text.text)

    adjustments: list[str] = []
    if normalized_shared:
        adjustments.extend(normalized_shared)
    if normalized_patches:
        adjustments.extend(normalized_patches)

    if canonical_for_text:
        adjustments.extend([_normalize_sentence(defn) for defn in canonical_for_text])

    body: list[str] = []
    if base_sentences:
        # weave adjustments after the first couple of sentences to keep flow
        body.extend(base_sentences[:3])
        remaining_base = base_sentences[3:]
        if adjustments:
            body.extend(adjustments[:3])
        if remaining_base:
            body.extend(remaining_base[:3])
        if len(adjustments) > 3:
            body.extend(adjustments[3:5])
    else:
        # construct from themes and adjustments
        if adjustments:
            body.extend(adjustments[:4])
        else:
            body.append(f"The section addresses {themes_text} with tighter wording and clearer grounding in source material.")

    if draft_mode == "EXECUTIVE_PLAIN_LANGUAGE":
        body.append("For decision-makers, the narrative keeps conclusions intact while underscoring intent, scope, and key caveats.")
    elif draft_mode == "TECHNICAL_CLARIFICATION":
        body.append("Analytical boundaries, tolerance assumptions, and non-regulatory interpretations are stated explicitly.")

    merged = " ".join([mode_intro] + body)
    return re.sub(r"\s+", " ", merged).strip()


def _revision_rationale(
    themes: list[str],
    shared_fixes: list[str],
    patch_candidates: list[Tuple[str, str]],
    grounded_from_original: bool,
) -> str:
    rationale_parts: list[str] = []
    if shared_fixes:
        rationale_parts.append("Consolidates shared fixes across clustered comments.")
    if patch_candidates:
        rationale_parts.append("Uses accepted patch text and contextual clarifications.")
    if grounded_from_original:
        rationale_parts.append("Anchored in reconstructed section text from the PDF context.")
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
    original_text: SectionSourceText,
    decision_lookup: Dict[str, ResolutionDecision] | None,
) -> list[str]:
    issues: list[str] = []

    # detect true conflicts only when requested changes point in incompatible directions
    patch_texts: list[str] = []
    if decision_lookup:
        for c in comments:
            decision = decision_lookup.get(c.id)
            if decision and decision.patch_text and decision.patch_confidence in {"HIGH", "MEDIUM"}:
                patch_texts.append(_normalize_sentence(decision.patch_text))
    unique_patches = [p for p in dict.fromkeys(patch_texts) if p]
    if len(unique_patches) > 1:
        baseline = unique_patches[0]
        if any(_token_overlap_ratio(baseline, p) < 0.35 for p in unique_patches[1:]):
            issues.append("CONFLICTING_COMMENTS")

    if not original_text.text or original_text.quality == "NONE":
        issues.append("MISSING_SECTION_TEXT")
    elif original_text.quality == "LOW":
        issues.append("LOW_CONTEXT_CONFIDENCE")
    if any(c.context_confidence in {"NO_CONTEXT_FOUND", "PAGE_APPROXIMATION"} for c in comments):
        issues.append("LOW_CONTEXT_CONFIDENCE")
    if any((c.patch_confidence or "").upper() == "LOW" for c in comments):
        issues.append("PATCH_CONFLICT")
    return list(dict.fromkeys(issues))


def _score_confidence(
    open_issues: list[str],
    original_text: SectionSourceText,
    patch_count: int,
    shared_fix_count: int,
) -> str:
    score = 2  # baseline medium
    if original_text.grounded and original_text.quality in {"HIGH", "MEDIUM"}:
        score += 1
    elif original_text.quality in {"LOW", "NONE"}:
        score -= 1

    if patch_count >= 2 or shared_fix_count >= 1:
        score += 1
    if patch_count == 0 and shared_fix_count == 0 and original_text.quality == "LOW":
        score -= 1

    if "CONFLICTING_COMMENTS" in open_issues or "MISSING_SECTION_TEXT" in open_issues:
        score -= 2
    if "PATCH_CONFLICT" in open_issues:
        score -= 1

    if score >= 3:
        return "HIGH"
    if score <= 0:
        return "LOW"
    return "MEDIUM"


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
        original_text = _collect_original_text(bucket, pdf_context)
        shared_fixes = _shared_fix_texts(section_id, section_shared)
        patch_candidates = _patch_candidates(bucket, decision_lookup)
        canonical_definitions = _canonical_definition_lines(bucket)
        source_patch_ids = [cid for _, cid in patch_candidates]

        revised_text = _compose_revised_text(
            section_id=section_id,
            draft_mode=normalized_mode,
            themes=themes,
            shared_fixes=shared_fixes,
            patch_candidates=patch_candidates,
            canonical_definitions=canonical_definitions,
            original_text=original_text,
        )
        rationale = _revision_rationale(themes, shared_fixes, patch_candidates, original_text.grounded)
        open_issues = _detect_open_issues(bucket, original_text, decision_lookup)
        confidence = _score_confidence(open_issues, original_text, len(patch_candidates), len(shared_fixes))
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
                original_text=original_text.text,
                revised_text=revised_text,
                revision_rationale=rationale,
                open_issues=open_issues,
                confidence=confidence,
                canonical_terms_used=sorted(dict.fromkeys(canonical_terms_used)),
                context_confidence_summary=_context_confidence_summary(bucket),
                shared_fix_count=len(shared_fixes),
                source_patch_ids=source_patch_ids,
                source_patch_count=len(source_patch_ids),
                grounded_from_original_text=original_text.grounded,
                grounding_quality=original_text.quality,
            )
        )
    return rewrites


def assemble_rev2_draft(rewrites: Iterable[SectionRewrite]) -> tuple[list[str], list[str]]:
    draft_lines: list[str] = ["# Rev-2 Draft Narrative", ""]
    appendix_lines: list[str] = ["# Rev-2 Revision Notes", ""]
    sorted_rewrites = sorted(list(rewrites), key=lambda r: _parse_section_key(r.section_id))
    for rewrite in sorted_rewrites:
        draft_lines.append(f"## Section {rewrite.section_id}")
        draft_lines.append(rewrite.revised_text.strip())
        draft_lines.append("")

        appendix_lines.append(f"## Section {rewrite.section_id}")
        appendix_lines.append(f"- Mode: {rewrite.draft_mode}")
        appendix_lines.append(f"- Themes: {', '.join(rewrite.revision_themes)}")
        appendix_lines.append(f"- Confidence: {rewrite.confidence}")
        appendix_lines.append(f"- Grounding: {'grounded in PDF text' if rewrite.grounded_from_original_text else 'limited grounding'} ({rewrite.grounding_quality})")
        appendix_lines.append(f"- Source comments: {len(rewrite.source_comment_ids)}; patches: {rewrite.source_patch_count}; shared fixes: {rewrite.shared_fix_count}")
        if rewrite.open_issues:
            appendix_lines.append(f"- Open issues: {', '.join(rewrite.open_issues)}")
        if rewrite.validation_codes:
            appendix_lines.append(f"- Validation flags: {', '.join(rewrite.validation_codes)}")
        appendix_lines.append("")

    return draft_lines, appendix_lines
