from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Iterable, List

from .analysis import assign_clusters, classify_intent, group_by_section, heat_map
from .contracts import (
    ConstitutionContext,
    DEFAULT_CONSTITUTION_PATH,
    DEFAULT_GENERATION_MODE,
    DEFAULT_WORKFLOW_NAME,
    DEFAULT_WORKFLOW_STEP,
    default_constitution_context,
)
from .contracts.artifacts import (
    build_adapter_artifact,
    build_comment_records_from_artifact,
    build_comment_resolution_matrix_artifact,
    build_provenance_record_artifact,
    load_reviewer_comment_set,
    new_resolution_run_id,
    validate_reviewer_comment_set,
    validate_comment_resolution_matrix_artifact,
    validate_provenance_record_artifact,
)
from .contracts.loader import load_constitution
from .config import load_column_mapping
from .excel_io import write_resolution_workbook
from .errors import CREError, ErrorCategory
from .spreadsheet_contract import MATRIX_CONTRACT, reorder_to_canonical
from .generation import (
    build_patch_records,
    build_resolution_decision,
    build_section_briefs,
    build_shared_resolutions,
    assemble_rev2_draft,
    build_section_rewrites,
    DEFAULT_DRAFT_MODE,
    generate_faq,
    top_briefing_points,
)
from .ingest import load_pdf_contexts, read_comment_matrix
from .models import AnalyzedComment
from .normalize import normalize_comments
from .provenance import build_provenance_record
from .rules import RuleEngine, Strictness, load_rule_pack
from .validation import validate_resolution
from .validation.rev2_validator import validate_section_rewrite


def _row_status(status: str, disposition: str | None = None) -> str:
    return MATRIX_CONTRACT.row_status(status, disposition or "")


def _resolution_task(comment: AnalyzedComment, disposition: str) -> str:
    context_note = "Context available" if comment.report_context else "No PDF context"
    return f"Resolve comment {comment.id} as {disposition}. Section {comment.section or 'N/A'}, line {comment.line or 'N/A'}. {context_note}."


def _hydrate_analyzed_comments(normalized) -> List[AnalyzedComment]:
    return [AnalyzedComment(**asdict(n)) for n in normalized]


def _canonicalize_version_label(label: str) -> str:
    return "".join(ch.lower() for ch in str(label).strip() if ch.isalnum())


def _match_report_version_label(label: str, pdf_contexts):
    normalized = _canonicalize_version_label(label)
    for key, ctx in pdf_contexts.items():
        candidates = {_canonicalize_version_label(key)}
        candidates.add(_canonicalize_version_label(getattr(ctx, "label", "")))
        source_path = getattr(ctx, "source_path", "")
        if source_path:
            candidates.add(_canonicalize_version_label(Path(source_path).stem))
        if normalized and normalized in candidates:
            return key, ctx
    return None


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


def _apply_rule_metadata(target, summary: dict) -> None:
    if not summary:
        return
    if hasattr(target, "rule_id"):
        target.rule_id = summary.get("rule_id", "")
    if hasattr(target, "rule_source"):
        target.rule_source = summary.get("rule_source", "")
    if hasattr(target, "rule_version"):
        target.rule_version = summary.get("rule_version", "")
    if hasattr(target, "rules_profile"):
        target.rules_profile = summary.get("rules_profile", "")
    if hasattr(target, "rules_version"):
        target.rules_version = summary.get("rules_version", "")
    if hasattr(target, "matched_rule_types"):
        target.matched_rule_types = list(summary.get("matched_rule_types", []))
    if hasattr(target, "generation_mode") and summary.get("generation_mode"):
        target.generation_mode = summary.get("generation_mode")
    if hasattr(target, "applied_rules"):
        applied = list(getattr(target, "applied_rules") or [])
        applied.extend(summary.get("applied_rules", []))
        target.applied_rules = applied


