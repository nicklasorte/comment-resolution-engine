from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from .config import ColumnMappingConfig
from .contracts import ConstitutionContext
from .models import (
    AnalyzedComment,
    FAQEntry,
    PatchRecord,
    ResolutionDecision,
    SectionIssueBrief,
    SharedResolution,
)


@dataclass(slots=True)
class PipelineRunResult:
    """Collected outputs from a single pipeline execution."""

    run_id: str
    output_df: pd.DataFrame
    analyzed_comments: List[AnalyzedComment]
    decisions: List[ResolutionDecision]
    patches: List[PatchRecord]
    shared_resolutions: List[SharedResolution]
    provenance_records: List[dict]
    canonical_matrix: Dict[str, Any]
    canonical_provenance: Dict[str, Any]
    reviewer_artifact: Dict[str, Any]
    rules_metadata: Dict[str, Any]
    constitution: ConstitutionContext
    raw_df: pd.DataFrame
    normalized_df: pd.DataFrame
    faq_entries: List[FAQEntry]
    briefs: List[SectionIssueBrief]
    briefing_points: List[str]
    pdf_contexts: Dict[str, Any]
    run_context: Dict[str, Any]
    mapping: ColumnMappingConfig
    output_paths: Dict[str, Path]
    input_paths: Dict[str, Any]
    include_metadata_columns: bool
    warnings: List[str]
    constitution_report_path: Optional[Path] = None
