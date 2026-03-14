# Constitution Integration

comment-resolution-engine now treats spectrum-systems as the governing constitution. A local manifest (`config/constitution.yaml`) pins SYS-001 to specific schema, prompt, rules, provenance, and error taxonomy references.

## Manifest
- Fields: `source_repo`, `system_id`, `pinned_version|pinned_commit`, `schema_refs`, `rules_profile_refs`, `prompt_refs`, `provenance_standard_ref`, `error_taxonomy_ref`, `compatibility_mode (strict|warn)`.
- Paths are resolved relative to the manifest location; include `..` prefixes to point at repo-root docs and prompts.

## Loader + Compatibility
- `contracts.loader.load_constitution(...)` loads the manifest, fingerprints referenced artifacts, and produces a compatibility report.
- Drift detection covers missing refs, schema/provenance/error taxonomy version mismatches, prompt/rules-profile gaps, and source/system ID mismatches.
- Severity defaults to `strict`; `warn` downgrades drift to warnings unless `--fail-on-drift` is passed.

## Runtime behavior
- CLI always loads the manifest before pipeline execution, writing a report to `--constitution-report` (defaults to `<output>_constitution_report.json`).
- `--check-constitution` runs the compatibility check without executing the pipeline.
- `--compatibility-mode` and `--fail-on-drift` override manifest defaults per run.

## Output stamping
- Provenance records include constitution source, pinned version/commit, schema/provenance/error taxonomy versions, and rules profile/version to anchor every artifact to the governing constitution.
