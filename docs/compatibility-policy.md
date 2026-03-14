# Compatibility Policy

Purpose: keep comment-resolution-engine aligned with the spectrum-systems constitution and fail early when drift is risky.

## Modes
- **strict** (default): schema/provenance/error-taxonomy drift or missing refs are errors; run stops. Rules/prompt gaps are also errors when declared in the manifest.
- **warn**: drift surfaces as warnings unless `--fail-on-drift` is set; structural mismatches (wrong system/source, missing manifest pins) always fail.

## Checks
- Manifest pins: `pinned_version|pinned_commit` must be present; `source_repo` must be `spectrum-systems`; `system_id` must be `SYS-001`.
- Artifacts: schema, prompt, rules profile, provenance, and error-taxonomy refs must exist; versions are compared to the engine’s declared versions.
- Rules: requested `--rules-profile` must be declared; manifest version is recorded alongside runtime version for provenance.

## When to fail
- Always fail on: missing manifest pins, system/source mismatch, absent provenance/error-taxonomy refs, or unreadable schema refs.
- Fail or warn on drift depending on `compatibility_mode` and `--fail-on-drift`.

## Reporting
- Compatibility report JSON captures findings, fingerprints (paths + hashes), and the active constitution context. Default location: `<output>_constitution_report.json` or `--constitution-report`.

## CI expectations
- CI should run `python -m comment_resolution_engine.cli --check-constitution --constitution config/constitution.yaml` to block incompatible changes before the pipeline executes.
