# Transformation mapping (reviewer_comment_set -> comment_resolution_matrix)

This engine ingests canonical `reviewer_comment_set` artifacts (or adapts legacy matrices) and emits canonical `comment_resolution_matrix` artifacts. Key field mappings:
- `comment_id` -> `rows[*].comment_id` and `rows[*].trace.source_comment_id` for linkage.
- `revision` -> `rows[*].revision_id` and `rows[*].resolved_against_revision` to preserve working paper revision.
- `agency_notes` -> `rows[*].agency_comment`; `agency_suggested_text` -> `rows[*].agency_suggested_text`.
- `comment_type` -> `rows[*].comment_type` after normalization; disposition/NTIA comments/resolution are generated and written to `rows[*].disposition`, `rows[*].ntia_comment`, and `rows[*].resolution_text`.
- Analysis and drafting metadata (clusters, intent, heat, canonical_term_used, rule ids, generation mode) are captured in `rows[*]` with matching provenance references.
- Each row references `provenance_record_id` in `rows[*].trace` and the run-level provenance feed (`<output>_provenance_record.json`) carries the full set of per-row provenance entries.

Legacy spreadsheets are adapted into the same canonical shape before processing to keep the boundary consistent; canonical JSON artifacts remain the preferred interface for interoperability.
