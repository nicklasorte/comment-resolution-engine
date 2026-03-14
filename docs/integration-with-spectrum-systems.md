# Integration with spectrum-systems

comment-resolution-engine implements SYS-001 and consumes architecture, schema, and governance defined in the spectrum-systems repository. Today, spectrum-systems is the source of truth for:
- Governing spec, schemas, and workflow contracts for SYS-001.
- Provenance guidance and error taxonomy definitions.
- Shared rules packs distributed under `spectrum-systems/rules/comment-resolution`.

What remains local to this repository:
- Executable pipeline code, deterministic heuristics, and fallbacks.
- Local column mapping configuration and CLI UX.
- Built-in validation, clustering, generation, and export logic.

Current integration behavior:
- External rules packs are loaded from `--rules-path` (e.g., `../spectrum-systems/rules/comment-resolution`) with optional `--rules-profile` and `--rules-version` metadata.
- Canonical term rules augment/override local canonical definitions and normalize revision/source naming.
- Issue pattern rules classify comments before local heuristics and can drive disposition.
- Disposition rules inform disposition/notes/patch templates when matches are found.
- Validation rules run before local validation, blocking runs when missing PDFs or revisions, and contributing rule provenance when applicable.
- Drafting rules post-process generated resolution/NTIA text (e.g., revision lineage, review callouts) after validation.
- Canonical contract artifacts are enforced at the boundary: `reviewer_comment_set` is validated on ingest, and the engine emits `comment_resolution_matrix` plus `provenance_record` artifacts that align with the spectrum-systems contract definitions.
- Before running the pipeline, validate spectrum-systems rule edits with `python -m comment_resolution_engine.cli --validate-rules --rules-path ../spectrum-systems/rules/comment-resolution --rules-strict` to catch schema or enum regressions early.

Fallback behavior:
- When `--rules-path` is omitted, local deterministic heuristics remain in place for canonical matching, issue detection, disposition selection, drafting, and validation.
- If a rule file is missing from the pack, the corresponding local behavior is used without failing the run.

Provenance:
- Run-level provenance records include `rules_path`, `rules_profile`, `rules_version`, and `rules_loaded_count`.
- Record-level provenance captures `rule_id`, `rule_source`, `rule_version`, `rules_profile`, `rules_version`, `matched_rule_types`, and `generation_mode` when external rules contribute.
