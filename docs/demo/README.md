# Demo package

This demo shows the full packaged execution path with real inputs checked into the repo.

## Inputs
- `docs/demo/inputs/reviewer_comments.json` — canonical reviewer comment set
- `docs/demo/inputs/demo_working_paper.pdf` — working paper text aligned to the comments

## Run the demo

```bash
python -m comment_resolution_engine.cli \
  --reviewer-comment-set docs/demo/inputs/reviewer_comments.json \
  --report docs/demo/inputs/demo_working_paper.pdf \
  --output /tmp/demo_legacy.xlsx \
  --output-dir docs/demo/expected \
  --emit-run-manifest
```

Outputs land in `docs/demo/expected/` (tracked here as the expected tree):
- `run_manifest.json` — machine-readable handoff with run_id, tool version, inputs/outputs + SHA-256 hashes, constitution/standards hashes, and warning summary.
- `summary.json` — lightweight counters for dashboards (totals, dispositions, reason codes, agencies, missing/duplicate counts).
- `artifacts/comment_resolution_matrix.json` — canonical adjudication artifact.
- `artifacts/provenance_record.json` — canonical provenance artifact.
- `artifacts/legacy_comment_resolution_matrix.xlsx` — legacy spreadsheet output.
- `artifacts/constitution_report.json` — compatibility drift report for the run.
- `artifacts/patches.json`, `shared_resolutions.json`, `faq.md`, `section_summary.md`, `briefing.md`, `reviewer_comment_set.json` — supporting artifacts for implementers.
- `debug/normalized_records.json`, `adjudication_decisions.json`, `provenance_records.json` — intermediate payloads to aid troubleshooting.

The output contract and file semantics are described in `docs/output-contract.md`.