def _provenance_for_comment(comment: AnalyzedComment, pdf_contexts, decision, rules_metadata: dict | None = None, constitution: ConstitutionContext | None = None) -> dict:
    resolved_revision = comment.resolved_against_revision or comment.revision
    context = pdf_contexts.get(resolved_revision) or pdf_contexts.get(comment.revision)
    source_document = comment.source_document or (context.source_path if context else "")
    review_status = comment.review_status or decision.validation_status or _row_status(decision.validation_status, comment.comment_disposition)
    confidence_score = comment.confidence_score or decision.patch_confidence
    record_id = comment.provenance_record_id or f"prov-{comment.id}"

    derived_from = {"raw_row": comment.raw_row}
    if rules_metadata:
        derived_from["rules"] = rules_metadata
    if getattr(comment, "applied_rules", None):
        derived_from["applied_rules"] = comment.applied_rules

    provenance_record = build_provenance_record(
        record_id=record_id,
        record_type=comment.record_type or "comment_resolution",
        source_document=source_document,
        source_revision=comment.revision,
        resolved_against_revision=resolved_revision,
        derived_from=derived_from,
        review_status=review_status,
        confidence_score=confidence_score or "",
        workflow_name=DEFAULT_WORKFLOW_NAME,
        workflow_step=DEFAULT_WORKFLOW_STEP,
        generation_mode=comment.generation_mode or DEFAULT_GENERATION_MODE,
        constitution=constitution,
    )

    comment.provenance_record_id = provenance_record.record_id
    comment.review_status = review_status
    comment.confidence_score = confidence_score or ""
    comment.source_document = source_document
    comment.resolved_against_revision = resolved_revision
    comment.generation_mode = comment.generation_mode or DEFAULT_GENERATION_MODE
    comment.provenance = provenance_record.asdict()
    return provenance_record.asdict()


