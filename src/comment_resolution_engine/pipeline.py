from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Iterable, List

from .analysis import assign_clusters, classify_intent, group_by_section, heat_map
from .config import load_column_mapping
from .excel_io import write_resolution_workbook
from .generation import (
    build_patch_records,
    build_resolution_decision,
    build_section_briefs,
    build_shared_resolutions,
    generate_faq,
    top_briefing_points,
)
from .ingest import load_pdf_context, read_comment_matrix
from .models import AnalyzedComment
from .normalize import normalize_comments
from .validation import validate_resolution


def _row_status(status: str) -> str:
    status_text = (status or "").strip().lower()
    return "Complete" if status_text in {"complete", "completed", "closed", "resolved", "done"} else "Draft"


def _resolution_task(comment: AnalyzedComment, disposition: str) -> str:
    context_note = "Context available" if comment.report_context else "No PDF context"
    return f"Resolve comment {comment.id} as {disposition}. Section {comment.section or 'N/A'}, line {comment.line or 'N/A'}. {context_note}."


def _hydrate_analyzed_comments(normalized) -> List[AnalyzedComment]:
    return [AnalyzedComment(**asdict(n)) for n in normalized]


def _set_column(output_df, mapping, canonical_key: str, values: Iterable[str], always_override: bool = False):
    import pandas as pd

    values = list(values)
    series = pd.Series([str(v) if v is not None else "" for v in values], index=output_df.index)
    col_name = mapping.resolve_column_name(output_df.columns, canonical_key)
    if always_override or col_name not in output_df.columns:
        output_df[col_name] = series
        return

    existing = output_df[col_name]
    existing_str = existing.where(existing.notna(), "").astype(str).replace("nan", "")
    output_df[col_name] = existing_str.where(existing_str.str.strip() != "", series)


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def _write_markdown(path: Path, lines: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines))


