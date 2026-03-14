from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Sequence, Set

import pandas as pd

from ..config import ColumnMappingConfig, DEFAULT_MAPPING

STATUS_RANK = {"FAIL": 0, "NEEDS_REVIEW": 1, "NEEDS REVIEW": 1, "WARN": 2, "PASS": 3}


def _normalize_text(value) -> str:
    if value is None:
        return ""
    text = str(value)
    if text.lower() in {"nan", "none"}:
        return ""
    return text.strip()


def _col(df: pd.DataFrame, mapping: ColumnMappingConfig, key: str) -> pd.Series | None:
    name = mapping.resolve_column_name(df.columns, key)
    return df[name] if name in df.columns else None


def _status_meets_threshold(actual: str, required: str) -> bool:
    actual_rank = STATUS_RANK.get((actual or "").strip().upper(), -1)
    required_rank = STATUS_RANK.get((required or "").strip().upper(), -1)
    return actual_rank >= required_rank >= 0


@dataclass(slots=True)
class CommentExpectation:
    disposition: str | None = None
    intent: str | None = None
    section_group: str | None = None
    requires_context: bool = False
    requires_human_review: bool = False
    require_resolution: bool = True
    require_ntia_comment: bool = True
    validation_status_min: str = "PASS"
    provenance_fields: List[str] = field(default_factory=list)


@dataclass(slots=True)
class GoldenExpectations:
    comments: Dict[str, CommentExpectation]
    section_heatmap: Dict[str, str] = field(default_factory=dict)


def load_expectations(raw: dict) -> GoldenExpectations:
    comment_entries = raw.get("comments") or {}
    expectations: Dict[str, CommentExpectation] = {}
    for cid, data in comment_entries.items():
        expectations[str(cid)] = CommentExpectation(
            disposition=data.get("disposition"),
            intent=data.get("intent"),
            section_group=data.get("section_group"),
            requires_context=bool(data.get("requires_context")),
            requires_human_review=bool(data.get("requires_human_review")),
            require_resolution=data.get("require_resolution", True),
            require_ntia_comment=data.get("require_ntia_comment", True),
            validation_status_min=data.get("validation_status_min", "PASS"),
            provenance_fields=list(data.get("provenance_fields") or []),
        )
    return GoldenExpectations(comments=expectations, section_heatmap=raw.get("section_heatmap") or {})


def _comment_lookup(df: pd.DataFrame, mapping: ColumnMappingConfig) -> Dict[str, pd.Series]:
    id_col = mapping.resolve_column_name(df.columns, "comment_number")
    if id_col not in df.columns:
        return {}
    lookup: Dict[str, pd.Series] = {}
    for _, row in df.iterrows():
        cid = _normalize_text(row.get(id_col))
        lookup[cid] = row
    return lookup


def _provenance_lookup(records: Sequence[dict]) -> Dict[str, dict]:
    return {str(rec.get("record_id")): rec for rec in records or []}


def _heatmap_lookup(df: pd.DataFrame, mapping: ColumnMappingConfig) -> Dict[str, str]:
    section_col = mapping.resolve_column_name(df.columns, "section_group")
    heat_col = mapping.resolve_column_name(df.columns, "heat_level")
    if section_col not in df.columns or heat_col not in df.columns:
        return {}
    combined = df[[section_col, heat_col]].dropna()
    lookup: Dict[str, str] = {}
    for _, row in combined.iterrows():
        section = _normalize_text(row[section_col])
        heat = _normalize_text(row[heat_col])
        if section and section not in lookup:
            lookup[section] = heat
    return lookup