def run_pipeline(
    comments_path: str | Path,
    report_path: str | Path | list[str | Path] | None,
    output_path: str | Path,
    config_path: str | Path | None = None,
    patch_output: str | Path | None = None,
    faq_output: str | Path | None = None,
    summary_output: str | Path | None = None,
    briefing_output: str | Path | None = None,
    draft_rev2: bool = False,
    draft_mode: str = DEFAULT_DRAFT_MODE,
    draft_sections: list[str] | None = None,
    draft_high_priority_only: bool = False,
    draft_shared_only: bool = False,
    assemble_rev2: bool = False,
    rev2_sections_output: str | Path | None = None,
    rev2_draft_output: str | Path | None = None,
    rules_path: str | Path | None = None,
    rules_profile: str | None = None,
    rules_version: str | None = None,
    rules_strict: bool = False,
    constitution_path: str | Path | None = None,
    constitution_report_path: str | Path | None = None,
    compatibility_mode: str | None = None,
    fail_on_drift: bool = False,
    skip_constitution_check: bool = False,
    constitution_context: ConstitutionContext | None = None,
    include_metadata_columns: bool = False,
):
    import pandas as pd

    resolution_run_id = new_resolution_run_id()
    active_constitution = constitution_context or default_constitution_context()
    if not skip_constitution_check and constitution_context is None:
        active_constitution, _ = load_constitution(
            manifest_path=constitution_path or DEFAULT_CONSTITUTION_PATH,
            compatibility_mode=compatibility_mode,
            rules_profile=rules_profile,
            rules_version=rules_version,
            fail_on_drift=fail_on_drift,
            require_compatible=True,
            report_path=constitution_report_path,
        )

    mapping = load_column_mapping(config_path)
    reviewer_artifact = None
    if isinstance(comments_path, (str, Path)) and str(comments_path).lower().endswith((".json", ".yaml", ".yml")):
        reviewer_artifact = load_reviewer_comment_set(Path(comments_path))

    if reviewer_artifact:
        records, normalized_df, raw_df = build_comment_records_from_artifact(reviewer_artifact, mapping)
    else:
        records, normalized_df, raw_df = read_comment_matrix(str(comments_path), mapping)
        reviewer_artifact = validate_reviewer_comment_set(build_adapter_artifact(records, source_path=comments_path), allow_blank_revision=True)
    rule_pack = (
        load_rule_pack(
            rules_path,
            profile=rules_profile,
            requested_version=rules_version,
            strictness=Strictness.STRICT if rules_strict else Strictness.PERMISSIVE,
        )
        if rules_path
        else None
    )
    rule_engine = RuleEngine(rule_pack)
    rules_metadata = rule_pack.to_metadata() if rule_pack else {
        "rules_path": str(rules_path) if rules_path else None,
        "rules_profile": rules_profile or "local-defaults",
        "rules_version": rules_version or "local",
        "rules_loaded_count": 0,
    }
    records, normalized_df, raw_df = read_comment_matrix(str(comments_path), mapping)
    pre_pdf_context = {"pdf_count": len(report_path) if isinstance(report_path, list) else (1 if report_path else 0)}
    if rule_engine.enabled:
        rule_engine.apply_run_validations(pre_pdf_context)
    pdf_contexts = load_pdf_contexts(report_path)
    default_revision_label, default_revision_context = next(iter(pdf_contexts.items()))

    run_context = {
        "pdf_revisions": list(pdf_contexts.keys()),
        "pdf_count": len(pdf_contexts),
        "rules_profile": rules_metadata.get("rules_profile"),
        "rules_version": rules_metadata.get("rules_version"),
        "constitution_version": active_constitution.pinned_version,
        "constitution_commit": active_constitution.pinned_commit,
        "constitution_mode": active_constitution.compatibility_mode,
        "resolution_run_id": resolution_run_id,
        "source_comment_set_id": reviewer_artifact.get("artifact_id") if reviewer_artifact else None,
    }

    for record in records:
        if rule_engine.enabled:
            rule_engine.apply_canonical_rules(record, run_context=run_context)
        requested_version = (record.report_version or record.revision or "").strip()
        match = _match_report_version_label(requested_version, pdf_contexts) if requested_version else None
        if match:
            revision_key, pdf_context = match
        elif not requested_version:
            if len(pdf_contexts) == 1:
                revision_key, pdf_context = default_revision_label, default_revision_context
                record.report_version = record.report_version or pdf_context.label or revision_key
            else:
                raise CREError(ErrorCategory.VALIDATION_ERROR, "ERROR: Comments spreadsheet must contain a 'Report Version' value for each comment when multiple working paper revisions are uploaded.")
        else:
            missing_context = {**run_context, "missing_report_version": requested_version}
            if rule_engine.enabled:
                rule_engine.apply_run_validations(missing_context)
            raise CREError(ErrorCategory.PROVENANCE_ERROR, f"ERROR: Comment references report version '{requested_version}' but no corresponding working paper was uploaded.")
        record.revision = revision_key
        record.resolved_against_revision = revision_key
        record.source_document = pdf_context.source_path
        record.generation_mode = record.generation_mode or DEFAULT_GENERATION_MODE
        record.review_status = record.review_status or _row_status(record.review_status, record.comment_disposition)

    normalized = normalize_comments(records, pdf_contexts)
    analyzed = _hydrate_analyzed_comments(normalized)

    if rule_engine.enabled:
        for comment in analyzed:
            matches = rule_engine.apply_canonical_rules(comment, run_context=run_context)
            if matches:
                summary = rule_engine.summarize_matches(matches)
                _apply_rule_metadata(comment, summary)
                comment.generation_mode = summary.get("generation_mode", comment.generation_mode or DEFAULT_GENERATION_MODE)

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
        if rule_engine.enabled:
            issue_match, issue_matches = rule_engine.match_issue_pattern(comment, run_context=run_context)
            if issue_match:
                comment.issue_pattern = issue_match.applied_action.get("issue_type", "")
                summary = rule_engine.summarize_matches(issue_matches)
                _apply_rule_metadata(comment, summary)
                if summary.get("generation_mode"):
                    comment.generation_mode = summary["generation_mode"]

    decisions = [build_resolution_decision(comment, rule_engine=rule_engine, run_context=run_context) for comment in analyzed]
    decision_lookup = {comment.id: decision for comment, decision in zip(analyzed, decisions)}
    provenance_records: list[dict] = []

    shared_resolutions = build_shared_resolutions(analyzed, decision_lookup)
    shared_lookup = {}
    for sr in shared_resolutions:
        for cid in sr.linked_comment_ids:
            shared_lookup[cid] = sr.master_resolution_id

    for comment in analyzed:
        if comment.id in shared_lookup:
            comment.shared_resolution_id = shared_lookup[comment.id]

    decisions = [validate_resolution(c, decision_lookup[c.id], rule_engine=rule_engine, run_context=run_context) for c in analyzed]
    decision_lookup = {comment.id: decision for comment, decision in zip(analyzed, decisions)}
    if rule_engine.enabled:
        updated_decisions = []
        for comment, decision in zip(analyzed, decisions):
            matches, resolution_text, ntia_comment = rule_engine.apply_drafting_rules(comment, decision, run_context=run_context)
            if matches:
                decision.resolution_text = resolution_text
                decision.ntia_comment = ntia_comment
                summary = rule_engine.summarize_matches(matches)
                decision.matched_rule_types = list(dict.fromkeys((decision.matched_rule_types or []) + summary.get("matched_rule_types", [])))
                decision.rule_id = decision.rule_id or summary.get("rule_id", "")
                decision.rule_source = decision.rule_source or summary.get("rule_source", "")
                decision.rule_version = decision.rule_version or summary.get("rule_version", "")
                decision.rules_profile = decision.rules_profile or summary.get("rules_profile", "")
                decision.rules_version = decision.rules_version or summary.get("rules_version", "")
                decision.generation_mode = summary.get("generation_mode", decision.generation_mode)
                comment.applied_rules.extend(summary.get("applied_rules", []))
            updated_decisions.append(decision)
        decisions = updated_decisions
        decision_lookup = {comment.id: decision for comment, decision in zip(analyzed, decisions)}
    for comment in analyzed:
        decision = decision_lookup.get(comment.id)
        if decision:
            comment.patch_text = decision.patch_text
            comment.patch_source = decision.patch_source
            comment.patch_confidence = decision.patch_confidence
            comment.resolution_basis = decision.resolution_basis
            comment.canonical_term_used = decision.canonical_term_used
            comment.review_status = comment.review_status or decision.validation_status
            comment.confidence_score = comment.confidence_score or decision.patch_confidence
            comment.generation_mode = decision.generation_mode or comment.generation_mode or DEFAULT_GENERATION_MODE
            if decision.rule_id:
                comment.rule_id = decision.rule_id
                comment.rule_source = decision.rule_source
                comment.rule_version = decision.rule_version
                comment.rules_profile = decision.rules_profile
                comment.rules_version = decision.rules_version
                comment.matched_rule_types = decision.matched_rule_types
                comment.applied_rules.extend(getattr(comment, "applied_rules", []))
            decision_rules_metadata = {
                **(rules_metadata or {}),
                "rule_id": decision.rule_id,
                "rule_source": decision.rule_source,
                "rule_version": decision.rule_version,
                "matched_rule_types": decision.matched_rule_types,
            }
            provenance_records.append(_provenance_for_comment(comment, pdf_contexts, decision, decision_rules_metadata, active_constitution))

    patches = build_patch_records(analyzed, decision_lookup)
    faq_entries = generate_faq(analyzed, decision_lookup)
    briefs = build_section_briefs(analyzed)
    briefing_points = top_briefing_points(briefs)

    output_df = raw_df.copy()
    MATRIX_CONTRACT.validate_collisions(raw_df.columns, include_metadata=include_metadata_columns)

    # Canonical MVP spreadsheet fields (always included)
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

    _set_column(output_df, mapping, "ntia_comments", [d.ntia_comment for d in decisions], always_override=True)
    _set_column(output_df, mapping, "comment_disposition", [d.disposition for d in decisions], always_override=True)
    _set_column(output_df, mapping, "resolution", [d.resolution_text for d in decisions], always_override=True)

    if include_metadata_columns:
        _set_column(output_df, mapping, "revision", [c.revision for c in analyzed], always_override=False)
        _set_column(output_df, mapping, "resolved_against_revision", [c.resolved_against_revision for c in analyzed], always_override=True)
        _set_column(output_df, mapping, "wg_chain_comments", [c.wg_chain_comments for c in analyzed], always_override=False)
        _set_column(output_df, mapping, "patch_text", [d.patch_text for d in decisions], always_override=True)
        _set_column(output_df, mapping, "patch_source", [d.patch_source for d in decisions], always_override=True)
        _set_column(output_df, mapping, "patch_confidence", [d.patch_confidence for d in decisions], always_override=True)
        _set_column(output_df, mapping, "resolution_basis", [d.resolution_basis for d in decisions], always_override=True)
        _set_column(output_df, mapping, "report_context", [c.report_context for c in analyzed], always_override=True)
        _set_column(output_df, mapping, "context_confidence", [c.context_confidence for c in analyzed], always_override=True)
        _set_column(output_df, mapping, "resolution_task", [_resolution_task(c, d.disposition) for c, d in zip(analyzed, decisions)], always_override=True)
        _set_column(output_df, mapping, "generation_mode", [c.generation_mode for c in analyzed], always_override=True)
        _set_column(output_df, mapping, "rule_id", [c.rule_id for c in analyzed], always_override=True)
        _set_column(output_df, mapping, "rule_source", [c.rule_source for c in analyzed], always_override=True)
        _set_column(output_df, mapping, "rule_version", [c.rule_version for c in analyzed], always_override=True)
        _set_column(output_df, mapping, "rules_profile", [c.rules_profile for c in analyzed], always_override=True)
        _set_column(output_df, mapping, "rules_version", [c.rules_version for c in analyzed], always_override=True)
        _set_column(output_df, mapping, "matched_rule_types", ["|".join(c.matched_rule_types or []) for c in analyzed], always_override=True)
        _set_column(output_df, mapping, "review_status", [c.review_status for c in analyzed], always_override=True)
        _set_column(output_df, mapping, "confidence_score", [c.confidence_score for c in analyzed], always_override=True)
        _set_column(output_df, mapping, "provenance_record_id", [c.provenance_record_id for c in analyzed], always_override=True)
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

    output_df = reorder_to_canonical(output_df, include_metadata=include_metadata_columns)
    write_resolution_workbook(output_df, output_path, include_metadata=include_metadata_columns)

    base = Path(output_path)
    patch_file = Path(patch_output) if patch_output else base.with_name(base.stem + "_patches.json")
    faq_file = Path(faq_output) if faq_output else base.with_name(base.stem + "_faq.md")
    summary_file = Path(summary_output) if summary_output else base.with_name(base.stem + "_section_summary.md")
    briefing_file = Path(briefing_output) if briefing_output else base.with_name(base.stem + "_briefing.md")
    provenance_file = base.with_name(base.stem + "_provenance.json")

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
                "source_revision": p.source_revision,
                "resolved_against_revision": p.resolved_against_revision,
                "provenance_record_id": p.provenance_record_id,
                "provenance": p.provenance,
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
    _write_json(provenance_file, provenance_records)

    canonical_matrix = build_comment_resolution_matrix_artifact(
        run_id=resolution_run_id,
        input_artifact=reviewer_artifact,
        comments=analyzed,
        decisions=decisions,
        provenance_records=provenance_records,
        constitution=active_constitution,
        rules_metadata=rules_metadata,
    )
    validate_comment_resolution_matrix_artifact(canonical_matrix)
    canonical_matrix_path = base.with_name(base.stem + "_comment_resolution_matrix.json")
    _write_json(canonical_matrix_path, canonical_matrix)

    canonical_provenance = build_provenance_record_artifact(
        run_id=resolution_run_id,
        input_artifact=reviewer_artifact,
        matrix_artifact=canonical_matrix,
        provenance_records=provenance_records,
        constitution=active_constitution,
    )
    validate_provenance_record_artifact(canonical_provenance)
    _write_json(base.with_name(base.stem + "_provenance_record.json"), canonical_provenance)

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

    primary_pdf_context = pdf_contexts.get(default_revision_label)

    if draft_rev2 or assemble_rev2:
        rev2_sections_path = Path(rev2_sections_output) if rev2_sections_output else base.with_name(base.stem + "_rev2_sections.json")
        rev2_draft_path = Path(rev2_draft_output) if rev2_draft_output else base.with_name(base.stem + "_rev2_draft.md")
        rev2_appendix_path = base.with_name(base.stem + "_rev2_appendix.md")
        rewrites = build_section_rewrites(
            analyzed,
            decision_lookup=decision_lookup,
            shared_resolutions=shared_resolutions,
            draft_mode=draft_mode,
            draft_sections=draft_sections,
            high_priority_only=draft_high_priority_only,
            require_shared_fix=draft_shared_only,
            heat_levels=heat_levels,
            pdf_context=primary_pdf_context,
        )
        validated_rewrites = [validate_section_rewrite(r) for r in rewrites]
        _write_json(rev2_sections_path, [asdict(r) for r in validated_rewrites])
        if assemble_rev2:
            draft_lines, appendix_lines = assemble_rev2_draft(validated_rewrites)
            _write_markdown(rev2_draft_path, draft_lines)
            _write_markdown(rev2_appendix_path, appendix_lines)

    return output_df
