from __future__ import annotations

import re

from ..models import SectionRewrite


def validate_section_rewrite(rewrite: SectionRewrite) -> SectionRewrite:
    codes = list(rewrite.validation_codes or [])
    lowered = (rewrite.revised_text or "").lower()

    if not (rewrite.revised_text or "").strip():
        codes.append("REV2_EMPTY")
    elif len((rewrite.revised_text or "").split()) < 8:
        codes.append("REV2_FRAGMENTED")

    meta_triggers = ["shared fix", "patch", "source text reference", "rewritten", "draft mode", "rewrite"]
    if any(trigger in lowered for trigger in meta_triggers):
        codes.append("REV2_META_COMMENTARY")

    if lowered.count(";") >= 3 or "|" in rewrite.revised_text:
        codes.append("REV2_PATCH_STITCHING")

    if re.search(r"\b[~]?l\d+(?:[:)\-]?\s*)", rewrite.revised_text or "", flags=re.IGNORECASE):
        codes.append("REV2_SOURCE_DUMP")

    figure_patterns = re.finditer(r"(figure|table)\s+\d+", lowered)
    for match in figure_patterns:
        span_text = lowered[match.start() : match.end() + 40]
        if any(word in span_text for word in ["depict", "illustrat", "redrawn", "recreate", "shows"]) and "unchanged" not in span_text:
            codes.append("REV2_FIGURE_RECREATION_ATTEMPT")

    if not rewrite.grounded_from_original_text and rewrite.grounding_quality in {"LOW", "NONE"} and not rewrite.source_patch_ids:
        codes.append("REV2_LOW_GROUNDEDNESS")

    if not rewrite.source_comment_ids:
        codes.append("REV2_UNSUPPORTED_ASSERTION")

    unique_codes = list(dict.fromkeys(codes))
    rewrite.validation_codes = unique_codes

    if "REV2_EMPTY" in unique_codes or "REV2_FRAGMENTED" in unique_codes:
        rewrite.confidence = "LOW"
    elif {"REV2_META_COMMENTARY", "REV2_PATCH_STITCHING", "REV2_SOURCE_DUMP", "REV2_LOW_GROUNDEDNESS"} & set(unique_codes):
        rewrite.confidence = "LOW" if rewrite.confidence != "LOW" else rewrite.confidence
    elif unique_codes and rewrite.confidence == "HIGH":
        rewrite.confidence = "MEDIUM"
    return rewrite