def score_case(
    case_id: str,
    output_df: pd.DataFrame,
    provenance_records: Sequence[dict],
    queue_comment_ids: Iterable[str],
    expectations: GoldenExpectations,
    mapping: ColumnMappingConfig = DEFAULT_MAPPING,
) -> dict:
    rows = _comment_lookup(output_df, mapping)
    queue_set: Set[str] = {str(cid) for cid in queue_comment_ids}
    prov_lookup = _provenance_lookup(provenance_records)
    heat_lookup = _heatmap_lookup(output_df, mapping)

    disposition_col = _col(output_df, mapping, "disposition")
    intent_col = _col(output_df, mapping, "intent_classification")
    section_col = _col(output_df, mapping, "section_group")
    resolution_col = _col(output_df, mapping, "resolution")
    ntia_col = _col(output_df, mapping, "ntia_comments")
    context_col = _col(output_df, mapping, "report_context")
    validation_col = _col(output_df, mapping, "validation_status")
    provenance_id_col = _col(output_df, mapping, "provenance_record_id")

    metrics = {
        "disposition_accuracy": 0.0,
        "intent_accuracy": 0.0,
        "required_resolution_presence_rate": 0.0,
        "required_ntia_comment_presence_rate": 0.0,
        "provenance_completeness_rate": 0.0,
        "validation_pass_rate": 0.0,
        "human_review_precision": 0.0,
        "human_review_recall": 0.0,
        "context_attachment_rate": 0.0,
        "section_heatmap_stability": 0.0,
    }

    if not expectations.comments:
        return {"case_id": case_id, "metrics": metrics, "per_comment": {}, "queue": sorted(queue_set)}

    per_comment_results: Dict[str, dict] = {}
    expected_ids = list(expectations.comments.keys())
    total = len(expected_ids)

    correct_disposition = 0
    correct_intent = 0
    correct_section = 0
    resolution_hits = 0
    resolution_needed = 0
    ntia_hits = 0
    ntia_needed = 0
    context_hits = 0
    context_needed = 0
    provenance_hits = 0
    provenance_needed = 0
    validation_hits = 0
    expected_review = {cid for cid, exp in expectations.comments.items() if exp.requires_human_review}

    for cid in expected_ids:
        exp = expectations.comments[cid]
        row = rows.get(cid)
        disposition = _normalize_text(row.get(disposition_col.name)) if (row is not None and disposition_col is not None) else ""
        intent = _normalize_text(row.get(intent_col.name)) if (row is not None and intent_col is not None) else ""
        section = _normalize_text(row.get(section_col.name)) if (row is not None and section_col is not None) else ""
        resolution = _normalize_text(row.get(resolution_col.name)) if (row is not None and resolution_col is not None) else ""
        ntia = _normalize_text(row.get(ntia_col.name)) if (row is not None and ntia_col is not None) else ""
        context_text = _normalize_text(row.get(context_col.name)) if (row is not None and context_col is not None) else ""
        validation = _normalize_text(row.get(validation_col.name)) if (row is not None and validation_col is not None) else ""
        prov_id = _normalize_text(row.get(provenance_id_col.name)) if (row is not None and provenance_id_col is not None) else ""

        if exp.disposition and disposition.lower() == exp.disposition.lower():
            correct_disposition += 1
        if exp.intent and intent.lower() == exp.intent.lower():
            correct_intent += 1
        if exp.section_group and section == exp.section_group:
            correct_section += 1

        if exp.require_resolution:
            resolution_needed += 1
            if resolution:
                resolution_hits += 1

        if exp.require_ntia_comment:
            ntia_needed += 1
            if ntia:
                ntia_hits += 1

        if exp.requires_context:
            context_needed += 1
            if context_text:
                context_hits += 1

        if exp.provenance_fields:
            provenance_needed += 1
            prov = prov_lookup.get(prov_id, {})
            if prov and all(field in prov and _normalize_text(prov.get(field)) for field in exp.provenance_fields):
                provenance_hits += 1

        if _status_meets_threshold(validation, exp.validation_status_min):
            validation_hits += 1

        per_comment_results[cid] = {
            "actual_disposition": disposition,
            "expected_disposition": exp.disposition,
            "actual_intent": intent,
            "expected_intent": exp.intent,
            "actual_section_group": section,
            "expected_section_group": exp.section_group,
            "validation_status": validation,
            "provenance_record_id": prov_id,
            "in_queue": cid in queue_set,
            "requires_human_review": exp.requires_human_review,
        }

    metrics["disposition_accuracy"] = correct_disposition / total
    metrics["intent_accuracy"] = correct_intent / total
    metrics["required_resolution_presence_rate"] = resolution_hits / resolution_needed if resolution_needed else 1.0
    metrics["required_ntia_comment_presence_rate"] = ntia_hits / ntia_needed if ntia_needed else 1.0
    metrics["context_attachment_rate"] = context_hits / context_needed if context_needed else 1.0
    metrics["provenance_completeness_rate"] = provenance_hits / provenance_needed if provenance_needed else 1.0
    metrics["validation_pass_rate"] = validation_hits / total

    true_positives = len(queue_set.intersection(expected_review))
    metrics["human_review_precision"] = true_positives / len(queue_set) if queue_set else 1.0 if not expected_review else 0.0
    metrics["human_review_recall"] = true_positives / len(expected_review) if expected_review else 1.0

    if expectations.section_heatmap:
        matches = 0
        for section, expected_heat in expectations.section_heatmap.items():
            actual_heat = _normalize_text(heat_lookup.get(section))
            if actual_heat and actual_heat.lower() == str(expected_heat).lower():
                matches += 1
        metrics["section_heatmap_stability"] = matches / len(expectations.section_heatmap)
    else:
        metrics["section_heatmap_stability"] = 1.0

    return {"case_id": case_id, "metrics": metrics, "per_comment": per_comment_results, "queue": sorted(queue_set)}
