# Output Contract

The packaged output directory is the automation surface for downstream systems. Every run is written into a single directory with predictable names and hashes.

## Layout

```
outputs/
  artifacts/
    comment_resolution_matrix.json
    provenance_record.json
    legacy_comment_resolution_matrix.xlsx
    patches.json
    shared_resolutions.json
    constitution_report.json
    reviewer_comment_set.json
    faq.md
    section_summary.md
    briefing.md
  debug/
    normalized_records.json
    adjudication_decisions.json
    provenance_records.json
  run_manifest.json
  summary.json
```

## Artifact descriptions

- `artifacts/comment_resolution_matrix.json` – Canonical contract artifact with every resolved comment and trace metadata.
- `artifacts/provenance_record.json` – Canonical provenance artifact for the run.
- `artifacts/legacy_comment_resolution_matrix.xlsx` – Spreadsheet version of the matrix for human review.
- `artifacts/patches.json` – Line-level patch suggestions generated during adjudication.
- `artifacts/shared_resolutions.json` – Linked resolutions that were applied to multiple comments.
- `artifacts/constitution_report.json` – Compatibility evaluation of the run against the pinned constitution manifest.
- `artifacts/reviewer_comment_set.json` – Canonicalized copy of the input reviewer comment set used for this run.
- `artifacts/faq.md` – FAQ / issue log derived from the comment set.
- `artifacts/section_summary.md` – Section-level summary with themes and revision strategy.
- `artifacts/briefing.md` – Briefing bullets for working group reviewers.

Debug helpers:

- `debug/normalized_records.json` – Normalized comment rows after ingest.
- `debug/adjudication_decisions.json` – Per-comment disposition, validation status, and rule metadata.
- `debug/provenance_records.json` – Raw provenance records emitted during the run.

Top-level handoff files:

- `summary.json` – Lightweight counts for dashboards (totals, dispositions, reason codes, agencies, missing/duplicate counts).
- `run_manifest.json` – Machine-readable description of the run, including run_id, tool version, timestamps, constitution and standards hashes, inputs, outputs, and per-file SHA-256 hashes.

## Hashing

All declared inputs and packaged outputs in `run_manifest.json` include a SHA-256 checksum and file size for provenance and change detection. Constitution and standards manifest hashes are also included to make contract drift visible to orchestrators.