def run_pipeline(
    comments_path: str | Path,
    report_path: str | Path | None,
    output_path: str | Path,
    config_path: str | Path | None = None,
    patch_output: str | Path | None = None,
    faq_output: str | Path | None = None,
    summary_output: str | Path | None = None,
    briefing_output: str | Path | None = None,
):
    import pandas as pd

    mapping = load_column_mapping(config_path)
    records, normalized_df, raw_df = read_comment_matrix(str(comments_path), mapping)
    pdf_context = load_pdf_context(report_path)

    normalized = normalize_comments(records, pdf_context)
    analyzed = _hydrate_analyzed_comments(normalized)

    cluster_output = assign_clusters(analyzed)
    cluster_ids = cluster_output.assignments
    for comment, cluster_id in zip(analyzed, cluster_ids):
        comment.cluster_id = cluster_id
        cluster_info = cluster_output.clusters.get(cluster_id)
        if cluster_info:
            comment.cluster_label = cluster_info.cluster_label
            comment.cluster_size = cluster_info.cluster_size

    section_groups = group_by_section(analyzed)
    heat_levels = heat_map(section_groups)

    for comment in analyzed:
        comment.section_group = comment.section or "Unspecified"
        comment.intent_classification = classify_intent(comment)
        count, level = heat_levels.get(comment.section_group, (len(section_groups.get(comment.section_group, [])), "LOW"))
        comment.heat_count = count
        comment.heat_level = level

    decisions = [build_resolution_decision(comment) for comment in analyzed]
    decision_lookup = {comment.id: decision for comment, decision in zip(analyzed, decisions)}

    shared_resolutions = build_shared_resolutions(analyzed, decision_lookup)
    shared_lookup = {}
    for sr in shared_resolutions:
        for cid in sr.linked_comment_ids:
            shared_lookup[cid] = sr.master_resolution_id

    for comment in analyzed:
        if comment.id in shared_lookup:
            comment.shared_resolution_id = shared_lookup[comment.id]

    decisions = [validate_resolution(c, decision_lookup[c.id]) for c in analyzed]
    decision_lookup = {comment.id: decision for comment, decision in zip(analyzed, decisions)}
    for comment in analyzed:
        decision = decision_lookup.get(comment.id)
        if decision:
            comment.patch_text = decision.patch_text
            comment.patch_source = decision.patch_source
            comment.patch_confidence = decision.patch_confidence
            comment.resolution_basis = decision.resolution_basis
            comment.canonical_term_used = decision.canonical_term_used

    patches = build_patch_records(analyzed, decision_lookup)
    faq_entries = generate_faq(analyzed, decision_lookup)
    briefs = build_section_briefs(analyzed)
    briefing_points = top_briefing_points(briefs)

    output_df = raw_df.copy()

    _set_column(output_df, mapping, "comment_number", [c.id for c in analyzed], always_override=False)
    _set_column(output_df, mapping, "reviewer_initials", [c.reviewer_initials for c in analyzed], always_override=False)
    _set_column(output_df, mapping, "agency", [c.agency for c in analyzed], always_override=False)
    _set_column(output_df, mapping, "report_version", [c.report_version for c in analyzed], always_override=False)
    _set_column(output_df, mapping, "section", [c.section for c in analyzed], always_override=False)
    _set_column(output_df, mapping, "page", [c.page for c in analyzed], always_override=False)
    _set_column(output_df, mapping, "line", [c.line for c in analyzed], always_override=False)
    _set_column(output_df, mapping, "comment_type", [c.normalized_type for c in analyzed], always_override=True)
    _set_column(output_df, mapping, "agency_notes", [c.agency_notes for c in analyzed], always_override=False)
    _set_column(output_df, mapping, "agency_suggested_text", [c.agency_suggested_text for c in analyzed], always_override=False)
    _set_column(output_df, mapping, "wg_chain_comments", [c.wg_chain_comments for c in analyzed], always_override=False)

    _set_column(output_df, mapping, "ntia_comments", [d.ntia_comment for d in decisions], always_override=True)
    _set_column(output_df, mapping, "disposition", [d.disposition for d in decisions], always_override=True)
    _set_column(output_df, mapping, "resolution", [d.resolution_text for d in decisions], always_override=True)
    _set_column(output_df, mapping, "patch_text", [d.patch_text for d in decisions], always_override=True)
    _set_column(output_df, mapping, "patch_source", [d.patch_source for d in decisions], always_override=True)
    _set_column(output_df, mapping, "patch_confidence", [d.patch_confidence for d in decisions], always_override=True)
    _set_column(output_df, mapping, "resolution_basis", [d.resolution_basis for d in decisions], always_override=True)
    _set_column(output_df, mapping, "report_context", [c.report_context for c in analyzed], always_override=True)
    _set_column(output_df, mapping, "context_confidence", [c.context_confidence for c in analyzed], always_override=True)
    _set_column(output_df, mapping, "resolution_task", [_resolution_task(c, d.disposition) for c, d in zip(analyzed, decisions)], always_override=True)
    _set_column(output_df, mapping, "comment_cluster_id", [c.cluster_id for c in analyzed], always_override=True)
    _set_column(output_df, mapping, "cluster_label", [c.cluster_label for c in analyzed], always_override=True)
    _set_column(output_df, mapping, "cluster_size", [str(c.cluster_size) for c in analyzed], always_override=True)
    _set_column(output_df, mapping, "intent_classification", [c.intent_classification for c in analyzed], always_override=True)
    _set_column(output_df, mapping, "section_group", [c.section_group for c in analyzed], always_override=True)
    _set_column(output_df, mapping, "heat_level", [c.heat_level for c in analyzed], always_override=True)
    _set_column(output_df, mapping, "validation_status", [d.validation_status for d in decisions], always_override=True)
    _set_column(output_df, mapping, "validation_code", [d.validation_code for d in decisions], always_override=True)
    _set_column(output_df, mapping, "validation_notes", [d.validation_notes for d in decisions], always_override=True)
    _set_column(output_df, mapping, "shared_resolution_id", [c.shared_resolution_id for c in analyzed], always_override=True)
    _set_column(output_df, mapping, "canonical_term_used", [d.canonical_term_used for d in decisions], always_override=True)

    write_resolution_workbook(output_df, output_path)

    base = Path(output_path)
    patch_file = Path(patch_output) if patch_output else base.with_name(base.stem + "_patches.json")
    faq_file = Path(faq_output) if faq_output else base.with_name(base.stem + "_faq.md")
    summary_file = Path(summary_output) if summary_output else base.with_name(base.stem + "_section_summary.md")
    briefing_file = Path(briefing_output) if briefing_output else base.with_name(base.stem + "_briefing.md")

    _write_json(
        patch_file,
        [
            {
                "comment_id": p.comment_id,
                "target_section": p.target_section,
                "target_lines": p.target_lines,
                "action_type": p.action_type,
                "old_text": p.old_text,
                "new_text": p.new_text,
                "rationale": p.rationale,
                "patch_source": p.patch_source,
                "confidence": p.confidence,
                "shared_resolution_id": p.shared_resolution_id,
            }
            for p in patches
        ],
    )

    _write_json(
        base.with_name(base.stem + "_shared_resolutions.json"),
        [
            {
                "master_resolution_id": sr.master_resolution_id,
                "linked_comment_ids": sr.linked_comment_ids,
                "shared_fix_text": sr.shared_fix_text,
                "target_section": sr.target_section,
            }
            for sr in shared_resolutions
        ],
    )

    faq_lines = ["# FAQ / Issue Log"]
    for entry in faq_entries:
        faq_lines.append(f"## {entry.faq_id}")
        faq_lines.append(f"**Question:** {entry.normalized_question}")
        faq_lines.append(f"**Answer:** {entry.canonical_answer}")
        if entry.related_comment_ids:
            faq_lines.append(f"Related comments: {', '.join(entry.related_comment_ids)}")
        if entry.affected_sections:
            faq_lines.append(f"Affected sections: {', '.join(entry.affected_sections)}")
    _write_markdown(faq_file, faq_lines)

    summary_lines = ["# Section Summary"]
    for brief in briefs:
        summary_lines.append(f"## Section {brief.section}")
        summary_lines.append(f"Total comments: {brief.total_comments}")
        summary_lines.append(f"Themes: {', '.join(brief.themes)}")
        summary_lines.append("Recommended revision strategy:")
        for step in brief.revision_strategy:
            summary_lines.append(f"- {step}")
    _write_markdown(summary_file, summary_lines)

    briefing_lines = ["# Working Group Briefing Bullets", "Top issues this review cycle:"]
    for point in briefing_points:
        briefing_lines.append(f"- {point}")
    _write_markdown(briefing_file, briefing_lines)

    return output_df
