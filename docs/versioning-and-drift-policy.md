# Versioning and Drift Policy

## Pinning
- `config/constitution.yaml` pins SYS-001 to a specific spectrum-systems version/commit and enumerates referenced artifacts (schemas, prompts, rules profile, provenance guidance, error taxonomy).
- Pinned values should be updated intentionally with a recorded rationale in PR descriptions.

## Drift detection
- Fingerprints capture path + SHA-256 for each referenced artifact. Any missing file or version mismatch is treated as drift.
- Strict mode blocks drift; warn mode surfaces drift but allows runs unless `--fail-on-drift` is set.
- Rules/profile drift is recorded even when fallback heuristics are used, ensuring provenance shows the rule set in effect.

## Update workflow
1) Update manifest references and pinned_version/commit.
2) Run `python -m comment_resolution_engine.cli --check-constitution --constitution config/constitution.yaml`.
3) Run the full pipeline to ensure provenance stamping carries the new versions.

## Provenance stamping
- Each output record carries constitution source, pinned version/commit, schema/provenance/error-taxonomy versions, and rules profile/version.
- Compatibility reports should be kept with run artifacts to audit which constitution snapshot governed a run.
