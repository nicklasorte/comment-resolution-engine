from __future__ import annotations

from ..models import SectionRewrite


def validate_section_rewrite(rewrite: SectionRewrite) -> SectionRewrite:
    codes = list(rewrite.validation_codes or [])
    lowered = (rewrite.revised_text or "").lower()

    if not (rewrite.revised_text or "").strip():
        codes.append("REV2_EMPTY")
    elif len((rewrite.revised_text or "").split()) < 8:
        codes.append("REV2_FRAGMENTED")

    if "figure" in lowered or "table" in lowered:
        if "remain unchanged" not in lowered and "unchanged" not in lowered:
            codes.append("REV2_FIGURE_RECREATION_ATTEMPT")

    if rewrite.section_id and rewrite.section_id not in (rewrite.revised_text or ""):
        codes.append("REV2_SECTION_DRIFT")

    if not rewrite.source_comment_ids:
        codes.append("REV2_UNSUPPORTED_ASSERTION")

    unique_codes = list(dict.fromkeys(codes))
    rewrite.validation_codes = unique_codes

    if "REV2_EMPTY" in unique_codes or "REV2_FRAGMENTED" in unique_codes:
        rewrite.confidence = "LOW"
    elif unique_codes and rewrite.confidence == "HIGH":
        rewrite.confidence = "MEDIUM"
    return rewrite
