from __future__ import annotations

from typing import Iterable, List

from ..ingest.pdf_parser import PdfContext
from ..models import CommentRecord, NormalizedComment


CANONICAL_TYPES = {
    "technical": "TECHNICAL",
    "tech": "TECHNICAL",
    "clarification": "CLARIFICATION",
    "clarify": "CLARIFICATION",
    "editorial": "EDITORIAL",
    "grammar": "EDITORIAL",
    "grammatical": "EDITORIAL",
}


def normalize_type(raw_type: str) -> str:
    value = (raw_type or "").strip().lower()
    if not value:
        return ""
    for key, canonical in CANONICAL_TYPES.items():
        if key in value:
            return canonical
    return ""


def derive_effective_comment(notes: str, suggested: str) -> str:
    if notes and str(notes).strip():
        return str(notes).strip()
    if suggested and str(suggested).strip():
        return str(suggested).strip()
    return ""


def derive_effective_suggested_text(suggested: str) -> str:
    return str(suggested).strip() if suggested else ""


def normalize_comments(records: Iterable[CommentRecord], pdf_context: dict[str, PdfContext]) -> List[NormalizedComment]:
    normalized: List[NormalizedComment] = []
    for record in records:
        ntype = normalize_type(record.comment_type) or normalize_type(record.agency_notes) or normalize_type(record.agency_suggested_text)
        effective_comment = derive_effective_comment(record.agency_notes, record.agency_suggested_text)
        effective_suggested_text = derive_effective_suggested_text(record.agency_suggested_text)
        revision = (record.revision or "").strip().lower()
        context, context_confidence = ("", "NO_CONTEXT_FOUND")
        ctx = pdf_context.get(revision) if pdf_context else None
        if ctx:
            context, context_confidence = ctx.extract_window(record.page, record.line, window=5)

        normalized.append(
            NormalizedComment(
                **{k: getattr(record, k) for k in record.__slots__},
                normalized_type=ntype or "CLARIFICATION",
                effective_comment=effective_comment,
                effective_suggested_text=effective_suggested_text,
                report_context=context,
                context_confidence=context_confidence,
            )
        )
    return normalized
